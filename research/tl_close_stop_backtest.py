"""Research only: the trendline trade with a close-based stop (lakky, 2026-10-24).

lakky: "i got a buy trade because it got a trendline support and if a candle closes
below that trendline then the sl will be the candle low and not the expected sl ...
only matter is closing".

Same trades as live (every TL touch alert, entry at the line, live fill rules), only
the stop changes:
  live   = lakky's candle stop (wick/body >= 0.75% past entry), 1R target
  close  = no stop while candles close on the right side of the line. Once a candle of
           the alert's timeframe CLOSES through the line (buy: below a support), the stop
           goes to that candle's low (sell: high) from the next candle on; out when price
           trades there (a gap fills at the open). Target = the live 1R target.
  close-exit = out at the close of the first candle that closes through the line (reference).
R is in units of the live stop distance (the close stop has no fixed risk), so %/trade is
the fair comparison. Net after fees + stop slippage. Crypto on Delta candles, NSE on Yahoo.
Crypto trades filling within 15 min of CPI/PPI/FOMC are left out. Open trades are not counted.

    PYTHONPATH=research python research/tl_close_stop_backtest.py --since 2026-06-01
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
from fib_trendline_data import CRYPTO, IST, NSE, candle_is_closed  # noqa: E402
from tl_break_candle_backtest import news_fine  # noqa: E402
import news_window_backtest as nw  # noqa: E402
from trendlines import SUPPORT, build_trendlines  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "tl_close_stop"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")), ("1D", ("1d",)), ("1W", ("1w",)), ("1M", ("1M",)))
RULES = ("live stop", "close stop (candle low)", "close-exit (at close)")

_plan = trades.trendline_plan


def _plan_with_bar(kind_is_support, level, tf, bar=None, *a, **k):
    plan = _plan(kind_is_support, level, tf, bar, *a, **k)
    plan["bar"] = bar
    return plan


trades.trendline_plan = _plan_with_bar


def close_rule(t, base, evalc, line, exit_at_close):
    """(outcome, exit price) for the close-based stop, or ("open", None)."""
    plan, res = t["plan"], t["result"]
    long = plan["side"] == "long"
    entry = plan["entry"]
    target = trades.target_price(plan)
    times = [c[0] for c in base]
    eval_ts = [c[0] for c in evalc]
    k = bisect.bisect_left(eval_ts, res["fill_ts"])
    stop = None
    cur = bisect.bisect_right(times, evalc[k][0]) - 1
    first = True
    while k < len(evalc):
        ts, o, h, l, c = evalc[k]
        j = bisect.bisect_right(times, ts) - 1
        if j != cur:                                   # bar `cur` has closed: did it close through the line?
            if stop is None and cur < len(base):
                level = line.price_at(cur)
                bc = base[cur]
                if (bc[4] < level) if long else (bc[4] > level):
                    if exit_at_close:
                        return "close", bc[4]
                    stop = bc[3] if long else bc[2]
            cur = j
        if stop is not None:
            if (o <= stop) if long else (o >= stop):
                return "stop", o
            if (l <= stop) if long else (h >= stop):
                return "stop", trades.slipped(stop, plan)
        if not first and ((h >= target) if long else (l <= target)):
            return "1R", target
        first = False
        k += 1
    return "open", None


def score(plan, market, exit_px):
    sign = 1 if plan["side"] == "long" else -1
    pct = sign * (exit_px - plan["entry"]) / plan["entry"] * 100 - trades.COST_PCT[market]
    return pct / trades.risk_pct(plan), pct


def chart_trades(market, symbol, base_all, evals, now, since):
    out = []
    for tf in fbt.TIMEFRAMES:
        base = base_all.get(tf, [])
        evalc = evals.get(trades.EVAL_RESOLUTION[market][tf], [])
        if base and not candle_is_closed(market, base[-1][0], tf, now):
            base = base[:-1]
        if len(base) <= fbt.MIN_BARS or not evalc:
            continue
        got = [t for t in fbt.replay(market, symbol, tf, base, evalc, now)
               if t["kind"] == "trendline" and t["alert_ts"] >= since and t["result"]["filled"]]
        if not got:
            continue
        highs, lows, closes = ([c[j] for c in base] for j in (2, 3, 4))
        lines = build_trendlines(highs, lows, closes, config.TRENDLINE_SWING_LENGTH, config.TRENDLINES_KEEP,
                                 history=True)
        for t in got:
            i, level = t["plan"]["bar"], t["plan"]["entry"]
            want = SUPPORT if t["plan"]["side"] == "long" else 1 - SUPPORT
            line = next((ln for ln in lines if ln.kind == want and ln.created < i
                         and abs(ln.price_at(i) - level) <= 1e-9 * max(1.0, abs(level))), None)
            if line is None:
                print(f"{symbol} {tf}: no line for a trade at bar {i}")
                continue
            live = trades.booked_r(t["plan"], market, t["result"])[1]
            rows = {"live stop": None if live is None else (live, live * trades.risk_pct(t["plan"]),
                                                            t["result"]["outcome"])}
            for name, at_close in (("close stop (candle low)", False), ("close-exit (at close)", True)):
                outcome, px = close_rule(t, base, evalc, line, at_close)
                rows[name] = None if px is None else (*score(t["plan"], market, px), outcome)
            out.append({"market": market, "symbol": symbol, "tf": tf, "t": t, "rows": rows})
    return out


def crypto_one(symbol, now, since):
    try:
        data = fbt.crypto_data(symbol, now)
        if not data:
            return []
        got = chart_trades(CRYPTO, symbol, *data, now, since)
        fine = news_fine(symbol, since, now)
        for g in got:
            g["news"] = nw.in_window(g["t"], fine)
        print(f"{symbol}: {len(got)} filled TL trades")
        return got
    except Exception as error:  # noqa: BLE001
        print(f"crypto {symbol} failed: {error}")
        return []


def row(rule, items):
    got = [g["rows"][rule] for g in items if g["rows"].get(rule)]
    n = len(got)
    wins = sum(1 for r, _p, _o in got if r > 0)
    return {"rule": rule, "trades": n, "win_%": round(100 * wins / n) if n else None,
            "R_per_trade": round(sum(r for r, _p, _o in got) / n, 3) if n else None,
            "%_per_trade": round(sum(p for _r, p, _o in got) / n, 3) if n else None,
            "%_total": round(sum(p for _r, p, _o in got), 1),
            "worst_%": round(min(p for _r, p, _o in got), 2) if n else None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-06-01")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-nse", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    since = int(pd.Timestamp(args.since, tz=IST).timestamp())
    now = int(time.time())
    got = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(lambda s: crypto_one(s, now, since), list(scanner.active_watchlist())[: args.limit or None]):
            got += res
    if not args.no_nse:
        import nse_scanner
        for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
            got += chart_trades(NSE, symbol, base, evals, now, since)
    skipped = sum(1 for g in got if g.get("news"))
    kept = [g for g in got if not g.get("news")]
    # same trades in every row: only trades closed under all three rules
    both = [g for g in kept if all(g["rows"].get(r) for r in RULES)]
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            pick = [g for g in both if g["market"] == market and g["tf"] in tfs]
            for rule in RULES:
                if pick:
                    rows.append({"market": market, "tf": group, **row(rule, pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame([{"market": g["market"], "symbol": g["symbol"], "tf": g["tf"], "side": g["t"]["plan"]["side"],
                   "alert_ist": pd.Timestamp(g["t"]["alert_ts"], unit="s", tz=IST).strftime("%Y-%m-%d %H:%M"),
                   "entry": g["t"]["plan"]["entry"], "live_sl": g["t"]["plan"]["sl"],
                   **{f"{r}|{k}": (v[i] if v else None) for r, v in g["rows"].items()
                      for i, k in ((0, "R"), (1, "pct"), (2, "outcome"))}}
                  for g in got]).to_csv(OUT / "trades.csv", index=False)
    text = [f"# Trendline trades: stop only after a close through the line ({args.since} to now)", "",
            "Live TL touch trades (same entries). R in units of the live stop distance; % per trade net of fees. "
            f"Only trades closed under all three rules. {skipped} crypto trades filled within 15 min of "
            "CPI/PPI/FOMC left out. Crypto on Delta candles.", "", df.to_markdown(index=False), ""]
    (OUT / "TL_CLOSE_STOP.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
