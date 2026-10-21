"""Research only: S/R zone alerts on 1D, 1W and 1M next to today's 4H (lakky, 2026-10-16).

lakky: "remove 30m for now and add other 4h, 1d, 1w and 1month". Zones only run on
30m and 4H today, so 1D/1W/1M zones are a new strategy - this replays the live zone
engine (scanner.build_zones, nearest zone per side, too-young, over-touched, stop
too wide, approach side only, MAX_DISTANCE_PCT band and re-arm, 4h cooldown, crypto
daily-trend filter and alert window) on each timeframe, Sep 1 to now.

Scoring: the zone report's 6-hour crypto window and same-day NSE window are built
for 30m/4H trades, so every timeframe here - 4H included, for a like-for-like row -
is scored the way fib alerts are (fib_trendline_trades.simulate: entry at the zone's
near edge within 5 candles of the alert's timeframe, held up to 20, 1R/2R, +0.5R
breakeven, net of fees). Crypto on Bitunix candles (as live alerts), NSE on Yahoo.

    PYTHONPATH=research python research/zone_htf_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import bisect
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bitunix_data  # noqa: E402
import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import (  # noqa: E402
    CRYPTO, HISTORY_START, IST, NSE, TF_SECONDS, bitunix_candles, candle_is_closed, monthly_from_daily,
)

OUT = Path(__file__).resolve().parent / "out" / "zone_htf"
TIMEFRAMES = ["4h", "1d", "1w", "1M"]
MIN_HISTORY = 50          # closed candles before a zone build is tried (1M has ~55 on Bitunix)
EARLY_BAND = [True]       # the live 3% band on 1W / 1M (config.alert_band_pct); research/early_band_backtest.py turns it off


def crypto_load(symbol, now, since):
    contract = scanner.delta_contract(symbol)
    if contract is None or not bitunix_data.uses_bitunix(symbol):
        return None
    pair = bitunix_data.pair_for(symbol, contract)

    def get(res, start):
        return fbt._cached(f"zh_{pair}_{res}_{int(start) // 86400}", lambda: bitunix_candles(pair, res, start, now))

    daily = get("1d", HISTORY_START)
    base = {"4h": get("4h", since - (config.OHLCV_LIMIT + 50) * TF_SECONDS["4h"]),
            "1d": daily, "1w": get("1w", HISTORY_START), "1M": monthly_from_daily(daily)}
    evals = {"1d": daily, "4h": get("4h", since - 2 * 86400), "1h": get("1h", since - 2 * 86400)}
    return base, evals, daily


def daily_trend_at(daily, ts):
    closes = [c[4] for c in daily if c[0] + 86400 <= ts]
    if len(closes) < config.CRYPTO_TREND_EMA + 5:
        return None
    ema = pd.Series(closes).ewm(span=config.CRYPTO_TREND_EMA, adjust=False).mean().iloc[-1]
    return 1 if closes[-1] > ema else -1


def replay(market, symbol, tf, base, evalc, daily, since, now):
    """Zone alerts the live scanner would send on this chart, each traded and scored."""
    if base and not candle_is_closed(market, base[-1][0], tf, now):
        base = base[:-1]
    if len(base) <= MIN_HISTORY or not evalc:
        return []
    df = pd.DataFrame([c[:5] + [0.0] for c in base], columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = df["time"] * 1000
    times = [c[0] for c in base]
    eval_ts = [c[0] for c in evalc]
    eval_secs = TF_SECONDS[trades.EVAL_RESOLUTION[market][tf]]
    band = (config.alert_band_pct(tf, config.MAX_DISTANCE_PCT) if EARLY_BAND[0] else config.MAX_DISTANCE_PCT) / 100
    rearm = band * config.REARM_FACTOR
    horizon = (config.FIB_TL_ENTRY_WAIT_BARS + config.FIB_TL_MAX_HOLD_BARS + 1) * trades.EVAL_PER_BAR[market][tf]
    trend_filter = market == CRYPTO and symbol in config.CRYPTO_WATCHLIST and config.CRYPTO_TREND_FILTER
    state, out = {}, []
    # Bar i is the forming candle: zones from the closed candles before it, price walked on finer candles.
    # The forming candle itself is left out (the live scan feeds it in - the one simplification).
    n = len(base) + 1      # one past the last closed candle: the candle forming now
    for i in range(MIN_HISTORY, n):
        start = times[i] if i < len(base) else times[-1] + TF_SECONDS[tf]
        if start + TF_SECONDS[tf] <= since:
            continue
        hist = df.iloc[max(0, i - config.OHLCV_LIMIT):i].reset_index(drop=True)
        supply, demand = scanner.build_zones(hist)
        cur = len(hist)
        end = times[i + 1] if i + 1 < len(base) else start + TF_SECONDS[tf]
        e0, e1 = bisect.bisect_left(eval_ts, max(start, since)), bisect.bisect_left(eval_ts, end)
        if e0 >= e1:
            continue
        open_px = float(evalc[e0][1])
        for zone_type, zones in (("supply", supply), ("demand", demand)):
            zone, _ = scanner.nearest_active_zone(open_px, zones, zone_type, cur)
            if zone is None or scanner.stop_too_wide(zone_type, zone):
                continue
            entry = scanner.planned_entry_price(zone_type, zone)
            stop = scanner.planned_stop_price(zone_type, zone)
            key = f"{zone_type}|{zone['bottom']:.10g}|{zone['top']:.10g}"
            st = state.setdefault(key, {"in_zone": False, "last": -10**12})
            for k in range(e0, e1):
                ts, o, h, l, c = evalc[k][:5]
                if zone_type == "demand":
                    if l <= zone["bottom"]:
                        break                              # wick through the far edge kills it
                    touched, past, far = l <= entry * (1 + band), o < entry, (c - entry) / c > rearm
                else:
                    if h >= zone["top"]:
                        break
                    touched, past, far = h >= entry * (1 - band), o > entry, (entry - c) / c > rearm
                if touched:
                    # as live plan_alerts: re-alert only after leaving the re-arm band AND the 4h cooldown
                    due = (not st["in_zone"]) and ts - st["last"] >= config.ALERT_COOLDOWN_SECONDS
                    awake = market != CRYPTO or not fbt.crypto_held(ts, eval_secs)
                    against = trend_filter and scanner.against_daily_trend(zone_type, daily_trend_at(daily, ts))
                    if due and not past and awake and not against \
                            and ts - st["last"] >= scanner.ZONE_REPEAT_SUPPRESSION_SECONDS:
                        st["last"] = ts
                        plan = {"side": "long" if zone_type == "demand" else "short", "entry": entry, "sl": stop}
                        out.append({"market": market, "symbol": symbol, "tf": tf, "kind": "zone", "alert_ts": ts,
                                    "plan": plan,
                                    "result": trades.simulate(plan, market, tf, ts, evalc[k + 1:k + 1 + horizon])})
                    st["in_zone"] = True
                elif far:
                    st["in_zone"] = False
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--limit", type=int, default=0, help="first N symbols per market (smoke test)")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    scanner.ZONE_BASE_EXTRA = 1    # auto_base_extra is 1 for 4h and every larger timeframe
    since = int(pd.Timestamp(args.since, tz=IST).timestamp())
    now = int(time.time())
    started = time.time()
    got = []

    crypto = list(config.WATCHLIST)[: args.limit or None]

    def one(symbol):
        try:
            data = crypto_load(symbol, now, since)
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            return []
        if not data:
            print(f"crypto {symbol}: no Bitunix chart")
            return []
        base, evals, daily = data
        res = []
        for tf in TIMEFRAMES:
            res += replay(CRYPTO, symbol, tf, base[tf], evals[trades.EVAL_RESOLUTION[CRYPTO][tf]], daily, since, now)
        print(f"crypto {symbol}: {len(res)} alerts ({time.time() - started:.0f}s)")
        return res

    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(one, crypto):
            got += res

    import nse_scanner
    symbols = nse_scanner.load_watchlist()[: args.limit or None]
    fbt.TIMEFRAMES = TIMEFRAMES
    for symbol, (base, evals) in fbt.nse_data(symbols).items():
        res = []
        for tf in TIMEFRAMES:
            res += replay(NSE, symbol, tf, base.get(tf, []), evals.get(trades.EVAL_RESOLUTION[NSE][tf], []),
                          None, since, now)
        got += res
    print(f"NSE done ({time.time() - started:.0f}s)")

    rows = []
    for market in (CRYPTO, NSE):
        for tf in TIMEFRAMES:
            pick = [t for t in got if t["market"] == market and t["tf"] == tf]
            if pick:
                rows.append({"market": market, "tf": tf, **row(f"zones {tf}", pick)})
        for label, tfs in (("1D+ (1D/1W/1M)", ("1d", "1w", "1M")),):
            pick = [t for t in got if t["market"] == market and t["tf"] in tfs]
            if pick:
                rows.append({"market": market, "tf": label, **row(f"zones {label}", pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame([{**{k: t[k] for k in ("market", "symbol", "tf", "alert_ts")}, **t["plan"],
                   "outcome": t["result"]["outcome"],
                   "net_r": (trades.booked_r(t["plan"], t["market"], t["result"])[1]
                             if t["result"]["filled"] else None)} for t in got]).to_csv(OUT / "trades.csv", index=False)
    text = [f"# S/R zone alerts on 4H, 1D, 1W, 1M ({args.since} to now)", "",
            "Live zone engine and alert filters on each timeframe. Every row scored like fib alerts "
            "(entry within 5 candles, hold 20, 1R/2R, +0.5R breakeven), net after fees; % = R x the trade's "
            "stop distance. Crypto on Bitunix, NSE on Yahoo.", "",
            df.to_markdown(index=False), ""]
    (OUT / "ZONE_HTF.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
