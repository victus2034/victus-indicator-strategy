"""Research only: fib (L2-L4) + trendline setups on every liquid xStock Delta India lists
(lakky, 2026-11-21: "do a backtest of xstock in delta as there are massive opportunities").

1. Lists every live Delta perpetual that is an xStock (description says stock / ETF / backed, or it
   is already on the watchlist) with its average traded value over the last 7 and 30 days
   (volume_7d_30d_probe.delta, the coin-list rule).
2. Replays the live fib / trendline rules on Delta candles for each one with >= --min USD a day on
   BOTH windows: fib L2-L4 (config.FIB_ALERT_LEVELS, the live per-level stops, 2R + BE), trendline
   touches (wick/body stop, 1R) and TL BROKEN trades (entry at the alert, stop past the candle before
   the break, 1R) - the scanner's own scoring, Delta fees (CRYPTO_ROUND_TRIP_COST_PCT) and stop slip.
   Trades filled within 15 min of a US CPI / PPI / FOMC release are left out.

    PYTHONPATH=research python research/xstock_delta_backtest.py --since 2026-09-01 [--min 1e5 --out wide]
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
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
import tl_broken_alert_backtest as tbt  # noqa: E402
from coin_list_review import COMMODITIES, delta_descriptions, is_xstock  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST  # noqa: E402
from trail_fib_tl_backtest import news  # noqa: E402
from volume_7d_30d_probe import delta  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "xstock_delta"
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")))
KINDS = (("Fib L2-L4", "fib"), ("TL touch", "trendline"), ("TL break", "break"))
LIVE_BREAK_RULE = [r for r in tbt.RULES if r[0] == "at close, SL candle before break, 1R"]


def xstocks():
    """[(base, contract, avg7, avg30)] for every live Delta xStock perp."""
    vols, _note = delta()
    desc = delta_descriptions()
    live = set(config.XSTOCK_WATCHLIST)
    out = []
    for base, (a7, a30, _days, _tick, sym) in vols.items():
        if base in COMMODITIES or sym in config.OTHER_WATCHLIST:
            continue
        if sym in live or is_xstock(base, desc.get(base, "")):
            out.append((base, sym, a7, a30))
    return sorted(out, key=lambda x: -x[3])


def replay_one(contract, now, since):
    scanner.delta_contract = lambda s: s          # research only: any Delta contract by its own name
    data = fbt.crypto_data(contract, now)
    if not data:
        return []
    base, evals = data
    got = []
    for tf in fbt.TIMEFRAMES:
        res = trades.EVAL_RESOLUTION[CRYPTO][tf]
        got += fbt.replay(CRYPTO, contract, tf, base.get(tf, []), evals.get(res, []), now)
        got += tbt.breaks(CRYPTO, contract, tf, base.get(tf, []), evals.get(res, []), now, since,
                          rules=LIVE_BREAK_RULE)
    return [t for t in got if t["alert_ts"] >= since and not news(t["result"].get("fill_ts"))]


def table(items, label_key):
    rows = []
    for group, tfs in GROUPS:
        for label, kind in KINDS + (("All", None),):
            pick = [t for t in items if t["tf"] in tfs and (kind is None or t["kind"] == kind)]
            if pick:
                r = row(label, pick)
                rows.append({label_key: label, "tf": group, "alerts": r["alerts"], "trades": r["trades"],
                             "win_%": r["win_%"], "R/trade": r["R_per_trade"], "%/trade": r["%_per_trade"],
                             "R total": r["R_total"]})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--min", type=float, default=1e6, help="USD a day on Delta, 7d and 30d")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    global OUT
    if args.out:
        OUT = OUT / args.out
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    fbt.FIB_LEVELS = config.FIB_ALERT_LEVELS
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()

    listed = xstocks()
    vol = pd.DataFrame([{"symbol": s, "base": b, "7d $M/day": round(a7 / 1e6, 2), "30d $M/day": round(a30 / 1e6, 2),
                         "live": s in config.XSTOCK_WATCHLIST, "tested": a7 >= args.min and a30 >= args.min}
                        for b, s, a7, a30 in listed])
    picked = list(dict.fromkeys(s for b, s, a7, a30 in listed if a7 >= args.min and a30 >= args.min))
    print(f"{len(listed)} xStocks on Delta, {len(picked)} with >= {args.min / 1e6:g}M a day: {picked}")

    every = []
    for sym in picked:
        try:
            got = replay_one(sym, now, since)
        except Exception as error:  # noqa: BLE001
            print(f"{sym} failed: {error}")
            continue
        print(f"{sym}: {len(got)} alerts")
        every += got

    live = [t for t in every if t["symbol"] in config.XSTOCK_WATCHLIST]
    new = [t for t in every if t["symbol"] not in config.XSTOCK_WATCHLIST]
    per_sym = []
    for sym in picked:
        for group, tfs in GROUPS:
            pick = [t for t in every if t["symbol"] == sym and t["tf"] in tfs]
            if pick:
                r = row(sym, pick)
                per_sym.append({"symbol": sym, "tf": group, "trades": r["trades"], "win_%": r["win_%"],
                                "R/trade": r["R_per_trade"], "%/trade": r["%_per_trade"], "R total": r["R_total"]})
    pd.DataFrame([{k: v for k, v in t.items() if k in ("symbol", "tf", "kind", "level", "alert_ts")}
                  | {"outcome": t["result"]["outcome"],
                     "net_r": trades.booked_r(t["plan"], CRYPTO, t["result"])[1] if t["result"]["filled"] else None,
                     "risk_%": round(trades.risk_pct(t["plan"]), 3)}
                  for t in every]).to_csv(OUT / "trades.csv", index=False)

    text = [f"# xStocks on Delta: fib L2-L4 + trendlines ({args.since} to now)", "",
            f"Delta candles, Delta fees ({trades.COST_PCT[CRYPTO]}% round trip) + stop slip. Live rules: "
            "fib L2-L4 own stops 2R + BE; TL touch wick/body stop 1R; TL break entry at alert, stop past the "
            "candle before the break, 1R. Entries filled within 15 min of US CPI/PPI/FOMC left out.", "",
            f"## xStocks Delta lists (tested = >= {args.min / 1e6:g}M USD a day on both 7d and 30d)", "",
            vol.to_markdown(index=False), "",
            "## All tested xStocks", "", table(every, "setup").to_markdown(index=False), "",
            "## Live 3 (TSLA, SNDK, QQQ)", "", table(live, "setup").to_markdown(index=False), "",
            "## Not on the watchlist yet", "", table(new, "setup").to_markdown(index=False), "",
            "## Per symbol (all setups)", "", pd.DataFrame(per_sym).to_markdown(index=False), ""]
    (OUT / "XSTOCK_DELTA.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
