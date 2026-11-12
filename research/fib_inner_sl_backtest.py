"""Research only (lakky, 2026-11-12, NEAR 1D chart): the fib SL from a small fib drawn inside the box.

He draws a fib between a level and the next deeper one (L1 -> L2 is the weak box, L2 -> L3 the gap,
L3 -> L4 the strong box) and puts the stop on that inner fib's 2nd or 3rd line. NEAR 1D BUY: entry
L1 4.744, next level L2 4.332, inner lines 4.600 / 4.555 / 4.516 / 4.471 - his "L1 SL" is 4.557.

  live   today's rule: just past the next deeper level on 4H / 1D, candle body on 1W / 1M
  in2    the inner fib's 2nd line: 45% of the way from the level to the next deeper one
  in3    the inner fib's 3rd line: 55% of the way
  (L4 has no deeper level: its span is one box height past L4, as in the live rule)

L1-L4 all replayed, each level once, 2R + BE, net after fees; "L2-L4" = the levels that alert live.
Sep 1 to now; trades filled within 15 min of US CPI / PPI / FOMC left out.

    PYTHONPATH=research python research/fib_inner_sl_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_scanner as fts  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
from fib_entry_touched_backtest import replay_all  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402
from trail_fib_tl_backtest import news  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_inner_sl"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")), ("1D", ("1d",)), ("1W", ("1w",)), ("1M", ("1M",)))
INNER = {"in2": 0.45, "in3": 0.55}
NAMES = ("L1", "L2", "L3", "L4")
LIVE_STOPS = fbt.fib_level_stops


def inner_stops(d, base, top, share):
    """{L1..L4: stop}: `share` of the way from each level to the next deeper one."""
    lv = fts.fib_levels(d, base, top)
    box = abs(lv["L3"] - lv["L4"])
    out = {}
    for n, k in enumerate(NAMES):
        far = lv[NAMES[n + 1]] if n < 3 else lv[k] - d * box
        out[k] = lv[k] + share * (far - lv[k])
    return out


def level_stops(d, base, top, rule=None, bodies=None):
    if rule in INNER:
        return inner_stops(d, base, top, INNER[rule])
    return LIVE_STOPS(d, base, top, rule, bodies)


def median_risk(items):
    risks = sorted(trades.risk_pct(t["plan"]) for t in items)
    return round(risks[len(risks) // 2], 2) if risks else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    near = inner_stops(1, 2.272, 6.017, 0.45)         # NEAR 1D, his chart: L1 4.744 -> SL 4.557, L2 4.332 -> 4.165
    print("NEAR 1D check, in2 stops:", {k: round(v, 3) for k, v in near.items()})
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    fbt.FIB_LEVELS = {tf: NAMES for tf in config.FIB_ALERT_LEVELS}
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    runs = {}
    fbt.fib_level_stops = level_stops
    try:
        for rule in ("live", "in2", "in3"):
            fbt.FIB_SL_RULE = None if rule == "live" else rule
            runs[rule] = [t for t in replay_all(now) if t["alert_ts"] >= since and not news(t["result"].get("fill_ts"))]
    finally:
        fbt.fib_level_stops = LIVE_STOPS
        fbt.FIB_SL_RULE = None
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            for level in ("L2-L4", "L1", "L2", "L3", "L4"):
                for rule, items in runs.items():
                    pick = [t for t in items if t["market"] == market and t["tf"] in tfs
                            and (t.get("level") == level or (level == "L2-L4" and t.get("level") != "L1"))]
                    if pick:
                        rows.append({"market": market, "tf": group, "level": level, **row(rule, pick),
                                     "median_stop_%": median_risk(pick)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib SL on the inner fib ({args.since} to now)", "",
            "live = today's stop (past the next deeper level on 4H / 1D, candle body on 1W / 1M); in2 / in3 = 45% / 55% of "
            "the way from the level to the next deeper one (the 2nd / 3rd line of a fib drawn between them). Each level "
            "once, 2R + BE, net after fees, R and % per trade. Crypto on Delta candles. Entries filled within 15 min of "
            "US CPI/PPI/FOMC left out.", "", df.to_markdown(index=False), ""]
    (OUT / "FIB_INNER_SL.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
