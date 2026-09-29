"""Fib and trendline alerts on 30m / 4h / 1d / 1w / 1M - two Discord channels of their own.

Apart from the zone alerts on purpose: nothing here reads or writes the zone
scanner's state, records or webhooks, and nothing there reads this. It only
borrows scanner.py's watchlist, symbol names, price formatting, alert window
and Discord sender.

- Fib alerts (DISCORD_FIB_WEBHOOK_URL): price is inside Zone 1 or Zone 2 of the
  live fib, as indicator v12.3 draws it (fib_engine.py). Once per zone per fib -
  a new top or base is a new fib and can alert again.
- Trendline alerts (DISCORD_TRENDLINE_WEBHOOK_URL): price comes within
  TRENDLINE_TOUCH_PCT of a live trendline (indicator v11.0, trendlines.py), or a
  candle closes through one. A touch re-arms once price has left the band and a
  full candle has passed.

Both are built from CLOSED candles, like the chart's confirmed swings; the
candle still forming only supplies the current price.

    python fib_trendline_scanner.py            # one pass
    python fib_trendline_scanner.py --dry-run  # print alerts, send and save nothing
"""
import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

import fib_engine
import scanner
from config import (
    DELTA_API_BASE_URL,
    DISCORD_FIB_WEBHOOK_URL,
    DISCORD_TRENDLINE_WEBHOOK_URL,
    FIB_SWING_LENGTH,
    FIB_TL_TIMEFRAMES,
    SCAN_WORKERS,
    TRENDLINE_SWING_LENGTH,
    TRENDLINE_TOUCH_PCT,
    TRENDLINES_KEEP,
)
from trendlines import SUPPORT, build_trendlines

STATE_FILE = Path(__file__).with_name(os.getenv("VICTUS_FIB_TL_STATE_FILE", "fib_trendline_state.json"))
SEEDED_KEY = "__seeded__"
STATE_RETENTION_SECONDS = 120 * 24 * 3600

TF_SECONDS = {"30m": 1800, "4h": 14400, "1d": 86400, "1w": 7 * 86400, "1M": 31 * 86400}
TF_LABEL = {"30m": "30m", "4h": "4h", "1d": "1D", "1w": "1W", "1M": "1M"}
INTRADAY_BARS = 1500
DAILY_HISTORY_DAYS = 2000        # everything Delta India has (it starts Dec 2023)
MIN_BARS = 2 * max(FIB_SWING_LENGTH, TRENDLINE_SWING_LENGTH) + 2

FIB_ENV, TL_ENV = "DISCORD_FIB_WEBHOOK_URL", "DISCORD_TRENDLINE_WEBHOOK_URL"


# ----------------------------------------------------------------- candles

def _delta_candles(contract, resolution, start, end):
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(
                f"{DELTA_API_BASE_URL}/v2/history/candles",
                params={"symbol": contract, "resolution": resolution, "start": start, "end": end},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("success"):
                raise RuntimeError(payload)
            rows = sorted(payload.get("result") or [], key=lambda c: c["time"])
            return [
                [int(c["time"]), float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])]
                for c in rows
            ]
        except Exception as error:     # noqa: BLE001 - retried, then re-raised
            last_error = error
            time.sleep(1.5 * (attempt + 1))
    raise last_error


def monthly_from_daily(daily):
    """Calendar-month candles (UTC) from daily ones: [open_ts, o, h, l, c]."""
    months = []
    for ts, o, h, l, c in daily:
        day = datetime.fromtimestamp(ts, timezone.utc)
        key = (day.year, day.month)
        if months and months[-1][0] == key:
            m = months[-1][1]
            m[2], m[3], m[4] = max(m[2], h), min(m[3], l), c
        else:
            start = int(datetime(day.year, day.month, 1, tzinfo=timezone.utc).timestamp())
            months.append((key, [start, o, h, l, c]))
    return [m for _, m in months]


def candle_is_closed(open_ts, tf, now):
    if tf == "1M":
        start = datetime.fromtimestamp(open_ts, timezone.utc)
        year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
        return datetime(year, month, 1, tzinfo=timezone.utc).timestamp() <= now
    return open_ts + TF_SECONDS[tf] <= now


def fetch_all_timeframes(contract, timeframes, now):
    out = {}
    daily = None
    for tf in timeframes:
        if tf in ("1d", "1M"):
            if daily is None:
                daily = _delta_candles(contract, "1d", int(now) - DAILY_HISTORY_DAYS * 86400, int(now))
            out[tf] = daily if tf == "1d" else monthly_from_daily(daily)
        elif tf == "1w":
            out[tf] = _delta_candles(contract, "1w", int(now) - DAILY_HISTORY_DAYS * 86400, int(now))
        else:
            out[tf] = _delta_candles(contract, tf, int(now) - INTRADAY_BARS * TF_SECONDS[tf], int(now))
    return out


# ----------------------------------------------------------------- analysis

def fib_zones(d, base, top):
    """[(zone number, low, high, entry, sl)] for the live fib.

    Zone 2 is always the deeper one: the lower box on an up move, the upper
    box on a down move. Entry and SL are the inner fib of each box (EX 2/278):
    its 0.66 and 0.55 lines, SL on the 0.55.
    """
    u66, u55, d55, d66 = fib_engine.levels(base, top)
    (upper_entry, upper_sl), (lower_entry, lower_sl) = fib_engine.sl_lines(base, top, d)
    upper = (u55, u66, upper_entry, upper_sl)
    lower = (d66, d55, lower_entry, lower_sl)
    zone1, zone2 = (upper, lower) if d == 1 else (lower, upper)
    return [(1, *zone1), (2, *zone2)]


def analyse(symbol, tf, candles, now):
    """Everything alertable on one chart right now. Pure - no state, no sends."""
    if len(candles) < 2:
        return {"fib": [], "touch": [], "break": [], "bars": len(candles)}
    closed = candles[:-1] if not candle_is_closed(candles[-1][0], tf, now) else candles
    price = candles[-1][4]
    result = {"fib": [], "touch": [], "break": [], "bars": len(closed), "price": price}
    if len(closed) < MIN_BARS:
        return result

    times = [c[0] for c in closed]
    highs = [c[2] for c in closed]
    lows = [c[3] for c in closed]
    closes = [c[4] for c in closed]
    stamp = [datetime.fromtimestamp(t, scanner.IST).strftime("%Y-%m-%d %H:%M") for t in times]

    snaps, _ = fib_engine.run(stamp, highs, lows, N=FIB_SWING_LENGTH)
    live = snaps[-1]
    d, base, top = live["d"], live["O"], live["E"]
    inside_box = base < price < top if d == 1 else top < price < base
    if inside_box and base != top:
        for number, low, high, entry, sl in fib_zones(d, base, top):
            if low <= price <= high:
                result["fib"].append({
                    "key": f"fib|{symbol}|{tf}|{d}|{times[live['Ot']] if live['Ot'] is not None else base}|{top}|{number}",
                    "d": d, "zone": number, "low": low, "high": high, "entry": entry, "sl": sl,
                    "base": base, "top": top,
                    "base_time": stamp[live["Ot"]] if live["Ot"] is not None else None,
                    "top_time": stamp[live["Et"]],
                })

    lines = build_trendlines(highs, lows, closes, TRENDLINE_SWING_LENGTH, TRENDLINES_KEEP)
    now_bar = len(closed)               # the forming candle
    band = TRENDLINE_TOUCH_PCT.get(tf, 0.5)
    for line in lines:
        ident = f"{symbol}|{tf}|{line.kind}|{times[line.x1]}|{times[line.x2]}"
        info = {
            "kind": line.kind, "from": (line.y1, stamp[line.x1]), "to": (line.y2, stamp[line.x2]),
        }
        if line.alive:
            level = line.price_at(now_bar)
            if level <= 0:
                continue
            distance = (price - level) / level * 100
            if abs(distance) <= band:
                result["touch"].append({**info, "key": f"tl|{ident}", "level": level, "distance": distance})
        elif line.broken_at >= len(closed) - 2:
            result["break"].append({
                **info, "key": f"tlbreak|{ident}", "level": line.price_at(line.broken_at),
                "close": closes[line.broken_at], "time": stamp[line.broken_at],
            })
    return result


# ----------------------------------------------------------------- messages

def _fmt(value, places):
    return f"{value:.{places}f}"


def format_fib_alert(symbol, tf, price, z):
    places = scanner.price_decimals(z["entry"])
    side = "LONG" if z["d"] == 1 else "SHORT"
    deeper = " (deeper zone)" if z["zone"] == 2 else ""
    sl_pct = abs(z["entry"] - z["sl"]) / z["entry"] * 100
    return (
        f"{scanner.alert_symbol(symbol)} | FIB ZONE {z['zone']} | {TF_LABEL[tf]} | {side}\n"
        f"Price: {_fmt(price, places)}\n"
        f"Zone {z['zone']}: {_fmt(z['low'], places)} - {_fmt(z['high'], places)}{deeper}\n"
        f"Entry: {_fmt(z['entry'], places)} | SL: {_fmt(z['sl'], places)} | {sl_pct:.2f}%\n"
        f"Fib: {_fmt(z['base'], places)} -> {_fmt(z['top'], places)}"
    )


def format_touch_alert(symbol, tf, price, t):
    places = scanner.price_decimals(t["level"])
    name = "SUPPORT" if t["kind"] == SUPPORT else "RESISTANCE"
    side = "above" if t["distance"] >= 0 else "below"
    return (
        f"{scanner.alert_symbol(symbol)} | {name} TRENDLINE | {TF_LABEL[tf]}\n"
        f"Price: {_fmt(price, places)} | {abs(t['distance']):.2f}% {side} the line\n"
        f"Line now: {_fmt(t['level'], places)}\n"
        f"Drawn: {_fmt(t['from'][0], places)} ({t['from'][1]}) -> {_fmt(t['to'][0], places)} ({t['to'][1]})"
    )


def format_break_alert(symbol, tf, b):
    places = scanner.price_decimals(b["level"])
    name = "SUPPORT" if b["kind"] == SUPPORT else "RESISTANCE"
    side = "below" if b["kind"] == SUPPORT else "above"
    return (
        f"{scanner.alert_symbol(symbol)} | {name} TRENDLINE BROKEN | {TF_LABEL[tf]}\n"
        f"Close {_fmt(b['close'], places)} {side} the line at {_fmt(b['level'], places)} ({b['time']} IST)\n"
        f"Drawn: {_fmt(b['from'][0], places)} ({b['from'][1]}) -> {_fmt(b['to'][0], places)} ({b['to'][1]})"
    )


# ----------------------------------------------------------------- state + sending

def load_state():
    try:
        with STATE_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state, now):
    for key in [k for k, v in state.items() if isinstance(v, dict) and now - v.get("seen", now) > STATE_RETENTION_SECONDS]:
        del state[key]
    tmp = STATE_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=1, sort_keys=True)
    os.replace(tmp, STATE_FILE)


def plan_alerts(state, symbol, tf, analysis, now):
    """(channel, key, message) for what is new since the last pass; updates touch bands."""
    planned = []
    price = analysis.get("price")
    for z in analysis["fib"]:
        if z["key"] not in state:
            planned.append(("fib", z["key"], format_fib_alert(symbol, tf, price, z)))
        else:
            state[z["key"]]["seen"] = now   # still true: keep it from being pruned
    for b in analysis["break"]:
        if b["key"] not in state:
            planned.append(("trendline", b["key"], format_break_alert(symbol, tf, b)))

    in_band = {t["key"] for t in analysis["touch"]}
    prefix = f"tl|{symbol}|{tf}|"
    for key, entry in state.items():
        if key.startswith(prefix) and key not in in_band and isinstance(entry, dict):
            entry["in_band"] = False     # left the band: the next touch may alert
    for t in analysis["touch"]:
        entry = state.get(t["key"])
        if entry is None or (not entry.get("in_band") and now - entry.get("sent", 0) >= TF_SECONDS[tf]):
            planned.append(("trendline", t["key"], format_touch_alert(symbol, tf, price, t)))
        elif entry is not None:
            entry["in_band"] = True
            entry["seen"] = now
    return planned


def mark_sent(state, key, now):
    state[key] = {"sent": now, "seen": now, "in_band": key.startswith("tl|")}


def send(channel, message):
    env, fallback = (FIB_ENV, DISCORD_FIB_WEBHOOK_URL) if channel == "fib" else (TL_ENV, DISCORD_TRENDLINE_WEBHOOK_URL)
    try:
        return scanner.send_discord_message(message, webhook_env_name=env, webhook_config_value=fallback)
    except requests.RequestException as error:
        print(f"Discord {channel} alert failed: {error}")
        return False


# ----------------------------------------------------------------- main

def scan_symbol(symbol, timeframes, now):
    contract = scanner.delta_contract(symbol)
    if contract is None:
        return symbol, None, "not a Delta contract"
    try:
        charts = fetch_all_timeframes(contract, timeframes, now)
        return symbol, {tf: analyse(symbol, tf, charts[tf], now) for tf in timeframes}, None
    except Exception as error:         # noqa: BLE001 - one bad symbol must not stop the pass
        return symbol, None, str(error)


def run_once(dry_run=False):
    now = time.time()
    timeframes = [tf for tf in FIB_TL_TIMEFRAMES if tf in TF_SECONDS]
    symbols = scanner.active_watchlist()
    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
        results = list(pool.map(lambda s: scan_symbol(s, timeframes, now), symbols))

    state = load_state()
    # Per channel: {"fib": ts, "trendline": ts}, set by the first pass that
    # channel's webhook was configured for.
    seeded = state.setdefault(SEEDED_KEY, {})
    configured = {
        "fib": bool(scanner.get_env_or_config(FIB_ENV, DISCORD_FIB_WEBHOOK_URL)),
        "trendline": bool(scanner.get_env_or_config(TL_ENV, DISCORD_TRENDLINE_WEBHOOK_URL)),
    }
    seeding = {c for c, ok in configured.items() if ok and c not in seeded}
    awake = scanner.in_alert_window()
    counts = {"fib": 0, "trendline": 0}
    failures = []
    for symbol, analyses, error in results:
        if analyses is None:
            failures.append(f"{symbol}: {error}")
            continue
        for tf, analysis in analyses.items():
            for channel, key, message in plan_alerts(state, symbol, tf, analysis, now):
                if dry_run:
                    print(f"[{channel}] {message}\n")
                    continue
                if not configured[channel]:
                    continue             # nothing recorded: no webhook, no channel yet
                if channel in seeding:
                    # First pass with this channel's webhook: everything already
                    # in a zone or at a line is old news. Record it silently
                    # instead of posting dozens at once.
                    mark_sent(state, key, now)
                    counts[channel] += 1
                    continue
                if not awake:
                    continue             # held - it alerts later if it is still true
                print(f"[{channel}] {message}\n")
                if send(channel, message):
                    mark_sent(state, key, now)
                    counts[channel] += 1

    print(
        f"Fib/trendline pass: {len(symbols) - len(failures)}/{len(symbols)} symbols, "
        f"timeframes {', '.join(timeframes)}; fib {counts['fib']}, trendline {counts['trendline']}"
        + (f" (seeded, not sent: {', '.join(sorted(seeding))})" if seeding else "")
        + ("" if awake else " - outside alert window, holding")
    )
    for channel, ok in configured.items():
        if not ok:
            print(f"{FIB_ENV if channel == 'fib' else TL_ENV} is not configured - {channel} alerts off.")
    for line in failures:
        print(f"  failed {line}")

    if dry_run:
        return
    for channel in sorted(seeding):
        seeded[channel] = now
        scanner.send_status_message(
            f"{channel.capitalize()} alerts started. Seeded silently: {counts[channel]} "
            f"{'fib zones' if channel == 'fib' else 'trendlines'} price was already at. "
            "Only new ones will alert from here."
        )
    if failures and len(failures) == len(symbols):
        raise RuntimeError("every symbol failed: " + "; ".join(failures[:3]))
    save_state(state, now)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print what would alert; send and save nothing")
    args = parser.parse_args(argv)
    run_once(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
