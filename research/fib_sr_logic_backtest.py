"""Research only - nothing here is imported by the live scanners.

Lakky (2026-10-08, Notion 20 follow-up): try the support/resistance zone trade
logic on the fib zones before changing anything. The S/R rules that carry over:

  stop   - 25% of the zone's height beyond its far edge (scanner.planned_stop_price,
           ZONE_SL_MODE "zone_pct"), instead of the fib's own SL inside the zone
  cap    - no alert when that stop is more than MAX_ALERT_STOP_PCT (1.5%) from entry
  trend  - a buy only while the last closed daily candle is above its EMA50, a sell
           only below (CRYPTO_TREND_FILTER; live it is crypto only - shown for NSE too)

Entry stays the zone's near edge (same as S/R). The 15-bar "too young" wait is not
carried over: it must not apply to fibs (Lakky, 2026-10-04).

    python research/fib_sr_logic_backtest.py --since 2026-09-01
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

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402
from fib_trendline_scanner import fib_zones  # noqa: E402
from fib_zone_preference import row  # noqa: E402  (research/ on sys.path as the script dir)

OUT = Path(__file__).resolve().parent / "out" / "fib_sr_logic"
HEIGHT = config.ZONE_SL_HEIGHT_PCT / 100
CAP = config.MAX_ALERT_STOP_PCT
EMA = config.CRYPTO_TREND_EMA


def with_sr_stops(d, base, top):
    """Today's two zones (1, 2) plus the same boxes with the S/R stop ("1sr", "2sr")."""
    out = fib_zones(d, base, top)
    for zone in list(out):
        pad = (zone["high"] - zone["low"]) * HEIGHT
        sl = zone["low"] - pad if d == 1 else zone["high"] + pad
        out.append({**zone, "zone": f"{zone['zone']}sr", "sl": sl})
    return out


def trend_at(daily, ts):
    """+1/-1/None from closed daily candles before ts, as scanner._trend_from_daily."""
    if not daily:
        return None
    opens = [c[0] for c in daily]
    closes = [c[4] for c in daily[:bisect.bisect_right(opens, ts - 86400)]]
    if len(closes) < EMA + 5:
        return None
    ema = pd.Series(closes).ewm(span=EMA, adjust=False).mean().iloc[-1]
    return 1 if closes[-1] > ema else -1


def tag(trades_, daily):
    for t in trades_:
        plan = t["plan"]
        t["stop_pct"] = abs(plan["entry"] - plan["sl"]) / plan["entry"] * 100
        trend = trend_at(daily, t["alert_ts"])
        t["against_trend"] = trend is not None and (trend < 0 if plan["side"] == "long" else trend > 0)
    return trades_


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    fbt.fib_zones = with_sr_stops
    fbt.ALERT_ZONES = (1, 2, "1sr", "2sr")
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    got = []

    def one(symbol):
        try:
            data = fbt.crypto_data(symbol, now)
            return tag(fbt.replay_symbol(CRYPTO, symbol, *data, now), data[0].get("1d")) if data else []
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            return []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(one, scanner.active_watchlist()):
            got += result
    import nse_scanner
    for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
        got += tag(fbt.replay_symbol(NSE, symbol, base, evals, now), base.get("1d"))

    fibs = [t for t in got if t["kind"] == "fib" and t["alert_ts"] >= since]
    print(f"{len(fibs)} fib alerts since {args.since}")
    capped = lambda t: CAP <= 0 or t["stop_pct"] <= CAP          # noqa: E731
    trend = lambda t: not t["against_trend"]                     # noqa: E731
    schemes = [
        ("live today: both zones, fib SL", lambda t: t["zone"] in (1, 2)),
        ("PR #22: deeper zone, fib SL", lambda t: t["zone"] == 2),
        ("PR #22 + daily trend", lambda t: t["zone"] == 2 and trend(t)),
        ("S/R stop, both zones", lambda t: t["zone"] in ("1sr", "2sr")),
        ("S/R stop, deeper zone", lambda t: t["zone"] == "2sr"),
        ("S/R stop + 1.5% cap, both zones", lambda t: t["zone"] in ("1sr", "2sr") and capped(t)),
        ("S/R stop + 1.5% cap, deeper zone", lambda t: t["zone"] == "2sr" and capped(t)),
        ("S/R full (stop + cap + trend), both zones", lambda t: t["zone"] in ("1sr", "2sr") and capped(t) and trend(t)),
        ("S/R full (stop + cap + trend), deeper zone", lambda t: t["zone"] == "2sr" and capped(t) and trend(t)),
    ]
    rows = []
    for market in (CRYPTO, NSE):
        mk = [t for t in fibs if t["market"] == market]
        for label, keep in schemes:
            items = [t for t in mk if keep(t)]
            if items:
                rows.append({"market": market, "tf": "all", **row(label, items)})
        for tf in fbt.TIMEFRAMES:
            for label, keep in (schemes[1], schemes[8]):
                items = [t for t in mk if t["tf"] == tf and keep(t)]
                if items:
                    rows.append({"market": market, "tf": tf, **row(label, items)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib zones with the S/R trade logic: {args.since} to now", "",
            f"S/R stop = {config.ZONE_SL_HEIGHT_PCT:g}% of zone height beyond the far edge; cap = stop within "
            f"{CAP:g}% of entry; trend = daily EMA{EMA}. Entry = near edge everywhere. Live trade rules "
            "(2R target, BE at +0.5R), net R after fees. Crypto replayed on Delta candles.", "",
            df.to_markdown(index=False), ""]
    (OUT / "FIB_SR_LOGIC.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
