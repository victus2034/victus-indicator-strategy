"""Research only: the fib rule of 2026-10-12 (no alert once the forming candle reached
the entry) tried on trendline touches (lakky, 2026-10-12).

A trendline touch alerts only while the candle forming on the alert's timeframe has
not yet traded to the line (fib_trendline_backtest.TL_SKIP_TOUCHED_ENTRY). Live TL
rules otherwise: lakky's candle stop, one 1R target, no breakeven, no hold limit.
Sep 1 to now, split 4H vs 1D+ and crypto vs NSE.

    PYTHONPATH=research python research/tl_entry_touched_backtest.py --since 2026-09-01
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
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "tl_entry_touched"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")))


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
    return [t for t in got if t["kind"] == "trendline"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    runs = {}
    for label, flag in (("live: alert even after this candle hit the line", False),
                        ("new: line not yet reached this candle", True)):
        fbt.TL_SKIP_TOUCHED_ENTRY = flag
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
    text = [f"# Trendline alerts: no alert once this candle reached the line ({args.since} to now)", "",
            "Live TL rules (lakky candle stop, TP 1R, no BE, no hold limit), net after fees. R and % per trade "
            "and in total (% = R x the trade's stop distance). Crypto replayed on Delta candles.", "",
            df.to_markdown(index=False), ""]
    (OUT / "TL_ENTRY_TOUCHED.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
