"""Research only: does Bitunix return the same daily history on every call?

The fib probe saw BNB 1d start 2022-04-17 in one fetch and 2022-05-26 in the
next, minutes apart. The 1M fib runs from the first candle, so a different
depth is a different fib (BNB 1M: Jun 2022 base on Oct 8, Aug 2024 on Oct 12).
This repeats the same full-history fetch and prints every page.
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bitunix_data                     # noqa: E402


def day(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")


def pages(pair, interval):
    step = 86400 * 1000
    cursor = int(time.time()) // 86400 * step
    out = []
    while cursor > 0:
        rows = bitunix_data._request(pair, interval, 0, cursor, 200)
        times = sorted(int(r["time"]) for r in rows)
        out.append((day(cursor), len(rows), day(times[0]) if times else "-", day(times[-1]) if times else "-"))
        if len(rows) < 200:
            break
        cursor = times[0]
    return out


def main():
    for pair in ("BNBUSDT", "BTCUSDT", "LINKUSDT"):
        for attempt in range(4):
            got = pages(pair, "1d")
            print(f"{pair} try {attempt + 1}: " + " | ".join(f"end {e} n{n} {a}..{b}" for e, n, a, b in got))
            # what the live code sees
            rows = bitunix_data.klines(pair, "1d", 1483228800, int(time.time()))
            print(f"   klines: {len(rows)} candles from {day(rows[0][0] * 1000)}")
            time.sleep(2)
        # does a page further back than the short one still have data?
        rows = bitunix_data._request(pair, "1d", 0, int(datetime(2022, 6, 1, tzinfo=timezone.utc).timestamp()) * 1000, 200)
        times = sorted(int(r["time"]) for r in rows)
        print(f"   page ending 2022-06-01: n{len(rows)} {day(times[0]) if times else '-'}..{day(times[-1]) if times else '-'}")


if __name__ == "__main__":
    main()
