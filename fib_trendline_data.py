"""Candles for the fib/trendline alerts and their backtests - crypto from Delta, NSE from Yahoo.

Every candle is [open_ts, open, high, low, close], open_ts in epoch seconds. Crypto
comes from Delta India (the book Shiva charts); NSE from yfinance, the same source
nse_scanner.py uses, with 4h candles anchored to the 09:15 open the same way.
"""
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests

import bitunix_data
from config import DELTA_API_BASE_URL

IST = ZoneInfo("Asia/Kolkata")
CRYPTO, NSE = "crypto", "nse"
TIMEFRAMES = ["30m", "4h", "1d", "1w", "1M"]
TF_SECONDS = {
    "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400,
    "1d": 86400, "1w": 7 * 86400, "1M": 31 * 86400,
}
TF_LABEL = {"30m": "30m", "4h": "4H", "1d": "1D", "1w": "1W", "1M": "1M"}
DELTA_MAX_BARS = 4000                  # Delta returns at most this many, the newest
# A page this long that starts inside its window may have been capped by the API.
PARTIAL_PAGE_BARS = 500
NSE_CLOSE = (15, 30)


# ----------------------------------------------------------------- crypto (Delta)

def delta_candles(contract, resolution, start, end, attempts=3):
    """All candles in [start, end], paging back in DELTA_MAX_BARS windows."""
    seconds = TF_SECONDS[resolution]
    out = {}
    window_end = int(end)
    while window_end > start:
        window_start = max(int(start), window_end - (DELTA_MAX_BARS - 1) * seconds)
        rows = _delta_request(contract, resolution, window_start, window_end, attempts)
        for row in rows:
            out[row[0]] = row
        if not rows:
            break
        if rows[0][0] > window_start and len(rows) >= PARTIAL_PAGE_BARS:
            # A long page that starts after its window start may have been
            # capped by the API below DELTA_MAX_BARS - stopping there would
            # silently cut history short, and the fib engine's state depends
            # on where history starts. Page on from the oldest candle seen;
            # if that was the listing, the next request comes back empty.
            window_end = rows[0][0] - 1
            continue
        # The first candle is well inside the window: the contract was listed
        # inside it, so there is nothing older to page back to.
        if rows[0][0] > window_start + 2 * seconds:
            break
        window_end = window_start - 1
    return [out[k] for k in sorted(out)]


def _delta_request(contract, resolution, start, end, attempts):
    last_error = None
    for attempt in range(attempts):
        try:
            response = requests.get(
                f"{DELTA_API_BASE_URL}/v2/history/candles",
                params={"symbol": contract, "resolution": resolution, "start": int(start), "end": int(end)},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("success"):
                raise RuntimeError(payload)
            rows = sorted(payload.get("result") or [], key=lambda c: c["time"])
            return [
                [int(c["time"]), float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"])]
                for c in rows
            ]
        except Exception as error:     # noqa: BLE001 - retried, then re-raised
            last_error = error
            time.sleep(1.5 * (attempt + 1))
    raise last_error


def monthly_from_daily(daily, tz=timezone.utc):
    """Calendar-month candles from daily ones."""
    months = []
    for ts, o, h, l, c in daily:
        day = datetime.fromtimestamp(ts, tz)
        key = (day.year, day.month)
        if months and months[-1][0] == key:
            m = months[-1][1]
            m[2], m[3], m[4] = max(m[2], h), min(m[3], l), c
        else:
            start = int(datetime(day.year, day.month, 1, tzinfo=tz).timestamp())
            months.append((key, [start, o, h, l, c]))
    return [m for _, m in months]


ALL_HISTORY_DAYS = 2000                # further back than Delta India exists (Dec 2023)


def bitunix_candles(contract, resolution, start, end):
    """delta_candles' shape ([open_ts, o, h, l, c]) from Bitunix's book."""
    pair = bitunix_data.bitunix_pair(contract)
    return [row[:5] for row in bitunix_data.klines(pair, resolution, int(start), int(end) + 1)]


def crypto_charts(contract, timeframes, now, intraday_bars=1500, source="delta"):
    """Live charts for one crypto contract: {tf: candles}.

    4H and up load everything Delta has, not a recent window. The fib engine is a
    state machine that runs from the first candle, and where it starts changes
    where it ends: over 12 symbols of 4H, a 1500-candle window disagreed with the
    full history on 5.7% of bars (UNI: a down fib from 4.561 instead of an up
    fib from 2.303). The chart runs from the first candle it loads, so the full
    history is what matches it - and a start fixed at the listing never slides.
    30m (off by default) keeps a window: its full history is ~12 requests a symbol.
    """
    since = now - ALL_HISTORY_DAYS * 86400
    fetch = bitunix_candles if source == "bitunix" else delta_candles
    out, daily = {}, None
    for tf in timeframes:
        if tf in ("1d", "1M"):
            if daily is None:
                daily = fetch(contract, "1d", since, now)
            out[tf] = daily if tf == "1d" else monthly_from_daily(daily)
        elif tf in ("1w", "4h"):
            out[tf] = fetch(contract, tf, since, now)
        else:
            out[tf] = fetch(contract, tf, now - intraday_bars * TF_SECONDS[tf], now)
    return out


# ----------------------------------------------------------------- NSE (yfinance)

YF_INTERVAL = {"5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "1d": "1d", "1w": "1wk", "1M": "1mo"}
# Daily and up: everything Yahoo has, for the same reason crypto_charts loads the
# full history. Intraday is capped by Yahoo itself (60 days of 5m-30m, 730 of 1h).
YF_PERIOD = {"5m": "60d", "15m": "60d", "30m": "60d", "1h": "700d", "1d": "max", "1w": "max", "1M": "max"}


def _frame_to_candles(frame):
    frame = frame.dropna(subset=["Open", "High", "Low", "Close"])
    index = frame.index
    if index.tz is None:
        index = index.tz_localize(IST)
    return [
        [int(ts.timestamp()), float(o), float(h), float(l), float(c)]
        for ts, o, h, l, c in zip(index, frame["Open"], frame["High"], frame["Low"], frame["Close"])
    ]


def _resample_4h(candles):
    if not candles:
        return []
    frame = pd.DataFrame(candles, columns=["ts", "Open", "High", "Low", "Close"])
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame["ts"].to_numpy(), unit="s", utc=True)).tz_convert(IST)
    bars = frame.resample("4h", origin="start_day", offset="1h15min").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    ).dropna()
    return _frame_to_candles(bars)


def nse_download(symbols, interval, period=None, chunk=50):
    """{symbol: candles} for one Yahoo interval ("4h" is built from 1h)."""
    import yfinance as yf

    source = "1h" if interval == "4h" else interval
    if source == "1h" and period is None:
        # Yahoo can turn an intraday period into "since listing" for newer stocks and
        # then reject it as over 730 days - nse_scanner.yfinance_time_range, same fix.
        end = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)
        span = {"start": (end - pd.Timedelta(days=700)).to_pydatetime(), "end": end.to_pydatetime()}
    else:
        span = {"period": period or YF_PERIOD[source]}
    out = {}
    for start in range(0, len(symbols), chunk):
        part = symbols[start:start + chunk]
        try:
            raw = yf.download(
                tickers=" ".join(part), interval=YF_INTERVAL[source],
                auto_adjust=False, progress=False, threads=True, group_by="ticker", **span,
            )
        except Exception as error:     # noqa: BLE001 - one bad chunk must not stop the rest
            print(f"yfinance {interval} chunk at {part[0]} failed: {error}")
            continue
        for symbol in part:
            try:
                frame = raw[symbol] if isinstance(raw.columns, pd.MultiIndex) else raw
                candles = _frame_to_candles(frame)
            except Exception:          # noqa: BLE001 - missing ticker in the batch
                continue
            if candles:
                out[symbol] = _resample_4h(candles) if interval == "4h" else candles
    return out


def nse_charts(symbols, timeframes):
    """Live charts for the NSE watchlist: {symbol: {tf: candles}}."""
    by_tf = {tf: nse_download(symbols, tf) for tf in timeframes}
    return {s: {tf: by_tf[tf].get(s, []) for tf in timeframes} for s in symbols}


# ----------------------------------------------------------------- closed or forming

def candle_is_closed(market, open_ts, tf, now):
    if market == CRYPTO:
        if tf == "1M":
            start = datetime.fromtimestamp(open_ts, timezone.utc)
            year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
            return datetime(year, month, 1, tzinfo=timezone.utc).timestamp() <= now
        return open_ts + TF_SECONDS[tf] <= now

    start = datetime.fromtimestamp(open_ts, IST)
    if tf in ("30m", "4h", "1h", "5m", "15m"):
        session_close = start.replace(hour=NSE_CLOSE[0], minute=NSE_CLOSE[1], second=0, microsecond=0)
        return min(start + timedelta(seconds=TF_SECONDS[tf]), session_close).timestamp() <= now
    if tf == "1d":
        return start.replace(hour=NSE_CLOSE[0], minute=NSE_CLOSE[1]).timestamp() <= now
    if tf == "1w":
        friday = (start + timedelta(days=4)).replace(hour=NSE_CLOSE[0], minute=NSE_CLOSE[1])
        return friday.timestamp() <= now
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    return datetime(year, month, 1, tzinfo=IST).timestamp() <= now
