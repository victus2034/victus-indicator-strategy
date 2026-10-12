"""Research only: the live rule of 2026-10-12 (lakky, BNB 1M) against the old one.

No fib alert once the candle still forming (of the alert's own timeframe) has
reached the zone's entry - price inside the zone, or through the entry and back,
in the same candle (fib_trendline_scanner.entry_already_touched; the replay's
SKIP_TOUCHED_ENTRY). Sep 1 to now, live fib rules otherwise.

    PYTHONPATH=research python research/fib_entry_touched_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import scanner  # noqa: E402
from fib_touched_before_backtest import GROUPS, row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_entry_touched"


def replay_all(now):
    got = []
    for symbol in scanner.active_watchlist():
        try:
            data = fbt.crypto_data(symbol, now)
            got += fbt.replay_symbol(CRYPTO, symbol, *data, now) if data else []
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
    import nse_scanner
    for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
        got += fbt.replay_symbol(NSE, symbol, base, evals, now)
    return [t for t in got if t["kind"] == "fib"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    runs = {}
    for label, flag in (("old: alert inside the zone too", False), ("new: entry not yet reached this candle", True)):
        fbt.SKIP_TOUCHED_ENTRY = flag
        runs[label] = [t for t in replay_all(now) if t["alert_ts"] >= since]
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for label, items in runs.items():
                pick = [t for t in items if t["market"] == market and t["tf"] in tfs]
                if pick:
                    rows.append({"market": market, "tf": group, **row(label, pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib alerts: no alert once this candle reached the entry ({args.since} to now)", "",
            "Live fib rules (deeper zone, S/R stop, 2R + BE), net after fees. R and % per trade and in total "
            "(% = R x the trade's stop distance). Crypto replayed on Delta candles.", "",
            df.to_markdown(index=False), ""]
    (OUT / "FIB_ENTRY_TOUCHED.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
