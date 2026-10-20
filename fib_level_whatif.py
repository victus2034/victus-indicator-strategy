"""What if a fib alert had entered at L1, L2 or L4 instead of L3 (lakky, 2026-10-19).

The bot enters every fib at L3, the strong box's near edge. To compare the other
box edges, each fib alert is also scored as if it had been sent at L1, L2 and L4:

- Same stop as the real alert (25% of the strong box past L4, where the fib dies),
  so each level is one entry against one invalidation point.
- The "alert" for a level is the first candle after the fib's top that comes within
  FIB_TL_MAX_DISTANCE_PCT of that level - the real alert's band. L1 and L2 are
  usually reached before the L3 alert, L4 after it.
- From there it is fib_trendline_trades.simulate, the same rules as every fib
  trade: 5 candles to fill, 20 to finish, 1R / 2R, breakeven at +0.5R.

Nothing here posts or changes an alert. Results go to LEVEL_RESULTS_FILE, keyed by
alert id, for the journal's Fib levels tab; a level that resolved is not scored again.
"""
import json
import os
from collections import defaultdict
from pathlib import Path

import fib_trendline_trades as trades
from config import FIB_TL_ENTRY_WAIT_BARS, FIB_TL_MAX_DISTANCE_PCT, FIB_TL_MAX_HOLD_BARS
from fib_trendline_data import NSE, TF_SECONDS, nse_download

LEVEL_RESULTS_FILE = Path(__file__).with_name(os.getenv("VICTUS_FIB_LEVEL_RESULTS_FILE", "fib_level_results.json"))
RATIOS = {"L1": 0.34, "L2": 0.45, "L3": 0.55, "L4": 0.66}
WHAT_IF = ("L1", "L2", "L4")
ENTRY_LEVEL = {1: "L1", 2: "L3"}
# The fib's top on the scoring candles must be this close to the one the alert
# was drawn from (Bitunix vs Delta, and Delta's history starts Dec 2023).
TOP_TOLERANCE_PCT = 1.0


def load_level_results():
    try:
        with LEVEL_RESULTS_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


def save_level_results(results):
    tmp = LEVEL_RESULTS_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=1, sort_keys=True)
    os.replace(tmp, LEVEL_RESULTS_FILE)


def geometry(record):
    """(origin_ts, top, {L1..L4}) of a fib record, or None.

    From the record's own `levels` when it has them; older records are worked out
    from the key (fib|symbol|tf|d|origin_ts|top|zone) and the entry, which sits at
    L3 for zone 2 and L1 for zone 1."""
    if record.get("kind") != "fib":
        return None
    parts = str(record.get("key") or record.get("id", "")).split("@")[0].split("|")
    if len(parts) != 7 or parts[0] != "fib":
        return None      # an L1/L2/L4 alert (key ends |Lx, 2026-10-20) is its own level: no what-ifs
    try:
        origin, top, zone = int(float(parts[4])), float(parts[5]), int(float(parts[6]))
        entry = float(record["plan"]["entry"])
    except (KeyError, TypeError, ValueError):
        return None
    if isinstance(record.get("levels"), dict) and all(k in record["levels"] for k in RATIOS):
        return origin, top, {k: float(record["levels"][k]) for k in RATIOS}
    level = ENTRY_LEVEL.get(zone)
    if not level:
        return None
    span = (entry - top) / RATIOS[level]
    if span == 0:
        return None
    return origin, top, {k: top + r * span for k, r in RATIOS.items()}


def level_alert_ts(long, top, level, candles, origin, sent_ts):
    """The moment a level would have alerted: just before the first candle after the
    fib's top that came within the band of it. None when the top is not in the
    candles, or price never got there."""
    window = [c for c in candles if origin <= c[0] <= sent_ts]
    if not window:
        return None
    # The top is the extreme between the origin and the alert (a new extreme would
    # have been a new fib): the high for a buy fib, the low for a sell one.
    top_i = max(range(len(window)), key=lambda i: window[i][2]) if long else min(range(len(window)), key=lambda i: window[i][3])
    seen_top = window[top_i][2] if long else window[top_i][3]
    if abs(seen_top - top) / top * 100 > TOP_TOLERANCE_PCT:
        return None
    band = level * FIB_TL_MAX_DISTANCE_PCT / 100
    for ts, _o, h, l, _c in candles:
        if ts <= window[top_i][0]:
            continue
        if (l <= level + band) if long else (h >= level - band):
            return ts - 1
    return None


def gave_up(record, now):
    """A level not reached by the time the real alert's trade would have ended
    (wait + hold candles of its timeframe) is "not reached", and is not looked for again."""
    bars = FIB_TL_ENTRY_WAIT_BARS + FIB_TL_MAX_HOLD_BARS
    return now - record["sent_ts"] > bars * TF_SECONDS.get(record["tf"], 86400)


def score_record(record, candles, old=None, now=None):
    """{level: simulate result + "alert_ts"} for L1, L2 and L4 of one fib alert."""
    geo = geometry(record)
    if not geo:
        return None
    origin, top, levels = geo
    plan = record["plan"]
    long = plan["side"] == "long"
    out = dict(old or {})
    for name in WHAT_IF:
        if (out.get(name) or {}).get("resolved"):
            continue
        what_if = {"side": plan["side"], "entry": levels[name], "sl": plan["sl"]}
        if (what_if["entry"] <= what_if["sl"]) if long else (what_if["entry"] >= what_if["sl"]):
            out[name] = dict(outcome="no fill", filled=False, resolved=True, alert_ts=None, entry=what_if["entry"])
            continue
        at = level_alert_ts(long, top, levels[name], candles, origin, record["sent_ts"]) if candles else None
        if at is None:
            # Not reached yet (or no data): open, tried again tomorrow - unless its
            # time is up and the candles were there to look in.
            done = bool(candles) and now is not None and gave_up(record, now)
            out[name] = dict(outcome="not reached" if done else "open", filled=False, resolved=done,
                             alert_ts=None, entry=what_if["entry"])
            continue
        result = trades.simulate(what_if, record["market"], record["tf"], at, candles)
        out[name] = dict(result, alert_ts=at, entry=what_if["entry"])
    return out


def score_levels(records, results, now, fetch):
    """Score L1/L2/L4 for every fib alert not fully resolved. `fetch(market, symbol,
    resolution, start, now)` gives evaluation candles (the daily report's)."""
    pending = []
    for record in records:
        if not geometry(record):
            continue
        old = results.get(record["id"]) or {}
        if all((old.get(n) or {}).get("resolved") for n in WHAT_IF):
            continue
        pending.append(record)
    groups = defaultdict(list)
    for record in pending:
        groups[(record["market"], record["symbol"], trades.EVAL_RESOLUTION[record["market"]][record["tf"]])].append(record)
    nse = {}
    for resolution in {res for m, _, res in groups if m == NSE}:
        symbols = sorted({s for m, s, res in groups if m == NSE and res == resolution})
        try:
            nse[resolution] = nse_download(symbols, resolution)
        except Exception as error:     # noqa: BLE001 - retried tomorrow
            print(f"fib levels: NSE {resolution} download failed: {error}")
    for (market, symbol, resolution), rows in groups.items():
        try:
            if market == NSE:
                candles = nse.get(resolution, {}).get(symbol, [])
            else:
                candles = fetch(market, symbol, resolution, min(geometry(r)[0] for r in rows), now)
        except Exception as error:     # noqa: BLE001 - retried tomorrow
            print(f"fib levels: no {resolution} candles for {symbol}: {error}")
            candles = []
        for record in rows:
            scored = score_record(record, candles, results.get(record["id"]), now)
            if scored:
                results[record["id"]] = scored
    return results
