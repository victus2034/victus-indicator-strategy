"""Trendline anchor backtest - which earlier swing a new swing joins to.

Lakky, 2026-10-07 (HYPEUSDT 1D): lines start far off-screen and come in
near-parallel twins. Pine 6b joins each new swing to the OLDEST earlier swing
that no swing in between cuts; its tooltip says "the last two rising swing
lows". This replays both - oldest (live) and nearest - with the same data,
trade rules and scoring as trendline_length_backtest.py. Nothing live changes.

    python research/trendline_anchor_backtest.py
"""
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import trendlines  # noqa: E402
from trendline_length_backtest import CRYPTO, LIVE_TFS, NSE, bt, load, no_fibs, run, stats  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "trendline_anchor"
OLDEST = trendlines._best_anchor


def nearest(xs, ys, nx, ny, lower):
    """Latest earlier swing beyond which no swing in between cuts the line."""
    for i in range(len(xs) - 1, -1, -1):
        if (ys[i] < ny) if lower else (ys[i] > ny):
            ok = True
            for j in range(i + 1, len(xs)):
                yl = ys[i] + (ny - ys[i]) * (xs[j] - xs[i]) / (nx - xs[i])
                if (ys[j] < yl) if lower else (ys[j] > yl):
                    ok = False
                    break
            if ok:
                return i
    return -1


def main():
    bt.fib_engine = SimpleNamespace(run=no_fibs)
    now = time.time()
    data = load(now)
    results = {}
    for name, fn in (("oldest (live)", OLDEST), ("nearest", nearest)):
        trendlines._best_anchor = fn
        results[name] = run(10, data, now)
    trendlines._best_anchor = OLDEST
    lines = ["# Trendline anchor backtest (trendlines only, length 10)", "",
             "oldest = live Pine rule; nearest = join the last valid earlier swing. Same data, trade rules "
             "and scoring as `trendline_length_backtest.py`.", "",
             "| market | tf | anchor | alerts | /day | filled | win@2R | net R | R/trade |",
             "|---|---|---|---|---|---|---|---|---|"]
    for market in (CRYPTO, NSE):
        for tf in LIVE_TFS + ["all"]:
            for name, items in results.items():
                sel = [t for t in items if t["market"] == market and (t["tf"] == tf or (tf == "all" and t["tf"] in LIVE_TFS))]
                s = stats(sel)
                lines.append(f"| {market} | {tf} | {name} | {s['alerts']} | {s['per_day']:.1f} | {s['filled']} | "
                             f"{s['win2r'] * 100:.0f}% | {s['net']:+.1f} | {s['per_trade']:+.3f} |")
    lines += ["", "## Total, live timeframes, both markets", "", "| anchor | alerts | filled | net R | R/trade |", "|---|---|---|---|---|"]
    for name, items in results.items():
        s = stats([t for t in items if t["tf"] in LIVE_TFS])
        lines.append(f"| {name} | {s['alerts']} | {s['filled']} | {s['net']:+.1f} | {s['per_trade']:+.3f} |")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
