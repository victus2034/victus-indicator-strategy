"""Research only: can the xStocks (and XAUT / SLVON) alert off Bitunix candles?

For each Delta symbol below this finds the Bitunix pairs that could be the same
underlying, says whether their kline endpoint answers, and compares 30m / 4h /
1d candles over the last 60 days against Delta: bar counts, missing slots,
zero-volume bars, close difference, weekday coverage, and how many of the zones
each source builds land on the same levels. Posts nothing, touches no state.
"""
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_data                     # noqa: E402
import config                           # noqa: E402
import fib_trendline_data as ftd        # noqa: E402
from live_audit import delta_rows       # noqa: E402

BASE = config.BITUNIX_API_BASE_URL
# Delta contract -> underlying names a Bitunix pair could carry.
TARGETS = {
    "TSLAXUSD": ["TSLA"],
    "METAXUSD": ["META"],
    "SOXLBUSD": ["SOXL"],
    "SNDKBUSD": ["SNDK"],
    "MRVLBUSD": ["MRVL"],
    "NVDAXUSD": ["NVDA"],
    "XAUTUSD": ["XAUT", "XAU", "PAXG", "GOLD"],
    "SLVONUSD": ["SLV", "XAG", "SILVER"],
}
TFS = ["30m", "4h", "1d"]
DAYS = 60


def pairs():
    r = requests.get(BASE + "/api/v1/futures/market/trading_pairs", timeout=20)
    return r.json().get("data") or []


def kline_ok(pair):
    now = int(time.time() * 1000)
    r = requests.get(BASE + "/api/v1/futures/market/kline",
                     params={"symbol": pair, "interval": "4h", "limit": 5, "endTime": now}, timeout=20)
    j = r.json()
    return str(j.get("code")) == "0" and bool(j.get("data")), j if str(j.get("code")) != "0" else None


def frame(rows):
    return pd.DataFrame([[r[0] * 1000, *r[1:6]] for r in rows],
                        columns=["time", "open", "high", "low", "close", "volume"])


def zone_levels(rows, tf):
    import importlib
    import os
    os.environ["VICTUS_TIMEFRAME"] = tf
    importlib.reload(config)
    import scanner
    importlib.reload(scanner)
    df = frame(rows[-config.OHLCV_LIMIT:])
    supply, demand = scanner.build_zones(df)
    live = [(z["type"] if "type" in z else k, round(z["bottom"], 6), round(z["top"], 6))
            for k, zs in (("supply", supply), ("demand", demand)) for z in zs if z.get("active")]
    return live


def same_zone(a, b, tol_pct=0.3):
    if a[0] != b[0]:
        return False
    mid = (a[1] + a[2]) / 2
    return abs(a[1] - b[1]) / mid * 100 <= tol_pct and abs(a[2] - b[2]) / mid * 100 <= tol_pct


def compare(delta_sym, pair, tf):
    seconds = ftd.TF_SECONDS[tf]
    end = int(time.time()) // seconds * seconds          # closed candles only
    start = end - DAYS * 86400
    d = [r for r in delta_rows(delta_sym, tf, start, end - 1) if r[0] < end]
    b = bitunix_data.klines(pair, tf, start, end)
    dm = {r[0]: r for r in d}
    bm = {r[0]: r for r in b}
    both = sorted(set(dm) & set(bm))
    slots = (end - start) // seconds
    diffs = [abs(bm[t][4] - dm[t][4]) / dm[t][4] * 100 for t in both if dm[t][4]]
    hl = [abs((bm[t][2] - bm[t][3]) - (dm[t][2] - dm[t][3])) / dm[t][4] * 100 for t in both if dm[t][4]]
    zero_d = sum(1 for r in d if not r[5])
    zero_b = sum(1 for r in b if not r[5])
    flat_d = sum(1 for r in d if r[2] == r[3])
    flat_b = sum(1 for r in b if r[2] == r[3])
    wd = lambda rows: dict(sorted(Counter(datetime.fromtimestamp(r[0], timezone.utc).strftime("%a") for r in rows).items()))
    print(f"  {tf:>3} slots={slots} delta={len(d)} bitunix={len(b)} both={len(both)} "
          f"only_delta={len(set(dm) - set(bm))} only_bitunix={len(set(bm) - set(dm))}")
    if diffs:
        print(f"      close diff %: median={statistics.median(diffs):.3f} p90={sorted(diffs)[int(len(diffs) * .9)]:.3f} max={max(diffs):.3f}"
              f" | range diff % median={statistics.median(hl):.3f}")
    print(f"      zero-volume delta={zero_d} bitunix={zero_b} | high==low delta={flat_d} bitunix={flat_b}")
    print(f"      weekdays delta={wd(d)}")
    print(f"      weekdays bitunix={wd(b)}")
    if tf in ("30m", "4h"):
        # Zones on the full engine window from each source.
        lookback = (config.OHLCV_LIMIT + 80) * seconds
        d_full = [r for r in delta_rows(delta_sym, tf, end - lookback, end - 1) if r[0] < end]
        b_full = bitunix_data.klines(pair, tf, end - lookback, end)
        try:
            zd, zb = zone_levels(d_full, tf), zone_levels(b_full, tf)
            matched = sum(1 for z in zb if any(same_zone(z, y) for y in zd))
            print(f"      active zones delta={len(zd)} bitunix={len(zb)} bitunix-matching-delta(0.3%)={matched}")
            for z in zb:
                print(f"        bitunix {z}")
            for z in zd:
                print(f"        delta   {z}")
        except Exception as error:   # noqa: BLE001
            print(f"      zones failed: {error!r}")


def main():
    listed = pairs()
    print(f"Bitunix pairs listed: {len(listed)}")
    for delta_sym, bases in TARGETS.items():
        print(f"\n=== {delta_sym} ===")
        hits = [p for p in listed if any(str(p.get("symbol", "")).startswith(base) for base in bases)]
        for p in hits:
            print("  listed:", {k: p.get(k) for k in p if k in (
                "symbol", "base", "quote", "symbolStatus", "status", "maxLeverage", "minTradeVolume",
                "basePrecision", "quotePrecision", "minBuyPriceOffset")} or p)
        chosen = None
        others = []
        for p in hits:
            sym = p.get("symbol")
            ok, err = kline_ok(sym)
            print(f"  kline {sym}: {'ok' if ok else err}")
            if ok and sym.endswith("USDT"):
                chosen = chosen or sym
                if delta_sym == "SLVONUSD" or delta_sym == "XAUTUSD":
                    others.append(sym)
        if not chosen:
            print("  -> no usable Bitunix pair")
            continue
        print(f"  -> comparing Delta {delta_sym} vs Bitunix {chosen}")
        for pair in others or [chosen]:
            if pair != chosen:
                print(f"  -> also comparing Delta {delta_sym} vs Bitunix {pair}")
            for tf in TFS:
                try:
                    compare(delta_sym, pair, tf)
                except Exception as error:   # noqa: BLE001
                    print(f"  {tf} failed: {error!r}")
        try:
            print(f"  last price bitunix={bitunix_data.last_price(chosen)}")
        except Exception as error:      # noqa: BLE001
            print(f"  last price failed: {error!r}")


if __name__ == "__main__":
    main()
