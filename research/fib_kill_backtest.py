"""Research only: when an old fib dies (lakky, 2026-10-13, DOGE 1D).

Second round (same day): the Oct 13 1D wick dipped just under L4 (0.08064) of the\nAug-Sep BUY fib and killed it, though the trade's stop (0.07959) held.

Live, a fib dies only once price takes out its origin (the top of a down fib).
DOGE 1D ran 0.06762 -> 0.1059 straight through both sell boxes of the May fib
(top 0.11857) and the bot kept that SELL fib; lakky's chart draws the BUY fib
0.06762 -> 0.1059. Variants: the fib also dies once price trades past its
strong box's far edge (L4, 0.66 of the range from the extreme), the new fib
starting at the extreme (low) or at the last higher low (the live flip rule).
Sep 1 to now, live fib rules otherwise.

    PYTHONPATH=research python research/fib_kill_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import inspect
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import fib_engine  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
from fib_entry_touched_backtest import replay_all  # noqa: E402
from fib_touched_before_backtest import GROUPS, row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_kill"
LIVE_RUN = fib_engine.run


KILL_AT = {"L4": None, "stop": 0.66 + 0.25 * 0.11, "old": 0}


def variant(rule):
    """The live engine (fib dies past L4) with the kill line moved: 'stop' = 25% of
    the box height past L4 (where the fib trade is stopped), 'old' = no L4 kill."""
    if rule == "L4":
        return LIVE_RUN
    s = inspect.getsource(fib_engine)
    for old in ("l[i] < E - ZONE1 * (E - O)", "h[i] > E + ZONE1 * (O - E)"):
        assert old in s
        s = s.replace(old, "False" if rule == "old" else old.replace("ZONE1", str(KILL_AT[rule])))
    s = s.replace("past_l4 = l[i] >= O", "past_l4 = l[i] >= O").replace("past_l4 = h[i] <= O", "past_l4 = h[i] <= O")
    ns = {}
    exec(compile(s, "fib_engine_variant", "exec"), ns)
    return ns["run"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    runs = {}
    for label, rule in (("old: dies only past its top/base", "old"),
                        ("live: dies past L4", "L4"),
                        ("dies past the stop (L4 + 25% box)", "stop")):
        fib_engine.run = variant(rule)
        runs[label] = [t for t in replay_all(now) if t["alert_ts"] >= since]
    fib_engine.run = LIVE_RUN
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for label, items in runs.items():
                pick = [t for t in items if t["market"] == market and t["tf"] in tfs]
                if pick:
                    rows.append({"market": market, "tf": group, **row(label, pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib: when an old fib dies ({args.since} to now)", "",
            "Live fib rules otherwise (deeper zone, S/R stop, 2R + BE, entry not reached this candle), net after fees. "
            "R and % per trade and in total (% = R x the trade's stop distance).", "",
            df.to_markdown(index=False), ""]
    (OUT / "FIB_KILL.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
