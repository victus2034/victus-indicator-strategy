"""Research only - nothing here is imported by the live scanners.

Lakky (2026-10-10, "okay do it"): the longer test of S/R zone alerts traded with
a fixed 1.5% stop and a 3% or 4% target, with the trend only (daily EMA50 on
every market), against today's live rules.

  alerts  - replayed, not read from the live records, so the window can start
            before the records do: bitunix_compare.replay_zones' rules (nearest
            zone, too-young, stop too wide, approach side, alert window, re-arm,
            repeat suppression), run twice - every alert, and trend only.
            Crypto and xStocks on Bitunix candles, XAUT/SLVON on Delta (as live);
            NSE on Yahoo (30m: Yahoo keeps 60 days, so ~3 weeks after the
            500-candle lookback; 4h: built from 1h at 09:15).
  grading - the production scorer (daily_backtest_summary.simulate_alerts): fill
            at the planned entry, 6h after entry for crypto/xStock/other, same day
            to 15:10 for NSE, +0.5R breakeven, fees and stop slip. The fixed rules
            only swap the stop for entry -/+ 1.5% and the 2R target for 3% or 4%.
            Crypto graded on Delta 5m, NSE 30m on Yahoo 5m, NSE 4h on Yahoo 1h.
  live    - today's stop and 2R target; trend filter on crypto only.

    VICTUS_TIMEFRAME=30m python research/fixed_pct_zone_replay.py --tf 30m --since 2026-06-01
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_compare as bc  # noqa: E402
import config  # noqa: E402
import daily_backtest_summary as dbs  # noqa: E402
import scanner  # noqa: E402
from daily_backtest_summary import market_class  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fixed_pct_zones"
SL_PCT = 1.5
TARGETS = (3.0, 4.0)
CLASSES = ("CRYPTO", "XSTOCK", "OTHER", "NSE")
NSE_OPEN, NSE_CLOSE = (9, 15), (15, 30)


def in_window(cls, ts):
    if cls != "NSE":
        return bc.in_window(ts)
    t = datetime.fromtimestamp(ts, bc.IST)
    return NSE_OPEN <= (t.hour, t.minute) <= NSE_CLOSE


def replay(args):
    """{"all": alerts, "trend": alerts}: one zone build per bar, two alert states."""
    symbol, cls, tf, base, fine, daily, eval_start, lookback = args
    secs = bc.TF_SECONDS[tf]
    df = pd.DataFrame([c[:5] + [c[5] if len(c) > 5 else 0.0] for c in base],
                      columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = df["time"] * 1000
    fine_ts = [c[0] for c in fine]
    band = config.MAX_DISTANCE_PCT / 100
    rearm = band * config.REARM_FACTOR
    states = {"all": {}, "trend": {}}
    alerts = {"all": [], "trend": []}
    first = next((i for i, c in enumerate(base) if c[0] >= eval_start), len(base))
    for t in range(max(first, 200), len(base)):
        hist = df.iloc[max(0, t - lookback):t].reset_index(drop=True)
        supply, demand = scanner.build_zones(hist)
        open_t = float(base[t][1])
        cur = len(hist)
        lo = int(np.searchsorted(fine_ts, base[t][0]))
        hi = int(np.searchsorted(fine_ts, base[t][0] + secs))
        for zone_type, zones in (("supply", supply), ("demand", demand)):
            zone, _ = scanner.nearest_active_zone(open_t, zones, zone_type, cur)
            if zone is None or scanner.stop_too_wide(zone_type, zone):
                continue
            entry = scanner.planned_entry_price(zone_type, zone)
            key = f"{zone_type}|{zone['bottom']:.10g}|{zone['top']:.10g}"
            for variant in states:
                st = states[variant].setdefault(key, {"in_zone": False, "last": -10**12})
                for k in range(lo, hi):
                    ts, o, h, l, c = fine[k][:5]
                    if zone_type == "demand":
                        if l <= zone["bottom"]:
                            break
                        touched, past, far = l <= entry * (1 + band), o < entry, (c - entry) / c > rearm
                    else:
                        if h >= zone["top"]:
                            break
                        touched, past, far = h >= entry * (1 - band), o > entry, (entry - c) / c > rearm
                    if touched:
                        due = (not st["in_zone"]) or ts - st["last"] >= config.ALERT_COOLDOWN_SECONDS
                        blocked = variant == "trend" and scanner.against_daily_trend(
                            zone_type, bc.daily_trend_at(daily, ts))
                        if due and not past and ts - st["last"] >= scanner.ZONE_REPEAT_SUPPRESSION_SECONDS \
                                and in_window(cls, ts) and not blocked:
                            st["last"] = ts
                            record = {
                                "delivered_at_utc": pd.Timestamp(ts, unit="s", tz="UTC").isoformat(),
                                "symbol": symbol, "timeframe": tf,
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
    return symbol, alerts


def fixed(record):
    sign = 1 if record["side"] == "long" else -1
    entry = record["planned_entry"]
    return {**record, "stop_price": entry * (1 - sign * SL_PCT / 100), "stop_distance_pct": SL_PCT}


def score(records, frames, cls, tf, target_r=2.0, breakeven=True):
    """Production scorer on these records; returns per-trade (net R, net %, outcome)."""
    path = OUT / f"_tmp_{cls}_{tf}.jsonl"
    with path.open("w") as fh:
        for rec in sorted(records, key=lambda r: r["delivered_at_utc"]):
            fh.write(json.dumps(rec) + "\n")
    alerts = dbs.load_records(path, tf)
    path.unlink()
    if alerts.empty:
        return []
    market = "nse" if cls == "NSE" else "crypto"
    # The target sits at TARGET_2_R and a "+2R" exit is booked at FINAL_RESULT_R["+2R"].
    saved = dbs.TARGET_2_R, dbs.BREAK_EVEN_ENABLED, dbs.FINAL_RESULT_R["+2R"]
    dbs.TARGET_2_R, dbs.BREAK_EVEN_ENABLED, dbs.FINAL_RESULT_R["+2R"] = target_r, breakeven, target_r
    try:
        rows = dbs.simulate_alerts(alerts, frames, market)
    finally:
        dbs.TARGET_2_R, dbs.BREAK_EVEN_ENABLED, dbs.FINAL_RESULT_R["+2R"] = saved
    results, _ = dbs.apply_same_day_zone_cooldown(pd.DataFrame(rows), market)
    results = results.reset_index(drop=True)
    risk = alerts["stop_distance_pct"].values
    out = []
    for i, row in results.iterrows():
        res = row.get("final_result")
        if not row.get("filled") or res not in bc.FILLED:
            continue
        r = pd.to_numeric(row.get("net_realized_r"), errors="coerce")
        if pd.notna(r):
            out.append((float(r), float(r) * float(risk[i]), res))
    return out


def summary(items):
    if not items:
        return {"trades": 0}
    rs = [r for r, _, _ in items]
    outs = pd.Series([o for _, _, o in items]).value_counts().to_dict()
    target = outs.get("+2R", 0)
    return {"trades": len(rs), "target_hit": target, "SL": outs.get("SL", 0), "BE": outs.get("BE", 0),
            "time_exit": outs.get("+1R", 0) + outs.get("Neither", 0),
            "target_%": round(100 * target / len(rs)), "net_R": round(sum(rs), 1),
            "R_per_trade": round(sum(rs) / len(rs), 3),
            "net_%_per_trade": round(sum(p for _, p, _ in items) / len(rs), 3)}


def load_crypto(symbols, tf, eval_start, now):
    base_start = eval_start - (config.OHLCV_LIMIT + 50) * bc.TF_SECONDS[tf]

    def one(symbol):
        cls = market_class(symbol)
        src = "delta" if cls == "OTHER" else "bitunix"
        try:
            return symbol, cls, {
                "base": bc.candles(src, symbol, tf, base_start, now),
                "fine": bc.candles(src, symbol, "5m", eval_start - 3600, now),
                "daily": bc.candles(src, symbol, "1d", eval_start - 400 * 86400, now),
                "grade": bc.candles("delta", symbol, "5m", eval_start - 3600, now),
            }
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} failed: {error}")
            return symbol, cls, None
    out = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for symbol, cls, d in pool.map(one, symbols):
            if d and d["base"] and d["grade"]:
                d["frame"] = dbs.normalize_crypto_frame([[c[0] * 1000, *c[1:6]] for c in d["grade"]])
                out[symbol] = (cls, d)
                print(f"{symbol}: {len(d['base'])} {tf} / {len(d['fine'])} 5m / {len(d['grade'])} grade")
    return out


def load_nse(tf):
    import nse_scanner
    from fib_trendline_data import nse_download
    symbols = nse_scanner.load_watchlist()
    fine_res = "5m" if tf == "30m" else "1h"
    base, fine, daily = nse_download(symbols, tf), nse_download(symbols, fine_res), nse_download(symbols, "1d")
    out = {}
    for s in symbols:
        if base.get(s) and fine.get(s):
            frame = pd.DataFrame([c[1:5] for c in fine[s]], columns=["open", "high", "low", "close"])
            frame.index = pd.DatetimeIndex(pd.to_datetime([c[0] for c in fine[s]], unit="s", utc=True)).tz_convert(bc.IST)
            frame["volume"] = 0.0
            out[s] = ("NSE", {"base": base[s], "fine": fine[s], "daily": daily.get(s, []), "frame": frame})
    print(f"NSE: {len(out)} of {len(symbols)} stocks, {tf} base, {fine_res} fine")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tf", choices=["30m", "4h"], required=True)
    parser.add_argument("--since", default="2026-06-01")
    args = parser.parse_args()
    tf = args.tf
    assert scanner.TIMEFRAME == tf, "set VICTUS_TIMEFRAME to the --tf value"
    OUT.mkdir(parents=True, exist_ok=True)
    now = int(time.time()) // 300 * 300
    eval_start = int(pd.Timestamp(args.since, tz=bc.IST).timestamp())
    data = load_crypto(list(config.WATCHLIST), tf, eval_start, now)
    try:
        data.update(load_nse(tf))
    except Exception as error:  # noqa: BLE001
        print(f"NSE load failed: {error}")
    import nse_config
    jobs = [(s, cls, tf, d["base"], d["fine"], d["daily"], eval_start,
             nse_config.OHLCV_LIMIT if cls == "NSE" else config.OHLCV_LIMIT) for s, (cls, d) in data.items()]
    alerts = {(cls, v): [] for cls in CLASSES for v in ("all", "trend")}
    started = time.time()
    with ProcessPoolExecutor() as pool:
        for symbol, result in pool.map(replay, jobs, chunksize=4):
            cls = data[symbol][0]
            for v in result:
                alerts[(cls, v)] += result[v]
            print(f"replayed {symbol}: {len(result['all'])} / {len(result['trend'])} ({time.time() - started:.0f}s)")

    dbs.configure_crypto_data(tf)    # after the replay: it points scanner.TIMEFRAME at 5m
    rows = []
    for cls in CLASSES:
        frames = {s: d["frame"] for s, (c, d) in data.items() if c == cls}
        if not frames:
            continue
        live = alerts[(cls, "trend" if cls == "CRYPTO" else "all")]
        trend = alerts[(cls, "trend")]
        first = min((r["delivered_at_utc"] for r in alerts[(cls, "all")]), default="-")[:10]
        variants = [("live rules (as today)", live, 2.0, True),
                    ("live rules, trend only", trend, 2.0, True)]
        fixed_trend = [fixed(r) for r in trend]
        for target in TARGETS:
            for be in (False, True):
                variants.append((f"SL 1.5% / TP {target:g}%{' + BE' if be else ''}, trend only",
                                 fixed_trend, target / SL_PCT, be))
        for label, recs, target_r, be in variants:
            rows.append({"market": cls, "tf": tf, "from": first, "rule": label,
                         **summary(score(recs, frames, cls, tf, target_r, be))})
            print(rows[-1])
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"summary_{tf}.csv", index=False)
    text = [f"# Zones, fixed 1.5% stop / 3-4% target, trend only: {tf}, {args.since} to "
            f"{datetime.fromtimestamp(now, bc.IST):%Y-%m-%d}", "",
            "Alerts replayed with the live zone rules. Graded by the production scorer (6h after entry for "
            "crypto/xStock/other, same day to 15:10 for NSE; fees, stop slip). 'BE' = +0.5R moves the stop "
            "past entry. Net R in each rule's own R (fixed: 1R = 1.5%); net_%_per_trade = net R x stop % - "
            "compare that column across rules. 'from' = first alert (NSE 30m: Yahoo keeps 60 days).", "",
            df.to_markdown(index=False), ""]
    (OUT / f"FIXED_PCT_ZONES_{tf}.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
