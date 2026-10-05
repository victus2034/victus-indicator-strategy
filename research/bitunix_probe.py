"""Research only: what Bitunix's public futures kline API actually returns.

Prints the raw shape of a kline response, how startTime/endTime paging behaves,
how far back 5m/30m/4h/1d go, and which watchlist coins Bitunix lists.
"""
import json
import time

import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config

BASE = "https://fapi.bitunix.com"


def get(path, **params):
    r = requests.get(BASE + path, params=params, timeout=20)
    print(f"GET {path} {params} -> {r.status_code}")
    return r.json()


def base_of(symbol):
    s = symbol.split("/")[0]
    return s[:-3] if s.endswith("USD") and "/" not in symbol else s


pairs = get("/api/v1/futures/market/trading_pairs")
listed = {p.get("symbol") for p in (pairs.get("data") or [])}
print("pairs keys:", list((pairs.get("data") or [{}])[0].keys()))
print("total pairs:", len(listed))
for sym in config.WATCHLIST:
    b = base_of(sym)
    hits = sorted(x for x in listed if x and x.startswith(b) and x.endswith("USDT"))
    print(f"  {sym:18s} base={b:8s} -> {hits[:4]}")

k = get("/api/v1/futures/market/kline", symbol="BTCUSDT", interval="4h", limit=3)
print(json.dumps(k)[:1500])

now = int(time.time() * 1000)
for label, params in [
    ("end only", dict(endTime=now - 30 * 86400_000)),
    ("start only", dict(startTime=now - 30 * 86400_000)),
    ("start+end 10d", dict(startTime=now - 30 * 86400_000, endTime=now - 20 * 86400_000)),
]:
    d = get("/api/v1/futures/market/kline", symbol="BTCUSDT", interval="30m", limit=200, **params).get("data") or []
    ts = [int(x.get("time")) for x in d]
    print(f"  {label}: n={len(ts)} first={min(ts) if ts else None} last={max(ts) if ts else None} "
          f"order={'asc' if ts == sorted(ts) else 'desc'}")

for interval, days in [("5m", 400), ("30m", 800), ("4h", 1500), ("1d", 3000)]:
    for back in (days // 8, days // 4, days // 2, days):
        start = now - back * 86400_000
        d = get("/api/v1/futures/market/kline", symbol="BTCUSDT", interval=interval, limit=5,
                startTime=start, endTime=start + 6 * 3600_000 * (24 if interval == "1d" else 1)).get("data") or []
        print(f"  {interval} {back}d back: n={len(d)}")
    time.sleep(0.2)

for sym in ("ETHUSDT", "HUSDT", "TACUSDT", "RIVERUSDT"):
    d = get("/api/v1/futures/market/kline", symbol=sym, interval="1d", limit=200, startTime=now - 1500 * 86400_000).get("data") or []
    print(f"  {sym} 1d from 1500d back: n={len(d)} first={d and min(int(x['time']) for x in d)}")

# Same BTC 4h candles from Delta, for unit comparison
r = requests.get(f"{config.DELTA_API_BASE_URL}/v2/history/candles",
                 params={"symbol": "BTCUSD", "resolution": "4h", "start": now // 1000 - 3 * 14400, "end": now // 1000}, timeout=20)
print("delta:", json.dumps(r.json())[:800])
