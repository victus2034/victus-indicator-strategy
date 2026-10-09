"""Research only: what Bitunix's kline endpoint does at a page boundary.

The UNI trace (research/out/live_audit/UNI_TRACE.txt) found that paging the same
range from two different ends gives different candles: one candle missing at
each page boundary, and the candle after it carrying another candle's open.
This asks small pages with endTime around one candle open and prints exactly
which candles come back, so bitunix_data.klines can page correctly.
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bitunix_data                     # noqa: E402

STEP_MS = 1800 * 1000


def ts(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%m-%d %H:%M")


def show(label, rows):
    rows = sorted(rows, key=lambda r: int(r["time"]))
    print(f"{label}: " + " | ".join(f"{ts(int(r['time']))} o{r['open']} c{r['close']}" for r in rows))


def main():
    for pair in ("UNIUSDT", "BTCUSDT"):
        now = int(time.time() * 1000)
        t = (now // STEP_MS - 300) * STEP_MS          # a closed candle well back
        print(f"\n=== {pair} 30m, T = {ts(t)} ===")
        # Reference: a page ending far after T, so T sits in its middle.
        ref = bitunix_data._request(pair, "30m", t - 10 * STEP_MS, t + 10 * STEP_MS, 21)
        show("reference (T in the middle)", [r for r in ref if t - 3 * STEP_MS <= int(r["time"]) <= t + 2 * STEP_MS])
        for name, end in (("T-1ms", t - 1), ("T", t), ("T+1ms", t + 1), ("T+step-1ms", t + STEP_MS - 1),
                          ("T+step", t + STEP_MS), ("T+step+1ms", t + STEP_MS + 1)):
            rows = bitunix_data._request(pair, "30m", t - 10 * STEP_MS, end, 3)
            show(f"endTime {name:>11} limit 3", rows)
        # Does the oldest row of a page carry a wrong open?
        for limit in (3, 5, 8):
            rows = bitunix_data._request(pair, "30m", 0, t + STEP_MS, limit)
            show(f"limit {limit} ending at T+step", rows)


if __name__ == "__main__":
    main()
