"""Research only (lakky, 2026-11-12: "run the backtest on this basis" + his journal Signals screen).

The inner-fib SL (research/fib_inner_sl_backtest.py) scored the way his journal is set:
  CRYPTO 1D fib alerts, all coins, levels L2-L4; Exit at 1.5R; Move SL "SL shift" at +1R to +0.75R;
  Trail TP on, TP +0.5R, SL 0.25R behind; hold till TP / SL; with fees.

SL columns:
  live   the alert's own stop (just past the next deeper level)
  wb     his journal pick "Wick or body, at least 0.75% past entry": the most recent closed 1D candle
         whose wick, or body, is that far past the entry - the closer of the two (alert's stop if none)
  in2    the inner fib's 2nd line (45% of the way from the level to the next deeper one)
  in3    the inner fib's 3rd line (55%)

The journal's own walk (coindcx_strategy_backtest.walk) on Bitunix 1h candles, limit entry filled within
20 days, fees 0.0826%, stop slip 0.05%. Fills within 15 min of US CPI / PPI / FOMC left out.

    PYTHONPATH=research python research/fib_inner_sl_journal_backtest.py --since 2026-06-01
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_data  # noqa: E402
import config  # noqa: E402
import coindcx_strategy_backtest as cs  # noqa: E402
import fib_inner_sl_backtest as inner  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, HISTORY_START, IST, bitunix_candles  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_inner_sl"
RULES = ("live", "wb", "in2", "in3")
LEVELS = ("L2", "L3", "L4")
cs.TRAIL_STEP, cs.TRAIL_GAP = 0.5, 0.25           # his screen: TP +0.5R, SL 0.25R behind


def symbol_trades(symbol, since, now):
    contract = scanner.delta_contract(symbol)
    pair = bitunix_data.pair_for(symbol, contract)

    def get(res, start):
        return fbt._cached(f"ft_{pair}_{res}_{int(start) // 86400}", lambda: bitunix_candles(pair, res, start, now))

    daily, four = get("1d", HISTORY_START), get("4h", HISTORY_START)
    hourly = get("1h", since - 3 * 86400)
    band = fbt.band_for("1d")
    cols = [[c[k] for c in daily] for k in range(5)]
    out = []
    for rule in RULES:
        fbt.FIB_SL_RULE = rule if rule in inner.INNER else None
        alerts = [t for t in fbt.replay(CRYPTO, symbol, "1d", daily, four, now)
                  if t["kind"] == "fib" and t["alert_ts"] >= since and t.get("level") in LEVELS]
        for t in alerts:
            plan = dict(t["plan"])
            if rule == "wb":
                bar = sum(1 for ts in cols[0] if ts + 86400 <= t["alert_ts"])
                stop = trades.candle_stop(plan["side"] == "long", plan["entry"], bar, cols[1], cols[2], cols[3], cols[4])
                if stop is not None:
                    plan["sl"] = stop
            start = cs.alert_hour(plan, t["alert_ts"], None, hourly, band)
            w = cs.walk(plan, start, hourly, now)
            news = bool(w.get("filled")) and cs.news_overlap(w["fill_ts"], w["fill_ts"] + cs.H)
            out.append({"rule": rule, "symbol": symbol, "level": t.get("level"), "alert_ts": t["alert_ts"],
                        "news": news, **w})
    return out


def _safe(symbol, since, now):
    try:
        return symbol_trades(symbol, since, now)
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} failed: {error}")
        return []


def line(name, items):
    done = [t for t in items if t.get("filled") and not t["news"] and t.get("r") is not None]
    if not done:
        return f"| {name} | 0 | | | | | | | |"
    n = len(done)
    rs = [t["r"] for t in done]
    wins, tot = sum(r > 0 for r in rs), sum(rs)
    gain, loss = sum(r for r in rs if r > 0), -sum(r for r in rs if r < 0)
    pct = sum(t["r"] * t["risk_pct"] for t in done) / n
    risks = sorted(t["risk_pct"] for t in done)
    run = peak = dd = 0.0
    for t in sorted(done, key=lambda t: t["alert_ts"]):
        run += t["r"]
        peak = max(peak, run)
        dd = max(dd, peak - run)
    opened = sum(1 for t in items if t.get("outcome") == "open")
    return (f"| {name} | {n} | {wins / n * 100:.0f}% | {tot:+.1f}R | {tot / n:+.2f}R | {pct:+.2f}% | "
            f"{gain / loss if loss else 0:.2f} | -{dd:.1f}R | {risks[n // 2]:.2f}% | {opened} |")


HEAD = ("| SL | Trades | Won | Total R | R/trade | %/trade | Profit factor | Max DD | Median stop | Still open |\n"
        "|---|---|---|---|---|---|---|---|---|---|")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-06-01")
    args = ap.parse_args()
    since = int(pd.Timestamp(args.since, tz=IST).timestamp())
    now = int(time.time())
    fbt.FIB_LEVELS = {tf: ("L1", "L2", "L3", "L4") for tf in config.FIB_ALERT_LEVELS}
    fbt.fib_level_stops = inner.level_stops
    got = []
    # one symbol at a time: the SL rule is a module setting while a symbol replays
    with ThreadPoolExecutor(max_workers=1) as pool:
        for symbol, res in zip(config.CRYPTO_WATCHLIST, pool.map(lambda s: _safe(s, since, now), config.CRYPTO_WATCHLIST)):
            print(f"{symbol}: {len(res)} rows")
            got += res
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(got).to_csv(OUT / "journal_trades.csv", index=False)
    day = lambda s: int(pd.Timestamp(s, tz=IST).timestamp())
    month = now - 31 * 86400
    windows = (("Last 1 month (as on his screen)", month), ("Sep 1 to now", day("2026-09-01")), (f"{args.since} to now", since))
    text = ["# Inner-fib SL, scored like the journal (crypto 1D fibs, L2-L4)", "",
            "Exit 1.5R, SL shift at +1R to +0.75R, Trail TP +0.5R with the SL 0.25R behind, hold till TP / SL, fees "
            "0.0826%, stop slip 0.05%, limit entry filled within 20 days, Bitunix 1h candles, all "
            f"{len(config.CRYPTO_WATCHLIST)} crypto coins. live = the alert's stop, wb = wick or body 0.75% past entry, "
            "in2 / in3 = the inner fib's 2nd / 3rd line. Fills within 15 min of US CPI/PPI/FOMC left out.", ""]
    for title, start in windows:
        text += [f"## {title}", "", HEAD]
        text += [line(rule, [t for t in got if t["rule"] == rule and t["alert_ts"] >= start]) for rule in RULES]
        text += [""]
    text += ["## By level, Sep 1 to now", "", HEAD]
    for lv in LEVELS:
        text += [line(f"{lv} {rule}", [t for t in got if t["rule"] == rule and t["level"] == lv
                                        and t["alert_ts"] >= day("2026-09-01")]) for rule in RULES]
    (OUT / "FIB_INNER_SL_JOURNAL.md").write_text("\n".join(text) + "\n")
    print("\n".join(text))


if __name__ == "__main__":
    main()
