"""Hand-trace recent crypto trendline alerts against several candle feeds.

Lakky, 2026-10-05: "I am getting trendline alerts but my indicator draws no
trendline." For every crypto trendline alert sent since --since, this replays
trendlines.build_trendlines (the port of Pine 6b) on each feed's candles as they
stood when the alert went out, and again on the candles as they stand now, and
says whether the alerted line (same two anchor candles) exists on that feed:
live, broken, trimmed or never drawn - and if never drawn, which anchor is not a
swing there and why.

Research only: reads the runtime-state records, posts nothing, writes
research/out/trendline_trace/.

    python research/trendline_trace.py --records fib_trendline_alert_records.jsonl --since 2026-10-03
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import (  # noqa: E402
    CRYPTO, TF_SECONDS, bitunix_candles, candle_is_closed, delta_candles, monthly_from_daily,
)
from trendlines import SUPPORT, _is_pivot, build_trendlines  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "trendline_trace"
LENGTH, KEEP = config.TRENDLINE_SWING_LENGTH, config.TRENDLINES_KEEP
CCXT_FEEDS = ("okx", "binanceusdm", "bybit")
CCXT_BARS = {"4h": 3000, "1d": 1500, "1w": 300}


def utc(ts):
    return datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%d %H:%M")


def _ccxt(feed, contract, tf):
    import ccxt

    exchange = getattr(_ccxt, feed, None)
    if exchange is None:
        exchange = getattr(ccxt, feed)({"enableRateLimit": True})
        exchange.load_markets()
        setattr(_ccxt, feed, exchange)
    pair = f"{contract[:-3]}/USDT:USDT"
    if pair not in exchange.markets:
        return None
    resolution = "1d" if tf == "1M" else tf
    since = (int(time.time()) - CCXT_BARS.get(resolution, 1500) * TF_SECONDS[resolution]) * 1000
    out = {}
    while True:
        rows = exchange.fetch_ohlcv(pair, timeframe=resolution, since=since, limit=200)
        if not rows:
            break
        for row in rows:
            out[int(row[0]) // 1000] = [int(row[0]) // 1000, *map(float, row[1:5])]
        nxt = int(rows[-1][0]) + 1
        if nxt <= since or len(rows) < 2:
            break
        since = nxt
    rows = [out[k] for k in sorted(out)]
    return monthly_from_daily(rows) if tf == "1M" else rows


def fetch(feed, contract, tf, now):
    if feed in CCXT_FEEDS:
        return _ccxt(feed, contract, tf)
    get = bitunix_candles if feed == "bitunix" else delta_candles
    since = now - 2000 * 86400
    if tf in ("1d", "1M"):
        rows = get(contract, "1d", since, now)
        return monthly_from_daily(rows) if tf == "1M" else rows
    return get(contract, tf, since, now)


def gaps(rows, tf):
    if tf == "1M" or len(rows) < 2:
        return 0
    step = TF_SECONDS[tf]
    return sum(1 for a, b in zip(rows, rows[1:]) if b[0] - a[0] != step)


def trace(rows, tf, at, x1_ts, x2_ts, kind):
    """What this feed's chart shows for the alerted line as of `at`."""
    closed = [r for r in rows if candle_is_closed(CRYPTO, r[0], tf, at)]
    if len(closed) < 2 * LENGTH + 2:
        return {"status": "no data"}
    times = [r[0] for r in closed]
    highs = [r[2] for r in closed]
    lows = [r[3] for r in closed]
    closes = [r[4] for r in closed]
    index = {t: i for i, t in enumerate(times)}
    out = {"bars": len(closed), "first": utc(times[0]), "gaps": gaps(closed, tf)}
    values = lows if kind == SUPPORT else highs
    for name, ts in (("x1", x1_ts), ("x2", x2_ts)):
        i = index.get(ts)
        if i is None:
            out[name] = "candle missing"
            continue
        pivot = LENGTH <= i < len(closed) - LENGTH and _is_pivot(values, i, LENGTH, high=kind != SUPPORT)
        out[name] = f"{values[i]:.6g} {'swing' if pivot else 'NOT a swing'}"
        if not pivot and LENGTH <= i < len(closed) - LENGTH:
            window = values[i - LENGTH:i + LENGTH + 1]
            beat = max(window) if kind != SUPPORT else min(window)
            j = i - LENGTH + window.index(beat)
            out[name] += f" (beaten by {beat:.6g} at {utc(times[j])})"
    history = build_trendlines(highs, lows, closes, LENGTH, KEEP, history=True)
    now_bar = len(closed)
    match = None
    for line in history:
        if line.kind == kind and times[line.x1] == x1_ts and times[line.x2] == x2_ts:
            match = line
    if match is None:
        out["status"] = "NOT DRAWN"
    elif match.broken_at is not None:
        out["status"] = f"broken {utc(times[match.broken_at])}"
    elif match.trimmed_at is not None and match.trimmed_at < now_bar:
        out["status"] = f"trimmed {utc(times[match.trimmed_at])}"
    else:
        out["status"] = f"live @ {match.price_at(now_bar):.6g}"
    live = [l for l in build_trendlines(highs, lows, closes, LENGTH, KEEP)
            if l.alive and l.kind == kind]
    out["live_same_side"] = [f"{l.y1:.6g} {utc(times[l.x1])} -> {l.y2:.6g} {utc(times[l.x2])} "
                             f"@ {l.price_at(now_bar):.6g}" for l in live]
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    parser.add_argument("--since", default="2026-10-03")
    parser.add_argument("--feeds", default="bitunix,delta,okx,binanceusdm,bybit")
    args = parser.parse_args()
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc).timestamp()
    feeds = args.feeds.split(",")
    alerts = []
    for line in Path(args.records).read_text().splitlines():
        rec = json.loads(line)
        if rec.get("kind") == "trendline" and rec.get("market") == "crypto" and rec["sent_ts"] >= since:
            alerts.append(rec)
    now = int(time.time())
    OUT.mkdir(parents=True, exist_ok=True)
    cache, results = {}, []
    for rec in alerts:
        symbol, tf, kind = rec["symbol"], rec["tf"], rec["line"]
        _, _, _, _, x1, x2 = rec["key"].split("|")
        contract = scanner.delta_contract(symbol)
        row = {"symbol": symbol, "tf": tf, "kind": "SUP" if kind == SUPPORT else "RES",
               "sent": utc(rec["sent_ts"]), "price": rec["price"], "entry": rec["plan"]["entry"],
               "x1": utc(x1), "x2": utc(x2), "feeds": {}}
        for feed in feeds:
            key = (feed, contract, tf)
            if key not in cache:
                try:
                    cache[key] = fetch(feed, contract, tf, now)
                except Exception as error:  # noqa: BLE001 - one feed down must not stop the trace
                    cache[key] = f"error: {str(error)[:120]}"
            rows = cache[key]
            if not isinstance(rows, list):
                row["feeds"][feed] = {"status": rows or "not listed"}
                continue
            row["feeds"][feed] = {"at_alert": trace(rows, tf, rec["sent_ts"], int(x1), int(x2), kind),
                                  "now": trace(rows, tf, now, int(x1), int(x2), kind)}
        results.append(row)
        print(json.dumps(row)[:600], flush=True)
    (OUT / "trace.json").write_text(json.dumps(results, indent=1))

    lines = ["# Crypto trendline alerts traced per feed", "",
             f"Run {utc(now)} UTC. Alerts since {args.since}. Status = the alerted line on that feed's chart.", "",
             "| sent | symbol | tf | line | anchors | " + " | ".join(f"{f} at alert / now" for f in feeds) + " |",
             "|---" * (5 + len(feeds)) + "|"]
    for r in results:
        cells = []
        for f in feeds:
            v = r["feeds"][f]
            if "at_alert" in v:
                cells.append(f"{v['at_alert']['status']} / {v['now']['status']}")
            else:
                cells.append(str(v["status"])[:40])
        lines.append(f"| {r['sent']} | {r['symbol']} | {r['tf']} | {r['kind']} | {r['x1']} -> {r['x2']} | "
                     + " | ".join(cells) + " |")
    (OUT / "TRACE.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
