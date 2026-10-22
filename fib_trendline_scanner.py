"""Fib and trendline alerts on 4H / 1D / 1W / 1M (30m off), crypto and NSE - two Discord channels of their own.

Apart from the zone alerts on purpose: nothing here reads or writes the zone
scanners' state, records or webhooks, and nothing there reads this. It only
borrows their watchlists, symbol names, price formatting, alert window and
Discord sender.

- Fib alerts (DISCORD_FIB_WEBHOOK_URL): price is within FIB_TL_MAX_DISTANCE_PCT
  (0.75%) of the live fib's deeper (strong) zone, down to its near edge
  (FIB_ALERT_LEVELS since 2026-10-20: 4H L2-L4, 1D+ L1-L4; fib_engine.py). Stop = the S/R zone rule. Once per zone per
  fib - a new top or base is a new fib and can alert again.
- Trendline alerts (DISCORD_TRENDLINE_WEBHOOK_URL): price is within the same
  0.75% of a live trendline (indicator v12.6 anchors, trendlines.py), or a
  candle closes through one. A touch re-arms once price has left the band and a
  full candle has passed.

Crypto and xStocks (Bitunix; XAUT and SLVON on Delta) scan on every pass, inside
the 08:00-01:00 IST alert window. NSE (Yahoo, the zone scanner's 200 stocks)
scans during the session only, every NSE_MIN_INTERVAL_SECONDS. Each market can
have its own pair of channels (DISCORD_{FIB,TRENDLINE}_{CRYPTO,NSE}_WEBHOOK_URL).

- S/R zone alerts on 1D / 1W / 1M (ZONE_HTF_TIMEFRAMES, lakky 2026-10-16): the zone
  scanner's engine and rules (nearest zone per side, too young, over-touched, stop
  too wide, approach side, MAX_DISTANCE_PCT band, 4h cooldown, crypto daily trend)
  on these charts, posted to the old 30m zone channels (DISCORD_30M_WEBHOOK_URL,
  DISCORD_NSE_30M_WEBHOOK_URL) and scored like fib alerts.

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
    CRYPTO_WATCHLIST,
    DISCORD_FIB_WEBHOOK_URL,
    DISCORD_TRENDLINE_WEBHOOK_URL,
    FIB_ALERT_LEVELS,
    FIB_ALERT_ZONES,  # noqa: F401 - the backtest test compares it
    FIB_SL_HEIGHT_PCT,
    FIB_SWING_LENGTH,
    FIB_TL_BREAK_SKIP_LEVELS,
    FIB_TL_BREAK_SKIP_MARKETS,
    FIB_TL_BREAK_SKIP_SECONDS,
    FIB_TL_MAX_DISTANCE_PCT,
    FIB_TL_MIN_DISTANCE_PCT,
    FIB_TL_TIMEFRAMES,
    RISK_WARN_MARKET_MIN_AGAINST,
    RISK_WARN_MARKET_SYMBOLS,
    RISK_WARN_MOVE_PCT,
    SCAN_WORKERS,
    TRENDLINE_SWING_LENGTH,
    TRENDLINES_KEEP,
    ZONE_HTF_TIMEFRAMES,
    alert_band_pct,
)
from fib_trendline_data import (
    CRYPTO, IST, NSE, TF_LABEL, TF_SECONDS, candle_close_ts, candle_is_closed, crypto_charts, nse_charts,
    nse_download,
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
# v5 (2026-10-07): v12.6 trendlines - lower lows get lines from the last swing below.
# v6 (2026-10-08): deeper fib zone only, stop beyond the box - a zone price sits
# in below the old (inner) stop alerts now.
# v7 (2026-10-09): xStocks drawn from Bitunix - their fibs and lines get new keys.
# v8 (2026-10-13): a fib dies once price trades past L4 (fib_engine, v12.7.10) -
# many live fibs get a new base/top.
# v9 (2026-10-13): past the strong box's stop, not L4 (v12.7.11).
# v10 (2026-10-13): a fib just born from a stop kill is not stop-killed (v12.7.12).
# Not bumped for the 3% band on 1W / 1M (2026-10-21): the first pass then sends the 1W / 1M
# levels already within 3% once - the early warning asked for - and nothing else is new.
SEED_VERSION = "v10"
# Bitunix candles draw different fibs and lines, each a new key: turning the
# source on re-seeds silently rather than posting every level already in range.
if bitunix_data.CRYPTO_CANDLE_SOURCE == "bitunix":
    SEED_VERSION += "-bitunix"
NSE_LAST_SCAN_KEY = "__nse_last_scan__"
# Wick into the band (lakky, 2026-10-16, QNT 1D): the band is judged on the range
# traded since the previous pass, not only the price at this moment - a wick into
# it between two checks alerts too. Looked back at most this far (a missed pass);
# without a previous pass, SWEEP_DEFAULT_SECONDS.
SWEEP_MAX_SECONDS = 30 * 60
SWEEP_DEFAULT_SECONDS = 10 * 60
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
# 1D+ zones post where the 30m zone alerts did (those are off since 2026-10-16).
ZONE_ENV = {CRYPTO: "DISCORD_30M_WEBHOOK_URL", NSE: "DISCORD_NSE_30M_WEBHOOK_URL"}
CHANNELS = ("fib", "trendline", "zone")


def webhook_env(channel, market):
    """The channel's webhook for one market, e.g. DISCORD_FIB_NSE_WEBHOOK_URL.

    FIB_ENV / TL_ENV stay as the shared fallback, so a market with no channel of
    its own yet keeps posting where it did.
    """
    if channel == "zone":
        return ZONE_ENV[market]
    return f"DISCORD_{'FIB' if channel == 'fib' else 'TRENDLINE'}_{market.upper()}_WEBHOOK_URL"


def webhook_url(channel, market):
    if channel == "zone":
        return scanner.get_env_or_config(ZONE_ENV[market], "")
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
    first, as in Shiva's EX 2/278 ETH trades (entry 2723.94 zone 1, 2672.86
    zone 2). The stop is the S/R zone rule (Lakky, 2026-10-08):
    FIB_SL_HEIGHT_PCT of the box's height beyond its far edge.
    """
    u66, u55, d55, d66 = fib_engine.levels(base, top)
    upper = dict(low=u55, high=u66)
    lower = dict(low=d66, high=d55)
    for zone in (upper, lower):
        pad = (zone["high"] - zone["low"]) * FIB_SL_HEIGHT_PCT / 100
        zone["entry"] = zone["high"] if d == 1 else zone["low"]
        zone["sl"] = zone["low"] - pad if d == 1 else zone["high"] + pad
    zone1, zone2 = (upper, lower) if d == 1 else (lower, upper)
    return [dict(zone=1, **zone1), dict(zone=2, **zone2)]


def fib_legs(d, base, top, tf):
    """[(level, zone)] this timeframe alerts at (FIB_ALERT_LEVELS, lakky 2026-10-20).

    L1/L2 are the weaker box's near/far edge, L3/L4 the stronger box's. Every leg shares the
    strong box's stop. A near edge (L1, L3) alerts from anywhere in its box down to the edge; a far
    edge (L2, L4) is a single price, so only the approach to it alerts. Without a setting for
    the timeframe it is the old rule: L3 only."""
    zones = {z["zone"]: z for z in fib_zones(d, base, top)}
    stop = zones[2]["sl"]
    legs = []
    for level in FIB_ALERT_LEVELS.get(tf, ("L3",)):
        src = zones[1] if level in ("L1", "L2") else zones[2]
        if level in ("L1", "L3"):
            legs.append((level, dict(src, sl=stop)))
        else:
            far = src["low"] if d == 1 else src["high"]
            legs.append((level, dict(src, low=far, high=far, entry=far, sl=stop)))
    return legs


def fib_level_key(symbol, tf, d, origin, top, level, zone):
    """L3 keeps the key every fib alert has had (one per zone); the others get the level on the end."""
    key = f"fib|{symbol}|{tf}|{d}|{origin}|{top}|{zone}"
    return key if level == "L3" else f"{key}|{level}"


def fib_distance(d, zone, price):
    """% from price down to (long) / up to (short) the zone; 0 inside; None once past it.

    Also None once price is through the zone's stop. Until 2026-10-08 the SL
    sat inside the zone (the inner fib's 0.55), so "inside the zone" used to
    include price already below a long's stop: 54 of the first 213 live fib
    alerts were sent that way, each scored -1R the moment it filled.
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


def in_band(distance, tf=None):
    """FIB_TL_MAX_DISTANCE_PCT (0.75%) away down to 0.00% (Shiva); 3% on 1W / 1M
    (EARLY_ALERT_BAND_PCT, lakky 2026-10-21). Never beyond 0: a fib zone price has gone
    through is None already, and price through a trendline before the candle
    closes is a break in progress - alerting it as a BUY at support (as the
    first version did, calling it "0.00%") pointed the wrong way. A close
    through the line has its own BROKEN alert."""
    return distance is not None and FIB_TL_MIN_DISTANCE_PCT <= distance <= alert_band_pct(tf, FIB_TL_MAX_DISTANCE_PCT)


# ----------------------------------------------------------------- analysis

TF_ORDER = ["30m", "4h", "1d", "1w", "1M"]

def current_price(charts):
    """The close of the freshest candle across a symbol's timeframes.

    Each timeframe's own last close would do on Delta, but Yahoo's daily and
    weekly candles can lag the intraday ones; one price for all timeframes means
    a 1W level is judged against the same price as a 4H one.
    """
    last = [c[-1] for c in charts.values() if c]
    return max(last, key=lambda c: c[0])[4] if last else None


def current_candle_range(market, charts, tf, now, live=None):
    """(low, high) traded so far in tf's candle still forming, or None.

    Bitunix never returns a forming candle, so the range is read off the finer
    timeframes too: the days of this month for a 1M candle, the 4H candles of
    today for a 1D one. Those are closed candles only, so `live` - the 4H candle
    forming now (bitunix_data.forming_candle) - adds the last few hours. Without
    it a 4H chart had no range at all and a 1D one missed up to 4 hours (lakky,
    2026-10-16, QNT 1D).
    """
    candles = charts.get(tf) or []
    if not candles:
        return None
    last = candles[-1][0]
    opened = candle_close_ts(market, last, tf) if candle_is_closed(market, last, tf, now) else last
    rows = [c for c in candles if c[0] >= opened]
    for finer in TF_ORDER[:TF_ORDER.index(tf)]:
        rows += [c for c in charts.get(finer) or [] if c[0] >= opened]
    if live and live[0] >= opened:
        rows.append(live)
    if not rows:
        return None
    return min(c[3] for c in rows), max(c[2] for c in rows)


def entry_already_touched(d, zone, price, forming):
    """True once price has reached a fib zone's entry in the candle still forming.

    Lakky (2026-10-12, BNB 1M): October's candle had traded through 838.05 (low
    716.91 on Oct 8) when that entry was alerted at 751.92, 16% of risk away on
    the wrong side. An entry the current candle already reached is a trade
    already on, not one to get ready for; the next candle can alert it again.
    """
    entry = zone["entry"]
    if (price < entry) if d == 1 else (price > entry):
        return True
    if forming is None:
        return False
    low, high = forming
    return low < entry if d == 1 else high > entry


def line_already_touched(kind, level, forming):
    """True once the candle still forming has traded to a trendline (lakky, 2026-10-12).

    The fib rule (entry_already_touched) on trendlines, for crypto and NSE. Such a
    touch neither alerts nor re-arms: it stays "in band", so it only removes alerts
    (research/tl_entry_touched_backtest.py, fib_trendline_backtest.TL_SKIP_TOUCHED_ENTRY).
    """
    if forming is None:
        return False
    low, high = forming
    return low <= level if kind == SUPPORT else high >= level


def zone_candidates(symbol, tf, closed, price, forming, trend=None):
    """1D+ S/R zones price is near now, the zone scanner's rules on this chart.

    [{key, zone_type, zone, entry, distance, alert, plan}]: listed while price is
    within the re-arm band (MAX_DISTANCE_PCT x REARM_FACTOR) on the approach side,
    alert=True inside MAX_DISTANCE_PCT. Zones are built from closed candles; one
    the forming candle has already wicked through its far edge is dead.
    research/zone_htf_backtest.py replays the same rules.
    """
    import pandas as pd

    df = pd.DataFrame([list(c[:5]) + [0.0] for c in closed[-scanner.OHLCV_LIMIT:]],
                      columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = df["time"] * 1000
    # auto_base_extra is 1 for 4h and every larger timeframe. This process scans no
    # 30m zones, so it is set rather than swapped (the symbols run in threads).
    scanner.ZONE_BASE_EXTRA = 1
    supply, demand = scanner.build_zones(df)
    band = alert_band_pct(tf, scanner.MAX_DISTANCE_PCT)     # 3% on 1W / 1M (lakky, 2026-10-21)
    out = []
    for zone_type, zones in (("supply", supply), ("demand", demand)):
        zone, _ = scanner.nearest_active_zone(price, zones, zone_type, len(df))
        if zone is None or scanner.stop_too_wide(zone_type, zone):
            continue
        if forming is not None and (forming[0] <= zone["bottom"] if zone_type == "demand" else forming[1] >= zone["top"]):
            continue
        if scanner.price_past_entry(zone_type, zone, price):
            continue
        if scanner.trend_filter_applies(symbol) and scanner.against_daily_trend(zone_type, trend):
            continue
        entry = scanner.planned_entry_price(zone_type, zone)
        distance = abs(price - entry) / entry * 100
        if distance > band * scanner.REARM_FACTOR:
            continue
        side = "long" if zone_type == "demand" else "short"
        out.append({
            "key": f"zone|{symbol}|{tf}|{zone_type}|{zone['bottom']:.10g}|{zone['top']:.10g}",
            "zone_type": zone_type, "zone": zone, "entry": entry, "distance": distance,
            "alert": distance <= band,
            "plan": {"side": side, "entry": entry, "sl": scanner.planned_stop_price(zone_type, zone)},
        })
    return out


def band_price(long_side, price, swept):
    """The price that decides the band: the deepest one traded since the last pass.

    A long (fib BUY, support) is approached from above, so it is the swept low; a
    short the swept high. Without a swept range, the price now. Whether the entry
    was reached is still entry_already_touched / line_already_touched's call.
    """
    if not swept:
        return price
    return min(price, swept[0]) if long_side else max(price, swept[1])


def analyse(market, symbol, tf, candles, now, price=None, forming=None, trend=None, swept=None):
    """Everything alertable on one chart right now. Pure - no state, no sends.

    forming: (low, high) of tf's candle so far (current_candle_range).
    swept: (low, high) traded since the previous pass - the band counts a wick into it
    (band_price). Messages still show the price now and its distance.
    trend: crypto daily EMA trend for the zone filter (scanner.daily_trend's sign)."""
    result = {"fib": [], "touch": [], "break": [], "zone": [], "bars": 0, "price": None}
    if len(candles) < 2:
        return result
    closed = candles if candle_is_closed(market, candles[-1][0], tf, now) else candles[:-1]
    price = candles[-1][4] if price is None else price
    result.update(bars=len(closed), price=price)
    if len(closed) < MIN_BARS:
        return result

    times = [c[0] for c in closed]
    opens = [c[1] for c in closed]
    highs = [c[2] for c in closed]
    lows = [c[3] for c in closed]
    closes = [c[4] for c in closed]
    stamp = [datetime.fromtimestamp(t, IST).strftime("%Y-%m-%d %H:%M") for t in times]

    snaps, _ = fib_engine.run(stamp, highs, lows, N=FIB_SWING_LENGTH)
    live = snaps[-1]
    d, base, top = live["d"], live["O"], live["E"]
    inside_box = base < price < top if d == 1 else top < price < base
    if inside_box and base != top:
        for level, zone in fib_legs(d, base, top, tf):
            distance = fib_distance(d, zone, price)
            reached = fib_distance(d, zone, band_price(d == 1, price, swept))
            if (distance is not None and in_band(reached, tf)
                    and not entry_already_touched(d, zone, price, forming)):
                result["fib"].append({
                    **zone, "key": fib_level_key(symbol, tf, d, times[live["Ot"]], top, level, zone["zone"]),
                    "level": level, "d": d, "base": base, "top": top, "distance": distance,
                    "plan": trades.fib_plan(d, zone),
                })

    if tf in ZONE_HTF_TIMEFRAMES:
        result["zone"] = zone_candidates(symbol, tf, closed, price, forming, trend)

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
            if in_band(line_distance(line.kind, level, band_price(line.kind == SUPPORT, price, swept)), tf):
                result["touch"].append({
                    **info, "key": f"tl|{ident}", "level": level, "distance": distance,
                    "touched": line_already_touched(line.kind, level, forming),
                    "plan": trades.trendline_plan(line.kind == SUPPORT, level, tf,
                                                  now_bar, opens, highs, lows, closes),
                })
        elif line.broken_at >= max(len(closed) - 2, line.created):   # never one broken before it was drawn
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


def price_text(value):
    """Shared with the zone alerts: at most 3 decimals from 1 up (scanner.price_text)."""
    return scanner.price_text(value)


def stamp_text(stamp):
    """'2026-08-10 00:00' -> '10 Aug'; '2026-07-08 13:15' -> '8 Jul 13:15'."""
    when = datetime.strptime(stamp, "%Y-%m-%d %H:%M")
    day = f"{when.day} {when:%b}"
    return day if when.hour == 0 and when.minute == 0 else f"{day} {when:%H:%M}"


def _header(market, tf, title, side=None):
    return scanner.alert_title(title, side, f"{TF_LABEL[tf]} {MARKET_LABEL[market]}")


def zone_name(d, number):
    """Shiva reads the chart as upper and lower zone, not 1 and 2 (2026-09-29).

    Zone 1 is the upper box on an up move and the lower one on a down move;
    Zone 2, the deeper one, the other. The numbers stay underneath - in the
    state keys, the records and the backtest - so renaming re-alerts nothing.
    """
    return "UPPER" if (number == 1) == (d == 1) else "LOWER"


# Short on purpose (lakky, 2026-10-08): side, timeframe, entry, stop and stop %
# up front, prices at five figures. Nothing parses this text - records carry the plan.

def fib_levels(d, base, top):
    """Lakky's L1-L4 (2026-10-12): a fib's four box edges in the order price reaches
    them - L1/L2 the weaker box, L3/L4 the stronger, L4 the strongest. The bot
    enters at L3, the stronger box's near edge."""
    u66, u55, d55, d66 = fib_engine.levels(base, top)
    edges = (u66, u55, d55, d66) if d == 1 else (d66, d55, u55, u66)
    return {f"L{n}": price for n, price in enumerate(edges, start=1)}


def format_fib_alert(market, symbol, tf, price, z, name=None):
    """Three lines (lakky, 2026-10-12): the zone edges stay in the record
    (fib_levels), off the message - the chart shows them. name: the title's symbol text."""
    side = "BUY" if z["d"] == 1 else "SELL"
    level = z.get("level") or "L3"
    name = name or display(market, symbol)
    return (
        f"{_header(market, tf, f'{name} · FIB {level} · {side}', side)}\n"
        f"Price {price_text(price)} · {z['distance']:.2f}% away\n"
        f"Entry {price_text(z['entry'])} · SL {price_text(z['sl'])} ({trades.risk_pct(z['plan']):.2f}%)"
        f" · TP {price_text(trades.target_price(z['plan']))} (1R)"
    )


def format_touch_alert(market, symbol, tf, price, t, name=None):
    """Three lines (lakky, 2026-10-12): the line's two points stay in the record."""
    line, side = ("S", "BUY") if t["kind"] == SUPPORT else ("R", "SELL")
    name = name or display(market, symbol)
    return (
        f"{_header(market, tf, f'{name} · {line} TL · {side}', side)}\n"
        f"Price {price_text(price)} · {t['distance']:.2f}% away\n"
        f"Entry {price_text(t['level'])} · SL {price_text(t['plan']['sl'])} ({trades.risk_pct(t['plan']):.2f}%)"
        f" · TP {price_text(trades.target_price(t['plan']))} (1R)"
    )


def move_24h(hourly, price, now):
    """% move from the close 24 hours ago (1h candles [ts, o, h, l, c]) to price, or None."""
    if not hourly or not price:
        return None
    then = int(now) // 3600 * 3600 - 24 * 3600      # that hour's close = the next hour's open
    past = [c for c in hourly if c[0] + 3600 <= then]
    if not past or then - (past[-1][0] + 3600) > 3600:
        return None
    return (price / past[-1][4] - 1) * 100


def risk_warning(market, symbol, side, risk):
    """lakky (2026-10-17): one bold line when a crypto alert looks risky, else None.

    risk: {"move": % over 24h or None, "market": {symbol: daily trend +1/-1/None} for
    RISK_WARN_MARKET_SYMBOLS}. The market is against a BUY when at least
    RISK_WARN_MARKET_MIN_AGAINST of them are under their daily EMA (a SELL: over)."""
    if market != CRYPTO or not risk:
        return None
    parts = []
    move = risk.get("move")
    if move is not None and abs(move) >= RISK_WARN_MOVE_PCT:
        parts.append("Big 24h move")
    trends = risk.get("market") or {}
    against = sum(1 for t in trends.values() if t is not None and (t < 0 if side == "long" else t > 0))
    if against >= RISK_WARN_MARKET_MIN_AGAINST:
        arrows = " ".join(f"{scanner.alert_symbol(s)} {arrow(trends.get(s))}" for s in RISK_WARN_MARKET_SYMBOLS)
        parts.append(f"Market {'down' if side == 'long' else 'up'}: {arrows}")
    return f"⚠️ **{' · '.join(parts)}**" if parts else None


def arrow(trend):
    return "↑" if trend and trend > 0 else "↓" if trend and trend < 0 else "-"


def name_with_move(market, symbol, risk):
    """'SOL -5.2%' on crypto alerts with a known 24h move (lakky, 2026-10-17), else the name."""
    name = display(market, symbol)
    move = (risk or {}).get("move") if market == CRYPTO else None
    return f"{name} {move:+.1f}%" if move is not None else name


def with_warning(message, warning):
    return f"{message}\n{warning}" if warning else message


def format_zone_alert(market, symbol, tf, price, z):
    """The zone scanner's three lines (scanner.format_alert), with 1D / 1W / 1M."""
    side = "SELL" if z["zone_type"] == "supply" else "BUY"
    zone, entry, stop = z["zone"], z["entry"], z["plan"]["sl"]
    places = scanner.level_places((zone["bottom"], zone["top"], stop), scanner.short_places(entry))
    return (
        f"**{display(market, symbol)} | {side} | {TF_LABEL[tf]}**\n"
        f"Price {scanner.price_text(price, places)} · {z['distance']:.2f}% away\n"
        f"Entry {scanner.price_text(entry, places)} · SL {scanner.price_text(stop, places)}"
        f" ({trades.risk_pct(z['plan']):.2f}%)"
    )


def format_break_alert(market, symbol, tf, b):
    name = "S" if b["kind"] == SUPPORT else "R"
    side = "below" if b["kind"] == SUPPORT else "above"
    return (
        f"{_header(market, tf, f'{display(market, symbol)} · {name} TL BROKEN')}\n"
        f"Close {price_text(b['close'])} {side} line {price_text(b['level'])}"
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
    title_name = name_with_move(market, symbol, analysis.get("risk"))
    base = {"market": market, "symbol": symbol, "tf": tf, "price": price}
    for z in analysis["fib"]:
        if z["key"] not in state:
            record = {**base, "kind": "fib", "plan": z["plan"], "zone": z["zone"],
                      "base": z["base"], "top": z["top"], "levels": fib_levels(z["d"], z["base"], z["top"]),
                      "level": z.get("level", "L3")}
            warning = risk_warning(market, symbol, z["plan"]["side"], analysis.get("risk"))
            if warning:
                record["warning"] = warning
            planned.append(("fib", z["key"], with_warning(format_fib_alert(market, symbol, tf, price, z, title_name), warning),
                            record))
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
        if t.get("touched"):
            if isinstance(entry, dict):
                entry["seen"] = now      # this candle already reached the line: no alert, band unchanged
            continue
        if entry is None or (not entry.get("in_band") and now - entry.get("sent", 0) >= TF_SECONDS[tf]):
            record = {**base, "kind": "trendline", "plan": t["plan"], "line": t["kind"],
                      "from": list(t["from"]), "to": list(t["to"])}
            warning = risk_warning(market, symbol, t["plan"]["side"], analysis.get("risk"))
            if warning:
                record["warning"] = warning
            planned.append(("trendline", t["key"], with_warning(format_touch_alert(market, symbol, tf, price, t, title_name),
                                                                warning), record))
        else:
            entry["in_band"] = True
            entry["seen"] = now

    # Zones: the zone scanner's re-arm - a zone alerts again only once price has left
    # MAX_DISTANCE_PCT x REARM_FACTOR and the 4h cooldown (ALERT_COOLDOWN_SECONDS) has passed.
    near = {z["key"] for z in analysis.get("zone", [])}
    prefix = f"zone|{symbol}|{tf}|"
    for key, entry in state.items():
        if key.startswith(prefix) and key not in near and isinstance(entry, dict):
            entry["in_band"] = False
    for z in analysis.get("zone", []):
        entry = state.get(z["key"])
        if z["alert"] and (entry is None or (not entry.get("in_band")
                                             and now - entry.get("sent", 0) >= scanner.ALERT_COOLDOWN_SECONDS)):
            record = {**base, "kind": "zone", "plan": z["plan"], "zone_type": z["zone_type"],
                      "zone_bottom": z["zone"]["bottom"], "zone_top": z["zone"]["top"]}
            planned.append(("zone", z["key"], format_zone_alert(market, symbol, tf, price, z), record))
        elif isinstance(entry, dict):
            entry["in_band"] = True
            entry["seen"] = now
    return planned


def tl_break_skip_sides(market, analyses, now):
    """{1, -1}: the fib sides whose L1/L2 are skipped now after a 4H TL break (lakky, 2026-10-22).

    A broken support skips BUY (1), a broken resistance SELL (-1), for FIB_TL_BREAK_SKIP_SECONDS from
    the breaking 4H candle's close. analyse keeps a break for the last two closed candles, which covers it."""
    if market not in FIB_TL_BREAK_SKIP_MARKETS:
        return set()
    sides = set()
    for b in (analyses.get("4h") or {}).get("break", []):
        closed_at = b.get("closed_at")
        if closed_at is not None and closed_at <= now < closed_at + FIB_TL_BREAK_SKIP_SECONDS:
            sides.add(1 if b.get("kind") == SUPPORT else -1)
    return sides


def skipped_by_tl_break(channel, record, sides):
    """True for a fib L1/L2 alert on a side tl_break_skip_sides paused."""
    if channel != "fib" or not record or not sides or record.get("level") not in FIB_TL_BREAK_SKIP_LEVELS:
        return False
    return (1 if record["plan"]["side"] == "long" else -1) in sides


def mark_sent(state, key, now):
    state[key] = {"sent": now, "seen": now, "in_band": key.startswith(("tl|", "zone|"))}


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

def swept_since(rows, since, seconds=60):
    """(low, high) of the `seconds` candles [ts, o, h, l, c, ...] that closed after `since`, or None."""
    rows = [r for r in rows if r[0] + seconds > since]
    return (min(r[3] for r in rows), max(r[2] for r in rows)) if rows else None


def sweep_start(last_scan, now):
    """Where this pass's swept range starts: the previous pass, at most SWEEP_MAX_SECONDS back."""
    if not last_scan:
        return now - SWEEP_DEFAULT_SECONDS
    return max(last_scan, now - SWEEP_MAX_SECONDS)


def scan_crypto(timeframes, now, since=None):
    since = now - SWEEP_DEFAULT_SECONDS if since is None else since
    market_trend = {}                  # once a pass, for risk_warning
    for coin in RISK_WARN_MARKET_SYMBOLS:
        try:
            market_trend[coin] = scanner.daily_trend(coin)
        except Exception as error:     # noqa: BLE001 - no trend = that coin does not count
            print(f"{coin} daily trend unavailable: {str(error)[:80]}")
            market_trend[coin] = None

    def one(symbol):
        contract = scanner.delta_contract(symbol)
        if contract is None:
            return symbol, None, "not a Delta contract"
        try:
            source = "bitunix" if bitunix_data.uses_bitunix(symbol) else "delta"
            pair = bitunix_data.pair_for(symbol, contract) if source == "bitunix" else None
            # No Delta fallback here, unlike the zone scan. A fib's key names its
            # base candle, and Delta's history starts Dec 2023 while Bitunix's runs
            # years further back, so the same chart on Delta is a different fib:
            # BNB 1M re-alerted on 2026-10-09 with a 2024 base and an entry above
            # price. Trendline keys carry Delta's own prices too. A pass with
            # Bitunix down skips the symbol; BREAK_GRACE_SECONDS covers the gap.
            # A Bitunix pair passes through bitunix_pair unchanged, so the
            # xStocks' own pairs (TSLAUSDT for TSLAXUSD) reach the API as is.
            charts = crypto_charts(pair or contract, timeframes, now, source=source)
            price = current_price(charts)
            live = swept = move = None
            if source == "bitunix":
                # Bitunix candles stop at the last closed one, so their newest
                # close is up to a 4H candle old; the distance needs the price now.
                try:
                    price = bitunix_data.last_price(pair)
                except Exception as error:     # noqa: BLE001 - keep the candle close
                    print(f"{symbol} Bitunix live price unavailable: {str(error)[:80]}")
                # ...and the forming 4H candle, so "this candle already reached the
                # entry" sees the last few hours too (current_candle_range).
                try:
                    live = bitunix_data.forming_candle(pair, "4h", now)
                except Exception as error:     # noqa: BLE001 - closed candles only
                    print(f"{symbol} Bitunix forming 4h unavailable: {str(error)[:80]}")
                # ...and the 24h move for the warning line.
                if symbol in CRYPTO_WATCHLIST:
                    try:
                        move = move_24h(bitunix_data.klines(pair, "1h", int(now) - 27 * 3600, int(now) + 1),
                                        price, now)
                    except Exception as error:     # noqa: BLE001 - no move = no move warning
                        print(f"{symbol} Bitunix 1h for the 24h move unavailable: {str(error)[:80]}")
                # ...and what traded since the last pass: a wick into the band counts.
                try:
                    start = int(since) // 60 * 60
                    swept = swept_since(bitunix_data.klines(pair, "1m", start, int(now) + 1), since)
                except Exception as error:     # noqa: BLE001 - the price now decides
                    print(f"{symbol} Bitunix 1m sweep unavailable: {str(error)[:80]}")
            trend = None
            if scanner.trend_filter_applies(symbol) and charts.get("1d"):
                trend = scanner._trend_from_daily([(c[0], c[4]) for c in charts["1d"]], now)
            # The warning line (risk_warning), crypto only; a failed fetch only drops that half of it.
            risk = {"move": move, "market": market_trend} if symbol in CRYPTO_WATCHLIST else None
            out = {tf: analyse(CRYPTO, symbol, tf, charts[tf], now, price,
                               current_candle_range(CRYPTO, charts, tf, now, live), trend, swept)
                   for tf in timeframes}
            for analysis in out.values():
                analysis["risk"] = risk
            return symbol, out, None
        except Exception as error:     # noqa: BLE001 - one bad symbol must not stop the pass
            return symbol, None, str(error)

    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
        return list(pool.map(one, scanner.active_watchlist()))


def nse_session_open(now):
    import nse_scanner
    import pandas as pd

    is_open, *_ = nse_scanner.market_window_status(pd.Timestamp.fromtimestamp(now, tz=IST))
    return is_open


def scan_nse(timeframes, now, since=None):
    import nse_scanner

    since = now - SWEEP_DEFAULT_SECONDS if since is None else since
    symbols = nse_scanner.load_watchlist()
    charts = nse_charts(symbols, timeframes)
    try:
        fine = nse_download(symbols, "5m", period="1d")     # what traded since the last pass
    except Exception as error:     # noqa: BLE001 - the price now decides
        print(f"NSE 5m sweep unavailable: {str(error)[:80]}")
        fine = {}
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
            swept = swept_since(fine.get(symbol, []), since, 300)
            results.append((symbol, {tf: analyse(NSE, symbol, tf, charts[symbol][tf], now, price,
                                                 current_candle_range(NSE, charts[symbol], tf, now),
                                                 swept=swept)
                                     for tf in timeframes}, None))
        except Exception as error:     # noqa: BLE001
            results.append((symbol, None, str(error)))
    return results


# ----------------------------------------------------------------- main

def run_once(dry_run=False, force_nse=False):
    now = time.time()
    timeframes = [tf for tf in FIB_TL_TIMEFRAMES if tf in TF_LABEL]
    state = load_state()

    previous = state.get(LAST_SCAN_KEY) if isinstance(state.get(LAST_SCAN_KEY), dict) else {}
    markets = {CRYPTO: scan_crypto(timeframes, now, sweep_start(previous.get(CRYPTO), now))}
    nse_due = now - state.get(NSE_LAST_SCAN_KEY, 0) >= NSE_MIN_INTERVAL_SECONDS
    if force_nse or (nse_due and nse_session_open(now)):
        markets[NSE] = scan_nse(timeframes, now, sweep_start(state.get(NSE_LAST_SCAN_KEY), now))
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
                  for channel in CHANNELS for market in (CRYPTO, NSE)}
    awake = {CRYPTO: scanner.in_alert_window(), NSE: True}   # NSE only scans in session
    last_scans = state.get(LAST_SCAN_KEY)
    if not isinstance(last_scans, dict):
        last_scans = {}
    state[LAST_SCAN_KEY] = last_scans
    previous_scan = dict(last_scans)
    seeding = {
        (channel, market)
        for market, results in markets.items() if results
        for channel in CHANNELS
        if configured[(channel, market)] and f"{channel}:{market}:{SEED_VERSION}" not in seeded
    }
    counts = {}
    failures = []
    for market, results in markets.items():
        for symbol, analyses, error in results:
            if analyses is None:
                failures.append(f"{market} {symbol}: {error}")
                continue
            skip_sides = tl_break_skip_sides(market, analyses, now)
            for tf, analysis in analyses.items():
                for channel, key, message, record in plan_alerts(state, market, symbol, tf, analysis, now,
                                                                 previous_scan.get(market)):
                    skip = skipped_by_tl_break(channel, record, skip_sides)
                    if dry_run:
                        print(f"[{channel}]{' (skipped: 4H TL break)' if skip else ''} {message}\n")
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
                    if skip:
                        # A 4H trendline just broke against this fib's side: this L1/L2 level is
                        # dropped for good, as if sent (FIB_TL_BREAK_SKIP_SECONDS, lakky 2026-10-22).
                        print(f"[{channel}] skipped after a 4H TL break: {key}")
                        mark_sent(state, key, now)
                        state[key]["skipped"] = "4h_tl_break"
                        save_state(state, now)
                        continue
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
        sent = ", ".join(f"{c} {counts.get((c, market), 0)}" for c in CHANNELS)
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
            f"{'1D+ zone' if channel == 'zone' else channel.capitalize()} alerts ({MARKET_LABEL[market]}, 0-"
            f"{scanner.MAX_DISTANCE_PCT if channel == 'zone' else FIB_TL_MAX_DISTANCE_PCT:g}% band) started. "
            f"Seeded silently: {counts.get((channel, market), 0)} "
            f"{ {'fib': 'fib zones', 'trendline': 'trendlines', 'zone': 'S/R zones'}[channel]} price was already within range. "
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
