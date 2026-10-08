"""Research only - nothing here is imported by the live scanners.

Notion task 20 (2026-10-08, Lakky): "on the buy call prefer the lower zone, on
the sell side prefer the upper zone". Two readings, both replayed here against
the live rule (alert the nearest zone per side):

  deepest_X  - stacked zones: when another active demand zone sits within X% below
               the nearest one, skip the nearer zone and alert only the lowest of
               the stack (supply: the highest). A single zone alerts as today.
  discount_N - range location: a demand zone alerts only if its entry sits in the
               lower half of the last N candles' high-low range, a supply zone
               only in the upper half.

    VICTUS_TIMEFRAME=30m PYTHONPATH=research python research/zone_preference_backtest.py --tf 30m
    VICTUS_TIMEFRAME=4h  PYTHONPATH=research python research/zone_preference_backtest.py --tf 4h

Crypto watchlist, Bitunix candles for the alerts (as live), graded by the
production scorer (daily_backtest_summary) on Delta 5m candles with Delta fees.
Replay rules are bitunix_compare.replay_zones' (too-young, over-touched, stop too
wide, daily trend, approach side, alert window, re-arm, repeat suppression).
Writes research/out/zone_preference/.
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import bitunix_compare as bc  # research/ on PYTHONPATH
import config
import scanner

OUT = Path(__file__).resolve().parent / "out" / "zone_preference"
EVAL_DAYS = {"30m": 90, "4h": 240}
CLUSTERS = (1.0, 2.0, 3.0)        # deepest_X: % below/above the nearest entry
RANGES = (100, 300)               # discount_N: candles in the range
VARIANTS = ["nearest (live)"] + [f"deepest_{c:g}%" for c in CLUSTERS] + [f"discount_{n}" for n in RANGES]


def eligible(zones, zone_type, cur):
    return [z for z in zones
            if z["active"] and not z.get("over_touched", False)
            and not scanner.too_young_to_alert(z, cur) and not scanner.stop_too_wide(zone_type, z)]


def pick(variant, price, zones, zone_type, cur, hist):
    zone, _ = scanner.nearest_active_zone(price, zones, zone_type, cur)
    if zone is None or scanner.stop_too_wide(zone_type, zone):
        return None
    if variant.startswith("deepest_"):
        cluster = float(variant.split("_")[1].rstrip("%")) / 100
        entry = scanner.planned_entry_price(zone_type, zone)
        pool = eligible(zones, zone_type, cur)
        if zone_type == "demand":
            stack = [z for z in pool if entry * (1 - cluster) <= scanner.planned_entry_price(zone_type, z) < entry]
            return min(stack, key=lambda z: z["top"]) if stack else zone
        stack = [z for z in pool if entry < scanner.planned_entry_price(zone_type, z) <= entry * (1 + cluster)]
        return max(stack, key=lambda z: z["bottom"]) if stack else zone
    if variant.startswith("discount_"):
        n = int(variant.split("_")[1])
        tail = hist.iloc[-n:]
        lo, hi = float(tail["low"].min()), float(tail["high"].max())
        if hi <= lo:
            return zone
        where = (scanner.planned_entry_price(zone_type, zone) - lo) / (hi - lo)
        ok = where <= 0.5 if zone_type == "demand" else where >= 0.5
        return zone if ok else None
    return zone


def replay(args) -> dict[str, list[dict]]:
    """bitunix_compare.replay_zones, one zone build per bar shared by every variant."""
    symbol, tf, base, fine, daily, eval_start = args
    secs = bc.TF_SECONDS[tf]
    df = pd.DataFrame(base, columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = df["time"] * 1000
    fine_ts = [c[0] for c in fine]
    band = config.MAX_DISTANCE_PCT / 100
    rearm = band * config.REARM_FACTOR
    states = {v: {} for v in VARIANTS}
    alerts = {v: [] for v in VARIANTS}
    first = next((i for i, c in enumerate(base) if c[0] >= eval_start), len(base))
    for t in range(max(first, 200), len(base)):
        hist = df.iloc[max(0, t - config.OHLCV_LIMIT):t].reset_index(drop=True)
        supply, demand = scanner.build_zones(hist)
        open_t = float(base[t][1])
        cur = len(hist)
        lo = int(np.searchsorted(fine_ts, base[t][0]))
        hi = int(np.searchsorted(fine_ts, base[t][0] + secs))
        for zone_type, zones in (("supply", supply), ("demand", demand)):
            for variant in VARIANTS:
                zone = pick(variant, open_t, zones, zone_type, cur, hist)
                if zone is None:
                    continue
                entry = scanner.planned_entry_price(zone_type, zone)
                key = f"{zone_type}|{zone['bottom']:.10g}|{zone['top']:.10g}"
                st = states[variant].setdefault(key, {"in_zone": False, "last": -10**12})
                for k in range(lo, hi):
                    ts, o, h, l, c = fine[k][:5]
                    if zone_type == "demand":
                        if l <= zone["bottom"]:
                            break
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
                                and bc.in_window(ts) \
                                and not scanner.against_daily_trend(zone_type, bc.daily_trend_at(daily, ts)):
                            st["last"] = ts
                            record = {
                                "delivered_at_utc": pd.Timestamp(ts, unit="s", tz="UTC").isoformat(),
                                "symbol": symbol, "exchange": "bitunix", "timeframe": tf,
                                "side": "short" if zone_type == "supply" else "long", "zone_type": zone_type,
                                "distance_pct": config.MAX_DISTANCE_PCT,
                                "alert_price": entry * (1 + band if zone_type == "demand" else 1 - band),
                                "level": float(zone["top"] if zone_type == "supply" else zone["bottom"]),
                                "zone_bottom": float(zone["bottom"]), "zone_top": float(zone["top"]),
                                "body_entry": zone.get("body_entry"), "planned_entry": entry,
                                "stop_price": scanner.planned_stop_price(zone_type, zone),
                                "stop_distance_pct": scanner.planned_stop_distance_pct(zone_type, zone),
                                "score": None,
                            }
                            record["trade_id"] = scanner.delivered_alert_id(record)
                            alerts[variant].append(record)
                        st["in_zone"] = True
                    elif far:
                        st["in_zone"] = False
    return alerts


def halves(results: pd.DataFrame, mid: int) -> tuple[float, float]:
    if results.empty:
        return 0.0, 0.0
    filled = results[results["final_result"].isin(bc.FILLED) & results["filled"].fillna(False).astype(bool)]
    net = pd.to_numeric(filled["net_realized_r"], errors="coerce")
    early = filled["event_ts"] < mid
    return round(float(net[early].sum()), 1), round(float(net[~early].sum()), 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tf", choices=list(EVAL_DAYS), default="30m")
    args = parser.parse_args()
    tf = args.tf
    assert scanner.TIMEFRAME == tf, "set VICTUS_TIMEFRAME to the --tf value"
    OUT.mkdir(parents=True, exist_ok=True)
    now = int(time.time()) // 300 * 300
    eval_start = now - EVAL_DAYS[tf] * 86400
    base_start = eval_start - (config.OHLCV_LIMIT + 50) * bc.TF_SECONDS[tf]
    daily_start = eval_start - 400 * 86400

    def load(symbol):
        try:
            return symbol, {
                "base": bc.candles("bitunix", symbol, tf, base_start, now),
                "fine": bc.candles("bitunix", symbol, "5m", eval_start - 3600, now),
                "daily": bc.candles("bitunix", symbol, "1d", daily_start, now),
                "grade": bc.candles("delta", symbol, "5m", eval_start - 3600, now),
            }
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} failed: {error}")
            return symbol, None

    data = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for symbol, out in pool.map(load, bc.SYMBOLS):
            if out and out["base"] and out["grade"]:
                data[symbol] = out
                print(f"{symbol}: {len(out['base'])} {tf} / {len(out['fine'])} 5m")

    jobs = [(s, tf, d["base"], d["fine"], d["daily"], eval_start) for s, d in data.items()]
    alerts = {v: [] for v in VARIANTS}
    started = time.time()
    with ProcessPoolExecutor() as pool:
        for job, result in zip(jobs, pool.map(replay, jobs)):
            for v in VARIANTS:
                alerts[v] += result[v]
            print(f"replayed {job[0]}: " + ", ".join(f"{len(result[v])}" for v in VARIANTS)
                  + f" ({time.time() - started:.0f}s)")

    import daily_backtest_summary as dbs
    dbs.configure_crypto_data(tf)
    fine_frames = {s: dbs.normalize_crypto_frame([[c[0] * 1000, *c[1:6]] for c in d["grade"]])
                   for s, d in data.items()}
    mid = (eval_start + now) // 2
    rows = []
    for i, v in enumerate(VARIANTS):
        path = OUT / f"alerts_{tf}_{i}.jsonl"
        with path.open("w") as fh:
            for rec in sorted(alerts[v], key=lambda r: r["delivered_at_utc"]):
                fh.write(json.dumps(rec) + "\n")
        res = bc.grade(path, tf, fine_frames)
        res.to_csv(OUT / f"graded_{tf}_{i}.csv", index=False)
        first, second = halves(res, mid)
        rows.append({"variant": v, **bc.summarise(res), "net_R_1st_half": first, "net_R_2nd_half": second})
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / f"summary_{tf}.csv", index=False)
    text = [f"# Zone preference (Notion 20): {tf}", "",
            f"Last {EVAL_DAYS[tf]} days to {datetime.fromtimestamp(now, bc.IST):%Y-%m-%d %H:%M} IST; "
            f"{len(data)} crypto symbols. Alerts on Bitunix candles, graded on Delta 5m with Delta fees.", "",
            summary.to_markdown(index=False), ""]
    (OUT / f"ZONE_PREFERENCE_{tf}.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
