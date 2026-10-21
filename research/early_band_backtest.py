"""Research only (lakky, 2026-10-21): 1W / 1M alerts from 3% away instead of 0.75% (fib, TL) / 0.20% (zones).

lakky: "for 1w and 1m alerts i want to give alert space of 3% which help me to get ready for big
timeframe trades because when alert came it already touched". Crypto and NSE.

  live   fib/TL band 0.75%, S/R zone band 0.20% (MAX_DISTANCE_PCT), every timeframe.
  3%     the same rules with a 3% band on 1W and 1M (config.alert_band_pct).

Entry, stop and target do not change, so a trade is the same trade - the band only decides when
lakky hears of it, and whether the "this candle already reached the entry" rule silences it first.
Fibs at the live levels (FIB_ALERT_LEVELS), each once; TL lakky's stop + 1R; zones 2R + BE.
Sep 1 to now, net after fees; entries filled within 15 min of US CPI / PPI / FOMC left out.

    PYTHONPATH=research python research/early_band_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
import zone_htf_backtest as zhb  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402
from trail_fib_tl_backtest import news  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "early_band"
TFS = ["1w", "1M"]
MODES = (("live (0.75% / zones 0.20%)", False), ("3% on 1W/1M", True))


def fib_tl(now):
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
    return [t for t in got if t["kind"] in ("fib", "trendline")]


def zones(now, since):
    got = []
    scanner.ZONE_BASE_EXTRA = 1
    for symbol in config.WATCHLIST:
        try:
            data = zhb.crypto_load(symbol, now, since)
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} zones failed: {error}")
            continue
        if not data:
            continue
        base, evals, daily = data
        for tf in TFS:
            got += zhb.replay(CRYPTO, symbol, tf, base[tf], evals[trades.EVAL_RESOLUTION[CRYPTO][tf]], daily, since, now)
    import nse_scanner
    for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
        for tf in TFS:
            got += zhb.replay(NSE, symbol, tf, base.get(tf, []), evals.get(trades.EVAL_RESOLUTION[NSE][tf], []),
                              None, since, now)
    return got


def lead_days(items):
    days = [(t["result"]["fill_ts"] - t["alert_ts"]) / 86400 for t in items if t["result"].get("fill_ts")]
    return round(statistics.median(days), 1) if days else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = TFS
    fbt.FIB_LEVELS = config.FIB_ALERT_LEVELS      # the live levels, each alerts once
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    runs = {}
    for label, early in MODES:
        fbt.EARLY_BAND = early
        zhb.EARLY_BAND[0] = early
        got = fib_tl(now) + zones(int(now), int(since))
        runs[label] = [t for t in got if t["alert_ts"] >= since and not news(t["result"].get("fill_ts"))]
    early = runs[MODES[1][0]]
    rows = []
    for market in (CRYPTO, NSE):
        for kind in ("fib", "trendline", "zone"):
            for tf in TFS:
                for label, items in runs.items():
                    pick = [t for t in items if t["market"] == market and t["kind"] == kind and t["tf"] == tf]
                    if not pick:
                        continue
                    rows.append({"market": market, "kind": kind, "tf": tf, **row(label, pick),
                                 "days_alert_to_fill": lead_days(pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame([{**{k: t[k] for k in ("market", "symbol", "tf", "kind", "alert_ts")}, "level": t.get("level"),
                   **t["plan"], "outcome": t["result"]["outcome"], "fill_ts": t["result"].get("fill_ts")}
                  for t in early]).to_csv(OUT / "trades_3pct.csv", index=False)
    text = [f"# 1W / 1M alerts from 3% away ({args.since} to now)", "",
            "Same entry, stop and target; only the alert band changes on 1W and 1M. Fibs at the live levels "
            "(once each, 2R + BE), TL lakky stop + 1R, zones 2R + BE; net after fees. R and % per trade. "
            "Crypto fib/TL on Delta candles, zones on Bitunix; NSE on Yahoo. Entries filled within 15 min of "
            "US CPI/PPI/FOMC left out. days_alert_to_fill = median days from the alert "
            "to the entry filling (daily candles).", "",
            df.to_markdown(index=False), ""]
    (OUT / "EARLY_BAND.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
