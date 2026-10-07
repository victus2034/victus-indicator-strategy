"""Fib and trendline alerts on 4H / 1D / 1W / 1M (30m off), crypto and NSE - two Discord channels of their own.

Apart from the zone alerts on purpose: nothing here reads or writes the zone
scanners' state, records or webhooks, and nothing there reads this. It only
borrows their watchlists, symbol names, price formatting, alert window and
Discord sender.

- Fib alerts (DISCORD_FIB_WEBHOOK_URL): price is within FIB_TL_MAX_DISTANCE_PCT
  (0.75%) of Zone 1 or Zone 2 of the live fib, down to inside it, as indicator
  v12.3 draws it (fib_engine.py). Once per zone per fib - a new top or base is a
  new fib and can alert again.
- Trendline alerts (DISCORD_TRENDLINE_WEBHOOK_URL): price is within the same
  0.75% of a live trendline (indicator v11.0, trendlines.py), or a candle closes
  through one. A touch re-arms once price has left the band and a full candle
  has passed.

Crypto (Delta) scans on every pass, inside the 08:00-01:00 IST alert window.
NSE (Yahoo, the zone scanner's 200 stocks) scans during the session only,
every NSE_MIN_INTERVAL_SECONDS. Both post to the same two channels, the market
named on each alert.

Levels come from CLOSED candles, like the chart's confirmed swings; the candle
still forming only supplies the current price. Every fib and trendline-touch
alert that is sent is also written to RECORDS_FILE with its entry and SL, which
fib_trendline_daily_report.py scores once a day.

    python fib_trendline_scanner.py                        # one pass
    python fib_trendline_scanner.py --dry-run              # print alerts, send and save nothing
    python fib_trendline_scanner.py --dry-run --force-nse  # include NSE outside the session
"""
import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import requests

import bitunix_data
import fib_engine
import fib_trendline_trades as trades
import scanner
from config import (
    DISCORD_FIB_WEBHOOK_URL,
    DISCORD_TRENDLINE_WEBHOOK_URL,
    FIB_SWING_LENGTH,
    FIB_TL_MAX_DISTANCE_PCT,
    FIB_TL_MIN_DISTANCE_PCT,
    FIB_TL_TIMEFRAMES,
    SCAN_WORKERS,
    TRENDLINE_SWING_LENGTH,
    TRENDLINES_KEEP,
)
from fib_trendline_data import (
    CRYPTO, IST, NSE, TF_LABEL, TF_SECONDS, candle_close_ts, candle_is_closed, crypto_charts, nse_charts,
)
from trendlines import SUPPORT, build_trendlines

STATE_FILE = Path(__file__).with_name(os.getenv("VICTUS_FIB_TL_STATE_FILE", "fib_trendline_state.json"))
RECORDS_FILE = Path(__file__).with_name(os.getenv("VICTUS_FIB_TL_RECORDS_FILE", "fib_trendline_alert_records.jsonl"))
SEEDED_KEY = "__seeded__"
ATTEMPTS_KEY = "__attempts__"
RETRY_BACKOFF_SECONDS = 30 * 60   # a failed Discord send is not retried sooner than this
# Bumped when what counts as an alert changes, so the first pass under the new
# rule seeds silently instead of posting everything the new rule now catches.
# v2 (2026-09-29): 0-1.5% band instead of inside-zone / per-timeframe touch.
# v3 (2026-09-29): full history for 4H and NSE daily+ - some live fibs get a new
# base/top, i.e. a new key, and would otherwise all post as new on the first pass.
# v4 (2026-10-07): v12.5 trendline anchors - most live lines get a new start point.
SEED_VERSION = "v4"
# Bitunix candles draw different fibs and lines, each a new key: turning the
# source on re-seeds silently rather than posting every level already in range.
if bitunix_data.CRYPTO_CANDLE_SOURCE == "bitunix":
    SEED_VERSION += "-bitunix"
NSE_LAST_SCAN_KEY = "__nse_last_scan__"
# {market: when that market was last scanned with alerts awake}. A BROKEN alert
# goes out only on the first scans after the breaking candle closed: once a pass
# has run after that, a break seen later is old news (Lakky, 2026-10-05 - PFIZER's
# 1M break on September's close posted on Oct 5, four sessions late, while the
# other 1M breaks went out on Oct 1).
LAST_SCAN_KEY = "__last_scan__"
BREAK_GRACE_SECONDS = 3600      # a symbol whose data was missing for a pass can still catch up within this
NSE_MIN_INTERVAL_SECONDS = 8 * 60
STATE_RETENTION_SECONDS = 120 * 24 * 3600
MIN_BARS = 2 * max(FIB_SWING_LENGTH, TRENDLINE_SWING_LENGTH) + 2
MARKET_LABEL = {CRYPTO: "Crypto", NSE: "NSE"}

FIB_ENV, TL_ENV = "DISCORD_FIB_WEBHOOK_URL", "DISCORD_TRENDLINE_WEBHOOK_URL"


def webhook_env(channel, market):
    """The channel's webhook for one market, e.g. DISCORD_FIB_NSE_WEBHOOK_URL.

    FIB_ENV / TL_ENV stay as the shared fallback, so a market with no channel of
    its own yet keeps posting where it did.
    """
    return f"DISCORD_{'FIB' if channel == 'fib' else 'TRENDLINE'}_{market.upper()}_WEBHOOK_URL"


def webhook_url(channel, market):
    shared = scanner.get_env_or_config(
        FIB_ENV if channel == "fib" else TL_ENV,
        DISCORD_FIB_WEBHOOK_URL if channel == "fib" else DISCORD_TRENDLINE_WEBHOOK_URL,
    )
    return scanner.get_env_or_config(webhook_env(channel, market), shared)


# ----------------------------------------------------------------- geometry (shared with the backtest)

def fib_zones(d, base, top):
    """[{zone, low, high, entry, sl}] for the live fib.

    Zone 2 is always the deeper one: the lower box on an up move, the upper
    box on a down move. Entry is the zone's near edge - the one price reaches
    first - and SL the inner fib's 0.55 line, as in Shiva's EX 2/278 ETH trades:
    entry 2723.94 / SL 2711.79 (zone 1), 2672.86 / 2660.74 (zone 2).
    """
    u66, u55, d55, d66 = fib_engine.levels(base, top)
    (_, upper_sl), (_, lower_sl) = fib_engine.sl_lines(base, top, d)
    upper = dict(low=u55, high=u66, sl=upper_sl)
    lower = dict(low=d66, high=d55, sl=lower_sl)
    for zone in (upper, lower):
        zone["entry"] = zone["high"] if d == 1 else zone["low"]
    zone1, zone2 = (upper, lower) if d == 1 else (lower, upper)
    return [dict(zone=1, **zone1), dict(zone=2, **zone2)]


def fib_distance(d, zone, price):
    """% from price down to (long) / up to (short) the zone; 0 inside; None once past it.

    Also None once price is through the zone's stop. The SL line sits inside
    the zone (the inner fib's 0.55), so "inside the zone" used to include
    price already below a long's stop: 54 of the first 213 live fib alerts
    were sent that way, and every one was scored a -1R the moment it filled.
    """
    sl = zone.get("sl")
    if sl is not None and ((price <= sl) if d == 1 else (price >= sl)):
        return None
    if d == 1:
        if price > zone["high"]:
            return (price - zone["high"]) / zone["high"] * 100
        return 0.0 if price >= zone["low"] else None
    if price < zone["low"]:
        return (zone["low"] - price) / zone["low"] * 100
    return 0.0 if price <= zone["high"] else None


def line_distance(kind, level, price):
    """% from price to the line on the side it approaches from; negative = through it."""
    if kind == SUPPORT:
        return (price - level) / level * 100
    return (level - price) / level * 100


def in_band(distance):
    """FIB_TL_MAX_DISTANCE_PCT (0.75%) away down to 0.00% (Shiva). Never beyond 0: a fib zone price has gone
    through is None already, and price through a trendline before the candle
    closes is a break in progress - alerting it as a BUY at support (as the
    first version did, calling it "0.00%") pointed the wrong way. A close
    through the line has its own BROKEN alert."""
    return distance is not None and FIB_TL_MIN_DISTANCE_PCT <= distance <= FIB_TL_MAX_DISTANCE_PCT


# ----------------------------------------------------------------- analysis

def current_price(charts):
    """The close of the freshest candle across a symbol's timeframes.

    Each timeframe's own last close would do on Delta, but Yahoo's daily and
    weekly candles can lag the intraday ones; one price for all timeframes means
    a 1W level is judged against the same price as a 4H one.
    """
    last = [c[-1] for c in charts.values() if c]
    return max(last, key=lambda c: c[0])[4] if last else None


def analyse(market, symbol, tf, candles, now, price=None):
    """Everything alertable on one chart right now. Pure - no state, no sends."""
    result = {"fib": [], "touch": [], "break": [], "bars": 0, "price": None}
    if len(candles) < 2:
        return result
    closed = candles if candle_is_closed(market, candles[-1][0], tf, now) else candles[:-1]
    price = candles[-1][4] if price is None else price
    result.update(bars=len(closed), price=price)
    if len(closed) < MIN_BARS:
        return result

    times = [c[0] for c in closed]
    highs = [c[2] for c in closed]
    lows = [c[3] for c in closed]
    closes = [c[4] for c in closed]
    stamp = [datetime.fromtimestamp(t, IST).strftime("%Y-%m-%d %H:%M") for t in times]

    snaps, _ = fib_engine.run(stamp, highs, lows, N=FIB_SWING_LENGTH)
    live = snaps[-1]
    d, base, top = live["d"], live["O"], live["E"]
    inside_box = base < price < top if d == 1 else top < price < base
    if inside_box and base != top:
        for zone in fib_zones(d, base, top):
            distance = fib_distance(d, zone, price)
            if in_band(distance):
                result["fib"].append({
                    **zone, "key": f"fib|{symbol}|{tf}|{d}|{times[live['Ot']]}|{top}|{zone['zone']}",
                    "d": d, "base": base, "top": top, "distance": distance,
                    "plan": trades.fib_plan(d, zone),
                })

    lines = build_trendlines(highs, lows, closes, TRENDLINE_SWING_LENGTH, TRENDLINES_KEEP)
    now_bar = len(closed)               # the forming candle
    for line in lines:
        ident = f"{symbol}|{tf}|{line.kind}|{times[line.x1]}|{times[line.x2]}"
        info = {"kind": line.kind, "from": (line.y1, stamp[line.x1]), "to": (line.y2, stamp[line.x2])}
        if line.alive:
            level = line.price_at(now_bar)
            if level <= 0:
                continue
            distance = line_distance(line.kind, level, price)
            if in_band(distance):
                result["touch"].append({
                    **info, "key": f"tl|{ident}", "level": level, "distance": distance,
                    "plan": trades.trendline_plan(line.kind == SUPPORT, level, tf),
                })
        elif line.broken_at >= len(closed) - 2:
            result["break"].append({
                **info, "key": f"tlbreak|{ident}", "level": line.price_at(line.broken_at),
                "close": closes[line.broken_at], "time": stamp[line.broken_at],
                "closed_at": candle_close_ts(market, times[line.broken_at], tf),
            })
    return result


# ----------------------------------------------------------------- messages

def display(market, symbol):
    if market == NSE:
        return symbol[:-3] if symbol.upper().endswith(".NS") else symbol
    return scanner.alert_symbol(symbol)


def _fmt(value, places):
    return f"{value:.{places}f}"


def _header(market, tf):
    return f"Timeframe: {TF_LABEL[tf]} | {MARKET_LABEL[market]}"


def zone_name(d, number):
    """Shiva reads the chart as upper and lower zone, not 1 and 2 (2026-09-29).

    Zone 1 is the upper box on an up move and the lower one on a down move;
    Zone 2, the deeper one, the other. The numbers stay underneath - in the
    state keys, the records and the backtest - so renaming re-alerts nothing.
    """
    return "UPPER" if (number == 1) == (d == 1) else "LOWER"


def format_fib_alert(market, symbol, tf, price, z):
    places = scanner.price_decimals(z["entry"])
    side = "LONG" if z["d"] == 1 else "SHORT"
    name = zone_name(z["d"], z["zone"])
    deeper = " (deeper)" if z["zone"] == 2 else ""
    where = "inside the zone" if z["distance"] <= 0 else f"{z['distance']:.2f}% away"
    return (
        f"{display(market, symbol)} | FIB {name} ZONE | {side}\n"
        f"{_header(market, tf)}\n"
        f"Price: {_fmt(price, places)} | {where}\n"
        # Upper/lower names the zone, top/bottom its edges (Shiva, 2026-09-29).
        f"{name.capitalize()} zone: bottom {_fmt(z['low'], places)} - top {_fmt(z['high'], places)}{deeper}\n"
        f"Entry: {_fmt(z['entry'], places)} (zone {'top' if z['d'] == 1 else 'bottom'}) | "
        f"SL: {_fmt(z['sl'], places)} | {trades.risk_pct(z['plan']):.2f}%\n"
        f"Fib: {_fmt(z['base'], places)} -> {_fmt(z['top'], places)}"
    )


def format_touch_alert(market, symbol, tf, price, t):
    places = scanner.price_decimals(t["level"])
    support = t["kind"] == SUPPORT
    name, side = ("SUP", "BUY") if support else ("RES", "SELL")
    where = f"{t['distance']:.2f}% {'above' if support else 'below'} the line"
    return (
        f"{display(market, symbol)} | {name} TL | {side}\n"
        f"{_header(market, tf)}\n"
        f"Price: {_fmt(price, places)} | {where}\n"
        f"Entry (line): {_fmt(t['level'], places)} | SL: {_fmt(t['plan']['sl'], places)} | "
        f"{trades.risk_pct(t['plan']):.2f}%\n"
        f"Drawn: {_fmt(t['from'][0], places)} ({t['from'][1]}) -> {_fmt(t['to'][0], places)} ({t['to'][1]})"
    )


def format_break_alert(market, symbol, tf, b):
    places = scanner.price_decimals(b["level"])
    name = "SUP" if b["kind"] == SUPPORT else "RES"
    side = "below" if b["kind"] == SUPPORT else "above"
    return (
        f"{display(market, symbol)} | {name} TL BR\n"
        f"{_header(market, tf)}\n"
        f"Close {_fmt(b['close'], places)} {side} the line at {_fmt(b['level'], places)} ({b['time']} IST)\n"
        f"Drawn: {_fmt(b['from'][0], places)} ({b['from'][1]}) -> {_fmt(b['to'][0], places)} ({b['to'][1]})"
    )


# ----------------------------------------------------------------- state, records, sending

def load_state():
    try:
        with STATE_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


# A sent key is kept at least this many candles of its own timeframe. The flat
# 120 days was shorter than a 1W or 1M level can sit untouched, so a weekly or
# monthly fib zone price came back to after four months alerted a second time.
RETENTION_CANDLES = 60


def retention_seconds(key):
    parts = str(key).split("|")
    tf = parts[2] if len(parts) > 2 else None
    return max(STATE_RETENTION_SECONDS, TF_SECONDS.get(tf, 0) * RETENTION_CANDLES)


def save_state(state, now):
    for key in [k for k, v in state.items()
                if isinstance(v, dict) and "sent" in v and now - v.get("seen", now) > retention_seconds(k)]:
        del state[key]
    tmp = STATE_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=1, sort_keys=True)
    os.replace(tmp, STATE_FILE)


def break_is_fresh(b, last_scan):
    """True unless a pass already ran (with alerts awake) after the breaking candle closed."""
    return last_scan is None or b.get("closed_at") is None or b["closed_at"] >= last_scan - BREAK_GRACE_SECONDS


def plan_alerts(state, market, symbol, tf, analysis, now, last_scan=None):
    """[(channel, key, message, record)] for what is new since the last pass; updates touch bands.

    last_scan: when this market was last scanned awake - a break older than that is not sent.
    """
    planned = []
    price = analysis.get("price")
    base = {"market": market, "symbol": symbol, "tf": tf, "price": price}
    for z in analysis["fib"]:
        if z["key"] not in state:
            record = {**base, "kind": "fib", "plan": z["plan"], "zone": z["zone"]}
            planned.append(("fib", z["key"], format_fib_alert(market, symbol, tf, price, z), record))
        else:
            state[z["key"]]["seen"] = now   # still true: keep it from being pruned
    for b in analysis["break"]:
        if b["key"] not in state and break_is_fresh(b, last_scan):
            planned.append(("trendline", b["key"], format_break_alert(market, symbol, tf, b), None))

    in_band_now = {t["key"] for t in analysis["touch"]}
    prefix = f"tl|{symbol}|{tf}|"
    for key, entry in state.items():
        if key.startswith(prefix) and key not in in_band_now and isinstance(entry, dict):
            entry["in_band"] = False     # left the band: the next touch may alert
    for t in analysis["touch"]:
        entry = state.get(t["key"])
        if entry is None or (not entry.get("in_band") and now - entry.get("sent", 0) >= TF_SECONDS[tf]):
            record = {**base, "kind": "trendline", "plan": t["plan"], "line": t["kind"]}
            planned.append(("trendline", t["key"], format_touch_alert(market, symbol, tf, price, t), record))
        else:
            entry["in_band"] = True
            entry["seen"] = now
    return planned


def mark_sent(state, key, now):
    state[key] = {"sent": now, "seen": now, "in_band": key.startswith("tl|")}


def append_record(record, key, now):
    row = {**record, "id": f"{key}@{int(now)}", "key": key, "sent_ts": int(now)}
    with RECORDS_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row) + "\n")


def send(channel, message, market):
    try:
        return scanner.send_discord_message(
            message, webhook_env_name=webhook_env(channel, market),
            webhook_config_value=webhook_url(channel, market),
        )
    except requests.RequestException as error:
        print(f"Discord {channel} alert failed: {error}")
        return False


# ----------------------------------------------------------------- markets

def scan_crypto(timeframes, now):
    def one(symbol):
        contract = scanner.delta_contract(symbol)
        if contract is None:
            return symbol, None, "not a Delta contract"
        try:
            source = "bitunix" if bitunix_data.uses_bitunix(symbol) else "delta"
            try:
                charts = crypto_charts(contract, timeframes, now, source=source)
            except Exception as error:     # noqa: BLE001 - Bitunix down: Delta still draws the levels
                if source == "delta":
                    raise
                print(f"{symbol} Bitunix charts unavailable, using Delta: {str(error)[:80]}")
                charts = crypto_charts(contract, timeframes, now)
            price = current_price(charts)
            return symbol, {tf: analyse(CRYPTO, symbol, tf, charts[tf], now, price) for tf in timeframes}, None
        except Exception as error:     # noqa: BLE001 - one bad symbol must not stop the pass
            return symbol, None, str(error)

    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
        return list(pool.map(one, scanner.active_watchlist()))


def nse_session_open(now):
    import nse_scanner
    import pandas as pd

    is_open, *_ = nse_scanner.market_window_status(pd.Timestamp.fromtimestamp(now, tz=IST))
    return is_open


def scan_nse(timeframes, now):
    import nse_scanner

    symbols = nse_scanner.load_watchlist()
    charts = nse_charts(symbols, timeframes)
    today = datetime.fromtimestamp(now, IST).date()
    intraday = next((tf for tf in ("30m", "4h") if tf in timeframes), None)
    fresh = sum(1 for s in symbols if intraday and charts[s].get(intraday)
                and datetime.fromtimestamp(charts[s][intraday][-1][0], IST).date() == today)
    if intraday and fresh < len(symbols) / 2:
        print(f"NSE: only {fresh}/{len(symbols)} symbols have today's candles - holiday or stale feed, skipping")
        return []
    results = []
    for symbol in symbols:
        try:
            price = current_price(charts[symbol])
            results.append((symbol, {tf: analyse(NSE, symbol, tf, charts[symbol][tf], now, price)
                                     for tf in timeframes}, None))
        except Exception as error:     # noqa: BLE001
            results.append((symbol, None, str(error)))
    return results


# ----------------------------------------------------------------- main

def run_once(dry_run=False, force_nse=False):
    now = time.time()
    timeframes = [tf for tf in FIB_TL_TIMEFRAMES if tf in TF_LABEL]
    state = load_state()

    markets = {CRYPTO: scan_crypto(timeframes, now)}
    nse_due = now - state.get(NSE_LAST_SCAN_KEY, 0) >= NSE_MIN_INTERVAL_SECONDS
    if force_nse or (nse_due and nse_session_open(now)):
        markets[NSE] = scan_nse(timeframes, now)
        if not dry_run:
            state[NSE_LAST_SCAN_KEY] = now

    seeded = state.get(SEEDED_KEY)
    if not isinstance(seeded, dict):
        seeded = {}
    state[SEEDED_KEY] = seeded
    attempts = state.get(ATTEMPTS_KEY)
    if not isinstance(attempts, dict):
        attempts = {}
    state[ATTEMPTS_KEY] = attempts
    for key in [k for k, t in attempts.items() if now - t > STATE_RETENTION_SECONDS]:
        del attempts[key]
    configured = {(channel, market): bool(webhook_url(channel, market))
                  for channel in ("fib", "trendline") for market in (CRYPTO, NSE)}
    awake = {CRYPTO: scanner.in_alert_window(), NSE: True}   # NSE only scans in session
    last_scans = state.get(LAST_SCAN_KEY)
    if not isinstance(last_scans, dict):
        last_scans = {}
    state[LAST_SCAN_KEY] = last_scans
    previous_scan = dict(last_scans)
    seeding = {
        (channel, market)
        for market, results in markets.items() if results
        for channel in ("fib", "trendline")
        if configured[(channel, market)] and f"{channel}:{market}:{SEED_VERSION}" not in seeded
    }
    counts = {}
    failures = []
    for market, results in markets.items():
        for symbol, analyses, error in results:
            if analyses is None:
                failures.append(f"{market} {symbol}: {error}")
                continue
            for tf, analysis in analyses.items():
                for channel, key, message, record in plan_alerts(state, market, symbol, tf, analysis, now,
                                                                 previous_scan.get(market)):
                    if dry_run:
                        print(f"[{channel}] {message}\n")
                        continue
                    if not configured[(channel, market)]:
                        continue             # nothing recorded: no webhook, no channel yet
                    tally = (channel, market)
                    if tally in seeding:
                        # First pass under this rule with this webhook: everything
                        # already in range is old news. Record it silently instead
                        # of posting dozens at once.
                        mark_sent(state, key, now)
                        counts[tally] = counts.get(tally, 0) + 1
                        continue
                    if not awake[market]:
                        continue             # held - it alerts later if it is still true
                    if now - attempts.get(key, 0) < RETRY_BACKOFF_SECONDS:
                        continue             # the last send failed: wait out the backoff
                    print(f"[{channel}] {message}\n")
                    if send(channel, message, market):
                        attempts.pop(key, None)
                        mark_sent(state, key, now)
                        if record:
                            append_record(record, key, now)
                        counts[tally] = counts.get(tally, 0) + 1
                        # Saved per alert: a crash later in this pass must not
                        # send the ones already posted again.
                        save_state(state, now)
                    else:
                        attempts[key] = now  # stays out of state so it still alerts once Discord is back

    if not dry_run:
        for market, results in markets.items():
            if results and awake[market]:
                last_scans[market] = now

    for market, results in markets.items():
        ok = sum(1 for _, a, _ in results if a is not None)
        sent = ", ".join(f"{c} {counts.get((c, market), 0)}" for c in ("fib", "trendline"))
        print(f"{MARKET_LABEL[market]}: {ok}/{len(results)} symbols, timeframes {', '.join(timeframes)}; {sent}"
              + (f" (seeded, not sent: {', '.join(sorted(c for c, m in seeding if m == market))})"
                 if any(m == market for _, m in seeding) else ""))
    if not awake[CRYPTO]:
        print("Crypto: outside the alert window, holding")
    for (channel, market), ok in configured.items():
        if not ok and market in markets:
            print(f"{webhook_env(channel, market)} is not configured - {MARKET_LABEL[market]} {channel} alerts off.")
    for line in failures[:20]:
        print(f"  failed {line}")

    if dry_run:
        return
    for channel, market in sorted(seeding):
        seeded[f"{channel}:{market}:{SEED_VERSION}"] = now
        scanner.send_status_message(
            f"{channel.capitalize()} alerts ({MARKET_LABEL[market]}, 0-{FIB_TL_MAX_DISTANCE_PCT:g}% band) started. "
            f"Seeded silently: {counts.get((channel, market), 0)} "
            f"{'fib zones' if channel == 'fib' else 'trendlines'} price was already within range. "
            "Only new ones will alert from here."
        )
    # Saved before anything that can raise: the alerts above are already in
    # Discord, and a crash here would otherwise send them all again next pass.
    save_state(state, now)
    try:
        import fib_trendline_daily_report
        fib_trendline_daily_report.maybe_send(state, now)
        save_state(state, now)
    except Exception as error:     # noqa: BLE001 - the report retries next pass
        print(f"daily fib/trendline report failed: {error}")
    crypto_results = markets[CRYPTO]
    if crypto_results and all(a is None for _, a, _ in crypto_results):
        raise RuntimeError("every crypto symbol failed: " + "; ".join(failures[:3]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print what would alert; send and save nothing")
    parser.add_argument("--force-nse", action="store_true", help="scan NSE even outside the session")
    args = parser.parse_args(argv)
    run_once(dry_run=args.dry_run, force_nse=args.force_nse)


if __name__ == "__main__":
    main()
