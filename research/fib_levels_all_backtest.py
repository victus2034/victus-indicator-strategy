"""Research only (lakky, 2026-10-20): alerts at every fib level - L1-L4 on 1D / 1W / 1M, L2-L4 on 4H.

  live        L3 only, once per zone.
  requested   the levels above, each alerts once.
  repeat      the same, and a level alerts again after price left its band and came back - at once if
              its last alert never touched the entry, after 4 hours if it did (his rule).

L1 / L2 are the weaker box's near / far edge, L3 / L4 the strong box's. Every level trades its own entry
with the one stop the fib alert has (25% of the strong box beyond L4), 2R + breakeven, as fib_level_whatif.
Sep 1 to now, net after fees; trades filled within 15 min of a US CPI / PPI / FOMC release left out.

    PYTHONPATH=research python research/fib_levels_all_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
from fib_entry_touched_backtest import replay_all  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402
from trail_fib_tl_backtest import news  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_levels_all"
GROUPS = (("4H", ("4h",)), ("1D", ("1d",)), ("1W", ("1w",)), ("1M", ("1M",)))
REQUESTED = {"4h": ("L2", "L3", "L4"), "1d": ("L1", "L2", "L3", "L4"), "1w": ("L1", "L2", "L3", "L4"),
             "1M": ("L1", "L2", "L3", "L4")}
MODES = (("live: L3 once", dict(FIB_LEVELS=None, FIB_L4=False, FIB_REARM=False, FIB_REPEAT_WAIT=0)),
         ("requested levels, once each", dict(FIB_LEVELS=REQUESTED, FIB_REARM=False, FIB_REPEAT_WAIT=0)),
         ("requested + repeat rule", dict(FIB_LEVELS=REQUESTED, FIB_REARM=True, FIB_REPEAT_WAIT=4 * 3600)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    runs = {}
    for label, flags in MODES:
        for name, value in flags.items():
            setattr(fbt, name, value)
        runs[label] = [t for t in replay_all(now) if t["alert_ts"] >= since and not news(t["result"].get("fill_ts"))]
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for label, items in runs.items():
                pick = [t for t in items if t["market"] == market and t["tf"] in tfs]
                if pick:
                    rows.append({"market": market, "tf": group, "level": "all", **row(label, pick)})
            for level in ("L1", "L2", "L3", "L4"):
                pick = [t for t in runs["requested levels, once each"]
                        if t["market"] == market and t["tf"] in tfs and t.get("level") == level]
                if pick:
                    rows.append({"market": market, "tf": group, "level": level, **row("requested, once", pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib alerts at every level ({args.since} to now)", "",
            "L1-L4 on 1D/1W/1M, L2-L4 on 4H. Each level trades its own entry with the alert's stop, 2R + BE, "
            "net after fees. R and % per trade and in total. Crypto on Delta candles. Entries filled within "
            "15 min of US CPI/PPI/FOMC left out.", "", df.to_markdown(index=False), ""]
    (OUT / "FIB_LEVELS_ALL.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
