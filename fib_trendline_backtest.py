"""History backtest of the fib and trendline alerts - crypto and NSE, 30m to 1M.

Replays each chart bar by bar. While bar i forms, the levels are the ones the
live scanner would have: the fib state and the trendlines built from bars up to
i-1. Bar i is walked on finer evaluation candles (fib_trendline_trades.
EVAL_RESOLUTION); the first evaluation candle that comes within the live band
(FIB_TL_MAX_DISTANCE_PCT) fires the alert, with the same once-only and re-arm
rules as the scanner, and the crypto 01:00-08:00 IST hold. Each alert is then
traded and scored by fib_trendline_trades.simulate - the same function the daily
report uses on live alerts.

How far back depends on the data: crypto from Delta (30m ~83 days, 4H ~22
months, 1D/1W/1M since Delta India's launch in Dec 2023); NSE from Yahoo (30m 60
days; 4H and 1D limited to the 700 days Yahoo keeps 1h candles; 1W/1M 5 years
on daily candles).

    python fib_trendline_backtest.py                 # both markets, writes reports/
    python fib_trendline_backtest.py --market crypto
"""
import argparse
import bisect
import csv
import json
import random
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import fib_engine
import fib_trendline_trades as trades
import scanner
from config import (
    FIB_ALERT_ZONES,
    FIB_SL_HEIGHT_PCT,
    FIB_SWING_LENGTH,
    FIB_TL_ENTRY_WAIT_BARS,
    FIB_TL_MAX_DISTANCE_PCT,
    FIB_TL_MAX_HOLD_BARS,
    REARM_FACTOR,
    TRENDLINE_SL_PCT,
    TRENDLINE_SWING_LENGTH,
    TRENDLINES_KEEP,
    alert_band_pct,
)
from fib_trendline_data import (
    CRYPTO, IST, NSE, TF_LABEL, TF_SECONDS, TIMEFRAMES, candle_is_closed, delta_candles,
    monthly_from_daily, nse_download,
)
from fib_trendline_scanner import MIN_BARS, fib_zones
from trendlines import SUPPORT, build_trendlines

HERE = Path(__file__).parent
CACHE = HERE / ".fib_tl_bt_cache"
REPORT_MD = HERE / "reports" / "FIB_TRENDLINE_BACKTEST.md"
TRADES_CSV = HERE / "reports" / "fib_trendline_backtest_trades.csv"
BAND = FIB_TL_MAX_DISTANCE_PCT / 100
# The live 3% band on 1W / 1M (config.alert_band_pct, lakky 2026-10-21). Research turns it off.
EARLY_BAND = True
ALERT_ZONES = FIB_ALERT_ZONES      # research overrides it to replay both zones
# The live rule since 2026-10-12: no fib alert once the candle forming has reached
# the entry (fib_trendline_scanner.entry_already_touched). Research turns it off.
SKIP_TOUCHED_ENTRY = True
# The same rule for trendline touches, live since 2026-10-12 (lakky): no alert once the
# candle forming has reached the line (fib_trendline_scanner.line_already_touched).
TL_SKIP_TOUCHED_ENTRY = True
# Research hook (research/band_wick_backtest.py): band(market, symbol, start, end, lo, hi)
# -> the first time price was in [lo, hi] within [start, end) on finer candles, or None.
# None here = the eval candle's own range decides, as always.
BAND_PROBE = None
# Research hook (research/fib_rearm_backtest.py): a fib zone that already alerted alerts again
# once price has left its band by REARM_FACTOR and come back. Live: one alert per zone.
FIB_REARM = False
# Research hook (lakky, 2026-10-20): also alert at L4, the strong box's far edge, as its own level,
# and wait FIB_REPEAT_WAIT seconds before repeating a level whose last alert touched the entry.
FIB_L4 = False
FIB_REPEAT_WAIT = 0
# Research hook (lakky, 2026-10-20): {timeframe: ("L1".."L4")} - which fib levels alert; overrides ALERT_ZONES and FIB_L4.
FIB_LEVELS = None


# ----------------------------------------------------------------- data (cached per day)

def _cached(name, fetch):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{datetime.now(IST):%Y%m%d}_{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    data = fetch()
    path.write_text(json.dumps(data))
    return data


def crypto_data(symbol, now):
    contract = scanner.delta_contract(symbol)
    if contract is None:
        return None
    since_launch = now - 2000 * 86400
    daily = _cached(f"c_{contract}_1d", lambda: delta_candles(contract, "1d", since_launch, now))
    base = {
        "30m": _cached(f"c_{contract}_30m", lambda: delta_candles(contract, "30m", now - 3999 * 1800, now)),
        "4h": _cached(f"c_{contract}_4h_all", lambda: delta_candles(contract, "4h", since_launch, now)),
        "1d": daily,
        "1w": _cached(f"c_{contract}_1w", lambda: delta_candles(contract, "1w", since_launch, now)),
        "1M": monthly_from_daily(daily),
    }
    # 1d evaluation candles are the daily series, and 4h ones (for 1D alerts)
    # are the full 4h history already in base - fetching either again only
    # downloaded the same candles twice.
    evals = {"1d": daily, "4h": base["4h"]}
    for tf in ("30m", "4h", "1d"):
        res = trades.EVAL_RESOLUTION[CRYPTO][tf]
        if res not in evals and base[tf]:
            start = base[tf][0][0]
            evals[res] = _cached(f"c_{contract}_eval_{res}", lambda: delta_candles(contract, res, start, now))
    return base, evals


def nse_data(symbols):
    base = {tf: _cached(f"n_{tf}", lambda tf=tf: nse_download(symbols, tf)) for tf in TIMEFRAMES}
    # A resolution already downloaded as a base timeframe (1d) is the same
    # call - reuse it rather than downloading it twice.
    evals = {res: base[res] if res in base else _cached(f"n_eval_{res}", lambda res=res: nse_download(symbols, res))
             for res in sorted(set(trades.EVAL_RESOLUTION[NSE].values()))}
    return {s: ({tf: base[tf].get(s, []) for tf in TIMEFRAMES},
                {res: evals[res].get(s, []) for res in evals}) for s in symbols}


# ----------------------------------------------------------------- replay

def crypto_held(ts, seconds):
    """The live crypto scanner holds alerts 01:00-08:00 IST - only a candle wholly inside that counts.

    A daily candle opens at 05:30 IST but spans the whole day; judging it by its
    open time held every one of them, and silently left 1W and 1M with no alerts.
    """
    start = datetime.fromtimestamp(ts, IST)
    end = datetime.fromtimestamp(ts + seconds, IST)
    return start.date() == end.date() and start.hour >= 1 and (end.hour, end.minute) <= (8, 0)


class TouchClock:
    """The zone scanner's age rules, for a fib zone or a trendline (scanner.record_zone_touch).

    Fed one closed candle at a time, oldest first, from when the level appeared.
    quiet(i) is too_young_to_alert's age at candle i: candles since the last
    touch, or the quiet run earned before the touch episode now in progress.
    max_streak is what the over-touched veto reads (2 in a row = over-touched).
    Recorded on each backtest alert so candidate filters can be tested without
    changing what alerts - see the filter study in reports/.
    """

    def __init__(self, start):
        self.clock, self.last_gap, self.streak, self.max_streak = start, None, 0, 0

    def feed(self, index, touched):
        if touched:
            if self.streak == 0:
                self.last_gap = index - self.clock
            self.clock = index
            self.streak += 1
        else:
            self.streak = 0
        self.max_streak = max(self.max_streak, self.streak)

    def quiet(self, index):
        run = index - self.clock
        return max(run, self.last_gap) if self.last_gap is not None else run


def band_for(tf):
    """The alert band as a fraction on timeframe tf: BAND, or the early band on 1W / 1M."""
    return alert_band_pct(tf, BAND * 100) / 100 if EARLY_BAND else BAND


def replay(market, symbol, tf, base, evalc, now):
    """Every alert the live scanner would have sent on this chart, traded and scored."""
    band = band_for(tf)
    if base and not candle_is_closed(market, base[-1][0], tf, now):
        base = base[:-1]
    n = len(base)
    if n <= MIN_BARS or not evalc:
        return []
    times = [c[0] for c in base]
    opens = [c[1] for c in base]
    highs = [c[2] for c in base]
    lows = [c[3] for c in base]
    closes = [c[4] for c in base]
    eval_ts = [c[0] for c in evalc]
    eval_seconds = TF_SECONDS[trades.EVAL_RESOLUTION[market][tf]]
    held = (lambda ts: crypto_held(ts, eval_seconds)) if market == CRYPTO else (lambda ts: False)
    horizon = (FIB_TL_ENTRY_WAIT_BARS + FIB_TL_MAX_HOLD_BARS + 1) * trades.EVAL_PER_BAR[market][tf]

    def bar_slice(i):
        end = times[i + 1] if i + 1 < n else times[i] + TF_SECONDS[tf]
        return bisect.bisect_left(eval_ts, times[i]), bisect.bisect_left(eval_ts, end)

    def trade(kind, plan, k, extra):
        ts = evalc[k][0]
        # a 1R plan has no hold limit (Lakky's trendline trades): it runs to the data's end
        after = evalc[k + 1:] if plan.get("target_r") == 1 else evalc[k + 1:k + 1 + horizon]
        return {"market": market, "symbol": symbol, "tf": tf, "kind": kind, "alert_ts": ts,
                "plan": plan, "result": trades.simulate(plan, market, tf, ts, after), **extra}

    first = next((i for i in range(MIN_BARS, n) if times[i] >= eval_ts[0]), n)
    out = []

    stamp = [str(t) for t in times]
    snaps, _ = fib_engine.run(stamp, highs, lows, N=FIB_SWING_LENGTH)
    fired, spent, last = set(), set(), {}
    for i in range(first, n):
        s = snaps[i - 1]
        d, base_px, top = s["d"], s["O"], s["E"]
        if base_px == top:
            continue
        e0, e1 = bar_slice(i)
        zs = {z["zone"]: z for z in fib_zones(d, base_px, top)}
        legs = []
        if FIB_LEVELS:
            # L1/L2 = the weaker box's near/far edge, L3/L4 = the strong box's; one stop for all (the strong box's)
            for name in FIB_LEVELS.get(tf, ()):
                src = zs[1] if name in ("L1", "L2") else zs[2]
                far = src["low"] if d == 1 else src["high"]
                near = src["entry"]
                legs.append((name, dict(src, entry=near if name in ("L1", "L3") else far, sl=zs[2]["sl"])))
        else:
            for zone0 in zs.values():
                if zone0["zone"] not in ALERT_ZONES:
                    continue
                legs.append(("L3", zone0))
                if FIB_L4:
                    # L4 is the strong box's far edge: its own entry, the same stop (lakky, 2026-10-20)
                    legs.append(("L4", dict(zone0, entry=zone0["low"] if d == 1 else zone0["high"])))
        if True:
            for leg, zone in legs:
                key = (d, times[s["Ot"]], top, leg if FIB_LEVELS else zone["zone"], leg)
                if leg in ("L1", "L3"):
                    lo_band = zone["low"] if d == 1 else zone["low"] * (1 - band)
                    hi_band = zone["high"] * (1 + band) if d == 1 else zone["high"]
                    ref_hi, ref_lo = zone["high"], zone["low"]
                else:
                    lo_band = zone["entry"] if d == 1 else zone["entry"] * (1 - band)
                    hi_band = zone["entry"] * (1 + band) if d == 1 else zone["entry"]
                    ref_hi = ref_lo = zone["entry"]
                entry = zone["entry"]
                if key in fired:
                    if not FIB_REARM:
                        continue
                    away = 1 + band * REARM_FACTOR
                    if key in spent:
                        # re-arm once a candle sat wholly beyond the band by REARM_FACTOR on the approach side
                        if any((evalc[k][3] > ref_hi * away) if d == 1 else (evalc[k][2] < ref_lo / away)
                               for k in range(e0, e1)):
                            spent.discard(key)
                        continue
                for k in range(e0, e1):
                    ts, _o, h, l, _c = evalc[k]
                    if (l <= base_px) if d == 1 else (h >= base_px):
                        break                    # the fib died inside this bar
                    if SKIP_TOUCHED_ENTRY and ((_o < entry) if d == 1 else (_o > entry)):
                        break                    # this candle already reached the entry (entry_already_touched)
                    outside = l > hi_band or h < lo_band
                    band_ts = None
                    if not outside and BAND_PROBE is not None:
                        end = evalc[k + 1][0] if k + 1 < len(evalc) else ts + eval_seconds
                        band_ts = BAND_PROBE(market, symbol, ts, end, lo_band, hi_band)
                        outside = band_ts is None
                    if held(ts) or outside:
                        if SKIP_TOUCHED_ENTRY and ((l < entry) if d == 1 else (h > entry)):
                            break
                        continue
                    if trades.already_stopped(trades.fib_plan(d, zone), _c):
                        # The live scanner sends nothing once price is through
                        # the stop (fib_trendline_scanner.fib_distance); this
                        # candle closed there, so it is not an alert either.
                        if SKIP_TOUCHED_ENTRY:
                            break
                        continue
                    if FIB_REPEAT_WAIT and key in fired and key in last and last[key][1] \
                            and ts < last[key][0] + FIB_REPEAT_WAIT:
                        continue             # the last alert of this level touched: wait before the next one
                    fired.add(key)
                    spent.add(key)
                    clock = TouchClock(s["Et"])
                    for j in range(s["Et"] + 1, i):
                        clock.feed(j, highs[j] >= zone["low"] and lows[j] <= zone["high"])
                    features = {"swing_gap": s["Et"] - s["Ot"], "age": i - s["Et"],
                                "quiet": clock.quiet(i), "max_streak": clock.max_streak}
                    got = trade("fib", trades.fib_plan(d, zone), k,
                                {"zone": zone["zone"], "level": leg,
                                 "fib_id": f"{symbol}|{tf}|{d}|{times[s['Ot']]}|{top}",
                                 "band_ts": band_ts, **features})
                    last[key] = (ts, got["result"]["filled"])
                    out.append(got)
                    break

    for line in build_trendlines(highs, lows, closes, TRENDLINE_SWING_LENGTH, TRENDLINES_KEEP, history=True):
        last = min(x for x in (line.broken_at, line.trimmed_at, n - 1) if x is not None)
        in_band, last_alert = False, None
        clock = TouchClock(line.created)
        for i in range(line.created + 1, first):          # touches before the window still count
            level = line.price_at(i)
            clock.feed(i, lows[i] <= level <= highs[i])
        for i in range(max(line.created + 1, first), last + 1):
            level = line.price_at(i)
            if level <= 0:
                continue
            # the approach side only, as the live in_band: never through the line
            lo_band, hi_band = (level, level * (1 + band)) if line.kind == SUPPORT else (level * (1 - band), level)
            e0, e1 = bar_slice(i)
            touched = False                                # this candle has reached the line
            for k in range(e0, e1):
                ts, _o, h, l, _c = evalc[k]
                if TL_SKIP_TOUCHED_ENTRY and (touched or ((_o <= level) if line.kind == SUPPORT else (_o >= level))):
                    touched = True                         # skipped; never re-arms the band, so it only removes alerts
                    continue
                crossed = (l <= level) if line.kind == SUPPORT else (h >= level)
                if held(ts):
                    touched = touched or crossed
                    continue
                outside = l > hi_band or h < lo_band
                band_ts = None
                if not outside and BAND_PROBE is not None:
                    end = evalc[k + 1][0] if k + 1 < len(evalc) else ts + eval_seconds
                    band_ts = BAND_PROBE(market, symbol, ts, end, lo_band, hi_band)
                    outside = band_ts is None
                if outside:
                    touched = touched or crossed
                    in_band = False
                    continue
                if not in_band and (last_alert is None or ts - last_alert >= TF_SECONDS[tf]):
                    plan = trades.trendline_plan(line.kind == SUPPORT, level, tf, i, opens, highs, lows, closes)
                    out.append(trade("trendline", plan, k, {
                        "band_ts": band_ts,
                        "line": line.kind, "swing_gap": line.x2 - line.x1, "age": i - line.created,
                        "quiet": clock.quiet(i), "max_streak": clock.max_streak}))
                    last_alert = ts
                in_band = True
                touched = touched or crossed
            clock.feed(i, lows[i] <= level <= highs[i])
    return out


BASELINE_SAMPLES = 100


def baseline(market, symbol, tf, evalc):
    """No-edge control: limit orders at random levels, scored exactly like the alerts.

    A level half the band away on a random side, SL TRENDLINE_SL_PCT beyond it,
    one 1R target and no hold limit, as the trendline trades.
    Under these rules a level with no edge does not win 50% at 1R: a limit only
    fills when price is moving against it, and a candle touching both SL and
    target is scored as the SL. This row is the number an alert has to beat.
    """
    per_bar = trades.EVAL_PER_BAR[market][tf]
    horizon = (FIB_TL_ENTRY_WAIT_BARS + FIB_TL_MAX_HOLD_BARS + 1) * per_bar
    if len(evalc) <= horizon + 1:
        return []
    rng = random.Random(f"{symbol}|{tf}")
    out = []
    for _ in range(BASELINE_SAMPLES):
        k = rng.randrange(0, len(evalc) - horizon - 1)
        price = evalc[k][4]
        support = rng.random() < 0.5
        level = price * (1 - BAND / 2) if support else price * (1 + BAND / 2)
        plan = trades.trendline_plan(support, level, tf)
        out.append({"market": market, "symbol": symbol, "tf": tf, "kind": "random", "alert_ts": evalc[k][0],
                    "plan": plan, "result": trades.simulate(plan, market, tf, evalc[k][0], evalc[k + 1:])})
    return out


def replay_symbol(market, symbol, base, evals, now):
    out = []
    for tf in TIMEFRAMES:
        res = trades.EVAL_RESOLUTION[market][tf]
        out += replay(market, symbol, tf, base.get(tf, []), evals.get(res, []), now)
        out += baseline(market, symbol, tf, evals.get(res, []))
    return out


# ----------------------------------------------------------------- report

def span_days(items):
    if not items:
        return 0
    ts = [t["alert_ts"] for t in items]
    return max(1.0, (max(ts) - min(ts)) / 86400)


def touch_order(fib_trades):
    """Split fib trades into the first touch of each fib and the later ones.

    A fib is one base and one top (a new top is a new fib). Its trades - at most
    one per zone - are ranked by when they filled: the first is the first time
    price reached the fib at all, usually Zone 1; a later one is the other zone
    after the first already traded, usually Zone 2 after price went through
    Zone 1. Unfilled alerts never touched the entry and are left out.
    """
    by_fib = defaultdict(list)
    for t in fib_trades:
        if t["result"]["filled"]:
            by_fib[t["fib_id"]].append(t)
    first, later = [], []
    for items in by_fib.values():
        items.sort(key=lambda t: t["result"]["fill_ts"])
        first.append(items[0])
        later += items[1:]
    return first, later


def write_report(all_trades, symbol_counts, started):
    rows = trades.summarise(all_trades)
    by_group = defaultdict(list)
    for t in all_trades:
        by_group[(t["market"], t["kind"], t["tf"])].append(t)
    out = [
        "# Fib + trendline alerts - history backtest",
        "",
        f"Generated {datetime.now(IST):%Y-%m-%d %H:%M} IST by `fib_trendline_backtest.py` in "
        f"{(time.time() - started) / 60:.0f} min. Symbols: "
        + ", ".join(f"{m.upper()} {c}" for m, c in symbol_counts.items()) + ".",
        "",
        "## Rules",
        "",
        f"- **Alert**: price comes within {FIB_TL_MAX_DISTANCE_PCT:g}% of a fib zone or a live trendline "
        "(down to touching it), with the live scanner's levels, once-only and re-arm rules, and the crypto "
        "01:00-08:00 IST hold.",
        f"- **Fib trade**: entry at the zone's near edge (Shiva's EX 2 ETH trades), SL {FIB_SL_HEIGHT_PCT:g}% of the "
        "zone's height beyond its far edge (the S/R zone rule).",
        "- **Trendline trade**: entry at the line, SL "
        + ", ".join(f"{TF_LABEL[tf]} {p}%" for tf, p in TRENDLINE_SL_PCT.items()) + " beyond it.",
        f"- Limit entry, filled only from the evaluation candle after the alert and within "
        f"{FIB_TL_ENTRY_WAIT_BARS} candles of the alert's timeframe; held up to {FIB_TL_MAX_HOLD_BARS} candles "
        "(trading candles - an NSE trade's clock stops overnight).",
        "- Scored on finer candles: crypto "
        + ", ".join(f"{TF_LABEL[tf]} on {r}" for tf, r in trades.EVAL_RESOLUTION[CRYPTO].items())
        + "; NSE " + ", ".join(f"{TF_LABEL[tf]} on {r}" for tf, r in trades.EVAL_RESOLUTION[NSE].items())
        + ". A candle that touches both the SL and a target counts as the SL.",
        f"- Breakeven: once +0.5R trades the stop moves {trades.BREAK_EVEN_PCT[CRYPTO]}% (crypto) / "
        f"{trades.BREAK_EVEN_PCT[NSE]}% (NSE) past entry, from the next candle - the zone trades' rule. "
        "A stop there is **BE**.",
        f"- Net R subtracts the round trip (crypto {trades.COST_PCT[CRYPTO]}%, NSE {trades.COST_PCT[NSE]}%) "
        "divided by the trade's own risk %, so tight stops pay more R in costs.",
        "",
        "**Win @1R** = reached 1R before the SL, out of trades that did one or the other. **Win @2R** the same "
        "for 2R. **Net R** = average result per filled trade booking everything at that target. "
        "Timeouts and still-open trades are left out of both; BE trades count in Net R, not in win rates.",
        "",
        "**Read every win rate against the Baseline table at the end, not against 50%.** Random levels "
        "scored by these same rules win well under 50% at 1R, because a limit order only fills while price "
        "moves against it and a candle touching both SL and target counts as the SL. An alert type has an "
        "edge only where it beats the baseline for the same market and timeframe.",
        "",
    ]
    for kind, title in (("fib", "Fib"), ("trendline", "Trendline"),
                        ("random", f"Baseline - random levels, no edge ({BASELINE_SAMPLES} per symbol and timeframe)")):
        out += [f"## {title}", "",
                "| Market | TF | Alerts | Alerts/day | Filled | SL | BE | 1R | 2R | Timeout | Open | No fill | "
                "Win @1R | Win @2R | Net R @1R | Net R @2R | Median risk |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for row in (r for r in rows if r["kind"] == kind):
            items = by_group[(row["market"], kind, row["tf"])]
            out.append(
                f"| {row['market'].upper()} | {TF_LABEL[row['tf']]} | {row['alerts']} | "
                f"{row['alerts'] / span_days(items):.1f} | {row['filled']} | {row['SL']} | {row['BE']} | {row['1R']} | "
                f"{row['2R']} | {row['timeout']} | {row['open']} | {row['no fill']} | "
                f"{trades.pct(row['win_1r'])} | {trades.pct(row['win_2r'])} | {trades.r(row['net_r_1r'])} | "
                f"{trades.r(row['net_r_2r'])} | {row['median_risk_pct']:.2f}% |"
            )
        out.append("")
    first, later = touch_order([t for t in all_trades if t["kind"] == "fib"])
    out += ["## Fib - first touch vs later touches", "",
            "Filled fib trades only, split by whether it was the first time price reached that fib "
            "(one base, one top) or a later touch of the same fib - the other zone, after the first "
            "had already traded. See `touch_order`.", "",
            "| Market | TF | Touch | Trades | SL | BE | 1R | 2R | Win @1R | Win @2R | Net R @1R | Net R @2R | "
            "Zone 1 share |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    tagged = [{**t, "kind": "first"} for t in first] + [{**t, "kind": "later"} for t in later]
    for row in sorted(trades.summarise(tagged), key=lambda r: (r["market"], TIMEFRAMES.index(r["tf"]), r["kind"])):
        items = [t for t in tagged if (t["market"], t["tf"], t["kind"]) == (row["market"], row["tf"], row["kind"])]
        zone1 = sum(1 for t in items if t["zone"] == 1) / len(items)
        out.append(
            f"| {row['market'].upper()} | {TF_LABEL[row['tf']]} | {row['kind']} | {row['filled']} | {row['SL']} | {row['BE']} | "
            f"{row['1R']} | {row['2R']} | {trades.pct(row['win_1r'])} | {trades.pct(row['win_2r'])} | "
            f"{trades.r(row['net_r_1r'])} | {trades.r(row['net_r_2r'])} | {zone1:.0%} |"
        )
    out.append("")
    real = [t for t in all_trades if t["kind"] != "random"]
    ambiguous = sum(1 for t in real if t["result"]["ambiguous"])
    out.append(f"{ambiguous} of {len(real)} alert trades had a candle touching both SL and a target "
               "(scored as SL).")
    REPORT_MD.parent.mkdir(exist_ok=True)
    REPORT_MD.write_text("\n".join(out) + "\n", encoding="utf-8")

    with TRADES_CSV.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["market", "symbol", "tf", "kind", "alert_ist", "side", "entry", "sl", "risk_pct",
                         "outcome", "filled", "fill_ist", "half_r", "r1", "r2", "sl_hit", "be_hit", "ambiguous"])
        for t in sorted(real, key=lambda t: t["alert_ts"]):
            r, p = t["result"], t["plan"]
            ist = lambda ts: datetime.fromtimestamp(ts, IST).strftime("%Y-%m-%d %H:%M") if ts else ""
            writer.writerow([t["market"], t["symbol"], t["tf"], t["kind"], ist(t["alert_ts"]), p["side"],
                             f"{p['entry']:.8g}", f"{p['sl']:.8g}", f"{trades.risk_pct(p):.3f}", r["outcome"],
                             r["filled"], ist(r["fill_ts"]), r["half"], r["r1"], r["r2"], r["sl"], r["be"],
                             r["ambiguous"]])
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--market", choices=[CRYPTO, NSE, "both"], default="both")
    args = parser.parse_args(argv)
    started = now = time.time()
    all_trades, symbol_counts = [], {}

    if args.market in (CRYPTO, "both"):
        symbols = scanner.active_watchlist()

        def one(symbol):
            try:
                data = crypto_data(symbol, now)
                return replay_symbol(CRYPTO, symbol, *data, now) if data else []
            except Exception as error:  # noqa: BLE001
                print(f"crypto {symbol} failed: {error}")
                return []

        with ThreadPoolExecutor(max_workers=4) as pool:
            for result in pool.map(one, symbols):
                all_trades += result
        symbol_counts[CRYPTO] = len(symbols)
        print(f"crypto: {sum(t['market'] == CRYPTO and t['kind'] != 'random' for t in all_trades)} alerts replayed")

    if args.market in (NSE, "both"):
        import nse_scanner

        symbols = nse_scanner.load_watchlist()
        for symbol, (base, evals) in nse_data(symbols).items():
            all_trades += replay_symbol(NSE, symbol, base, evals, now)
        symbol_counts[NSE] = len(symbols)
        print(f"nse: {sum(t['market'] == NSE and t['kind'] != 'random' for t in all_trades)} alerts replayed")

    write_report(all_trades, symbol_counts, started)
    print(REPORT_MD.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
