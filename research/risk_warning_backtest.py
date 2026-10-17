"""Research only: a warning line on risky crypto alerts (lakky, 2026-10-17).

lakky: "a warning before alert like crypto is 4% up or down and overall market is in
up side so i can avoid that trade". Two warnings, tagged on every crypto alert the
live rules would have sent (S/R zones, fibs, trendlines), Sep 1 to now:

  big move  - the coin moved >= MOVE_PCT (4%) either way over the 24 hours before
              the alert (1h Bitunix closes: last closed hour vs 24 hours before it).
  market    - the alert goes against BTC's daily trend: BUY while BTC's last closed
              daily candle is under its EMA50, SELL while above (the live zone
              trend filter's rule, scanner._trend_from_daily, applied to BTC).

The question: do warned alerts do worse than the rest? Nothing is filtered - each
group is scored the live way and shown side by side, R and % per trade and in total.

  zones     - research/zone_htf_backtest.replay (live zone engine, Bitunix candles,
              coin's own trend filter already on, scored like fibs).
  fib / TL  - fib_trendline_backtest.replay_symbol (live rules, Delta candles).

    PYTHONPATH=research python research/risk_warning_backtest.py --since 2026-09-01
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
import scanner  # noqa: E402
import zone_htf_backtest as zh  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, bitunix_candles  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "risk_warning"
MOVE_PCT = 4.0
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")))


def move_24h(hourly, ts):
    """% change from 24h before the last closed hour to that hour's close, or None."""
    opens = [c[0] for c in hourly]
    i = bisect.bisect_right(opens, ts - 3600) - 1      # last hour fully closed at ts
    j = bisect.bisect_right(opens, opens[i] - 24 * 3600) - 1 if i >= 0 else -1
    if i < 0 or j < 0 or opens[i] - opens[j] != 24 * 3600:
        return None
    return (hourly[i][4] / hourly[j][4] - 1) * 100


def btc_trend(daily, ts):
    closes = [c[4] for c in daily if c[0] + 86400 <= ts]
    if len(closes) < config.CRYPTO_TREND_EMA + 5:
        return None
    ema = pd.Series(closes).ewm(span=config.CRYPTO_TREND_EMA, adjust=False).mean().iloc[-1]
    return 1 if closes[-1] > ema else -1


def tag(t, hourly, btc_daily):
    mv = move_24h(hourly, t["alert_ts"]) if hourly else None
    trend = btc_trend(btc_daily, t["alert_ts"])
    side = t["plan"]["side"]
    t["move_24h"] = mv
    t["big_move"] = mv is not None and abs(mv) >= MOVE_PCT
    t["btc_against"] = trend is not None and (trend < 0 if side == "long" else trend > 0)
    return t


def collect(since, now, limit):
    scanner.ZONE_BASE_EXTRA = 1
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    btc_daily = fbt._cached("rw_btc_1d", lambda: bitunix_candles("BTCUSD", "1d", now - 500 * 86400, now))
    symbols = list(config.CRYPTO_WATCHLIST)[: limit or None]

    def one(symbol):
        out = []
        try:
            hourly = fbt._cached(f"rw_{symbol}_1h", lambda: bitunix_candles(symbol, "1h", since - 3 * 86400, now))
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} 1h failed: {error}")
            hourly = []
        try:
            data = zh.crypto_load(symbol, now, since)
            if data:
                base, evals, daily = data
                for tf in zh.TIMEFRAMES:
                    out += zh.replay(CRYPTO, symbol, tf, base[tf], evals[trades.EVAL_RESOLUTION[CRYPTO][tf]],
                                     daily, since, now)
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} zones failed: {error}")
        try:
            data = fbt.crypto_data(symbol, now)
            if data:
                out += [t for t in fbt.replay_symbol(CRYPTO, symbol, *data, now)
                        if t["kind"] in ("fib", "trendline")]
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} fib/TL failed: {error}")
        out = [tag(t, hourly, btc_daily) for t in out if t["alert_ts"] >= since]
        print(f"{symbol}: {len(out)} alerts")
        return out

    got = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(one, symbols):
            got += res
    return got


SPLITS = (
    ("all alerts", lambda t: True),
    ("no warning", lambda t: not t["big_move"] and not t["btc_against"]),
    ("4%+ move", lambda t: t["big_move"]),
    ("BTC against", lambda t: t["btc_against"]),
    ("both warnings", lambda t: t["big_move"] and t["btc_against"]),
    ("any warning", lambda t: t["big_move"] or t["btc_against"]),
)


def table(got):
    rows = []
    for kind, name in (("zone", "S/R zone"), ("fib", "fib"), ("trendline", "TL")):
        for group, tfs in GROUPS:
            items = [t for t in got if t["kind"] == kind and t["tf"] in tfs]
            for label, keep in SPLITS:
                pick = [t for t in items if keep(t)]
                if pick:
                    r = row(label, pick)
                    rows.append({"alert": name, "tf": group, **r})
    return pd.DataFrame(rows)


def sensitivity(got):
    rows = []
    for pct in (3, 4, 5, 6):
        for label, keep in ((f"move >= {pct}%", lambda t, p=pct: t["move_24h"] is not None and abs(t["move_24h"]) >= p),
                            (f"move < {pct}%", lambda t, p=pct: t["move_24h"] is not None and abs(t["move_24h"]) < p)):
            pick = [t for t in got if keep(t)]
            if pick:
                rows.append(row(label, pick))
    # direction of the move vs the trade: into the level (BUY after a drop) or away from it
    for label, keep in (("4%+ move, with trade side (BUY after rise / SELL after drop)",
                         lambda t: t["big_move"] and (t["move_24h"] > 0) == (t["plan"]["side"] == "long")),
                        ("4%+ move, against trade side (BUY after drop / SELL after rise)",
                         lambda t: t["big_move"] and (t["move_24h"] > 0) != (t["plan"]["side"] == "long"))):
        pick = [t for t in got if keep(t)]
        if pick:
            rows.append(row(label, pick))
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--limit", type=int, default=0, help="first N coins (smoke test)")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    since = int(pd.Timestamp(args.since, tz=IST).timestamp())
    now = int(time.time())
    got = collect(since, now, args.limit)
    df, sens = table(got), sensitivity(got)
    df.to_csv(OUT / "summary.csv", index=False)
    sens.to_csv(OUT / "sensitivity.csv", index=False)
    pd.DataFrame([{**{k: t[k] for k in ("symbol", "tf", "kind", "alert_ts", "move_24h", "big_move", "btc_against")},
                   "side": t["plan"]["side"], "entry": t["plan"]["entry"], "outcome": t["result"]["outcome"],
                   "net_r": (trades.booked_r(t["plan"], t["market"], t["result"])[1] if t["result"]["filled"]
                             else None)} for t in got]).to_csv(OUT / "trades.csv", index=False)
    text = [f"# Risk warnings on crypto alerts ({args.since} to now)", "",
            f"Warnings: coin moved >= {MOVE_PCT:g}% either way in the 24h before the alert; alert against "
            f"BTC's daily EMA{config.CRYPTO_TREND_EMA} trend. Nothing filtered - each group scored the live way, "
            "net after fees. Zones on Bitunix (scored like fibs), fib/TL on Delta.", "",
            df.to_markdown(index=False), "", "## Move size and direction (all crypto alerts)", "",
            sens.to_markdown(index=False), ""]
    (OUT / "RISK_WARNING.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
