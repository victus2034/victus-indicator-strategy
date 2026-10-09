"""Research only - nothing here is imported by the live scanners.

Delta India vs Bitunix as the candle source for the crypto alerts (2026-10-05).

    VICTUS_TIMEFRAME=30m python research/bitunix_compare.py --part zones --tf 30m
    VICTUS_TIMEFRAME=4h  python research/bitunix_compare.py --part zones --tf 4h
    python research/bitunix_compare.py --part fib

zones: (A) candle-by-candle comparison of the two venues (plus OKX as a neutral
third book where it lists the coin) and (B) a replay of the zone alerts on each
venue's candles, scored by the production scorer (daily_backtest_summary) on
5m candles. Each alert set is scored on Delta's 5m candles (where the trade is
taken and the fees are paid) and on Bitunix's.

fib: the fib/trendline history backtest (fib_trendline_backtest.replay) run once
on Delta and once on Bitunix candles, cut to the window both venues cover.

Fees stay Delta's in every run. Writes research/out/bitunix/.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import scanner  # noqa: E402

IST = scanner.IST
BITUNIX = "https://fapi.bitunix.com"
TF_SECONDS = {"5m": 300, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800}
OUT = Path(__file__).resolve().parent / "out" / "bitunix"
CACHE = Path(__file__).resolve().parent / ".bitunix_cache"
SYMBOLS = list(config.CRYPTO_WATCHLIST)
EVAL_DAYS = {"30m": 60, "4h": 120}
SOURCES = ("delta", "bitunix")

# ----------------------------------------------------------------- candles

_rate_lock = threading.Lock()
_last_call = [0.0]


def _throttle(gap=0.13):
    with _rate_lock:
        wait = _last_call[0] + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()


def bitunix_symbol(symbol: str) -> str:
    if symbol in config.BITUNIX_XSTOCK_PAIRS:
        return config.BITUNIX_XSTOCK_PAIRS[symbol]
    contract = scanner.delta_contract(symbol) or symbol.split("/")[0] + "USD"
    return contract[:-3] + "USDT"


def _get_json(url, params, attempts=4):
    last = None
    for attempt in range(attempts):
        try:
            _throttle()
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as error:  # noqa: BLE001
            last = error
            time.sleep(1.5 * (attempt + 1))
    raise last


def bitunix_candles(sym: str, interval: str, start: int, end: int) -> list[list[float]]:
    """[ts_s, o, h, l, c, base_volume] for [start, end), oldest first.

    The API returns at most 200 rows, newest first, ending at endTime - so page
    backwards from end until a short page or the start is reached."""
    out = {}
    cursor = end * 1000 - 1
    while cursor > start * 1000:
        payload = _get_json(f"{BITUNIX}/api/v1/futures/market/kline", {
            "symbol": sym, "interval": interval, "limit": 200,
            "startTime": start * 1000, "endTime": cursor})
        rows = payload.get("data") or []
        if payload.get("code") not in (0, "0"):
            raise RuntimeError(payload)
        for row in rows:
            ts = int(row["time"]) // 1000
            if start <= ts < end:
                out[ts] = [ts, float(row["open"]), float(row["high"]), float(row["low"]),
                           float(row["close"]), float(row.get("baseVol") or 0)]
        if len(rows) < 200:
            break
        oldest = min(int(row["time"]) for row in rows)
        if oldest - 1 >= cursor:
            break
        cursor = oldest - 1
    return [out[k] for k in sorted(out)]


_contract_values: dict[str, float] = {}


def delta_contract_value(contract: str) -> float:
    if contract not in _contract_values:
        payload = _get_json(f"{config.DELTA_API_BASE_URL}/v2/products/{contract}", {})
        _contract_values[contract] = float((payload.get("result") or {}).get("contract_value") or 1.0)
    return _contract_values[contract]


def delta_candles(contract: str, resolution: str, start: int, end: int) -> list[list[float]]:
    """[ts_s, o, h, l, c, base_volume]: volume in contracts x contract value."""
    seconds = TF_SECONDS[resolution]
    value = delta_contract_value(contract)
    out = {}
    window_end = end
    while window_end > start:
        window_start = max(start, window_end - 1999 * seconds)
        payload = _get_json(f"{config.DELTA_API_BASE_URL}/v2/history/candles", {
            "symbol": contract, "resolution": resolution, "start": window_start, "end": window_end})
        if not payload.get("success"):
            raise RuntimeError(payload)
        rows = payload.get("result") or []
        for c in rows:
            ts = int(c["time"])
            if start <= ts < end:
                out[ts] = [ts, float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]),
                           float(c.get("volume") or 0) * value]
        if not rows:
            break
        window_end = window_start - 1
    return [out[k] for k in sorted(out)]


def okx_candles(symbol: str, resolution: str, start: int, end: int) -> list[list[float]]:
    import ccxt

    exchange = getattr(okx_candles, "_ex", None)
    if exchange is None:
        exchange = okx_candles._ex = ccxt.okx({"enableRateLimit": True})
        exchange.load_markets()
    pair = f"{bitunix_symbol(symbol)[:-4]}/USDT:USDT"
    if pair not in exchange.markets:
        return []
    out = {}
    since = start * 1000
    while since < end * 1000:
        rows = exchange.fetch_ohlcv(pair, timeframe=resolution, since=since, limit=100)
        if not rows:
            break
        for row in rows:
            ts = int(row[0]) // 1000
            if start <= ts < end:
                out[ts] = [ts, *map(float, row[1:6])]
        nxt = int(rows[-1][0]) + TF_SECONDS[resolution] * 1000
        if nxt <= since:
            break
        since = nxt
    return [out[k] for k in sorted(out)]


def cached(name, fetch):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    data = fetch()
    path.write_text(json.dumps(data))
    return data


def candles(source: str, symbol: str, resolution: str, start: int, end: int):
    contract = scanner.delta_contract(symbol)
    key = f"{source}_{contract}_{resolution}_{start // 86400}_{end // 3600}"
    if source == "delta":
        return cached(key, lambda: delta_candles(contract, resolution, start, end))
    if source == "bitunix":
        return cached(key, lambda: bitunix_candles(bitunix_symbol(symbol), resolution, start, end))
    return cached(key, lambda: okx_candles(symbol, resolution, start, end))


# ----------------------------------------------------------------- (A) candle comparison

def frame(rows) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    return df.set_index("ts")


def compare_candles(symbol: str, tf: str, data: dict[str, list]) -> dict:
    d, b = frame(data["delta"]), frame(data["bitunix"])
    o = frame(data["okx"]) if data.get("okx") else None
    both = d.join(b, lsuffix="_d", rsuffix="_b", how="inner")
    if both.empty:
        return {"symbol": symbol, "tf": tf, "common_bars": 0}
    span = (max(d.index.max(), b.index.max()) - max(d.index.min(), b.index.min())) // TF_SECONDS[tf] + 1
    tr = pd.concat([both["high_b"] - both["low_b"], (both["high_b"] - both["close_b"].shift()).abs(),
                    (both["low_b"] - both["close_b"].shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14, min_periods=5).mean().bfill()
    tol = 0.25 * atr
    d_spike = ((both["high_d"] - both["high_b"]) > tol) | ((both["low_b"] - both["low_d"]) > tol)
    b_spike = ((both["high_b"] - both["high_d"]) > tol) | ((both["low_d"] - both["low_b"]) > tol)
    row = {
        "symbol": symbol, "tf": tf, "common_bars": len(both),
        "delta_missing": int(max(0, span - len(d.loc[d.index >= b.index.min()]))),
        "bitunix_missing": int(max(0, span - len(b.loc[b.index >= d.index.min()]))),
        "close_diff_med_pct": float(((both["close_d"] - both["close_b"]).abs() / both["close_b"]).median() * 100),
        "range_ratio_med": float(((both["high_d"] - both["low_d"]) / (both["high_b"] - both["low_b"]).replace(0, np.nan)).median()),
        "vol_ratio_bitunix_to_delta": float((both["volume_b"] / both["volume_d"].replace(0, np.nan)).median()),
        "delta_thin_pct": float((both["volume_d"] < 0.1 * both["volume_d"].median()).mean() * 100),
        "bitunix_thin_pct": float((both["volume_b"] < 0.1 * both["volume_b"].median()).mean() * 100),
        "delta_zero_vol": int((both["volume_d"] <= 0).sum()),
        "bitunix_zero_vol": int((both["volume_b"] <= 0).sum()),
        "delta_wick_outliers": int(d_spike.sum()),
        "bitunix_wick_outliers": int(b_spike.sum()),
    }
    if o is not None and not o.empty:
        tri = both.join(o.add_suffix("_o"), how="inner")
        if not tri.empty:
            t = tol.reindex(tri.index)
            # An outlier the third book does not print either: that venue's own wick.
            d_only = (((tri["high_d"] - tri[["high_b", "high_o"]].max(axis=1)) > t)
                      | ((tri[["low_b", "low_o"]].min(axis=1) - tri["low_d"]) > t))
            b_only = (((tri["high_b"] - tri[["high_d", "high_o"]].max(axis=1)) > t)
                      | ((tri[["low_d", "low_o"]].min(axis=1) - tri["low_b"]) > t))
            row.update({"okx_bars": len(tri), "delta_only_wicks": int(d_only.sum()),
                        "bitunix_only_wicks": int(b_only.sum())})
    return row


# ----------------------------------------------------------------- (B) zone replay

def daily_trend_at(daily: list, ts: int):
    closes = [c[4] for c in daily if c[0] + 86400 <= ts]
    if len(closes) < config.CRYPTO_TREND_EMA + 5:
        return None
    ema = pd.Series(closes).ewm(span=config.CRYPTO_TREND_EMA, adjust=False).mean().iloc[-1]
    return 1 if closes[-1] > ema else -1


def in_window(ts: int) -> bool:
    return scanner.in_alert_window(datetime.fromtimestamp(ts, IST))


def replay_zones(args) -> list[dict]:
    """Alerts the live crypto scanner would have sent on these candles.

    Bar t is the forming candle: zones come from the closed candles before it
    (the live scan also feeds the forming one in - the only simplification),
    and price inside it is walked on 5m candles. Same filters as
    process_candidate: nearest zone per side, too-young, over-touched, stop too
    wide, daily trend, approach side only, the 08:00-01:00 IST window, re-arm at
    MAX_DISTANCE_PCT x REARM_FACTOR and the 4h repeat suppression."""
    symbol, tf, source, base, fine, daily, eval_start = args
    secs = TF_SECONDS[tf]
    df = pd.DataFrame(base, columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = df["time"] * 1000
    fine_ts = [c[0] for c in fine]
    band = config.MAX_DISTANCE_PCT / 100
    rearm = band * config.REARM_FACTOR
    state: dict[str, dict] = {}
    alerts = []
    first = next((i for i, c in enumerate(base) if c[0] >= eval_start), len(base))
    for t in range(max(first, 200), len(base)):
        hist = df.iloc[max(0, t - config.OHLCV_LIMIT):t].reset_index(drop=True)
        supply, demand = scanner.build_zones(hist)
        open_t = float(base[t][1])
        cur = len(hist)
        lo = int(np.searchsorted(fine_ts, base[t][0]))
        hi = int(np.searchsorted(fine_ts, base[t][0] + secs))
        for zone_type, zones in (("supply", supply), ("demand", demand)):
            zone, _dist = scanner.nearest_active_zone(open_t, zones, zone_type, cur)
            if zone is None or scanner.stop_too_wide(zone_type, zone):
                continue
            entry = scanner.planned_entry_price(zone_type, zone)
            key = f"{zone_type}|{zone['bottom']:.10g}|{zone['top']:.10g}"
            st = state.setdefault(key, {"in_zone": False, "last": -10**12})
            for k in range(lo, hi):
                ts, o, h, l, c = fine[k][:5]
                if zone_type == "demand":
                    if l <= zone["bottom"]:
                        break                                   # wick through the far edge kills it
                    touched = l <= entry * (1 + band)
                    past = o < entry
                    far = (c - entry) / c > rearm
                else:
                    if h >= zone["top"]:
                        break
                    touched = h >= entry * (1 - band)
                    past = o > entry
                    far = (entry - c) / c > rearm
                if touched:
                    due = (not st["in_zone"]) or ts - st["last"] >= config.ALERT_COOLDOWN_SECONDS
                    if due and not past and ts - st["last"] >= scanner.ZONE_REPEAT_SUPPRESSION_SECONDS \
                            and in_window(ts) and not (symbol in config.CRYPTO_WATCHLIST and scanner.against_daily_trend(
                                zone_type, daily_trend_at(daily, ts))):
                        st["last"] = ts
                        record = {
                            "delivered_at_utc": pd.Timestamp(ts, unit="s", tz="UTC").isoformat(),
                            "symbol": symbol, "exchange": source, "timeframe": tf,
                            "side": "short" if zone_type == "supply" else "long", "zone_type": zone_type,
                            "distance_pct": config.MAX_DISTANCE_PCT, "alert_price": entry * (1 + band if zone_type == "demand" else 1 - band),
                            "level": float(zone["top"] if zone_type == "supply" else zone["bottom"]),
                            "zone_bottom": float(zone["bottom"]), "zone_top": float(zone["top"]),
                            "body_entry": zone.get("body_entry"), "planned_entry": entry,
                            "stop_price": scanner.planned_stop_price(zone_type, zone),
                            "stop_distance_pct": scanner.planned_stop_distance_pct(zone_type, zone),
                            "score": None,
                        }
                        record["trade_id"] = scanner.delivered_alert_id(record)
                        alerts.append(record)
                    st["in_zone"] = True
                elif far:
                    st["in_zone"] = False
    return alerts


def grade(alert_path: Path, tf: str, fine_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    import daily_backtest_summary as dbs

    alerts = dbs.load_records(alert_path, tf)
    if alerts.empty:
        return pd.DataFrame()
    rows = dbs.simulate_alerts(alerts, fine_frames, "crypto")
    results, _ = dbs.apply_same_day_zone_cooldown(pd.DataFrame(rows), "crypto")
    results = results.reset_index(drop=True)
    results["event_ts"] = alerts["event_time"].map(lambda t: int(pd.Timestamp(t).timestamp())).values
    results["planned_entry_x"] = alerts["planned_entry"].values
    return results


FILLED = {"SL", "BE", "+1R", "+2R", "Neither"}


def summarise(results: pd.DataFrame) -> dict:
    if results.empty:
        return {"alerts": 0}
    res = results.get("final_result", pd.Series(index=results.index, dtype=object)).where(results.get("filled", pd.Series(False, index=results.index)).fillna(False).astype(bool), results.get("outcome"))
    filled = results[res.isin(FILLED)]
    net = pd.to_numeric(filled["net_realized_r"], errors="coerce")
    counts = res.value_counts().to_dict()
    wins = counts.get("+1R", 0) + counts.get("+2R", 0)
    return {
        "alerts": int((res != "zone_cooldown").sum()), "filled": len(filled),
        "SL": counts.get("SL", 0), "BE": counts.get("BE", 0), "+1R": counts.get("+1R", 0),
        "+2R": counts.get("+2R", 0), "Neither": counts.get("Neither", 0),
        "ambiguous": int((results.get("final_result", pd.Series(dtype=str)).astype(str) == str(__import__("daily_backtest_summary").DATA_QUALITY_AMBIGUOUS)).sum()),
        "win_pct": round(100 * wins / (wins + counts.get("SL", 0)), 1) if wins + counts.get("SL", 0) else None,
        "net_R": round(float(net.sum()), 1), "R_per_trade": round(float(net.mean()), 3) if len(net) else None,
    }


def unmatched(a: pd.DataFrame, b: pd.DataFrame) -> pd.Series:
    """True for alerts in a with no alert in b on the same zone (+-2h, entry within 0.3%)."""
    if a.empty:
        return pd.Series(dtype=bool)
    out = []
    groups = {k: g for k, g in b.groupby(["symbol", "side"])} if not b.empty else {}
    for row in a.itertuples():
        g = groups.get((row.symbol, row.side))
        if g is None:
            out.append(True)
            continue
        near = (g["event_ts"] - row.event_ts).abs() <= 2 * 3600
        close = (g["planned_entry_x"] - row.planned_entry_x).abs() / row.planned_entry_x <= 0.003
        out.append(not bool((near & close).any()))
    return pd.Series(out, index=a.index)


def zones_part(tf: str) -> None:
    assert scanner.TIMEFRAME == tf, "set VICTUS_TIMEFRAME to the --tf value"
    OUT.mkdir(parents=True, exist_ok=True)
    now = int(time.time()) // 300 * 300
    eval_start = now - EVAL_DAYS[tf] * 86400
    base_start = eval_start - (config.OHLCV_LIMIT + 50) * TF_SECONDS[tf]
    daily_start = eval_start - 400 * 86400
    data = {}

    def load(symbol):
        out = {}
        for source in SOURCES:
            try:
                out[source] = {
                    "base": candles(source, symbol, tf, base_start, now),
                    "fine": candles(source, symbol, "5m", eval_start - 3600, now),
                    "daily": candles(source, symbol, "1d", daily_start, now),
                }
            except Exception as error:  # noqa: BLE001
                print(f"{source} {symbol} failed: {error}")
        try:
            out["okx"] = candles("okx", symbol, tf, eval_start, now)
        except Exception as error:  # noqa: BLE001
            print(f"okx {symbol} unavailable: {str(error)[:80]}")
        return symbol, out

    with ThreadPoolExecutor(max_workers=4) as pool:
        for symbol, out in pool.map(load, SYMBOLS):
            data[symbol] = out
            print(f"{symbol}: " + ", ".join(f"{s} {len(v['base'])}/{len(v['fine'])}" for s, v in out.items() if s in SOURCES))

    # (A) candles over the evaluation window, closed bars only
    rows = []
    for symbol, out in data.items():
        if not all(s in out for s in SOURCES):
            continue
        cut = now - TF_SECONDS[tf]
        win = {s: [c for c in out[s]["base"] if eval_start <= c[0] < cut] for s in SOURCES}
        win["okx"] = [c for c in out.get("okx") or [] if eval_start <= c[0] < cut]
        rows.append(compare_candles(symbol, tf, win))
    candles_df = pd.DataFrame(rows)
    candles_df.to_csv(OUT / f"candles_{tf}.csv", index=False)

    # (B) replay - only symbols both venues serve, so the totals compare like for like
    common = [s for s, out in data.items() if all(s in out and out[s]["base"] for s in SOURCES)]
    jobs = [(s, tf, src, data[s][src]["base"], data[s][src]["fine"], data[s][src]["daily"], eval_start)
            for s in common for src in SOURCES]
    alerts = {src: [] for src in SOURCES}
    started = time.time()
    with ProcessPoolExecutor() as pool:
        for job, result in zip(jobs, pool.map(replay_zones, jobs)):
            alerts[job[2]] += result
            print(f"replayed {job[0]} {job[2]}: {len(result)} alerts ({time.time() - started:.0f}s)")
    paths = {}
    for src in SOURCES:
        paths[src] = OUT / f"alerts_{tf}_{src}.jsonl"
        with paths[src].open("w") as fh:
            for rec in sorted(alerts[src], key=lambda r: r["delivered_at_utc"]):
                fh.write(json.dumps(rec) + "\n")

    import daily_backtest_summary as dbs
    dbs.configure_crypto_data(tf)
    fine_frames = {g: {s: dbs.normalize_crypto_frame([[c[0] * 1000, *c[1:6]] for c in data[s][g]["fine"]])
                       for s in common} for g in SOURCES}
    graded = {(a, g): grade(paths[a], tf, fine_frames[g]) for a in SOURCES for g in SOURCES}
    summary = []
    for (a, g), res in graded.items():
        summary.append({"alerts_from": a, "graded_on": g, **summarise(res)})
    # Alerts one venue sent and the other did not - graded on Delta, where the trade is.
    for a, b in (("delta", "bitunix"), ("bitunix", "delta")):
        res = graded[(a, "delta")]
        if res.empty:
            continue
        only = res[unmatched(res, graded[(b, "delta")])]
        summary.append({"alerts_from": f"{a} only", "graded_on": "delta", **summarise(only)})
        only.to_csv(OUT / f"only_{a}_{tf}.csv", index=False)
    pd.DataFrame(summary).to_csv(OUT / f"zones_{tf}.csv", index=False)

    lines = [f"# Zones {tf}: Delta vs Bitunix candles", "",
             f"Window: last {EVAL_DAYS[tf]} days to {datetime.fromtimestamp(now, IST):%Y-%m-%d %H:%M} IST; "
             f"{len(common)} crypto symbols both venues serve. Fees: Delta in every row.", "",
             "## Candles (evaluation window, closed bars)", "", candles_df.to_markdown(index=False, floatfmt=".3f"),
             "", "## Alert replay", "", pd.DataFrame(summary).to_markdown(index=False), ""]
    (OUT / f"ZONES_{tf}.md").write_text("\n".join(lines))
    print("\n".join(lines))


# ----------------------------------------------------------------- fib / trendline

def fib_part() -> None:
    import fib_trendline_backtest as fbt
    import fib_trendline_trades as trades
    from fib_trendline_data import monthly_from_daily

    OUT.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    since = now - 2000 * 86400
    tfs = list(config.FIB_TL_TIMEFRAMES)          # live set: 30m is off
    fbt.TIMEFRAMES = tfs

    def load(source, symbol):
        get = lambda res: [c[:5] for c in candles(source, symbol, res, since, now)]  # noqa: E731
        daily = get("1d")
        base = {"4h": get("4h"), "1d": daily, "1w": get("1w"), "1M": monthly_from_daily(daily)}
        evals = {"1d": daily, "4h": base["4h"]}
        if base["4h"]:
            evals["1h"] = [c[:5] for c in candles(source, symbol, "1h", base["4h"][0][0], now)]
        return base, evals

    def regrade_on(t, evals):
        res = trades.EVAL_RESOLUTION[fbt.CRYPTO][t["tf"]]
        series = evals.get(res) or []
        stamps = [c[0] for c in series]
        k = __import__("bisect").bisect_right(stamps, t["alert_ts"])
        horizon = (config.FIB_TL_ENTRY_WAIT_BARS + config.FIB_TL_MAX_HOLD_BARS + 1) * trades.EVAL_PER_BAR[fbt.CRYPTO][t["tf"]]
        after = series[k:k + horizon]
        return {**t, "graded": "delta", "result": trades.simulate(t["plan"], fbt.CRYPTO, t["tf"], t["alert_ts"], after)}

    def one(symbol):
        out = {}
        try:
            data = {src: load(src, symbol) for src in SOURCES}
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} failed: {error}")
            return out
        for src in SOURCES:
            base, evals = data[src]
            got = fbt.replay_symbol(fbt.CRYPTO, symbol, base, evals, now)
            if src == "bitunix":
                # The same Bitunix alerts traded on Delta's candles - where the
                # order actually sits - so a calmer book cannot flatter the score.
                got += [regrade_on(t, data["delta"][1]) for t in got]
            # cut to the window both venues cover for this timeframe
            keep = []
            for t in got:
                starts = [data[s][0][t["tf"]][0][0] for s in SOURCES if data[s][0].get(t["tf"])]
                if len(starts) == 2 and t["alert_ts"] >= max(starts) + 60 * TF_SECONDS.get(t["tf"], 86400 * 30):
                    keep.append(t)
            out[src] = keep
        print(f"{symbol}: " + ", ".join(f"{s} {len(v)}" for s, v in out.items()))
        return out

    every = {src: [] for src in SOURCES}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for out in pool.map(one, SYMBOLS):
            for src, items in out.items():
                every[src] += items

    sets = {
        "delta (graded on delta)": every["delta"],
        "bitunix (graded on bitunix)": [t for t in every["bitunix"] if t.get("graded") != "delta"],
        "bitunix (graded on delta)": [t for t in every["bitunix"] if t.get("graded") == "delta"],
    }
    rows = []
    for src, items in sets.items():
        for r in trades.summarise(items):
            r = dict(r)
            filled = r["filled"]
            rows.append({"source": src, "kind": r["kind"], "tf": r["tf"], "alerts": r["alerts"], "filled": filled,
                         "win_1r": r["win_1r"], "net_R_at_2R": None if r["net_r_2r"] is None else round(r["net_r_2r"] * filled, 1),
                         "R_per_trade_2R": r["net_r_2r"], "net_R_at_1R": None if r["net_r_1r"] is None else round(r["net_r_1r"] * filled, 1)})
    df = pd.DataFrame(rows).sort_values(["kind", "tf", "source"])
    df.to_csv(OUT / "fib_trendline.csv", index=False)
    text = ["# Fib + trendline: Delta vs Bitunix candles", "",
            f"Live timeframes {', '.join(tfs)}; {len(SYMBOLS)} crypto symbols; each timeframe cut to the window both "
            "venues cover (plus 60 bars of warm-up). 'random' is the no-edge control. Fees: Delta.", "",
            df.to_markdown(index=False, floatfmt=".3f"), ""]
    (OUT / "FIB_TRENDLINE.md").write_text("\n".join(text))
    print("\n".join(text))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--part", choices=["zones", "fib"], required=True)
    parser.add_argument("--tf", choices=list(EVAL_DAYS), default="30m")
    parser.add_argument("--symbols", choices=["crypto", "xstock"], default="crypto",
                        help="xstock: the six xStocks (2026-10-09), written to research/out/xstock/")
    args = parser.parse_args()
    if args.symbols == "xstock":
        global SYMBOLS, OUT, CACHE
        SYMBOLS = list(config.XSTOCK_WATCHLIST)
        OUT = OUT.parent / "xstock"
        CACHE = CACHE.parent / ".xstock_cache"
    if args.part == "zones":
        zones_part(args.tf)
    else:
        fib_part()


if __name__ == "__main__":
    main()
