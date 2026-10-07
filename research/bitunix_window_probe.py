"""How many candles does the live zone scan get from Bitunix, and which?

chart_vs_bot (2026-10-07) showed scanner.fetch_bitunix_ohlcv returning 199
candles on 4h and 1d, not OHLCV_LIMIT (1500), with the forming candle missing,
while fib_trendline_data's full-history fetch got everything. The two differ
only in endTime: the scanner asks up to one candle in the future.

Research only - prints, sends nothing.

    python research/bitunix_window_probe.py
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bitunix_data  # noqa: E402

STEP = {"30m": 1800, "4h": 14400, "1d": 86400}


def ts(ms):
    return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")


def main():
    now = int(time.time())
    print(f"now {ts(now * 1000)} UTC")
    for tf, step in STEP.items():
        print(f"\n== BTCUSDT {tf} ==")
        start = (now - 1570 * step) * 1000
        for label, end in (("end=now", now), ("end=now+1s", now + 1), ("end=now+tf/2", now + step // 2),
                           ("end=now+tf", now + step), ("end=now+3tf", now + 3 * step)):
            rows = bitunix_data._request("BTCUSDT", tf, start, end * 1000 - 1, 200)
            times = sorted(int(r["time"]) for r in rows)
            print(f"  one page {label:13s}: {len(rows):3d} rows {ts(times[0])} -> {ts(times[-1])}")
        for label, end in (("now+1", now + 1), ("now+tf (live scanner)", now + step)):
            got = bitunix_data.klines("BTCUSDT", tf, now - 1570 * step, end)
            print(f"  klines end={label:22s}: {len(got):4d} candles {ts(got[0][0] * 1000)} -> {ts(got[-1][0] * 1000)}")


if __name__ == "__main__":
    main()
