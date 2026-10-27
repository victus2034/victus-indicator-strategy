"""Research (lakky, 2026-10-27, ENA 4H): each fib level its own stop, not one stop for L1-L4.

  shared   live until now: every level on L3's stop (25% of the strong box past L4).
  own      just past the level itself (25% of a box) - his "too tight" stop (~0.2% on ENA 4H).
  next     a level's stop just past the NEXT deeper level (L1 -> past L2, L2 -> past L3,
           L3 -> past L4 = today's stop, L4 -> one box past L4). His pick in the note.

Live levels (config.FIB_ALERT_LEVELS), each alerts once, 2R + breakeven, net after fees.
Sep 1 to now; trades filled within 15 min of a US CPI / PPI / FOMC release left out.

    PYTHONPATH=research python research/fib_level_sl_backtest.py --since 2026-09-01
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
import fib_trendline_trades as trades  # noqa: E402
from fib_entry_touched_backtest import replay_all  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402
from trail_fib_tl_backtest import news  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_level_sl"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")), ("1D", ("1d",)), ("1W", ("1w",)), ("1M", ("1M",)))
RULES = ("shared", "own", "next")


def median_risk(items):
    risks = sorted(trades.risk_pct(t["plan"]) for t in items)
    return round(risks[len(risks) // 2], 2) if risks else None


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
    for rule in RULES:
        fbt.FIB_SL_RULE = rule
        runs[rule] = [t for t in replay_all(now) if t["alert_ts"] >= since and not news(t["result"].get("fill_ts"))]
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for level in ("all", "L1", "L2", "L3", "L4"):
                for rule in RULES:
                    pick = [t for t in runs[rule] if t["market"] == market and t["tf"] in tfs
                            and (level == "all" or t.get("level") == level)]
                    if pick:
                        rows.append({"market": market, "tf": group, "level": level,
                                     **row(rule, pick), "median_stop_%": median_risk(pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib stop per level ({args.since} to now)", "",
            "shared = all levels on L3's stop (old live), own = just past the level, next = just past the "
            "next deeper level. Live levels, once each, 2R + BE, net after fees, R and % per trade. "
            "Crypto on Delta candles. Entries filled within 15 min of US CPI/PPI/FOMC left out.", "",
            df.to_markdown(index=False), ""]
    (OUT / "FIB_LEVEL_SL.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
