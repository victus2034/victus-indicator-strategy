"""Research (lakky, 2026-11-03, METAUSDT 4H): fib level SL = the nearest candle WICK past the level
(SELL: a high above it, BUY: a low below it), short of the next level; none -> just past the level.
His chart: L2 619.19 -> 620.83, L3 622.18 -> 622.78, L4 625.47 -> 626.56.

  next       live on 4H: just past the NEXT deeper level (L2 -> 623.00 on META).
  wick 0     nearest wick past the level, any distance.
  wick 0.05  ... at least 0.05% past it.
  wick 0.1   ... at least 0.1% past it.

4H only (1D / 1W / 1M stay on the live rule). Live levels, each alerts once, 2R + breakeven, net
after fees. Sep 1 to now; trades filled within 15 min of a US CPI / PPI / FOMC release left out.

    PYTHONPATH=research python research/fib_wick_sl_backtest.py --since 2026-09-01
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
import fib_trendline_scanner as fts  # noqa: E402
from fib_entry_touched_backtest import replay_all  # noqa: E402
from fib_level_sl_backtest import median_risk  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, NSE, IST  # noqa: E402
from trail_fib_tl_backtest import news  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_wick_sl"
RULES = (("next", "next", 0.0), ("wick 0", "wick", 0.0), ("wick 0.05", "wick", 0.05), ("wick 0.1", "wick", 0.1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = [tf for tf in config.FIB_TL_TIMEFRAMES if tf == "4h"]
    fbt.FIB_LEVELS = dict(config.FIB_ALERT_LEVELS)
    fbt.FIB_SL_RULE = None
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    runs = {}
    for name, rule, gap in RULES:
        fts.FIB_LEVEL_SL_RULE_BY_TF = dict(config.FIB_LEVEL_SL_RULE_BY_TF, **{"4h": rule})
        fts.FIB_SL_WICK_GAP_PCT = gap
        runs[name] = [t for t in replay_all(now) if t["alert_ts"] >= since and not news(t["result"].get("fill_ts"))]
    rows = []
    for market in (CRYPTO, NSE):
        for level in ("all", "L2", "L3", "L4"):
            for name, _, _ in RULES:
                pick = [t for t in runs[name] if t["market"] == market and t["tf"] == "4h"
                        and (level == "all" or t.get("level") == level)]
                if pick:
                    rows.append({"market": market, "tf": "4H", "level": level,
                                 **row(name, pick), "median_stop_%": median_risk(pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib 4H stop: next level vs nearest wick ({args.since} to now)", "",
            "Live 4H levels (L2-L4), once each, 2R + BE, net after fees, R and % per trade. Crypto on Delta "
            "candles. Entries filled within 15 min of US CPI/PPI/FOMC left out.", "",
            df.to_markdown(index=False), ""]
    (OUT / "FIB_WICK_SL.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
