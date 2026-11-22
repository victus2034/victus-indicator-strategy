"""Sideways / market-regime filters a live bot can use (lakky, 2026-11-21: "is it possible to
trade with sideways filter on real account").

The journal's BTC "Sideways" filter reads the alert day's own BTC close, only known after the
day ends (look-ahead). Every filter here reads only daily candles that CLOSED before the alert
(plus, for "so far today", BTC 15m candles closed before the alert), so the live bot could run it.

Setups (journal exits, as journal_tl_setup_backtest / journal_fib_setup_backtest):
  tl   - 1D TL touch + TL BROKEN, wick/body SL 0.75%+ past entry, 1.5R + trail + SL shift
  fib  - 1D fib L2-L4, same SL and exits
Fees 0.0826%, stop slip 0.05%; fills within 15 min of US CPI / PPI / FOMC left out.

Filters (fixed thresholds picked before the run, not tuned):
  btc_prev     BTC previous day closed within +-1.5% of its open
  btc_3d       BTC close moved <= 3% over the last 3 closed days
  btc_adx20    BTC daily ADX(14) < 20          (no trend)
  btc_adx25    BTC daily ADX(14) < 25
  btc_er       BTC 10-day efficiency ratio < 0.3 (|net move| / sum of daily moves)
  btc_atr      BTC ATR(7) / ATR(30) < 0.9      (volatility shrinking)
  btc_slope    BTC EMA20 moved <= 0.5 ATR(14) over 5 days (flat EMA)
  btc_range    BTC 7-day high-low range <= 3 ATR(14)
  coin_*       the same on the alert's own coin
  btc_sofar    BTC within +-1.5% from today's 00:00 UTC open to the alert (journal script)
  btc_same     the journal's (look-ahead) - reference only, NOT usable live

    PYTHONPATH=research python research/sideways_filter_backtest.py --setup tl --since 2025-01-01
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
import journal_fib_setup_backtest as jfs  # noqa: E402
import journal_tl_setup_backtest as jts  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import HISTORY_START, bitunix_candles, delta_candles  # noqa: E402
from journal_fib_setup_backtest import DAY, IST, ist, stats  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "sideways_filter"
SEP1 = int(datetime(2026, 9, 1, tzinfo=IST).timestamp())


# ----------------------------------------------------------------- indicators on closed daily candles

def ema(xs, n):
    out, k, e = [], 2 / (n + 1), None
    for x in xs:
        e = x if e is None else e + k * (x - e)
        out.append(e)
    return out


def wilder(xs, n):
    out, v = [], None
    for i, x in enumerate(xs):
        if i < n - 1:
            out.append(None)
            continue
        v = sum(xs[:n]) / n if v is None else (v * (n - 1) + x) / n
        out.append(v)
    return out


def regime(daily):
    """daily [ts, o, h, l, c] oldest first -> per candle i, metrics known once candle i has closed."""
    o = [c[1] for c in daily]
    h = [c[2] for c in daily]
    lo = [c[3] for c in daily]
    cl = [c[4] for c in daily]
    n = len(daily)
    tr = [h[0] - lo[0]] + [max(h[i] - lo[i], abs(h[i] - cl[i - 1]), abs(lo[i] - cl[i - 1])) for i in range(1, n)]
    pdm = [0.0] + [max(h[i] - h[i - 1], 0) if h[i] - h[i - 1] > lo[i - 1] - lo[i] else 0.0 for i in range(1, n)]
    mdm = [0.0] + [max(lo[i - 1] - lo[i], 0) if lo[i - 1] - lo[i] > h[i] - h[i - 1] else 0.0 for i in range(1, n)]
    atr14, atr7, atr30 = wilder(tr, 14), wilder(tr, 7), wilder(tr, 30)
    sp, sm = wilder(pdm, 14), wilder(mdm, 14)
    dx = []
    for i in range(n):
        if atr14[i] is None or not atr14[i]:
            dx.append(None)
            continue
        p, m = 100 * sp[i] / atr14[i], 100 * sm[i] / atr14[i]
        dx.append(100 * abs(p - m) / (p + m) if p + m else 0.0)
    first = next((i for i, d in enumerate(dx) if d is not None), n)
    adx = [None] * first + wilder(dx[first:], 14)
    e20 = ema(cl, 20)
    out = []
    for i in range(n):
        m = {"body": abs(cl[i] - o[i]) / o[i] * 100 if o[i] else None}
        if i >= 3:
            m["move3"] = abs(cl[i] - cl[i - 3]) / cl[i - 3] * 100
        m["adx"] = adx[i]
        if i >= 10:
            path = sum(abs(cl[j] - cl[j - 1]) for j in range(i - 9, i + 1))
            m["er"] = abs(cl[i] - cl[i - 10]) / path if path else 0.0
        if atr7[i] and atr30[i]:
            m["atr"] = atr7[i] / atr30[i]
        if i >= 25 and atr14[i]:
            m["slope"] = abs(e20[i] - e20[i - 5]) / atr14[i]
            m["range"] = (max(h[i - 6:i + 1]) - min(lo[i - 6:i + 1])) / atr14[i]
        out.append(m)
    return out


RULES = {
    "prev": lambda m: m.get("body") is not None and m["body"] <= 1.5,
    "3d": lambda m: m.get("move3") is not None and m["move3"] <= 3,
    "adx20": lambda m: m.get("adx") is not None and m["adx"] < 20,
    "adx25": lambda m: m.get("adx") is not None and m["adx"] < 25,
    "er": lambda m: m.get("er") is not None and m["er"] < 0.3,
    "atr": lambda m: m.get("atr") is not None and m["atr"] < 0.9,
    "slope": lambda m: m.get("slope") is not None and m["slope"] <= 0.5,
    "range": lambda m: m.get("range") is not None and m["range"] <= 3,
}


class Regime:
    def __init__(self, daily):
        self.ts = [c[0] for c in daily]
        self.m = regime(daily)

    def at(self, t):
        """Metrics of the last daily candle closed by t."""
        i = bisect.bisect_right(self.ts, t - DAY) - 1
        return self.m[i] if i >= 0 else {}


# ----------------------------------------------------------------- run

def daily_for(symbol, now):
    contract = scanner.delta_contract(symbol)
    if bitunix_data.uses_bitunix(symbol):
        pair = bitunix_data.pair_for(symbol, contract)
        return fbt._cached(f"jf_{pair}_1d_{int(HISTORY_START) // DAY}", lambda: bitunix_candles(pair, "1d", HISTORY_START, now))
    return fbt._cached(f"jf_{contract}_1d_{int(HISTORY_START) // DAY}",
                       lambda: delta_candles(contract, "1d", max(HISTORY_START, now - 2000 * DAY), now))


def trades(setup, symbol, since, now):
    try:
        rows = (jts if setup == "tl" else jfs).symbol_trades(symbol, since, now)
        return rows, Regime(daily_for(symbol, now))
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} failed: {error!r}")
        return None, None


def row(name, rows):
    st = stats(sorted(rows, key=lambda t: t["alert_ts"]))
    if not st:
        return f"| {name} | 0 | | | | | |"
    return (f"| {name} | {st['n']} | {st['wins'] / st['n'] * 100:.0f}% | {st['avg']:+.3f}R | {st['pct']:+.2f}% | "
            f"{st['tot']:+.1f}R | -{st['dd']:.1f}R |")


HEAD = "| Filter | Trades | Win | R/trade | %/trade | Total R | Max DD |\n|---|---|---|---|---|---|---|"


def main(setup, since_text):
    since = int(datetime.fromisoformat(since_text).replace(tzinfo=IST).timestamp())
    now = int(time.time())
    fbt.FIB_LEVELS = config.FIB_ALERT_LEVELS
    symbols = list(config.WATCHLIST)
    got, coin_reg, failed = [], {}, []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for symbol, (rows, reg) in zip(symbols, pool.map(lambda s: trades(setup, s, since, now), symbols)):
            if rows is None:
                failed.append(symbol)
                continue
            print(f"{symbol}: {len(rows)} alerts")
            coin_reg[symbol] = reg
            got += rows
    btc = Regime(daily_for("BTCUSD", now))
    days = jts.btc_days(fbt._cached(f"jt_btc_1d_{since // DAY}", lambda: bitunix_candles("BTCUSD", "1d", since - 10 * DAY, now)))
    b15 = fbt._cached(f"jt_btc_15m_{since // DAY}", lambda: bitunix_candles("BTCUSD", "15m", since - 2 * DAY, now))
    ok = [t for t in got if t["outcome"] != "no stop" and not t.get("news")]
    for t in ok:
        bm, cm = btc.at(t["alert_ts"]), coin_reg[t["symbol"]].at(t["alert_ts"])
        t["f"] = {"all": True, "btc_same (look-ahead)": bool(jts.side_on(days, t["alert_ts"])),
                  "btc_sofar": bool(jts.side_so_far(b15, t["alert_ts"]))}
        for k, fn in RULES.items():
            t["f"][f"btc_{k}"] = fn(bm)
            t["f"][f"coin_{k}"] = fn(cm)
        t["f"]["btc_adx20+coin_adx20"] = t["f"]["btc_adx20"] and t["f"]["coin_adx20"]
        t["f"]["btc_er+coin_er"] = t["f"]["btc_er"] and t["f"]["coin_er"]
    names = list(ok[0]["f"]) if ok else []
    periods = [("Sep 1 - now", [t for t in ok if t["alert_ts"] >= max(since, SEP1)])]
    if since < SEP1:
        periods.append((f"{since_text} - now", ok))
    title = "1D TL touch + break" if setup == "tl" else "1D fib L2-L4"
    news = sum(1 for t in got if t.get("news"))
    text = [f"# Live-safe sideways filters - {title} (journal setup), to {ist(now)[:10]}", "",
            "Filters read only daily candles closed before the alert (btc_sofar: BTC 15m closed before it). "
            "Journal exits: wick/body SL 0.75%+, 1.5R + trail 0.25R / 0.5R behind, SL shift +1R -> +0.75R. "
            f"Fees 0.0826%, stop slip 0.05%. {news} fills within 15 min of US CPI / PPI / FOMC left out."
            + (f" FAILED: {', '.join(failed)}." if failed else "")]
    for label, rows in periods:
        text += ["", f"## {label}", "", HEAD] + [row(n, [t for t in rows if t["f"][n]]) for n in names]
        if setup == "tl":
            for kind in ("touch", "BR"):
                sub = [t for t in rows if t["level"] == kind]
                text += ["", f"### {label}, {kind} only", "", HEAD] + [row(n, [t for t in sub if t["f"][n]]) for n in names]
        for half, cut in (("first half", 0), ("second half", 1)):
            srt = sorted(rows, key=lambda t: t["alert_ts"])
            part = srt[: len(srt) // 2] if cut == 0 else srt[len(srt) // 2:]
            text += ["", f"### {label}, {half} of trades (stability check)", "", HEAD] + [row(n, [t for t in part if t["f"][n]]) for n in names]
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"{setup}_{since_text}"
    (OUT / f"SUMMARY_{tag}.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    (OUT / f"trades_{tag}.json").write_text(json.dumps(
        [{k: t.get(k) for k in ("symbol", "level", "side", "alert_ts", "r", "risk_pct", "outcome", "f")} for t in ok]))
    print("\n".join(text))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", choices=("tl", "fib"), default="tl")
    ap.add_argument("--since", default="2025-01-01")
    a = ap.parse_args()
    main(a.setup, a.since)
