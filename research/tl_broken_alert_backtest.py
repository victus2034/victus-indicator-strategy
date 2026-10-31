"""Research only: trade the TL BROKEN alert in the direction of the break
(lakky, 2026-10-31: "do a backtest of alerts of broken trendline").

The live scanner posts TL BROKEN when a candle CLOSES through a live trendline:
support closed below -> SELL, resistance closed above -> BUY. Rules tested:
  close  = market entry when the alert lands: the open of the first candle after the
           break candle closes (on 5m/1h evaluation candles, so a gap counts)
  hl     = stop order at the break candle's low (sell) / high (buy), fills within
           FIB_TL_ENTRY_WAIT_BARS candles (lakky's 2026-10-23 rule, PR #65, for comparison)
Stops (lakky 2026-10-31: "sl is above the previous candle"):
  candle = the break candle's other end (sell: its high, buy: its low)
  before = the candle before the break candle (sell: its high, buy: its low)
  both   = the wider of those two
  line   = back inside the line: the line's price on the entry candle
Exits: 1R, no breakeven, no hold limit (the live TL exit) and 2R + BE, hold 20 (the fib exit).
Compared with the live TL touch trades over the same period. Crypto on Delta candles,
NSE on Yahoo, Delta fees + stop slippage. Crypto trades filling within 15 min of US
CPI / PPI / FOMC are left out (news_window_backtest); NSE closes before those releases.

    PYTHONPATH=research python research/tl_broken_alert_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import bisect
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import news_window_backtest as nw  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE, TF_SECONDS, bitunix_candles, candle_is_closed  # noqa: E402
from trendlines import SUPPORT, build_trendlines  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "tl_broken_alert"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")), ("1D", ("1d",)), ("1W", ("1w",)), ("1M", ("1M",)))
RULES = (("at close, SL break candle, 1R", "close", "candle", 1),
         ("at close, SL break candle, 2R+BE", "close", "candle", 2),
         ("at close, SL candle before break, 1R", "close", "before", 1),
         ("at close, SL candle before break, 2R+BE", "close", "before", 2),
         ("at close, SL wider of the two, 1R", "close", "both", 1),
         ("at close, SL line, 1R", "close", "line", 1),
         ("break low/high, SL break candle, 1R", "hl", "candle", 1))


def breaks(market, symbol, tf, base, evalc, now, since):
    """Every break trade, for each rule, on one chart."""
    if base and not candle_is_closed(market, base[-1][0], tf, now):
        base = base[:-1]
    n = len(base)
    if n <= fbt.MIN_BARS or not evalc:
        return []
    times = [c[0] for c in base]
    opens, highs, lows, closes = ([c[j] for c in base] for j in (1, 2, 3, 4))
    eval_ts = [c[0] for c in evalc]
    per_bar = trades.EVAL_PER_BAR[market][tf]
    wait_n = config.FIB_TL_ENTRY_WAIT_BARS * per_bar
    horizon = (config.FIB_TL_MAX_HOLD_BARS + 1) * per_bar
    out = []
    for line in build_trendlines(highs, lows, closes, config.TRENDLINE_SWING_LENGTH, config.TRENDLINES_KEEP,
                                 history=True):
        b = line.broken_at
        if b is None or b <= line.created or not line.live_during(b) or b >= n:
            continue                       # never drawn (confirm-window break) or not on the chart
        close_ts = times[b + 1] if b + 1 < n else times[b] + TF_SECONDS[tf]
        if close_ts < since:
            continue
        long = line.kind != SUPPORT        # resistance broken -> buy
        k0 = bisect.bisect_left(eval_ts, close_ts)
        if k0 >= len(evalc):
            continue                       # alert not out yet / no candle after it
        fills = {"close": (k0, evalc[k0][1])}
        level = highs[b] if long else lows[b]
        fills["hl"] = (None, level)
        for k in range(k0, min(k0 + wait_n, len(evalc))):
            _ts, o, h, l, _c = evalc[k]
            if (h >= level) if long else (l <= level):
                fills["hl"] = (k, max(level, o) if long else min(level, o))    # a gap fills at the open
                break
        entry_bar = min(b + 1, n - 1)
        for label, how, stop, target in RULES:
            fill, fill_px = fills[how]
            if stop == "candle":
                sl = lows[b] if long else highs[b]
            elif stop == "before":
                sl = lows[b - 1] if long else highs[b - 1]
            elif stop == "both":
                sl = min(lows[b - 1], lows[b]) if long else max(highs[b - 1], highs[b])
            else:
                sl = line.price_at(b + 1)
            plan = {"side": "long" if long else "short", "entry": fill_px, "sl": sl}
            if target == 1:
                plan["target_r"] = 1
            if fill is None or ((sl >= fill_px) if long else (sl <= fill_px)):
                result = dict(outcome="no fill", filled=False, fill_ts=None, half=False, r1=False, r2=False,
                              sl=False, be=False, ambiguous=False, resolved=True, end_ts=None)
            else:
                after = evalc[fill:] if target == 1 else evalc[fill:fill + horizon]
                # simulate's own fill test is a limit's; the fill candle trades through the entry anyway
                result = trades.simulate(plan, market, tf, evalc[fill][0] - 1, after)
            out.append({"market": market, "symbol": symbol, "tf": tf, "kind": "break", "rule": label,
                        "how": how, "alert_ts": close_ts, "plan": plan, "result": result,
                        "line": "S" if line.kind == SUPPORT else "R", "break_ts": times[b]})
    return out


def news_fine(symbol, since, now):
    fine = []
    for _name, ev in nw.EVENT_TS:
        if ev < since - 86400 or ev > now:
            continue
        day = ev - ev % 86400
        try:
            fine += fbt._cached(f"nw_{symbol}_5m_{day}",
                                lambda day=day: bitunix_candles(symbol, "5m", day, min(day + 86400 - 1, now)))
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} 5m failed: {error}")
    return sorted(fine)


def news_flag(t, fine):
    if t["market"] != CRYPTO or not t["result"]["filled"]:
        return None
    probe = dict(t)
    if t["kind"] == "break" and t.get("how") == "hl":   # a stop entry: flip the side for the 5m fill test
        probe["plan"] = dict(t["plan"], side="short" if t["plan"]["side"] == "long" else "long")
    return nw.in_window(probe, fine)


def crypto_one(symbol, now, since):
    out = []
    try:
        data = fbt.crypto_data(symbol, now)
        if not data:
            return []
        base, evals = data
        for tf in fbt.TIMEFRAMES:
            out += breaks(CRYPTO, symbol, tf, base.get(tf, []), evals.get(trades.EVAL_RESOLUTION[CRYPTO][tf], []),
                          now, since)
        live = [dict(t, rule="live TL touch (now)") for t in fbt.replay_symbol(CRYPTO, symbol, base, evals, now)
                if t["kind"] == "trendline" and t["alert_ts"] >= since]
        out += live
        fine = news_fine(symbol, since, now)
        for t in out:
            t["news"] = news_flag(t, fine)
    except Exception as error:  # noqa: BLE001
        print(f"crypto {symbol} failed: {error}")
    print(f"{symbol}: {sum(1 for t in out if t['kind'] == 'break') // len(RULES)} breaks")
    return out


def row(label, items):
    filled = [t for t in items if t["result"]["filled"]]
    booked = []
    for t in filled:
        net = trades.booked_r(t["plan"], t["market"], t["result"])[1]
        if net is not None:
            booked.append((net, net * trades.risk_pct(t["plan"])))
    wins = sum(1 for t in filled if t["result"]["r1"] if t["plan"].get("target_r") == 1) + \
        sum(1 for t in filled if t["result"]["r2"] if t["plan"].get("target_r") != 1)
    n = len(booked)
    return {"rule": label, "signals": len(items), "trades": n,
            "win_%": round(100 * wins / n) if n else None,
            "avg_stop_%": round(sum(trades.risk_pct(t["plan"]) for t in filled) / len(filled), 2) if filled else None,
            "R_per_trade": round(sum(r for r, _ in booked) / n, 3) if n else None,
            "%_per_trade": round(sum(p for _, p in booked) / n, 3) if n else None,
            "R_total": round(sum(r for r, _ in booked), 1)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-nse", action="store_true")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    global OUT
    if args.out:
        OUT = OUT.parent / f"tl_broken_alert_{args.out}"
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    since = int(pd.Timestamp(args.since, tz=IST).timestamp())
    now = int(time.time())
    symbols = list(scanner.active_watchlist())[: args.limit or None]
    got = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(lambda s: crypto_one(s, now, since), symbols):
            got += res
    if not args.no_nse:
        import nse_scanner
        for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
            for tf in fbt.TIMEFRAMES:
                got += breaks(NSE, symbol, tf, base.get(tf, []), evals.get(trades.EVAL_RESOLUTION[NSE][tf], []),
                              now, since)
            got += [dict(t, rule="live TL touch (now)", news=None)
                    for t in fbt.replay_symbol(NSE, symbol, base, evals, now)
                    if t["kind"] == "trendline" and t["alert_ts"] >= since]
    for t in got:
        t.setdefault("news", None)
    kept = [t for t in got if not t["news"]]
    labels = [r[0] for r in RULES] + ["live TL touch (now)"]
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for label in labels:
                pick = [t for t in kept if t["market"] == market and t["tf"] in tfs and t["rule"] == label]
                if pick:
                    rows.append({"market": market, "tf": group, **row(label, pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame([{"market": t["market"], "symbol": t["symbol"], "tf": t["tf"], "rule": t["rule"],
                   "line": t.get("line"), "side": t["plan"]["side"],
                   "signal_ist": pd.Timestamp(t["alert_ts"], unit="s", tz=IST).strftime("%Y-%m-%d %H:%M"),
                   "entry": t["plan"]["entry"], "sl": t["plan"]["sl"], "stop_%": round(trades.risk_pct(t["plan"]), 3),
                   "outcome": t["result"]["outcome"],
                   "net_r": trades.booked_r(t["plan"], t["market"], t["result"])[1] if t["result"]["filled"] else None,
                   "news": t["news"][0] if t["news"] else ""}
                  for t in got if t["kind"] == "break"]).to_csv(OUT / "trades.csv", index=False)
    skipped = sum(1 for t in got if t["news"])
    text = [f"# TL BROKEN alerts traded in the break direction ({args.since} to now)", "",
            "Support closed below -> sell; resistance closed above -> buy. 'at close' = market entry at the next "
            "candle's open; 'break low/high' = stop order at the break candle's far end within 5 candles. "
            "SL break candle = its other end; SL candle before break = that candle's high (sell) / low (buy); "
            "wider = the further of the two; SL line = back inside the line. "
            "Net after fees + stop slippage; % = net R x stop %. "
            f"Crypto on Delta candles; {skipped} crypto trades filled within 15 min of CPI/PPI/FOMC left out.", "",
            df.to_markdown(index=False), ""]
    (OUT / "TL_BROKEN_ALERT.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
