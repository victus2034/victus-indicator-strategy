"""Rebuild the fib and trendline backtest under today's rules (lakky, 2026-10-27: "Do it").

Same idea as research/zone_rebuild.py: the journal's Fib and Trendline tabs read
the scanner's stored alerts, graded under the rules of their day (L3-only fibs
before 20 Oct, 0.75% band on 1W/1M before 21 Oct, older fib kill and trendline
rules, coins since dropped). This replays every fib and trendline touch alert
today's scanner would have sent, Sep 1 to now, on today's watchlists, with
fib_trendline_backtest.replay (the history backtest the live rules are
checked against):

  - fibs at every live level (config.FIB_ALERT_LEVELS: 4H L2-L4, 1D+ L1-L4),
    each once, the fib's one stop; no alert once the candle reached the entry
  - trendlines: v12.7.9 lines, lakky's candle stop, one 1R target, no hold
    limit; no alert once the candle reached the line
  - 0.75% band, 3% on 1W / 1M; crypto 01:00-08:00 IST hold
  - crypto and xStocks on Bitunix from HISTORY_START (as live), XAUT / SLVON on
    Delta, NSE on Yahoo
  - scored by fib_trendline_trades.simulate - the daily report's own scoring

TL BROKEN alerts are added as trades too (lakky, 2026-10-31: "i trade only when a
candle closes below or above the trendline ... sl is above the previous candle"):
support closed below -> sell, resistance closed above -> buy, entered at the break
close (the next candle's open), stop past the candle before the break candle, one 1R
target, no hold limit (tl_broken_alert_backtest, rule BREAK_RULE). Kind "trendline",
key "tl|SYM|tf|line|x1|x2|br" with line = the broken line (0 support, 1 resistance),
so the journal's SP TL BR / RS TL BR types pick them up. A fill within 15 min of US
CPI / PPI / FOMC is flagged news_window and left out (backtest standard).

Writes OUT: fibtl_rebuild_records.jsonl (like fib_trendline_alert_records.jsonl),
fibtl_rebuild_results.json (like fib_trendline_results.json),
fibtl_rebuild_meta.json and SUMMARY.md. The workflow's -apply part copies the
three data files to scanner-runtime-state (new files; no live file changes).

    PYTHONPATH=research python research/fibtl_rebuild.py --since 2026-09-01 --state /tmp/rt
"""
from __future__ import annotations

import argparse
import bisect
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_data  # noqa: E402
import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, HISTORY_START, IST, NSE, TF_SECONDS, bitunix_candles, delta_candles, monthly_from_daily  # noqa: E402
import tl_broken_alert_backtest as tlb  # noqa: E402
from zone_rebuild import jsonable, news_overlap  # noqa: E402

BREAK_RULE = (("at close, SL candle before break, 1R", "close", "before", 1),)

OUT = Path(__file__).resolve().parent / "out" / "fibtl_rebuild"
TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)


def crypto_data(symbol, now, since):
    """The live charts: Bitunix (Delta for XAUT / SLVON) from HISTORY_START, eval candles from `since`."""
    contract = scanner.delta_contract(symbol)
    if contract is None:
        return None
    if bitunix_data.uses_bitunix(symbol):
        pair = bitunix_data.pair_for(symbol, contract)
        tag, fetch = pair, lambda res, start: bitunix_candles(pair, res, start, now)
    else:
        tag, fetch = contract, lambda res, start: delta_candles(contract, res, start, now)

    def get(res, start):
        return fbt._cached(f"ft_{tag}_{res}_{int(start) // 86400}", lambda: fetch(res, start))

    daily = get("1d", HISTORY_START)
    four = get("4h", HISTORY_START)
    base = {"4h": four, "1d": daily, "1w": get("1w", HISTORY_START), "1M": monthly_from_daily(daily)}
    evals = {"1d": daily, "4h": four, "1h": get("1h", since - 3 * 86400)}
    return base, evals


def replay_all(since, now, limit):
    got, opens = [], {}
    started = time.time()

    def keep(market, symbol, evals):
        for res, candles in evals.items():
            opens[(market, symbol, res)] = ([c[0] for c in candles], [c[1] for c in candles])

    def one(symbol):
        try:
            data = crypto_data(symbol, now, since)
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            return symbol, None, []
        if not data:
            print(f"crypto {symbol}: no chart")
            return symbol, None, []
        base, evals = data
        res = []
        for tf in TIMEFRAMES:
            res += fbt.replay(CRYPTO, symbol, tf, base[tf], evals[trades.EVAL_RESOLUTION[CRYPTO][tf]], now)
            res += tlb.breaks(CRYPTO, symbol, tf, base[tf], evals[trades.EVAL_RESOLUTION[CRYPTO][tf]], now, since,
                              BREAK_RULE)
        print(f"crypto {symbol}: {len(res)} alerts ({time.time() - started:.0f}s)")
        return symbol, evals, res

    with ThreadPoolExecutor(max_workers=4) as pool:
        for symbol, evals, res in pool.map(one, list(config.WATCHLIST)[: limit or None]):
            if evals:
                keep(CRYPTO, symbol, evals)
            got += res

    import nse_scanner
    for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()[: limit or None]).items():
        keep(NSE, symbol, evals)
        for tf in TIMEFRAMES:
            got += fbt.replay(NSE, symbol, tf, base.get(tf, []), evals.get(trades.EVAL_RESOLUTION[NSE][tf], []), now)
            got += tlb.breaks(NSE, symbol, tf, base.get(tf, []), evals.get(trades.EVAL_RESOLUTION[NSE][tf], []),
                              now, since, BREAK_RULE)
    print(f"replay done: {len(got)} alerts ({time.time() - started:.0f}s)")
    return [t for t in got if t["kind"] in ("fib", "trendline", "break") and t["alert_ts"] >= since], opens


def alert_price(t, opens):
    """Where price stood when it came into the band: the eval candle's open, pulled into the band."""
    if t["kind"] == "break":
        return t["plan"]["entry"]          # entered at the alert: the price then
    ts_list, open_list = opens.get((t["market"], t["symbol"], trades.EVAL_RESOLUTION[t["market"]][t["tf"]]), ([], []))
    k = bisect.bisect_left(ts_list, t["alert_ts"])
    entry, band = t["plan"]["entry"], fbt.band_for(t["tf"])
    if k >= len(ts_list) or ts_list[k] != t["alert_ts"]:
        return entry
    o = open_list[k]
    return min(o, entry * (1 + band)) if t["plan"]["side"] == "long" else max(o, entry * (1 - band))


def stamp(ts):
    return datetime.fromtimestamp(ts, IST).strftime("%Y-%m-%d %H:%M")


def records(got, opens):
    recs, results = [], {}
    for t in got:
        ts = int(t["alert_ts"])
        rec = {"market": t["market"], "symbol": t["symbol"], "tf": t["tf"],
               "kind": "trendline" if t["kind"] == "break" else t["kind"],
               "plan": t["plan"], "price": alert_price(t, opens), "sent_ts": ts, "rebuild": True}
        if t["kind"] == "fib":
            zone = 1 if t["level"] in ("L1", "L2") else 2
            key = f"fib|{t['symbol']}|{t['tf']}|{t['d']}|{t['origin']}|{t['top']}|{zone}"
            key = key if t["level"] == "L3" else f"{key}|{t['level']}"
            rec.update(level=t["level"], zone=zone, d=t["d"], base=t["base"], top=t["top"])
        elif t["kind"] == "break":
            x1, y1, x2, y2 = t["anchors"]
            key = f"tl|{t['symbol']}|{t['tf']}|{t['line_kind']}|{x1}|{x2}|br"
            rec.update(line=t["line_kind"], broken=True, break_ts=t["break_ts"],
                       **{"from": [y1, stamp(x1)], "to": [y2, stamp(x2)]})
        else:
            x1, y1, x2, y2 = t["anchors"]
            key = f"tl|{t['symbol']}|{t['tf']}|{t['line']}|{x1}|{x2}"
            rec.update(line=t["line"], **{"from": [y1, stamp(x1)], "to": [y2, stamp(x2)]})
        rec["key"], rec["id"] = key, f"{key}@{ts}|rb"
        res = dict(t["result"])
        if res.get("filled") and res.get("fill_ts") is not None:
            secs = TF_SECONDS[trades.EVAL_RESOLUTION[t["market"]][t["tf"]]]
            res["news_window"] = news_overlap(res["fill_ts"], res["fill_ts"] + secs)
        recs.append(rec)
        results[rec["id"]] = {k: jsonable(v) for k, v in res.items()}
    return recs, results


def summary(recs, results):
    order = ["4h", "1d", "1w", "1M"]
    groups = {}
    for rec in recs:
        res = results[rec["id"]]
        key = (rec["market"].upper(), "TL broken" if rec.get("broken") else rec["kind"], rec["tf"])
        g = groups.setdefault(key, {"alerts": 0, "rs": []})
        g["alerts"] += 1
        if not res.get("filled") or res.get("news_window"):
            continue
        net = trades.booked_r(rec["plan"], rec["market"], res)[1]
        if net is not None:
            g["rs"].append((net, net * trades.risk_pct(rec["plan"])))
    lines = ["| market | kind | tf | alerts | closed trades | win % | total R | R/trade | %/trade |",
             "|---|---|---|---|---|---|---|---|---|"]
    for key in sorted(groups, key=lambda k: (k[0], k[1], order.index(k[2]))):
        g = groups[key]
        n = len(g["rs"])
        tot = sum(r for r, _ in g["rs"])
        win = sum(1 for r, _ in g["rs"] if r > 0)
        pct = sum(p for _, p in g["rs"]) / n if n else 0
        lines.append(f"| {key[0]} | {key[1]} | {key[2].upper()} | {g['alerts']} | {n} | "
                     f"{win / n * 100 if n else 0:.0f}% | {tot:+.1f} | {tot / n if n else 0:+.2f} | {pct:+.2f}% |")
    return lines


def live_match(state: Path, recs, since_live: float):
    """Live fib / TL touch alerts since since_live whose key the replay also sends within 3 days."""
    replay = {}
    for rec in recs:
        replay.setdefault(rec["key"], []).append(rec["sent_ts"])
    path = state / "fib_trendline_alert_records.jsonl"
    hit, total = Counter(), Counter()
    if not path.exists():
        return []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("kind") not in ("fib", "trendline") or not r.get("plan") or float(r.get("sent_ts", 0)) < since_live:
            continue
        group = f"{r['kind']} {'4H' if r['tf'] == '4h' else '1D+'}"
        total[group] += 1
        if any(abs(float(r["sent_ts"]) - x) <= 3 * 86400 for x in replay.get(r.get("key"), [])):
            hit[group] += 1
    since_text = pd.Timestamp(since_live, unit="s", tz=IST).strftime("%Y-%m-%d")
    return [f"Check: live fib / TL alerts since {since_text} the replay also sends (same level key, within 3 days): "
            + ", ".join(f"{g} {hit[g]}/{total[g]}" for g in sorted(total)), ""]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--state", default="")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = TIMEFRAMES
    fbt.FIB_LEVELS = config.FIB_ALERT_LEVELS
    fbt.EARLY_BAND = True
    since = int(pd.Timestamp(args.since, tz=IST).timestamp())
    now = int(time.time())

    got, opens = replay_all(since, now, args.limit)
    recs, results = records(got, opens)
    with (OUT / "fibtl_rebuild_records.jsonl").open("w", encoding="utf-8") as fh:
        for r in sorted(recs, key=lambda r: r["sent_ts"]):
            fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    (OUT / "fibtl_rebuild_results.json").write_text(json.dumps(results, sort_keys=True, default=str), encoding="utf-8")
    meta = {"since": pd.Timestamp(since, unit="s", tz="UTC").isoformat(),
            "cutoff": pd.Timestamp(now, unit="s", tz="UTC").isoformat(),
            "built_at": pd.Timestamp(now, unit="s", tz="UTC").isoformat(),
            "rows": len(recs), "fib": sum(1 for r in recs if r["kind"] == "fib"),
            "trendline": sum(1 for r in recs if r["kind"] == "trendline" and not r.get("broken")),
            "tl_broken": sum(1 for r in recs if r.get("broken"))}
    (OUT / "fibtl_rebuild_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")

    news = sum(1 for r in results.values() if r.get("news_window"))
    text = [f"# Fib + trendline backtest rebuilt under today's rules ({args.since} to "
            f"{pd.Timestamp(now, unit='s', tz=IST):%Y-%m-%d %H:%M} IST)", "",
            "Fibs at every live level (4H L2-L4, 1D+ L1-L4, 2R + BE, hold 20), trendlines lakky's stop + 1R; "
            "0.75% band, 3% on 1W/1M. Crypto on Bitunix (as live), NSE on Yahoo. Net after fees; "
            f"% = R x the trade's stop distance. {news} fills within 15 min of US CPI/PPI/FOMC left out. "
            "Open trades are not counted.", ""]
    text += summary(recs, results)
    if args.state:
        text += [""] + live_match(Path(args.state), recs, pd.Timestamp("2026-10-21 21:00", tz=IST).timestamp())
    levels = Counter((r["kind"], r.get("level")) for r in recs)
    text += ["", "Alerts by level: " + ", ".join(f"{k[1] or 'TL'} {v}" for k, v in sorted(levels.items(), key=str)), ""]
    (OUT / "SUMMARY.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text))


if __name__ == "__main__":
    main()
