"""Research only - nothing here is imported by the live scanners.

Audit of the zone-trade backtest (2026-10-04). Three checks on the stored
daily_backtest_finalized_records.jsonl:

1. Re-simulate every recorded alert with the production code
   (daily_backtest_summary.simulate_alerts + the 1m tie-break + the duplicate
   cooldown) on fresh 5m candles, and diff against what is stored. A stored
   row that the current code would grade differently is history that was
   never re-scored, or a grading that depended on stale data.
2. Score the same alerts with an independent reference written here from the
   rules alone (it shares no function with daily_backtest_summary), and diff it
   against the production re-simulation. A disagreement is a logic bug in one
   of the two.
3. Print candle-by-candle traces of a sample of trades, so a person can check
   fill, stop, breakeven and target by eye.

Writes research/out/audit/: AUDIT.md, diffs.csv, rescored_finalized.jsonl
(stored rows re-graded by the current code - NOT applied anywhere), traces.txt.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, time as dtime, timedelta
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))  # after PYTHONPATH, so a CI step can swap in main's scoring

import daily_backtest_summary as dbs  # noqa: E402
import fib_trendline_data as ftd  # noqa: E402
import scanner as crypto_scanner  # noqa: E402

IST = dbs.IST
FILLED = {"SL", "BE", "+1R", "+2R", "Neither"}
ALERT_FILES = {
    ("crypto", "30m"): "crypto_alert_records_30m.jsonl",
    ("crypto", "4h"): "crypto_alert_records.jsonl",
    ("nse", "30m"): "nse_alert_records_30m.jsonl",
    ("nse", "4h"): "nse_alert_records.jsonl",
}
MARKETS_IN_FILE = {"crypto": ["crypto", "xstock", "other"], "nse": ["nse"]}


# ----------------------------------------------------------------- candles

def contract_for(symbol: str) -> str | None:
    contract = crypto_scanner.delta_contract(symbol)
    if contract:
        return contract
    if symbol.endswith("/USDT"):
        return symbol.split("/")[0] + "USD"
    return None


def to_frame(candles) -> pd.DataFrame:
    frame = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close"])
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame["ts"], unit="s", utc=True)).tz_convert(IST)
    frame["volume"] = 0.0
    return frame.drop(columns="ts").sort_index()


def fetch_frames(market: str, symbols: list[str], start: int, end: int) -> dict[str, pd.DataFrame]:
    frames = {}
    if market == "nse":
        raw = ftd.nse_download(symbols, "5m")
        for symbol, candles in raw.items():
            frames[symbol] = to_frame(candles)
        return frames
    for symbol in symbols:
        contract = contract_for(symbol)
        if contract is None:
            print(f"skip {symbol}: no Delta contract")
            continue
        try:
            frames[symbol] = to_frame(ftd.delta_candles(contract, "5m", start, end))
        except Exception as error:  # noqa: BLE001
            print(f"skip {symbol}: {error}")
        time.sleep(0.2)
    return frames


# ----------------------------------------------------------------- independent reference

def reference(frame: pd.DataFrame, alert: dict, market: str) -> dict:
    """The rules, from scratch. Returns outcome / entry_time / exit_time / gross_r / net_r.

    Rules: limit at planned entry, fills from the 5m candle after the one the
    alert landed in, within 3 candles of the alert's timeframe (NSE: same day,
    not before 09:15, nothing ending after 15:10). Stop counts on the fill
    candle; targets only from the next candle unless the fill candle opened at
    or through the entry. +0.5R moves the stop to entry + offset from the next
    candle (if that level is not beyond +0.5R). +2R is the only target exit.
    Crypto-like: 6h after the fill candle opens. A candle touching a live stop
    and a level that would change the result is "AMB" (production asks 1m data).
    """
    side = alert["side"]
    long = side == "long"
    entry = float(alert["planned_entry"]) if pd.notna(alert.get("planned_entry")) else None
    stop = float(alert["stop_price"]) if pd.notna(alert.get("stop_price")) else None
    if entry is None or stop is None:
        return {"outcome": "no_levels"}
    nse = market == "nse"
    t_alert = pd.Timestamp(alert["event_time_ist"]).tz_convert(IST)
    starts = list(frame.index)
    bar = timedelta(minutes=5)
    alert_bar = timedelta(minutes=30) if alert["timeframe"] == "30m" else timedelta(hours=4)
    window = max(3, int(alert_bar * 3 / bar))
    # candle containing the alert
    k = None
    for i, s in enumerate(starts):
        if s <= t_alert:
            k = i
        else:
            break
    if k is None:
        return {"outcome": "alert_before_data"}
    cutoff = datetime.combine(t_alert.date(), dtime(15, 10), tzinfo=IST)

    def usable(i):
        s = starts[i]
        if nse:
            return s.date() == t_alert.date() and s + bar <= cutoff
        return True

    fill = None
    for i in range(k + 1, min(k + window, len(starts) - 1) + 1):
        if not usable(i):
            if nse and starts[i].date() != t_alert.date():
                break
            continue
        if nse and starts[i].time() < dtime(9, 15):
            continue
        lo, hi = frame["low"].iat[i], frame["high"].iat[i]
        if (lo <= entry) if long else (hi >= entry):
            fill = i
            break
    if fill is None:
        return {"outcome": "zone_not_touched"}
    sign = 1 if long else -1
    risk = sign * (entry - stop)
    if risk <= 0:
        return {"outcome": "bad_stop"}
    rate = dbs.ROUND_TRIP_COST_PCT if nse else dbs.CRYPTO_ROUND_TRIP_COST_PCT
    cost_r = entry * rate / 100 / risk
    if cost_r > dbs.MAX_COST_R:
        return {"outcome": "stop_too_tight"}
    be_pct = dbs.BREAK_EVEN_OFFSET_PCT if nse else dbs.CRYPTO_BREAK_EVEN_OFFSET_PCT
    be_stop = entry + sign * entry * be_pct / 100
    half, t1, t2 = entry + sign * 0.5 * risk, entry + sign * risk, entry + sign * 2 * risk
    be_ok = sign * (half - be_stop) >= 0
    if nse:
        last = fill
        for i in range(fill, len(starts)):
            if starts[i].date() == t_alert.date() and starts[i] + bar <= cutoff:
                last = i
            elif starts[i].date() != t_alert.date():
                break
    else:
        expiry = starts[fill] + timedelta(hours=6)
        last = fill
        for i in range(fill, len(starts)):
            if starts[i] + bar <= expiry:
                last = i
            else:
                break
        if starts[last] + bar < expiry and last == len(starts) - 1:
            return {"outcome": "data_short"}
    reached_half = reached_1 = False
    outcome, exit_i, exit_px = "Neither", last, None
    for i in range(fill, last + 1):
        o, h, l = frame["open"].iat[i], frame["high"].iat[i], frame["low"].iat[i]
        if i == fill:
            opened_through = (o <= entry) if long else (o >= entry)
            if not opened_through:
                h, l = (min(h, entry), l) if long else (h, max(l, entry))
        moved = reached_half and be_ok
        live = be_stop if moved else stop
        stop_hit = (l <= live) if long else (h >= live)
        hit_half = (h >= half) if long else (l <= half)
        hit_1 = (h >= t1) if long else (l <= t1)
        hit_2 = (h >= t2) if long else (l <= t2)
        deciding = (hit_1 or hit_2) if moved else (hit_half or hit_1 or hit_2)
        if stop_hit and deciding:
            return {"outcome": "AMB", "entry_time": starts[fill], "exit_time": starts[i]}
        if stop_hit:
            outcome, exit_i = ("BE" if moved else "SL"), i
            exit_px = be_stop if moved else stop * (1 - sign * dbs.SL_FILL_SLIPPAGE_PCT / 100)
            break
        if hit_half or hit_1:
            reached_half = True
        if hit_1:
            reached_1 = True
            outcome = "+1R"
        if hit_2:
            outcome, exit_i, exit_px = "+2R", i, t2
            break
    if exit_px is None:
        exit_px = frame["close"].iat[exit_i]
    gross = sign * (exit_px - entry) / risk
    return {"outcome": outcome, "entry_time": starts[fill], "exit_time": starts[exit_i],
            "gross_r": gross, "net_r": gross - cost_r, "reached_1r": reached_1}


# ----------------------------------------------------------------- trace

def trace(frame: pd.DataFrame, row: dict, stored: dict) -> str:
    long = row["side"] == "long"
    entry, stop = float(row["entry_price"]), float(row["stop_price"])
    sign = 1 if long else -1
    risk = sign * (entry - stop)
    nse = row["market"] == "NSE"
    be_pct = dbs.BREAK_EVEN_OFFSET_PCT if nse else dbs.CRYPTO_BREAK_EVEN_OFFSET_PCT
    be = entry + sign * entry * be_pct / 100
    lv = {"SL": stop, "BE": be, "+0.5R": entry + sign * .5 * risk, "+1R": entry + sign * risk,
          "+2R": entry + sign * 2 * risk}
    alert_t = pd.Timestamp(row["alert_time"]).tz_convert(IST)
    exit_t = pd.Timestamp(row["exit_time"]).tz_convert(IST) if row.get("exit_time") else alert_t
    view = frame[(frame.index >= alert_t - timedelta(minutes=5)) & (frame.index <= exit_t + timedelta(minutes=10))]
    lines = [
        f"=== {row['symbol']} {row['timeframe']} {row['side'].upper()} alert {alert_t:%Y-%m-%d %H:%M:%S} "
        f"| stored {stored.get('final_result')} net {stored.get('net_realized_r')} "
        f"| resim {row.get('final_result')} net {row.get('net_realized_r')}",
        "levels: entry %.6g  " % entry + "  ".join(f"{k} {v:.6g}" for k, v in lv.items()),
        f"entry_time {row.get('entry_time')}  exit_time {row.get('exit_time')}",
    ]
    for ts, c in view.iterrows():
        marks = []
        if (c["low"] <= entry) if long else (c["high"] >= entry):
            marks.append("touches-entry")
        for name, px in lv.items():
            if name in ("SL", "BE"):
                if (c["low"] <= px) if long else (c["high"] >= px):
                    marks.append(name)
            elif (c["high"] >= px) if long else (c["low"] <= px):
                marks.append(name)
        lines.append(f"  {ts:%m-%d %H:%M}  O {c['open']:.6g} H {c['high']:.6g} L {c['low']:.6g} "
                     f"C {c['close']:.6g}  {' '.join(marks)}")
    return "\n".join(lines)


# ----------------------------------------------------------------- main

def jsonable(value):
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", default="daily_backtest_finalized_records.jsonl")
    parser.add_argument("--alerts-dir", default=".")
    parser.add_argument("--out", default="research/out/audit")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    stored = {r["trade_id"]: r for r in dbs.read_jsonl(Path(args.records))}
    # Rows graded before 2026-09-17 carry the backtest's own stable id, not
    # the scanner's trade_id that load_records now prefers, so join on the
    # zone and the delivery moment instead.
    by_key = {(r.get("zone_id"), str(r.get("alert_time"))[:26]): r["trade_id"] for r in stored.values()}
    print(f"stored rows: {len(stored)}")
    diffs, rescored, ref_diffs, traces = [], [], [], []
    summary = defaultdict(lambda: defaultdict(float))
    transitions = Counter()
    random.seed(7)

    for (file_market, tf), name in ALERT_FILES.items():
        path = Path(args.alerts_dir) / name
        alerts = dbs.load_records(path, tf)
        if alerts.empty:
            continue
        alerts["trade_id"] = [
            by_key.get((z, t.isoformat()[:26]), tid)
            for z, t, tid in zip(alerts["zone_id"], alerts["event_time_ist"], alerts["trade_id"])
        ]
        alerts = alerts[alerts["trade_id"].astype(str).isin(stored)].copy()
        if alerts.empty:
            continue
        for market in MARKETS_IN_FILE[file_market]:
            sub = alerts[alerts["market_class"] == market.upper()].copy().reset_index(drop=True)
            if sub.empty:
                continue
            symbols = sorted(sub["symbol"].unique())
            start = int(sub["event_time"].min().timestamp()) - 3 * 3600
            end = int(sub["event_time"].max().timestamp()) + 40 * 3600
            if market != "nse":
                dbs.configure_crypto_data(tf)
            frames = fetch_frames(market if market == "nse" else "crypto", symbols, start, end)
            print(f"{market} {tf}: {len(sub)} alerts, frames for {len(frames)}/{len(symbols)} symbols")
            rows = dbs.simulate_alerts(sub, frames, market)
            amb = pd.DataFrame([r for r in rows if r.get("final_result") == dbs.DATA_QUALITY_AMBIGUOUS])
            if not amb.empty:
                fine, failures = dbs.fetch_resolution_frames(
                    sorted(amb["symbol"].unique()), market, windows=dbs.resolution_windows(amb))
                if failures:
                    print(f"  fine-data failures: {len(failures)}")
                rows = dbs.rerun_ambiguous(sub, rows, frames, market, fine)
            results, _ = dbs.apply_same_day_zone_cooldown(pd.DataFrame(rows), market)
            for alert, row in zip(sub.to_dict("records"), results.to_dict("records")):
                old = stored[alert["trade_id"]]
                key = (old["market"], tf)
                new_res = row.get("final_result") if row.get("filled") else row.get("outcome")
                old_res = old.get("final_result") if old.get("filled") else old.get("outcome")
                if alert["symbol"] not in frames:
                    new_res = "no_candles"
                transitions[(key, old_res, new_res)] += 1
                old_net = old.get("net_realized_r") if old.get("final_result") in FILLED else None
                new_net = row.get("net_realized_r") if new_res in FILLED else None
                if old_net is not None:
                    summary[key]["stored_net"] += old_net
                    summary[key]["stored_n"] += 1
                if new_net is not None and not pd.isna(new_net):
                    summary[key]["resim_net"] += new_net
                    summary[key]["resim_n"] += 1
                    trail = row.get("trail_net_r")
                    if trail is not None and not pd.isna(trail):
                        summary[key]["trail_net"] += trail
                if old_res != new_res or (
                    old_net is not None and new_net is not None and abs(old_net - new_net) > 1e-6
                ):
                    diffs.append({
                        "market": old["market"], "timeframe": tf, "symbol": alert["symbol"],
                        "trade_id": alert["trade_id"], "alert_time": old.get("alert_time"),
                        "stored": old_res, "resim": new_res, "stored_net": old_net, "resim_net": new_net,
                        "stored_entry_time": old.get("entry_time"), "resim_entry_time": jsonable(row.get("entry_time")),
                    })
                if alert["symbol"] in frames and new_res != "no_candles":
                    payload = dbs.lifecycle_payload(row, old.get("date"), tf, market)
                    payload["date"] = old.get("date")
                    rescored.append(payload)
                    ref = reference(frames[alert["symbol"]], alert, market)
                    if ref["outcome"] not in ("AMB", "data_short") and new_res != "zone_cooldown":
                        same = ref["outcome"] == new_res or (
                            ref["outcome"] == "zone_not_touched" and new_res == "immature")
                        if same and ref["outcome"] in FILLED and abs(ref["net_r"] - (new_net or 0)) > 1e-6:
                            same = False
                        if not same:
                            ref_diffs.append({
                                "market": old["market"], "timeframe": tf, "symbol": alert["symbol"],
                                "trade_id": alert["trade_id"], "alert_time": old.get("alert_time"),
                                "production": new_res, "reference": ref["outcome"],
                                "production_net": new_net, "reference_net": ref.get("net_r"),
                                "production_entry": jsonable(row.get("entry_time")),
                                "reference_entry": jsonable(ref.get("entry_time")),
                            })
                    if row.get("filled") and new_res in FILLED and (
                        old_res == "+1R" or random.random() < 0.01
                    ) and len(traces) < 40:
                        traces.append(trace(frames[alert["symbol"]], {**row, "market": old["market"],
                                                                      "alert_time": old["alert_time"]}, old))

    pd.DataFrame(diffs).to_csv(out / "diffs.csv", index=False)
    pd.DataFrame(ref_diffs).to_csv(out / "reference_diffs.csv", index=False)
    with (out / "rescored_finalized.jsonl").open("w", encoding="utf-8") as fh:
        for row in rescored:
            fh.write(json.dumps({k: jsonable(v) for k, v in row.items()}, sort_keys=True) + "\n")
    (out / "traces.txt").write_text("\n\n".join(traces) + "\n", encoding="utf-8")

    lines = ["# Backtest audit - stored vs re-simulated (current code)", ""]
    lines.append("| market | tf | stored trades | stored net R | resim trades | resim net R | resim trail R |")
    lines.append("|---|---|---|---|---|---|---|")
    for key in sorted(summary):
        s = summary[key]
        lines.append(f"| {key[0]} | {key[1]} | {int(s['stored_n'])} | {s['stored_net']:+.1f} | "
                     f"{int(s['resim_n'])} | {s['resim_net']:+.1f} | {s['trail_net']:+.1f} |")
    lines += ["", f"Rows that grade differently now: {len(diffs)}", "",
              "## Transitions (stored -> resim), changed only", "", "| market | tf | stored | resim | n |",
              "|---|---|---|---|---|"]
    for (key, a, b), n in sorted(transitions.items(), key=lambda kv: -kv[1]):
        if a != b:
            lines.append(f"| {key[0]} | {key[1]} | {a} | {b} | {n} |")
    lines += ["", f"## Independent reference vs production: {len(ref_diffs)} disagreements", ""]
    if ref_diffs:
        c = Counter((d["production"], d["reference"]) for d in ref_diffs)
        lines += ["| production | reference | n |", "|---|---|---|"]
        lines += [f"| {a} | {b} | {n} |" for (a, b), n in c.most_common()]
    (out / "AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
