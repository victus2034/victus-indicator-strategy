"""More trades for the live bot? (lakky, 2026-11-26: "Yes do it" - backtest adding 4H TL breaks and
1D fib L3 to the live bot's rules, alone and together, vs today's rules.)

Today's live rules (coindcx_live):
  - 1D crypto TL BROKEN: market entry at the next 15m open, SL wick/body 0.75%+ past entry on daily
    candles, exit 1.5R + trail TP +0.25R / 0.5R behind, SL shift +1R -> +0.75R, held till stop
  - 1D crypto fib L2 + L4 while BTC is flat: journal v210 rules (journal_v210_fib_backtest.V210)
Added, scored the same way:
  - 4H crypto TL BROKEN: same exits, wick/body stop on 4H candles (the candle before the break)
  - 1D crypto fib L3 while BTC is flat, v210 rules
Bitunix 15m walks after the alert, fees 0.0826%, stops slip 0.05%; fills within 15 min of US
CPI / PPI / FOMC left out. No one-trade-per-coin limit (each setup scored on its own).

    PYTHONPATH=research python research/more_trades_backtest.py --since 2026-09-01
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
import journal_fib_setup_backtest as jfs  # noqa: E402
import journal_v210_fib_backtest as jv  # noqa: E402
import scanner  # noqa: E402
import tl_broken_alert_backtest as tlb  # noqa: E402
from fib_trendline_data import CRYPTO, HISTORY_START, bitunix_candles  # noqa: E402
from journal_fib_setup_backtest import DAY, IST, ist, walk  # noqa: E402
from journal_tl_setup_backtest import BREAK_RULE  # noqa: E402
from journal_fib_setup_backtest import news_overlap  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "more_trades"
H4 = 4 * 3600
V210_L3 = jv.Rules("v210 L3, BTC flat", ("L3",), "body", 2.0, 1.0, 0.25, 1.0, 1.0, 20 * DAY, 0.05, "flat")


def wick_body_stop(candles, period, t0, entry, s):
    """jfs.wick_body_stop on candles of any length: closed before t0, 0.75%+ past entry."""
    closed = [c for c in candles if c[0] + period <= t0]
    shifted = [[c[0] + period - DAY] + list(c[1:]) for c in closed]   # so jfs sees them as closed
    return jfs.wick_body_stop(shifted, t0, entry, s)[0]


def symbol_breaks(symbol, since, now):
    pair = bitunix_data.pair_for(symbol, scanner.delta_contract(symbol))
    get = lambda res, start: fbt._cached(f"jf_{pair}_{res}_{int(start) // DAY}", lambda: bitunix_candles(pair, res, start, now))
    daily, four, one = get("1d", HISTORY_START), get("4h", HISTORY_START), get("1h", HISTORY_START)
    m15 = get("15m", since - 3 * DAY)
    fine = [[c[0], c[2], c[3], c[4], 900] for c in m15]
    opens = {c[0]: c[1] for c in m15}
    out = []
    for tf, base, evalc, stop_on, period in (("1d", daily, four, daily, DAY), ("4h", four, one, four, H4)):
        for t in tlb.breaks(CRYPTO, symbol, tf, base, evalc, now, since, rules=BREAK_RULE):
            k = next((b[0] for b in fine if b[0] >= t["alert_ts"]), None)
            if k is None:
                continue
            entry, s = opens[k], 1 if t["plan"]["side"] == "long" else -1
            stop = wick_body_stop(stop_on, period, k, entry, s)
            if stop is None:
                continue
            w = walk(entry, stop, s, fine, k, False)
            if w.get("fill_ts") is not None and news_overlap(w["fill_ts"], w["fill_ts"] + 900):
                continue
            out.append({"setup": f"{tf} BR", "symbol": symbol, "side": t["plan"]["side"], "alert_ts": k, **w})
    return out


def symbol_fibs(symbol, since, now):
    out = []
    for row in jv.symbol_alerts(symbol, since, now):
        for rule, name in ((jv.V210, "1d fib L2/L4"), (V210_L3, "1d fib L3")):
            res = row.get(rule.name)
            if not res or res.get("outcome") == "no stop" or res.get("news"):
                continue
            out.append({"setup": name, "symbol": symbol, "side": row["side"], "alert_ts": row["alert_ts"], **res})
    return out


def _safe(fn, symbol, since, now):
    try:
        return fn(symbol, since, now)
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} {fn.__name__} failed: {error!r}")
        return []


def row(name, rows, weeks):
    done = [x for x in rows if x.get("r") is not None]
    if not done:
        return f"| {name} | 0 | | | | | |"
    rs = [x["r"] for x in done]
    eq = peak = dd = 0.0
    for v in rs:
        eq += v
        peak, dd = max(peak, eq), max(dd, max(peak, eq) - eq)
    pct = sum(x["r"] * x["risk_pct"] for x in done) / len(done)
    return (f"| {name} | {len(done)} | {len(done) / weeks:.1f} | {sum(v > 0 for v in rs) / len(rs) * 100:.0f}% | "
            f"{sum(rs):+.2f}R | {sum(rs) / len(rs):+.3f}R | {pct:+.2f}% | -{dd:.1f}R |")


def run(since_text):
    since = int(datetime.fromisoformat(since_text).replace(tzinfo=IST).timestamp())
    now = int(time.time())
    fbt.FIB_LEVELS = config.FIB_ALERT_LEVELS
    jv.ALL_RULES = (jv.V210, V210_L3)
    symbols = list(config.CRYPTO_WATCHLIST)
    got = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for res in pool.map(lambda x: _safe(symbol_breaks, x, since, now), symbols):
            got += res
        fibs = []
        for res in pool.map(lambda x: _safe(symbol_fibs, x, since, now), symbols):
            fibs += res
    # BTC flat, as the live bot reads it (journal v210 filter)
    btc = next(x for x in symbols if x.startswith("BTC"))
    btc15 = {c[0]: c[1:] for c in jv.candles(btc, now, since)[2]}
    for x in fibs:
        p = jv.btc_move(btc15, x["alert_ts"])
        if p is not None and abs(p) < jv.BTC_FLAT_PCT:
            got.append(x)
    got = [x for x in got if x.get("fill_ts") is not None]
    got.sort(key=lambda x: x["fill_ts"])
    weeks = (now - since) / (7 * DAY)
    pick = lambda *names: [x for x in got if x["setup"] in names]
    head = ("| Rules | Trades | / week | Won | Total R | R/trade | %/trade | Max DD |\n"
            "|---|---|---|---|---|---|---|---|")
    text = [f"# More trades for the live bot - {since_text} to {ist(now)[:10]}", "",
            f"{len(symbols)} crypto coins, Bitunix 15m, CPI/PPI/FOMC fills left out, no one-per-coin limit.", "",
            head,
            row("Today: 1D breaks + 1D fib L2/L4", pick("1d BR", "1d fib L2/L4"), weeks),
            row("+ 4H breaks", pick("1d BR", "1d fib L2/L4", "4h BR"), weeks),
            row("+ 1D fib L3", pick("1d BR", "1d fib L2/L4", "1d fib L3"), weeks),
            row("+ both", got, weeks), "", "## Each setup alone", "", head]
    text += [row(s, pick(s), weeks) for s in ("1d BR", "1d fib L2/L4", "4h BR", "1d fib L3")]
    text += ["", "## By month (each setup)", "", head]
    for m in sorted({ist(x["fill_ts"])[:7] for x in got}):
        for s in ("1d BR", "1d fib L2/L4", "4h BR", "1d fib L3"):
            text.append(row(f"{m} {s}", [x for x in pick(s) if ist(x["fill_ts"])[:7] == m], weeks))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"SUMMARY_{since_text}.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    (OUT / f"trades_{since_text}.json").write_text(json.dumps(got, indent=0, default=str))
    print("\n".join(text))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-09-01")
    run(ap.parse_args().since)
