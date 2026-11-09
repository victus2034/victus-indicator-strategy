"""Delta candles for the journal's Signals backtest from 1 Jan (lakky, 2026-11-09).

lakky asked for every Signals filter (Exit at, Move SL, Trail TP, Hold, Fees, Coins,
BTC day, Level / Type, channel) crossed with each other on every crypto fib and
trendline alert since the start of 2026. The journal scores "Exit at" and the rest on
Delta's public candles, read in the browser (index.html tgtOne / mktFetch), and the
cloud sandbox cannot reach Delta. So this saves, once, every Delta candle those reads
could ask for, and the journal's own code is then run on them offline:

  - each watchlist symbol (Delta's own names) at 1d, 4h, 1h and 15m from 1 Sep 2025,
    5m for the last 9 days and 1m for the last 3 (tgtOne picks the finest candles that
    fit 1900 in one read, so recent alerts read 1m / 5m)
  - BTCUSD 1d is the journal's BTC day (bullish / bearish / sideways)

Writes OUT/<SYMBOL>_<res>.json.gz ([time, open, high, low, close, volume] rows, time =
the candle's open in epoch seconds) and OUT/meta.json (end = the "now" the journal is
replayed at). Read only; posts nothing, touches no live state.

    python research/journal_bt_candles.py --out research/out/journal_bt/candles
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402

RES_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
PAGE = 1900                      # bars per read, as the journal asks
START = 1756684800               # 2025-09-01 00:00 UTC
FINE_DAYS = {"5m": 9, "1m": 3}


def get(symbol, res, start, end, attempts=4):
    last = None
    for i in range(attempts):
        try:
            r = requests.get(f"{config.DELTA_API_BASE_URL}/v2/history/candles",
                             params={"symbol": symbol, "resolution": res, "start": int(start), "end": int(end)},
                             timeout=30)
            r.raise_for_status()
            j = r.json()
            if not j.get("success"):
                raise RuntimeError(str(j)[:200])
            return j.get("result") or []
        except Exception as error:  # noqa: BLE001 - retried, then re-raised
            last = error
            time.sleep(2 * (i + 1))
    raise last


def candles(symbol, res, start, end):
    """Every candle from start to end; pages overlap by one candle so none is lost at an edge."""
    sec, out, ws = RES_SECONDS[res], {}, int(start)
    while True:
        we = min(int(end), ws + (PAGE - 1) * sec)
        for c in get(symbol, res, ws, we):
            out[int(c["time"])] = [int(c["time"]), float(c["open"]), float(c["high"]), float(c["low"]),
                                   float(c["close"]), float(c.get("volume") or 0)]
        time.sleep(0.12)
        if we >= end:
            break
        ws = we - sec
    return [out[k] for k in sorted(out)]


def edge_probe(end):
    """Which candles Delta returns for a window: is the candle that opens at `end` in it, and the
    one that opened before `start`? The offline replay slices the saved candles the same way."""
    h = (end - 3 * 86400) // 3600 * 3600
    def times(a, b):
        return [int(c["time"]) - h for c in get("BTCUSD", "1h", a, b)]
    return {"aligned [h, h+2h]": times(h, h + 7200), "start h+60s": times(h + 60, h + 7200),
            "end h+2h-60s": times(h, h + 7200 - 60), "end h+2h+60s": times(h, h + 7200 + 60)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="research/out/journal_bt/candles")
    ap.add_argument("--end", type=int, default=0, help="epoch seconds; default now, to the minute")
    ap.add_argument("--symbols", default="", help="comma list; default the watchlist")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    end = args.end or int(time.time()) // 60 * 60
    symbols = [s for s in args.symbols.split(",") if s] or list(dict.fromkeys(config.WATCHLIST))
    counts = {}
    try:
        probe = edge_probe(end)
    except Exception as error:  # noqa: BLE001
        probe = {"error": str(error)}
    print("edge probe (seconds after h):", probe)
    for sym in symbols:
        for res in ("1d", "4h", "1h", "15m", "5m", "1m"):
            start = end - FINE_DAYS[res] * 86400 if res in FINE_DAYS else START
            try:
                rows = candles(sym, res, start, end)
            except Exception as error:  # noqa: BLE001
                print(f"{sym} {res}: failed {error}")
                rows = None
            if rows is None:
                continue
            counts[f"{sym}_{res}"] = len(rows)
            with gzip.open(out / f"{sym}_{res}.json.gz", "wt", encoding="utf-8") as fh:
                json.dump({"symbol": sym, "res": res, "start": start, "end": end, "candles": rows}, fh,
                          separators=(",", ":"))
            print(f"{sym} {res}: {len(rows)} candles"
                  + (f" from {time.strftime('%Y-%m-%d', time.gmtime(rows[0][0]))}" if rows else ""))
    (out / "meta.json").write_text(json.dumps({"end": end, "start": START, "fine_days": FINE_DAYS,
                                               "symbols": symbols, "counts": counts,
                                               "edge_probe": probe}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
