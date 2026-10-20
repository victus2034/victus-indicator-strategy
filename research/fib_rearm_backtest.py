"""Research only (lakky, 2026-10-20, BTW 4H: "yes do it"): a fib zone that already alerted
alerts again after price left its band by REARM_FACTOR and came back (BTW L3 sent 16 Oct,
price ran to 2.1 and fell back to L4 on 20 Oct with no alert). Live: one alert per zone.

Sep 1 to now, live fib rules otherwise (deeper zone, S/R stop, 2R + BE), net after fees.
Trades filled within 15 min of a US CPI / PPI / FOMC release are left out.

    PYTHONPATH=research python research/fib_rearm_backtest.py --since 2026-09-01
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

OUT = Path(__file__).resolve().parent / "out" / "fib_rearm"
GROUPS = (("4H", ("4h",)), ("1D", ("1d",)), ("1W", ("1w",)), ("1M", ("1M",)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    runs = {}
    for label, flag in (("live: one alert per zone", False), ("re-arm: again after price left and came back", True)):
        fbt.FIB_REARM = flag
        runs[label] = [t for t in replay_all(now) if t["alert_ts"] >= since
                       and not news(t["result"].get("fill_ts"))]
    first = {(t["symbol"], t["tf"], t["fib_id"], t["alert_ts"]) for t in runs["live: one alert per zone"]}
    again = [t for t in runs["re-arm: again after price left and came back"]
             if (t["symbol"], t["tf"], t["fib_id"], t["alert_ts"]) not in first]
    runs["extra alerts only"] = again
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for label, items in runs.items():
                pick = [t for t in items if t["market"] == market and t["tf"] in tfs]
                if pick:
                    rows.append({"market": market, "tf": group, **row(label, pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame([{k: t[k] for k in ("market", "symbol", "tf", "fib_id", "alert_ts")} for t in again]).to_csv(
        OUT / "extra_alerts.csv", index=False)
    text = [f"# Fib re-arm after price leaves and returns ({args.since} to now)", "",
            "Live fib rules, net after fees. R and % per trade and in total. Crypto on Delta candles. "
            "Entries filled within 15 min of US CPI/PPI/FOMC left out. 'extra alerts only' = the second+ alerts "
            "of a zone (overlapping trades on one fib are all counted).", "", df.to_markdown(index=False), ""]
    (OUT / "FIB_REARM.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
