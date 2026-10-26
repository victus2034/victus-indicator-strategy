"""Research only: a fib's stop kill needs a wick a little past the stop (lakky, ENA 4H, 2026-10-26).

ENA 4H: the SELL fib 0.22579 -> 0.18371 died on the 26 Oct 12:00 UTC candle, whose
high 0.21279 passed its stop 0.21264 by 0.07%; the chart then drew BUY 0.18371 ->
0.21279. lakky's chart keeps the SELL fib. Variant: the stop kills only once a
wick passes it by more than BUFFER of price (the base/top kill is unchanged).
Live fib rules otherwise. Entries filled within 15 min of US CPI/PPI/FOMC left out.

    PYTHONPATH=research python research/fib_kill_buffer_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import inspect
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_engine  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
from fib_entry_touched_backtest import replay_all  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402
from trail_fib_tl_backtest import news  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_kill_buffer"
GROUPS = (("4H", ("4h",)), ("1D", ("1d",)), ("1W", ("1w",)), ("1M", ("1M",)), ("1D+", ("1d", "1w", "1M")))
LIVE_RUN = fib_engine.run


def variant(buffer):
    if not buffer:
        return LIVE_RUN
    s = inspect.getsource(fib_engine)
    for old, new in (("l[i] < E - KILL * (E - O)", f"l[i] < (E - KILL * (E - O)) * (1 - {buffer!r})"),
                     ("h[i] > E + KILL * (O - E)", f"h[i] > (E + KILL * (O - E)) * (1 + {buffer!r})")):
        assert s.count(old + ")") == 1
        s = s.replace(old + ")", new + ")", 1)
    ns = {}
    exec(compile(s, "fib_engine_variant", "exec"), ns)
    return ns["run"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    runs = {}
    for label, buffer in (("live: any wick past the stop", 0), ("wick > 0.1% past the stop", 0.001),
                          ("wick > 0.25% past the stop", 0.0025), ("wick > 0.5% past the stop", 0.005)):
        fib_engine.run = variant(buffer)
        runs[label] = [t for t in replay_all(now) if t["alert_ts"] >= since and not news(t["result"].get("fill_ts"))]
    fib_engine.run = LIVE_RUN
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for label, items in runs.items():
                pick = [t for t in items if t["market"] == market and t["tf"] in tfs]
                if pick:
                    rows.append({"market": market, "tf": group, **row(label, pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib stop kill with a small buffer ({args.since} to now)", "",
            "Live fib rules otherwise (every live level, S/R stop, 2R + BE), net after fees. R and % per trade "
            "and in total. Entries filled within 15 min of US CPI/PPI/FOMC left out.", "",
            df.to_markdown(index=False), ""]
    (OUT / "FIB_KILL_BUFFER.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
