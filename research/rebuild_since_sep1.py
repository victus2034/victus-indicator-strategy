"""Research only - nothing here is imported by the live scanners.

Lakky (2026-10-11): "optimize the whole alerts since 1 sep so i can see the
updated data on journal". The journal reads the scanner's alert logs and
results off the runtime-state branch, and those still hold every alert as it
was sent under the rules of its day. This rebuilds every alert from
2026-09-01 (IST) to now under today's live rules:

Zones (crypto / xStock / gold-silver / NSE, 30m and 4h)
  - dropped: a crypto symbol no longer on the watchlist; price already past the
    entry before the approach-side rule went live (2026-10-02 18:12 UTC); a
    crypto zone against the daily EMA50 trend before the filter went live
    (2026-10-04 07:07 UTC, trend read off Bitunix daily candles as live); a stop
    over MAX_ALERT_STOP_PCT under today's stop.
  - re-planned: the stop is today's planned_stop_price (25% of the zone's
    height past the far edge - NSE had a fixed 0.10% until 2026-10-02).
  - re-scored: every kept alert, with the production grading
    (research/backtest_audit.py, which runs daily_backtest_summary's own code).
Fib (crypto and NSE, 4H-1M - the logs start 2026-09-29)
  - dropped: the shallow zone (Zone 1); a fib today's chart (Bitunix for crypto)
    does not draw; price outside today's alert band or already through the stop.
  - re-planned: today's fib_zones - entry at the strong zone's near edge (L1),
    S/R stop (25% of the box's height past the far edge).
Trendlines
  - dropped: a line today's trendlines (v12.7.9) do not draw at that moment, or
    price outside the band of today's line.
  - re-planned: Lakky's candle stop, one 1R target, no BE, no hold limit.
Fib and trendline results are re-scored with fib_trendline_daily_report.score.

Nothing is applied here. It writes OUT/patch.json (drop / replace per file),
OUT/SUMMARY.md (before vs after, R and % per trade) and OUT/drops.csv.
research/apply_rebuild_patch.py applies the patch to a state checkout.

    python research/rebuild_since_sep1.py --state /tmp/rt --out research/out/rebuild_sep1
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_data  # noqa: E402
import daily_backtest_summary as dbs  # noqa: E402
import fib_engine  # noqa: E402
import fib_trendline_daily_report as ftr  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from config import FIB_SWING_LENGTH, MAX_ALERT_STOP_PCT, TRENDLINE_SWING_LENGTH, TRENDLINES_KEEP  # noqa: E402
from fib_sr_logic_backtest import trend_at  # noqa: E402
from fib_trendline_data import (  # noqa: E402
    CRYPTO, IST, NSE, bitunix_candles, candle_is_closed, crypto_charts, delta_candles, nse_charts,
)
from fib_trendline_scanner import MIN_BARS, fib_distance, fib_zones, in_band, line_distance  # noqa: E402
from trendlines import SUPPORT, build_trendlines  # noqa: E402

SINCE = pd.Timestamp("2026-09-01 00:00", tz=IST).timestamp()
APPROACH_LIVE = pd.Timestamp("2026-10-02 18:12", tz="UTC").timestamp()
TREND_LIVE = pd.Timestamp("2026-10-04 07:07", tz="UTC").timestamp()
ZONE_FILES = {
    "crypto_alert_records_30m.jsonl": ("crypto", "30m"),
    "crypto_alert_records.jsonl": ("crypto", "4h"),
    "nse_alert_records_30m.jsonl": ("nse", "30m"),
    "nse_alert_records.jsonl": ("nse", "4h"),
}
FILLED = {"SL", "BE", "+1R", "+2R", "Neither"}


def read_jsonl(path):
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def num(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value == value else None


# ----------------------------------------------------------------- zones

def crypto_daily(symbols, now):
    """Daily candles the live trend filter reads: Bitunix where the symbol alerts off it, else Delta."""
    out = {}
    for symbol in symbols:
        contract = scanner.delta_contract(symbol)
        if contract is None:
            continue
        start = now - 400 * 86400
        try:
            if bitunix_data.uses_bitunix(symbol):
                out[symbol] = bitunix_candles(bitunix_data.pair_for(symbol, contract), "1d", start, now)
                continue
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} Bitunix daily failed, Delta: {error}")
        try:
            out[symbol] = delta_candles(contract, "1d", start, now)
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} daily failed: {error}")
    return out


def zone_pass(state, now):
    """-> (kept rows per file with today's stop, drop reasons per (file, trade_id), changed rows per file)."""
    watch = set(scanner.active_watchlist())
    raw = {name: read_jsonl(state / name) for name in ZONE_FILES}
    need_trend = sorted({
        r["symbol"] for name, rows in raw.items() if ZONE_FILES[name][0] == "crypto" for r in rows
        if SINCE <= pd.Timestamp(r["delivered_at_utc"]).timestamp() < TREND_LIVE
        and scanner.trend_filter_applies(r["symbol"])
    })
    daily = crypto_daily(need_trend, now)
    kept, drops, changed = defaultdict(list), {}, defaultdict(dict)
    for name, rows in raw.items():
        file_market, _tf = ZONE_FILES[name]
        for r in rows:
            ts = pd.Timestamp(r["delivered_at_utc"]).timestamp()
            if ts < SINCE:
                continue
            tid = r.get("trade_id")
            side = r.get("side")
            zone_type = "demand" if side == "long" else "supply"
            top, bottom, entry, price = num(r.get("zone_top")), num(r.get("zone_bottom")), num(
                r.get("planned_entry")), num(r.get("alert_price"))
            reason = None
            if None in (top, bottom, entry, price) or not tid:
                kept[name].append(r)        # nothing to judge it by: left as sent
                continue
            stop = scanner.planned_stop_price(zone_type, {"top": top, "bottom": bottom})
            stop_pct = abs(entry - stop) / entry * 100
            if file_market == "crypto" and r["symbol"] not in watch:
                reason = "not on today's watchlist"
            elif ts < APPROACH_LIVE and (price < entry if side == "long" else price > entry):
                reason = "price already past the entry"
            elif (file_market == "crypto" and ts < TREND_LIVE and scanner.trend_filter_applies(r["symbol"])
                  and scanner.against_daily_trend(zone_type, trend_at(daily.get(r["symbol"]), ts))):
                reason = "against the daily EMA50 trend"
            elif MAX_ALERT_STOP_PCT > 0 and stop_pct > MAX_ALERT_STOP_PCT:
                reason = f"stop over {MAX_ALERT_STOP_PCT:g}%"
            if reason:
                drops[(name, tid)] = reason
                continue
            old = num(r.get("stop_price"))
            if old is None or abs(old - stop) > 1e-9 * max(1.0, abs(stop)):
                r = {**r, "stop_price": stop, "stop_distance_pct": stop_pct}
                changed[name][tid] = r
            kept[name].append(r)
    return kept, drops, changed


def stored_id_map(state, stored):
    """Alert-log trade_id -> finalized trade_id, as backtest_audit joins them."""
    by_key = {(r.get("zone_id"), str(r.get("alert_time"))[:26]): r["trade_id"] for r in stored.values()}
    out = {}
    for name, (_m, tf) in ZONE_FILES.items():
        frame = dbs.load_records(state / name, tf)
        if frame.empty:
            continue
        for tid, zid, when in zip(frame["trade_id"], frame["zone_id"], frame["event_time_ist"]):
            sid = by_key.get((zid, when.isoformat()[:26]), tid)
            if sid in stored:
                out[(name, str(tid))] = sid
    return out


def rescore_zones(kept, stored, work):
    """Run the production re-grade (backtest_audit) on the kept alerts -> {trade_id: payload}."""
    import backtest_audit

    alerts_dir = work / "alerts"
    alerts_dir.mkdir(parents=True, exist_ok=True)
    for name in ZONE_FILES:
        with (alerts_dir / name).open("w", encoding="utf-8") as fh:
            for r in kept.get(name, []):
                fh.write(json.dumps(r) + "\n")
    records = work / "finalized.jsonl"
    with records.open("w", encoding="utf-8") as fh:
        for r in stored.values():
            fh.write(json.dumps(r) + "\n")
    out = work / "audit"
    argv = sys.argv
    sys.argv = ["backtest_audit.py", "--records", str(records), "--alerts-dir", str(alerts_dir), "--out", str(out)]
    try:
        backtest_audit.main()
    finally:
        sys.argv = argv
    return {r["trade_id"]: r for r in read_jsonl(out / "rescored_finalized.jsonl")}


def zone_stats(rows):
    """[(class, tf) -> dict] from finalized rows: alerts, trades, wins, net R, % per trade."""
    groups = defaultdict(lambda: defaultdict(float))
    for r in rows:
        key = (r.get("market"), r.get("timeframe"))
        g = groups[key]
        g["alerts"] += 1
        res = r.get("final_result") if r.get("filled") else r.get("outcome")
        net = num(r.get("net_realized_r"))
        if res not in FILLED or net is None:
            continue
        entry, stop = num(r.get("entry_price")) or num(r.get("planned_entry")), num(r.get("stop_price"))
        risk = abs(entry - stop) / entry * 100 if entry and stop else 0.0
        g["trades"] += 1
        g["wins"] += net > 0.05
        g["net_r"] += net
        g["net_pct"] += net * risk
    return groups


# ----------------------------------------------------------------- fib / trendline

def closed_upto(market, candles, tf, ts):
    return [c for c in candles if candle_is_closed(market, c[0], tf, ts)]


def fetch_charts(records, now):
    """{(market, symbol): {tf: candles}} from today's live sources (Bitunix for crypto, Yahoo for NSE)."""
    tfs = defaultdict(set)
    for r in records:
        tfs[(r["market"], r["symbol"])].add(r["tf"])
    charts = {}
    for (market, symbol), want in sorted(tfs.items()):
        if market != CRYPTO:
            continue
        contract = scanner.delta_contract(symbol)
        if contract is None:
            continue
        source = "bitunix" if bitunix_data.uses_bitunix(symbol) else "delta"
        pair = bitunix_data.pair_for(symbol, contract) if source == "bitunix" else None
        try:
            charts[(market, symbol)] = crypto_charts(pair or contract, sorted(want), now, source=source)
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} charts failed: {error}")
    nse = sorted({s for m, s in tfs if m == NSE})
    if nse:
        want = sorted({tf for (m, _s), v in tfs.items() if m == NSE for tf in v})
        for symbol, by_tf in nse_charts(nse, want).items():
            charts[(NSE, symbol)] = by_tf
    return charts


def fib_tl_pass(state, now):
    records = read_jsonl(state / "fib_trendline_alert_records.jsonl")
    results = {}
    path = state / "fib_trendline_results.json"
    if path.exists():
        results = json.loads(path.read_text(encoding="utf-8"))
    records = [r for r in records if r.get("sent_ts", 0) >= SINCE]
    charts = fetch_charts(records, now)
    kept, drops = [], {}
    cache = {}
    for r in records:
        market, symbol, tf, ts, price = r["market"], r["symbol"], r["tf"], r["sent_ts"], num(r.get("price"))
        candles = charts.get((market, symbol), {}).get(tf)
        if not candles:
            drops[r["id"]] = "no candles today"
            continue
        ck = (market, symbol, tf, ts)
        closed = closed_upto(market, candles, tf, ts)
        if len(closed) < MIN_BARS:
            drops[r["id"]] = "too little history"
            continue
        times = [c[0] for c in closed]
        opens, highs, lows, closes = ([c[i] for c in closed] for i in (1, 2, 3, 4))
        if r["kind"] == "fib":
            if r.get("zone") != 2:
                drops[r["id"]] = "shallow fib zone (Zone 1)"
                continue
            stamp = [datetime.fromtimestamp(t, IST).strftime("%Y-%m-%d %H:%M") for t in times]
            snaps, _ = fib_engine.run(stamp, highs, lows, N=FIB_SWING_LENGTH)
            live = snaps[-1]
            d, base, top = live["d"], live["O"], live["E"]
            _f, _s, _t, kd, kbase_t, ktop, _z = r["key"].split("|")
            if int(kd) != d or float(kbase_t) != float(times[live["Ot"]]) or abs(top - float(ktop)) > 0.01 * abs(float(ktop)):
                drops[r["id"]] = "fib not on today's chart"
                continue
            zone = next(z for z in fib_zones(d, base, top) if z["zone"] == 2)
            if price is None or not in_band(fib_distance(d, zone, price)):
                drops[r["id"]] = "outside today's fib band / through the stop"
                continue
            kept.append({**r, "plan": trades.fib_plan(d, zone)})
        else:
            if ck not in cache:
                cache[ck] = build_trendlines(highs, lows, closes, TRENDLINE_SWING_LENGTH, TRENDLINES_KEEP)
            key = r["key"]
            line = next((x for x in cache[ck] if x.alive
                         and f"tl|{symbol}|{tf}|{x.kind}|{times[x.x1]}|{times[x.x2]}" == key), None)
            if line is None:
                drops[r["id"]] = "line not drawn by today's trendlines"
                continue
            now_bar = len(closed)
            level = line.price_at(now_bar)
            if level <= 0 or price is None or not in_band(line_distance(line.kind, level, price)):
                drops[r["id"]] = "outside today's line band"
                continue
            plan = trades.trendline_plan(line.kind == SUPPORT, level, tf, now_bar, opens, highs, lows, closes)
            kept.append({**r, "plan": plan})
    new_results = ftr.score(kept, {}, now)
    return records, results, kept, drops, new_results


def booked(record, result):
    if not result or not result.get("filled"):
        return None
    at1, at2 = trades.booked_r(record["plan"], record["market"], result)
    value = at1 if record["kind"] == "trendline" else at2
    return value


def fib_tl_stats(pairs):
    groups = defaultdict(lambda: defaultdict(float))
    for record, result in pairs:
        band = "4H" if record["tf"] in ("30m", "4h") else "1D+"
        g = groups[(record["kind"], record["market"].upper(), band)]
        g["alerts"] += 1
        net = booked(record, result)
        if net is None:
            continue
        g["trades"] += 1
        g["wins"] += net > 0.05
        g["net_r"] += net
        g["net_pct"] += net * trades.risk_pct(record["plan"])
    return groups


# ----------------------------------------------------------------- report

def table(title, before, after, key_names):
    lines = [f"## {title}", "",
             "| " + " | ".join(key_names) + " | Alerts before | Alerts after | Trades before | Trades after | "
             "Win % before | Win % after | R/trade before | R/trade after | %/trade before | %/trade after | "
             "Total R before | Total R after | Total % before | Total % after |",
             "|" + "---|" * (len(key_names) + 14)]
    tot = {"b": defaultdict(float), "a": defaultdict(float)}
    for key in sorted(set(before) | set(after), key=str):
        b, a = before.get(key, {}), after.get(key, {})
        for side, g in (("b", b), ("a", a)):
            for k in ("alerts", "trades", "wins", "net_r", "net_pct"):
                tot[side][k] += g.get(k, 0)
        lines.append(row(key, b, a))
    lines.append(row(("**All**",) + ("",) * (len(key_names) - 1), tot["b"], tot["a"]))
    return lines + [""]


def row(key, b, a):
    def per(g, k):
        return f"{g.get(k, 0) / g['trades']:+.2f}" if g.get("trades") else "-"

    def win(g):
        return f"{100 * g.get('wins', 0) / g['trades']:.0f}%" if g.get("trades") else "-"

    return ("| " + " | ".join(str(k) for k in key) + " | "
            f"{int(b.get('alerts', 0))} | {int(a.get('alerts', 0))} | {int(b.get('trades', 0))} | {int(a.get('trades', 0))} | "
            f"{win(b)} | {win(a)} | {per(b, 'net_r')} | {per(a, 'net_r')} | {per(b, 'net_pct')}% | {per(a, 'net_pct')}% | "
            f"{b.get('net_r', 0):+.1f} | {a.get('net_r', 0):+.1f} | {b.get('net_pct', 0):+.1f}% | {a.get('net_pct', 0):+.1f}% |")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, help="a checkout of scanner-runtime-state")
    parser.add_argument("--out", default="research/out/rebuild_sep1")
    args = parser.parse_args()
    state, out = Path(args.state), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    work = Path("/tmp/rebuild_sep1")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    now = time.time()
    patch = {"generated_at": datetime.now(IST).isoformat(), "since": "2026-09-01 IST",
             "zone_logs": {}, "finalized": {"drop": [], "replace": {}},
             "fibtl_records": {"drop": [], "replace": {}}, "fibtl_results": {"drop": [], "set": {}}}
    drop_rows = []

    # zones
    kept, zdrops, changed = zone_pass(state, now)
    stored = {r["trade_id"]: r for r in read_jsonl(state / "daily_backtest_finalized_records.jsonl")}
    ids = stored_id_map(state, stored)
    for name in ZONE_FILES:
        patch["zone_logs"][name] = {"drop": sorted(tid for (n, tid) in zdrops if n == name),
                                    "replace": changed.get(name, {})}
    dropped_stored = {ids[k] for k in zdrops if k in ids}
    for (name, tid), reason in zdrops.items():
        drop_rows.append({"kind": "zone", "file": name, "id": tid, "reason": reason})
    rescored = rescore_zones(kept, stored, work)
    patch["finalized"]["drop"] = sorted(dropped_stored)
    patch["finalized"]["replace"] = {tid: r for tid, r in rescored.items() if tid not in dropped_stored}
    since_rows = [r for r in stored.values() if pd.Timestamp(r["alert_time"]).timestamp() >= SINCE]
    after_rows = [patch["finalized"]["replace"].get(r["trade_id"], r) for r in since_rows
                  if r["trade_id"] not in dropped_stored]
    zb, za = zone_stats(since_rows), zone_stats(after_rows)

    # fib / trendline
    records, results, fkept, fdrops, new_results = fib_tl_pass(state, now)
    kept_ids = {r["id"] for r in fkept}
    patch["fibtl_records"]["drop"] = sorted(fdrops)
    patch["fibtl_records"]["replace"] = {r["id"]: r for r in fkept}
    patch["fibtl_results"]["drop"] = sorted(i for i in fdrops if i in results)
    patch["fibtl_results"]["set"] = {i: x for i, x in new_results.items() if i in kept_ids}
    for i, reason in fdrops.items():
        drop_rows.append({"kind": i.split("|")[0], "file": "fib_trendline_alert_records.jsonl", "id": i,
                          "reason": reason})
    fb = fib_tl_stats([(r, results.get(r["id"])) for r in records])
    fa = fib_tl_stats([(r, new_results.get(r["id"])) for r in fkept])

    (out / "patch.json").write_text(json.dumps(patch, indent=0, sort_keys=True, default=str), encoding="utf-8")
    with (out / "drops.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["kind", "file", "id", "reason"])
        writer.writeheader()
        writer.writerows(drop_rows)

    reasons = Counter((d["kind"] if d["kind"] != "tl" else "trendline", d["reason"]) for d in drop_rows)
    md = ["# Alerts since 2026-09-01 rebuilt under today's rules", "",
          f"Generated {datetime.now(IST):%Y-%m-%d %H:%M} IST by `research/rebuild_since_sep1.py`. "
          "R is net of costs; % per trade = net R x the trade's stop %.", "",
          "## Dropped alerts", "", "| Kind | Reason | Alerts |", "|---|---|---|"]
    md += [f"| {k} | {why} | {n} |" for (k, why), n in sorted(reasons.items())]
    md += ["", f"Zone stops re-planned (kept alerts): {sum(len(v) for v in changed.values())}. "
           f"Zone finalized rows re-scored: {len(patch['finalized']['replace'])}, dropped: {len(dropped_stored)}.", ""]
    md += table("Zones (finalized trades)", zb, za, ["Market", "TF"])
    md += table("Fib and trendline (4H vs 1D and above)", fb, fa, ["Kind", "Market", "TF"])
    (out / "SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
