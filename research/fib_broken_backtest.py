"""Research only (lakky, 2026-11-11): when is a fib "broken"?

Live: a fib is dead as soon as a wick trades past its strong box's stop (0.6875 of the range
from the extreme, `fib_engine.KILL`), and the opposite fib starts at once from the old extreme.
His charts (BTC Apr-May, ETH Apr-May 1D): "a fib i consider broken when a candle form below the
last level and again a candle is formed below the previous candle low", and maybe only past 0.77.

  live   wick past the stop (0.6875)
  two    a candle CLOSES past L4 (0.66), then the next candle trades past that candle's low / high
  c77    a candle closes past 0.77
  w77    a wick past 0.77
  his    research/fib_engine_nested.py: base = the last pullback low, broken = the 2-candle rule, a broken
         fib steps back to the older base (twice at most) before it flips (lakky's BTC / UNI drawings)

A fib still dies when price takes out its base / top. Live levels (L2-L4), each once, 2R + BE,
net after fees; Sep 1 to now; trades filled within 15 min of US CPI / PPI / FOMC left out.
Also writes STATE.md: the 1D fib each rule holds NOW on every crypto chart (to hold against his drawings).

    PYTHONPATH=research python research/fib_broken_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import datetime as dt
import inspect
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_engine  # noqa: E402
import fib_engine_nested  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
from fib_entry_touched_backtest import replay_all  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402
from trail_fib_tl_backtest import news  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_broken"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")), ("1D", ("1d",)), ("1W", ("1w",)), ("1M", ("1M",)))
LIVE_RUN = fib_engine.run
LIVE_REPLAY = fbt.replay
HOLD = {"c": []}          # closes of the chart being replayed, for the rules that read a close
STATE = {}                # rule -> {symbol: last 1D snapshot}
RULE = {"name": "live"}

BUY = {"two": "C['c'][i - 1] < E - ZONE1 * (E - O) and l[i] < l[i - 1]",
       "c77": "C['c'][i] < E - 0.77 * (E - O)",
       "w77": "l[i] < E - 0.77 * (E - O)"}
SELL = {"two": "C['c'][i - 1] > E + ZONE1 * (O - E) and h[i] > h[i - 1]",
        "c77": "C['c'][i] > E + 0.77 * (O - E)",
        "w77": "h[i] > E + 0.77 * (O - E)"}


def variant(rule):
    """The live engine with only the stop-kill condition changed."""
    if rule == "live":
        return LIVE_RUN
    if rule == "his":
        return lambda *a, **k: fib_engine_nested.run(*a, c=HOLD["c"], **k)
    s = inspect.getsource(fib_engine)
    for old, new in (("(not fresh and l[i] < E - KILL * (E - O))", f"(not fresh and ({BUY[rule]}))"),
                     ("(not fresh and h[i] > E + KILL * (O - E))", f"(not fresh and ({SELL[rule]}))")):
        assert s.count(old) == 1, old
        s = s.replace(old, new, 1)
    ns = {"C": HOLD}
    exec(compile(s, "fib_engine_" + rule, "exec"), ns)
    return ns["run"]


def replay(market, symbol, tf, base, evalc, now):
    """fbt.replay, handing the closes to the engine variant and keeping the 1D crypto end state."""
    closed = base[:-1] if base and not fbt.candle_is_closed(market, base[-1][0], tf, now) else base
    HOLD["c"] = [c[4] for c in closed]
    if market == CRYPTO and tf == "1d" and len(closed) > fbt.MIN_BARS:
        snaps, _ = fib_engine.run([str(c[0]) for c in closed], [c[2] for c in closed], [c[3] for c in closed],
                                  N=fbt.FIB_SWING_LENGTH)
        s = snaps[-1]
        day = lambda k: dt.datetime.fromtimestamp(closed[k][0], dt.UTC).strftime("%d %b")   # noqa: E731
        STATE.setdefault(RULE["name"], {})[symbol] = (
            f"{'BUY' if s['d'] == 1 else 'SELL'} {s['O']:g} ({day(s['Ot'])}) -> {s['E']:g} ({day(s['Et'])})")
        HOLD["c"] = [c[4] for c in closed]
    return LIVE_REPLAY(market, symbol, tf, base, evalc, now)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--rules", default="live,two,c77,w77,his")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    fbt.FIB_LEVELS = dict(config.FIB_ALERT_LEVELS)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    runs = {}
    fbt.replay = replay
    try:
        for rule in args.rules.split(","):
            RULE["name"] = rule
            fib_engine.run = variant(rule)
            runs[rule] = [t for t in replay_all(now) if t["alert_ts"] >= since and not news(t["result"].get("fill_ts"))]
    finally:
        fib_engine.run = LIVE_RUN
        fbt.replay = LIVE_REPLAY
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for level in ("all", "L2", "L3", "L4"):
                for rule, items in runs.items():
                    pick = [t for t in items if t["market"] == market and t["tf"] in tfs
                            and (level == "all" or t.get("level") == level)]
                    if pick:
                        rows.append({"market": market, "tf": group, "level": level, **row(rule, pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# When is a fib broken ({args.since} to now)", "",
            "live = wick past the stop (0.6875); two = a close past L4, then the next candle past that candle's "
            "low / high; c77 = a close past 0.77; w77 = a wick past 0.77; his = fib_engine_nested (last pullback low as "
            "base, 2-candle rule, step back to the older base before a flip). Live levels (L2-L4), each once, 2R + BE, "
            "net after fees, R and % per trade. Crypto on Delta candles. Entries filled within 15 min of US "
            "CPI/PPI/FOMC left out.", "", df.to_markdown(index=False), ""]
    (OUT / "FIB_BROKEN.md").write_text("\n".join(text))
    symbols = sorted({s for per in STATE.values() for s in per})
    state = pd.DataFrame([{"symbol": s, **{rule: STATE.get(rule, {}).get(s, "") for rule in runs}} for s in symbols])
    (OUT / "STATE.md").write_text("# The 1D fib each rule holds now (Delta candles)\n\n" + state.to_markdown(index=False) + "\n")
    print("\n".join(text))
    print(state.to_markdown(index=False))


if __name__ == "__main__":
    main()
