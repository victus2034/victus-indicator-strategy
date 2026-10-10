"""Research only - nothing here is imported by the live scanners.

Lakky, 2026-10-10 (HUSDT 1D, AVAXUSDT 1D, Bitunix): how he places the stop and
targets on a trendline trade by hand, so the alert could carry that stop.

  HUSDT: entry on the line; SL just below the PREVIOUS TOUCH of the line (the
         last candle whose low reached it). TP1 1.5R, then "go with the flow":
         exit below the previous daily candle.
  AVAX:  the previous touch is too far (bad risk to reward), so the SL goes
         just below the CLOSEST candle low under entry. TP1 1.5R, then the top
         of the recent big day candle.

Stops tested (support = buy; resistance mirrors it):
  live     TRENDLINE_SL_PCT beyond the line (1D 1.5%) - today's alert
  touch    TOUCH_BUFFER_PCT beyond the low of the last candle that touched the line
  nearest  beyond the closest swing low under entry (2 bars each side, last 20 closed candles)
  hybrid   touch, but nearest when touch risk is more than HYBRID_MAX_ATR x ATR(14)
           (Lakky's AVAX rule; "too far" is not stated, so 1 ATR is the default here)
Exits tested:
  2R+BE    live: BE at +0.5R, 1R and 2R targets, booked held for 2R
  1.5R     everything off at 1.5R
  1.5R+trail  half off at 1.5R, the rest trails below the previous candle of the
              alert's timeframe (Lakky's HUSDT rule)
  1.5R+high   half off at 1.5R, the rest at the highest high of the last 10
              candles before the alert, or trailed if that is under 1.5R (AVAX rule)

Alerts are the live trendline alerts (v12.6, length 10, 0.75% band, approach side,
re-arm rules), replayed bar by bar like fib_trendline_backtest.replay. Crypto on
Bitunix candles (XAUT/SLVON Delta), NSE on Yahoo; Delta fees. Same-candle stop
and target = stop. Timeouts close at market (live booking drops them).

    python research/trendline_sl_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import bisect
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE, TF_SECONDS, candle_is_closed, monthly_from_daily  # noqa: E402
from trendlines import SUPPORT, build_trendlines  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "trendline_sl"
TOUCH_BUFFER_PCT = 0.1
HYBRID_MAX_ATR = 1.0
NEAR_LOOKBACK, PIVOT_SIDE = 20, 2
TP1_R = 1.5
TRAIL_MAX_BARS = 60
STOPS = ("live", "touch", "nearest", "hybrid")
EXITS = ("2R+BE", "1.5R", "1.5R+trail", "1.5R+high")
BAND = config.FIB_TL_MAX_DISTANCE_PCT / 100


def atr14(highs, lows, closes):
    out, prev = [None] * len(closes), None
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        prev = tr if prev is None else (prev * 13 + tr) / 14
        out[i] = prev if i >= 14 else None
    return out


def stop_prices(line, i, entry, highs, lows, atr, tf):
    """Every stop for an alert on bar i (bars up to i-1 closed)."""
    long = line.kind == SUPPORT
    buf = TOUCH_BUFFER_PCT / 100
    out = {"live": trades.trendline_plan(long, entry, tf)["sl"]}
    touch = None
    for j in range(i - 1, line.x2 - 1, -1):
        level = line.price_at(j)
        if (lows[j] <= level * (1 + BAND)) if long else (highs[j] >= level * (1 - BAND)):
            touch = lows[j] * (1 - buf) if long else highs[j] * (1 + buf)
            break
    if touch is not None and ((touch < entry) if long else (touch > entry)):
        out["touch"] = touch
    near = None
    for j in range(i - 1 - PIVOT_SIDE, max(i - 1 - NEAR_LOOKBACK, PIVOT_SIDE) - 1, -1):
        side = range(j - PIVOT_SIDE, j + PIVOT_SIDE + 1)
        if long and lows[j] < entry and all(lows[j] <= lows[k] for k in side):
            cand = lows[j] * (1 - buf)
            near = cand if near is None else max(near, cand)
        if not long and highs[j] > entry and all(highs[j] >= highs[k] for k in side):
            cand = highs[j] * (1 + buf)
            near = cand if near is None else min(near, cand)
    out["nearest"] = near if near is not None else out.get("touch", out["live"])
    out.setdefault("touch", out["nearest"])
    a = atr[i - 1]
    far = a is not None and abs(entry - out["touch"]) > HYBRID_MAX_ATR * a
    out["hybrid"] = out["nearest"] if far else out["touch"]
    return out


def simulate(long, entry, sl, exit_rule, market, tf, evalc, k, base_times, base_lows, base_highs, recent_high):
    """One trade on evaluation candles after index k. Returns net R or None (no fill)."""
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    sign = 1 if long else -1
    per_bar = trades.EVAL_PER_BAR[market][tf]
    wait_n = config.FIB_TL_ENTRY_WAIT_BARS * per_bar
    hold_n = (TRAIL_MAX_BARS if "+" in exit_rule and exit_rule != "2R+BE" else config.FIB_TL_MAX_HOLD_BARS) * per_bar
    cost_r = trades.COST_PCT[market] / (risk / entry * 100)
    plan = {"side": "long" if long else "short", "entry": entry, "sl": sl}
    be_stop = trades.break_even_stop(plan, market)
    half_px = entry + sign * 0.5 * risk
    be_ok = (half_px >= be_stop) if long else (half_px <= be_stop)
    tp1 = entry + sign * TP1_R * risk
    tp2 = entry + sign * 2 * risk
    r_of = lambda px: sign * (px - entry) / risk  # noqa: E731
    slip = lambda px: trades.slipped(px, plan)    # noqa: E731
    high_tp = None
    if exit_rule == "1.5R+high" and recent_high is not None and sign * (recent_high - tp1) > 0:
        high_tp = recent_high
    filled, seen, fill_at, stop, half, banked, moved = False, 0, 0, sl, False, 0.0, False
    last_close = None
    for ts, _o, h, l, c in evalc[k + 1:]:
        seen += 1
        last_close = c
        if not filled:
            if seen > wait_n:
                return None
            if (l <= entry) if long else (h >= entry):
                filled, fill_at = True, seen
                if (l <= sl) if long else (h >= sl):
                    return r_of(slip(sl)) - cost_r
            continue
        if seen - fill_at > hold_n:
            return (banked + (0.5 if half else 1.0) * r_of(c)) - cost_r
        if exit_rule == "2R+BE":
            cur = be_stop if moved else sl
            if (l <= cur) if long else (h >= cur):
                return r_of(slip(cur)) - cost_r
            if ((h >= half_px) if long else (l <= half_px)) and be_ok:
                moved = True
            if (h >= tp2) if long else (l <= tp2):
                return 2.0 - cost_r
            continue
        if half and exit_rule in ("1.5R+trail", "1.5R+high"):
            # trail below the last closed candle of the alert timeframe, never loosened
            b = bisect.bisect_right(base_times, ts) - 2
            if b >= 0:
                trail = base_lows[b] if long else base_highs[b]
                stop = max(stop, trail) if long else min(stop, trail)
        if (l <= stop) if long else (h >= stop):
            return banked + (0.5 if half else 1.0) * r_of(slip(stop)) - cost_r
        if not half and ((h >= tp1) if long else (l <= tp1)):
            if exit_rule == "1.5R":
                return TP1_R - cost_r
            half, banked = True, 0.5 * TP1_R
            continue
        if half and high_tp is not None and ((h >= high_tp) if long else (l <= high_tp)):
            return banked + 0.5 * r_of(high_tp) - cost_r
    if not filled:
        return None
    return banked + (0.5 if half else 1.0) * r_of(last_close) - cost_r   # still open: mark to market


def replay(market, symbol, tf, base, evalc, now, since):
    if base and not candle_is_closed(market, base[-1][0], tf, now):
        base = base[:-1]
    n = len(base)
    if n <= fbt.MIN_BARS or not evalc:
        return []
    times = [c[0] for c in base]
    highs = [c[2] for c in base]
    lows = [c[3] for c in base]
    closes = [c[4] for c in base]
    atr = atr14(highs, lows, closes)
    eval_ts = [c[0] for c in evalc]
    eval_seconds = TF_SECONDS[trades.EVAL_RESOLUTION[market][tf]]
    held = (lambda ts: fbt.crypto_held(ts, eval_seconds)) if market == CRYPTO else (lambda ts: False)

    def bar_slice(i):
        end = times[i + 1] if i + 1 < n else times[i] + TF_SECONDS[tf]
        return bisect.bisect_left(eval_ts, times[i]), bisect.bisect_left(eval_ts, end)

    first = next((i for i in range(fbt.MIN_BARS, n) if times[i] >= eval_ts[0]), n)
    out = []
    lines = build_trendlines(highs, lows, closes, config.TRENDLINE_SWING_LENGTH, config.TRENDLINES_KEEP, history=True)
    for line in lines:
        last = min(x for x in (line.broken_at, line.trimmed_at, n - 1) if x is not None)
        in_band, last_alert = False, None
        for i in range(max(line.created + 1, first), last + 1):
            level = line.price_at(i)
            if level <= 0:
                continue
            lo_band, hi_band = (level, level * (1 + BAND)) if line.kind == SUPPORT else (level * (1 - BAND), level)
            e0, e1 = bar_slice(i)
            for k in range(e0, e1):
                ts, _o, h, l, _c = evalc[k]
                if held(ts):
                    continue
                if l > hi_band or h < lo_band:
                    in_band = False
                    continue
                if not in_band and (last_alert is None or ts - last_alert >= TF_SECONDS[tf]):
                    last_alert = ts
                    if ts >= since:
                        long = line.kind == SUPPORT
                        stops = stop_prices(line, i, level, highs, lows, atr, tf)
                        window = range(max(0, i - 10), i)
                        recent = max(highs[j] for j in window) if long else min(lows[j] for j in window)
                        t = {"market": market, "symbol": symbol, "tf": tf, "alert_ts": ts, "entry": level,
                             "long": long, "stops": stops}
                        for s in STOPS:
                            t[f"risk_{s}"] = abs(level - stops[s]) / level * 100
                            for e in EXITS:
                                t[f"{s}|{e}"] = simulate(long, level, stops[s], e, market, tf, evalc, k,
                                                         times, lows, highs, recent)
                        out.append(t)
                in_band = True
    return out


def crypto_load(symbol, now):
    from bitunix_compare import candles
    source = "delta" if symbol in ("XAUTUSD", "SLVONUSD") or scanner.delta_contract(symbol) in ("XAUTUSD", "SLVONUSD") else "bitunix"
    start = now - 2000 * 86400
    get = lambda res, s=start: [c[:5] for c in candles(source, symbol, res, s, now)]  # noqa: E731
    daily = get("1d")
    base = {"4h": get("4h"), "1d": daily, "1w": get("1w"), "1M": monthly_from_daily(daily)}
    evals = {"1d": daily, "4h": base["4h"]}
    if base["4h"]:
        evals["1h"] = get("1h", base["4h"][0][0])
    return base, evals


def run_symbol(market, symbol, base, evals, now, since):
    out = []
    for tf in config.FIB_TL_TIMEFRAMES:
        res = trades.EVAL_RESOLUTION[market][tf]
        out += replay(market, symbol, tf, base.get(tf, []), evals.get(res, []), now, since)
    return out


def table(got):
    rows = []
    groups = defaultdict(list)
    for t in got:
        for tf in ("all", t["tf"]):
            groups[(t["market"], tf)].append(t)
    order = ["all"] + list(config.FIB_TL_TIMEFRAMES)
    for (market, tf), items in sorted(groups.items(), key=lambda kv: (kv[0][0], order.index(kv[0][1]))):
        for s in STOPS:
            risks = sorted(t[f"risk_{s}"] for t in items)
            for e in EXITS:
                net = [t[f"{s}|{e}"] for t in items if t[f"{s}|{e}"] is not None]
                if not net:
                    continue
                rows.append({"market": market, "tf": tf, "stop": s, "exit": e, "alerts": len(items),
                             "filled": len(net), "wins_%": round(100 * sum(1 for x in net if x > 0.05) / len(net)),
                             "net_R": round(sum(net), 1), "R_per_trade": round(sum(net) / len(net), 3),
                             "median_risk_%": round(risks[len(risks) // 2], 2)})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = int(time.time())
    got = []

    def one(symbol):
        try:
            return run_symbol(CRYPTO, symbol, *crypto_load(symbol, now), now, since)
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            return []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for r in pool.map(one, scanner.active_watchlist()):
            got += r
    import nse_scanner
    for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
        got += run_symbol(NSE, symbol, base, evals, now, since)

    pd.DataFrame([{k: v for k, v in t.items() if k != "stops"} for t in got]).to_csv(OUT / "trades.csv", index=False)
    df = table(got)
    df.to_csv(OUT / "summary.csv", index=False)
    best = df[df["tf"] == "all"].sort_values(["market", "R_per_trade"], ascending=[True, False])
    text = [f"# Trendline stop + exit backtest: {args.since} to now", "",
            "Live trendline alerts replayed; only the stop and the exit change. Net R after Delta fees, "
            "stops slipped, timeouts closed at market. Crypto on Bitunix candles.", "",
            "## All timeframes, best first", "", best.to_markdown(index=False), "",
            "## By timeframe", "", df[df["tf"] != "all"].to_markdown(index=False), ""]
    (OUT / "RESULTS.md").write_text("\n".join(text))
    print("\n".join(text))
    trace(got)


def trace(got):
    """Lakky's two charts: every AVAX 1D alert since Oct 1 with each stop."""
    lines = ["# AVAX 1D trendline alerts (chart check)", ""]
    for t in got:
        if t["symbol"].startswith("AVAX") and t["tf"] == "1d" and t["alert_ts"] >= pd.Timestamp("2026-10-01", tz="UTC").timestamp():
            when = pd.Timestamp(t["alert_ts"], unit="s", tz="UTC")
            stops = ", ".join(f"{k} {v:.4f} ({t[f'risk_{k}']:.2f}%)" for k, v in t["stops"].items())
            lines.append(f"- {when:%Y-%m-%d %H:%M} {'BUY' if t['long'] else 'SELL'} entry {t['entry']:.4f}: {stops}")
    (OUT / "AVAX_TRACE.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
