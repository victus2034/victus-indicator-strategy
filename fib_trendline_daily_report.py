"""Daily backtest of the live fib and trendline alerts, posted to the daily-backtest channel.

Every fib and trendline-touch alert fib_trendline_scanner.py sends is written to
fib_trendline_alert_records.jsonl with its entry and SL. Once a day, on the first
scanner pass after REPORT_HOUR IST, this scores every alert not yet resolved
(fib_trendline_trades.simulate, on finer candles than the alert's) and posts:
yesterday's alerts and how they went, plus the running totals per timeframe.

A 1W or 1M alert can take months to resolve, so it shows as "open" until it does;
its result is kept in RESULTS_FILE and never re-scored once final.

    python fib_trendline_daily_report.py                 # score and print, send nothing
    python fib_trendline_daily_report.py --send          # score and post
    python fib_trendline_daily_report.py --date 2026-09-29
"""
import argparse
import json
import os
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

import fib_trendline_trades as trades
import scanner
from fib_trendline_data import CRYPTO, IST, NSE, TF_LABEL, TF_SECONDS, delta_candles, nse_download

RECORDS_FILE = Path(__file__).with_name(os.getenv("VICTUS_FIB_TL_RECORDS_FILE", "fib_trendline_alert_records.jsonl"))
RESULTS_FILE = Path(__file__).with_name(os.getenv("VICTUS_FIB_TL_RESULTS_FILE", "fib_trendline_results.json"))
WEBHOOK_ENV = "DISCORD_DAILY_BACKTEST_WEBHOOK_URL"
REPORT_KEY = "__daily_report__"
REPORT_HOUR = 8
DISCORD_LIMIT = 1900


def load_records():
    try:
        with RECORDS_FILE.open("r", encoding="utf-8") as file:
            return [json.loads(line) for line in file if line.strip()]
    except OSError:
        return []


def load_results():
    try:
        with RESULTS_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


def save_results(results):
    tmp = RESULTS_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=1, sort_keys=True)
    os.replace(tmp, RESULTS_FILE)


def eval_candles(market, symbol, resolution, start, now):
    if market == CRYPTO:
        contract = scanner.delta_contract(symbol)
        return delta_candles(contract, resolution, start - TF_SECONDS[resolution], now) if contract else []
    return nse_download([symbol], resolution).get(symbol, [])


def score(records, results, now):
    """Simulate every record without a final result; returns the updated results."""
    pending = [r for r in records if not results.get(r["id"], {}).get("resolved")]
    groups = defaultdict(list)
    for record in pending:
        resolution = trades.EVAL_RESOLUTION[record["market"]][record["tf"]]
        groups[(record["market"], record["symbol"], resolution)].append(record)
    for (market, symbol, resolution), rows in groups.items():
        try:
            candles = eval_candles(market, symbol, resolution, min(r["sent_ts"] for r in rows), now)
        except Exception as error:     # noqa: BLE001 - retried tomorrow
            print(f"daily report: no {resolution} candles for {symbol}: {error}")
            continue
        for record in rows:
            results[record["id"]] = trades.simulate(record["plan"], market, record["tf"], record["sent_ts"], candles)
    return results


def ist_date(ts):
    return datetime.fromtimestamp(ts, IST).date()


def _day_line(label, items):
    count = defaultdict(int)
    for _, result in items:
        count[result["outcome"]] += 1
    parts = [f"{o} {count[o]}" for o in trades.OUTCOMES if count[o]]
    return f"{label}: {len(items)} alert{'s' * (len(items) != 1)} - " + (", ".join(parts) or "none")


def build_report(report_day, records, results):
    joined = [(r, results[r["id"]]) for r in records if r["id"] in results]
    lines = [f"**Fib + Trendline backtest - {report_day:%d %b %Y}**",
             "Fib: entry at the zone edge, SL inner 0.55 | Trendline: entry at the line, SL beyond it | "
             "1R/2R targets, a candle hitting SL and target counts as SL"]
    for kind, title in (("fib", "FIB"), ("trendline", "TRENDLINE")):
        day = [(r, x) for r, x in joined if r["kind"] == kind and ist_date(r["sent_ts"]) == report_day]
        lines.append(f"\n**{title}**")
        if not day:
            lines.append("Yesterday: no alerts")
        for market in (CRYPTO, NSE):
            for tf in TF_LABEL:
                items = [(r, x) for r, x in day if r["market"] == market and r["tf"] == tf]
                if items:
                    lines.append(_day_line(f"{TF_LABEL[tf]} {market.upper()}", items))
        rows = trades.summarise([
            {"market": r["market"], "kind": r["kind"], "tf": r["tf"], "plan": r["plan"], "result": x}
            for r, x in joined if r["kind"] == kind
        ])
        if rows:
            lines.append("All alerts so far (win @1R | win @2R | avg net R booking 1R / 2R):")
            for row in rows:
                lines.append(
                    f"`{TF_LABEL[row['tf']]:>3} {row['market'].upper():<6}` {row['alerts']} alerts, "
                    f"{row['filled']} filled | {trades.pct(row['win_1r'])} | {trades.pct(row['win_2r'])} | "
                    f"{trades.r(row['net_r_1r'])} / {trades.r(row['net_r_2r'])} | open {row['open']}"
                )
    return "\n".join(lines)


def chunks(text):
    out, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > DISCORD_LIMIT:
            out.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        out.append(current)
    return out


def run(report_day, now, send=False):
    records = load_records()
    if not records:
        print("daily report: no fib/trendline alerts recorded yet")
        return None
    results = score(records, load_results(), now)
    save_results(results)
    text = build_report(report_day, records, results)
    print(text)
    if send:
        for part in chunks(text):
            scanner.send_discord_message(part, webhook_env_name=WEBHOOK_ENV, webhook_config_value="")
    return text


def maybe_send(state, now):
    """Called by the scanner every pass: posts once a day, after REPORT_HOUR IST."""
    local = datetime.fromtimestamp(now, IST)
    if local.hour < REPORT_HOUR or state.get(REPORT_KEY) == local.date().isoformat():
        return
    if not os.getenv(WEBHOOK_ENV, "").strip():
        print(f"{WEBHOOK_ENV} is not configured - daily fib/trendline report skipped")
        return
    try:
        run(local.date() - timedelta(days=1), now, send=True)
    except requests.RequestException as error:
        print(f"daily fib/trendline report failed, will retry next pass: {error}")
        return
    state[REPORT_KEY] = local.date().isoformat()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", help="report day, YYYY-MM-DD (default yesterday IST)")
    parser.add_argument("--send", action="store_true", help="post to Discord")
    args = parser.parse_args(argv)
    now = time.time()
    day = date.fromisoformat(args.date) if args.date else ist_date(now) - timedelta(days=1)
    run(day, now, send=args.send)


if __name__ == "__main__":
    main()
