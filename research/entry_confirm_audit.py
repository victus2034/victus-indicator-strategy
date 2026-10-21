"""Did price reach the entry of each 1D/1W/1M fib/trendline alert inside its
entry-confirm window? (lakky, 2026-10-21: "fib and trendline alerts came properly
but in entry confirm it does not come", 1D+.)

Reads research/entry_confirm_alerts_in.json (the 1D+ fib/TL records since Oct 9),
walks 5m candles from each alert to the end of its window (entry_confirm.fib_tl_window)
and writes, per alert, the first 5m candle within GET READY's 0.50% and the first
that traded through the entry, the IST time of both and whether entry confirm was
running then (crypto 08:00-01:00 IST, NSE 09:15-15:10 IST). Joined with the
entry_confirm_state history offline. Read-only: posts nothing, touches no state.
"""
import json
import sys
import time
from datetime import time as dtime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import bitunix_data  # noqa: E402
import entry_confirm  # noqa: E402
import fib_trendline_data as data  # noqa: E402

IST = "Asia/Kolkata"
OUT = ROOT / "research" / "out" / "entry_confirm"


def in_hours(market, ts):
    t = pd.Timestamp(ts, unit="s", tz="UTC").tz_convert(IST).time()
    if market == "nse":
        day = pd.Timestamp(ts, unit="s", tz="UTC").tz_convert(IST).weekday()
        return day < 5 and dtime(9, 15) <= t <= dtime(15, 10)
    return t >= dtime(8, 0) or t <= dtime(1, 0)


def crypto_5m(symbol, start, end):
    try:
        pair = bitunix_data.pair_for(symbol, symbol)
        rows = bitunix_data.klines(pair, "5m", int(start) - 300, int(end))
        if rows:
            return [r[:5] for r in rows]
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} bitunix: {error}")
    try:
        return data.delta_candles(symbol, "5m", int(start) - 300, int(end))
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} delta: {error}")
        return []


def main():
    alerts = json.loads((ROOT / "research" / "entry_confirm_alerts_in.json").read_text())
    now = time.time()
    nse_syms = sorted({a["symbol"] for a in alerts if a["market"] == "nse"})
    nse = data.nse_download(nse_syms, "5m") if nse_syms else {}
    cache = {}
    out = []
    for a in alerts:
        window = entry_confirm.fib_tl_window(a["market"], a["tf"]).total_seconds()
        end = min(now, a["sent_ts"] + window)
        if a["market"] == "nse":
            candles = nse.get(a["symbol"], [])
        else:
            if a["symbol"] not in cache:
                first = min(x["sent_ts"] for x in alerts if x["symbol"] == a["symbol"])
                cache[a["symbol"]] = crypto_5m(a["symbol"], first, now)
            candles = cache[a["symbol"]]
        entry, sl, side = a["entry"], a["sl"], a["side"]
        risk = abs(entry - sl)
        row = dict(a, window_end=end, n=0, ready_ts=None, touch_ts=None,
                   touch_in_hours=None, ready_in_hours=None, touch_progress=None,
                   stop_ts=None, any_touch_in_hours_ts=None)
        for ts, o, h, l, c in candles:
            # a 5m candle opening before the alert went out is not counted
            if ts + 300 <= a["sent_ts"] or ts >= end:
                continue
            row["n"] += 1
            fav = l if side == "long" else h
            prog = (entry - fav) / risk if side == "long" else (fav - entry) / risk
            near = abs(fav - entry) / entry * 100 <= 0.50 or prog >= 0
            if near and row["ready_ts"] is None:
                row["ready_ts"] = ts
                row["ready_in_hours"] = in_hours(a["market"], ts)
            if prog >= 0:
                if row["touch_ts"] is None:
                    row["touch_ts"] = ts
                    row["touch_in_hours"] = in_hours(a["market"], ts)
                    row["touch_progress"] = round(prog, 3)
                if row["any_touch_in_hours_ts"] is None and in_hours(a["market"], ts):
                    row["any_touch_in_hours_ts"] = ts
            if prog >= 1 and row["stop_ts"] is None:
                row["stop_ts"] = ts
        out.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "touches.json").write_text(json.dumps(out, indent=0))
    touched = [r for r in out if r["touch_ts"]]
    print(f"{len(out)} alerts, {len(touched)} touched entry in window, "
          f"{sum(1 for r in touched if r['touch_in_hours'])} first touch in hours, "
          f"{sum(1 for r in out if r['n'] == 0)} with no candles")


if __name__ == "__main__":
    main()
