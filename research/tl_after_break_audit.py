"""Trendline alerts sent on a line a closed candle had already broken.

Lakky, 2026-10-10, GLENMARK 1D: the Oct 8 candle closed at ~2192, far under
the Jun 17 -> Aug 3 support (~2249), yet the bot sent TL BUY on that line on
Oct 9 11:53 IST and no TL BROKEN. The chart (Pine) ends the line on Oct 8.

1. GLENMARK: Yahoo's 1d rows for Oct 5-9 next to the daily close rebuilt from
   1h candles, and the line replayed on today's candles cut at the alert time.
2. Every NSE trendline alert since --since: replay today's candles up to the
   alert and flag the ones whose line was already broken (closed candle
   through it) - with today's data. Same for crypto on Bitunix.

    python research/tl_after_break_audit.py --records /tmp/tl_records.jsonl --since 2026-10-01
"""
import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE, candle_is_closed, nse_download  # noqa: E402
from trendlines import build_trendlines  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "tl_after_break"


def ist(ts):
    return datetime.fromtimestamp(ts, IST).strftime("%Y-%m-%d %H:%M")


def check(market, rec, candles, window=False):
    """'ok' / 'broken <date>' / 'no line' for one alert, on these candles.
    window=False is the live rule when the alert went out (v12.7.8)."""
    sent = rec["sent_ts"]
    _, symbol, tf, kind, t1, t2 = rec["key"].split("|")
    upto = [c for c in candles if c[0] < sent]
    closed = upto if upto and candle_is_closed(market, upto[-1][0], tf, sent) else upto[:-1]
    times = [c[0] for c in closed]
    lines = build_trendlines([c[2] for c in closed], [c[3] for c in closed], [c[4] for c in closed],
                             config.TRENDLINE_SWING_LENGTH, config.TRENDLINES_KEEP, history=True,
                             check_confirm_window=window)
    match = [l for l in lines if l.kind == int(kind) and times[l.x1] == int(t1) and times[l.x2] == int(t2)]
    if not match:
        return "no line", None
    line = match[-1]
    if line.broken_at is None:
        return "ok", line
    return f"broken {ist(times[line.broken_at])[:10]} close {closed[line.broken_at][4]:.2f} " \
           f"line {line.price_at(line.broken_at):.2f}", line


def daily_from_hourly(hourly):
    out = {}
    for ts, _o, _h, _l, c in hourly:
        out[datetime.fromtimestamp(ts, IST).strftime("%Y-%m-%d")] = c
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--records", required=True)
    p.add_argument("--since", default="2026-10-01")
    a = p.parse_args()
    start = datetime.fromisoformat(a.since).replace(tzinfo=IST).timestamp()
    recs = [json.loads(l) for l in open(a.records) if l.strip()]
    recs = [r for r in recs if r.get("kind") == "trendline" and r.get("sent_ts", 0) >= start]
    out = []

    d1 = nse_download(["GLENMARK.NS"], "1d").get("GLENMARK.NS", [])
    h1 = nse_download(["GLENMARK.NS"], "1h").get("GLENMARK.NS", [])
    rebuilt = daily_from_hourly(h1)
    out += ["# GLENMARK 1d: Yahoo daily vs close rebuilt from 1h", "", "date | open | high | low | close | 1h close",
            "---|---|---|---|---|---"]
    for c in d1[-8:]:
        day = datetime.fromtimestamp(c[0], IST).strftime("%Y-%m-%d")
        out.append(f"{day} {datetime.fromtimestamp(c[0], IST).strftime('%H:%M %z')} | {c[1]:.2f} | {c[2]:.2f} | "
                   f"{c[3]:.2f} | {c[4]:.2f} | {rebuilt.get(day, float('nan')):.2f}")
    out.append("")
    for r in recs:
        if r["symbol"] == "GLENMARK.NS" and r["tf"] == "1d":
            status, _ = check(NSE, r, d1)
            out.append(f"GLENMARK 1d alert {ist(r['sent_ts'])} entry {r['plan']['entry']:.2f} {r['key']}: {status}")

    out += ["", f"# All trendline alerts since {a.since}, replayed on today's candles", ""]
    nse_syms = sorted({r["symbol"] for r in recs if r["market"] == NSE})
    nse_tfs = sorted({r["tf"] for r in recs if r["market"] == NSE})
    charts = {tf: nse_download(nse_syms, tf) for tf in nse_tfs}
    crypto = {}
    try:
        from fib_trendline_data import crypto_charts
        csyms = sorted({r["symbol"] for r in recs if r["market"] == CRYPTO})
        ctfs = sorted({r["tf"] for r in recs if r["market"] == CRYPTO})
        for s in csyms:
            try:
                crypto[s] = crypto_charts(s, ctfs, time.time(), source="bitunix")
            except Exception as error:  # noqa: BLE001
                print(f"crypto {s}: {error}")
    except ImportError:
        pass
    tally = Counter()
    bad = []
    for r in recs:
        candles = charts.get(r["tf"], {}).get(r["symbol"]) if r["market"] == NSE else \
            (crypto.get(r["symbol"]) or {}).get(r["tf"])
        if not candles:
            tally[(r["market"], r["tf"], "no data")] += 1
            continue
        status, _ = check(r["market"], r, candles)
        if status == "ok" and check(r["market"], r, candles, window=True)[0].startswith("broken"):
            status = "window-" + check(r["market"], r, candles, window=True)[0]
        tally[(r["market"], r["tf"], status.split()[0])] += 1
        if "broken" in status:
            bad.append(f"{r['market']} {r['symbol']} {r['tf']} sent {ist(r['sent_ts'])} entry "
                       f"{r['plan']['entry']:.2f}: {status}")
    out += ["market | tf | status | alerts", "---|---|---|---"]
    out += [f"{m} | {tf} | {s} | {n}" for (m, tf, s), n in sorted(tally.items())]
    out += ["", "## Alerts on an already broken line", ""] + bad
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "RESULTS.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
