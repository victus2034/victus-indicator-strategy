"""Bitunix public futures candles, for the crypto alerts when CRYPTO_CANDLE_SOURCE is "bitunix".

Delta India stays the venue the trades are taken on and the backtest grades on;
this only changes where the alert levels are drawn from. Shiva saw Delta's
chart print thin candles with wicks TradingView's other books did not, and
alerts fire off those wicks.

Public endpoint, no key: GET /api/v1/futures/market/kline. At most 200 candles
a request, newest first, ending at endTime; 10 requests a second per IP. Every
candle here is [open_ts_seconds, open, high, low, close, base_volume], oldest
first.

Probed 2026-10-07 (research/bitunix_window_probe.py): the endpoint never returns
the candle still forming, whatever the request, and every candle slot between
now and an endTime in the future still counts against the 200 - so a page asked
to end one candle ahead comes back with 199.

Probed 2026-10-09 (research/bitunix_page_probe.py): endTime must sit on a
candle open. There it is exclusive and the page is right; anywhere else the
page loses one candle and the next one carries the lost candle's open. Paging
back by "oldest - 1ms" hit that once per 200 candles (7 bad candles in UNI's
1500 30m, and a demand zone that did not rebuild).
"""
import threading
import time

import requests

from config import (
    BITUNIX_API_BASE_URL,
    BITUNIX_MIN_REQUEST_GAP_SECONDS,
    BITUNIX_SYMBOLS,
    BITUNIX_XSTOCK_PAIRS,
    CRYPTO_CANDLE_SOURCE,
)

MAX_BARS_PER_REQUEST = 200
INTERVALS = {"1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"}
# Candles that open on a multiple of their length from the epoch (UTC).
INTERVAL_SECONDS = {"5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "2h": 7200, "4h": 14400, "1d": 86400}
# The page edges klines aligns endTime to; 3d, 1w and 1M are not used here.
_PAGE_STEP = {"1m": 60, **INTERVAL_SECONDS, "6h": 21600, "8h": 28800, "12h": 43200}

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


def pair_for(symbol, contract):
    """The Bitunix pair a watchlist symbol alerts off: its own entry in
    BITUNIX_XSTOCK_PAIRS (TSLAXUSD -> TSLAUSDT), else its Delta contract's."""
    return BITUNIX_XSTOCK_PAIRS.get(symbol) or bitunix_pair(contract)


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

    Pages backwards from end: each page is the newest 200 opening before its
    endTime, a candle open, and the next page ends at the oldest candle seen.
    A short page means the listing (or start) was reached.
    """
    if interval not in INTERVALS:
        raise ValueError(f"Bitunix has no {interval} interval")
    step = _PAGE_STEP.get(interval)
    out = {}
    # Never past now: future slots count against the page, so the page comes
    # back short and reads as the listing reached. The zone scan asked one
    # candle ahead and got 199 of its 1500 (2026-10-05 to 10-07).
    if step:
        cursor = min(-(-int(end) // step), int(time.time()) // step) * step * 1000
    else:
        cursor = min(int(end) * 1000, int(time.time() * 1000)) - 1
    start_ms = int(start) * 1000
    while cursor > start_ms or (not step and cursor == start_ms):
        rows = _request(pair, interval, start_ms, cursor, MAX_BARS_PER_REQUEST)
        for row in rows:
            ts = int(row["time"]) // 1000
            if start <= ts < end:
                out[ts] = [ts, float(row["open"]), float(row["high"]), float(row["low"]),
                           float(row["close"]), float(row.get("baseVol") or 0)]
        if len(rows) < MAX_BARS_PER_REQUEST:
            break
        oldest = min(int(row["time"]) for row in rows)
        nxt = oldest if step else oldest - 1
        if nxt >= cursor:
            break
        cursor = nxt
    return [out[k] for k in sorted(out)]


def forming_candle(pair, interval, now=None):
    """The candle still forming on `interval`, built from its finished 1m candles.

    The kline endpoint leaves it out, but the chart draws it and the zones are
    built on it, like the chart (a wick through a far edge kills a zone at once).
    None in the candle's first minute, or for an interval not in INTERVAL_SECONDS.
    """
    step = INTERVAL_SECONDS.get(interval)
    if step is None:
        return None
    now = int(time.time()) if now is None else int(now)
    opened = now // step * step
    rows = klines(pair, "1m", opened, now + 1)
    if not rows:
        return None
    return [opened, rows[0][1], max(r[2] for r in rows), min(r[3] for r in rows),
            rows[-1][4], sum(r[5] for r in rows)]


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
