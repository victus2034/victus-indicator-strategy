"""Live CoinDCX / Delta bot: TL breaks only vs today's touch + break (lakky, 2026-11-21: "Yes" to
"backtest the live bot trading breaks only and dropping touches").

The live bot's rules (coindcx_live.py), replayed on its 16 crypto coins (config.CRYPTO_WATCHLIST),
scanner awake all night (live since 15 Nov):
  touch  - waits for a closed 1h candle that trades the line and closes back, enters at market,
           stop = wick-or-body 0.75% on daily candles closed before then
           (tl_lower_tf_entry_backtest "confirm 1h, SL day")
  break  - market at the first 15m open after the break candle closes, same stop rule
           (journal_tl_setup_backtest BR rows)
  exits  - 1.5R, SL shift +1R -> +0.75R, trail TP +0.25R / 0.5R behind; fees 0.0826%, slip 0.05%
  slots  - one trade per coin, at most COINDCX_LIVE_MAX_OPEN (5) open; a waiting touch takes none
Fills within 15 min of US CPI / PPI / FOMC left out. The 10 USDT kill switch is not replayed.

    PYTHONPATH=research python research/tl_breaks_only_backtest.py --since 2025-01-01
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

import config  # noqa: E402
import journal_tl_setup_backtest as jts  # noqa: E402
import tl_lower_tf_entry_backtest as low  # noqa: E402
from journal_fib_setup_backtest import IST, ist, stats  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "tl_breaks_only"
SEP1 = int(datetime(2026, 9, 1, tzinfo=IST).timestamp())
FAR = 10 ** 12


def symbol_rows(symbol, since, now):
    try:
        touches = low.symbol_trades(symbol, since, now)["confirm 1h, SL day"]
        breaks = [t for t in jts.symbol_trades(symbol, since, now) if t["level"] == "BR"]
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} failed: {error!r}")
        return None
    for t in touches:
        t["level"] = "touch"
    return touches + breaks


def slots(rows, max_open):
    """Keep trades the live bot could take: one per coin, at most max_open at once."""
    taken = []
    for t in sorted(rows, key=lambda t: t["fill_ts"]):
        live = [x for x in taken if x["fill_ts"] <= t["fill_ts"] < x.get("exit_ts", FAR)]
        if len(live) >= max_open or any(x["symbol"] == t["symbol"] for x in live):
            continue
        taken.append(t)
    return taken


def row(name, rows):
    st = stats(sorted(rows, key=lambda t: t["fill_ts"]))
    opened = sum(1 for t in rows if t.get("outcome") == "open")
    if not st:
        return f"| {name} | 0 | | | | | | {opened} |"
    return (f"| {name} | {st['n']} | {st['wins'] / st['n'] * 100:.0f}% | {st['avg']:+.3f}R | {st['pct']:+.2f}% | "
            f"{st['tot']:+.1f}R | -{st['dd']:.1f}R | {opened} |")


HEAD = "| Set | Closed | Win | R/trade | %/trade | Total R | Max DD | Open |\n|---|---|---|---|---|---|---|---|"


def main(since_text):
    since = int(datetime.fromisoformat(since_text).replace(tzinfo=IST).timestamp())
    now = int(time.time())
    config.FIB_TL_CRYPTO_NIGHT = True
    symbols = list(config.CRYPTO_WATCHLIST)
    got, failed = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for symbol, rows in zip(symbols, pool.map(lambda s: symbol_rows(s, since, now), symbols)):
            if rows is None:
                failed.append(symbol)
                continue
            print(f"{symbol}: {len(rows)}")
            got += rows
    news = sum(1 for t in got if t.get("news"))
    ok = [t for t in got if t.get("fill_ts") is not None and t.get("outcome") != "no stop" and not t.get("news")]
    text = [f"# Live bot, 1D TL: breaks only vs touch + break - {since_text} to {ist(now)[:10]}", "",
            f"{len(symbols)} crypto coins, live bot rules (1h-confirm touches, market breaks, wick/body 0.75% SL, 1.5R + "
            "SL shift + trail), scanner awake all night, Bitunix 15m, fees 0.0826%, slip 0.05%. "
            f"{news} fills within 15 min of US CPI / PPI / FOMC left out. Kill switch not replayed."
            + (f" FAILED: {', '.join(failed)}." if failed else "")]
    periods = [("Sep 1 - now", [t for t in ok if t["fill_ts"] >= max(since, SEP1)])]
    if since < SEP1:
        periods.append((f"{since_text} - now", ok))
    for label, rows in periods:
        br = [t for t in rows if t["level"] == "BR"]
        to = [t for t in rows if t["level"] == "touch"]
        text += ["", f"## {label}", "", HEAD,
                 row("Live now: touch + break, 1 per coin, max 5", slots(rows, config.COINDCX_LIVE_MAX_OPEN)),
                 row("Breaks only, 1 per coin, max 5", slots(br, config.COINDCX_LIVE_MAX_OPEN)),
                 row("Touch + break, no slot limit", rows),
                 row("Breaks only, no slot limit", br),
                 row("Touches only, no slot limit", to)]
        text += ["", f"### {label}, breaks only by month (slots)", "", HEAD]
        b = slots(br, config.COINDCX_LIVE_MAX_OPEN)
        for m in sorted({ist(t["fill_ts"])[:7] for t in b}):
            text.append(row(m, [t for t in b if ist(t["fill_ts"])[:7] == m]))
        text += ["", f"### {label}, breaks only by side (slots)", "", HEAD]
        text += [row(sd, [t for t in b if t["side"] == sd]) for sd in ("long", "short")]
        text += ["", f"### {label}, breaks only by coin (slots)", "", HEAD]
        text += [row(s, [t for t in b if t["symbol"] == s]) for s in symbols]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"SUMMARY_{since_text}.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    (OUT / f"trades_{since_text}.json").write_text(json.dumps(
        [{k: t.get(k) for k in ("symbol", "level", "side", "entry", "sl", "fill_ts", "exit_ts", "r", "risk_pct", "outcome")} for t in ok]))
    print("\n".join(text))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2025-01-01")
    main(ap.parse_args().since)
