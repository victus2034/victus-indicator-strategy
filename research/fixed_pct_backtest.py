"""Research only - nothing here is imported by the live scanners.

Lakky (2026-10-10): keep the entries we have, but trade them with a fixed
1.5% stop and a 3% or 4% target, and only with the trend (daily EMA50, the
CRYPTO_TREND_FILTER rule, applied to every market here).

  entries  - zones: the live, scored trades (daily_backtest_finalized_records)
             and their recorded fill; fib / trendline: history replay with
             today's rules, filled as live (fib_trendline_trades.simulate).
  exit     - stop 1.5% from entry (counts on the fill candle), target 3% or 4%
             (from the next candle); a candle touching both = stop. Optional
             breakeven: at +0.5R the stop moves past entry by the live offset.
             Out at the close after HOLD_BARS candles of the alert timeframe.
  costs    - live round trip (crypto 0.0826%, NSE 0.1063%) and 0.05% slip on stops.

    python research/fixed_pct_backtest.py --state FINALIZED.jsonl --since 2026-09-01
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import daily_backtest_summary as dbs  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from daily_backtest_summary import market_class  # noqa: E402
from fib_sr_logic_backtest import trend_at  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE, TF_SECONDS, delta_candles, nse_download  # noqa: E402
from trend_filter_all_backtest import CRYPTO_FILTER_LIVE, against  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fixed_pct"
SL_PCT = 1.5
TARGETS = (3.0, 4.0)
HOLD_BARS = 20
COST = {CRYPTO: dbs.CRYPTO_ROUND_TRIP_COST_PCT, NSE: dbs.ROUND_TRIP_COST_PCT}
BE_OFFSET = {CRYPTO: dbs.CRYPTO_BREAK_EVEN_OFFSET_PCT, NSE: dbs.BREAK_EVEN_OFFSET_PCT}
SLIP = dbs.SL_FILL_SLIPPAGE_PCT


def fixed_exit(side, entry, fill_ts, candles, market, tf, target_pct, breakeven):
    """Net R of one filled trade: (r, outcome). candles [ts, o, h, l, c], fill candle included."""
    long = side == "long"
    sign = 1 if long else -1
    sl = entry * (1 - sign * SL_PCT / 100)
    tp = entry * (1 + sign * target_pct / 100)
    half = entry * (1 + sign * SL_PCT / 200)
    be = entry * (1 + sign * BE_OFFSET[market] / 100)
    cost_r = COST[market] / SL_PCT
    stop_r = -1 - SLIP / SL_PCT
    end = fill_ts + HOLD_BARS * TF_SECONDS[tf]
    step = candles[1][0] - candles[0][0] if len(candles) > 1 else 0
    stop, moved, last = sl, False, None
    for ts, _o, h, l, c in candles:
        if ts + step <= fill_ts:
            continue
        fill_candle = ts <= fill_ts
        hit_stop = (l <= stop) if long else (h >= stop)
        if hit_stop:
            r = (sign * (stop - entry) / entry * 100 - SLIP) / SL_PCT if moved else stop_r
            return r - cost_r, "BE" if moved else "SL"
        if not fill_candle:
            if (h >= tp) if long else (l <= tp):
                return target_pct / SL_PCT - cost_r, "TP"
            if breakeven and not moved and ((h >= half) if long else (l <= half)):
                stop, moved = be, True
        last = c
        if ts >= end:
            break
    if last is None or (candles and candles[-1][0] < end and time.time() < end):
        return None, "open"
    return sign * (last - entry) / entry * 100 / SL_PCT - cost_r, "time"


def zone_trades(path, since, now):
    out = []
    for line in open(path):
        if not line.strip():
            continue
        r = json.loads(line)
        if not r.get("filled") or r.get("net_realized_r") is None or not r.get("entry_time"):
            continue
        ts = pd.Timestamp(r["alert_time"]).timestamp()
        cls = market_class(r["symbol"])
        if ts < since or (cls == "CRYPTO" and ts >= CRYPTO_FILTER_LIVE):
            continue
        out.append({"kind": "zone", "cls": cls, "market": NSE if cls == "NSE" else CRYPTO,
                    "symbol": r["symbol"], "tf": r["timeframe"], "side": r["side"], "alert_ts": ts,
                    "entry": float(r["entry_price"]), "fill_ts": pd.Timestamp(r["entry_time"]).timestamp(),
                    "live_r": float(r["net_realized_r"])})
    start = since - 400 * 86400
    daily, evals = {}, defaultdict(dict)
    nse = sorted({t["symbol"] for t in out if t["cls"] == "NSE"})
    if nse:
        daily.update(nse_download(nse, "1d"))
        for res in ("5m", "1h"):
            evals[res].update(nse_download(nse, res))
    for symbol in sorted({t["symbol"] for t in out if t["cls"] != "NSE"}):
        contract = scanner.delta_contract(symbol)
        if not contract:
            continue
        try:
            daily[symbol] = delta_candles(contract, "1d", start, now)
            for res in ("5m", "1h"):
                evals[res][symbol] = delta_candles(contract, res, since - 86400, now)
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} candles failed: {error}")
    for t in out:
        t["against"] = against(trend_at(daily.get(t["symbol"]), t["alert_ts"]), t["side"])
        res = trades.EVAL_RESOLUTION[t["market"]][t["tf"]]
        t["candles"] = [c[:5] for c in evals[res].get(t["symbol"], [])]
    return out


def fib_tl_trades(since, now):
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    got = []

    def keep(market, cls, symbol, base, evals, out):
        res = []
        for t in out:
            if t["kind"] not in ("fib", "trendline") or t["alert_ts"] < since or not t["result"]["filled"]:
                continue
            plan = t["plan"]
            booked = trades.booked_r(plan, market, t["result"])[1]
            ev = evals.get(trades.EVAL_RESOLUTION[market][t["tf"]], [])
            res.append({"kind": t["kind"], "cls": cls, "market": market, "symbol": symbol, "tf": t["tf"],
                        "side": plan["side"], "alert_ts": t["alert_ts"], "entry": plan["entry"],
                        "fill_ts": t["result"]["fill_ts"], "live_r": booked,
                        "against": against(trend_at(base.get("1d"), t["alert_ts"]), plan["side"]),
                        "candles": [c[:5] for c in ev]})
        return res

    def one(symbol):
        try:
            data = fbt.crypto_data(symbol, now)
            if not data:
                return []
            return keep(CRYPTO, market_class(symbol), symbol, data[0], data[1],
                        fbt.replay_symbol(CRYPTO, symbol, *data, now))
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            return []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(one, scanner.active_watchlist()):
            got += result
    import nse_scanner
    for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
        got += keep(NSE, "NSE", symbol, base, evals, fbt.replay_symbol(NSE, symbol, base, evals, now))
    return got


def summary(label, items):
    rs = [r for r, _ in items if r is not None]
    tp = sum(1 for _, o in items if o == "TP")
    sl = sum(1 for _, o in items if o == "SL")
    return {"rule": label, "trades": len(rs), "TP": tp, "SL": sl,
            "BE": sum(1 for _, o in items if o == "BE"), "time": sum(1 for _, o in items if o == "time"),
            "win_%": round(100 * tp / len(rs)) if rs else None,
            "net_R": round(sum(rs), 1), "R_per_trade": round(sum(rs) / len(rs), 3) if rs else None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    all_trades = zone_trades(args.state, since, now) + fib_tl_trades(since, now)
    rows = []
    for (kind, cls), items in sorted(groupby(all_trades).items()):
        trend = [t for t in items if not t["against"]]
        variants = [("live rules, all trades", [(t["live_r"], "live") for t in items]),
                    ("live rules, trend only", [(t["live_r"], "live") for t in trend])]
        for target in TARGETS:
            for be in (False, True):
                label = f"SL 1.5% / TP {target:g}%{' + BE' if be else ''}, trend only"
                variants.append((label, [fixed_exit(t["side"], t["entry"], t["fill_ts"], t["candles"],
                                                    t["market"], t["tf"], target, be) for t in trend]))
        for label, results in variants:
            rows.append({"alert": kind, "market": cls, **summary(label, results)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fixed 1.5% stop, 3% / 4% target, with the trend: {args.since} to now", "",
            f"Entries as live. Stop {SL_PCT:g}% from entry, target 3% or 4%; a candle touching both is the stop. "
            f"BE = at +0.5R the stop moves past entry by the live offset. Out at the close after {HOLD_BARS} "
            "candles of the alert's timeframe ('time'). Trend = daily EMA50 on every market. Net R after "
            "fees and 0.05% stop slip, 1R = 1.5%. 'live rules' = today's stop and 2R target as scored live "
            "(zones) or replayed (fib/trendline). win_% counts target hits only.", "",
            df.to_markdown(index=False), ""]
    (OUT / "FIXED_PCT.md").write_text("\n".join(text))
    print("\n".join(text))


def groupby(items):
    groups = defaultdict(list)
    for t in items:
        groups[(t["kind"], t["cls"])].append(t)
    return groups


if __name__ == "__main__":
    main()
