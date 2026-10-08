"""Research only - nothing here is imported by the live scanners.

Notion task 20 (2026-10-08, Lakky): on a buy, prefer the lower fib zone; on a
sell, the upper one. Each live fib alerts both of its zones: Zone 1 is the
shallow box (upper on an up move / long, lower on a down move / short), Zone 2
the deeper one (lower for longs, upper for shorts). The zones alert and trade
independently, so "Zone 2 only" is the live result with every Zone 1 trade
removed. This splits the fib history backtest by zone and side.

    python research/fib_zone_preference.py --since 2026-09-01

Replay and trade rules are fib_trendline_backtest's (live timeframes, crypto on
Delta candles, NSE on Yahoo). Writes research/out/fib_zone_preference/.
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_zone_preference"


def row(label, items):
    market = items[0]["market"]
    filled = [t for t in items if t["result"]["filled"]]
    net = [n for n in (trades.booked_r(t["plan"], market, t["result"])[1] for t in filled) if n is not None]
    out = defaultdict(int)
    for t in items:
        out[t["result"]["outcome"]] += 1
    wins = out["1R"] + out["2R"]
    return {"group": label, "alerts": len(items), "filled": len(filled),
            "SL": out["SL"], "BE": out.get("BE", 0), "1R": out["1R"], "2R": out["2R"],
            "win_1r_%": round(100 * wins / (wins + out["SL"])) if wins + out["SL"] else None,
            "net_R": round(sum(net), 1), "R_per_trade": round(sum(net) / len(net), 3) if net else None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01", help="IST date the alert window starts")
    parser.add_argument("--market", choices=[CRYPTO, NSE, "both"], default="both")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)          # live set: 30m is off
    fbt.ALERT_ZONES = (1, 2)                                 # both, to compare them
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    got = []

    if args.market in (CRYPTO, "both"):
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
    if args.market in (NSE, "both"):
        import nse_scanner
        for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
            got += fbt.replay_symbol(NSE, symbol, base, evals, now)

    fibs = [t for t in got if t["kind"] == "fib" and t["alert_ts"] >= since]
    print(f"{len(fibs)} fib alerts since {args.since}")
    for t in fibs:
        t["side"] = t["plan"]["side"]
    rows = []
    for market in (CRYPTO, NSE):
        mk = [t for t in fibs if t["market"] == market]
        if not mk:
            continue
        for label, keep in (("both zones (live)", lambda t: True),
                            ("Zone 1 only (shallow)", lambda t: t["zone"] == 1),
                            ("Zone 2 only (deeper: lower for buys, upper for sells)", lambda t: t["zone"] == 2)):
            items = [t for t in mk if keep(t)]
            if items:
                rows.append({"market": market, "tf": "all", **row(label, items)})
        for tf in fbt.TIMEFRAMES:
            for zone in (1, 2):
                items = [t for t in mk if t["tf"] == tf and t["zone"] == zone]
                if items:
                    rows.append({"market": market, "tf": tf, **row(f"Zone {zone}", items)})
        for side in ("long", "short"):
            for zone in (1, 2):
                items = [t for t in mk if t["side"] == side and t["zone"] == zone]
                if items:
                    rows.append({"market": market, "tf": "all", **row(f"{side} Zone {zone}", items)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib zone preference (Notion 20): {args.since} to now", "",
            "Zone 1 = shallow box (upper for longs, lower for shorts); Zone 2 = deeper (lower for longs, "
            "upper for shorts). Live timeframes, live trade rules (2R target, BE at +0.5R), net R after fees.", "",
            df.to_markdown(index=False), ""]
    (OUT / "FIB_ZONE_PREFERENCE.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
