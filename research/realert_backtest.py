"""Research only. Zone backtest, Sep 1 - now: first delivery of a zone only
(the old rule) vs also grading a re-alert when the alert it repeats never
filled (promote_repeats, lakky 2026-10-18).

Production code on fresh Delta / Yahoo 5m candles, 1m tie-break, same-day
cooldown. Trades filled within 15 min of a US CPI / PPI / FOMC release are left
out (backtest rule, 2026-10-17; calendar copied from news_window_backtest.py).

Writes research/out/realert/REALERT.md and promoted.jsonl (the extra trades,
in the finalized-record shape - NOT applied anywhere).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parent))

import backtest_audit as ba  # noqa: E402
import daily_backtest_summary as dbs  # noqa: E402

IST = dbs.IST
FILLED = {"SL", "BE", "+1R", "+2R", "Neither"}
CPI = ["2025-09-11", "2025-10-24", "2025-12-18", "2026-01-13", "2026-02-13", "2026-03-11", "2026-04-10",
       "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12", "2026-09-11", "2026-10-14", "2026-11-10"]
PPI = ["2025-09-10", "2025-11-25", "2026-01-14", "2026-01-30", "2026-02-27", "2026-03-18", "2026-04-14",
       "2026-05-13", "2026-06-11", "2026-07-15", "2026-08-13", "2026-09-10", "2026-10-15", "2026-11-13"]
FOMC = ["2025-09-17", "2025-10-29", "2025-12-10", "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
        "2026-07-29", "2026-09-16", "2026-10-28"]
EVENTS = [pd.Timestamp(f"{d} 08:30", tz="America/New_York") for d in CPI + PPI] + \
         [pd.Timestamp(f"{d} 14:00", tz="America/New_York") for d in FOMC]


def news(entry_time) -> bool:
    t = pd.Timestamp(entry_time)
    return any(abs((t - e).total_seconds()) <= 15 * 60 for e in EVENTS)


def num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default=".")
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--out", default="research/out/realert")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    since = pd.Timestamp(args.since, tz=IST)
    stats = defaultdict(lambda: defaultdict(float))
    promoted_rows = []
    skipped_news = 0

    for (file_market, tf), name in ba.ALERT_FILES.items():
        records = dbs.load_records(Path(args.state) / name, tf, keep_repeats=True)
        if records.empty:
            continue
        records = records[records["event_time_ist"] >= since]
        for market in ba.MARKETS_IN_FILE[file_market]:
            sub = records[records["market_class"] == market.upper()].copy().reset_index(drop=True)
            if sub.empty:
                continue
            first = sub[sub["repeat_of"].isna()].reset_index(drop=True)
            repeats = sub[sub["repeat_of"].notna()].reset_index(drop=True)
            symbols = sorted(sub["symbol"].unique())
            start = int(sub["event_time"].min().timestamp()) - 3 * 3600
            end = int(sub["event_time"].max().timestamp()) + 40 * 3600
            if market != "nse":
                dbs.configure_crypto_data(tf)
            frames = ba.fetch_frames(market if market == "nse" else "crypto", symbols, start, end)
            print(f"{market} {tf}: {len(first)} first, {len(repeats)} repeats, frames {len(frames)}/{len(symbols)}")
            for label, use_repeats in (("old", False), ("new", True)):
                rows = dbs.simulate_alerts(first, frames, market)
                if use_repeats:
                    rows = dbs.promote_repeats(rows, repeats, frames, market)
                amb = pd.DataFrame([r for r in rows if r.get("final_result") == dbs.DATA_QUALITY_AMBIGUOUS])
                if not amb.empty:
                    fine, _ = dbs.fetch_resolution_frames(sorted(amb["symbol"].unique()), market,
                                                          windows=dbs.resolution_windows(amb))
                    alerts = pd.concat([first, repeats], ignore_index=True)
                    by_id = {str(a["trade_id"]): a for a in alerts.to_dict("records")}
                    for i, r in enumerate(rows):
                        if r.get("final_result") == dbs.DATA_QUALITY_AMBIGUOUS:
                            a = by_id[str(r["trade_id"])]
                            again = dbs.simulate_alerts(pd.DataFrame([a]), frames, market,
                                                        resolution_frames=fine)[0]
                            again["promoted_from"] = r.get("promoted_from")
                            rows[i] = again
                results, _ = dbs.apply_same_day_zone_cooldown(pd.DataFrame(rows), market)
                key = (market.upper(), tf, label)
                for r in results.to_dict("records"):
                    if not r.get("filled") or r.get("final_result") not in FILLED:
                        continue
                    if news(r["entry_time"]):
                        skipped_news += label == "new"
                        continue
                    net = num(r.get("net_realized_r"))
                    if net is None:
                        continue
                    stop_pct = abs(float(r["entry_price"]) - float(r["stop_price"])) / float(r["entry_price"]) * 100
                    s = stats[key]
                    s["n"] += 1
                    s["r"] += net
                    s["pct"] += net * stop_pct
                    s["wins"] += r["final_result"] in {"+1R", "+2R"} or (r["final_result"] == "Neither" and net > 0)
                    if label == "new" and isinstance(r.get("promoted_from"), str):
                        s["extra_n"] += 1
                        s["extra_r"] += net
                        s["extra_pct"] += net * stop_pct
                        payload = dbs.lifecycle_payload(r, r.get("report_date") or r["event_time_ist"], tf, market)
                        payload["promoted_from"] = r.get("promoted_from")
                        promoted_rows.append(payload)

    lines = [f"# Re-alert after an unfilled first alert - zones, {args.since} to now", "",
             f"News rule: trades filled within 15 min of US CPI/PPI/FOMC left out ({skipped_news} in the new set).", "",
             "| market | tf | old trades | old R | old R/trade | old %/trade | new trades | new R | new R/trade | new %/trade | extra trades | extra R/trade | extra %/trade |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    keys = sorted({(k[0], k[1]) for k in stats})
    tot = defaultdict(float)
    for m, tf in keys:
        o, n = stats[(m, tf, "old")], stats[(m, tf, "new")]
        per = lambda s, f: s[f] / s["n"] if s["n"] else 0.0  # noqa: E731
        ex = (n["extra_r"] / n["extra_n"]) if n["extra_n"] else 0.0
        exp = (n["extra_pct"] / n["extra_n"]) if n["extra_n"] else 0.0
        lines.append(f"| {m} | {tf} | {int(o['n'])} | {o['r']:+.1f} | {per(o, 'r'):+.3f} | {per(o, 'pct'):+.3f}% | "
                     f"{int(n['n'])} | {n['r']:+.1f} | {per(n, 'r'):+.3f} | {per(n, 'pct'):+.3f}% | "
                     f"{int(n['extra_n'])} | {ex:+.3f} | {exp:+.3f}% |")
        for f in ("n", "r", "pct", "extra_n", "extra_r"):
            tot["o" + f] += o[f]
            tot["n" + f] += n[f]
    if tot["on"]:
        lines += ["", f"ALL: old {int(tot['on'])} trades {tot['or']:+.1f}R ({tot['or']/tot['on']:+.3f}R, "
                      f"{tot['opct']/tot['on']:+.3f}% a trade) | new {int(tot['nn'])} trades {tot['nr']:+.1f}R "
                      f"({tot['nr']/tot['nn']:+.3f}R, {tot['npct']/tot['nn']:+.3f}% a trade) | "
                      f"extra {int(tot['nextra_n'])} trades {tot['nextra_r']:+.1f}R"]
    (out / "REALERT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (out / "promoted.jsonl").open("w", encoding="utf-8") as fh:
        for row in promoted_rows:
            fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
