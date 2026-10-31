"""Rebuild the S/R zone backtest under today's live rules (lakky, 2026-10-27).

lakky: "Remove all the 30m support and resistance backtest data and make new
backtest data up to date with new rules". The journal's Zone alerts tab read
the scanner's stored alerts, graded under the rules of their day - 30m zones
(off since 2026-10-16), coins since dropped, old stops and filters. This
replays every zone alert today's scanner would have sent, Sep 1 to now, on
today's watchlists:

  4H     the live zone engine on Bitunix (crypto, xStocks) / Delta (XAUT,
         SLVON) / Yahoo (NSE) 4H charts (research/zone_htf_backtest.replay:
         nearest zone, too young, over-touched, stop cap, approach side, 0.20%
         band + re-arm, 4h cooldown, crypto 01:00-08:00 IST hold, crypto daily
         EMA50 filter, 25% stop). Each alert is written as a live alert record
         and graded by the daily zone report's own code (daily_backtest_summary:
         Delta 5m crypto, Yahoo 5m NSE, fees, BE, repeat cooldown), so a row
         reads exactly like daily_backtest_finalized_records.jsonl.
  1D/1W/1M  the same replay, scored the way the live 1D+ zone alerts are
         (fib_trendline_trades.simulate: 5 candles to fill, 20 to hold, 2R +
         BE, fees); 1W/1M from the live 3% band. Written like
         fib_trendline_alert_records.jsonl + fib_trendline_results.json.

Backtest standard (lakky, 2026-10-17): a trade whose entry fills within 15 min
of a US CPI / PPI / FOMC release is left out (4H on the 5m fill, 1D+ on the
fill candle).

Nothing live is touched. Writes OUT:
  zone_rebuild_4h.jsonl          finalized-format rows (4H)
  zone_rebuild_htf.jsonl         alert records (1D/1W/1M)
  zone_rebuild_htf_results.json  their results
  zone_rebuild_meta.json         since / cutoff / counts - the journal reads this
  SUMMARY.md                     R and % per trade, 4H vs 1D / 1W / 1M
With --apply the workflow copies the four data files to scanner-runtime-state
(new files; no live file is changed).

    PYTHONPATH=research python research/zone_rebuild.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import backtest_audit as ba  # noqa: E402
import bitunix_data  # noqa: E402
import config  # noqa: E402
import daily_backtest_summary as dbs  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
import zone_htf_backtest as zh  # noqa: E402
from fib_trendline_data import CRYPTO, HISTORY_START, IST, NSE, TF_SECONDS, bitunix_candles, delta_candles, monthly_from_daily  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "zone_rebuild"
HTF = ("1d", "1w", "1M")
FILLED = {"SL", "BE", "+1R", "+2R", "Neither"}

# US CPI / PPI 08:30 and FOMC 14:00, New York time (BLS and Fed calendars;
# the same list as research/news_window_backtest.py, PR #54).
NEWS_MIN = 15
CPI = ["2026-08-12", "2026-09-11", "2026-10-14", "2026-11-10", "2026-12-10"]
PPI = ["2026-08-13", "2026-09-10", "2026-10-15", "2026-11-13", "2026-12-15"]
FOMC = ["2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]
NEWS_TS = sorted([int(pd.Timestamp(f"{d} 08:30", tz="America/New_York").timestamp()) for d in CPI + PPI]
                 + [int(pd.Timestamp(f"{d} 14:00", tz="America/New_York").timestamp()) for d in FOMC])


def news_overlap(start: float, end: float) -> bool:
    """True when [start, end) touches a release +-15 min."""
    return any(start <= ev + NEWS_MIN * 60 and end > ev - NEWS_MIN * 60 for ev in NEWS_TS)


def num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def jsonable(v):
    if hasattr(v, "item") and not isinstance(v, (list, dict, str)):
        v = v.item()                       # numpy scalars
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


# ----------------------------------------------------------------- replay

def crypto_load(symbol, now, since):
    """zone_htf_backtest.crypto_load, with Delta for the symbols that alert off Delta (XAUT, SLVON)."""
    if bitunix_data.uses_bitunix(symbol):
        return zh.crypto_load(symbol, now, since)
    contract = scanner.delta_contract(symbol)
    if contract is None:
        return None

    def get(res, start):
        return fbt._cached(f"zr_{contract}_{res}_{int(start) // 86400}", lambda: delta_candles(contract, res, start, now))

    daily = get("1d", HISTORY_START)
    base = {"4h": get("4h", since - (config.OHLCV_LIMIT + 50) * TF_SECONDS["4h"]),
            "1d": daily, "1w": get("1w", HISTORY_START), "1M": monthly_from_daily(daily)}
    evals = {"1d": daily, "4h": get("4h", since - 2 * 86400), "1h": get("1h", since - 2 * 86400)}
    return base, evals, daily


def replay_all(since, now, limit):
    got = []
    started = time.time()
    crypto = list(config.WATCHLIST)[: limit or None]

    def one(symbol):
        try:
            data = crypto_load(symbol, now, since)
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            return []
        if not data:
            print(f"crypto {symbol}: no chart")
            return []
        base, evals, daily = data
        res = []
        for tf in zh.TIMEFRAMES:
            res += zh.replay(CRYPTO, symbol, tf, base[tf], evals[trades.EVAL_RESOLUTION[CRYPTO][tf]], daily, since, now)
        print(f"crypto {symbol}: {len(res)} alerts ({time.time() - started:.0f}s)")
        return res

    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(one, crypto):
            got += res

    import nse_scanner
    symbols = nse_scanner.load_watchlist()[: limit or None]
    fbt.TIMEFRAMES = zh.TIMEFRAMES
    for symbol, (base, evals) in fbt.nse_data(symbols).items():
        for tf in zh.TIMEFRAMES:
            got += zh.replay(NSE, symbol, tf, base.get(tf, []), evals.get(trades.EVAL_RESOLUTION[NSE][tf], []),
                             None, since, now)
    print(f"replay done: {len(got)} alerts ({time.time() - started:.0f}s)")
    return got


# ----------------------------------------------------------------- 4H: graded by the zone report's code

def refine_alert_time(t, frame):
    """The 5m candle inside the replay's eval candle where price first came within the band."""
    if frame is None or frame.empty:
        return t["alert_ts"]
    entry, band = t["plan"]["entry"], t["band"]
    start = pd.Timestamp(t["alert_ts"], unit="s", tz="UTC").tz_convert(IST)
    end = start + pd.Timedelta(seconds=t["eval_secs"])
    part = frame[(frame.index >= start) & (frame.index < end)]
    for ts, c in part.iterrows():
        if (t["plan"]["side"] == "long" and c["low"] <= entry * (1 + band)) or \
                (t["plan"]["side"] == "short" and c["high"] >= entry * (1 - band)):
            return int(ts.timestamp())
    return t["alert_ts"]


def alert_record(t, when):
    entry, stop = t["plan"]["entry"], t["plan"]["sl"]
    side = t["plan"]["side"]
    level = t["zone"]["top"] if side == "short" else t["zone"]["bottom"]
    return {
        "delivered_at_utc": datetime.fromtimestamp(when, timezone.utc).isoformat(),
        "symbol": t["symbol"], "timeframe": "4h", "side": side, "zone_type": t["zone"]["type"],
        "distance_pct": abs(t["price"] - entry) / entry * 100, "alert_price": t["price"], "level": level,
        "zone_bottom": t["zone"]["bottom"], "zone_top": t["zone"]["top"], "body_entry": entry,
        "planned_entry": entry, "stop_price": stop, "stop_distance_pct": abs(entry - stop) / entry * 100,
        "rebuild": True,
    }


def grade_4h(alerts4, now):
    """-> finalized-format rows for every 4H replay alert, by market class."""
    rows_out = []
    by_market = {"crypto": [], "nse": []}
    for t in alerts4:
        by_market["nse" if t["market"] == NSE else "crypto"].append(t)
    for file_market, items in by_market.items():
        if not items:
            continue
        symbols = sorted({t["symbol"] for t in items})
        start = min(t["alert_ts"] for t in items) - 3 * 3600
        if file_market == "crypto":
            dbs.configure_crypto_data("4h")
        frames = ba.fetch_frames("nse" if file_market == "nse" else "crypto", symbols, start, now)
        recs = [alert_record(t, refine_alert_time(t, frames.get(t["symbol"]))) for t in items]
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            for r in sorted(recs, key=lambda r: r["delivered_at_utc"]):
                fh.write(json.dumps(r) + "\n")
            path = Path(fh.name)
        alerts = dbs.load_records(path, "4h")
        if alerts.empty:
            continue
        for market in ba.MARKETS_IN_FILE[file_market]:
            sub = alerts[alerts["market_class"] == market.upper()].copy().reset_index(drop=True)
            if sub.empty:
                continue
            sub = dbs.assign_report_dates(sub, market)
            res = dbs.simulate_alerts(sub, frames, market)
            amb = pd.DataFrame([r for r in res if r.get("final_result") == dbs.DATA_QUALITY_AMBIGUOUS])
            if not amb.empty:
                fine, _ = dbs.fetch_resolution_frames(sorted(amb["symbol"].unique()), market,
                                                       windows=dbs.resolution_windows(amb))
                res = dbs.rerun_ambiguous(sub, res, frames, market, fine)
            results, _ = dbs.apply_same_day_zone_cooldown(pd.DataFrame(res), market)
            for alert, row in zip(sub.to_dict("records"), results.to_dict("records")):
                row.setdefault("report_date", alert.get("report_date"))
                payload = dbs.lifecycle_payload(row, alert.get("report_date"), "4h", market)
                payload = {k: jsonable(v) for k, v in payload.items()}
                payload["rebuild"] = True
                entry_time = pd.Timestamp(payload["entry_time"]).timestamp() if payload.get("entry_time") else None
                payload["news_window"] = bool(payload.get("filled") and entry_time is not None
                                              and news_overlap(entry_time, entry_time + 300))
                rows_out.append(payload)
            print(f"4h {market}: {len(sub)} alerts graded")
    return rows_out


# ----------------------------------------------------------------- 1D / 1W / 1M: scored like the live 1D+ zones

def htf_records(alerts_htf):
    recs, results = [], {}
    for t in alerts_htf:
        z = t["zone"]
        key = f"zone|{t['symbol']}|{t['tf']}|{z['type']}|{z['bottom']:.10g}|{z['top']:.10g}"
        rid = f"{key}@{int(t['alert_ts'])}|rb"
        res = dict(t["result"])
        if res.get("filled") and res.get("fill_ts") is not None:
            secs = TF_SECONDS[trades.EVAL_RESOLUTION[t["market"]][t["tf"]]]
            res["news_window"] = news_overlap(res["fill_ts"], res["fill_ts"] + secs)
        recs.append({"market": t["market"], "symbol": t["symbol"], "tf": t["tf"], "price": t["price"], "kind": "zone",
                     "plan": t["plan"], "zone_type": z["type"], "zone_bottom": z["bottom"], "zone_top": z["top"],
                     "id": rid, "key": key, "sent_ts": int(t["alert_ts"]), "rebuild": True})
        results[rid] = {k: jsonable(v) for k, v in res.items()}
    return recs, results


# ----------------------------------------------------------------- summary

def summary_rows(rows4, recs, results):
    """(group, market, tf) -> list of (net R, stop %) for filled, graded, non-news trades."""
    out = {}
    for r in rows4:
        if r.get("news_window") or r.get("final_result") not in FILLED or num(r.get("net_realized_r")) is None:
            continue
        entry, stop = num(r.get("planned_entry")), num(r.get("stop_price"))
        risk = abs(entry - stop) / entry * 100 if entry and stop else 0
        out.setdefault((r["market"], "4H"), []).append((r["net_realized_r"], risk))
    for rec in recs:
        res = results[rec["id"]]
        if not res.get("filled") or res.get("news_window"):
            continue
        _, net = trades.booked_r(rec["plan"], rec["market"], res)
        if net is None:
            continue
        mk = "NSE" if rec["market"] == NSE else "CRYPTO"
        out.setdefault((mk, rec["tf"].upper()), []).append((net, trades.risk_pct(rec["plan"])))
    return out


def table(groups, rows4, recs):
    lines = ["| market | tf | alerts | filled+closed | win % | total R | R/trade | %/trade |",
             "|---|---|---|---|---|---|---|---|"]
    alerts = Counter((r["market"], "4H") for r in rows4)
    for rec in recs:
        alerts[("NSE" if rec["market"] == NSE else "CRYPTO", rec["tf"].upper())] += 1
    order = ["4H", "1D", "1W", "1M"]
    keys = sorted(set(alerts) | set(groups), key=lambda k: (k[0], order.index(k[1]) if k[1] in order else 9))
    for k in keys:
        g = groups.get(k, [])
        n = len(g)
        tot = sum(x for x, _ in g)
        win = sum(1 for x, _ in g if x > 0)
        pct = sum(x * risk for x, risk in g) / n if n else 0
        lines.append(f"| {k[0]} | {k[1]} | {alerts[k]} | {n} | {win / n * 100 if n else 0:.0f}% | {tot:+.1f} | "
                     f"{tot / n if n else 0:+.2f} | {pct:+.2f}% |")
    return lines


def live_match(state: Path, got, since_live: float) -> list[str]:
    """How many live zone alerts since since_live the replay also sends (same symbol, side, tf, within 4h)."""
    def norm(sym):
        return str(sym).split("/")[0].replace(":USDT", "").upper()
    replay = {}
    for t in got:
        replay.setdefault((norm(t["symbol"]), t["plan"]["side"], t["tf"]), []).append(t["alert_ts"])
    live = []
    for name in ("crypto_alert_records.jsonl", "nse_alert_records.jsonl"):
        path = state / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                    live.append((norm(r["symbol"]), r["side"], r.get("timeframe", "4h"),
                                 pd.Timestamp(r["delivered_at_utc"]).timestamp()))
                except (ValueError, KeyError):
                    continue
    path = state / "fib_trendline_alert_records.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("kind") == "zone":
                live.append((norm(r["symbol"]), r["plan"]["side"], r["tf"], float(r["sent_ts"])))
    hit, total = Counter(), Counter()
    for sym, side, tf, ts in live:
        if ts < since_live:
            continue
        group = "4H" if tf == "4h" else "1D+"
        total[group] += 1
        if any(abs(ts - x) <= 4 * 3600 for x in replay.get((sym, side, tf), [])):
            hit[group] += 1
    since_text = pd.Timestamp(since_live, unit="s", tz=IST).strftime("%Y-%m-%d")
    return [f"Check: live zone alerts since {since_text} that the replay also sends (same symbol, side, timeframe, "
            "within 4h): " + ", ".join(f"{g} {hit[g]}/{total[g]}" for g in sorted(total)), ""]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--state", default="", help="scanner-runtime-state checkout, for the live-vs-replay check")
    parser.add_argument("--limit", type=int, default=0, help="first N symbols per market (smoke test)")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    scanner.ZONE_BASE_EXTRA = 1
    since = int(pd.Timestamp(args.since, tz=IST).timestamp())
    now = int(time.time())

    got = replay_all(since, now, args.limit)
    rows4 = grade_4h([t for t in got if t["tf"] == "4h"], now)
    recs, results = htf_records([t for t in got if t["tf"] in HTF])

    with (OUT / "zone_rebuild_4h.jsonl").open("w", encoding="utf-8") as fh:
        for r in sorted(rows4, key=lambda r: r["alert_time"] or ""):
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    with (OUT / "zone_rebuild_htf.jsonl").open("w", encoding="utf-8") as fh:
        for r in sorted(recs, key=lambda r: r["sent_ts"]):
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    (OUT / "zone_rebuild_htf_results.json").write_text(json.dumps(results, sort_keys=True, default=str), encoding="utf-8")
    meta = {"since": pd.Timestamp(since, unit="s", tz="UTC").isoformat(),
            "cutoff": pd.Timestamp(now, unit="s", tz="UTC").isoformat(),
            "built_at": pd.Timestamp(now, unit="s", tz="UTC").isoformat(),
            "rows_4h": len(rows4), "rows_htf": len(recs)}
    (OUT / "zone_rebuild_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")

    groups = summary_rows(rows4, recs, results)
    news = sum(1 for r in rows4 if r.get("news_window")) + sum(1 for r in results.values() if r.get("news_window"))
    outcomes = Counter(r.get("final_result") if r.get("filled") else r.get("outcome") for r in rows4)
    text = [f"# S/R zone backtest rebuilt under today's rules ({args.since} to "
            f"{pd.Timestamp(now, unit='s', tz=IST):%Y-%m-%d %H:%M} IST)", "",
            "Today's zone engine, filters and watchlists on 4H, 1D, 1W, 1M (no 30m). 4H graded by the daily "
            "zone report's code (Delta / Yahoo 5m, fees, BE); 1D+ like the live 1D+ zone alerts (5 candles to "
            "fill, hold 20, 2R + BE, fees). % = R x the trade's stop distance. "
            f"{news} trades filled within 15 min of US CPI/PPI/FOMC left out.", ""]
    text += table(groups, rows4, recs)
    if args.state:
        # 2026-10-21: the last zone rule change (3% band on 1W / 1M); watchlist since 2026-10-16
        text += [""] + live_match(Path(args.state), got, pd.Timestamp("2026-10-21 21:00", tz=IST).timestamp())
    text += ["", "4H outcomes: " + ", ".join(f"{k} {v}" for k, v in outcomes.most_common()), ""]
    (OUT / "SUMMARY.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text))


if __name__ == "__main__":
    main()
