"""Research only (lakky, 2026-10-18: "yes do it"): the zone cards' trail test on fibs
and trendlines. Live fib / TL alerts since --since are replayed with the live rules
(fib_trendline_backtest.replay_symbol, Delta candles for crypto, Yahoo for NSE) and
each filled trade is scored twice:

  live   - its own rules: fibs 2R + breakeven, hold 20 candles; trendlines lakky's
           way (candle stop, 1R, no breakeven). trades.booked_r, net after fees.
  trail  - same entry, same first stop; from the candle after the fill the stop
           follows 0.25R behind the best price once +0.5R has traded
           (daily_backtest_summary.TRAIL_START_R / TRAIL_DISTANCE_R, as the zone
           cards' "Trail test"). No target. Out at the stop (slip paid) or at the
           close of the 20th candle of the alert's timeframe. Net after fees.

Only trades both scores have closed are compared. Trades filled within 15 min of a
US CPI / PPI / FOMC release are left out (backtest rule, 2026-10-17).

    PYTHONPATH=research python research/trail_fib_tl_backtest.py --since 2026-09-01
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

import config  # noqa: E402
import daily_backtest_summary as dbs  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "trail_fib_tl"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")))

CPI = ["2025-09-11", "2025-10-24", "2025-12-18", "2026-01-13", "2026-02-13", "2026-03-11", "2026-04-10",
       "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12", "2026-09-11", "2026-10-14", "2026-11-10"]
PPI = ["2025-09-10", "2025-11-25", "2026-01-14", "2026-01-30", "2026-02-27", "2026-03-18", "2026-04-14",
       "2026-05-13", "2026-06-11", "2026-07-15", "2026-08-13", "2026-09-10", "2026-10-15", "2026-11-13"]
FOMC = ["2025-09-17", "2025-10-29", "2025-12-10", "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
        "2026-07-29", "2026-09-16", "2026-10-28"]
EVENTS = [pd.Timestamp(f"{d} 08:30", tz="America/New_York").timestamp() for d in CPI + PPI] + \
         [pd.Timestamp(f"{d} 14:00", tz="America/New_York").timestamp() for d in FOMC]


def news(ts) -> bool:
    return ts is not None and any(abs(ts - e) <= 15 * 60 for e in EVENTS)


def trail_r(plan, market, tf, alert_ts, candles):
    """Net R of the trailing-stop score, or None when the trade never filled or is still open."""
    entry, sl = plan["entry"], plan["sl"]
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    sign = 1 if plan["side"] == "long" else -1
    per_bar = trades.EVAL_PER_BAR[market][tf]
    wait_n, hold_n = config.FIB_TL_ENTRY_WAIT_BARS * per_bar, config.FIB_TL_MAX_HOLD_BARS * per_bar
    cost_r = trades.COST_PCT[market] / trades.risk_pct(plan)
    seen = fill_index = 0
    filled = False
    active, peak = sl, 0.0
    for ts, _o, h, l, c in candles:
        if ts <= alert_ts:
            continue
        seen += 1
        if not filled:
            if seen > wait_n:
                return None
            if (l <= entry) if sign > 0 else (h >= entry):
                filled, fill_index = True, seen
                if (l <= sl) if sign > 0 else (h >= sl):
                    return trades.stop_r(plan) - cost_r
            continue
        if (l <= active) if sign > 0 else (h >= active):
            return sign * (trades.slipped(active, plan) - entry) / risk - cost_r
        if seen - fill_index >= hold_n:
            return sign * (c - entry) / risk - cost_r
        peak = max(peak, ((h - entry) if sign > 0 else (entry - l)) / risk)
        if peak >= dbs.TRAIL_START_R:
            level = entry + sign * (peak - dbs.TRAIL_DISTANCE_R) * risk
            if sign * (level - active) > 0:
                active = level
    return None


def score(market, symbol, base, evals, now, since):
    out = []
    for t in fbt.replay_symbol(market, symbol, base, evals, now):
        if t["kind"] not in ("fib", "trendline") or t["alert_ts"] < since or not t["result"]["filled"]:
            continue
        if news(t["result"]["fill_ts"]):
            continue
        live = trades.booked_r(t["plan"], market, t["result"])[1]
        candles = evals.get(trades.EVAL_RESOLUTION[market][t["tf"]], [])
        trail = trail_r(t["plan"], market, t["tf"], t["alert_ts"], candles)
        if live is None or trail is None:
            continue
        out.append({"market": market, "symbol": symbol, "kind": t["kind"], "tf": t["tf"],
                    "alert_ts": t["alert_ts"], "risk_pct": trades.risk_pct(t["plan"]),
                    "outcome": t["result"]["outcome"], "live_r": live, "trail_r": trail})
    return out


def table(df):
    rows = []
    for market in (CRYPTO, NSE):
        for kind, name in (("fib", "fib"), ("trendline", "TL")):
            for group, tfs in GROUPS:
                g = df[(df.market == market) & (df.kind == kind) & (df.tf.isin(tfs))]
                if g.empty:
                    continue
                row = {"market": market, "alert": name, "tf": group, "trades": len(g)}
                for col, label in (("live_r", "live"), ("trail_r", "trail")):
                    pct = g[col] * g["risk_pct"]
                    row[f"{label} R/trade"] = round(g[col].mean(), 3)
                    row[f"{label} %/trade"] = round(pct.mean(), 3)
                    row[f"{label} R total"] = round(g[col].sum(), 1)
                    row[f"{label} % total"] = round(pct.sum(), 1)
                rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--limit", type=int, default=0, help="first N symbols per market (smoke test)")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    got = []

    def one(symbol):
        try:
            data = fbt.crypto_data(symbol, now)
            return score(CRYPTO, symbol, *data, now, since) if data else []
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            return []
    crypto_symbols = list(scanner.active_watchlist())[: args.limit or None]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(one, crypto_symbols):
            got += result
    import nse_scanner
    nse_symbols = list(nse_scanner.load_watchlist())[: args.limit or None]
    for symbol, (base, evals) in fbt.nse_data(nse_symbols).items():
        try:
            got += score(NSE, symbol, base, evals, now, since)
        except Exception as error:  # noqa: BLE001
            print(f"nse {symbol} failed: {error}")

    df = pd.DataFrame(got)
    df.to_csv(OUT / "trades.csv", index=False)
    summary = table(df) if not df.empty else pd.DataFrame()
    summary.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Trail test on fibs and trendlines ({args.since} to now)", "",
            "Same filled trades scored two ways, net after fees: live = the live rules (fib 2R + BE, "
            "TL candle stop + 1R); trail = stop follows 0.25R behind the best price once +0.5R traded, "
            "no target, out at the stop or the 20th candle's close. % = R x the trade's stop distance. "
            "Trades filled within 15 min of US CPI/PPI/FOMC left out.", "",
            summary.to_markdown(index=False) if not summary.empty else "No trades.", ""]
    (OUT / "TRAIL_FIB_TL.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
