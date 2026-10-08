"""Research only - nothing here is imported by the live scanners.

lakky (2026-10-08): "L2 is more accurate than L1 and more powerful in return".
Strong zone (the deeper fib box) levels: L1 = near edge (today's entry - upper
on a buy, lower on a sell), L2 = far edge. Both use the live stop (S/R rule:
FIB_SL_HEIGHT_PCT of the box's height beyond the far edge), so L2's risk is a
quarter of the box and L1's a box and a quarter.

    python research/fib_level_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402
from fib_trendline_scanner import fib_zones  # noqa: E402
from fib_zone_preference import row  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_level"


def levels(d, base, top):
    strong = next(z for z in fib_zones(d, base, top) if z["zone"] == 2)
    far = strong["low"] if d == 1 else strong["high"]
    return [{**strong, "zone": "L1"},
            {**strong, "zone": "L2", "low": far, "high": far, "entry": far}]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    fbt.fib_zones = levels
    fbt.ALERT_ZONES = ("L1", "L2")
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    got = []

    def one(symbol):
        try:
            data = fbt.crypto_data(symbol, now)
            return fbt.replay_symbol(CRYPTO, symbol, *data, now) if data else []
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            return []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(one, scanner.active_watchlist()):
            got += result
    import nse_scanner
    for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
        got += fbt.replay_symbol(NSE, symbol, base, evals, now)

    fibs = [t for t in got if t["kind"] == "fib" and t["alert_ts"] >= since]
    print(f"{len(fibs)} fib level alerts since {args.since}")
    rows = []
    for market in (CRYPTO, NSE):
        mk = [t for t in fibs if t["market"] == market]
        for label, keep in (("L1 only (live)", {"L1"}), ("L2 only", {"L2"}), ("L1 + L2", {"L1", "L2"})):
            items = [t for t in mk if t["zone"] in keep]
            if items:
                rows.append({"market": market, "tf": "all", **row(label, items)})
        for tf in fbt.TIMEFRAMES:
            for level in ("L1", "L2"):
                items = [t for t in mk if t["tf"] == tf and t["zone"] == level]
                if items:
                    rows.append({"market": market, "tf": tf, **row(level, items)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib strong zone L1 vs L2: {args.since} to now", "",
            "L1 = strong zone near edge (live entry), L2 = far edge. Stop for both = "
            f"{config.FIB_SL_HEIGHT_PCT:g}% of box height beyond the far edge (live). Live trade rules "
            "(2R target, BE at +0.5R), net R after fees. Crypto replayed on Delta candles.", "",
            df.to_markdown(index=False), ""]
    (OUT / "FIB_LEVEL.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
