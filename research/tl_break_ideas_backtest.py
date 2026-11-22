"""New ideas for TL BROKEN trades, the part of the live bot that makes money (lakky, 2026-11-22:
"improve it more ... improve its accuracy").

Every crypto TL break today's rules send, on 1D (what the live bot trades) and 4H, replayed with
the live bot's rules (journal_tl_setup_backtest BR rows): market at the first 15m open after the
break candle closes, stop = first wick / body 0.75% past entry on closed candles of the break's own
timeframe, 1.5R + SL shift +1R -> +0.75R + trail TP 0.25R / 0.5R behind, fees 0.0826%, slip 0.05%.
Fills within 15 min of US CPI / PPI / FOMC left out; closed trades only. Then each idea is a filter
or a different entry on the same breaks - nothing here changes a live rule:

  strong close  - the break candle closed at least X% past the line
  close at edge - the break candle closed in its outer 30% (top for a buy, bottom for a sell)
  volume        - the break candle traded at least X times its 20-candle average volume
  retest        - no market order; a limit at the broken line, filled within 3 days, the same
                  stop rule from that price (tighter stop, fewer fills)
  stop cap      - skip breaks whose stop is more than 8% away

A second part checks the live bot's own trades (research/in/coindcx_live_state_*.json) against
the replay: alert time, fill slippage, stop, and whether price really reached the stop before a
trade the bot booked as SL.

    PYTHONPATH=research python research/tl_break_ideas_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import bisect
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
from fib_trendline_data import CRYPTO, HISTORY_START, TF_SECONDS  # noqa: E402
from journal_fib_setup_backtest import IST, ist, news_overlap, stats, walk  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "tl_break_ideas"
STATE = sorted((Path(__file__).resolve().parent / "in").glob("coindcx_live_state_*.json"))
BREAK_RULE = (("live", "close", "before", 1),)
SL_GAP_PCT, SL_LOOKBACK = 0.75, 300
RETEST_SECONDS = 3 * 86400
FAR = 10 ** 12


def klines(pair, res, start, now):
    """[ts, o, h, l, c, volume] from Bitunix, cached for the day."""
    return fbt._cached(f"tbi_{pair}_{res}_{int(start) // 86400}",
                       lambda: bitunix_data.klines(pair, res, int(start), int(now) + 1))


def wick_body_stop(candles, seconds, t0, entry, s):
    """The live bot's stop on candles of `seconds` closed before t0: first wick and first body
    at least 0.75% past entry walking back, the closer of the two."""
    closed = [c for c in candles if c[0] + seconds <= t0 and min(c[1:5]) > 0][-SL_LOOKBACK:]
    edge = entry * (1 - s * SL_GAP_PCT / 100)
    wick = body = None
    for c in reversed(closed):
        w = c[3] if s > 0 else c[2]
        b = min(c[1], c[4]) if s > 0 else max(c[1], c[4])
        if wick is None and ((w <= edge) if s > 0 else (w >= edge)):
            wick = w
        if body is None and ((b <= edge) if s > 0 else (b >= edge)):
            body = b
        if wick is not None and body is not None:
            break
    found = [x for x in (wick, body) if x is not None]
    return (max(found) if s > 0 else min(found)) if found else None


def line_price(anchors, times, ts):
    """The line's price on the candle opening at ts (straight in candle count, like the chart)."""
    t1, y1, t2, y2 = anchors
    i1, i2, i = (bisect.bisect_left(times, x) for x in (t1, t2, ts))
    return y1 + (y2 - y1) * (i - i1) / (i2 - i1) if i2 != i1 else y2


def trade(entry, stop, s, fine, t0, fill_within=None):
    w = walk(entry, stop, s, fine, t0, False)
    if fill_within and w.get("fill_ts") is not None and w["fill_ts"] > t0 + fill_within:
        return {"outcome": "no fill", "risk_pct": w["risk_pct"]}
    w["news"] = w.get("fill_ts") is not None and news_overlap(w["fill_ts"], w["fill_ts"] + 900)
    return w


def symbol_rows(symbol, since, now):
    contract = scanner.delta_contract(symbol)
    if not bitunix_data.uses_bitunix(symbol):
        return []
    pair = bitunix_data.pair_for(symbol, contract)
    daily = klines(pair, "1d", HISTORY_START, now)
    four = klines(pair, "4h", HISTORY_START, now)
    hour = klines(pair, "1h", since - 30 * 86400, now)
    q = klines(pair, "15m", since - 3 * 86400, now)
    fine = [[c[0], c[2], c[3], c[4], 900] for c in q]
    opens = {c[0]: c[1] for c in q}
    fine_ts = [c[0] for c in q]
    out = []
    for tf, base, evalc in (("1d", daily, four), ("4h", four, hour)):
        seconds = TF_SECONDS[tf]
        times = [c[0] for c in base]
        for t in tlb.breaks(CRYPTO, symbol, tf, [c[:5] for c in base], [c[:5] for c in evalc], now, since,
                            rules=BREAK_RULE):
            s = 1 if t["plan"]["side"] == "long" else -1
            k = bisect.bisect_left(fine_ts, t["alert_ts"])
            if k >= len(fine_ts):
                continue
            t0 = fine_ts[k]
            entry = opens[t0]
            bi = bisect.bisect_left(times, t["break_ts"])
            if bi >= len(base) or times[bi] != t["break_ts"]:
                continue
            _ts, o, h, l, c, v = base[bi][:6]
            line_b = line_price(t["anchors"], times, t["break_ts"])
            line_next = line_price(t["anchors"], times, t["break_ts"] + seconds)
            prev = [x[5] for x in base[max(0, bi - 20):bi] if x[5] > 0]
            row = {"symbol": symbol, "tf": tf, "side": t["plan"]["side"], "alert_ts": t0, "entry": entry,
                   "close_past_pct": s * (c - line_b) / line_b * 100,
                   "close_loc": ((c - l) / (h - l) if s > 0 else (h - c) / (h - l)) if h > l else 0.5,
                   "vol_x": v / (sum(prev) / len(prev)) if prev and v > 0 else None,
                   "line_next": line_next}
            stop = wick_body_stop(base, seconds, t0, entry, s)
            row["market"] = trade(entry, stop, s, fine, t0) if stop is not None and s * (entry - stop) > 0 else None
            # retest: a limit at the line's price on the candle after the break, the same stop rule from there
            r_entry = line_next
            ok = s * (entry - r_entry) > 0           # the line is behind price, so a pullback can reach it
            r_stop = wick_body_stop(base, seconds, t0, r_entry, s) if ok else None
            row["retest"] = (trade(r_entry, r_stop, s, fine, t0, RETEST_SECONDS)
                             if r_stop is not None and s * (r_entry - r_stop) > 0 else None)
            out.append(row)
    return out


def closed(rows, key):
    """Trades of one entry kind: filled, not in a news window, closed."""
    got = []
    for x in rows:
        w = x.get(key)
        if not w or w.get("fill_ts") is None or w.get("news") or w.get("r") is None:
            continue
        got.append({**x, **w})
    return sorted(got, key=lambda t: t["fill_ts"])


def slots(rows, max_open):
    taken = []
    for t in rows:
        live = [x for x in taken if x["fill_ts"] <= t["fill_ts"] < x.get("exit_ts", FAR)]
        if len(live) >= max_open or any(x["symbol"] == t["symbol"] for x in live):
            continue
        taken.append(t)
    return taken


HEAD = "| Idea | Trades | Win | R/trade | %/trade | Total R | Max DD | Avg SL |\n|---|---|---|---|---|---|---|---|"


def line(name, rows):
    st = stats(rows)
    if not st:
        return f"| {name} | 0 | | | | | | |"
    return (f"| {name} | {st['n']} | {st['wins'] / st['n'] * 100:.0f}% | {st['avg']:+.3f}R | {st['pct']:+.2f}% | "
            f"{st['tot']:+.1f}R | -{st['dd']:.1f}R | {st['risk']:.1f}% |")


IDEAS = [
    ("Today (market at break close)", "market", lambda x: True),
    ("Strong close >= 0.5% past line", "market", lambda x: x["close_past_pct"] >= 0.5),
    ("Strong close >= 1% past line", "market", lambda x: x["close_past_pct"] >= 1.0),
    ("Close in outer 30% of candle", "market", lambda x: x["close_loc"] >= 0.7),
    ("Volume >= 1x 20-candle avg", "market", lambda x: (x["vol_x"] or 0) >= 1.0),
    ("Volume >= 1.5x 20-candle avg", "market", lambda x: (x["vol_x"] or 0) >= 1.5),
    ("Stop <= 8% only", "market", lambda x: x["market"] is not None and x["market"]["risk_pct"] <= 8),
    ("Retest: limit at line, 3 days", "retest", lambda x: True),
]


def live_check(rows, now):
    """The live bot's own orders against the replay and the candles."""
    if not STATE:
        return ["", "No live state file in research/in/."]
    state = json.loads(STATE[-1].read_text())
    text = ["", f"## Live bot trades vs replay ({STATE[-1].name})", "",
            "| Coin | Type | Side | Status | Sent (IST) | Entry plan -> fill | Fill vs plan (+ better) | SL | Replay entry / SL | "
            "Exit why | R | Price reached SL before exit? |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for o in sorted(state["orders"].values(), key=lambda o: o.get("sent_ts", 0)):
        sym, side = o.get("symbol"), o.get("side")
        s = 1 if side == "long" else -1
        kind = "break" if o.get("broken") else "touch"
        rep = next((x for x in rows if x["tf"] == "1d" and x["symbol"] == sym and x["side"] == side and kind == "break"
                    and abs(x["alert_ts"] - o.get("sent_ts", 0)) < 86400), None)
        rep_txt = ""
        if rep and rep.get("market"):
            m = rep["market"]
            rep_txt = f"{scanner.price_text(rep['entry'])} / {m['risk_pct']:.2f}%"
        slip = ""
        if o.get("entry") and o.get("fill_price"):
            slip = f"{-s * (o['fill_price'] - o['entry']) / o['entry'] * 100:+.3f}%"
        reached = ""
        if o.get("status") == "closed" and o.get("exit_why") == "SL" and o.get("sl") and o.get("fill_ts"):
            try:
                pair = bitunix_data.pair_for(sym, scanner.delta_contract(sym))
                bars = klines(pair, "1m", o["fill_ts"] - 60, min(now, o["exit_ts"] + 60))
                hit = next((b for b in bars if b[0] <= o["exit_ts"] and ((b[3] <= o["sl"]) if s > 0 else (b[2] >= o["sl"]))), None)
                worst = (min(b[3] for b in bars if b[0] <= o["exit_ts"]) if s > 0
                         else max(b[2] for b in bars if b[0] <= o["exit_ts"]))
                reached = (f"yes, {ist(hit[0])[5:16]}" if hit else
                           f"NO - worst {scanner.price_text(worst)} vs SL {scanner.price_text(o['sl'])}")
            except Exception as error:  # noqa: BLE001
                reached = f"no candles ({error!r:.40})"
        text.append(f"| {sym} | {kind} | {side} | {o.get('status')} {o.get('reason') or ''} | {ist(o.get('sent_ts', 0))[5:16]} | "
                    f"{o.get('entry') or ''} -> {o.get('fill_price') or ''} | {slip} | "
                    f"{o.get('sl') or ''} ({(o.get('stop_pct') or 0):.2f}%) x{o.get('leverage') or ''} | {rep_txt} | "
                    f"{o.get('exit_why') or ''} | {o.get('r') if o.get('r') is not None else ''} | {reached} |")
    return text


def main(since_text):
    since = int(datetime.fromisoformat(since_text).replace(tzinfo=IST).timestamp())
    now = int(time.time())
    config.FIB_TL_CRYPTO_NIGHT = True
    symbols = list(config.CRYPTO_WATCHLIST)
    rows, failed = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for symbol, got in zip(symbols, pool.map(lambda s: _safe(s, since, now), symbols)):
            if got is None:
                failed.append(symbol)
                continue
            print(f"{symbol}: {len(got)} breaks")
            rows += got
    news = sum(1 for x in rows for k in ("market", "retest") if x.get(k) and x[k].get("news"))
    text = [f"# TL break ideas - {since_text} to {ist(now)[:10]}", "",
            f"{len(symbols)} crypto coins, Bitunix, live bot rules (market at the first 15m open after the break candle, "
            "wick/body 0.75% stop on the break's timeframe, 1.5R + SL shift + trail TP, fees 0.0826%, slip 0.05%). "
            f"{news} fills within 15 min of US CPI / PPI / FOMC left out. Closed trades only."
            + (f" FAILED: {', '.join(failed)}." if failed else "")]
    for tf, label in (("1d", "1D (live bot)"), ("4h", "4H")):
        tf_rows = [x for x in rows if x["tf"] == tf]
        retest_tried = [x for x in tf_rows if x.get("retest")]
        retest_filled = [x for x in retest_tried if x["retest"].get("fill_ts") is not None]
        text += ["", f"## {label}: {len(tf_rows)} breaks; retest filled {len(retest_filled)} of {len(retest_tried)}", "",
                 "### All breaks (no slot limit)", "", HEAD]
        for name, key, keep in IDEAS:
            text.append(line(name, closed([x for x in tf_rows if keep(x)], key)))
        text += ["", "### Live bot slots (1 per coin, max 5)", "", HEAD]
        for name, key, keep in IDEAS:
            text.append(line(name, slots(closed([x for x in tf_rows if keep(x)], key), config.COINDCX_LIVE_MAX_OPEN)))
    text += live_check(rows, now)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"SUMMARY_{since_text}.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    (OUT / f"breaks_{since_text}.json").write_text(json.dumps(rows, default=str))
    print("\n".join(text))


def _safe(symbol, since, now):
    try:
        return symbol_rows(symbol, since, now)
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} failed: {error!r}")
        return None


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--since", default="2026-09-01")
    main(p.parse_args().since)
