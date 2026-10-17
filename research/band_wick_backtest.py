"""Research only: alert a fib/trendline on a wick into the band, not only on the price
at the moment of a check (lakky, 2026-10-16, QNT 1D).

Live checks the price at one moment every ~5 minutes, so a quick wick into the 0.75%
band between two checks is missed (QNT 1D: the 20:50 IST wick to 201.38 alerted only
at 21:20). Two replays of the live rules, band judged on 5m candles:
  live: a 5m CLOSE inside the band (what a check every ~5 minutes sees)
  new:  a 5m candle's RANGE reaching the band (any wick between checks)
Everything else is the live replay (fib_trendline_backtest). Sep 1 to now, split
fib vs TL, 4H vs 1D+, crypto vs NSE; R and % per trade.

    PYTHONPATH=research python research/band_wick_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import bisect
import statistics
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import scanner  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE, delta_candles, nse_download  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "band_wick"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")))
FINE = {}           # (market, symbol) -> 5m candles
MODE = {"wick": False}
SINCE = [0.0]


def probe(market, symbol, start, end, lo, hi):
    if start < SINCE[0] - 86400:
        return start                    # before the test window: the eval candle decides, as live replay
    rows = FINE.get((market, symbol)) or []
    times = [r[0] for r in rows]
    for r in rows[bisect.bisect_left(times, start):bisect.bisect_left(times, end)]:
        _t, _o, h, l, c = r[:5]
        if (l <= hi and h >= lo) if MODE["wick"] else (lo <= c <= hi):
            return r[0]
    return None


def load_fine(now, since):
    for symbol in scanner.active_watchlist():
        contract = scanner.delta_contract(symbol)
        if contract:
            try:
                FINE[(CRYPTO, symbol)] = fbt._cached(f"c_{contract}_5m_band",
                                                     lambda: delta_candles(contract, "5m", since - 2 * 86400, now))
            except Exception as error:  # noqa: BLE001
                print(f"crypto {symbol} 5m failed: {error}")
    import nse_scanner
    for symbol, rows in fbt._cached("n_5m_band", lambda: nse_download(nse_scanner.load_watchlist(), "5m",
                                                                       period="60d")).items():
        FINE[(NSE, symbol)] = rows


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
    return got


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    SINCE[0] = since
    now = time.time()
    load_fine(now, since)
    print(f"5m charts: {sum(1 for v in FINE.values() if v)}")
    fbt.BAND_PROBE = probe
    runs = {}
    for label, wick in (("live: 5m close in band (a check every ~5 min)", False),
                        ("new: any wick into band", True)):
        MODE["wick"] = wick
        runs[label] = [t for t in replay_all(now) if t["alert_ts"] >= since]
    rows = []
    for market in (CRYPTO, NSE):
        for kind in ("fib", "trendline"):
            for group, tfs in GROUPS:
                for label, items in runs.items():
                    pick = [t for t in items if t["market"] == market and t["kind"] == kind and t["tf"] in tfs]
                    if pick:
                        rows.append({"market": market, "kind": kind, "tf": group, **row(label, pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    live, new = runs.values()
    key = lambda t: (t["market"], t["symbol"], t["tf"], t["kind"], t["plan"]["entry"])  # noqa: E731
    live_at = {key(t): t["band_ts"] for t in live if t.get("band_ts")}
    earlier = [(live_at[key(t)] - t["band_ts"]) / 60 for t in new
               if t.get("band_ts") and key(t) in live_at and live_at[key(t)] >= t["band_ts"]]
    live_keys = {key(x) for x in live}
    only_new = sum(1 for t in new if key(t) not in live_keys)
    text = [f"# Fib/TL alerts on a wick into the band vs a 5-minute check ({args.since} to now)", "",
            "Live rules otherwise (fib 2R + BE, TL lakky stop + 1R), net after fees. Band judged on 5m candles. "
            "R and % per trade and in total. Crypto replayed on Delta candles.", "",
            df.to_markdown(index=False), "",
            f"- Alerts only the wick rule sends: {only_new}",
            f"- Same alert, sent earlier by the wick rule: {sum(1 for m in earlier if m > 0)} of {len(earlier)}"
            + (f", median {statistics.median([m for m in earlier if m > 0] or [0]):.0f} min earlier" if earlier else ""),
            ""]
    (OUT / "BAND_WICK.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
