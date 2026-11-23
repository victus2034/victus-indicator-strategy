"""Data for the journal's Signals audit (lakky, 2026-11-23: "do a backtest of all the alerts and
make sure it matches with the backtest of journal with all conditions").

The journal (victus2034/journal, index.html) scores every Signals rule on Delta's public candles,
read in the browser, and the cloud sandbox cannot reach Delta. This saves, at one moment, the
scanner's alert files and every Delta candle the Signals tab can ask for, so the journal and an
independent retest (journal tools/signals-retest.py) can both be run on exactly the same data:

  - the alert files the journal reads (scanner-runtime-state branch), as they were at `end`
  - every watchlist symbol (Delta's own names, xStocks under any Delta alias) at
      15m from 25 May 2026 (the walks; fib / trendline history starts 1 Jun),
      4h from 1 Aug 2025 and 1d from 2017 (the candle SL looks 300 candles back; 1W / 1M
      are built from days, up to 1,900 back)
  - BTCUSD 1d / 15m / 1h (BTC day, BTC move)
  - Delta's product list (the Coins "Delta" filter and the bStocks names)

Writes OUT/candles/<SYMBOL>_<res>.json.gz ([time, open, high, low, close] rows, time = the
candle's open in epoch seconds), OUT/state/<file>.gz, OUT/products.json and OUT/meta.json
(end = the "now" both sides are run at). Read only; posts nothing, touches no live state.

    python research/signals_parity_data.py --state /tmp/rt --out research/out/signals_parity
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402

RES_SECONDS = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
PAGE = 1900
STARTS = {"15m": 1779667200, "4h": 1754006400, "1d": 1483228800}   # 2026-05-25, 2025-08-01, 2017-01-01
STATE_FILES = [
    "fibtl_rebuild_records.jsonl", "fibtl_rebuild_results.json", "fibtl_rebuild_meta.json",
    "fib_trendline_alert_records.jsonl", "fib_trendline_results.json", "fib_level_results.json",
    "zone_rebuild_4h.jsonl", "zone_rebuild_htf.jsonl", "zone_rebuild_htf_results.json", "zone_rebuild_meta.json",
    "crypto_alert_records.jsonl", "nse_alert_records.jsonl",
    "daily_backtest_finalized_records.jsonl", "daily_backtest_pending_records.jsonl",
]


def get(path, params=None, attempts=5):
    last = None
    for i in range(attempts):
        try:
            r = requests.get(f"{config.DELTA_API_BASE_URL}{path}", params=params, timeout=30)
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
    while ws < end:
        we = min(int(end), ws + (PAGE - 1) * sec)
        for c in get("/v2/history/candles", {"symbol": symbol, "resolution": res, "start": ws, "end": we}):
            out[int(c["time"])] = [int(c["time"]), float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])]
        time.sleep(0.12)
        if we >= end:
            break
        ws = we - sec
    return [out[k] for k in sorted(out)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True, help="the scanner-runtime-state files")
    ap.add_argument("--out", default="research/out/signals_parity")
    args = ap.parse_args()
    out = Path(args.out)
    (out / "candles").mkdir(parents=True, exist_ok=True)
    (out / "state").mkdir(parents=True, exist_ok=True)
    end = int(time.time()) // 60 * 60
    for name in STATE_FILES:
        src = Path(args.state) / name
        if src.exists():
            with open(src, "rb") as fi, gzip.open(out / "state" / (name + ".gz"), "wb") as fo:
                shutil.copyfileobj(fi, fo)
    products = get("/v2/products")
    perp = {p["symbol"]: p for p in products if p.get("contract_type") == "perpetual_futures"}
    (out / "products.json").write_text(json.dumps({"success": True, "result": [
        {k: p.get(k) for k in ("symbol", "contract_type", "state", "contract_value", "tick_size", "initial_margin", "short_description")}
        for p in perp.values()]}, separators=(",", ":")), encoding="utf-8")
    want = []
    for sym in config.WATCHLIST:
        base = sym[:-3] if sym.endswith("USD") else sym
        for cand in (sym, base + "USD", base + "XUSD", base + "BUSD", (base[:-1] + "USD") if base[-1:] in "XB" else ""):
            if cand and cand in perp and cand not in want:
                want.append(cand)
    if "BTCUSD" not in want:
        want.append("BTCUSD")
    counts = {}
    for sym in want:
        for res in ("15m", "4h", "1d") + (("1h",) if sym == "BTCUSD" else ()):
            start = STARTS.get(res, end - 70 * 86400)
            try:
                rows = candles(sym, res, start, end)
            except Exception as error:  # noqa: BLE001
                print(f"{sym} {res}: failed {error}")
                continue
            counts[f"{sym}_{res}"] = len(rows)
            with gzip.open(out / "candles" / f"{sym}_{res}.json.gz", "wt", encoding="utf-8") as fh:
                json.dump(rows, fh, separators=(",", ":"))
            print(f"{sym} {res}: {len(rows)} candles")
    (out / "meta.json").write_text(json.dumps({"end": end, "symbols": want, "counts": counts}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
