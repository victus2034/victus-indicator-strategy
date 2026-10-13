"""Research only: DOGE 1D fib on lakky's chart (2026-10-13) vs the bot.

Saves the Bitunix daily candles so the fib engine can be replayed offline, and
prints the engine's event log and the live fib.

    python research/doge_fib_trace.py [PAIR ...]   # default DOGEUSDT; MAGIC 4H round: MAGICUSDT
"""
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bitunix_data                       # noqa: E402
import fib_engine                         # noqa: E402
from fib_trendline_data import HISTORY_START  # noqa: E402
from fib_trendline_scanner import FIB_SWING_LENGTH  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "doge_fib"
PAIRS = sys.argv[1:] or ["DOGEUSDT"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    for pair, tf in ((p, tf) for p in PAIRS for tf in ("1d", "4h")):
        start = HISTORY_START if tf == "1d" or pair != "DOGEUSDT" else now - 400 * 86400
        rows = bitunix_data.klines(pair, tf, start, now)
        with open(OUT / f"{pair}_{tf}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t", "o", "h", "l", "c"])
            w.writerows(r[:5] for r in rows)
        stamp = [datetime.fromtimestamp(r[0] / 1000 if r[0] > 1e11 else r[0], timezone.utc).strftime("%Y-%m-%d %H:%M")
                 for r in rows]
        snaps, log = fib_engine.run(stamp, [r[2] for r in rows], [r[3] for r in rows], N=FIB_SWING_LENGTH)
        live = snaps[-1]
        print(f"== {pair} {tf}: {len(rows)} candles {stamp[0]} -> {stamp[-1]}")
        print("live:", {k: live[k] for k in ("d", "O", "E", "P")}, "O at", stamp[live["Ot"]], "E at", stamp[live["Et"]])
        print("levels:", [round(x, 5) for x in fib_engine.levels(live["O"], live["E"])])
        for t, msg in log[-40:]:
            print(" ", t, msg)


if __name__ == "__main__":
    main()
