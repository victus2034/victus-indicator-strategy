"""Research only (lakky, 2026-11-04, second reading): the daily fib after a breakout of yesterday's range.

lakky's Nov 4 Nifty 5m chart: the fib runs from Nov 3's low to Nov 4's high (price broke above Nov 3's
high), and he BOUGHT both 0.55-0.66 boxes - the upper box (0.55-0.66 measured up from the low, i.e. a
0.34-0.45 pullback) and the lower box (0.55-0.66 pullback from the high). Mirrored for a break below
yesterday's low: fib from yesterday's high to today's low, SELL both boxes.

Rules here:
  fib     anchor = yesterday's opposite extreme; the other end = today's high (low) so far, from the candles
          before the current one. It stretches with new highs only until the first fill of that side,
          then stays fixed for the rest of the day (one fib a day)
  entry   each box once a day, at its edge facing price ("near") or its far edge ("far"); price must come
          into it from the breakout side
  stop    25% of the box past its far edge (live fib rule)
  target  the fib's extreme (the day's high/low, his Nov 4 trade), or 1R / 2R; open trades close at day end
  order   stop on the fill candle counts, targets from the next candle, stop before target
Costs / news filter as research/daily_fib_backtest.py.

    PYTHONPATH=research python research/daily_fib_breakout_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import daily_backtest_summary as dbs  # noqa: E402
from daily_fib_backtest import FUTURES_COST, SLIP, by_day, news, summarize  # noqa: E402
from fib_trendline_data import IST  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "daily_fib_breakout"
TARGETS = ("high", "1R", "2R")
ENTRIES = ("near", "far")


def fib_boxes(side, anchor, ext, entry_at):
    """[(box, entry, stop)] for the two boxes. side buy: anchor = yesterday's low, ext = today's high."""
    d = 1 if side == "buy" else -1
    rng = (ext - anchor) * d
    box = 0.11 * rng
    # buy: upper box = anchor + .55..66 R, lower box = ext - .55..66 R; near edge = the top (first touched)
    upper_top, lower_top = anchor + d * 0.66 * rng, ext - d * 0.55 * rng
    out = []
    for name, top in (("upper", upper_top), ("lower", lower_top)):
        bottom = top - d * box
        out.append((name, top if entry_at == "near" else bottom, bottom - d * 0.25 * box))
    return out


def run_side(side, prev_hi, prev_lo, bars, entry_at, target, be_offset):
    d = 1 if side == "buy" else -1
    anchor, level = (prev_lo, prev_hi) if d == 1 else (prev_hi, prev_lo)
    ext, frozen, trades, done = None, False, [], set()
    for i, (ts, o, h, lo, c, *_) in enumerate(bars):
        if i and not frozen:
            seen = max(b[2] for b in bars[:i]) if d == 1 else min(b[3] for b in bars[:i])
            ext = seen if (seen - level) * d > 0 else None      # only after yesterday's range is broken
        if ext is None:
            continue
        for box, entry, stop in fib_boxes(side, anchor, ext, entry_at):
            if box in done or (o - entry) * d <= 0:              # must come in from the breakout side
                continue
            if ((lo if d == 1 else h) - entry) * d > 0:
                continue
            done.add(box)
            frozen = True
            risk = abs(entry - stop)
            tgt = ext if target == "high" else entry + d * float(target[:-1]) * risk
            res = walk(d, entry, stop, tgt, bars, i)
            trades.append({"box": box, "entry": entry, "stop": stop, "target": tgt, "ext": ext,
                           "fill_ts": ts, **res, "risk": risk})
    return trades


def walk(d, entry, stop, target, bars, i):
    ts, o, h, lo, c, *_ = bars[i]
    if ((lo if d == 1 else h) - stop) * d <= 0:
        return {"exit": stop * (1 - d * SLIP / 100), "outcome": "SL"}
    for ts, o, h, lo, c, *_ in bars[i + 1:]:
        if ((lo if d == 1 else h) - stop) * d <= 0:
            return {"exit": stop * (1 - d * SLIP / 100), "outcome": "SL"}
        if ((h if d == 1 else lo) - target) * d >= 0:
            return {"exit": target, "outcome": "TP"}
    return {"exit": bars[-1][4], "outcome": "EOD"}


def backtest(market, symbol, candles, tz, since, cost, be_offset, extra=()):
    rows = []
    days = list(by_day(candles, tz).items())
    for (pday, pbars), (day, bars) in zip(days, days[1:]):
        if day < since:
            continue
        ph, pl = max(b[2] for b in pbars), min(b[3] for b in pbars)
        for side in ("buy", "sell"):
            for entry_at in ENTRIES:
                for target in TARGETS:
                    for t in run_side(side, ph, pl, bars, entry_at, target, be_offset):
                        d = 1 if side == "buy" else -1
                        stop_pct = t["risk"] / t["entry"] * 100
                        gross = d * (t["exit"] - t["entry"]) / t["risk"]
                        row = {"market": market, "symbol": symbol, "day": str(day), "side": side,
                               "rule": f"{entry_at} / {target}", "box": t["box"], "prev_high": ph, "prev_low": pl,
                               "fib_end": round(t["ext"], 6), "entry": round(t["entry"], 6),
                               "stop": round(t["stop"], 6), "target": round(t["target"], 6),
                               "stop_%": round(stop_pct, 4),
                               "fill": datetime.fromtimestamp(t["fill_ts"], tz).strftime("%H:%M"),
                               "outcome": t["outcome"], "exit": round(t["exit"], 6), "gross_r": round(gross, 4),
                               "net_r": round(gross - cost / stop_pct, 4), "news": news(t["fill_ts"])}
                        for name, cst in extra:
                            row[f"net_r_{name}"] = round(gross - cst / stop_pct, 4)
                        rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-09-01")
    args = ap.parse_args()
    since = datetime.strptime(args.since, "%Y-%m-%d").date()
    OUT.mkdir(parents=True, exist_ok=True)
    import bitunix_data as bx
    import fib_trendline_data as fdata
    rows = []
    for interval, label in (("5m", "NIFTY 5m"), ("1h", "NIFTY 1h (2y)")):
        candles = fdata.nse_download(["^NSEI"], interval).get("^NSEI", [])
        print(f"^NSEI {interval}: {len(candles)} candles")
        start = since if interval == "5m" else datetime(2000, 1, 1).date()
        rows += backtest(label, "NIFTY", candles, IST, start, dbs.ROUND_TRIP_COST_PCT, dbs.BREAK_EVEN_OFFSET_PCT,
                         extra=[("fut", FUTURES_COST)])
    start = datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc).timestamp() - 86400
    today = datetime.now(timezone.utc).date()
    for sym in config.CRYPTO_WATCHLIST:
        try:
            candles = bx.klines(bx.pair_for(sym, sym), "5m", start, time.time())
        except Exception as error:  # noqa: BLE001
            print(f"{sym}: {error}")
            continue
        candles = [c for c in candles if datetime.fromtimestamp(c[0], timezone.utc).date() < today]
        rows += backtest("Crypto 5m", sym, candles, timezone.utc, since, dbs.CRYPTO_ROUND_TRIP_COST_PCT,
                         dbs.CRYPTO_BREAK_EVEN_OFFSET_PCT)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "trades.csv", index=False)
    print(df[(df.market == "NIFTY 5m") & (df.day >= "2026-11-03")].to_string())
    skipped = int(df["news"].sum())
    df = df[~df["news"]]
    table = []
    for market in df["market"].unique():
        for rule in df["rule"].unique():
            pick = df[(df.market == market) & (df.rule == rule)]
            r = {"market": market, "rule": rule, **summarize(pick.assign(outcome=pick.outcome.replace("TP", "1R")))}
            if "net_r_fut" in pick and pick["net_r_fut"].notna().any():
                s = summarize(pick.assign(outcome=pick.outcome.replace("TP", "1R")), "net_r_fut")
                r["R fut cost"], r["% fut cost"] = s.get("R/trade"), s.get("%/trade")
            table.append(r)
    tdf = pd.DataFrame(table)
    tdf.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Daily fib after a break of yesterday's range (run {datetime.now(IST):%Y-%m-%d %H:%M} IST)", "",
            f"win_% = target hit. {skipped} trades within 15 min of US CPI/PPI/FOMC left out.", "",
            tdf.to_markdown(index=False), ""]
    (OUT / "DAILY_FIB_BREAKOUT.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
