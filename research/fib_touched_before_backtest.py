"""Research only - nothing here is imported by the live scanners.

Lakky (2026-10-12, BNB 1M): "it already touched and worked on 8 Oct, the alert
makes no sense". Live, a fib zone alerts once per fib, the first time price is
in the band while alerts are awake and price is not past the stop - even when
price already traded into that same zone since the fib's top was set (during
held hours, or through the stop and back). This splits the live fib rule's
alerts by whether the zone had been touched since the top, to see what
"skip a zone already touched" would do.

"Touched before" = any closed candle after the fib's top candle and before the
alert candle overlapped the zone (fib_trendline_backtest's TouchClock,
max_streak >= 1).

    python research/fib_touched_before_backtest.py --since 2026-09-01

Live rules: deeper zone, S/R stop, 2R + BE. Crypto on Delta candles (live alerts
use Bitunix), NSE on Yahoo. Writes research/out/fib_touched_before/.
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
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_touched_before"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")), ("all", ("4h", "1d", "1w", "1M")))


def row(label, items):
    filled = [t for t in items if t["result"]["filled"]]
    booked = []
    for t in filled:
        net = trades.booked_r(t["plan"], t["market"], t["result"])[1]
        if net is not None:
            booked.append((net, net * trades.risk_pct(t["plan"])))
    wins = sum(1 for t in filled if t["result"]["outcome"] in ("1R", "2R"))
    sl = sum(1 for t in filled if t["result"]["outcome"] == "SL")
    n = len(booked)
    return {"rule": label, "alerts": len(items), "trades": n,
            "win_%": round(100 * wins / (wins + sl)) if wins + sl else None,
            "R_total": round(sum(r for r, _ in booked), 1),
            "R_per_trade": round(sum(r for r, _ in booked) / n, 3) if n else None,
            "%_total": round(sum(p for _, p in booked), 1),
            "%_per_trade": round(sum(p for _, p in booked) / n, 3) if n else None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
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
    for t in fibs:
        t["touched_before"] = t["max_streak"] >= 1
    print(f"{len(fibs)} fib alerts since {args.since}")
    schemes = [("live (all alerts)", lambda t: True),
               ("skip zones touched before (new rule)", lambda t: not t["touched_before"]),
               ("only the touched-before ones (removed)", lambda t: t["touched_before"])]
    rows = []
    for market in (CRYPTO, NSE):
        for group, tfs in GROUPS:
            mk = [t for t in fibs if t["market"] == market and t["tf"] in tfs]
            for label, keep in schemes:
                items = [t for t in mk if keep(t)]
                if items:
                    rows.append({"market": market, "tf": group, **row(label, items)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Fib alerts: skip zones already touched since the fib's top ({args.since} to now)", "",
            "Live fib rules (deeper zone, S/R stop, 2R + BE), net after fees. R and % are per trade "
            "and in total (% = R x the trade's stop distance). Crypto replayed on Delta candles.", "",
            df.to_markdown(index=False), ""]
    (OUT / "FIB_TOUCHED_BEFORE.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
