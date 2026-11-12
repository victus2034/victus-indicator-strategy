"""Research (lakky, 2026-11-10): no L1 alert when the fib's extreme candle, or the one after it, already reached L1.

  live    today's rule (L1-L4 alert as they are).
  l1void  L1 sends nothing when the extreme (top/bottom) candle or the next candle traded to L1's entry; L2-L4 unchanged.

Sep 1 to now, live levels, each once, 2R + breakeven, net after fees; trades filled within 15 min of US CPI/PPI/FOMC left out.

    PYTHONPATH=research python research/fib_l1_void_backtest.py --since 2026-09-01
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

OUT = Path(__file__).resolve().parent / "out" / "fib_l1_void"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")), ("1D", ("1d",)), ("1W", ("1w",)), ("1M", ("1M",)))
RULES = {"live": (), "l1void": ("L1",)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    fbt.FIB_LEVELS = dict(config.FIB_ALERT_LEVELS)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    runs = {}
    for name, void in RULES.items():
        fbt.FIB_VOID_LEVELS = void
        runs[name] = [t for t in replay_all(now) if t["alert_ts"] >= since and not news(t["result"].get("fill_ts"))]
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for level in ("all", "L1", "L2", "L3", "L4"):
                for name in RULES:
                    pick = [t for t in runs[name] if t["market"] == market and t["tf"] in tfs
                            and (level == "all" or t.get("level") == level)]
                    if pick:
                        rows.append({"market": market, "tf": group, "level": level, **row(name, pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# No L1 alert when the extreme candle or the next reached it ({args.since} to now)", "",
            "Live levels, each once, 2R + BE, net after fees, R and % per trade. Crypto on Delta candles. "
            "Entries filled within 15 min of US CPI/PPI/FOMC left out.", "", df.to_markdown(index=False), ""]
    (OUT / "FIB_L1_VOID.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
