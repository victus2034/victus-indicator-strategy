"""Which trendlines did the bot hold for a crypto symbol on one day, and when did price reach each?

lakky, 2026-11-15 (XRP 1D): "why it did not take that 2nd trendline trade". For each timeframe this
rebuilds the lines from Bitunix candles closed before the day (trendlines.build_trendlines, the live
rule), prints every line live that day with its price on it, then walks the day's 15m candles: when
price first came inside the alert band, when it first traded at the line, the day's low / high so far
at the band moment (the "forming candle already reached the line" rule) and the day's close.
Research only, reads candles, posts nothing.

    python research/tl_touch_trace.py XRPUSD --day 2026-11-14 --tfs 1d 1w
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from fib_trendline_data import HISTORY_START, TF_SECONDS, bitunix_candles  # noqa: E402
from trendlines import SUPPORT, build_trendlines  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


def ist(ts):
    return datetime.fromtimestamp(ts, IST).strftime("%d %b %H:%M")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("symbol")
    p.add_argument("--day", required=True)
    p.add_argument("--tfs", nargs="+", default=["1d"])
    a = p.parse_args()
    day = int(datetime.strptime(a.day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    fine = bitunix_candles(a.symbol, "15m", day - 86400, day + 2 * 86400)
    today = [c for c in fine if day <= c[0] < day + 86400]
    print(f"# {a.symbol} {a.day} (UTC day = 05:30 IST to 05:30 IST)")
    print(f"day open {today[0][1]}, high {max(c[2] for c in today)}, low {min(c[3] for c in today)}, close {today[-1][4]}")
    for tf in a.tfs:
        sec = TF_SECONDS[tf]
        rows = [c for c in bitunix_candles(a.symbol, tf, HISTORY_START, day + 86400) if c[0] + sec <= day]   # closed before the day
        highs, lows, closes = [c[2] for c in rows], [c[3] for c in rows], [c[4] for c in rows]
        bar = len(rows)                              # the candle forming on `day`
        band = config.alert_band_pct(tf, config.FIB_TL_MAX_DISTANCE_PCT)
        print(f"\n## {tf}: {len(rows)} closed candles, last opens {ist(rows[-1][0])}, band {band}%")
        for mode, lines in (("chart now (newest %d)" % config.TRENDLINES_KEEP,
                             build_trendlines(highs, lows, closes, config.TRENDLINE_SWING_LENGTH, config.TRENDLINES_KEEP)),
                            ("every line ever drawn, live that day", [
                                ln for ln in build_trendlines(highs, lows, closes, config.TRENDLINE_SWING_LENGTH,
                                                              config.TRENDLINES_KEEP, history=True) if ln.live_during(bar)])):
            print(f"\n### {mode}")
            for ln in lines:
                if not ln.alive and mode.startswith("chart"):
                    continue
                kind = "support" if ln.kind == SUPPORT else "resistance"
                level = ln.price_at(bar)
                line = (f"{kind} {ist(rows[ln.x1][0])} {ln.y1} -> {ist(rows[ln.x2][0])} {ln.y2} | drawn {ist(rows[ln.created][0]) if ln.created < len(rows) else 'not yet'}"
                        f" | broken_at {ln.broken_at} trimmed_at {ln.trimmed_at} | price on the day {level:.5f}")
                lo = hi = None
                first_band = first_touch = None
                for c in today:
                    lo = c[3] if lo is None else min(lo, c[3])
                    hi = c[2] if hi is None else max(hi, c[2])
                    near = c[3] if ln.kind == SUPPORT else c[2]
                    dist = (near - level) / level * 100 * (1 if ln.kind == SUPPORT else -1)
                    if first_band is None and dist <= band:
                        first_band = (c[0], dist, lo, hi)
                    if first_touch is None and dist <= 0:
                        first_touch = c[0]
                print(line)
                print(f"    band first reached: {ist(first_band[0]) + f' IST ({first_band[1]:+.2f}% from line in that 15m candle)' if first_band else 'never'}"
                      f" | line first traded: {ist(first_touch) + ' IST' if first_touch else 'never'}"
                      f" | day close vs line: {(today[-1][4] - level) / level * 100:+.2f}%")


if __name__ == "__main__":
    main()
