"""Daily backtest of the live fib and trendline alerts, posted to the daily-backtest channel.

Every fib and trendline-touch alert fib_trendline_scanner.py sends is written to
fib_trendline_alert_records.jsonl with its entry and SL. Once a day, on the first
scanner pass after REPORT_HOUR IST, this scores every alert not yet resolved
(fib_trendline_trades.simulate, on finer candles than the alert's) and posts one
card for fib and one for trendline: yesterday's alerts and how they went, broken
down by timeframe, side, fib zone, stop size and hour. One day only, no running totals.

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
DISCORD_LIMIT = 4000     # an embed description holds 4096


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
    # NSE in one Yahoo call per resolution, not one per stock: pending 1W/1M
    # alerts stay open for months, so the list only grows.
    nse = {}
    for resolution in {res for m, _, res in groups if m == NSE}:
        symbols = sorted({s for m, s, res in groups if m == NSE and res == resolution})
        try:
            nse[resolution] = nse_download(symbols, resolution)
        except Exception as error:     # noqa: BLE001 - retried tomorrow
            print(f"daily report: NSE {resolution} download failed: {error}")
    for (market, symbol, resolution), rows in groups.items():
        try:
            if market == NSE:
                candles = nse.get(resolution, {}).get(symbol, [])
            else:
                candles = eval_candles(market, symbol, resolution, min(r["sent_ts"] for r in rows), now)
        except Exception as error:     # noqa: BLE001 - retried tomorrow
            print(f"daily report: no {resolution} candles for {symbol}: {error}")
            continue
        if not candles:
            continue
        for record in rows:
            results[record["id"]] = trades.simulate(record["plan"], market, record["tf"], record["sent_ts"], candles)
    return results


def ist_date(ts):
    return datetime.fromtimestamp(ts, IST).date()


def tally(items):
    """Counts and net R for (record, result) pairs.

    +1R is every trade that reached 1R and not 2R, whatever it did afterwards.
    Net R is after costs under the two bookings fib_trendline_trades._row uses:
    out at 1R, or held for 2R (where a 1R trade that then stops is a loss).
    """
    t = defaultdict(int)
    net1 = net2 = 0.0
    for record, x in items:
        t["alerts"] += 1
        if not x["filled"]:
            t["no_fill" if x["outcome"] == "no fill" else "waiting"] += 1
            continue
        t["entries"] += 1
        t[{"SL": "sl", "1R": "r1", "2R": "r2", "timeout": "timeout"}.get(x["outcome"], "running")] += 1
        cost_r = trades.COST_PCT[record["market"]] / trades.risk_pct(record["plan"])
        if x["r1"]:
            net1 += 1 - cost_r
        elif x["sl"]:
            net1 += -1 - cost_r
        if x["r2"]:
            net2 += 2 - cost_r
        elif x["sl"]:
            net2 += -1 - cost_r
    wins, decided = t["r1"] + t["r2"], t["r1"] + t["r2"] + t["sl"]
    t["win"] = f"{wins / decided * 100:.1f}%" if decided else "N/A"
    t["net1"], t["net2"] = net1, net2
    return t


OUTCOME_PARTS = (("sl", "SL"), ("r1", "+1R"), ("r2", "+2R"), ("timeout", "Timeout"), ("running", "Running"))


def _row(label, items):
    t = tally(items)
    parts = [f"Alerts {t['alerts']}"]
    if not t["entries"]:
        parts.append("waiting" if t["waiting"] else "no fill")
        return f"{label} - " + " | ".join(parts)
    parts.append(f"Entries {t['entries']}")
    parts += [f"{name} {t[key]}" for key, name in OUTCOME_PARTS if t[key]]
    if t["win"] != "N/A":
        parts.append(t["win"])
    return f"{label} - " + " | ".join(parts)


def _block(title, groups):
    rows = [_row(label, items) for label, items in groups if items]
    return ["", title, *rows] if rows else []


def _day_block(day):
    if not day:
        return ["No alerts."]
    t = tally(day)
    head = [f"Alerts {t['alerts']}", f"Entries {t['entries']}"]
    head += [f"{name} {t[key]}" for key, name in (("no_fill", "No Fill"), ("waiting", "Waiting")) if t[key]]
    lines = [" · ".join(head)]
    counted = " · ".join(f"{name} {t[key]}" for key, name in OUTCOME_PARTS if t[key])
    if counted:
        lines.append(counted)
    lines.append(f"Win rate {t['win']} · TOTAL {trades.r(t['net1'])} booking 1R / {trades.r(t['net2'])} booking 2R")
    return lines


STOP_BUCKETS = (("under 0.5%", 0, 0.5), ("0.5 - 1%", 0.5, 1), ("1 - 2%", 1, 2), ("over 2%", 2, float("inf")))


def build_card(kind, title, report_day, joined):
    """One card for the report day's alerts only: the result on top, then broken down."""
    if not any(r["kind"] == kind for r, _ in joined):
        return None
    items = [(r, x) for r, x in joined if r["kind"] == kind and ist_date(r["sent_ts"]) == report_day]
    lines = [f"{title} BACKTEST · {report_day:%d %b %Y}".upper(), ""]
    lines += _day_block(items)
    lines += _block("TIMEFRAME", [
        (f"{TF_LABEL[tf]} {market.upper()}", [(r, x) for r, x in items if r["market"] == market and r["tf"] == tf])
        for market in (CRYPTO, NSE) for tf in TF_LABEL
    ])
    sides = (("long", "BUY"), ("short", "SELL")) if kind == "fib" else \
        (("long", "BUY (support)"), ("short", "SELL (resistance)"))
    lines += _block("SIDE", [(name, [(r, x) for r, x in items if r["plan"]["side"] == side]) for side, name in sides])
    if kind == "fib":
        zones = sorted({r["zone"] for r, _ in items if r.get("zone") is not None})
        lines += _block("ZONE", [(f"Zone {z}", [(r, x) for r, x in items if r.get("zone") == z]) for z in zones])
        # A trendline's stop is a fixed % per timeframe, so buckets say nothing there.
        lines += _block("STOP SIZE", [
            (name, [(r, x) for r, x in items if x["filled"] and lo <= trades.risk_pct(r["plan"]) < hi])
            for name, lo, hi in STOP_BUCKETS
        ])
    for market in (CRYPTO, NSE):
        hours = defaultdict(list)
        for r, x in items:
            if r["market"] == market:
                hours[datetime.fromtimestamp(r["sent_ts"], IST).hour].append((r, x))
        # An hour with no entry is a line saying nothing happened.
        lines += _block(f"HOURS (IST) · {market.upper()}", [
            (f"{hour:02d}:00", hours[hour]) for hour in sorted(hours) if any(x["filled"] for _, x in hours[hour])
        ])
    return "\n".join(lines)


def build_report(report_day, records, results):
    """The cards to post, fib first; a kind with no alerts yet has none."""
    joined = [(r, results[r["id"]]) for r in records if r["id"] in results]
    cards = [build_card(kind, title, report_day, joined) for kind, title in (("fib", "FIB"), ("trendline", "TRENDLINE"))]
    return [card for card in cards if card]


def send_card(text):
    """Post one card as an embed, like the crypto and NSE daily cards in the same channel."""
    url = scanner.get_env_or_config(WEBHOOK_ENV, "")
    if not url:
        return
    payload = {"embeds": [{"description": part.rstrip(), "color": 3447003} for part in chunks(text)[:10]]}
    for attempt in range(4):
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code != 429 or attempt == 3:
            response.raise_for_status()
            return
        try:
            wait = float(response.json().get("retry_after", 1))
        except (ValueError, AttributeError):
            wait = 1.0
        time.sleep(max(0.25, min(wait, 15.0)))


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
    cards = build_report(report_day, records, results)
    text = "\n\n".join(cards)
    print(text)
    if send:
        for card in cards:
            send_card(card)
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
