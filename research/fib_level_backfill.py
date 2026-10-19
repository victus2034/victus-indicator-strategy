"""Label every fib alert since Oct 1 with its L1-L4 levels and score the what-ifs now
(lakky, 2026-10-19: "make previous alerts correct, start from Oct").

Fib records saved before 2026-10-12 carry only the plan; this adds what newer ones
have - `base`, `top`, `levels` {L1..L4} - plus `level`, the level the alert entered at
(L3 for a deeper-zone alert), worked out from the key and the entry exactly as
fib_level_whatif.geometry does. Then fib_level_whatif.score_levels fills
fib_level_results.json for the journal's Fib levels tab, instead of waiting for the
next daily report. Nothing posts and no live alert changes.

    python research/fib_level_backfill.py --state DIR [--since 2026-10-01] [--apply]

Dry run by default. --apply writes the two files in DIR and keeps a backup of the
records file (fib_trendline_alert_records.pre_levels_2026-10-19.jsonl).
"""
import argparse
import json
import shutil
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fib_level_whatif as whatif  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
from fib_trendline_data import TF_SECONDS  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
RECORDS = "fib_trendline_alert_records.jsonl"
RESULTS = "fib_trendline_results.json"
LEVELS = "fib_level_results.json"
BACKUP = "fib_trendline_alert_records.pre_levels_2026-10-19.jsonl"
OUT = ROOT / "research" / "out" / "fib_levels"

# US CPI / PPI / FOMC, New York time (calendar of research/news_window_backtest.py,
# PR #54). A trade filling within 15 minutes of one is left out of the table.
WINDOW_MIN = 15
CPI = ["2026-09-11", "2026-10-14", "2026-11-10", "2026-12-10"]
PPI = ["2026-09-10", "2026-10-15", "2026-11-13", "2026-12-15"]
FOMC = ["2026-09-16", "2026-10-28", "2026-12-09"]
NY = timezone(timedelta(hours=-4))       # EDT through Nov 1 2026; EST after
NY_WINTER = timezone(timedelta(hours=-5))


def _ny(day, hhmm):
    tz = NY if day < "2026-11-01" else NY_WINTER
    return int(datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M").replace(tzinfo=tz).timestamp())


EVENT_TS = sorted([_ny(d, "08:30") for d in CPI + PPI] + [_ny(d, "14:00") for d in FOMC])


def near_news(result, tf, market):
    """True when the fill candle overlaps 15 min either side of a release."""
    if not result.get("filled") or not result.get("fill_ts"):
        return False
    start = result["fill_ts"]
    end = start + TF_SECONDS[trades.EVAL_RESOLUTION[market][tf]]
    w = WINDOW_MIN * 60
    return any(start <= ev + w and end > ev - w for ev in EVENT_TS)


def label(record):
    """Adds base/top/levels/level to a fib record that lacks them. True if changed."""
    geo = whatif.geometry(record)
    if not geo:
        return False
    _origin, top, levels = geo
    zone = int(str(record["key"]).split("|")[6])
    changed = False
    if not isinstance(record.get("levels"), dict):
        span = (levels["L3"] - top) / whatif.RATIOS["L3"]
        record["top"] = top
        record["base"] = top + span
        record["levels"] = levels
        changed = True
    entry_level = whatif.ENTRY_LEVEL.get(zone)
    if entry_level and record.get("level") != entry_level:
        record["level"] = entry_level
        changed = True
    return changed


def check_geometry(records):
    """Largest relative gap between the key-derived levels and the levels newer
    records saved themselves - the derivation used for older records."""
    worst = 0.0
    for r in records:
        if r.get("kind") != "fib" or not isinstance(r.get("levels"), dict):
            continue
        saved = dict(r)
        saved.pop("levels")
        geo = whatif.geometry(saved)
        if not geo:
            continue
        for k, v in geo[2].items():
            worst = max(worst, abs(v - r["levels"][k]) / abs(r["levels"][k]))
    return worst


def table(records, results, levels):
    rows = defaultdict(lambda: {"n": 0, "filled": 0, "r": [], "pct": [], "news": 0})
    for rec in records:
        geo = whatif.geometry(rec)
        if not geo:
            continue
        group = ("Crypto" if rec["market"] == "crypto" else "NSE") + (" 4H" if rec["tf"] == "4h" else " 1D+")
        per_level = {"L3": (rec["plan"], results.get(rec["id"]))}
        for k in whatif.WHAT_IF:
            y = (levels.get(rec["id"]) or {}).get(k)
            if y:
                per_level[k] = ({"side": rec["plan"]["side"], "entry": y["entry"], "sl": rec["plan"]["sl"]}, y)
        for k, (plan, res) in per_level.items():
            row = rows[(group, k)]
            row["n"] += 1
            if not res or not res.get("filled"):
                continue
            if near_news(res, rec["tf"], rec["market"]):
                row["news"] += 1
                continue
            row["filled"] += 1
            if "sl" not in res:
                continue
            net = trades.booked_r(plan, rec["market"], res)[1]
            if net is None:
                continue
            row["r"].append(net)
            row["pct"].append(net * trades.risk_pct(plan))
    lines = ["| Group | Level | Alerts | Filled | Closed | R / trade | % / trade | Total R |",
             "|---|---|---|---|---|---|---|---|"]
    for group in ("Crypto 4H", "Crypto 1D+", "NSE 4H", "NSE 1D+"):
        for k in ("L1", "L2", "L3", "L4"):
            row = rows.get((group, k))
            if not row:
                continue
            n = len(row["r"])
            avg_r = f"{sum(row['r']) / n:+.2f}" if n else "-"
            avg_p = f"{sum(row['pct']) / n:+.2f}%" if n else "-"
            tot = f"{sum(row['r']):+.1f}" if n else "-"
            mark = " (live)" if k == "L3" else ""
            lines.append(f"| {group} | {k}{mark} | {row['n']} | {row['filled']} | {n} | {avg_r} | {avg_p} | {tot} |")
    news = sum(v["news"] for v in rows.values())
    return "\n".join(lines), news


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True, type=Path)
    ap.add_argument("--since", default="2026-10-01")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    since = int(datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=IST).timestamp())

    rec_path = args.state / RECORDS
    lines = rec_path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    gap = check_geometry(records)

    fibs = [r for r in records if r.get("kind") == "fib" and r.get("sent_ts", 0) >= since]
    had = sum(1 for r in fibs if isinstance(r.get("levels"), dict))
    changed = {r["id"] for r in fibs if label(r)}
    relabelled = len(changed)
    no_geo = sum(1 for r in fibs if not whatif.geometry(r))

    try:
        results = json.loads((args.state / RESULTS).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        results = {}
    try:
        old_levels = json.loads((args.state / LEVELS).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        old_levels = {}

    from fib_trendline_daily_report import eval_candles
    now = int(time.time())
    levels = whatif.score_levels(fibs, dict(old_levels), now, eval_candles)

    status = defaultdict(int)
    for r in fibs:
        for k in whatif.WHAT_IF:
            y = (levels.get(r["id"]) or {}).get(k) or {}
            status[(k, y.get("outcome", "missing"))] += 1

    tbl, news = table(fibs, results, levels)
    first = datetime.fromtimestamp(min(r["sent_ts"] for r in fibs), IST).strftime("%d %b")
    report = [
        f"# Fib alerts since {args.since}: L1-L4 labels and what-ifs",
        "",
        f"- Fib alerts since {args.since}: {len(fibs)} (first {first} IST); {had} already had levels, "
        f"{relabelled} labelled now (levels and/or `level`), {no_geo} without a usable key.",
        f"- Key-derived levels vs the levels newer records saved: largest gap {gap * 100:.4f}%.",
        f"- What-if outcomes: " + ", ".join(f"{k} {o}: {n}" for (k, o), n in sorted(status.items())),
        f"- Left out of the table: {news} trades filling within 15 min of US CPI/PPI/FOMC.",
        "",
        "L3 is the live alert's own result. L1/L2/L4 are what-ifs: same alert, same stop, entered at that level "
        "from the first time price came within 0.75% of it; 2R target with breakeven at +0.5R, fees and slippage.",
        "",
        tbl,
        "",
        "Applied." if args.apply else "Dry run - nothing written.",
    ]
    text = "\n".join(report)
    print(text)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "BACKFILL.md").write_text(text + "\n", encoding="utf-8")

    if args.apply:
        shutil.copyfile(rec_path, args.state / BACKUP)
        by_id = {r["id"]: r for r in fibs if r["id"] in changed}
        out = []
        for line in lines:
            if not line.strip():
                continue
            rid = json.loads(line).get("id")
            out.append(json.dumps(by_id[rid]) if rid in by_id else line)
        rec_path.write_text("\n".join(out) + "\n", encoding="utf-8")
        (args.state / LEVELS).write_text(json.dumps(levels, indent=1, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
