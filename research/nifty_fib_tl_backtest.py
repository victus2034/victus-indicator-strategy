"""Research only (lakky, 2026-11-03): do the live fib and trendline rules work on the NIFTY 50 index?

"is fib and trendline strategy will work on nifty or not ... backtest with 15 timeframe to 1m".
One symbol, ^NSEI from Yahoo, every timeframe 15m / 30m / 1h / 4H / 1D / 1W / 1M, with today's live rules:
  fib        live levels (4H and below: L2-L4, 1D+ L1-L4), each level its own SL (next on 4H/1D and below,
             candle body on 1W/1M), 2R + breakeven, wait 5 / hold 20 candles
  TL touch   entry at the line, SL on the nearest candle >= 0.75% past it, 1R, no hold limit
  TL BROKEN  entry at the next open after the break close, SL past the candle before the break, 1R
NSE costs (round trip, breakeven offset, stop slippage) as the live NSE scoring. Bands 0.75%, 3% on 1W/1M.

History is what Yahoo keeps: 5m/15m/30m 60 days, 1h ~700 days, daily/weekly/monthly since 2007.
So 15m and 30m are scored on 5m (60 days), 1h on 1h and 4H/1D on 1h (~700 days, the live NSE rule),
and 1W/1M on daily candles (since 2007). A "1D long" row also scores 1D on daily candles since 2007.
Trades filling within 15 min of a US CPI / PPI / FOMC release are left out (none can: NSE is shut then).

    PYTHONPATH=research python research/nifty_fib_tl_backtest.py
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_data as fdata  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
from fib_trendline_data import IST, NSE  # noqa: E402
from tl_broken_alert_backtest import breaks, row  # noqa: E402
from trail_fib_tl_backtest import news  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "nifty_fib_tl"
SYMBOL = "^NSEI"
TFS = ["15m", "30m", "1h", "4h", "1d", "1w", "1M"]
LABEL = {"15m": "15m", "30m": "30m", "1h": "1H", "4h": "4H", "1d": "1D", "1w": "1W", "1M": "1M", "1d_long": "1D long"}
BREAK_RULE = [r for r in __import__("tl_broken_alert_backtest").RULES if r[0] == "at close, SL candle before break, 1R"]

# The live tables only know 30m-1M; the intraday timeframes follow 4H's rules.
for tf in ("15m", "1h"):
    fdata.TF_LABEL.setdefault(tf, LABEL[tf])
config.TRENDLINE_SL_PCT.setdefault("15m", 0.5)
config.TRENDLINE_SL_PCT.setdefault("1h", 0.75)
EVAL = {"15m": ("5m", 3), "30m": ("5m", 6), "1h": ("1h", 1), "4h": ("1h", 4), "1d": ("1h", 7),
        "1w": ("1d", 5), "1M": ("1d", 21)}
for tf, (res, per) in EVAL.items():
    trades.EVAL_RESOLUTION[NSE][tf] = res
    trades.EVAL_PER_BAR[NSE][tf] = per
LEVELS = {**config.FIB_ALERT_LEVELS, "15m": config.FIB_ALERT_LEVELS["4h"], "30m": config.FIB_ALERT_LEVELS["4h"],
          "1h": config.FIB_ALERT_LEVELS["4h"]}


def download():
    one = lambda interval: fdata.nse_download([SYMBOL], interval).get(SYMBOL, [])  # noqa: E731
    hourly = one("1h")
    data = {"5m": one("5m"), "15m": one("15m"), "30m": one("30m"), "1h": hourly,
            "4h": fdata._resample_4h(hourly), "1d": fdata.fill_daily_gaps(one("1d"), hourly),
            "1w": one("1w"), "1M": one("1M")}
    for k, v in data.items():
        print(f"{SYMBOL} {k}: {len(v)} candles"
              + (f", {datetime.fromtimestamp(v[0][0], IST):%Y-%m-%d} to {datetime.fromtimestamp(v[-1][0], IST):%Y-%m-%d}" if v else ""))
    return data


def run(tf, base, evalc, now, label=None):
    got = [t for t in fbt.replay(NSE, SYMBOL, tf, base, evalc, now) if t["kind"] in ("fib", "trendline")]
    # a break counts only once the scoring candles exist (else it would fill years later)
    since = evalc[0][0] + fdata.TF_SECONDS[tf] if evalc else now
    got += breaks(NSE, SYMBOL, tf, base, evalc, now, since, rules=BREAK_RULE)
    for t in got:
        t["row_tf"] = label or tf
        t["news"] = news(t["result"].get("fill_ts"))
    return got


def span(items):
    ts = [t["alert_ts"] for t in items]
    return f"{datetime.fromtimestamp(min(ts), IST):%Y-%m-%d} to {datetime.fromtimestamp(max(ts), IST):%Y-%m-%d}" if ts else "-"


def main() -> None:
    argparse.ArgumentParser().parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    fbt.FIB_LEVELS = LEVELS
    now = time.time()
    data = download()
    got = []
    for tf in TFS:
        got += run(tf, data[tf], data[EVAL[tf][0]], now)
    # 1D on daily candles since 2007: coarser scoring, ~9x the history
    trades.EVAL_RESOLUTION[NSE]["1d"], trades.EVAL_PER_BAR[NSE]["1d"] = "1d", 1
    got += run("1d", data["1d"], data["1d"], now, label="1d_long")
    skipped = sum(1 for t in got if t["news"])
    kept = [t for t in got if not t["news"]]
    names = {"fib": "Fib (all levels)", "trendline": "TL touch", "break": "TL BROKEN"}
    rows, levels = [], []
    for tf in TFS + ["1d_long"]:
        here = [t for t in kept if t["row_tf"] == tf]
        for kind, name in names.items():
            pick = [t for t in here if t["kind"] == kind]
            if pick:
                rows.append({"tf": LABEL[tf], "kind": name, "range": span(pick), **row(name, pick)})
        for lv in ("L1", "L2", "L3", "L4"):
            pick = [t for t in here if t["kind"] == "fib" and t.get("level") == lv]
            if pick:
                levels.append({"tf": LABEL[tf], "level": lv, **row(lv, pick)})
    df = pd.DataFrame(rows).drop(columns=["rule"])
    dl = pd.DataFrame(levels).drop(columns=["rule"])
    df.to_csv(OUT / "summary.csv", index=False)
    dl.to_csv(OUT / "fib_levels.csv", index=False)
    pd.DataFrame([{"tf": LABEL[t["row_tf"]], "kind": t["kind"], "level": t.get("level", t.get("line")),
                   "side": t["plan"]["side"],
                   "alert_ist": datetime.fromtimestamp(t["alert_ts"], IST).strftime("%Y-%m-%d %H:%M"),
                   "entry": t["plan"]["entry"], "sl": t["plan"]["sl"], "stop_%": round(trades.risk_pct(t["plan"]), 3),
                   "outcome": t["result"]["outcome"],
                   "net_r": trades.booked_r(t["plan"], NSE, t["result"])[1] if t["result"]["filled"] else None}
                  for t in got]).to_csv(OUT / "trades.csv", index=False)
    text = [f"# NIFTY 50 (^NSEI) - live fib + trendline rules, 15m to 1M (run {datetime.now(IST):%Y-%m-%d %H:%M} IST)", "",
            "Live rules, NSE costs + breakeven + stop slippage. win_% = trades reaching the target. "
            "% = net R x stop %. 15m/30m scored on 5m (60 days), 1H/4H/1D on 1h (~700 days), 1W/1M on daily "
            f"(since 2007); '1D long' = 1D on daily candles since 2007. {skipped} trades within 15 min of US "
            "CPI/PPI/FOMC left out.", "",
            df.to_markdown(index=False), "", "## Fib by level", "", dl.to_markdown(index=False), ""]
    (OUT / "NIFTY_FIB_TL.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
