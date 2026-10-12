"""Research only: BNB 1M fib vs where its daily history starts, and how often
a full-history Bitunix fetch comes back short (the live 1M fib depends on it)."""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bitunix_data                                  # noqa: E402
from fib_history_start_probe import day, live_fib    # noqa: E402
from fib_trendline_data import HISTORY_START, monthly_from_daily  # noqa: E402


def main():
    now = time.time()
    firsts = []
    for attempt in range(12):
        rows = bitunix_data.klines("BNBUSDT", "1d", HISTORY_START, int(now))
        firsts.append(day(rows[0][0]))
    print("12 full fetches, first candle:", firsts)
    daily = [r[:5] for r in rows]
    for start in ("2022-04-17", "2022-05-01", "2022-05-26", "2022-06-01", "2022-07-01", "2023-01-01",
                  "2023-12-01", "2024-01-01", "2024-06-01", "2024-09-01"):
        t = datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp()
        f = live_fib(monthly_from_daily([c for c in daily if c[0] >= t]), "1M", now)
        print(f"start {start}: fib {f['key']} base {f['base']:g} entry {f['entry']:.2f} sl {f['sl']:.2f}")


if __name__ == "__main__":
    main()
