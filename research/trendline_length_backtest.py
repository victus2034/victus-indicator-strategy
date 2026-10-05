"""Trendline swing length backtest - trendlines only, fibs and zones untouched.

Lakky, 2026-10-05: a trendline appears only once its second swing has
TRENDLINE_SWING_LENGTH (10) candles after it. Would a shorter confirmation
(7 / 5 / 3) alert better? Replays fib_trendline_backtest.replay with only the
trendline length changed (fibs skipped), same data, trade rules and scoring.
Nothing live changes.

    python research/trendline_length_backtest.py --lengths 10,7,5,3
"""
import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fib_trendline_backtest as bt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, NSE, TIMEFRAMES  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "trendline_length"
LIVE_TFS = ["4h", "1d", "1w", "1M"]


def no_fibs(stamp, highs, lows, N):
    return [{"d": 1, "O": 0.0, "E": 0.0, "Ot": 0, "Et": 0}] * len(stamp), None


def load(now):
    data = []
    for symbol in scanner.active_watchlist():
        try:
            d = bt.crypto_data(symbol, now)
            if d:
                data.append((CRYPTO, symbol, d))
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
    import nse_scanner
    for symbol, d in bt.nse_data(nse_scanner.load_watchlist()).items():
        data.append((NSE, symbol, d))
    return data


def run(length, data, now):
    bt.TRENDLINE_SWING_LENGTH = length
    out = []
    for market, symbol, (base, evals) in data:
        for tf in TIMEFRAMES:
            res = trades.EVAL_RESOLUTION[market][tf]
            out += bt.replay(market, symbol, tf, base.get(tf, []), evals.get(res, []), now)
    return [t for t in out if t["kind"] == "trendline"]


def stats(items):
    filled = [t for t in items if t["result"]["filled"]]
    net = [trades.booked_r(t["plan"], t["market"], t["result"])[1] for t in filled]
    net = [x for x in net if x is not None]
    count = defaultdict(int)
    for t in filled:
        count[t["result"]["outcome"]] += 1
    wins, losses = count["2R"], count["SL"]
    days = bt.span_days(items)
    return {"alerts": len(items), "per_day": len(items) / days if items else 0, "filled": len(filled),
            "net": sum(net), "per_trade": sum(net) / len(net) if net else 0,
            "win2r": wins / (wins + losses) if wins + losses else 0}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lengths", default="10,7,5,3")
    a = p.parse_args()
    lengths = [int(x) for x in a.lengths.split(",")]
    bt.fib_engine = SimpleNamespace(run=no_fibs)
    now = time.time()
    data = load(now)
    results = {L: run(L, data, now) for L in lengths}
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["# Trendline swing length backtest (trendlines only)", "",
             f"Lengths {lengths}; current live = 10. Same data, trade rules and scoring as "
             "`fib_trendline_backtest.py` (Delta candles for crypto, Yahoo for NSE; +2R target, BE at +0.5R, fees). "
             "Fibs and zones not touched. Live timeframes: 4H/1D/1W/1M.", ""]
    for scope, tfs in (("LIVE timeframes (4H/1D/1W/1M)", LIVE_TFS), ("30m (alerts off)", ["30m"])):
        lines += [f"## {scope}", "", "| market | tf | length | alerts | /day | filled | win@2R | net R | R/trade |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for market in (CRYPTO, NSE):
            for tf in tfs + (["all"] if len(tfs) > 1 else []):
                for L in lengths:
                    sel = [t for t in results[L] if t["market"] == market and (t["tf"] == tf or (tf == "all" and t["tf"] in tfs))]
                    s = stats(sel)
                    lines.append(f"| {market} | {tf} | {L} | {s['alerts']} | {s['per_day']:.1f} | {s['filled']} | "
                                 f"{s['win2r'] * 100:.0f}% | {s['net']:+.1f} | {s['per_trade']:+.3f} |")
        lines.append("")
    lines += ["## Total, live timeframes, both markets", "", "| length | alerts | filled | net R | R/trade |", "|---|---|---|---|---|"]
    for L in lengths:
        s = stats([t for t in results[L] if t["tf"] in LIVE_TFS])
        lines.append(f"| {L} | {s['alerts']} | {s['filled']} | {s['net']:+.1f} | {s['per_trade']:+.3f} |")
    (OUT / f"RESULTS_{a.lengths.replace(',', '_')}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
