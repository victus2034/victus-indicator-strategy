"""Research only - nothing here is imported by the live scanners.

Audit of the three scores on the daily zone card (2026-10-18, lakky):
backtest (TOTAL), trail test (trail_net_r) and paper (paper_trading_state.json).

For every stored zone trade since --since:
1. Re-grade it with the production code on fresh 5m candles (Delta / Yahoo)
   and diff against what is stored.
2. Grade it again with independent references written from the rules alone:
   research/backtest_audit.reference for the backtest, trail_reference below
   for the trail test.
3. Match every closed paper trade to its backtest twin and diff the two.
4. Print candle-by-candle traces: W 16 Oct (the +2R a re-run overwrote) and a
   sample, plus every disagreement.

Writes research/out/daily_scores_audit/: AUDIT.md, diffs.csv, traces.txt.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, time as dtime, timedelta
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parent))

import backtest_audit as ba  # noqa: E402
import daily_backtest_summary as dbs  # noqa: E402

IST = dbs.IST
FILLED = {"SL", "BE", "+1R", "+2R", "Neither"}


def trail_reference(frame: pd.DataFrame, alert: dict, market: str, ref: dict) -> float | None:
    """Trail test from the rule: original stop until +0.5R has traded, then a
    stop 0.25R behind the best price, moved from the candle after; stop counts
    on the fill candle, a stop exit pays the 0.05% slip; held to the same time
    limit as the trade; net of the round trip."""
    if ref.get("outcome") not in FILLED and ref.get("outcome") != "AMB":
        return None
    long = alert["side"] == "long"
    sign = 1 if long else -1
    entry, stop = float(alert["planned_entry"]), float(alert["stop_price"])
    risk = sign * (entry - stop)
    starts = list(frame.index)
    fill = starts.index(ref["entry_time"])
    bar = timedelta(minutes=5)
    if market == "nse":
        day = starts[fill].date()
        cutoff = datetime.combine(day, dtime(15, 10), tzinfo=IST)
        last = max(i for i in range(fill, len(starts)) if starts[i].date() == day and starts[i] + bar <= cutoff)
    else:
        expiry = starts[fill] + timedelta(hours=6)
        last = max(i for i in range(fill, len(starts)) if starts[i] + bar <= expiry)
    live, best = stop, 0.0
    exit_px = None
    for i in range(fill, last + 1):
        h, l = frame["high"].iat[i], frame["low"].iat[i]
        if (l <= live) if long else (h >= live):
            exit_px = live * (1 - sign * dbs.SL_FILL_SLIPPAGE_PCT / 100)
            break
        if i == fill:
            continue
        best = max(best, (h - entry) / risk if long else (entry - l) / risk)
        if best >= 0.5:
            level = entry + sign * (best - 0.25) * risk
            if sign * (level - live) > 0:
                live = level
    if exit_px is None:
        exit_px = frame["close"].iat[last]
    rate = dbs.ROUND_TRIP_COST_PCT if market == "nse" else dbs.CRYPTO_ROUND_TRIP_COST_PCT
    return sign * (exit_px - entry) / risk - entry * rate / 100 / risk


def num(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default=".")
    parser.add_argument("--since", default="2026-10-05")
    parser.add_argument("--out", default="research/out/daily_scores_audit")
    parser.add_argument("--probe", default="WUSD,OGNUSD,GTCUSD,CAPUSD,RSRUSD,LINKUSD,XRPUSD,BNBUSD",
                        help="Symbols to fetch through the backtest's own venue chain, logging the venue.")
    args = parser.parse_args()
    state = Path(args.state)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    since = pd.Timestamp(args.since, tz=IST)

    stored = {}
    for name in ("daily_backtest_finalized_records.jsonl", "daily_backtest_pending_records.jsonl"):
        for row in dbs.read_jsonl(state / name):
            if row.get("alert_time") and pd.Timestamp(row["alert_time"]) >= since:
                stored[row["trade_id"]] = row
    by_key = {(r.get("zone_id"), str(r.get("alert_time"))[:26]): r["trade_id"] for r in stored.values()}
    print(f"stored rows since {args.since}: {len(stored)}")

    lines_diff, ref_diffs, trail_diffs, traces, fetch_fail = [], [], [], [], Counter()
    summary = defaultdict(lambda: defaultdict(float))
    resim_by_id = {}
    random.seed(18)

    for (file_market, tf), name in ba.ALERT_FILES.items():
        alerts = dbs.load_records(state / name, tf)
        if alerts.empty:
            continue
        alerts["trade_id"] = [
            by_key.get((z, t.isoformat()[:26]), tid)
            for z, t, tid in zip(alerts["zone_id"], alerts["event_time_ist"], alerts["trade_id"])
        ]
        alerts = alerts[alerts["trade_id"].astype(str).isin(stored)].copy()
        for market in ba.MARKETS_IN_FILE[file_market]:
            sub = alerts[alerts["market_class"] == market.upper()].copy().reset_index(drop=True)
            if sub.empty:
                continue
            symbols = sorted(sub["symbol"].unique())
            start = int(sub["event_time"].min().timestamp()) - 3 * 3600
            end = int(sub["event_time"].max().timestamp()) + 40 * 3600
            if market != "nse":
                dbs.configure_crypto_data(tf)
            frames = ba.fetch_frames(market if market == "nse" else "crypto", symbols, start, end)
            for symbol in symbols:
                if symbol not in frames:
                    fetch_fail[symbol] += 1
            print(f"{market} {tf}: {len(sub)} alerts, frames {len(frames)}/{len(symbols)}")
            rows = dbs.simulate_alerts(sub, frames, market)
            amb = pd.DataFrame([r for r in rows if r.get("final_result") == dbs.DATA_QUALITY_AMBIGUOUS])
            if not amb.empty:
                fine, _ = dbs.fetch_resolution_frames(
                    sorted(amb["symbol"].unique()), market, windows=dbs.resolution_windows(amb))
                rows = dbs.rerun_ambiguous(sub, rows, frames, market, fine)
            results, _ = dbs.apply_same_day_zone_cooldown(pd.DataFrame(rows), market)
            for alert, row in zip(sub.to_dict("records"), results.to_dict("records")):
                old = stored[alert["trade_id"]]
                key = (old["market"], tf)
                new_res = row.get("final_result") if row.get("filled") else row.get("outcome")
                old_res = old.get("final_result") if old.get("filled") else old.get("outcome")
                if alert["symbol"] not in frames:
                    new_res = "no_candles"
                resim_by_id[alert["trade_id"]] = (new_res, num(row.get("net_realized_r")), num(row.get("trail_net_r")))
                old_net = num(old.get("net_realized_r")) if old_res in FILLED else None
                new_net = num(row.get("net_realized_r")) if new_res in FILLED else None
                s = summary[key]
                if old_net is not None:
                    s["stored_n"] += 1
                    s["stored_net"] += old_net
                    s["stored_trail"] += num(old.get("trail_net_r")) or 0.0
                if new_net is not None:
                    s["resim_n"] += 1
                    s["resim_net"] += new_net
                    s["resim_trail"] += num(row.get("trail_net_r")) or 0.0
                if old_res != new_res or (old_net is not None and new_net is not None and abs(old_net - new_net) > 1e-6):
                    lines_diff.append({"market": old["market"], "tf": tf, "symbol": alert["symbol"],
                                       "alert_time": old.get("alert_time"), "stored": old_res, "resim": new_res,
                                       "stored_net": old_net, "resim_net": new_net})
                if alert["symbol"] not in frames:
                    continue
                frame = frames[alert["symbol"]]
                ref = ba.reference(frame, alert, market)
                s["checked"] += 1
                if ref["outcome"] not in ("AMB", "data_short") and new_res not in ("zone_cooldown", "immature"):
                    same = ref["outcome"] == new_res
                    if same and ref["outcome"] in FILLED and abs(ref["net_r"] - (new_net or 0)) > 1e-6:
                        same = False
                    if not same:
                        ref_diffs.append({"market": old["market"], "tf": tf, "symbol": alert["symbol"],
                                          "alert_time": old.get("alert_time"), "production": new_res,
                                          "reference": ref["outcome"], "production_net": new_net,
                                          "reference_net": ref.get("net_r")})
                    elif ref["outcome"] in FILLED:
                        s["ref_agree"] += 1
                        trail_ref = trail_reference(frame, alert, market, ref)
                        trail_prod = num(row.get("trail_net_r"))
                        if trail_ref is not None and trail_prod is not None:
                            if abs(trail_ref - trail_prod) > 1e-6:
                                trail_diffs.append({"market": old["market"], "tf": tf, "symbol": alert["symbol"],
                                                    "alert_time": old.get("alert_time"),
                                                    "production": trail_prod, "reference": trail_ref})
                            else:
                                s["trail_agree"] += 1
                wanted = (alert["symbol"] == "WUSD" and str(old.get("alert_time", "")).startswith("2026-10-16")) \
                    or (row.get("filled") and new_res in FILLED and random.random() < 0.04)
                if wanted and row.get("filled") and len(traces) < 30:
                    traces.append(ba.trace(frame, {**row, "market": old["market"], "alert_time": old["alert_time"]}, old))
                    traces[-1] += f"\n  trail: stored {old.get('trail_net_r')} resim {row.get('trail_net_r')}"

    # paper vs backtest, same trade
    paper_rows = []
    paper_state = json.loads((state / "paper_trading_state.json").read_text(encoding="utf-8"))
    by_symbol_time = {}
    for r in stored.values():
        by_symbol_time[(r["symbol"], str(r.get("alert_time"))[:19])] = r
    paper_counts = Counter()
    for p in paper_state.get("closed", []):
        if pd.Timestamp(p["alert_time"]) < since:
            continue
        twin = by_symbol_time.get((p["symbol"], str(p["alert_time"])[:19]))
        if twin is None:
            paper_counts["paper_only"] += 1
            paper_rows.append({"symbol": p["symbol"], "alert_time": p["alert_time"], "paper": p["outcome"],
                               "backtest": "missing", "paper_net": p.get("net_realized_r"), "backtest_net": None})
            continue
        b_res = twin.get("final_result") if twin.get("filled") else twin.get("outcome")
        b_net = num(twin.get("net_realized_r"))
        p_net = num(p.get("net_realized_r"))
        same = p["outcome"] == b_res and (p_net is None or b_net is None or abs(p_net - b_net) < 1e-6)
        paper_counts["match" if same else "differ"] += 1
        if not same:
            paper_rows.append({"symbol": p["symbol"], "alert_time": p["alert_time"], "paper": p["outcome"],
                               "backtest": b_res, "paper_net": p_net, "backtest_net": b_net})

    pd.DataFrame(lines_diff).to_csv(out / "stored_vs_resim.csv", index=False)
    pd.DataFrame(ref_diffs).to_csv(out / "reference_diffs.csv", index=False)
    pd.DataFrame(trail_diffs).to_csv(out / "trail_diffs.csv", index=False)
    pd.DataFrame(paper_rows).to_csv(out / "paper_diffs.csv", index=False)
    (out / "traces.txt").write_text("\n\n".join(traces) + "\n", encoding="utf-8")

    md = [f"# Daily scores audit - since {args.since}", "",
          "| market | tf | stored trades | stored R | stored trail R | resim trades | resim R | resim trail R | checked | backtest = ref | trail = ref |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for key in sorted(summary):
        s = summary[key]
        md.append(f"| {key[0]} | {key[1]} | {int(s['stored_n'])} | {s['stored_net']:+.2f} | {s['stored_trail']:+.2f} | "
                  f"{int(s['resim_n'])} | {s['resim_net']:+.2f} | {s['resim_trail']:+.2f} | {int(s['checked'])} | "
                  f"{int(s['ref_agree'])} | {int(s['trail_agree'])} |")
    md += ["", f"Stored vs re-graded now: {len(lines_diff)} rows differ",
           f"Backtest vs independent reference: {len(ref_diffs)} disagree",
           f"Trail vs independent reference: {len(trail_diffs)} disagree",
           f"Paper vs backtest (same trade): {dict(paper_counts)}",
           f"No Delta/Yahoo candles: {dict(fetch_fail)}"]
    for title, rows in (("Stored vs re-graded", lines_diff), ("Reference", ref_diffs),
                        ("Trail", trail_diffs), ("Paper", paper_rows)):
        if rows:
            md += ["", f"## {title} (first 25)", "", pd.DataFrame(rows[:25]).to_markdown(index=False)]
    md += ["", "## Venue the daily backtest gets (crypto_fetch_ohlcv, 5m)", ""]
    dbs.configure_crypto_data("30m")
    for symbol in [s for s in args.probe.split(",") if s]:
        try:
            delta = dbs.crypto_scanner.fetch_delta_ohlcv(symbol)
            delta_note = "not a Delta contract" if delta is None else (
                f"{len(delta)} candles, last {pd.Timestamp(delta[-1][0], unit='ms', tz='UTC').tz_convert(IST):%m-%d %H:%M}")
        except Exception as error:  # noqa: BLE001
            delta_note = f"error {str(error)[:90]}"
        dbs.CRYPTO_FETCH_SOURCE_COUNTS.clear()
        try:
            rows = dbs.crypto_fetch_ohlcv(symbol)
            got = (f"{dict(dbs.CRYPTO_FETCH_SOURCE_COUNTS)} {len(rows)} candles from "
                   f"{pd.Timestamp(rows[0][0], unit='ms', tz='UTC').tz_convert(IST):%m-%d %H:%M}")
        except Exception as error:  # noqa: BLE001
            got = f"failed {str(error)[:90]}"
        md.append(f"- {symbol}: Delta direct: {delta_note} | chain: {got}")
    (out / "AUDIT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
