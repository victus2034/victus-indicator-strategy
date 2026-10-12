"""Research only: does the live fib move when the chart's start date moves?

Until 2026-10-12 crypto_charts() loaded "the last 2000 days", a start that
slides one day per day. With Bitunix history reaching further back than that,
the first (partial) month changes daily and the fib engine - a state machine
run from the first candle - can end on a different base. BNB 1M alerted at
719.15 on Oct 8 and at 838.05 on Oct 12.

For each Bitunix symbol this fetches 4H/1D/1W from HISTORY_START once, then
replays the live fib's key and Zone 2 entry with the chart starting at
"now - 2000 days" for every day Oct 1-12, and at HISTORY_START. Same end data
everywhere, so any change is the start alone. Also hand-traces BNB 1M.
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bitunix_data                     # noqa: E402
import fib_engine                       # noqa: E402
import fib_trendline_scanner as fts     # noqa: E402
import scanner                          # noqa: E402
from config import FIB_SWING_LENGTH     # noqa: E402
from fib_trendline_data import (        # noqa: E402
    CRYPTO, HISTORY_START, bitunix_candles, candle_is_closed, monthly_from_daily,
)


def day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def live_fib(candles, tf, now):
    closed = candles if candles and candle_is_closed(CRYPTO, candles[-1][0], tf, now) else candles[:-1]
    if len(closed) < fts.MIN_BARS:
        return None
    times = [c[0] for c in closed]
    stamp = [day(t) for t in times]
    snaps, _ = fib_engine.run(stamp, [c[2] for c in closed], [c[3] for c in closed], N=FIB_SWING_LENGTH)
    live = snaps[-1]
    d, base, top = live["d"], live["O"], live["E"]
    zone2 = [z for z in fts.fib_zones(d, base, top) if z["zone"] == 2][0]
    return dict(key=f"{d}|{day(times[live['Ot']])}|{top:g}", base=base, top=top, entry=zone2["entry"], sl=zone2["sl"])


def main():
    now = time.time()
    oct_days = [datetime(2026, 10, d, 4, tzinfo=timezone.utc).timestamp() for d in range(1, 13)]
    sliding = [t - 2000 * 86400 for t in oct_days]
    symbols = [s for s in scanner.active_watchlist() if bitunix_data.uses_bitunix(s)]
    flips = {tf: 0 for tf in ("4h", "1d", "1w", "1M")}
    differs = {tf: 0 for tf in flips}
    checked = 0
    print(f"HISTORY_START {day(HISTORY_START)}; sliding starts {day(sliding[0])} .. {day(sliding[-1])}\n")
    for symbol in symbols:
        contract = scanner.delta_contract(symbol)
        pair = bitunix_data.pair_for(symbol, contract)
        t0 = time.time()
        try:
            charts = {tf: bitunix_candles(pair, tf, HISTORY_START, now) for tf in ("4h", "1d", "1w")}
        except Exception as error:     # noqa: BLE001
            print(f"{symbol}: fetch failed {error}")
            continue
        took = time.time() - t0
        checked += 1
        first = {tf: day(c[0][0]) if c else "-" for tf, c in charts.items()}
        print(f"{symbol} ({pair}) first candle 4h {first['4h']} 1d {first['1d']} 1w {first['1w']} "
              f"| {len(charts['4h'])} 4h bars, fetch {took:.0f}s")
        for tf in flips:
            def chart(since):
                if tf == "1M":
                    return monthly_from_daily([c for c in charts["1d"] if c[0] >= since])
                return [c for c in charts[tf] if c[0] >= since]
            keys = []
            for since in sliding:
                f = live_fib(chart(since), tf, now)
                keys.append(f["key"] if f else None)
            full = live_fib(chart(HISTORY_START), tf, now)
            distinct = sorted(set(k for k in keys if k))
            if len(distinct) > 1:
                flips[tf] += 1
            if full and keys[-1] != full["key"]:
                differs[tf] += 1
            if len(distinct) > 1 or (full and keys[-1] != full["key"]):
                print(f"   {tf}: sliding start gave {distinct}; fixed start {full['key'] if full else None}")
    print(f"\n{checked} symbols. Fib changed with the sliding start alone (Oct 1-12): "
          + ", ".join(f"{tf} {n}" for tf, n in flips.items()))
    print("Oct 12 sliding start != fixed start: " + ", ".join(f"{tf} {n}" for tf, n in differs.items()))

    # ---- BNB 1M hand trace
    print("\n=== BNB 1M hand trace ===")
    daily = bitunix_candles("BNBUSDT", "1d", HISTORY_START, now)
    print(f"first daily candle {day(daily[0][0])}")
    for label, t in (("Oct 8 run", datetime(2026, 10, 8, 16, 58, tzinfo=timezone.utc).timestamp()),
                     ("Oct 12 run", datetime(2026, 10, 12, 3, 43, tzinfo=timezone.utc).timestamp())):
        since = t - 2000 * 86400
        months = monthly_from_daily([c for c in daily if since <= c[0] < t])
        f = live_fib(months, "1M", t)
        print(f"{label}: start {day(since)}, first month {day(months[0][0])} "
              f"H {months[0][2]:g} L {months[0][3]:g}; fib {f['key']} base {f['base']:g} "
              f"entry {f['entry']:.2f} sl {f['sl']:.2f}")
    months = monthly_from_daily([c for c in daily if c[0] < datetime(2026, 10, 12, 3, 43, tzinfo=timezone.utc).timestamp()])
    f = live_fib(months, "1M", now)
    print(f"fixed start: fib {f['key']} base {f['base']:g} entry {f['entry']:.2f} sl {f['sl']:.2f}")
    print("BNB daily Oct 1-12 (low / high):")
    for c in daily:
        if c[0] >= datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp():
            print(f"   {day(c[0])} L {c[3]:g} H {c[2]:g} C {c[4]:g}")


if __name__ == "__main__":
    main()
