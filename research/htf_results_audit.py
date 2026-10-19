"""Research only - nothing here is imported by the live scanners.

Audit of every live 1W / 1M fib, trendline and S/R zone alert (lakky, 2026-10-19:
"make sure result is correct and also new rules are applied on it").

For each stored 1W/1M alert record:
1. Rules: rebuild the alert from the chart as it stood when it was sent, with
   today's code (fib_trendline_scanner.analyse), and compare the plan (entry,
   stop, target). A record today's rules would not send, or would plan
   differently, is listed; its trade is re-scored on today's plan.
2. Result, two ways: the production scorer on the same candles it uses (1d),
   and an independent scorer written here from the rules alone, on finer
   candles (crypto Delta 5m, NSE Yahoo 1h). Both are diffed with what is stored.
3. News: crypto trades filled within 15 min of a US CPI / PPI / FOMC release are
   left out of the tables (the backtest rule since 2026-10-17); NSE is closed then.

Writes research/out/htf_results_audit/: AUDIT.md, trades.csv, traces.txt.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

import fib_trendline_scanner as fts  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from config import FIB_TL_ENTRY_WAIT_BARS, FIB_TL_MAX_HOLD_BARS  # noqa: E402
from daily_backtest_summary import TRAIL_DISTANCE_R, TRAIL_START_R  # noqa: E402
from fib_trendline_data import (CRYPTO, IST, NSE, bitunix_candles, delta_candles,  # noqa: E402
                                monthly_from_daily, nse_download, HISTORY_START)
import bitunix_data  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "htf_results_audit"
DAY = 86400
# One candle of the alert's timeframe in calendar time (wait 5, hold 20 of them).
PERIOD = {"1w": 7 * DAY, "1M": 30 * DAY}

# Same calendar as research/news_window_backtest.py (New York time).
CPI = ["2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13", "2025-06-11", "2025-07-15",
       "2025-08-12", "2025-09-11", "2025-10-24", "2025-12-18", "2026-01-13", "2026-02-13", "2026-03-11",
       "2026-04-10", "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12", "2026-09-11", "2026-10-14",
       "2026-11-10", "2026-12-10"]
PPI = ["2025-01-14", "2025-02-13", "2025-03-13", "2025-04-11", "2025-05-15", "2025-06-12", "2025-07-16",
       "2025-08-14", "2025-09-10", "2025-11-25", "2026-01-14", "2026-01-30", "2026-02-27", "2026-03-18",
       "2026-04-14", "2026-05-13", "2026-06-11", "2026-07-15", "2026-08-13", "2026-09-10", "2026-10-15",
       "2026-11-13", "2026-12-15"]
FOMC = ["2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29",
        "2025-12-10", "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16",
        "2026-10-28", "2026-12-09"]
EVENT_TS = sorted(int(pd.Timestamp(f"{d} {t}", tz="America/New_York").timestamp())
                  for days, t in ((CPI, "08:30"), (PPI, "08:30"), (FOMC, "14:00")) for d in days)


def news(ts):
    return ts is not None and any(e - 900 <= ts <= e + 900 for e in EVENT_TS)


def day(ts):
    return datetime.fromtimestamp(ts, IST).strftime("%d %b %H:%M") if ts else "-"


# ----------------------------------------------------------------- independent scorer

def reference(plan, market, tf, sent_ts, candles, exit_rule):
    """From the rules alone: fill = first candle after the alert that trades the entry,
    within 5 periods; a fill candle that also trades the stop is SL. Then, candle by
    candle: the stop first (a candle touching stop and target is the stop).
    exit_rule: '1r' (trendline: stop or 1R, no limit), '2r' (fib live: breakeven
    from the candle after +0.5R, out at 2R, at 20 periods +1R or timeout),
    'trail' (fib trail: no target, 0.25R behind best once +0.5R, out at 20 periods)."""
    long = plan["side"] == "long"
    s = 1 if long else -1
    entry, sl = plan["entry"], plan["sl"]
    risk = abs(entry - sl)
    out = {"outcome": "open", "fill_ts": None, "end_ts": None, "gross": None}
    fill_at = None
    stop, best, r1, half_seen = sl, 0.0, False, False
    be = trades.break_even_stop(plan, market)
    for ts, _o, h, l, c in candles:
        if ts <= sent_ts:
            continue
        if fill_at is None:
            if ts > sent_ts + FIB_TL_ENTRY_WAIT_BARS * PERIOD[tf]:
                out.update(outcome="no fill", end_ts=ts)
                return out
            if (l <= entry) if long else (h >= entry):
                fill_at = ts
                out["fill_ts"] = ts
                if (l <= sl) if long else (h >= sl):
                    out.update(outcome="SL", end_ts=ts, gross=trades.stop_r(plan))
                    return out
            continue
        if exit_rule == "2r" and ts > fill_at + FIB_TL_MAX_HOLD_BARS * PERIOD[tf]:
            out.update(outcome="1R" if r1 else "timeout", end_ts=ts, gross=1.0 if r1 else None)
            return out
        hit = (l <= stop) if long else (h >= stop)
        up = ((h - entry) if long else (entry - l)) / risk
        if hit:
            if exit_rule == "trail":
                moved = stop != sl
                out.update(outcome="TRAIL" if moved else "SL", end_ts=ts,
                           gross=s * (trades.slipped(stop, plan) - entry) / risk)
            elif exit_rule == "2r":
                moved = stop != sl
                out.update(outcome="1R" if r1 else ("BE" if moved else "SL"), end_ts=ts,
                           gross=1.0 if r1 else (trades.break_even_r(plan, market) if moved else trades.stop_r(plan)))
            else:
                out.update(outcome="SL", end_ts=ts, gross=trades.stop_r(plan))
            return out
        if exit_rule == "trail" and ts >= fill_at + FIB_TL_MAX_HOLD_BARS * PERIOD[tf]:
            out.update(outcome="timeout", end_ts=ts, gross=s * (c - entry) / risk)
            return out
        if exit_rule == "1r":
            if up >= 1:
                out.update(outcome="1R", end_ts=ts, gross=1.0)
                return out
            continue
        best = max(best, up)
        r1 = r1 or best >= 1
        if exit_rule == "2r":
            if best >= 2:
                out.update(outcome="2R", end_ts=ts, gross=2.0)
                return out
            if best >= 0.5 and not half_seen:
                half_seen = True
                if (0.5 * risk >= s * (be - entry)):       # breakeven reachable
                    stop = be                              # from the next candle on
        else:
            if best >= TRAIL_START_R:
                level = entry + s * (best - TRAIL_DISTANCE_R) * risk
                if s * (level - stop) > 0:
                    stop = level
    if out["fill_ts"] and r1 and exit_rule == "2r":
        out["outcome"] = "1R"           # banked, 2R still possible: open
    return out


def net(gross, plan, market):
    return None if gross is None else gross - trades.COST_PCT[market] / trades.risk_pct(plan)


def stored_net(record, result):
    if not result or not result.get("resolved") or not result.get("filled"):
        return None
    return trades.booked_r(record["plan"], record["market"], result)[0]


# ----------------------------------------------------------------- data

def crypto_chart(symbol, tf, now):
    contract = scanner.delta_contract(symbol)
    if bitunix_data.uses_bitunix(symbol):
        pair = bitunix_data.pair_for(symbol, contract)
        daily = bitunix_candles(pair, "1d", HISTORY_START, now) if tf == "1M" else None
        return monthly_from_daily(daily) if tf == "1M" else bitunix_candles(pair, "1w", HISTORY_START, now)
    daily = delta_candles(contract, "1d", HISTORY_START, now) if tf == "1M" else None
    return monthly_from_daily(daily) if tf == "1M" else delta_candles(contract, "1w", HISTORY_START, now)


def rebuild(record, chart):
    """The alert today's rules would make from the chart as it was at sent_ts."""
    t = record["sent_ts"]
    candles = [c for c in chart if c[0] <= t]
    a = fts.analyse(record["market"], record["symbol"], record["tf"], candles, t, record.get("price"))
    pool = {"fib": a["fib"], "trendline": a["touch"], "zone": [z for z in a["zone"] if z.get("alert")]}
    for item in pool.get(record["kind"], []):
        if item["key"] == record["key"]:
            return item["plan"]
    return None


def same_plan(a, b):
    return (a["side"] == b["side"] and abs(a["entry"] - b["entry"]) <= abs(b["entry"]) * 1e-6
            and abs(a["sl"] - b["sl"]) <= abs(b["entry"]) * 1e-4 and a.get("target_r") == b.get("target_r"))


# ----------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    args = ap.parse_args(argv)
    state = Path(args.state)
    records = [json.loads(x) for x in (state / "fib_trendline_alert_records.jsonl").read_text().splitlines() if x.strip()]
    results = json.loads((state / "fib_trendline_results.json").read_text())
    records = [r for r in records if r["tf"] in ("1w", "1M")]
    now = int(datetime.now(timezone.utc).timestamp())
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{len(records)} live 1W/1M records")

    nse_syms = sorted({r["symbol"] for r in records if r["market"] == NSE})
    nse_tf = {tf: nse_download(nse_syms, tf) for tf in ("1w", "1M", "1d", "1h")} if nse_syms else {}
    charts, fine, daily = {}, {}, {}
    for r in records:
        key = (r["symbol"], r["tf"])
        if r["market"] == NSE:
            charts[key] = nse_tf[r["tf"]].get(r["symbol"], [])
            fine[r["symbol"]] = nse_tf["1h"].get(r["symbol"], [])
            daily[r["symbol"]] = nse_tf["1d"].get(r["symbol"], [])
            continue
        if key not in charts:
            charts[key] = crypto_chart(r["symbol"], r["tf"], now)
        if r["symbol"] not in fine:
            contract = scanner.delta_contract(r["symbol"])
            start = min(x["sent_ts"] for x in records if x["symbol"] == r["symbol"]) - DAY
            fine[r["symbol"]] = delta_candles(contract, "5m", start, now)
            daily[r["symbol"]] = delta_candles(contract, "1d", start - DAY, now)

    rows, traces = [], []
    for r in sorted(records, key=lambda x: x["sent_ts"]):
        m, tf, plan = r["market"], r["tf"], r["plan"]
        stored = results.get(r["id"], {})
        try:
            now_plan = rebuild(r, charts[(r["symbol"], tf)])
        except Exception as error:     # noqa: BLE001
            now_plan, rule = None, f"rebuild failed: {error}"
        else:
            rule = ("same" if now_plan and same_plan(now_plan, plan)
                    else "not sent today" if now_plan is None else "plan differs")
        use = now_plan or plan
        rule_exit = "1r" if use.get("target_r") == 1 else "2r"
        # Production scorer on its own candles, stored plan and today's.
        prod = trades.simulate(plan, m, tf, r["sent_ts"], daily[r["symbol"]])
        prod_now = trades.simulate(use, m, tf, r["sent_ts"], daily[r["symbol"]])
        ref = reference(use, m, tf, r["sent_ts"], fine[r["symbol"]], rule_exit)
        trail = reference(use, m, tf, r["sent_ts"], fine[r["symbol"]], "trail") if r["kind"] == "fib" else None
        row = {
            "market": m, "kind": r["kind"], "tf": tf, "symbol": r["symbol"], "sent": day(r["sent_ts"]),
            "rules": rule, "entry": plan["entry"], "sl": plan["sl"],
            "now_entry": use["entry"], "now_sl": use["sl"], "risk_pct": round(trades.risk_pct(use), 3),
            "stored": stored.get("outcome", "none"), "stored_net": stored_net(r, stored),
            "prod_rerun": prod["outcome"], "prod_now": prod_now["outcome"],
            "ref": ref["outcome"], "ref_net": net(ref["gross"], use, m),
            "ref_fill": day(ref["fill_ts"]), "ref_end": day(ref["end_ts"]),
            "trail": trail["outcome"] if trail else "", "trail_net": net(trail["gross"], use, m) if trail else None,
            "news": m == CRYPTO and news(ref["fill_ts"]),
        }
        row["match"] = (row["stored"] == row["prod_rerun"] or row["stored"] == "none") and (
            row["ref"] == row["prod_now"] or (row["ref"] in ("open", "1R") and row["prod_now"] in ("open", "1R")))
        rows.append(row)
        if not row["match"] or rule != "same":
            traces.append(f"{m} {r['kind']} {tf} {r['symbol']} sent {row['sent']} rules={rule}\n"
                          f"  stored plan {plan}\n  today plan {use}\n"
                          f"  stored {row['stored']} | prod re-run {row['prod_rerun']} | prod today-plan {row['prod_now']}"
                          f" | reference {row['ref']} fill {row['ref_fill']} end {row['ref_end']}\n")
    with (OUT / "trades.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT / "traces.txt").write_text("\n".join(traces) or "no differences\n")

    def table(col_net, col_out, label):
        groups = defaultdict(list)
        for x in rows:
            groups[(x["market"], x["kind"], x["tf"])].append(x)
        lines = [f"### {label}", "", "| Group | Alerts | Not filled | Open | News | Closed | R/trade | %/trade |",
                 "|---|---|---|---|---|---|---|---|"]
        for k in sorted(groups):
            g = groups[k]
            closed = [x for x in g if x[col_net] is not None and not x["news"]]
            nf = sum(1 for x in g if x[col_out] in ("no fill", "none"))
            op = sum(1 for x in g if x[col_out] in ("open", "1R") and x[col_net] is None)
            nw = sum(1 for x in g if x["news"])
            rr = sum(x[col_net] for x in closed) / len(closed) if closed else None
            pp = sum(x[col_net] * x["risk_pct"] for x in closed) / len(closed) if closed else None
            lines.append(f"| {k[0]} {k[1]} {k[2]} | {len(g)} | {nf} | {op} | {nw} | {len(closed)} | "
                         + (f"{rr:+.2f}R | {pp:+.2f}% |" if closed else "- | - |"))
        return lines

    n_rule = defaultdict(int)
    for x in rows:
        n_rule[x["rules"]] += 1
    md = ["# 1W / 1M live alerts audit", "",
          f"Records: {len(rows)}. Rules today vs as sent: " + ", ".join(f"{k} {v}" for k, v in n_rule.items()),
          f"Result checks agree: {sum(x['match'] for x in rows)} / {len(rows)} (diffs in traces.txt)", ""]
    md += table("ref_net", "ref", "Today's rules, independent scorer (crypto 5m, NSE 1h)") + [""]
    md += table("stored_net", "stored", "As stored (what the cards / journal read)") + [""]
    fib_rows = [x for x in rows if x["kind"] == "fib"]
    if fib_rows:
        rows_backup = rows
        rows = [dict(x, ref_net=x["trail_net"], ref=x["trail"]) for x in fib_rows]
        md += table("ref_net", "ref", "Fibs with the trail exit (draft, not live yet)") + [""]
        rows = rows_backup
    (OUT / "AUDIT.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print((OUT / "traces.txt").read_text()[:20000])


if __name__ == "__main__":
    main()
