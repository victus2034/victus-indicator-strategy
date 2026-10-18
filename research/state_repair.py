"""One-off repair of the stored daily grades (lakky, 2026-10-18: "do it").

1. W 30m, 17 Oct card: the 18 Oct morning re-run overwrote its +2R with
   `alert_before_data` (Delta stopped serving W, the OKX fallback had 300
   candles). The row graded at the time is restored from runtime-state commit
   aea7a4f08 (research/state_repair_w_2026-10-17.jsonl).
2. Zone re-alerts after an unfilled first alert (promote_repeats, PR #55) are
   graded for every day already reported since --since, on Delta / Yahoo 5m
   candles, and added. Rows already stored are never changed; a repeat whose
   candles could not be fetched is left out rather than stored as a failure.

Dry run by default (prints what it would add). --apply writes
daily_backtest_finalized_records.jsonl; the workflow then persists it.
Run by .github/workflows/state_repair.yml.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parent))

import backtest_audit as ba  # noqa: E402
import daily_backtest_summary as dbs  # noqa: E402

W_ROW = Path(__file__).resolve().parent / "state_repair_w_2026-10-17.jsonl"
GRADED = {"SL", "BE", "+1R", "+2R", "Neither", "zone_not_touched", dbs.DATA_QUALITY_AMBIGUOUS}


def num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def restore_w(apply: bool) -> str:
    good = json.loads(W_ROW.read_text(encoding="utf-8").strip())
    rows = dbs.read_jsonl(dbs.FINALIZED_RECORDS_PATH)
    hit = [r for r in rows if r.get("trade_id") == good["trade_id"] and r.get("timeframe") == good["timeframe"]]
    if not hit:
        return "W 17 Oct: row not found, nothing done"
    if hit[0].get("outcome") not in dbs.DATA_FAILURE_OUTCOMES:
        return f"W 17 Oct: already {hit[0].get('outcome')}, nothing done"
    line = f"W 17 Oct 30m: {hit[0].get('outcome')} -> {good['outcome']} ({good['net_realized_r']:+.2f}R)"
    if apply:
        out = [good if (r.get("trade_id") == good["trade_id"] and r.get("timeframe") == good["timeframe"]) else r
               for r in rows]
        with dbs.FINALIZED_RECORDS_PATH.open("w", encoding="utf-8") as fh:
            for r in out:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    return line


def promote_history(since: pd.Timestamp, apply: bool) -> list[str]:
    lines = ["| market | tf | re-alert trades added | filled | total R | R/trade | %/trade |", "|---|---|---|---|---|---|---|"]
    stored = dbs.read_jsonl(dbs.FINALIZED_RECORDS_PATH)
    for (file_market, tf), name in ba.ALERT_FILES.items():
        for market in ba.MARKETS_IN_FILE[file_market]:
            label = market.upper()
            reported = [pd.Timestamp(r["date"]).date() for r in stored
                        if r.get("market") == label and r.get("timeframe") == tf and r.get("date")]
            if not reported:
                continue
            last_reported = max(reported)
            records = dbs.load_records(Path(name), tf, keep_repeats=True)
            if records.empty or "repeat_of" not in records:
                continue
            records = records[records["market_class"] == {"nse": dbs.MARKET_NSE, "crypto": dbs.MARKET_CRYPTO,
                                                          "xstock": dbs.MARKET_XSTOCK, "other": dbs.MARKET_OTHER}[market]]
            records = dbs.assign_report_dates(records.copy(), market)
            repeats = records[records["repeat_of"].notna()]
            repeats = repeats[(repeats["event_time_ist"] >= since) & (repeats["report_date"] <= last_reported)]
            repeats = repeats[~repeats["trade_id"].astype(str).isin(dbs.stored_trade_ids(dbs.FINALIZED_RECORDS_PATH))]
            if repeats.empty:
                continue
            symbols = sorted(repeats["symbol"].unique())
            start = int(repeats["event_time"].min().timestamp()) - 3 * 3600
            end = int(repeats["event_time"].max().timestamp()) + 40 * 3600
            if market != "nse":
                dbs.configure_crypto_data(tf)
            frames = ba.fetch_frames(market if market == "nse" else "crypto", symbols, start, end)
            outcomes = dbs.stored_outcomes(dbs.FINALIZED_RECORDS_PATH)
            added = filled = 0
            total_r = total_pct = 0.0
            for day in sorted(repeats["report_date"].unique()):
                day_repeats = repeats[repeats["report_date"] == day]
                rows = [r for r in dbs.promote_repeats([], day_repeats, frames, market, stored_outcomes=outcomes)
                        if r.get("outcome") in GRADED]
                amb = [r for r in rows if r.get("final_result") == dbs.DATA_QUALITY_AMBIGUOUS]
                if amb:
                    fine, _ = dbs.fetch_resolution_frames(sorted({r["symbol"] for r in amb}), market,
                                                          windows=dbs.resolution_windows(pd.DataFrame(amb)))
                    by_id = {str(a["trade_id"]): a for a in day_repeats.to_dict("records")}
                    for i, r in enumerate(rows):
                        if r.get("final_result") == dbs.DATA_QUALITY_AMBIGUOUS:
                            again = dbs.simulate_alerts(pd.DataFrame([by_id[str(r["trade_id"])]]), frames, market,
                                                        resolution_frames=fine)[0]
                            again["promoted_from"] = r.get("promoted_from")
                            rows[i] = again
                if not rows:
                    continue
                results, _ = dbs.apply_same_day_zone_cooldown(pd.DataFrame(rows), market)
                for r in results.to_dict("records"):
                    outcomes[str(r["trade_id"])] = (r.get("outcome"), r.get("event_time_ist"))
                    added += 1
                    net = num(r.get("net_realized_r"))
                    if r.get("filled") and net is not None:
                        filled += 1
                        total_r += net
                        total_pct += net * abs(float(r["entry_price"]) - float(r["stop_price"])) / float(r["entry_price"]) * 100
                if apply:
                    dbs.persist_finalized_records(day, tf, results, market)
            per = (total_r / filled) if filled else 0.0
            per_pct = (total_pct / filled) if filled else 0.0
            lines.append(f"| {label} | {tf} | {added} | {filled} | {total_r:+.2f} | {per:+.3f} | {per_pct:+.3f}% |")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    before = len(dbs.read_jsonl(dbs.FINALIZED_RECORDS_PATH))
    out = ["# State repair " + ("(applied)" if args.apply else "(dry run)"), "", restore_w(args.apply), ""]
    out += promote_history(pd.Timestamp(args.since, tz=dbs.IST), args.apply)
    after = len(dbs.read_jsonl(dbs.FINALIZED_RECORDS_PATH))
    out += ["", f"Finalized rows: {before} -> {after}"]
    text = "\n".join(out)
    print(text)
    Path("state_repair_report.md").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
