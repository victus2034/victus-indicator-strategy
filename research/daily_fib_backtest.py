"""Research only (lakky, 2026-11-04): one fib per day from the previous day's high and low.

lakky's Nifty 5m chart: a fib from a day's low to its high, two 0.55-0.66 boxes - the buy box
measured down from the high (H - 0.55R .. H - 0.66R) and the sell box measured up from the low
(L + 0.55R .. L + 0.66R). "make sure it is drawn for a single day not every minute": the fib is
drawn once from the previous day's candles and stays fixed for the whole next day; either box can
trade ("when it goes in any side").

Rules here (one trade per box per day, both boxes may trade the same day):
  entry   the box's near edge (0.55), approach side only: a box the day opens past is skipped
  stop    25% of the box past its far edge (0.66) - the live fib stop rule
  exit    1R target, or 2R with breakeven at +0.5R (live fib rule); whatever is open at the
          day's last candle closes there - the fib is for that day only
  order   stop on the fill candle counts, targets from the next candle, stop before target
  costs   NSE 0.1063% round trip (live) and a futures-like 0.03%; crypto Delta 0.0826%; stop
          exits pay 0.05% slippage; breakeven stop sits the live offset past entry
"with" = the box in the direction of the previous day's move (buy box after an up day, low before
high), "against" = the other box. Trades filling within 15 min of US CPI/PPI/FOMC are left out
(none can on NSE: it is shut at those times).

Data: NIFTY (^NSEI, Yahoo) 5m (60 days Yahoo keeps) and 1h (~700 days, coarser); crypto watchlist
on Bitunix 5m, day = UTC (the TradingView daily candle).

    PYTHONPATH=research python research/daily_fib_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import daily_backtest_summary as dbs  # noqa: E402
from fib_trendline_data import IST  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "daily_fib"
NEAR, FAR, PAD = 0.55, 0.66, 0.25          # box edges as fractions of the range, stop pad (x box)
SLIP = dbs.SL_FILL_SLIPPAGE_PCT
FUTURES_COST = 0.03
RULES = {"1R": (1.0, False), "2R+BE": (2.0, True)}


def news(ts) -> bool:
    from trail_fib_tl_backtest import EVENTS
    return any(abs(ts - e) <= 15 * 60 for e in EVENTS)


def by_day(candles, tz):
    days = OrderedDict()
    for c in candles:
        days.setdefault(datetime.fromtimestamp(c[0], tz).date(), []).append(c)
    return days


def day_fib(bars):
    """(high, low, up): up = the low came before the high (an up day)."""
    hi = max(range(len(bars)), key=lambda i: bars[i][2])
    lo = min(range(len(bars)), key=lambda i: bars[i][3])
    up = lo < hi or (lo == hi and bars[hi][4] >= bars[hi][1])
    return bars[hi][2], bars[lo][3], up


def boxes(high, low):
    """{side: (entry, far edge, stop)} for the two 0.55-0.66 boxes."""
    rng = high - low
    pad = PAD * (FAR - NEAR) * rng
    return {"buy": (high - NEAR * rng, high - FAR * rng, high - FAR * rng - pad),
            "sell": (low + NEAR * rng, low + FAR * rng, low + FAR * rng + pad)}


def simulate(side, entry, stop, bars, target_r, use_be, be_offset):
    """One box over one day's bars -> None (no fill / skipped) or (fill_ts, exit, outcome)."""
    d = 1 if side == "buy" else -1
    risk = abs(entry - stop)
    if risk <= 0 or (bars[0][1] - entry) * d <= 0:      # opened at/through the entry: not approach side
        return None
    target = entry + d * target_r * risk
    be_at = entry + d * 0.5 * risk
    cur_stop, be_armed, fill = stop, False, None
    for i, (ts, o, h, l, c, *_) in enumerate(bars):
        if fill is None:
            if (l if d == 1 else h) * d > entry * d:
                continue
            fill = ts
            if (l if d == 1 else h) * d <= stop * d:     # stop on the fill candle counts
                return fill, stop * (1 - d * SLIP / 100), "SL"
            continue                                     # its high/low may predate the fill: no BE, no target
        if be_armed:
            cur_stop = entry * (1 + d * be_offset / 100)
        if (l if d == 1 else h) * d <= cur_stop * d:
            px = cur_stop * (1 - d * SLIP / 100)
            return fill, px, "BE" if cur_stop != stop else "SL"
        if (h if d == 1 else l) * d >= target * d:
            return fill, target, f"{target_r:g}R"
        if use_be and (h if d == 1 else l) * d >= be_at * d:
            be_armed = True
    return (fill, bars[-1][4], "EOD") if fill is not None else None


def backtest(market, symbol, candles, tz, since, cost, be_offset, costs_extra=()):
    rows = []
    days = list(by_day(candles, tz).items())
    for (pday, pbars), (day, bars) in zip(days, days[1:]):
        if day < since:
            continue
        high, low, up = day_fib(pbars)
        if high <= low:
            continue
        for side, (entry, far, stop) in boxes(high, low).items():
            for rule, (tr, be) in RULES.items():
                got = simulate(side, entry, stop, bars, tr, be, be_offset)
                if got is None:
                    continue
                fill_ts, exit_px, outcome = got
                d = 1 if side == "buy" else -1
                stop_pct = abs(entry - stop) / entry * 100
                gross = d * (exit_px - entry) / abs(entry - stop)
                row = {"market": market, "symbol": symbol, "day": str(day), "rule": rule, "side": side,
                       "with": "with" if (side == "buy") == up else "against",
                       "prev_high": high, "prev_low": low, "entry": round(entry, 6), "stop": round(stop, 6),
                       "stop_%": round(stop_pct, 4), "fill": datetime.fromtimestamp(fill_ts, tz).strftime("%H:%M"),
                       "outcome": outcome, "gross_r": round(gross, 4), "news": news(fill_ts),
                       "net_r": round(gross - cost / stop_pct, 4)}
                for name, c in costs_extra:
                    row[f"net_r_{name}"] = round(gross - c / stop_pct, 4)
                rows.append(row)
    return rows


def summarize(df, col="net_r"):
    if df.empty:
        return {"trades": 0}
    target = df["outcome"].str.endswith("R")
    return {"trades": len(df), "win_%": round(100 * target.mean()),
            "R/trade": round(df[col].mean(), 2), "%/trade": round((df[col] * df["stop_%"]).mean(), 3),
            "avg_stop_%": round(df["stop_%"].mean(), 3)}


def nifty(since):
    import fib_trendline_data as fdata
    out = []
    for interval, label in (("5m", "NIFTY 5m"), ("1h", "NIFTY 1h (2y)")):
        candles = fdata.nse_download(["^NSEI"], interval).get("^NSEI", [])
        if not candles:
            print(f"no ^NSEI {interval} candles")
            continue
        print(f"^NSEI {interval}: {len(candles)} candles, "
              f"{datetime.fromtimestamp(candles[0][0], IST):%Y-%m-%d} to {datetime.fromtimestamp(candles[-1][0], IST):%Y-%m-%d %H:%M}")
        start = since if interval == "5m" else datetime(2000, 1, 1).date()
        out += backtest(label, "NIFTY", candles, IST, start, dbs.ROUND_TRIP_COST_PCT, dbs.BREAK_EVEN_OFFSET_PCT,
                        costs_extra=[("fut", FUTURES_COST)])
        if interval == "5m":
            # lakky's own drawing (Nov 3 low -> Nov 4 high) and the plain Nov 3 fib, for a hand check
            days = by_day(candles, IST)
            for name, keys in (("Nov 3 low -> Nov 4 high", ("2026-11-03", "2026-11-04")), ("Nov 3 only", ("2026-11-03",))):
                bars = [b for k, v in days.items() if str(k) in keys for b in v]
                if bars:
                    h, lo, up = day_fib(bars)
                    print(name, f"high {h:.2f} low {lo:.2f} up={up}",
                          {s: tuple(round(x, 2) for x in v) for s, v in boxes(h, lo).items()})
    return out


def crypto(since):
    import bitunix_data as bx
    out = []
    start = datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc).timestamp() - 86400
    for sym in config.CRYPTO_WATCHLIST:
        try:
            candles = bx.klines(bx.pair_for(sym, sym), "5m", start, time.time())
        except Exception as error:  # noqa: BLE001
            print(f"{sym}: {error}")
            continue
        print(f"{sym}: {len(candles)} 5m candles")
        # drop the forming day: only whole days are traded
        today = datetime.now(timezone.utc).date()
        candles = [c for c in candles if datetime.fromtimestamp(c[0], timezone.utc).date() < today]
        out += backtest("Crypto 5m", sym, candles, timezone.utc, since, dbs.CRYPTO_ROUND_TRIP_COST_PCT,
                        dbs.CRYPTO_BREAK_EVEN_OFFSET_PCT)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-09-01")
    ap.add_argument("--skip-crypto", action="store_true")
    args = ap.parse_args()
    since = datetime.strptime(args.since, "%Y-%m-%d").date()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = nifty(since) + ([] if args.skip_crypto else crypto(since))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "trades.csv", index=False)
    skipped = int(df["news"].sum()) if not df.empty else 0
    df = df[~df["news"]] if not df.empty else df
    table = []
    for market in df["market"].unique():
        for rule in RULES:
            for part in ("all", "with", "against"):
                pick = df[(df["market"] == market) & (df["rule"] == rule)]
                if part != "all":
                    pick = pick[pick["with"] == part]
                rng = f"{pick['day'].min()} to {pick['day'].max()}" if len(pick) else "-"
                table.append({"market": market, "rule": rule, "boxes": part, "range": rng, **summarize(pick)})
                if "net_r_fut" in pick and pick["net_r_fut"].notna().any():
                    s = summarize(pick, "net_r_fut")
                    table[-1]["R fut cost"] = s.get("R/trade")
                    table[-1]["% fut cost"] = s.get("%/trade")
    tdf = pd.DataFrame(table)
    tdf.to_csv(OUT / "summary.csv", index=False)
    text = [f"# One fib per day from the previous day's high/low (run {datetime.now(IST):%Y-%m-%d %H:%M} IST)", "",
            f"Entry 0.55, stop 25% of box past 0.66, closed at day end. {skipped} trades within 15 min of US "
            "CPI/PPI/FOMC left out.", "", tdf.to_markdown(index=False), ""]
    (OUT / "DAILY_FIB.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
