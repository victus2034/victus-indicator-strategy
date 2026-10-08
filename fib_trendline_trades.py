"""How a fib or trendline alert is traded and scored - one set of rules for the
history backtest (fib_trendline_backtest.py) and the daily report
(fib_trendline_daily_report.py), so the two can never grade differently.

Rules (Shiva, 2026-09-29):
- Fib: entry at the zone's near edge (Shiva's EX 2/278 ETH trades, 2723.94 /
  2672.86); SL FIB_SL_HEIGHT_PCT of the box's height beyond its far edge, the
  S/R zone rule (Lakky, 2026-10-08). It was the inner fib's 0.55 line before.
- Trendline: entry at the line's price when the alert fired, SL
  TRENDLINE_SL_PCT[tf] % beyond it. Support is a buy, resistance a sell.
- A limit entry: it fills only if price trades to it within ENTRY_WAIT_BARS
  candles of the alert's timeframe (trading candles, EVAL_PER_BAR), and only from the evaluation candle after
  the alert (inside the alert's own candle there is no telling which came first).
- Then 1R and 2R targets against the SL, for MAX_HOLD_BARS candles. A candle
  that touches both the SL and a target is scored as the SL - the order inside
  a candle is unknown, so the result can only be understated, never flattered.
  Scoring runs on finer candles than the alert's (EVAL_RESOLUTION) to keep
  those same-candle cases rare.
- Breakeven, the same rule as the zone trades (daily_backtest_summary,
  paper_trading): once +0.5R trades, the stop moves just past entry to clear the
  round trip (NSE 0.120%, crypto CRYPTO_BREAK_EVEN_OFFSET_PCT), from the next
  candle on. A stop there is "BE". A tight stop whose +0.5R is short of that
  level keeps its original stop, since a stop above the market fills at once.
"""
from collections import defaultdict

from config import FIB_TL_ENTRY_WAIT_BARS, FIB_TL_MAX_HOLD_BARS, TRENDLINE_SL_PCT
from daily_backtest_summary import (
    BREAK_EVEN_ENABLED,
    BREAK_EVEN_OFFSET_PCT,
    CRYPTO_BREAK_EVEN_OFFSET_PCT,
    CRYPTO_ROUND_TRIP_COST_PCT,
    HALF_R,
    ROUND_TRIP_COST_PCT,
    SL_FILL_SLIPPAGE_PCT,
)
from fib_trendline_data import CRYPTO, NSE

# Round trip, % of notional - the same numbers daily_backtest_summary.py uses.
COST_PCT = {CRYPTO: CRYPTO_ROUND_TRIP_COST_PCT, NSE: ROUND_TRIP_COST_PCT}
# Candles each alert timeframe is scored on.
EVAL_RESOLUTION = {
    CRYPTO: {"30m": "5m", "4h": "1h", "1d": "4h", "1w": "1d", "1M": "1d"},
    NSE: {"30m": "5m", "4h": "1h", "1d": "1h", "1w": "1d", "1M": "1d"},
}
# Evaluation candles in one candle of the alert's timeframe, in trading time -
# an NSE session is 6h15m, so its 1D holds 7 hourly candles and its 1W 5 daily.
EVAL_PER_BAR = {
    CRYPTO: {"30m": 6, "4h": 4, "1d": 6, "1w": 7, "1M": 30},
    NSE: {"30m": 6, "4h": 4, "1d": 7, "1w": 5, "1M": 21},
}
# Where the stop goes once +0.5R trades, as % past entry - the zone trades' numbers.
BREAK_EVEN_PCT = {CRYPTO: CRYPTO_BREAK_EVEN_OFFSET_PCT, NSE: BREAK_EVEN_OFFSET_PCT}
OUTCOMES = ["SL", "BE", "1R", "2R", "timeout", "open", "no fill"]


def fib_plan(d, zone):
    return {"side": "long" if d == 1 else "short", "entry": zone["entry"], "sl": zone["sl"]}


def trendline_plan(kind_is_support, level, tf):
    pct = TRENDLINE_SL_PCT.get(tf, 1.0) / 100
    if kind_is_support:
        return {"side": "long", "entry": level, "sl": level * (1 - pct)}
    return {"side": "short", "entry": level, "sl": level * (1 + pct)}


def break_even_stop(plan, market):
    entry = plan["entry"]
    sign = 1 if plan["side"] == "long" else -1
    return entry + sign * entry * BREAK_EVEN_PCT[market] / 100


def slipped(price, plan):
    """A stop's fill: SL_FILL_SLIPPAGE_PCT past its trigger, as the zone trades pay."""
    sign = 1 if plan["side"] == "long" else -1
    return price - sign * price * SL_FILL_SLIPPAGE_PCT / 100


def stop_r(plan):
    """Gross R of a full stop, slip included - a little worse than -1."""
    sign = 1 if plan["side"] == "long" else -1
    return sign * (slipped(plan["sl"], plan) - plan["entry"]) / abs(plan["entry"] - plan["sl"])


def break_even_r(plan, market):
    """Gross R booked when the breakeven stop is hit, slip included - near 0."""
    sign = 1 if plan["side"] == "long" else -1
    exit_price = slipped(break_even_stop(plan, market), plan)
    return sign * (exit_price - plan["entry"]) / abs(plan["entry"] - plan["sl"])


def simulate(plan, market, tf, alert_ts, candles):
    """Score one alert on evaluation candles; `candles` must start after the alert moment.

    Returns dict(outcome, filled, fill_ts, half, r1, r2, sl, be, ambiguous, resolved, end_ts).
    outcome: SL (stopped before 1R) | BE (reached +0.5R, then the breakeven stop
    before 1R) | 1R (reached 1R, not 2R) | 2R | timeout (filled, neither a stop
    nor 1R in time) | open (data ran out first) | no fill.
    sl / be say which stop finally closed the trade, also after 1R.
    """
    side, entry, sl = plan["side"], plan["entry"], plan["sl"]
    risk = abs(entry - sl)
    long = side == "long"
    t1 = entry + risk if long else entry - risk
    t2 = entry + 2 * risk if long else entry - 2 * risk
    half = entry + HALF_R * risk if long else entry - HALF_R * risk
    be_stop = break_even_stop(plan, market)
    # On a tight stop the offset can be past +0.5R itself; that stop would fill
    # at once, so nobody places it and the original stop stays.
    be_reachable = (half >= be_stop) if long else (half <= be_stop)
    per_bar = EVAL_PER_BAR[market][tf]
    wait_n, hold_n = FIB_TL_ENTRY_WAIT_BARS * per_bar, FIB_TL_MAX_HOLD_BARS * per_bar
    res = dict(outcome="open", filled=False, fill_ts=None, half=False, r1=False, r2=False, sl=False,
               be=False, ambiguous=False, resolved=False, end_ts=None)
    if risk <= 0:
        res.update(outcome="no fill", resolved=True)
        return res
    seen = fill_index = 0
    for ts, _o, h, l, _c in candles:
        if ts <= alert_ts:
            continue
        seen += 1
        if not res["filled"]:
            if seen > wait_n:
                res.update(outcome="no fill", resolved=True, end_ts=ts)
                return res
            if (l <= entry) if long else (h >= entry):
                res.update(filled=True, fill_ts=ts)
                fill_index = seen
                if (l <= sl) if long else (h >= sl):   # ran straight through entry to the stop
                    res.update(outcome="SL", sl=True, resolved=True, end_ts=ts)
                    return res
            continue
        if seen - fill_index > hold_n:
            res.update(outcome="1R" if res["r1"] else "timeout", resolved=True, end_ts=ts)
            return res
        # The stop moves from the candle after +0.5R traded - inside that candle
        # the order is unknown.
        moved = res["half"] and BREAK_EVEN_ENABLED and be_reachable
        stop = be_stop if moved else sl
        hit_stop = (l <= stop) if long else (h >= stop)
        hit_half = (h >= half) if long else (l <= half)
        hit1 = (h >= t1) if long else (l <= t1)
        hit2 = (h >= t2) if long else (l <= t2)
        if hit_stop:
            if (hit1 and not res["r1"]) or hit2:
                res["ambiguous"] = True
            outcome = "1R" if res["r1"] else ("BE" if moved else "SL")
            res.update({"outcome": outcome, "be" if moved else "sl": True, "resolved": True, "end_ts": ts})
            return res
        if hit_half or hit1:
            res["half"] = True
        if hit1:
            res["r1"] = True
        if hit2:
            res.update(r2=True, outcome="2R", resolved=True, end_ts=ts)
            return res
    if res["filled"] and res["r1"]:
        res["outcome"] = "1R"          # 1R is banked; 2R still possible, so not resolved
    return res


def already_stopped(plan, price):
    """True when price was already through the stop as the alert went out - not
    a trade anyone could take. The scanner no longer sends these
    (fib_trendline_scanner.fib_distance); the ones it sent are scored as no fill."""
    if price is None:
        return False
    return price <= plan["sl"] if plan["side"] == "long" else price >= plan["sl"]


def risk_pct(plan):
    return abs(plan["entry"] - plan["sl"]) / plan["entry"] * 100


def booked_r(plan, market, result):
    """Net R after costs (out at 1R, held for 2R) - None where that booking is undecided."""
    cost_r = COST_PCT[market] / risk_pct(plan)
    # Stops pay the slip, like the zone trades; it used to be a flat -1.
    closed_r = stop_r(plan) if result["sl"] else break_even_r(plan, market) if result.get("be") else None
    at1 = 1 if result["r1"] else closed_r
    at2 = 2 if result["r2"] else closed_r
    return (None if at1 is None else at1 - cost_r, None if at2 is None else at2 - cost_r)


def summarise(trades):
    """trades: dicts with market, kind, tf, plan and result. Rows grouped by (market, kind, tf)."""
    groups = defaultdict(list)
    for t in trades:
        groups[(t["market"], t["kind"], t["tf"])].append(t)
    rows = []
    for key in sorted(groups, key=lambda k: (k[0], k[1], ["30m", "4h", "1d", "1w", "1M"].index(k[2]))):
        rows.append(_row(key, groups[key]))
    return rows


def _row(key, trades):
    market, kind, tf = key
    count = defaultdict(int)
    net1, net2 = [], []
    for t in trades:
        r = t["result"]
        count[r["outcome"]] += 1
        if not r["filled"]:
            continue
        at1, at2 = booked_r(t["plan"], market, r)
        if at1 is not None:
            net1.append(at1)
        if at2 is not None:
            net2.append(at2)
    hits1 = count["1R"] + count["2R"]
    stops2 = count["SL"] + sum(1 for t in trades if t["result"]["outcome"] == "1R" and t["result"]["sl"])
    return {
        "market": market, "kind": kind, "tf": tf, "alerts": len(trades),
        "filled": sum(1 for t in trades if t["result"]["filled"]),
        **{o: count[o] for o in OUTCOMES},
        "win_1r": hits1 / (hits1 + count["SL"]) if hits1 + count["SL"] else None,
        "win_2r": count["2R"] / (count["2R"] + stops2) if count["2R"] + stops2 else None,
        "net_r_1r": sum(net1) / len(net1) if net1 else None,
        "net_r_2r": sum(net2) / len(net2) if net2 else None,
        "median_risk_pct": sorted(risk_pct(t["plan"]) for t in trades)[len(trades) // 2] if trades else None,
    }


def pct(value):
    return "-" if value is None else f"{value * 100:.0f}%"


def r(value):
    return "-" if value is None else f"{value:+.2f}R"
