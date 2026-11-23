"""Live fib / TL alert passes replayed on real Bitunix 1m candles: old rule vs the first-reach rule.

lakky, 2026-11-23: "Make sure no trade now misses as well as alerts". SUI (14 / 21 Nov) and BTC (21 Nov) 1D
lines were wicked through between two scanner passes and never alerted: the candle had reached the line, so
line_already_touched kept them silent. fib_trendline_scanner.first_reach now alerts a level first reached
since the last pass once. This walks passes every --step minutes (swept = 1m since the previous pass,
forming = the day's 1m range so far) through analyse + plan_alerts and prints every 1D crypto fib / TL touch
alert each rule sends. Research only.

    PYTHONPATH=research python research/first_reach_replay.py --start 2026-11-13 --days 10 --step 10
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bitunix_data  # noqa: E402
import config  # noqa: E402
import fib_trendline_scanner as fts  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, HISTORY_START, bitunix_candles  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
DAY = 86400


def ist(ts):
    return datetime.fromtimestamp(ts, IST).strftime("%d %b %H:%M")


def run(symbol, start, end, step):
    pair = bitunix_data.pair_for(symbol, scanner.delta_contract(symbol))
    daily = bitunix_candles(pair, "1d", HISTORY_START, end)
    fine = bitunix_candles(pair, "1m", start - DAY, end)
    out = {"old": [], "new": []}
    for rule in out:
        state, prev = {}, start - step
        i0 = 0
        for now in range(start, end, step):
            if now % DAY < step:
                print(f"  {symbol} {rule} {ist(now)}", flush=True)
            day = now - now % DAY
            closed = [c for c in daily if c[0] + DAY <= now][-500:]    # speed: lines converge; both rules see the same
            while i0 < len(fine) and fine[i0][0] < day:
                i0 += 1
            today = [c for c in fine[i0:] if c[0] + 60 <= now]
            if not today or len(closed) < 50:
                prev = now
                continue
            swept_rows = [c for c in today if c[0] >= prev]
            swept = (min(c[3] for c in swept_rows), max(c[2] for c in swept_rows)) if swept_rows else None
            forming = (min(c[3] for c in today), max(c[2] for c in today))
            price = today[-1][4]
            a = fts.analyse(CRYPTO, symbol, "1d", closed, now, price=price, forming=forming, swept=swept)
            if rule == "old":           # the rule before 23 Nov: nothing touched or through the line is listed
                a["touch"] = [t for t in a["touch"] if not t.get("touched")]
                a["fib"] = [z for z in a["fib"] if not z.get("touched")]
            for channel, key, text, _ in fts.plan_alerts(state, CRYPTO, symbol, "1d", a, now):
                fts.mark_sent(state, key, now)
                out[rule].append((now, channel, key, text.splitlines()[1]))
            prev = now
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-11-13")
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--step", type=int, default=10, help="minutes between passes")
    ap.add_argument("symbols", nargs="*")
    a = ap.parse_args()
    start = int(datetime.strptime(a.start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    end = min(start + a.days * DAY, int(datetime.now(timezone.utc).timestamp()) - 120)
    totals = {"old": 0, "new": 0}
    for symbol in a.symbols or config.CRYPTO_WATCHLIST:
        try:
            got = run(symbol, start, end, a.step * 60)
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} failed: {error!r}")
            continue
        old = {k for _, _, k, _ in got["old"]}
        for rule in ("old", "new"):
            totals[rule] += len(got[rule])
        for now, channel, key, line in got["new"]:
            tag = "" if key in old else "  <- NEW"
            print(f"{symbol} {ist(now)} {channel} {key.split('|')[0]} {line}{tag}")
        for now, channel, key, line in got["old"]:
            if key not in {k for _, _, k, _ in got["new"]}:
                print(f"{symbol} {ist(now)} {channel} only in OLD {line}")
    print(f"\n1D crypto fib + TL touch alerts, passes every {a.step} min: old rule {totals['old']}, new rule {totals['new']}")


if __name__ == "__main__":
    main()
