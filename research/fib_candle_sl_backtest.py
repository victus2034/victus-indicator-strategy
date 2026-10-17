"""Research only: lakky's fib stop, read off his RLC 1D charts (2026-10-17).

Chart 1: entry 0.8030, SL 0.7875 - just under the last candle low below the entry
(0.7893), 1.9% risk, target 2R. Chart 2: the "logical" stop was the structure at
0.7414 (8.3%), too much risk, so he took ~3.5%. The bot's stop (25% of the box past
L4) printed 0.63169, 21.3%.

Rule tested (BUY; SELL mirrored): walking back from the alert candle (closed candles
of the alert's own timeframe), the most recent candle whose wick is at least
MIN_GAP_PCT below the entry and the most recent whose body is - the closer of the
two (trades.candle_stop, the trendline rule) - with BUFFER_PCT more room. Then:
  cap  X%  - a stop further than X% from entry moves in to X%
  skip X%  - a stop further than X% means no trade
No candle found -> the cap (cap rules) / no trade (skip rules).

Same alerts as live (fib_trendline_backtest.replay, deeper zone, all live alert
rules), same entry, same 2R + BE scoring; only the stop changes.

    PYTHONPATH=research python research/fib_candle_sl_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import bisect
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE, candle_is_closed  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_candle_sl"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")))
MIN_GAP_PCT = 0.75
BUFFER_PCT = 0.2

RULES = (
    ("live (25% of box)", None),
    ("candle SL, no cap", ("cap", None)),
    ("candle SL, cap 3.5%", ("cap", 3.5)),
    ("candle SL, cap 5%", ("cap", 5.0)),
    ("candle SL, skip if > 3.5%", ("skip", 3.5)),
    ("candle SL, skip if > 5%", ("skip", 5.0)),
    ("fixed 3.5% SL", ("fixed", 3.5)),
)


def candle_level(long, entry, bar, base):
    """Most recent closed wick / body at least MIN_GAP_PCT past entry, the closer one, plus the buffer."""
    opens = [c[1] for c in base]
    highs = [c[2] for c in base]
    lows = [c[3] for c in base]
    closes = [c[4] for c in base]
    gap = entry * MIN_GAP_PCT / 100
    wick = body = None
    for j in range(min(bar, len(lows)) - 1, -1, -1):
        w = lows[j] if long else highs[j]
        b = min(opens[j], closes[j]) if long else max(opens[j], closes[j])
        if wick is None and ((w <= entry - gap) if long else (w >= entry + gap)):
            wick = w
        if body is None and ((b <= entry - gap) if long else (b >= entry + gap)):
            body = b
        if wick is not None and body is not None:
            break
    got = [x for x in (wick, body) if x is not None]
    if not got:
        return None
    level = max(got) if long else min(got)
    return level * (1 - BUFFER_PCT / 100) if long else level * (1 + BUFFER_PCT / 100)


def new_stop(rule, plan, level):
    long = plan["side"] == "long"
    entry = plan["entry"]
    mode, x = rule

    def at(pct):
        return entry * (1 - pct / 100) if long else entry * (1 + pct / 100)
    if mode == "fixed":
        return at(x)
    if level is None:
        return at(x) if (mode == "cap" and x) else None
    risk = abs(entry - level) / entry * 100
    if x is None or risk <= x:
        return level
    return at(x) if mode == "cap" else None


def rescore(market, tf, base, evalc, now, t):
    """Every rule's version of one live fib trade."""
    if base and not candle_is_closed(market, base[-1][0], tf, now):
        base = base[:-1]
    times = [c[0] for c in base]
    bar = bisect.bisect_right(times, t["alert_ts"]) - 1      # the candle the alert fired in
    eval_ts = [c[0] for c in evalc]
    k = bisect.bisect_left(eval_ts, t["alert_ts"])
    horizon = (config.FIB_TL_ENTRY_WAIT_BARS + config.FIB_TL_MAX_HOLD_BARS + 1) * trades.EVAL_PER_BAR[market][tf]
    after = evalc[k + 1:k + 1 + horizon]
    plan = t["plan"]
    level = candle_level(plan["side"] == "long", plan["entry"], bar, base) if bar > 0 else None
    out = []
    for label, rule in RULES:
        if rule is None:
            out.append({**t, "rule": label})
            continue
        sl = new_stop(rule, plan, level)
        if sl is None:
            out.append({**t, "rule": label, "skipped": True})
            continue
        p = {**plan, "sl": sl}
        out.append({**t, "rule": label, "plan": p, "result": trades.simulate(p, market, tf, t["alert_ts"], after)})
    return out


def fibs_for(market, symbol, base, evals, now, since):
    got = []
    for tf in fbt.TIMEFRAMES:
        res = trades.EVAL_RESOLUTION[market][tf]
        evalc = evals.get(res, [])
        for t in fbt.replay(market, symbol, tf, base.get(tf, []), evalc, now):
            if t["kind"] == "fib" and t["alert_ts"] >= since:
                got += rescore(market, tf, base.get(tf, []), evalc, now, t)
    return got


def collect(since, now, limit):
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    got = []

    def one(symbol):
        try:
            data = fbt.crypto_data(symbol, now)
            out = fibs_for(CRYPTO, symbol, *data, now, since) if data else []
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            out = []
        print(f"{symbol}: {len(out) // len(RULES)} fib alerts")
        return out
    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(one, list(config.CRYPTO_WATCHLIST)[: limit or None]):
            got += res
    import nse_scanner
    symbols = nse_scanner.load_watchlist()[: limit or None]
    for symbol, (base, evals) in fbt.nse_data(symbols).items():
        try:
            got += fibs_for(NSE, symbol, base, evals, now, since)
        except Exception as error:  # noqa: BLE001
            print(f"NSE {symbol} failed: {error}")
    return got


def table(got):
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for label, _ in RULES:
                items = [t for t in got if t["market"] == market and t["tf"] in tfs and t["rule"] == label]
                kept = [t for t in items if not t.get("skipped")]
                if not items:
                    continue
                r = row(label, kept) if kept else {"rule": label, "alerts": 0, "trades": 0}
                stops = [trades.risk_pct(t["plan"]) for t in kept]
                rows.append({"market": market, "tf": group, **r, "alerts": len(items),
                             "skipped": len(items) - len(kept),
                             "median_stop_%": round(pd.Series(stops).median(), 2) if stops else None})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--limit", type=int, default=0, help="first N symbols per market (smoke test)")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    since = int(pd.Timestamp(args.since, tz=IST).timestamp())
    now = int(time.time())
    got = collect(since, now, args.limit)
    df = table(got)
    df.to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame([{"market": t["market"], "symbol": t["symbol"], "tf": t["tf"], "rule": t["rule"],
                   "alert_ts": t["alert_ts"], "side": t["plan"]["side"], "entry": t["plan"]["entry"],
                   "sl": None if t.get("skipped") else t["plan"]["sl"],
                   "stop_%": None if t.get("skipped") else round(trades.risk_pct(t["plan"]), 2),
                   "outcome": "skipped" if t.get("skipped") else t["result"]["outcome"],
                   "net_r": (trades.booked_r(t["plan"], t["market"], t["result"])[1]
                             if not t.get("skipped") and t["result"]["filled"] else None)}
                  for t in got]).to_csv(OUT / "trades.csv", index=False)
    text = [f"# Fib stop: lakky's candle SL vs live ({args.since} to now)", "",
            f"Candle SL = most recent closed wick/body >= {MIN_GAP_PCT}% past entry (closer one) + "
            f"{BUFFER_PCT}% buffer. Same alerts, entry and 2R + BE scoring as live; net after fees. "
            "% = R x the trade's stop distance. Crypto on Delta candles, NSE on Yahoo.", "",
            df.to_markdown(index=False), ""]
    (OUT / "FIB_CANDLE_SL.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
