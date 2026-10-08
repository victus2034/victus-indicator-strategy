"""Research only - nothing here is imported by the live scanners.

Lakky's fib rule (2026-10-08, LINKUSDT 1D screenshots): for a buy the lower
fib box is the STRONG zone and the upper box the WEAK one (mirrored for a
sell). Entry levels in priority order:

  P1 = strong zone, far edge   (buy: lower box bottom 0.66 - LINK 12.362)
  P2 = strong zone, near edge  (buy: lower box top 0.55 - 12.929; today's Zone 2 entry)
  P3 = weak zone, far edge     (buy: upper box bottom 0.55 - 13.445)
  The weak zone's near edge (14.012 - today's Zone 1 entry, "W") is not used.
  A sell mirrors it.

Mapping used here (an assumption, not drawn on the screenshots): the side
follows the fib's direction as it does live (up fib = buys, down fib =
sells). P2 and W keep today's entry and stop. P1 and P3 sit on a far edge,
where today's stop (inside the box) would be on the wrong side, so each gets
its own box's risk distance placed beyond the edge.

Compares, Sep 1 to now, crypto + NSE, net R after fees:
  live (W + P2), PR #22 (P2 only), new rule (P1 + P2 + P3), and each level alone.

    python research/fib_priority_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
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

OUT = Path(__file__).resolve().parent / "out" / "fib_priority"


def priority_levels(d, base, top):
    """P1/P2/P3 (and today's W) as zone dicts the replay understands (low/high = where the alert band sits)."""
    zone1, zone2 = fib_zones(d, base, top)

    def far_edge(zone, name):
        risk = abs(zone["entry"] - zone["sl"])
        edge = zone["low"] if d == 1 else zone["high"]
        return dict(zone=name, low=edge, high=edge, entry=edge, sl=edge - risk if d == 1 else edge + risk)

    return [far_edge(zone2, "P1"), {**zone2, "zone": "P2"}, far_edge(zone1, "P3"), {**zone1, "zone": "W"}]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    fbt.fib_zones = priority_levels
    fbt.ALERT_ZONES = ("P1", "P2", "P3", "W")
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    got = []

    def one(symbol):
        try:
            data = fbt.crypto_data(symbol, now)
            return fbt.replay_symbol(CRYPTO, symbol, *data, now) if data else []
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            return []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(one, scanner.active_watchlist()):
            got += result
    import nse_scanner
    for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
        got += fbt.replay_symbol(NSE, symbol, base, evals, now)

    fibs = [t for t in got if t["kind"] == "fib" and t["alert_ts"] >= since]
    print(f"{len(fibs)} fib level alerts since {args.since}")
    schemes = [
        ("live today (W + P2)", {"W", "P2"}),
        ("PR #22 (P2 only)", {"P2"}),
        ("new rule (P1 + P2 + P3)", {"P1", "P2", "P3"}),
        ("P1 strong far edge only", {"P1"}),
        ("P1 + P2 (strong zone only)", {"P1", "P2"}),
        ("P3 weak far edge only", {"P3"}),
        ("W weak near edge only (today's Zone 1)", {"W"}),
    ]
    rows = []
    for market in (CRYPTO, NSE):
        mk = [t for t in fibs if t["market"] == market]
        for label, keep in schemes:
            items = [t for t in mk if t["zone"] in keep]
            if items:
                rows.append({"market": market, "tf": "all", **row(label, items)})
        for tf in fbt.TIMEFRAMES:
            for level in ("P1", "P2", "P3", "W"):
                items = [t for t in mk if t["tf"] == tf and t["zone"] == level]
                if items:
                    rows.append({"market": market, "tf": tf, **row(level, items)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib priority levels: {args.since} to now", "",
            "P1 = strong zone far edge, P2 = strong zone near edge, P3 = weak zone far edge (P1/P3 stop = "
            "that box's risk beyond the edge); W = weak zone near edge (today's Zone 1). Live trade rules, net R after fees.", "",
            df.to_markdown(index=False), ""]
    (OUT / "FIB_PRIORITY.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
