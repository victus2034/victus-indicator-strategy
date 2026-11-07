"""lakky's CoinDCX strategy, backtested (2026-11-07: "this is my so far final strategy ...
do a backtest ... 1st top 3-5 cryptos and 2nd all the cryptos of the coindcx list").

The settings, from his journal's Signals tab (Fib alerts, CRYPTO 1D):
  - every 1D crypto fib alert, all levels L1-L4, each its own live stop
  - limit entry at the alert's entry, filled within 20 daily candles of the alert
  - Exit at 1.5R; Move SL "SL shift": once +1R trades, the stop goes to +0.75R
  - Trail TP on: at 1.5R the stop locks at +1.5R and the target steps +0.25R; the
    stop then trails 0.5R behind the highest target reached (never under 1.5R)
  - Hold till TP / SL (no time limit); a candle touching the stop and a target is the stop
  - the stop fills 0.05% past its price; fees CoinDCX limit in (0.02%) + market out
    (0.05%) + 18% GST = 0.0826% of the position
  - Demo account: 1,000 start, fixed risk 75 a trade, leverage capped at 20x
The journal's own scoring (index.html tgtWalk / tgtScore / demoRun), on Bitunix 1h
candles, with the alerts fib_trendline_backtest.replay finds under today's live rules.

Groups: top 3 and top 5 coins by CoinDCX volume (30-day average, research/out/volume),
and every crypto on the watchlist (all 25 pass the CoinDCX 100M rule).
Fills within 15 min of US CPI / PPI / FOMC are left out (backtest standard).

    PYTHONPATH=research python research/coindcx_strategy_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_data  # noqa: E402
import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, HISTORY_START, IST, bitunix_candles, monthly_from_daily  # noqa: E402
from news_window_backtest import EVENT_TS, WINDOW_MIN  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "coindcx_strategy"
VOLUME = Path(__file__).resolve().parent / "out" / "volume" / "volume_7d_30d.json"

TARGET_R, SHIFT_AT, SHIFT_TO, TRAIL_STEP, TRAIL_GAP = 1.5, 1.0, 0.75, 0.25, 0.5
COST_PCT, SLIP_PCT = 0.0826, 0.05
FILL_WINDOW = 20 * 86400
START, RISK, LEVERAGE = 1000.0, 75.0, 20.0
H = 3600


def news_overlap(start, end):
    """True when [start, end) touches a US CPI / PPI / FOMC release +-15 min (Jan 2025 - Dec 2026)."""
    return any(start <= ev + WINDOW_MIN * 60 and end > ev - WINDOW_MIN * 60 for _name, ev in EVENT_TS)


def exit_r(level, risk_pct, side):
    """A moved stop's exit, in net R (journal tgtScore exit())."""
    s = -1 if side == "short" else 1
    return level - (1 + s * level * risk_pct / 100) * SLIP_PCT / risk_pct - COST_PCT / risk_pct


def walk(plan, alert_from, hourly, now):
    """The journal's walk on 1h candles [ts, o, h, l, c]. alert_from = first 1h candle
    that may fill. Returns a dict: filled, fill_ts, r (net), outcome, exit_ts; r None = open."""
    entry, stop0, side = plan["entry"], plan["sl"], plan["side"]
    s = -1 if side == "short" else 1
    risk_pct = abs(entry - stop0) / entry * 100
    rk = risk_pct / 100
    mv = lambda p: s * (p - entry) / entry / rk          # move in R
    bars = [c for c in hourly if c[0] >= alert_from]
    fill = next((i for i, c in enumerate(bars) if c[0] < alert_from + FILL_WINDOW
                 and ((c[3] <= entry) if s > 0 else (c[2] >= entry))), None)
    if fill is None:
        open_ = bars and bars[-1][0] < alert_from + FILL_WINDOW - H
        return {"filled": False, "outcome": "waiting" if open_ else "no fill"}
    f = bars[fill]
    res = {"filled": True, "fill_ts": f[0], "risk_pct": risk_pct}
    hit = lambda c, lvl: (c[3] <= lvl) if s > 0 else (c[2] >= lvl)
    if hit(f, stop0):
        return {**res, "r": -1 - (stop0 / entry) * SLIP_PCT / risk_pct - COST_PCT / risk_pct, "outcome": "SL",
                "exit_ts": f[0]}
    stop_r, why, tgt = None, "", TARGET_R      # stop_r: a moved stop, in R
    best = max(0.0, mv(f[4]))

    def raise_to(level, label):
        nonlocal stop_r, why
        if stop_r is None or level > stop_r + 1e-9:
            stop_r, why = level, label

    def apply(b):
        nonlocal tgt
        while b >= tgt - 1e-9:
            raise_to(max(TARGET_R, tgt - TRAIL_GAP), "Trail TP")
            tgt += TRAIL_STEP
        if SHIFT_AT < TARGET_R and b >= SHIFT_AT - 1e-9:
            raise_to(SHIFT_TO, "SL shift")

    apply(best)
    for c in bars[fill + 1:]:
        level = entry * (1 + s * stop_r * rk) if stop_r is not None else stop0
        if hit(c, level):
            if stop_r is None:
                return {**res, "r": -1 - (stop0 / entry) * SLIP_PCT / risk_pct - COST_PCT / risk_pct,
                        "outcome": "SL", "exit_ts": c[0]}
            return {**res, "r": exit_r(stop_r, risk_pct, side), "outcome": why, "exit_ts": c[0]}
        best = max(best, mv(c[2] if s > 0 else c[3]))
        apply(best)
    return {**res, "r": None, "outcome": "open"}


def alert_hour(plan, ts4h, hourly_ts, hourly, band):
    """The 1h candle inside the alert's 4h candle where price first came into the band;
    fills count from the next one."""
    entry, s = plan["entry"], -1 if plan["side"] == "short" else 1
    edge = entry * (1 + band) if s > 0 else entry * (1 - band)
    for c in hourly:
        if ts4h <= c[0] < ts4h + 4 * H and ((c[3] <= edge) if s > 0 else (c[2] >= edge)):
            return c[0] + H
    return ts4h + 4 * H


def symbol_trades(symbol, since, now):
    contract = scanner.delta_contract(symbol)
    pair = bitunix_data.pair_for(symbol, contract)

    def get(res, start):
        return fbt._cached(f"ft_{pair}_{res}_{int(start) // 86400}", lambda: bitunix_candles(pair, res, start, now))

    daily, four = get("1d", HISTORY_START), get("4h", HISTORY_START)
    hourly = get("1h", since - 3 * 86400)
    alerts = [t for t in fbt.replay(CRYPTO, symbol, "1d", daily, four, now)
              if t["kind"] == "fib" and t["alert_ts"] >= since]
    out = []
    band = fbt.band_for("1d")
    hourly_ts = [c[0] for c in hourly]
    for t in alerts:
        start = alert_hour(t["plan"], t["alert_ts"], hourly_ts, hourly, band)
        w = walk(t["plan"], start, hourly, now)
        news = bool(w.get("filled")) and news_overlap(w["fill_ts"], w["fill_ts"] + H)
        out.append({"symbol": symbol, "level": t.get("level"), "side": t["plan"]["side"],
                    "entry": t["plan"]["entry"], "sl": t["plan"]["sl"], "alert_ts": t["alert_ts"],
                    "news": news, **w})
    return out


def demo(rows):
    """journal demoRun: alerts in the order they fired, fixed risk, leverage capped."""
    bal, peak, low, dd = START, START, START, 0.0
    for t in sorted(rows, key=lambda t: t["alert_ts"]):
        risk = min(RISK, bal)
        lev = risk / (t["risk_pct"] / 100) / bal
        if lev > LEVERAGE:
            risk = bal * LEVERAGE * t["risk_pct"] / 100
        pnl = max(-bal, risk * t["r"])
        bal += pnl
        peak, low = max(peak, bal), min(low, bal)
        dd = max(dd, (peak - bal) / peak * 100 if peak > 0 else 0)
    return bal, dd, low


def row(name, items):
    done = [t for t in items if t.get("filled") and not t["news"] and t.get("r") is not None]
    if not done:
        return f"| {name} | 0 | | | | | | | |"
    n = len(done)
    wins = sum(t["r"] > 0 for t in done)
    tot = sum(t["r"] for t in done)
    pct = sum(t["r"] * t["risk_pct"] for t in done) / n
    bal, dd, low = demo(done)
    opened = sum(1 for t in items if t.get("outcome") == "open")
    return (f"| {name} | {n} | {wins / n * 100:.0f}% | {tot:+.1f}R | {tot / n:+.2f}R | {pct:+.2f}% | "
            f"{bal:,.0f} ({(bal - START) / START * 100:+.0f}%) | {dd:.0f}% | {opened} |")


HEAD = ("| Group | Trades | Won | Total R | R/trade | %/trade | Demo 1,000 -> | Max DD | Still open |\n"
        "|---|---|---|---|---|---|---|---|---|")


def ranked():
    rows = json.loads(VOLUME.read_text(encoding="utf-8"))
    vol = {r["watched"]: r.get("dcx_30d") or 0 for r in rows if r.get("watched")}
    return sorted(config.CRYPTO_WATCHLIST, key=lambda s: -vol.get(s, 0)), vol


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-09-01")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    since = int(pd.Timestamp(args.since, tz=IST).timestamp())
    now = int(time.time())
    fbt.FIB_LEVELS = config.FIB_ALERT_LEVELS        # every live level (1D: L1-L4), as live
    order, vol = ranked()
    got = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for symbol, res in zip(order, pool.map(lambda s: _safe(s, since, now), order)):
            print(f"{symbol}: {len(res)} alerts")
            got += res
    OUT.mkdir(parents=True, exist_ok=True)
    tag = args.tag or args.since
    (OUT / f"trades_{tag}.json").write_text(json.dumps(got, indent=0), encoding="utf-8")
    top3, top5 = order[:3], order[:5]
    pick = lambda syms: [t for t in got if t["symbol"] in syms]
    lines = [f"# CoinDCX strategy backtest - 1D crypto fibs, {args.since} to {pd.Timestamp(now, unit='s', tz=IST):%Y-%m-%d}",
             "",
             "Exit 1.5R, SL to +0.75R at 1R, Trail TP +0.25R with SL 0.5R behind (TP locked), held till TP / SL; "
             "fill within 20 days; fees 0.0826% (CoinDCX limit in, market out, GST); stop slip 0.05%; "
             "demo 1,000, fixed 75 risk, max 20x. Bitunix 1h candles. "
             f"{sum(t['news'] for t in got)} fills within 15 min of US CPI/PPI/FOMC left out.",
             "",
             f"Top by CoinDCX 30d volume: {', '.join(s[:-3] + f' ({vol.get(s, 0):,.0f}M)' for s in top5)}",
             "", HEAD,
             row("Top 3 (" + "/".join(s[:-3] for s in top3) + ")", pick(top3)),
             row("Top 5 (" + "/".join(s[:-3] for s in top5) + ")", pick(top5)),
             row(f"All {len(order)} coins", got),
             "", "## By level (all coins)", "", HEAD]
    for lv in ("L1", "L2", "L3", "L4"):
        lines.append(row(lv, [t for t in got if t["level"] == lv]))
    lines += ["", "## By coin", "", HEAD]
    for s in order:
        lines.append(row(s[:-3], pick([s])))
    outcomes = {}
    for t in got:
        if t.get("filled") and not t["news"]:
            outcomes[t["outcome"]] = outcomes.get(t["outcome"], 0) + 1
    lines += ["", "Exits: " + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items())),
              f"Alerts {len(got)}, filled {sum(1 for t in got if t.get('filled'))}."]
    text = "\n".join(lines)
    (OUT / f"SUMMARY_{tag}.md").write_text(text + "\n", encoding="utf-8")
    print(text)


def _safe(symbol, since, now):
    try:
        return symbol_trades(symbol, since, now)
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} failed: {error}")
        return []


if __name__ == "__main__":
    main()
