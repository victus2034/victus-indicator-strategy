"""Research only (lakky, 2026-10-20, BTW 4H): L3 and L4 as separate alerts, with his repeat rule.

  live      one L3 alert per fib zone.
  L3 + L4   plus one L4 alert (the strong box's far edge; entry L4, same stop), no repeats.
  lakky     L3 + L4, and each level may alert again after price left its band by REARM_FACTOR and
            came back - at once if its last alert never touched the entry, after 4 hours if it did.

Sep 1 to now, live fib rules otherwise (deeper zone, S/R stop, 2R + BE), net after fees. Trades filled
within 15 min of a US CPI / PPI / FOMC release are left out.

    PYTHONPATH=research python research/fib_l3_l4_backtest.py --since 2026-09-01
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

OUT = Path(__file__).resolve().parent / "out" / "fib_l3_l4"
GROUPS = (("4H", ("4h",)), ("1D", ("1d",)), ("1W", ("1w",)), ("1M", ("1M",)))
MODES = (("live: L3 once", dict(FIB_L4=False, FIB_REARM=False, FIB_REPEAT_WAIT=0)),
         ("L3 + L4, once each", dict(FIB_L4=True, FIB_REARM=False, FIB_REPEAT_WAIT=0)),
         ("lakky: L3 + L4, repeat rule", dict(FIB_L4=True, FIB_REARM=True, FIB_REPEAT_WAIT=4 * 3600)))


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
    live = runs[MODES[0][0]]
    runs["lakky: only the L4 alerts"] = [t for t in runs[MODES[2][0]] if t.get("level") == "L4"]
    runs["lakky: only L3 repeats"] = [t for t in runs[MODES[2][0]] if t.get("level") == "L3"
                                     and (t["symbol"], t["tf"], t["fib_id"], t["alert_ts"])
                                     not in {(x["symbol"], x["tf"], x["fib_id"], x["alert_ts"]) for x in live}]
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for label, items in runs.items():
                pick = [t for t in items if t["market"] == market and t["tf"] in tfs]
                if pick:
                    rows.append({"market": market, "tf": group, **row(label, pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib L3 + L4 alerts with lakky's repeat rule ({args.since} to now)", "",
            "Live fib rules, net after fees. R and % per trade and in total. Crypto on Delta candles. "
            "Entries filled within 15 min of US CPI/PPI/FOMC left out. L4 trades enter at the strong box's far "
            "edge with the same stop as L3 (25% of the box beyond it).", "", df.to_markdown(index=False), ""]
    (OUT / "FIB_L3_L4.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
