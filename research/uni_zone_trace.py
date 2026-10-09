"""Research only: why the UNI 30m alerts of 2026-10-08 (demand 7.51-7.57008) do not
rebuild from today's Bitunix candles.

The live scan read 1500 candles (its own log, run 9536), so the window length is
not it. This checks the candles themselves: gaps, the candle that made the zone,
and whether Bitunix serves the same candles when the same range is paged from a
different end. Prints only.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ["VICTUS_TIMEFRAME"] = "30m"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd                     # noqa: E402

import bitunix_data                     # noqa: E402
import config                           # noqa: E402
import scanner                          # noqa: E402
from live_audit import delta_rows       # noqa: E402

PAIR, CONTRACT = "UNIUSDT", "UNIUSD"
STEP = 1800
ALERTS = [datetime(2026, 10, 8, 12, 47, 10, tzinfo=timezone.utc), datetime(2026, 10, 8, 13, 41, 50, tzinfo=timezone.utc)]
BOTTOM, TOP = 7.51, 7.57008


def ts(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M")


def zones(window):
    frame = pd.DataFrame([[c[0] * 1000, *c[1:6]] for c in window],
                         columns=["time", "open", "high", "low", "close", "volume"])
    supply, demand = scanner.build_zones(frame)
    return frame, demand


def main():
    for sent in ALERTS:
        sent = int(sent.timestamp())
        opened = sent // STEP * STEP
        start = opened - (config.OHLCV_LIMIT + 80) * STEP
        print(f"\n=== alert {ts(sent)} (candle {ts(opened)}) ===")
        # 1. The scan's own request: paged back from just after the alert.
        a = bitunix_data.klines(PAIR, "30m", start, opened)
        # 2. The same range paged back from now (different page boundaries).
        b = [r for r in bitunix_data.klines(PAIR, "30m", start, int(datetime.now(timezone.utc).timestamp())) if r[0] < opened]
        am, bm = {r[0]: r for r in a}, {r[0]: r for r in b}
        print(f"paged from alert: {len(a)} closed; paged from now: {len(b)} in range")
        diff = [t for t in sorted(set(am) | set(bm)) if am.get(t, [None])[1:5] != bm.get(t, [None])[1:5]]
        print(f"candles that differ between the two pagings: {len(diff)}")
        for t in diff[:10]:
            print("   ", ts(t), am.get(t), bm.get(t))
        slots = set(range(a[0][0], opened, STEP))
        gaps = sorted(slots - set(am))
        print(f"missing 30m slots in the alert-time paging: {len(gaps)}" + (f" first {[ts(g) for g in gaps[:8]]}" if gaps else ""))

        # 3. Candles that could have made the zone.
        hits = [r for r in a if abs(r[3] - BOTTOM) / BOTTOM < 5e-4 or any(abs(x - TOP) / TOP < 2e-4 for x in r[1:5])]
        print("candles touching 7.51 low or 7.57008:")
        for r in hits:
            print("   ", ts(r[0]), r[1:6])

        # 4. Zones built on the scan's window, closed only and with the forming candle.
        closed = a[-(config.OHLCV_LIMIT - 1):]
        ones = bitunix_data.klines(PAIR, "1m", opened, sent - 60)
        forming = [opened, ones[0][1], max(m[2] for m in ones), min(m[3] for m in ones), ones[-1][4], sum(m[5] for m in ones)] if ones else None
        for label, window in (("closed + forming", closed + ([forming] if forming else [])), ("closed only", closed)):
            frame, demand = zones(window)
            near = [z for z in demand if 7.3 < z["bottom"] < 7.8]
            print(f"{label}: {len(window)} candles, demand zones 7.3-7.8:")
            for z in near:
                print(f"     {z['bottom']:.6g}-{z['top']:.6g} active={z['active']} created {ts(int(frame['time'].iloc[z['created_idx']]) // 1000)}")

        # 5. Delta's candles over the same window, for comparison.
        d = [r for r in delta_rows(CONTRACT, "30m", start, opened - 1) if r[0] < opened][-(config.OHLCV_LIMIT - 1):]
        frame, demand = zones(d)
        print(f"Delta closed window {len(d)} candles, demand zones 7.3-7.8:")
        for z in demand:
            if 7.3 < z["bottom"] < 7.8:
                print(f"     {z['bottom']:.6g}-{z['top']:.6g} active={z['active']} created {ts(int(frame['time'].iloc[z['created_idx']]) // 1000)}")


if __name__ == "__main__":
    main()
