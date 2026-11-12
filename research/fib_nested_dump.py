"""Research only: save Bitunix 1D candles (full history, as the live fib scan loads them) for the coins
lakky drew fibs on, so research/fib_engine_nested.py can be checked on his chart's venue.

    python research/fib_nested_dump.py    (part fib-nested-dump of bitunix_research.yml)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fib_trendline_data as data  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_nested" / "candles"
SYMBOLS = ("BTCUSD", "ETHUSD", "SOLUSD", "UNIUSD", "NEARUSD", "ADAUSD", "HYPEUSD", "FILUSD", "ONDOUSD",
           "1000PEPEUSD", "DOGEUSD", "XRPUSD", "ZECUSD", "BNBUSD", "SUIUSD", "ENAUSD", "WLDUSD", "LINKUSD")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for symbol in SYMBOLS:
        try:
            charts = data.crypto_charts(symbol, ["1d"], now, source="bitunix")
            rows = [list(c[:5]) for c in charts["1d"]]
        except Exception as error:  # noqa: BLE001
            print(symbol, "failed:", error)
            continue
        (OUT / f"{symbol}_1d.json").write_text(json.dumps(rows))
        print(symbol, len(rows), "candles, last", rows[-1])


if __name__ == "__main__":
    main()
