"""Stage pings for zone alerts that were already delivered.

Watches only zones that a real scanner alert already announced, and
reports how price is behaving relative to that alert's own recorded
entry and stop. It never re-derives levels, never scans for new
candidates, and never writes to the alert records the backtest reads.

Stages (one ping each, forward-only):
  1 GET READY     price within APPROACH_THRESHOLD_PCT of entry, entry
                  not yet reached
  2 ENTRY NOW     entry reached, under NEAR_SL_FRACTION of planned risk
                  consumed
  3 LATE/NEAR SL  entry reached, most of the planned risk already gone

Deliberately silent when the trade is no longer worth taking: price has
bounced back past entry into profit (entering now would sit far from the
locked stop), or the stop is already hit.

A fast mover can cross the whole GET READY -> ENTRY gap between two polls
and be seen for the first time already at ENTRY NOW or LATE. When that
happens the GET READY the user would otherwise never get is backfilled into
the same digest, marked as having moved fast rather than printed as a live
distance.

The dispatch interval is meant to be 5 minutes but is not reliably that -
real gaps of 20-40+ minutes happen. Stage detection therefore looks at the
last couple of candles' range (sweep_extreme()), not only the live ticker's
single point-in-time price, so a stage price touched and moved past before
this run got to look is still caught. Messages still show the live price -
only whether a stage has been reached looks at the swept range.

Every ping from one run goes out as a single digest. Posted one message
per symbol, a busy run buried the channel under dozens of separate blocks
and the few that mattered were impossible to pick out.
"""
from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import time as datetime_time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

from config import DELTA_LISTED_SYMBOLS, MAX_DISTANCE_PCT, WATCHLIST

# Only crypto is checked against its watchlist. The NSE side has no
# authoritative one here - nse_config carries a FALLBACK_WATCHLIST used when
# the live universe cannot be fetched, so filtering on it would drop real
# alerts for symbols that are perfectly valid.
CRYPTO_WATCHLIST_SET = {str(symbol).upper() for symbol in WATCHLIST}


IST = ZoneInfo("Asia/Kolkata")
WEBHOOK_ENV = "DISCORD_ENTRY_CONFIRM_WEBHOOK_URL"
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
# Zones the scanner noted as worth watching but did not alert on. Kept here
# only so older tests/tools can still locate the files; entry_confirm does not
# read them for live pings because that can announce a trade before the real
# crypto alert channel has delivered it.
WATCH_RECORDS = {
    "crypto": {
        "30m": Path(__file__).with_name("crypto_watch_records_30m.jsonl"),
        "4h": Path(__file__).with_name("crypto_watch_records.jsonl"),
    },
}
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
    # Both by default: the user watches 30m and 4h together, so covering
    # one silently halves the channel.
    parser.add_argument(
        "--timeframe", choices=["30m", "4h", "both"], default="both"
    )
    parser.add_argument(
        "--market",
        choices=["nse", "crypto", "all"],
        default="crypto",
        help="Which alert records to watch. Crypto covers xStocks too.",
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
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


# How different a re-alert's entry can be from an earlier one on the same
# symbol/side/timeframe and still count as a venue flip on the same real
# zone rather than a genuinely new one. fetch_symbol_ohlcv() tries CoinSwitch
# first each scan and falls back to Binance/Delta/others when it is slow or
# fails, so the same real level can come back priced from a different venue
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
    already confirmed - the "coinswitch alert still gets on the entry
    confirm" report. The first record in a matching run is kept as the
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


def load_watched_alerts(
    market: str, timeframe: str, now: pd.Timestamp, records_path=None
) -> list[dict]:
    """Alerts still inside their fillable window, newest occurrence wins.

    records_path points this at a different log - paper_trading uses it to read
    the shadow-geometry alerts, which are written by the scanner but never sent.
    """
    if records_path is not None:
        paths = [records_path]
    else:
        paths = [ALERT_RECORDS[market][timeframe]]

    window = pd.Timedelta(minutes=BAR_MINUTES[timeframe] * WATCH_BARS)
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
            # A symbol dropped from the watchlist keeps pinging for as long as its
            # last alert stays fillable - twelve hours on 4h - and broker_label
            # would call it CoinSwitch, because that is what anything outside the
            # Delta list resolves to. Sending someone to the wrong exchange is
            # worse than saying nothing, and the symbol was dropped on purpose.
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


def fetch_crypto_prices(symbols: list[str]) -> dict[str, dict[str, float]]:
    """Latest crypto price per symbol, plus the recent candle range swept.

    Each entry is {"price": ..., "recent_low": ..., "recent_high": ...} -
    the low/high cover the last SWEEP_CANDLES candles (closed and forming),
    so a stage the live ticker's single point-in-time price would have
    missed between two polls - price touched the level and moved on before
    this run happened - can still be caught from the candles.

    Imported lazily: the NSE-only path must not pay for ccxt's exchange
    loading, and a crypto venue being unreachable must not stop NSE pings.

    Run across a thread pool, not sequentially - each symbol here is a
    fetch_symbol_ohlcv() chain that can try CoinSwitch, Binance, Delta and
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

    def fetch_one(symbol):
        ohlcv, exchange_name = scanner.fetch_symbol_ohlcv(symbol)
        candle_close = float(ohlcv[-1][4])
        price, _ = scanner.live_ticker_price(exchange_name, symbol, candle_close)
        recent = ohlcv[-SWEEP_CANDLES:]
        recent_low = min(float(candle[3]) for candle in recent)
        recent_high = max(float(candle[2]) for candle in recent)
        # The live ticker can itself be beyond either candle boundary -
        # CoinSwitch's fine price in particular runs ahead of its own last
        # closed candle - so fold it in rather than trusting the candles
        # alone to bound where price has actually been.
        return {
            "price": float(price),
            "recent_low": min(recent_low, float(price)),
            "recent_high": max(recent_high, float(price)),
        }

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


def fetch_prices(symbols: list[str]) -> dict[str, float]:
    """Latest traded price per symbol, including the forming candle."""
    if not symbols:
        return {}
    try:
        raw = yf.download(
            tickers=" ".join(symbols),
            period="1d",
            interval="15m",
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

    closes = raw["Close"] if "Close" in raw else raw
    if isinstance(closes, pd.Series):
        closes = closes.to_frame(symbols[0])

    prices: dict[str, float] = {}
    for symbol in symbols:
        if symbol not in closes:
            continue
        series = pd.to_numeric(closes[symbol], errors="coerce").dropna()
        if not series.empty:
            prices[symbol] = float(series.iloc[-1])
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


def broker_label(record: dict) -> str | None:
    """Where to go and place this trade.

    Only crypto has a venue choice: an NSE symbol is not on either book,
    so tagging it would be noise. Delta lists what it lists and everything
    else on the watchlist is reached through CoinSwitch, which is why the
    fallback is unconditional rather than a second lookup.
    """
    if record.get("_market") != "crypto":
        return None
    symbol = str(record.get("symbol", "")).strip().upper()
    return "Delta" if symbol in DELTA_LISTED_SYMBOLS else "CoinSwitch"


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

    head = f"`{symbol}` {side}{score_text}"
    levels = f"{entry:.{places}f} → {price:.{places}f}"
    stop_text = f"SL {stop:.{places}f} ({stop_pct:.2f}%)"

    broker = broker_label(record)
    venue = f" · {broker}" if broker else ""
    note_text = f" · {note}" if note else ""

    if stage == STAGE_READY:
        away = abs(price - entry) / entry * 100.0
        return f"{head} · {levels} · {away:.2f}% away · {stop_text}{venue}{note_text}"
    return f"{head} · {levels} · {stop_text} · {progress * 100:.0f}% risk used{venue}{note_text}"


def build_digest(pings: list[tuple[int, str]], now: pd.Timestamp) -> list[str]:
    """Group a run's pings into as few messages as Discord allows."""
    if not pings:
        return []

    sections = []
    for stage in STAGE_ORDER:
        lines = [line for stage_id, line in pings if stage_id == stage]
        if lines:
            heading = f"**{STAGE_HEADINGS[stage]}**"
            sections.append(heading + "\n" + "\n".join(lines))

    header = f"__Entry watch · {now:%H:%M} IST__"
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


def send_ping(message: str) -> bool:
    webhook = os.getenv(WEBHOOK_ENV, "").strip()
    if not webhook:
        print(f"{WEBHOOK_ENV} is not configured; skipping send.")
        return False
    try:
        response = requests.post(webhook, json={"content": message}, timeout=15)
        response.raise_for_status()
        return True
    except requests.RequestException as error:
        print(f"entry-confirm ping failed: {error}")
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


def sweep_extreme(price_info: dict, side: str) -> float:
    """The most favourable price reached recently, for stage detection.

    A long's entry is approached from above, so its favourable extreme is
    the recent low; a short's is the recent high. Classifying against this
    instead of only the live point-in-time price catches a stage the
    ticker's single snapshot would have missed between two polls - price
    touched the level and moved on before this run happened to look.
    Falls back to the live price when no sweep range was fetched (NSE).
    """
    key = "recent_low" if side == "long" else "recent_high"
    return float(price_info.get(key, price_info["price"]))


def _rank(stage: int | None) -> int:
    return -1 if stage is None else stage


def resolve_pings(
    record: dict, price_info: dict, state: dict, now: pd.Timestamp
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
    extreme = sweep_extreme(price_info, record.get("side", "long"))
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

    pings: list[tuple[int, str]] = []
    if stage is not None and stage > last_stage:
        ready_seen = ready_recently(state, record, now) or level_ready_recently(
            state, record, now
        )
        if last_stage == 0 and stage in (STAGE_ENTRY, STAGE_LATE) and not ready_seen:
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
    return ["30m", "4h"] if choice == "both" else [choice]


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
            watched.extend(load_watched_alerts(market, timeframe, now))

    if not watched:
        print("No alerts inside their entry window.")
        return

    state = load_state()
    # NSE has no sweep range (fetch_prices only ever returns a close), so it
    # is wrapped to the same {"price": ...} shape crypto's sweep-aware fetch
    # returns - sweep_extreme() falls back to "price" when the range is absent.
    nse_prices = fetch_prices(
        sorted({r["symbol"] for r in watched if r["_market"] == "nse"})
    )
    prices: dict[str, dict[str, float]] = {
        symbol: {"price": price} for symbol, price in nse_prices.items()
    }
    prices.update(
        fetch_crypto_prices(
            sorted({r["symbol"] for r in watched if r["_market"] == "crypto"})
        )
    )

    # One heads-up per symbol, not one per level. Widening the watch band to
    # 0.75% put several stacked zones on the same symbol in range at once and
    # each warned separately: 74 GET READYs came from 36 symbols across 70
    # zones in half a day, TSLA alone six times for four levels. That the
    # price is approaching TSLA is one piece of news however many boxes are
    # drawn near it. The same exact level also gets a six-hour budget, so
    # repeat scanner deliveries cannot keep saying GET READY. The zone is
    # still marked, so its ENTRY NOW - which names a specific level and is
    # worth having per zone - still fires when price arrives.
    pings: list[tuple[int, str]] = []
    for record in watched:
        price_info = prices.get(record["symbol"])
        if price_info is None:
            continue
        record_pings, _ = resolve_pings(record, price_info, state, now)
        pings.extend(record_pings)

    messages = build_digest(pings, now)
    if not messages:
        print("Nothing new to report.")
    for message in messages:
        if args.dry_run:
            print(message + "\n")
        elif not send_ping(message):
            # The digest did not land, so nothing in it may be marked sent.
            print("digest not delivered; stages left unmarked for the next run.")
            return

    state = prune_state(state, {watch_key(record) for record in watched})
    if not args.dry_run:
        save_state(state)


if __name__ == "__main__":
    main()
