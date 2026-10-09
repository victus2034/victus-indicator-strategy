"""Bar-by-bar list of the fib / trendline alerts the bot's rules give on one
crypto chart, next to what the Pine chart markers (v12.7.3) give on the same
candles, so the two can be diffed. Research only - sends nothing.

Lakky, 2026-10-09 (LINK 1D): "signal differs with the alert ... make it strict
and only follow the rules we decided".

Each bar is judged the way the chart sees it: by its high and low. The bot's
side mirrors fib_trendline_scanner.analyse / plan_alerts (deeper zone only,
S/R stop, 0.75% approach band, once per fib + zone; trendline band on the
approach side, again only after price leaves the band; BROKEN on a close
through). The Pine side transcribes the v12.7.3 marker code.

    python research/chart_marker_replay.py LINKUSD --tf 1d --since 2026-07-01
"""
import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fib_engine  # noqa: E402
import scanner  # noqa: E402
from config import (  # noqa: E402
    FIB_ALERT_ZONES, FIB_TL_MAX_DISTANCE_PCT, TRENDLINE_SWING_LENGTH, TRENDLINES_KEEP,
)
from fib_trendline_data import CRYPTO, candle_is_closed, crypto_charts  # noqa: E402
from fib_trendline_scanner import FIB_SWING_LENGTH, fib_zones  # noqa: E402
from trendlines import SUPPORT, build_trendlines  # noqa: E402

BAND = FIB_TL_MAX_DISTANCE_PCT / 100


def day(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M")


def bot_markers(c, stamp):
    """[(bar, kind, text)] under the bot's rules."""
    n = len(c)
    highs = [x[2] for x in c]
    lows = [x[3] for x in c]
    closes = [x[4] for x in c]
    out = []
    snaps, _ = fib_engine.run(stamp, highs, lows, N=FIB_SWING_LENGTH)
    fired = set()
    for i in range(1, n):
        s = snaps[i - 1]
        d, base, top = s["d"], s["O"], s["E"]
        if base == top:
            continue
        for z in fib_zones(d, base, top):
            if z["zone"] not in FIB_ALERT_ZONES:
                continue
            key = (d, s["Ot"], top, z["zone"])
            if key in fired:
                continue
            # fib_distance: 0..BAND above (long) / below (short) the zone, 0 inside, None past it;
            # analyse: only while price is inside the fib (base < price < top)
            if d == 1:
                lo, hi = max(z["low"], base), min(z["high"] * (1 + BAND), top)
            else:
                lo, hi = max(z["low"] * (1 - BAND), top), min(z["high"], base)
            if hi > lo and lows[i] < hi and highs[i] > lo:
                fired.add(key)
                out.append((i, "FIB BUY" if d == 1 else "FIB SELL",
                            f"zone {z['low']:.4f}-{z['high']:.4f} entry {z['entry']:.4f} sl {z['sl']:.4f} base {base} top {top}"))
    for ln in build_trendlines(highs, lows, closes, TRENDLINE_SWING_LENGTH, TRENDLINES_KEEP, history=True):
        last = min(x for x in (ln.broken_at, ln.trimmed_at, n - 1) if x is not None)
        in_band, sent = False, None
        for i in range(ln.created + 1, last + 1):
            if ln.trimmed_at is not None and i > ln.trimmed_at:
                break
            level = ln.price_at(i)
            if level <= 0:
                continue
            lo, hi = (level, level * (1 + BAND)) if ln.kind == SUPPORT else (level * (1 - BAND), level)
            if lows[i] > hi or highs[i] < lo:
                in_band = False
            else:
                if not in_band and (sent is None or i > sent):
                    out.append((i, "TL BUY" if ln.kind == SUPPORT else "TL SELL",
                                f"line {ln.y1:.4f}@{stamp[ln.x1]} -> {ln.y2:.4f}@{stamp[ln.x2]} level {level:.4f}"))
                    sent = i
                in_band = True
        if ln.broken_at is not None and (ln.trimmed_at is None or ln.broken_at <= ln.trimmed_at):
            out.append((ln.broken_at, "TL BRK " + ("SUP" if ln.kind == SUPPORT else "RES"),
                        f"line {ln.y1:.4f}@{stamp[ln.x1]} -> {ln.y2:.4f}@{stamp[ln.x2]}"))
    return sorted(out)


def pine_markers(c, stamp):
    """[(bar, kind, text)] as Pine v12.7.3 marks them."""
    n = len(c)
    opens = [x[1] for x in c]
    highs = [x[2] for x in c]
    lows = [x[3] for x in c]
    closes = [x[4] for x in c]
    out = []
    snaps, _ = fib_engine.run(stamp, highs, lows, N=FIB_SWING_LENGTH)
    key_now, done = None, {1: False, 2: False}
    for i in range(1, n):
        s = snaps[i - 1]
        d, o, e = s["d"], s["O"], s["E"]
        if o == e:
            continue
        key = (d, s["Ot"], e)
        if key != key_now:
            key_now, done = key, {1: False, 2: False}
        flo, fr = min(o, e), abs(e - o)
        fw = 0.11 * fr
        for k in (2,):                      # 'Deeper zone only' default
            upper = (d == 1) == (k == 1)
            zl = flo + 0.55 * fr if upper else flo + 0.34 * fr
            zh = zl + fw
            sl = zl + 0.55 * fw if d == 1 else zh - 0.55 * fw
            lower = max(sl, o) if d == 1 else max(zl * (1 - BAND), e)
            upp = min(zh * (1 + BAND), e) if d == 1 else min(sl, o)
            hit = upp > lower and lows[i] <= upp and highs[i] >= lower and (highs[i] > lower if d == 1 else lows[i] < upp)
            if hit and not done[k]:
                done[k] = True
                out.append((i, "FIB BUY" if d == 1 else "FIB SELL", f"zone {zl:.4f}-{zh:.4f}"))
    for ln in build_trendlines(highs, lows, closes, TRENDLINE_SWING_LENGTH, TRENDLINES_KEEP, history=True):
        last = min(x for x in (ln.broken_at, ln.trimmed_at, n - 1) if x is not None)
        was, sent = False, -1
        for i in range(ln.created + 1, last + 1):
            if ln.trimmed_at is not None and i > ln.trimmed_at:
                break
            level = ln.price_at(i)
            if level <= 0:
                continue
            sup = ln.kind == SUPPORT
            edge = level * (1 + BAND) if sup else level * (1 - BAND)
            hit = (lows[i] <= edge and highs[i] >= level) if sup else (highs[i] >= edge and lows[i] <= level)
            if hit and not was and i > sent:
                out.append((i, "TL BUY" if sup else "TL SELL", f"level {level:.4f}"))
                sent = i
            was = hit and ((level <= closes[i] <= edge) if sup else (edge <= closes[i] <= level))
        if ln.broken_at is not None and (ln.trimmed_at is None or ln.broken_at <= ln.trimmed_at):
            out.append((ln.broken_at, "TL BRK " + ("SUP" if ln.kind == SUPPORT else "RES"), ""))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol")
    ap.add_argument("--tf", default="1d")
    ap.add_argument("--since", default="2026-07-01")
    a = ap.parse_args()
    now = int(time.time())
    contract = scanner.delta_contract(a.symbol)
    c = crypto_charts(contract, [a.tf], now, source="bitunix")[a.tf]
    c = [[int(x[0] / 1000 if x[0] > 1e11 else x[0]), *map(float, x[1:5])] for x in c]
    stamp = [day(x[0]) for x in c]
    out = Path(__file__).resolve().parent / "out" / "chart_markers"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{a.symbol}_{a.tf}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close"])
        w.writerows(c)
    forming = not candle_is_closed(CRYPTO, c[-1][0], a.tf, now)
    print(f"== {a.symbol} {a.tf} bitunix: {len(c)} candles {stamp[0]} -> {stamp[-1]}{' (last forming)' if forming else ''}")
    since = datetime.strptime(a.since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    bot = [m for m in bot_markers(c, stamp) if c[m[0]][0] >= since]
    pine = [m for m in pine_markers(c, stamp) if c[m[0]][0] >= since]
    print("\n-- BOT RULES --")
    for i, k, t in bot:
        print(f"{stamp[i]}  {k:12s} {t}")
    print("\n-- PINE v12.7.3 --")
    for i, k, t in pine:
        print(f"{stamp[i]}  {k:12s} {t}")
    bs = {(i, k) for i, k, _ in bot}
    ps = {(i, k) for i, k, _ in pine}
    print("\n-- ONLY ON CHART (Pine) --")
    for i, k in sorted(ps - bs):
        print(f"{stamp[i]}  {k}")
    print("\n-- ONLY IN BOT RULES --")
    for i, k in sorted(bs - ps):
        print(f"{stamp[i]}  {k}")


if __name__ == "__main__":
    main()
