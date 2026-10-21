"""Stage pings for fib and trendline alerts that were already delivered.

Since 2026-10-08 (lakky) this watches only the fib and trendline alerts on
1D, 1W and 1M, crypto and NSE (FIB_TL_RECORDS, written by
fib_trendline_scanner.py). The 30m and 4h zone alerts are no longer watched
here; their own channels are unchanged. The zone loaders below stay because
paper_trading.py still reads them.

Watches levels a real alert already announced, and reports how
price is behaving relative to that alert's own recorded entry and stop.
It never re-derives levels, never trades on a candidate the scanner has
not alerted on, and never writes to the alert records the backtest reads.

Stages (one ping each, forward-only):
  1 GET READY     price within APPROACH_THRESHOLD_PCT of entry, entry
                  not yet reached
  2 ENTRY NOW     entry reached, under NEAR_SL_FRACTION of planned risk
                  consumed
  3 LATE/NEAR SL  entry reached, most of the planned risk already gone

Deliberately silent when the trade is no longer worth taking: price has
bounced back past entry into profit (entering now would sit far from the
locked stop), or the stop is already hit.

A fast mover can cross the whole GET READY -> ENTRY gap between two polls.
When that happens the GET READY the user would otherwise never
get is backfilled into the same digest, marked as having moved fast rather
than printed as a live distance.

The dispatch interval is meant to be 5 minutes but is not reliably that -
real gaps of 20-40+ minutes happen. Stage detection therefore looks at every
fine candle (crypto Bitunix 1m, NSE Yahoo 5m) since the later of the alert
and the market's previous check (sweep_extreme()), not only the live price,
so a wick that touched the entry between two checks is still caught - and a
move from before the alert existed is not. Until 2026-10-21 NSE looked at the
latest 15m close only and missed 16 wick fills in 9 days, and crypto swept a
fixed hour that could reach back before the alert (lakky, 1D+ entry confirms
missing; research/entry_confirm_audit.py).

A fill that ran on past half the risk, or to the stop, before the next check
still gets its ENTRY NOW line, with "filled since the last check" and the risk
used (lakky, 2026-10-21). It used to be silent: 8 misses in 9 days, mostly
tight-stop L4 fibs and trendlines.

Every ping from one run goes out as a single digest. Posted one message
per symbol, a busy run buried the channel under dozens of separate blocks
and the few that mattered were impossible to pick out.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import time as datetime_time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

from config import FIB_TL_ENTRY_WAIT_BARS, MAX_DISTANCE_PCT, WATCHLIST
from fib_trendline_data import TF_LABEL, TF_SECONDS

# Only crypto is checked against its watchlist. The NSE side has no
# authoritative one here - nse_config carries a FALLBACK_WATCHLIST used when
# the live universe cannot be fetched, so filtering on it would drop real
# alerts for symbols that are perfectly valid.
CRYPTO_WATCHLIST_SET = {str(symbol).upper() for symbol in WATCHLIST}


IST = ZoneInfo("Asia/Kolkata")
WEBHOOK_ENV = "DISCORD_ENTRY_CONFIRM_WEBHOOK_URL"
# Each market can post to its own channel; unset, it falls back to the shared
# WEBHOOK_ENV, so nothing is lost before the new channel exists.
MARKET_WEBHOOK_ENVS = {
    "crypto": "DISCORD_ENTRY_CONFIRM_CRYPTO_WEBHOOK_URL",
    "nse": "DISCORD_ENTRY_CONFIRM_NSE_WEBHOOK_URL",
}
MARKET_LABELS = {"crypto": "Crypto", "nse": "NSE"}
STATE_PATH = Path(__file__).with_name("entry_confirm_state.json")
ALERT_RECORDS = {
    "nse": {
        "30m": Path(__file__).with_name("nse_alert_records_30m.jsonl"),
        "4h": Path(__file__).with_name("nse_alert_records.jsonl"),
    },
    "crypto": {
        "30m": Path(__file__).with_name("crypto_alert_records_30m.jsonl"),
        "4h": Path(__file__).with_name("crypto_alert_records.jsonl"),
    },
}
# Fib and trendline alerts, both markets, one file (fib_trendline_scanner.RECORDS_FILE).
FIB_TL_RECORDS = Path(__file__).with_name("fib_trendline_alert_records.jsonl")
# The only timeframes watched (lakky, 2026-10-08).
FIB_TL_WATCH_TIMEFRAMES = ["1d", "1w", "1M"]
FIB_TL_KIND_LABEL = {"fib": "FIB", "trendline": "TL"}
BAR_MINUTES = {"30m": 30, "4h": 240}
# Discord rejects anything longer; the digest is split rather than dropped.
MAX_MESSAGE_CHARS = 1900

# Fire the approach ping while price is still this close to - but has not
# yet reached - the recorded entry. The ping is only a cue to place the
# order at the recorded entry, so it never shifts where the trade is taken.
#
# Matched to the distance that fires an alert in the first place. At 0.10
# against an alert window of 0.20 there was a dead band: an alert would be
# delivered at, say, 0.15% away and then never ping at all unless price
# happened to close to within 0.10%. Crypto lives in that band - it moves
# far enough between polls to step over it - which is why the channel
# carried NSE pings and no crypto ones.
APPROACH_THRESHOLD_PCT = float(
    os.getenv("VICTUS_APPROACH_THRESHOLD_PCT", MAX_DISTANCE_PCT)
)
# How long one symbol's GET READY budget lasts. entry_confirm runs every 5
# minutes; a fresh zone on the same symbol inside this window rides the
# existing warning instead of adding a second message for it.
READY_COOLDOWN_SECONDS = int(os.getenv("VICTUS_READY_COOLDOWN_SECONDS", str(30 * 60)))
# Same exact level should not keep repeating a "getting close" message. ENTRY
# NOW is still allowed when price actually touches the level.
LEVEL_READY_COOLDOWN_SECONDS = int(
    os.getenv("VICTUS_LEVEL_READY_COOLDOWN_SECONDS", str(6 * 60 * 60))
)
# Past this share of the planned entry-to-stop distance, the trade is
# reported as late rather than as a clean entry.
NEAR_SL_FRACTION = 0.5
# Matches daily_backtest_summary.ENTRY_WAIT_BARS so a zone stops being
# watched exactly when the backtest stops counting it as fillable.
WATCH_BARS = 3

TRADE_START = datetime_time(9, 15)
# The user stops trading at 15:10, so a ping after that is noise.
TRADE_END = datetime_time(15, 10)

STAGE_READY = 1
STAGE_ENTRY = 2
STAGE_LATE = 3


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeframe", choices=["all", *FIB_TL_WATCH_TIMEFRAMES], default="all"
    )
    parser.add_argument(
        "--market",
        choices=["nse", "crypto", "all"],
        default="all",
        help="Which fib/trendline alerts to watch. Crypto covers xStocks too.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--ignore-session",
        action="store_true",
        help="Skip the market-hours guard (testing only).",
    )
    return parser.parse_args(argv)


def in_trading_session(now: pd.Timestamp) -> bool:
    if now.weekday() >= 5:
        return False
    return TRADE_START <= now.time() <= TRADE_END


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    temp_path = STATE_PATH.with_name(STATE_PATH.name + ".tmp")     # atomic: a killed run must not leave a half file
    temp_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp_path, STATE_PATH)


# How different a re-alert's entry can be from an earlier one on the same
# symbol/side/timeframe and still count as a venue flip on the same real
# zone rather than a genuinely new one. fetch_symbol_ohlcv() falls back from
# its first venue to others when it is slow or fails, so the same real level can come back priced from a different venue
# scan to scan - measured across 205 same-symbol/side/timeframe pairs inside
# a 3-hour window, the shift was 0.02-0.72%. 1% is generous against that and
# tight against anything that was ever a genuinely different zone in the
# same sample.
WATCH_KEY_MERGE_TOLERANCE_PCT = 1.0


def coalesce_venue_drift(records: list[dict], window: pd.Timedelta) -> None:
    """Snap a record's entry/stop to an earlier one's own, in place, when
    they are plausibly the same real zone re-alerted from a different venue.

    Left alone, a venue flip shifts the price just enough to clear
    watch_key's 6-significant-figure tolerance and look like a brand-new
    zone, restarting the GET READY -> ENTRY NOW cycle for a trade the user
    already confirmed. The first record in a matching run is kept as the
    group's anchor and every later record within tolerance of it (not of
    its immediate predecessor, so drift cannot creep past the tolerance one
    small hop at a time) is rewritten to the anchor's own levels, which is
    what gives them the same watch_key downstream.
    """
    groups: dict[tuple, list[dict]] = {}
    for record in records:
        key = (
            str(record.get("symbol", "")).upper(),
            record.get("side"),
            record.get("timeframe"),
        )
        groups.setdefault(key, []).append(record)

    for group in groups.values():
        group.sort(key=lambda r: r["_delivered"])
        anchor = None
        for record in group:
            if anchor is not None:
                gap = record["_delivered"] - anchor["_delivered"]
                pct_diff = (
                    abs(record["_entry"] - anchor["_entry"]) / anchor["_entry"] * 100.0
                )
                if gap <= window and pct_diff <= WATCH_KEY_MERGE_TOLERANCE_PCT:
                    record["_entry"] = anchor["_entry"]
                    record["_stop"] = anchor["_stop"]
                    continue
            anchor = record


def _parse_zone_records(
    paths: list[Path], timeframe: str, market: str, now: pd.Timestamp, window: pd.Timedelta
) -> list[dict]:
    """Shared parse/filter/coalesce/dedup for any zone-record log - real
    delivered alerts or the scanner's own pre-alert watch rows alike.
    """
    parsed: list[dict] = []
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("timeframe") != timeframe:
                continue
            # A symbol dropped from the watchlist was dropped on purpose; its
            # last alert must not keep pinging while it stays fillable.
            if market == "crypto" and str(record.get("symbol", "")).upper() not in CRYPTO_WATCHLIST_SET:
                continue
            delivered = pd.to_datetime(record.get("delivered_at_utc"), errors="coerce", utc=True)
            if pd.isna(delivered):
                continue
            delivered = delivered.tz_convert(IST)
            if now - delivered > window or delivered > now:
                continue
            entry = pd.to_numeric(record.get("planned_entry"), errors="coerce")
            stop = pd.to_numeric(record.get("stop_price"), errors="coerce")
            if pd.isna(entry) or pd.isna(stop) or entry <= 0:
                continue
            record["_entry"] = float(entry)
            record["_stop"] = float(stop)
            record["_delivered"] = delivered
            record["_market"] = market
            parsed.append(record)

    coalesce_venue_drift(parsed, window)
    watched: dict[str, dict] = {}
    for record in parsed:
        watched[watch_key(record)] = record
    return list(watched.values())


def load_watched_alerts(
    market: str, timeframe: str, now: pd.Timestamp, records_path=None
) -> list[dict]:
    """Alerts still inside their fillable window, newest occurrence wins.

    records_path points this at a different log than the market's own.
    """
    paths = [records_path] if records_path is not None else [ALERT_RECORDS[market][timeframe]]
    window = pd.Timedelta(minutes=BAR_MINUTES[timeframe] * WATCH_BARS)
    return _parse_zone_records(paths, timeframe, market, now, window)


def fib_tl_window(market: str, timeframe: str) -> pd.Timedelta:
    """How long a fib/trendline alert stays fillable: FIB_TL_ENTRY_WAIT_BARS
    candles of its timeframe, the same wait the daily report scores it with.
    An NSE week has five sessions, so its five daily candles span seven days.
    """
    seconds = TF_SECONDS[timeframe] * FIB_TL_ENTRY_WAIT_BARS
    if market == "nse" and timeframe == "1d":
        seconds = seconds * 7 // 5
    return pd.Timedelta(seconds=seconds)


def load_fib_tl_alerts(
    market: str, timeframe: str, now: pd.Timestamp, records_path=None
) -> list[dict]:
    """Fib and trendline alerts on this market and timeframe still inside
    their fillable window, in the same shape resolve_pings() reads.

    A trendline re-alerts as price comes back to the same line; only its
    newest alert is watched, with the entry and stop that alert planned.
    """
    path = records_path if records_path is not None else FIB_TL_RECORDS
    if not path.exists():
        return []
    window = fib_tl_window(market, timeframe)
    newest: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("market") != market or row.get("tf") != timeframe:
            continue
        if row.get("kind") not in FIB_TL_KIND_LABEL:
            continue
        symbol = str(row.get("symbol", ""))
        if market == "crypto" and symbol.upper() not in CRYPTO_WATCHLIST_SET:
            continue
        plan = row.get("plan") or {}
        try:
            entry = float(plan["entry"])
            stop = float(plan["sl"])
            delivered = pd.Timestamp(int(row["sent_ts"]), unit="s", tz="UTC").tz_convert(IST)
        except (KeyError, TypeError, ValueError):
            continue
        if entry <= 0 or stop == entry or plan.get("side") not in ("long", "short"):
            continue
        if now - delivered > window or delivered > now:
            continue
        record = {
            "symbol": symbol,
            "timeframe": timeframe,
            "side": plan["side"],
            "kind": row["kind"],
            "level": row.get("level") or "L3",
            "_entry": entry,
            "_stop": stop,
            "_delivered": delivered,
            "_market": market,
            "_alert_price": row.get("price"),
        }
        key = str(row.get("key") or watch_key(record))
        if key not in newest or delivered >= newest[key]["_delivered"]:
            newest[key] = record
    return [record for record in newest.values() if not past_entry_when_sent(record)]


def past_entry_when_sent(record: dict) -> bool:
    """True when price was already through the entry as the alert went out.

    A fib alerts from inside its zone (0% away), so a long can be sent with
    price already under its entry. Nothing is left to get ready for, and
    watching it backfilled "GET READY · moved fast, already at entry" next to
    a LATE for an entry the alert itself had already passed (BNB 1M, entry
    838.05 sent at 751.92 on 2026-10-12, lakky). The fib alert is the only
    message such a level gets.
    """
    try:
        price = float(record.get("_alert_price"))
    except (TypeError, ValueError):
        return False
    return risk_progress(price, record["_entry"], record["_stop"], record["side"]) > 0


# rating_allowed() (dropped 17 Sep 2026) used to gate this on
# MIN_CRYPTO_ZONE_SCORE - but the score it was checking could itself be
# wrong (a BNB alert once showed 9/10 while the record it wrote down scored
# it 4, see scanner.format_alert()'s fix), and rating_validation_report.py
# run against real decided trades that same day showed the ML rating is not
# currently discriminating outcomes at all: win rate flat ~50-53% from
# 3/10 through 9/10, not monotonic, while UNRATED zones (no ML score) won
# 74.2% - far better than any rated bucket. A gate that isn't demonstrably
# separating good zones from bad ones was just hiding real alerts from
# entry_confirm. Every zone the scanner alerts on is watched here now,
# unfiltered by score - re-add a gate if rating_validation_report.py ever
# shows the model earning its keep on live outcomes.


def watch_key(record: dict) -> str:
    """Identify a zone, not a particular delivery of it.

    The same zone is re-alerted every scan, and its edges drift in the
    far decimals as ATR moves with each new candle: one BANKINDIA level
    came through as 141.17203103 and then 141.17210107. Four fixed
    decimals split those into two keys, so the same trade was watched -
    and pinged - twice in one digest. Six significant figures is a
    thousand times finer than any real zone is wide, so distinct levels
    still get distinct keys.
    """
    symbol = str(record.get("symbol", "")).upper()
    entry = f"{float(record['_entry']):.6g}"
    stop = f"{float(record['_stop']):.6g}"
    return f"{symbol}|{record.get('timeframe')}|{record.get('side')}|{entry}|{stop}"


def drop_legacy_keys(state: dict) -> None:
    """Remove the _silent_ready| keys the zone watch rows (removed 2026-10-09)
    left behind; prune_state keeps underscore keys, so nothing else would."""
    for key in [k for k in state if k.startswith("_silent_ready|")]:
        del state[key]


def price_decimals(value: float, market: str = "crypto") -> int:
    """Crypto runs from 77,000 to 0.00002; two decimals suits neither.

    NSE stays at two throughout - that is how the exchange quotes and how
    the alerts have always read, and varying it by price would make one
    channel print the same kind of instrument three different ways.

    Deliberately its own rule rather than scanner.price_decimals. A ping is a
    one-line digest entry and reads narrower than the alert that preceded it;
    the two only have to agree about the level, which they do, not about how
    many trailing zeros to carry.
    """
    if market == "nse":
        return 2
    value = abs(float(value))
    if value >= 100:
        return 2
    if value >= 1:
        return 3
    if value >= 0.01:
        return 5
    return 8


# How many of the most recent candles to sweep for a missed stage. The
# dispatch interval is meant to be 5 minutes but is not reliably that in
# practice - real gaps up to 40+ minutes happen (queued runs behind a slow
# one, or the external cron dispatch itself skipping a slot). Two candles
# covers a 40-minute gap on the 30m feed with room to spare; on 4h it is
# generously wide, which is fine - a wider sweep only helps the same problem
# there too.
SWEEP_CANDLES = 2
# Candles requested per symbol for the price check (see fetch_crypto_prices).
PRICE_OHLCV_LIMIT = 50
# The fine-candle sweep never reaches back further than this, whatever the
# previous check: crypto sleeps 01:00-08:00 IST, so 12 hours covers the night.
SWEEP_MAX_SECONDS = 12 * 3600
LAST_CHECK_KEY = "_last_check|{market}"


def fine_rows(rows, seconds: int) -> dict:
    """The price_info fields for a fine-candle sweep: [[open_ts, high, low], ...]."""
    return {
        "candles": [[int(r[0]), float(r[1]), float(r[2])] for r in rows],
        "candle_seconds": int(seconds),
    }


def sweep_since(record: dict, state: dict, now: pd.Timestamp) -> float:
    """Where this record's sweep starts: the later of its alert and its
    market's previous check, never more than SWEEP_MAX_SECONDS back."""
    sent = record["_delivered"].timestamp()
    last = float(state.get(LAST_CHECK_KEY.format(market=record.get("_market", "")), 0.0) or 0.0)
    return max(sent, last, now.timestamp() - SWEEP_MAX_SECONDS)


def fetch_crypto_prices(symbols: list[str], since: dict[str, float] | None = None) -> dict[str, dict]:
    """Latest crypto price per symbol, plus the recent candle range swept.

    Each entry is {"price": ..., "recent_low": ..., "recent_high": ...} -
    the low/high cover the last SWEEP_CANDLES candles (closed and forming),
    so a stage the live ticker's single point-in-time price would have
    missed between two polls - price touched the level and moved on before
    this run happened - can still be caught from the candles.

    Imported lazily: the NSE-only path must not pay for ccxt's exchange
    loading, and a crypto venue being unreachable must not stop NSE pings.

    Run across a thread pool, not sequentially - each symbol here is a
    fetch_symbol_ohlcv() chain that can try Bitunix, Delta and
    every fallback exchange in turn before it gives up. One process running
    "both" timeframes can watch two dozen symbols at once, and at roughly a
    second or more per symbol that is a run comfortably past this job's
    5-minute dispatch interval - which does not free the runner, it queues
    the next dispatch behind it (workflow concurrency is cancel-in-progress:
    false), and the backlog compounds through the day. scanner.py's own scan
    already parallelizes this exact chain with SCAN_WORKERS; this mirrors it.
    """
    if not symbols:
        return {}
    try:
        import scanner
    except Exception as error:
        print(f"crypto price fetch unavailable: {error}")
        return {}

    # Only the last SWEEP_CANDLES candles and the live price are used here, so
    # there is no need for the scanner's full 1500-candle history per symbol.
    scanner.OHLCV_LIMIT = PRICE_OHLCV_LIMIT

    def fetch_one(symbol):
        ohlcv, exchange_name = scanner.fetch_symbol_ohlcv(symbol)
        candle_close = float(ohlcv[-1][4])
        price, _ = scanner.live_ticker_price(exchange_name, symbol, candle_close)
        recent = ohlcv[-SWEEP_CANDLES:]
        recent_low = min(float(candle[3]) for candle in recent)
        recent_high = max(float(candle[2]) for candle in recent)
        # The live ticker can itself be beyond either candle boundary - it
        # runs ahead of the last closed candle - so fold it in rather than trusting the candles
        # alone to bound where price has actually been.
        info = {
            "price": float(price),
            "recent_low": min(recent_low, float(price)),
            "recent_high": max(recent_high, float(price)),
        }
        start = (since or {}).get(symbol)
        if start is not None:
            # Bitunix 1m since the earliest sweep start of this symbol's records
            # (sweep_since); the fixed two-candle range above is only the
            # fallback for symbols Bitunix does not carry (XAUT, SLVON).
            try:
                import bitunix_data

                if bitunix_data.uses_bitunix(symbol):
                    pair = bitunix_data.pair_for(
                        symbol, scanner.delta_contract(symbol) or symbol
                    )
                    rows = bitunix_data.klines(pair, "1m", int(start) // 60 * 60, int(time.time()) + 1)
                    info.update(fine_rows([[r[0], r[2], r[3]] for r in rows], 60))
            except Exception as error:
                print(f"{symbol} 1m sweep unavailable: {str(error)[:80]}")
        return info

    prices: dict[str, dict[str, float]] = {}
    with ThreadPoolExecutor(max_workers=min(scanner.SCAN_WORKERS, len(symbols))) as executor:
        futures = {executor.submit(fetch_one, symbol): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                prices[symbol] = future.result()
            except Exception as error:
                print(f"{symbol} price unavailable: {str(error)[:80]}")
    return prices


def fetch_prices(symbols: list[str]) -> dict[str, dict]:
    """Latest traded price per symbol, and its 5m candles of the last few
    sessions for the sweep: {"price", "candles", "candle_seconds"}.

    It returned the last 15m close only, so an NSE wick that touched the entry
    and came back between two checks was never seen (16 of 26 missed 1D+
    entry confirms, 9-21 Oct 2026).
    """
    if not symbols:
        return {}
    try:
        raw = yf.download(
            tickers=" ".join(symbols),
            period="5d",
            interval="5m",
            auto_adjust=False,
            progress=False,
            threads=True,
            group_by="column",
        )
    except Exception as error:
        print(f"price fetch failed: {error}")
        return {}
    if raw is None or raw.empty:
        return {}

    def column(name):
        frame = raw[name] if name in raw else None
        if isinstance(frame, pd.Series):
            frame = frame.to_frame(symbols[0])
        return frame

    closes, highs, lows = column("Close"), column("High"), column("Low")
    if closes is None:
        return {}

    prices: dict[str, dict] = {}
    for symbol in symbols:
        if symbol not in closes:
            continue
        frame = pd.DataFrame({
            "close": pd.to_numeric(closes[symbol], errors="coerce"),
            "high": pd.to_numeric(highs[symbol], errors="coerce") if highs is not None and symbol in highs else None,
            "low": pd.to_numeric(lows[symbol], errors="coerce") if lows is not None and symbol in lows else None,
        }).dropna(subset=["close"])
        if frame.empty:
            continue
        info = {"price": float(frame["close"].iloc[-1])}
        bars = frame.dropna(subset=["high", "low"])
        if not bars.empty:
            index = bars.index if bars.index.tz is not None else bars.index.tz_localize(IST)
            info.update(fine_rows(
                [[int(ts.timestamp()), h, l] for ts, h, l in zip(index, bars["high"], bars["low"])],
                300,
            ))
        prices[symbol] = info
    return prices


def risk_progress(price: float, entry: float, stop: float, side: str) -> float:
    """Share of the planned entry-to-stop distance already consumed.

    0.0 sits exactly at entry, 1.0 at the stop, and negative means price
    has moved past entry into profit.
    """
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    direction = 1.0 if side == "long" else -1.0
    return -direction * (price - entry) / risk


def classify(price: float, record: dict, reached_entry: bool) -> tuple[int | None, bool]:
    """Return (stage, reached_entry) for the current price."""
    entry = record["_entry"]
    stop = record["_stop"]
    progress = risk_progress(price, entry, stop, record.get("side", "long"))

    if progress >= 1.0:
        return None, True
    if progress >= NEAR_SL_FRACTION:
        return STAGE_LATE, True
    if progress >= 0.0:
        return STAGE_ENTRY, True
    if reached_entry:
        # Bounced back past entry: the locked stop is now far away, so
        # taking it here would risk much more than the alert planned.
        return None, True
    if abs(price - entry) / entry * 100.0 <= APPROACH_THRESHOLD_PCT:
        return STAGE_READY, False
    return None, False


STAGE_HEADINGS = {
    STAGE_ENTRY: "🎯 ENTRY NOW",
    STAGE_LATE: "⚠️ LATE · NEAR SL",
    STAGE_READY: "👀 GET READY",
}
# Entry first: it is the only stage that asks for an action right now.
STAGE_ORDER = [STAGE_ENTRY, STAGE_LATE, STAGE_READY]


def format_line(stage: int, price: float, record: dict, note: str = "") -> str:
    """One line per alert. Three lines each turned a busy run into a wall.

    `price` and `note` must describe the same moment: the number printed
    always has to justify the stage next to it. A LATE ping built from a
    swept high but displayed with the live price once produced "LATE ·
    NEAR SL ... -108% risk used" - a self-contradiction, since price had
    since run back into profit. Whichever price actually earned the stage
    (see resolve_pings) is the one that belongs here; note says so when
    that price is not simply "right now".
    """
    entry = record["_entry"]
    stop = record["_stop"]
    side = "BUY" if record.get("side") == "long" else "SELL"
    score = record.get("score")
    score_text = f" {int(score)}/10" if score is not None else ""
    stop_pct = abs(entry - stop) / entry * 100.0
    progress = risk_progress(price, entry, stop, record.get("side", "long"))
    symbol = display_symbol(record.get("symbol", ""))
    places = price_decimals(entry, record.get("_market", "crypto"))

    kind = FIB_TL_KIND_LABEL.get(record.get("kind"))
    if kind:
        # Timeframe, kind and level in bold (lakky, 2026-10-12). A fib's four
        # edges are L1-L4 from the one price reaches first: L1/L2 the weaker
        # box, L3/L4 the stronger. The bot enters at the stronger box's near
        # edge, L3.
        level = f" {record.get('level') or 'L3'}" if record.get("kind") == "fib" else ""
        head = f"`{symbol}` {side} · **{TF_LABEL.get(record.get('timeframe'), record.get('timeframe'))} {kind}{level}**"
    else:
        head = f"`{symbol}` {side}{score_text}"
    levels = f"{price:.{places}f} → {entry:.{places}f}"
    stop_text = f"SL {stop:.{places}f} ({stop_pct:.2f}%)"

    note_text = f" · {note}" if note else ""

    if stage == STAGE_READY:
        away = abs(price - entry) / entry * 100.0
        return f"{head} · {levels} · {away:.2f}% away · {stop_text}{note_text}"
    return f"{head} · {levels} · {stop_text} · {progress * 100:.0f}% risk used{note_text}"


def build_digest(pings: list[tuple[int, str]], now: pd.Timestamp, market: str = "") -> list[str]:
    """Group a run's pings into as few messages as Discord allows."""
    if not pings:
        return []

    sections = []
    for stage in STAGE_ORDER:
        lines = [line for stage_id, line in pings if stage_id == stage]
        if lines:
            heading = f"**{STAGE_HEADINGS[stage]}**"
            sections.append(heading + "\n" + "\n".join(lines))

    label = MARKET_LABELS.get(market, "")
    header = f"__Entry watch · {label + ' · ' if label else ''}{now:%H:%M} IST__"
    messages, current = [], header
    for section in sections:
        candidate = current + "\n\n" + section
        if len(candidate) > MAX_MESSAGE_CHARS and current != header:
            messages.append(current)
            current = section
        else:
            current = candidate
    messages.append(current)

    # A single section can still outgrow one message on a busy day.
    split: list[str] = []
    for message in messages:
        while len(message) > MAX_MESSAGE_CHARS:
            cut = message.rfind("\n", 0, MAX_MESSAGE_CHARS)
            cut = cut if cut > 0 else MAX_MESSAGE_CHARS
            split.append(message[:cut])
            message = message[cut:].lstrip("\n")
        if message:
            split.append(message)
    return split


def display_symbol(symbol: str) -> str:
    text = str(symbol).strip().upper()
    if text.endswith(".NS"):
        return text[:-3]
    try:
        import scanner

        return scanner.display_symbol(text)
    except Exception:
        return text


def webhook_for(market: str = "") -> str:
    """The market's own entry-confirm webhook, else the shared one."""
    own = MARKET_WEBHOOK_ENVS.get(market)
    if own:
        url = os.getenv(own, "").strip()
        if url:
            return url
    return os.getenv(WEBHOOK_ENV, "").strip()


def send_ping(message: str, market: str = "") -> bool:
    webhook = webhook_for(market)
    if not webhook:
        print(f"No entry-confirm webhook configured for {market or 'this run'}; skipping send.")
        return False
    for attempt in range(3):
        try:
            response = requests.post(webhook, json={"content": message}, timeout=15)
            if response.status_code == 429 and attempt < 2:
                # Discord rate limit: wait what it asks (capped) and retry,
                # rather than dropping the digest for a whole run.
                try:
                    wait = float(response.json().get("retry_after", 1.0))
                except ValueError:
                    wait = 1.0
                time.sleep(min(max(wait, 0.5), 10.0))
                continue
            response.raise_for_status()
            return True
        except requests.RequestException as error:
            print(f"entry-confirm ping failed: {error}")
            return False
    return False


def ready_key(record: dict) -> str:
    """One GET READY budget per symbol per timeframe, not per zone."""
    symbol = str(record.get("symbol", "")).upper()
    return f"_ready|{symbol}|{record.get('timeframe')}"


def level_ready_key(record: dict) -> str:
    """One GET READY budget per exact level."""
    return "_level_ready|" + watch_key(record)


def ready_recently(state: dict, record: dict, now: pd.Timestamp) -> bool:
    last = float(state.get(ready_key(record), 0.0) or 0.0)
    if not last:
        return False
    return (now.timestamp() - last) < READY_COOLDOWN_SECONDS


def level_ready_recently(state: dict, record: dict, now: pd.Timestamp) -> bool:
    last = float(state.get(level_ready_key(record), 0.0) or 0.0)
    if not last:
        return False
    return (now.timestamp() - last) < LEVEL_READY_COOLDOWN_SECONDS


def prune_state(state: dict, active_keys: set[str]) -> dict:
    # Underscore-prefixed keys are bookkeeping, not zones - the GET READY
    # budget lives there. Pruning to active zone keys alone dropped it on
    # every run, which made the cooldown expire the instant it was written.
    return {
        key: value
        for key, value in state.items()
        if key in active_keys or key.startswith("_")
    }


def sweep_extreme(price_info: dict, side: str, since: float | None = None) -> float:
    """The most favourable price reached recently, for stage detection.

    A long's entry is approached from above, so its favourable extreme is
    the recent low; a short's is the recent high. Classifying against this
    instead of only the live point-in-time price catches a stage the
    ticker's single snapshot would have missed between two polls - price
    touched the level and moved on before this run happened to look.
    With fine candles and a start (sweep_since) only candles still open after
    the start count, and the live price is folded in. Otherwise the fixed
    recent range, else the live price.
    """
    price = float(price_info["price"])
    candles = price_info.get("candles")
    if candles is not None and since is not None:
        seconds = int(price_info.get("candle_seconds", 60))
        recent = [c for c in candles if c[0] + seconds > since]
        if side == "long":
            return min([price] + [float(c[2]) for c in recent])
        return max([price] + [float(c[1]) for c in recent])
    key = "recent_low" if side == "long" else "recent_high"
    return float(price_info.get(key, price))


def _rank(stage: int | None) -> int:
    return -1 if stage is None else stage


def resolve_pings(
    record: dict, price_info: dict, state: dict, now: pd.Timestamp, since: float | None = None
) -> tuple[list[tuple[int, str]], dict]:
    """Decide this record's pings for one run and its updated entry_state.

    Forward-only: a symbol reports each stage once, never on every run,
    which is what turned a handful of trades into a wall of near-identical
    messages.

    Classified twice - once against the live price, once against the
    swept range (sweep_extreme()) - and whichever is more advanced wins,
    so a stage reached and left behind between two polls still registers.
    Critically, the PRICE THAT WON is also the price the message shows: a
    LATE ping decided from a swept high but displayed with a live price
    that had since run back into profit once printed "LATE · NEAR SL ...
    -108% risk used" - a stage and a number that flatly contradicted each
    other. When the swept price is what earned the stage, the message
    says so instead of silently presenting a stale peak as "now".
    """
    key = watch_key(record)
    entry_state = state.get(key, {})
    reached_entry = bool(entry_state.get("reached_entry", False))
    last_stage = int(entry_state.get("stage", 0))

    price = float(price_info["price"])
    extreme = sweep_extreme(price_info, record.get("side", "long"), since)
    stage_now, reached_now = classify(price, record, reached_entry)
    stage_swept, reached_swept = classify(extreme, record, reached_entry)
    reached_entry = reached_now or reached_swept

    if _rank(stage_swept) > _rank(stage_now):
        stage = stage_swept
        display_price = extreme
        swept_only = True
    else:
        stage = stage_now
        display_price = price
        swept_only = False
    entry_state["reached_entry"] = reached_entry

    # classify() collapses "stop already hit" and "bounced back into
    # profit" to the same (None, True) - both go quiet, which is correct
    # for the run that observes it. But neither classify() nor
    # reached_entry remembers WHICH one happened, and reached_entry is
    # only consulted on the profit-bounce branch (progress < 0) - the
    # STAGE_ENTRY/STAGE_LATE branches don't look at it at all. So a stop
    # that was genuinely hit, followed by price drifting back into the
    # 0-100% risk band, used to report ENTRY NOW or LATE again for a trade
    # that had already failed - found auditing this rather than reported.
    # Once the stop is hit (by the live price or anything the sweep
    # touched), this zone is retired for good: no further stage, ever.
    side = record.get("side", "long")
    entry = record["_entry"]
    stop = record["_stop"]
    stopped_out = bool(entry_state.get("stopped_out", False)) or (
        risk_progress(price, entry, stop, side) >= 1.0
        or risk_progress(extreme, entry, stop, side) >= 1.0
    )
    newly_stopped = stopped_out and not entry_state.get("stopped_out", False)
    entry_state["stopped_out"] = stopped_out

    pings: list[tuple[int, str]] = []
    if last_stage < STAGE_ENTRY and (newly_stopped or stage == STAGE_LATE):
        # Filled and already past half the risk, or stopped, by the time this
        # check looked: entry was never announced. Say so once under ENTRY NOW
        # with the risk used, rather than nothing (lakky, 2026-10-21: GLAND 1D
        # L4 filled and stopped in one 5m candle; KAJARIACER L4 got a LATE but
        # never an ENTRY). An alert sent with price already past its entry is
        # not watched at all (past_entry_when_sent), so the BNB 1M case of
        # 2026-10-12 still sends nothing.
        worst = extreme if risk_progress(extreme, entry, stop, side) >= risk_progress(
            price, entry, stop, side) else price
        note = "filled and stopped since the last check" if stopped_out else "filled since the last check"
        pings.append((STAGE_ENTRY, format_line(STAGE_ENTRY, worst, record, note=note)))
        entry_state["stage"] = STAGE_LATE
        state[key] = entry_state
        return pings, entry_state
    if stopped_out:
        stage = None

    if stage is not None and stage > last_stage:
        ready_seen = ready_recently(state, record, now) or level_ready_recently(
            state, record, now
        )
        live_gap_pct = abs(price - entry) / entry * 100.0
        if (last_stage == 0 and stage == STAGE_ENTRY and not ready_seen
                and live_gap_pct <= APPROACH_THRESHOLD_PCT):
            # entry_confirm polls every few minutes; a fast mover (crypto
            # especially) can cross the whole GET READY -> ENTRY gap
            # between two polls and never get caught mid-approach - the
            # scanner alert itself only fires once price is already inside
            # APPROACH_THRESHOLD_PCT, so there is barely a window to catch
            # in the first place. Back-fill the GET READY the user would
            # otherwise never see, in the same digest, so a jump straight
            # to ENTRY NOW still comes with its heads-up.
            state[ready_key(record)] = now.timestamp()
            state[level_ready_key(record)] = now.timestamp()
            pings.append(
                (
                    STAGE_READY,
                    format_line(STAGE_READY, price, record, note="moved fast, already at entry"),
                )
            )

        if stage == STAGE_READY and ready_seen:
            entry_state["stage"] = stage
        else:
            if stage == STAGE_READY:
                state[ready_key(record)] = now.timestamp()
                state[level_ready_key(record)] = now.timestamp()
            note = "peaked here since the last check, price has since moved" if swept_only else ""
            pings.append((stage, format_line(stage, display_price, record, note=note)))
            entry_state["stage"] = stage

    state[key] = entry_state
    return pings, entry_state


def crypto_alert_window_open(now: pd.Timestamp) -> bool:
    """Same 08:00-01:00 IST window the crypto scanner alerts in.

    A ping is only useful if the alert behind it could have been
    posted, and following the scanner keeps one rule in one place.
    """
    try:
        import scanner

        return scanner.in_alert_window(now.to_pydatetime())
    except Exception:
        return True


def markets_for(choice: str) -> list[str]:
    return ["nse", "crypto"] if choice == "all" else [choice]


def timeframes_for(choice: str) -> list[str]:
    return list(FIB_TL_WATCH_TIMEFRAMES) if choice == "all" else [choice]


_MISSING = object()


def record_state_keys(record: dict) -> list[str]:
    """Every state key resolve_pings can write for this record."""
    return [watch_key(record), ready_key(record), level_ready_key(record)]


def undo_undelivered(state: dict, changes: list[tuple[list[str], dict]], delivered: list[str]) -> dict:
    """A copy of state with the stage updates of undelivered pings rolled back.

    A record counts as delivered only when every line it produced is in a
    posted message. Undelivered records are rolled back newest first, and a
    key that a delivered record changed afterwards (the per-symbol GET READY
    budget is shared) is left as the delivered record set it.
    """
    result = json.loads(json.dumps(state))
    sent_text = "\n".join(delivered)
    delivered_flags = [all(line in sent_text for line in lines) for lines, _ in changes]
    for index in range(len(changes) - 1, -1, -1):
        if delivered_flags[index]:
            continue
        _, before = changes[index]
        later_delivered_keys = {
            key
            for later in range(index + 1, len(changes))
            if delivered_flags[later]
            for key in changes[later][1]
        }
        for key, value in before.items():
            if key in later_delivered_keys:
                continue
            if value is _MISSING:
                result.pop(key, None)
            else:
                result[key] = json.loads(json.dumps(value))
    return result



def main() -> None:
    args = parse_args()
    now = pd.Timestamp.now(tz=IST)

    watched: list[dict] = []
    for market in markets_for(args.market):
        # Crypto never closes, so the 09:15-15:10 guard is an NSE rule and
        # applying it everywhere would silence crypto for most of the day.
        if market == "nse" and not args.ignore_session and not in_trading_session(now):
            print(f"NSE outside trading window ({now:%Y-%m-%d %H:%M} IST); skipping.")
            continue
        if (
            market == "crypto"
            and not args.ignore_session
            and not crypto_alert_window_open(now)
        ):
            print("Crypto outside the 08:00-01:00 IST window; skipping.")
            continue
        for timeframe in timeframes_for(args.timeframe):
            watched.extend(load_fib_tl_alerts(market, timeframe, now))

    if not watched:
        print("No alerts inside their entry window.")
        return

    state = load_state()
    since = {id(record): sweep_since(record, state, now) for record in watched}
    prices: dict[str, dict] = fetch_prices(
        sorted({r["symbol"] for r in watched if r["_market"] == "nse"})
    )
    crypto_since: dict[str, float] = {}
    for record in watched:
        if record["_market"] == "crypto":
            symbol = record["symbol"]
            crypto_since[symbol] = min(crypto_since.get(symbol, since[id(record)]), since[id(record)])
    prices.update(fetch_crypto_prices(sorted(crypto_since), crypto_since))
    drop_legacy_keys(state)

    # One heads-up per symbol, not one per level. Widening the watch band to
    # 0.75% put several stacked zones on the same symbol in range at once and
    # each warned separately: 74 GET READYs came from 36 symbols across 70
    # zones in half a day, TSLA alone six times for four levels. That the
    # price is approaching TSLA is one piece of news however many boxes are
    # drawn near it. The same exact level also gets a six-hour budget, so
    # repeat scanner deliveries cannot keep saying GET READY. The zone is
    # still marked, so its ENTRY NOW - which names a specific level and is
    # worth having per zone - still fires when price arrives.
    pings: dict[str, list[tuple[int, str]]] = {market: [] for market in MARKET_LABELS}
    changes: list[tuple[list[str], dict]] = []
    for record in watched:
        price_info = prices.get(record["symbol"])
        if price_info is None:
            continue
        before = {k: state.get(k, _MISSING) for k in record_state_keys(record)}
        record_pings, _ = resolve_pings(record, price_info, state, now, since[id(record)])
        pings.setdefault(record["_market"], []).extend(record_pings)
        if record_pings:
            changes.append(([line for _, line in record_pings], before))

    active_keys = {watch_key(record) for record in watched}
    # One digest per market, each to its own channel. A market whose post
    # fails stops there; the other market still goes out.
    digests = {market: build_digest(lines, now, market) for market, lines in pings.items()}
    if not any(digests.values()):
        print("Nothing new to report.")
    delivered: list[str] = []
    failed: set[str] = set()
    for market, messages in digests.items():
        for message in messages:
            if args.dry_run:
                print(message + "\n")
                continue
            if not send_ping(message, market):
                # Only what landed may be marked sent. Records whose lines are in
                # the undelivered parts go back to their earlier stage, so the
                # next run reports them - and the parts that did land are not
                # repeated, as they were when nothing at all was saved.
                print(f"{market} digest part not delivered; its stages left unmarked for the next run.")
                failed.add(market)
                break
            delivered.append(message)
            # Saved after every part, so a run cancelled mid-digest cannot
            # re-send the parts already posted.
            save_state(prune_state(undo_undelivered(state, changes, delivered), active_keys))

    if args.dry_run:
        return
    final = undo_undelivered(state, changes, delivered)
    # Where the next check's sweep starts, per market (sweep_since): only a
    # market this run priced and fully delivered, so an undelivered fill is
    # still inside the next run's sweep.
    for market in {r["_market"] for r in watched if r["symbol"] in prices} - failed:
        final[LAST_CHECK_KEY.format(market=market)] = now.timestamp()
    save_state(prune_state(final, active_keys))

if __name__ == "__main__":
    main()
