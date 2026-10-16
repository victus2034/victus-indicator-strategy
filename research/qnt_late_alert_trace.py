"""Research only: QNT 1D fib L3 BUY (entry 200.436) alerted at 21:20 IST on
2026-10-16 with price 201.2; lakky's 5m chart shows price near it from ~20:40.
Replays the live scanner's 1D fib check every 5 minutes that evening on
Bitunix candles as they stood then, and prints the 5m candles."""
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bitunix_data                                   # noqa: E402
import fib_trendline_scanner as fts                   # noqa: E402
from fib_trendline_data import HISTORY_START          # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
PAIR = "QNTUSDT"
START = int(datetime(2026, 10, 16, 13, 0, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 10, 16, 16, 40, tzinfo=timezone.utc).timestamp())


def ist(t):
    return datetime.fromtimestamp(t, IST).strftime("%H:%M")


def main():
    daily = [r[:5] for r in bitunix_data.klines(PAIR, "1d", HISTORY_START, END)]
    h4 = [r[:5] for r in bitunix_data.klines(PAIR, "4h", HISTORY_START, END)]
    m1 = [r[:5] for r in bitunix_data.klines(PAIR, "1m", START - 6 * 3600, END)]
    m5 = [r[:5] for r in bitunix_data.klines(PAIR, "5m", START, END)]
    print("5m candles (IST open, o h l c):")
    for c in m5:
        print(f"  {ist(c[0])}  {c[1]:.2f} {c[2]:.2f} {c[3]:.2f} {c[4]:.2f}")
    day_open = int(datetime(2026, 10, 16, tzinfo=timezone.utc).timestamp())
    print("today's low before each step (1m):")
    print("time  price   dist%  inband touched fib_alert  low_so_far")
    for t in range(START, END, 300):
        closed_1m = [c for c in m1 if c[0] + 60 <= t]
        price = closed_1m[-1][4]
        # As the live pass saw them: Bitunix serves closed candles only.
        charts = {"1d": [c for c in daily if c[0] + 86400 <= t],
                  "4h": [c for c in h4 if c[0] + 14400 <= t]}
        forming = fts.current_candle_range(fts.CRYPTO, charts, "1d", t)
        res = fts.analyse(fts.CRYPTO, "QNTUSD", "1d", charts["1d"], t, price, forming)
        low_today = min(c[3] for c in m1 if day_open <= c[0] < t)
        entry = 200.436
        dist = (price - entry) / entry * 100
        touched = fts.entry_already_touched(1, {"entry": entry}, price, forming)
        print(f"{ist(t)}  {price:.2f}  {dist:5.2f}  {fts.in_band(dist)!s:5} {touched!s:5} "
              f"{[round(z['entry'], 3) for z in res['fib']]}  {low_today:.2f}  forming={forming}")


if __name__ == "__main__":
    main()
