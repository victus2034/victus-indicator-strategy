"""lakky's journal setup for 1D crypto trendline alerts, backtested for the CoinDCX auto trade
(2026-11-13: "backtest this and tell me can we apply this strategy for coindcx auto trading").

His Signals screen (Trendline alerts, CRYPTO 1D, all coins, type All = S/R TL touches and
SP / RS TL BR breaks, BTC day = Sideways, 1 Month 13 Oct - 13 Nov):
  - SL "Wick or body" at least 0.75% past entry (journal_fib_setup_backtest.wick_body_stop)
  - Exit 1.5R; SL shift +1R -> +0.75R; Trail TP +0.25R step, 0.5R behind; held till TP / SL;
    fees 0.0826%, stops slip 0.05% (journal_fib_setup_backtest.walk)
  - BTC "Sideways" (journal MKT_SIDE_PCT): BTC's daily candle (UTC day of the alert) closed
    within +-1.5% of its open. That day's close is only known at 05:30 IST the next morning,
    so on a live alert it is not known yet: the replay shows the journal's same-day filter
    (look-ahead) and the one a bot can use, the PREVIOUS day's BTC candle.
  - journal: 61 alerts, 60 filled, 30W / 24L, +4.81R, +0.09R a trade, PF 1.19, max DD -8.37R

Two jobs, written from the rules, not from the journal's code:
  journal  - the TL alerts the journal shows for that month (rebuild before its cutoff, live
             after), Delta 15m after the alert only (a rebuilt touch fills only after the
             candle that first reached the 0.75% band, journal v.184), BTC day from Delta
  replay   - every 1D TL touch and TL BROKEN alert today's rules would have sent, whole
             watchlist, from --since, on Bitunix 15m; fills within 15 min of US CPI / PPI /
             FOMC left out (backtest standard)

    PYTHONPATH=research python research/journal_tl_setup_backtest.py journal STATE_DIR
    PYTHONPATH=research python research/journal_tl_setup_backtest.py replay --since 2026-09-01
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_data  # noqa: E402
import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import scanner  # noqa: E402
import tl_broken_alert_backtest as tlb  # noqa: E402
from fib_trendline_data import CRYPTO, HISTORY_START, bitunix_candles, delta_candles  # noqa: E402
from journal_fib_setup_backtest import (DAY, HEAD, IST, delta, delta_name, detail, ist, line, load,  # noqa: E402
                                        news_overlap, walk, wick_body_stop)

OUT = Path(__file__).resolve().parent / "out" / "journal_tl_setup"
SIDE_PCT = 1.5
TOP3 = ("BTCUSD", "ETHUSD", "ZECUSD")
BREAK_RULE = (("live", "close", "before", 1),)


def btc_days(candles):
    """{UTC day start: close-to-open %} from daily candles [ts, o, h, l, c]."""
    return {c[0] - c[0] % DAY: (c[4] - c[1]) / c[1] * 100 for c in candles if c[1] > 0}


def side_on(days, ts, back=0):
    pct = days.get(ts - ts % DAY - back * DAY)
    return None if pct is None else abs(pct) <= SIDE_PCT


# ----------------------------------------------------------------- job 1: the journal's month

def journal(state, since, now):
    state = Path(state)
    meta = json.loads((state / "fibtl_rebuild_meta.json").read_text())
    cutoff = datetime.fromisoformat(meta["cutoff"]).timestamp()
    res = json.loads((state / "fibtl_rebuild_results.json").read_text())
    ok = lambda r: (r.get("kind") == "trendline" and r.get("tf") == "1d" and r.get("market") == "crypto"
                    and since <= r.get("sent_ts", 0) <= now and r.get("plan"))
    recs = [dict(r, rb=True) for r in load(state / "fibtl_rebuild_records.jsonl") if ok(r) and r["sent_ts"] < cutoff
            and not (res.get(r["id"]) or {}).get("news_window")]
    recs += [r for r in load(state / "fib_trendline_alert_records.jsonl") if ok(r) and r["sent_ts"] >= cutoff]
    recs.sort(key=lambda r: r["sent_ts"])
    days = btc_days(delta("BTCUSD", 1440, "1d", since - 5 * DAY, now))
    cache = {}

    def candles(sym):
        if sym not in cache:
            d = delta_name(sym)
            cache[sym] = {"1d": delta(d, 1440, "1d", since - 320 * DAY, now) if d else [],
                          "15m": delta(d, 15, "15m", since - DAY, now) if d else []}
        return cache[sym]

    ways = {"all days": [], "BTC sideways (same day, the journal's)": [], "BTC sideways (previous day)": [],
            "BTC sideways same day, alert's own SL": []}
    skipped = []
    for rec in recs:
        p = rec["plan"]
        s = -1 if p["side"] == "short" else 1
        c = candles(rec["symbol"])
        t0 = rec["sent_ts"] // 60 * 60
        m15 = [[b[0], b[2], b[3], b[4], 900] for b in c["15m"]]
        start = t0
        broken = bool(rec.get("broken"))
        if rec.get("rb") and not broken:
            edge = p["entry"] * (1 + s * 0.0075)
            first = next((b for b in m15 if b[0] + 900 > t0 and ((b[2] <= edge) if s > 0 else (b[1] >= edge))), None)
            start = first[0] + 900 if first else now
        stop, sc = wick_body_stop(c["1d"], t0, p["entry"], s)
        tag = "BR" if broken else "touch"
        base = {"symbol": rec["symbol"], "level": tag, "side": p["side"], "entry": p["entry"], "alert_sl": p["sl"],
                "alert_ts": t0, "id": rec["id"], "same": side_on(days, t0), "prev": side_on(days, t0, 1)}
        if stop is None:
            skipped.append(f"{ist(t0)} {rec['symbol']} {tag}: " + ("no Delta candles" if not c["1d"] else "no candle 0.75% past entry"))
        else:
            row = {**base, "sl": stop, "stop_candle": sc, **walk(p["entry"], stop, s, m15, start, False)}
            ways["all days"].append(row)
            if row["same"]:
                ways["BTC sideways (same day, the journal's)"].append(row)
            if row["prev"]:
                ways["BTC sideways (previous day)"].append(row)
        if base["same"] and m15:
            ways["BTC sideways same day, alert's own SL"].append(
                {**base, "sl": p["sl"], "stop_candle": None, **walk(p["entry"], p["sl"], s, m15, start, False)})
    out = OUT / "journal"
    out.mkdir(parents=True, exist_ok=True)
    text = [f"# Journal check - CRYPTO 1D trendlines (touch + break), {ist(since)} to {ist(now)} IST", "",
            "His screen (BTC sideways): 61 alerts, 60 filled, 30W / 24L, +4.81R, +0.09R a trade, PF 1.19, max DD -8.37R.",
            f"Alerts found: {len(recs)} (rebuild before {ist(cutoff)}, live after), {len(skipped)} with no wick/body stop.",
            "Delta 15m, candles after the alert only; a rebuilt touch fills only after the candle that reached the band.",
            "", HEAD]
    text += [line(name, rows) for name, rows in ways.items()]
    sw = ways["BTC sideways (same day, the journal's)"]
    text += ["", "## Sideways same day, by type", "", HEAD,
             line("touch", [t for t in sw if t["level"] == "touch"]), line("break", [t for t in sw if t["level"] == "BR"])]
    text += ["", "Left out:"] + (skipped or ["none"])
    text += ["", "## BTC sideways (same day) trades", "```"] + [detail(t) for t in sw] + ["```"]
    (out / "result.json").write_text(json.dumps(ways, indent=0))
    (out / "SUMMARY.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text))


# ----------------------------------------------------------------- job 2: today's rules, replayed

def symbol_trades(symbol, since, now):
    contract = scanner.delta_contract(symbol)
    if bitunix_data.uses_bitunix(symbol):
        pair = bitunix_data.pair_for(symbol, contract)
        get = lambda res, start: fbt._cached(f"jf_{pair}_{res}_{int(start) // DAY}", lambda: bitunix_candles(pair, res, start, now))
    else:
        get = lambda res, start: fbt._cached(f"jf_{contract}_{res}_{int(start) // DAY}", lambda: delta_candles(contract, res, max(start, now - 2000 * DAY), now))
    daily, four = get("1d", HISTORY_START), get("4h", HISTORY_START)
    fine = [[c[0], c[2], c[3], c[4], 900] for c in get("15m", since - 3 * DAY)]
    opens = {c[0]: c[1] for c in get("15m", since - 3 * DAY)}
    band = fbt.band_for("1d")
    alerts = []
    for t in fbt.replay(CRYPTO, symbol, "1d", daily, four, now):
        if t["kind"] != "trendline" or t["alert_ts"] < since:
            continue
        p = t["plan"]
        s = -1 if p["side"] == "short" else 1
        edge = p["entry"] * (1 + s * band)
        # the alert goes out in the 15m candle that first comes into the band; fills from the next one
        t0 = next((b[0] + 900 for b in fine if t["alert_ts"] <= b[0] < t["alert_ts"] + 4 * 3600
                   and ((b[2] <= edge) if s > 0 else (b[1] >= edge))), t["alert_ts"] + 4 * 3600)
        alerts.append(("touch", t0, p["side"], p["entry"], p["sl"]))
    for t in tlb.breaks(CRYPTO, symbol, "1d", daily, four, now, since, rules=BREAK_RULE):
        # market entry: the open of the first 15m candle after the break candle closed
        t0 = t["alert_ts"]
        k = next((b[0] for b in fine if b[0] >= t0), None)
        if k is None:
            continue
        entry, sl, s = opens[k], t["plan"]["sl"], 1 if t["plan"]["side"] == "long" else -1
        if (sl >= entry) if s > 0 else (sl <= entry):
            continue                     # break_plan: no trade when the stop is on the wrong side
        alerts.append(("BR", k, t["plan"]["side"], entry, sl))
    out = []
    for tag, t0, side, entry, alert_sl in alerts:
        s = -1 if side == "short" else 1
        base = {"symbol": symbol, "level": tag, "side": side, "entry": entry, "alert_sl": alert_sl, "alert_ts": t0}
        own = walk(entry, alert_sl, s, fine, t0, False)
        own["news"] = own.get("fill_ts") is not None and news_overlap(own["fill_ts"], own["fill_ts"] + 900)
        stop, sc = wick_body_stop(daily, t0, entry, s)
        row = {**base, "sl": stop or 0.0, "stop_candle": sc, "own": own}
        if stop is None:
            out.append({**row, "outcome": "no stop", "risk_pct": 0.0})
            continue
        w = walk(entry, stop, s, fine, t0, False)
        w["news"] = w.get("fill_ts") is not None and news_overlap(w["fill_ts"], w["fill_ts"] + 900)
        out.append({**row, **w})
    return out


def _safe(symbol, since, now):
    try:
        return symbol_trades(symbol, since, now)
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} failed: {error!r}")
        return None


def replay(since_text, tag):
    since = int(datetime.fromisoformat(since_text).replace(tzinfo=IST).timestamp())
    now = int(time.time())
    symbols = list(config.WATCHLIST)
    got, failed = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for symbol, res in zip(symbols, pool.map(lambda x: _safe(x, since, now), symbols)):
            if res is None:
                failed.append(symbol)
                continue
            print(f"{symbol}: {len(res)} alerts")
            got += res
    got.sort(key=lambda t: t["alert_ts"])
    btc = fbt._cached(f"jt_btc_1d_{since // DAY}", lambda: bitunix_candles("BTCUSD", "1d", since - 10 * DAY, now))
    days = btc_days(btc)
    for t in got:
        t["same"], t["prev"] = side_on(days, t["alert_ts"]), side_on(days, t["alert_ts"], 1)
    wb = [t for t in got if t["outcome"] != "no stop" and not t.get("news")]
    own = [{**t, **{k: t["own"].get(k) for k in ("r", "risk_pct", "outcome", "fill_ts")}, "sl": t["alert_sl"]}
           for t in got if not t["own"].get("news")]
    crypto = set(config.CRYPTO_WATCHLIST)
    news = sum(1 for t in got if t.get("news"))
    nostop = sum(1 for t in got if t["outcome"] == "no stop")
    same = lambda rows: [t for t in rows if t["same"]]
    prev = lambda rows: [t for t in rows if t["prev"]]
    kind = lambda rows, k: [t for t in rows if t["level"] == k]
    text = [f"# Journal 1D trendline setup, replayed under today's rules - {since_text} to {ist(now)[:10]}", "",
            "TL touch + TL BROKEN, 1D crypto watchlist (16 crypto + xStocks + XAUT/SLVON). Exit 1.5R, SL shift +1R -> +0.75R, "
            "Trail TP +0.25R / 0.5R behind, held till TP / SL, fill within 20 days, fees 0.0826%, stop slip 0.05%. "
            "Bitunix 15m (XAUT / SLVON Delta). BTC sideways = Bitunix BTC daily (UTC) close within 1.5% of open. "
            f"{news} fills within 15 min of US CPI / PPI / FOMC left out; {nostop} alerts with no wick/body 0.75% past entry left out."
            + (f" FAILED symbols: {', '.join(failed)}." if failed else ""), "",
            "## His setup (SL wick or body 0.75%)", "", HEAD,
            line("All days", wb), line("BTC sideways same day (journal, look-ahead)", same(wb)),
            line("BTC sideways previous day (bot can use)", prev(wb)),
            line("touch, all days", kind(wb, "touch")), line("break, all days", kind(wb, "BR")),
            line("touch, sideways same day", same(kind(wb, "touch"))), line("break, sideways same day", same(kind(wb, "BR"))),
            line("touch, sideways prev day", prev(kind(wb, "touch"))), line("break, sideways prev day", prev(kind(wb, "BR"))),
            "", "## Same alerts, the alert's own SL", "", HEAD,
            line("All days", own), line("BTC sideways same day", same(own)), line("BTC sideways previous day", prev(own)),
            line("touch, all days", kind(own, "touch")), line("break, all days", kind(own, "BR")),
            line("break, sideways prev day", prev(kind(own, "BR"))),
            "", "## Coins (his setup)", "", HEAD]
    for name, rows in (("All", wb), (f"{len(crypto)} crypto only", [t for t in wb if t["symbol"] in crypto]),
                       ("Top 3 BTC/ETH/ZEC", [t for t in wb if t["symbol"] in TOP3])):
        text += [line(f"{name}, all days", rows), line(f"{name}, sideways same day", same(rows)),
                 line(f"{name}, sideways prev day", prev(rows))]
    text += ["", "## By month (his setup, all days / sideways prev day)", "", HEAD]
    for m in sorted({ist(t["alert_ts"])[:7] for t in wb}):
        rows = [t for t in wb if ist(t["alert_ts"])[:7] == m]
        text += [line(f"{m} all", rows), line(f"{m} prev-day sideways", prev(rows))]
    text += ["", "## By coin (his setup, all days)", "", HEAD] + [line(sym, [t for t in wb if t["symbol"] == sym]) for sym in symbols]
    outcomes = {}
    for t in wb:
        outcomes[t["outcome"]] = outcomes.get(t["outcome"], 0) + 1
    text += ["", "Outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())),
             "", "## Trades", "```"] + [detail(t) + (" SIDE" if t["same"] else "") + (" PREVSIDE" if t["prev"] else "")
                                         for t in got if t["outcome"] != "no stop"] + ["```"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"trades_{tag}.json").write_text(json.dumps(got, indent=0))
    (OUT / f"SUMMARY_{tag}.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text[:text.index("## Trades")]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("job", choices=("journal", "replay"))
    ap.add_argument("state", nargs="?")
    ap.add_argument("--since", default="2026-09-01")
    ap.add_argument("--tag", default="")
    ap.add_argument("--from-ist", default="2026-10-13T00:00")
    ap.add_argument("--to-ist", default="2026-11-13T13:03")       # his screenshot
    a = ap.parse_args()
    if a.job == "journal":
        journal(a.state, datetime.fromisoformat(a.from_ist).replace(tzinfo=IST).timestamp(),
                datetime.fromisoformat(a.to_ist).replace(tzinfo=IST).timestamp())
    else:
        replay(a.since, a.tag or a.since)
