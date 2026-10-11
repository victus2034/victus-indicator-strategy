"""Trendlines a candle closed through before they were drawn (v12.7.9 fix).

Lakky, 2026-10-10, DABUR 1D: a resistance line kept extending after a candle
had closed above it. A line is drawn `length` candles after its second swing,
and until v12.7.9 the closes in those candles were never checked.

1. DABUR 1D: every line under the old and the new rule, with the closes in
   its confirm window, so the chart can be checked candle by candle.
2. Quick backtest, alerts since --since: old rule vs new (trendlines only,
   same data, trade rules and scoring as fib_trendline_backtest.py), and how
   many lines were drawn already broken. Nothing live changes.

    python research/trendline_confirm_window.py --since 2026-09-01
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from fib_trendline_data import IST, nse_charts  # noqa: E402
from trendlines import SUPPORT, build_trendlines  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "trendline_confirm"
L = config.TRENDLINE_SWING_LENGTH


def trace(symbol, tf, since):
    rows = nse_charts([symbol], [tf])[symbol][tf]
    t = [datetime.fromtimestamp(r[0], IST).strftime("%Y-%m-%d") for r in rows]
    H = [r[2] for r in rows]; Lo = [r[3] for r in rows]; C = [r[4] for r in rows]
    out = [f"# {symbol} {tf}: {len(rows)} bars {t[0]} -> {t[-1]} (last bar may be forming)", ""]
    old = build_trendlines(H, Lo, C, L, config.TRENDLINES_KEEP, history=True, check_confirm_window=False)
    new = build_trendlines(H, Lo, C, L, config.TRENDLINES_KEEP, history=True)
    for o, n in zip(old, new):
        if t[o.created] < since and o.broken_at is not None and t[o.broken_at] < since:
            continue
        kind = "RES" if o.kind else "SUP"
        state = lambda ln: ("live" if ln.broken_at is None else f"broken {t[ln.broken_at]}") + \
            ("" if ln.trimmed_at is None else f", trimmed {t[ln.trimmed_at]}")
        out.append(f"{kind} {o.y1:.2f} ({t[o.x1]}) -> {o.y2:.2f} ({t[o.x2]}), drawn {t[o.created]}")
        out.append(f"   old rule: {state(o)}   new rule: {state(n)}")
        for k in range(o.x2 + 1, min(o.created + 3, len(C))):
            y = o.price_at(k)
            through = (C[k] < y) if o.kind == SUPPORT else (C[k] > y)
            tag = " <- closed through" if through else ""
            when = "window" if k < o.created else ("drawn" if k == o.created else "after")
            out.append(f"     {t[k]} {when:6s} close {C[k]:8.2f}  line {y:8.2f}{tag}")
    return out


def backtest(since):
    from trendline_length_backtest import LIVE_TFS, bt, load, no_fibs, run, stats
    from fib_trendline_data import CRYPTO, NSE
    bt.fib_engine = SimpleNamespace(run=no_fibs)
    now = time.time()
    data = load(now)
    start = datetime.fromisoformat(since).replace(tzinfo=IST).timestamp()
    live = bt.build_trendlines
    results = {}
    for name, flag in (("old", False), ("new", True)):
        bt.build_trendlines = lambda *a, _f=flag, **kw: live(*a, check_confirm_window=_f, **kw)
        results[name] = [x for x in run(L, data, now) if x["alert_ts"] >= start]
    bt.build_trendlines = live
    born = {CRYPTO: [0, 0], NSE: [0, 0]}
    for market, symbol, (base, _e) in data:
        for tf in LIVE_TFS:
            c = base.get(tf, [])
            if len(c) < 30:
                continue
            ls = build_trendlines([x[2] for x in c], [x[3] for x in c], [x[4] for x in c], L,
                                  config.TRENDLINES_KEEP, history=True)
            born[market][0] += len(ls)
            born[market][1] += sum(1 for x in ls if x.broken_at is not None and x.broken_at < x.created)
    lines = [f"# Trendline confirm-window fix: quick backtest, alerts since {since}", "",
             "old = closes before the line is drawn not checked (v12.7.8); new = v12.7.9. Trendlines only.", "",
             "| market | tf | rule | alerts | filled | win@2R | net R | R/trade |", "|---|---|---|---|---|---|---|---|"]
    for market in (CRYPTO, NSE):
        for tf in LIVE_TFS + ["all"]:
            for name, items in results.items():
                sel = [x for x in items if x["market"] == market and (x["tf"] == tf or (tf == "all" and x["tf"] in LIVE_TFS))]
                s = stats(sel)
                lines.append(f"| {market} | {tf} | {name} | {s['alerts']} | {s['filled']} | "
                             f"{s['win2r'] * 100:.0f}% | {s['net']:+.1f} | {s['per_trade']:+.3f} |")
    lines += ["", "## Lines drawn already broken (all history, live timeframes)", "",
              "| market | lines | drawn broken | share |", "|---|---|---|---|"]
    for market, (n, b) in born.items():
        lines.append(f"| {market} | {n} | {b} | {b / n * 100 if n else 0:.1f}% |")
    return lines


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="DABUR.NS")
    p.add_argument("--tf", default="1d")
    p.add_argument("--since", default="2026-09-01")
    p.add_argument("--skip-backtest", action="store_true")
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    text = trace(a.symbol, a.tf, a.since)
    (OUT / f"{a.symbol.replace('.', '_')}_{a.tf}.txt").write_text("\n".join(text) + "\n")
    print("\n".join(text))
    if not a.skip_backtest:
        res = backtest(a.since)
        (OUT / "RESULTS.md").write_text("\n".join(res) + "\n")
        print("\n".join(res))


if __name__ == "__main__":
    main()
