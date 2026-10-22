"""Research only (lakky, 2026-10-21): pause fib L1 / L2 alerts after a 4H trendline break - 1h, 4h, 1 day.

  live      the live rules: 4H fibs at L2-L4, 1D/1W/1M at L1-L4, each level once.
  pause     after a 4H TL BROKEN on the same symbol, that side's L1/L2 send nothing for PAUSE_SECONDS
            from the break candle's close (a broken support pauses BUY, a broken resistance SELL), on every
            fib timeframe. A level still in its band after the pause alerts then.
  skip      the same, but a level that would have alerted inside the pause is dropped for good.
Each is run with a 1h, 4h and 1 day pause (lakky: "try a longer pause").

The band inside a coarse candle (1D crypto on 4h, 1W/1M on 1d) is read off 1h candles, so the hour is an hour.
Sep 1 to now, net after fees; trades filled within 15 min of a US CPI / PPI / FOMC release left out.

    PYTHONPATH=research python research/fib_tl_break_pause_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import bisect
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import scanner  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE, candle_close_ts, candle_is_closed  # noqa: E402
from trail_fib_tl_backtest import news  # noqa: E402
from trendlines import SUPPORT, build_trendlines  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_tl_break_pause"
PAUSES = (("1h", 3600), ("4h", 4 * 3600), ("1d", 86400))
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")), ("1D", ("1d",)), ("1W", ("1w",)), ("1M", ("1M",)))
MODE = {"name": "live", "seconds": 3600}
CTX = {}            # (market, symbol) -> {"windows": [(start, end, d)], "fine": [1h candles]}
COUNT = {"paused": 0, "skipped": 0}


def break_windows(market, base4h, now):
    """[(start, end, d)] - the hour after each 4H TL BROKEN alert; d is the fib side it pauses (1 BUY, -1 SELL)."""
    if base4h and not candle_is_closed(market, base4h[-1][0], "4h", now):
        base4h = base4h[:-1]
    if len(base4h) < 50:
        return []
    times = [c[0] for c in base4h]
    highs, lows, closes = [c[2] for c in base4h], [c[3] for c in base4h], [c[4] for c in base4h]
    out = []
    for line in build_trendlines(highs, lows, closes, config.TRENDLINE_SWING_LENGTH, config.TRENDLINES_KEEP,
                                 history=True):
        if line.broken_at is None or line.broken_at < line.created:
            continue                       # never alerted: broken before it was drawn
        start = candle_close_ts(market, times[line.broken_at], "4h")
        out.append((start, 1 if line.kind == SUPPORT else -1))
    return out


def pause(market, symbol, d, leg, ts, end, lo, hi):
    if MODE["name"] == "live" or leg not in ("L1", "L2"):
        return "ok", None
    ctx = CTX.get((market, symbol), {})
    span = MODE["seconds"]
    wins = [(a, a + span) for a, side in ctx.get("windows", ()) if side == d and a < end and a + span > ts]
    if not wins:
        return "ok", None
    paused = lambda t: any(a <= t < b for a, b in wins)  # noqa: E731
    fine = ctx.get("fine", [])
    stamps = [c[0] for c in fine]
    found_paused = False
    for c in fine[bisect.bisect_left(stamps, ts):bisect.bisect_left(stamps, end)]:
        if c[3] > hi or c[2] < lo:
            continue                       # this hour never in the band
        if not paused(c[0]):
            return "ok", (c[0] if found_paused else None)
        found_paused = True
        if MODE["name"] == "skip":
            COUNT["skipped"] += 1
            return "skip", None
    if not fine and paused(ts):            # no 1h candles: judge the candle by its open
        found_paused = True
    if not found_paused:
        return "ok", None
    if MODE["name"] == "skip":
        COUNT["skipped"] += 1
        return "skip", None
    COUNT["paused"] += 1
    return "paused", None


def replay_all(now):
    got, breaks = [], {}
    jobs = []
    for symbol in scanner.active_watchlist():
        try:
            data = fbt.crypto_data(symbol, now)
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            continue
        if data:
            jobs.append((CRYPTO, symbol, *data))
    import nse_scanner
    for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
        jobs.append((NSE, symbol, base, evals))
    for market, symbol, base, evals in jobs:
        windows = break_windows(market, base.get("4h", []), now)
        breaks[(market, symbol)] = len(windows)
        CTX[(market, symbol)] = {"windows": windows, "fine": evals.get("1h", [])}
        got += [t for t in fbt.replay_symbol(market, symbol, base, evals, now) if t["kind"] == "fib"]
    return got, breaks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    fbt.FIB_LEVELS = dict(config.FIB_ALERT_LEVELS)
    fbt.FIB_PAUSE = pause
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    runs, counts = {}, {}
    modes = [("live", "live", 0)] + [(f"{kind} {name}", kind, sec) for name, sec in PAUSES for kind in ("pause", "skip")]
    for label, kind, seconds in modes:
        MODE.update(name=kind, seconds=seconds)
        COUNT.update(paused=0, skipped=0)
        items, breaks = replay_all(now)
        runs[label] = [t for t in items if t["alert_ts"] >= since and not news(t["result"].get("fill_ts"))]
        counts[label] = dict(COUNT)
    n_breaks = {m: sum(v for (mk, _), v in breaks.items() if mk == m) for m in (CRYPTO, NSE)}
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for scope, levels in (("all levels", None), ("L1+L2", ("L1", "L2"))):
                for label, items in runs.items():
                    pick = [t for t in items if t["market"] == market and t["tf"] in tfs
                            and (levels is None or t.get("level") in levels)]
                    if pick:
                        rows.append({"market": market, "tf": group, "levels": scope, **row(label, pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib L1/L2 paused after a 4H trendline break (1h / 4h / 1 day) ({args.since} to now)", "",
            "live = today's rules. pause = after a 4H TL BROKEN, same-side L1/L2 wait 1h / 4h / 1 day, then alert if "
            "still in band. skip = dropped instead. Net after fees, 2R + BE, crypto on Delta candles. "
            "Entries filled within 15 min of US CPI/PPI/FOMC left out.", "",
            f"4H breaks in the data (all history): crypto {n_breaks[CRYPTO]}, NSE {n_breaks[NSE]}. "
            "Candle checks paused / levels dropped (all history): " + ", ".join(
                f"{k} {v['paused'] or v['skipped']}" for k, v in counts.items() if k != "live") + ".",
            "", df.to_markdown(index=False), ""]
    (OUT / "FIB_TL_BREAK_PAUSE.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
