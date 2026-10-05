"""Bitunix public futures candles, for the crypto alerts when CRYPTO_CANDLE_SOURCE is "bitunix".

Delta India stays the venue the trades are taken on and the backtest grades on;
this only changes where the alert levels are drawn from. Shiva saw Delta's
chart print thin candles with wicks TradingView's other books did not, and
alerts fire off those wicks.

Public endpoint, no key: GET /api/v1/futures/market/kline. At most 200 candles
a request, newest first, ending at endTime; 10 requests a second per IP. Every
candle here is [open_ts_seconds, open, high, low, close, base_volume], oldest
first.
"""
import threading
import time

import requests

from config import (
    BITUNIX_API_BASE_URL,
    BITUNIX_MIN_REQUEST_GAP_SECONDS,
    BITUNIX_SYMBOLS,
    CRYPTO_CANDLE_SOURCE,
)

MAX_BARS_PER_REQUEST = 200
INTERVALS = {"1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"}

# The scanner fetches every symbol from a thread pool, and fib_trendline_scanner
# from another; one gap shared by all of them keeps the process under the limit.
_rate_lock = threading.Lock()
_last_request = [0.0]


def uses_bitunix(symbol):
    """True when this watchlist symbol's alert candles should come from Bitunix."""
    return CRYPTO_CANDLE_SOURCE == "bitunix" and symbol in BITUNIX_SYMBOLS


def bitunix_pair(contract):
    """Delta contract string -> Bitunix pair: BTCUSD -> BTCUSDT, HUSD -> HUSDT."""
    if contract.endswith("USDT"):
        return contract
    if not contract.endswith("USD"):
        raise ValueError(f"no Bitunix pair for {contract}")
    return contract[:-3] + "USDT"


def _throttle():
    with _rate_lock:
        wait = _last_request[0] + BITUNIX_MIN_REQUEST_GAP_SECONDS - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.time()


def _request(pair, interval, start_ms, end_ms, limit, attempts=3):
    last_error = None
    for attempt in range(attempts):
        try:
            _throttle()
            response = requests.get(
                f"{BITUNIX_API_BASE_URL}/api/v1/futures/market/kline",
                params={"symbol": pair, "interval": interval, "limit": limit,
                        "startTime": start_ms, "endTime": end_ms},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            if str(payload.get("code")) != "0":
                raise RuntimeError(f"Bitunix {pair} {interval}: {payload}")
            return payload.get("data") or []
        except Exception as error:     # noqa: BLE001 - retried, then re-raised
            last_error = error
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise last_error


def klines(pair, interval, start, end):
    """Every candle opening in [start, end) (epoch seconds), oldest first.

    Pages backwards from end: each page is the newest 200 at or before its
    endTime, so the next page ends just before the oldest candle seen. A short
    page means the listing (or start) was reached.
    """
    if interval not in INTERVALS:
        raise ValueError(f"Bitunix has no {interval} interval")
    out = {}
    cursor = int(end) * 1000 - 1
    start_ms = int(start) * 1000
    while cursor >= start_ms:
        rows = _request(pair, interval, start_ms, cursor, MAX_BARS_PER_REQUEST)
        for row in rows:
            ts = int(row["time"]) // 1000
            if start <= ts < end:
                out[ts] = [ts, float(row["open"]), float(row["high"]), float(row["low"]),
                           float(row["close"]), float(row.get("baseVol") or 0)]
        if len(rows) < MAX_BARS_PER_REQUEST:
            break
        oldest = min(int(row["time"]) for row in rows)
        if oldest - 1 >= cursor:
            break
        cursor = oldest - 1
    return [out[k] for k in sorted(out)]


def last_price(pair):
    """The latest trade price: the close of the newest 1m candle."""
    now_ms = int(time.time() * 1000)
    rows = _request(pair, "1m", now_ms - 10 * 60_000, now_ms, 5)
    if not rows:
        raise RuntimeError(f"Bitunix returned no 1m candle for {pair}")
    newest = max(rows, key=lambda row: int(row["time"]))
    price = float(newest["close"])
    if price <= 0:
        raise RuntimeError(f"Bitunix 1m close for {pair} is {price}")
    return price
