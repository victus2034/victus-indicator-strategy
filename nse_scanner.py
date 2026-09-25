import argparse
import hashlib
from io import StringIO
import json
import os
from statistics import median
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

from nse_config import (
    ALERT_COOLDOWN_SECONDS,
    ALERT_SCAN_START,
    ALERT_RANGE_FILTER_SIGNALS,
    ATR_PERIOD,
    BOX_WIDTH,
    DISCORD_NSE_WEBHOOK_URL,
    DISCORD_STATUS_WEBHOOK_URL,
    DISCORD_WEBHOOK_URL,
    HISTORY_OF_ZONES_TO_KEEP,
    MARKET_CLOSE,
    MARKET_OPEN,
    MARKET_TIMEZONE,
    MAX_CONSECUTIVE_ZONE_TOUCHES,
    MIN_ZONE_AGE_CANDLES,
    MAX_DISTANCE_PCT,
    MIN_DISTANCE_PCT,
    MIN_SCAN_INTERVAL_SECONDS,
    NSE_INDEX_CSV_URL,
    NSE_MARKET_CAP_RANK,
    NSE_RANK_START,
    NSE_RANK_END,
    OHLCV_LIMIT,
    OVERLAP_ATR,
    PRINT_ALERTS_TO_CONSOLE,
    PRINT_SCAN_SUMMARY,
    REARM_FACTOR,
    STRATEGY_CUTOFF,
    SHOW_4H_ZONE_SCORES,
    SCAN_SLEEP,
    SIGNAL_ALERT_COOLDOWN_SECONDS,
    SOURCE_INTERVAL,
    SOURCE_PERIOD,
    SWING_LENGTH,
    TIMEFRAME,
    SHOW_ZONE_RATINGS,
    ZONE_RATING_BASE,
)
import scanner as zone_engine
from zone_scoring import score_wick_zone


STATE_FILE = Path(__file__).with_name("nse_alert_state.json")
ALERT_RECORD_FILE = Path(__file__).with_name("nse_alert_records.jsonl")
SL_BUFFER_PCT = 0.10
# Round-trip Dhan NSE equity intraday charges as a share of turnover, and
# the stop distance below which the +0.5R capital-protection rule stops
# working. Kept in step with daily_backtest_summary, which prices results
# net of the same figures.
ROUND_TRIP_COST_PCT = 0.1063
MIN_SAFE_STOP_PCT = 0.240
MARKET_DATA = {}
# Follows the alert cooldown, exactly as the crypto scanner's does (its own
# comment: a zone repeats no faster than it may alert). Was a flat hour, which
# is a quarter of the 4h cooldown and twice the 30m one.
ZONE_REPEAT_SUPPRESSION_SECONDS = int(
    os.getenv("VICTUS_ZONE_REPEAT_SUPPRESSION_SECONDS", "").strip() or ALERT_COOLDOWN_SECONDS
)
NSE_SECTOR_MAP = {}
NSE_SECTOR_BIAS_THRESHOLD_PCT = float(os.getenv("NSE_SECTOR_BIAS_THRESHOLD_PCT", "1.5"))
NSE_SECTOR_BUCKETS = (
    ("Financials", ("financial", "bank", "insurance", "capital market")),
    ("Materials", ("metal", "mining", "cement", "chemical", "fertilizer", "paper", "packaging", "materials")),
    ("Industrials", ("capital goods", "construction", "engineering", "industrial", "logistics", "transport", "infrastructure")),
    ("Healthcare", ("healthcare", "pharma", "pharmaceutical", "hospital", "diagnostic", "biotech")),
    # "services" was deliberately dropped here: it's a generic qualifier
    # that real industry labels append to a specific sector name (e.g.
    # "Telecom - Services", "IT - Services"), so it was pre-empting the
    # correct, more specific bucket (Technology & Telecom) below since
    # this bucket is checked first. "consumer" alone already covers
    # genuine consumer-services labels like "Consumer Services".
    ("Consumer", ("consumer", "fmcg", "retail", "textile", "media", "hotel", "food", "beverage", "durable")),
    ("Automobile", ("automobile", "auto", "automotive")),
    ("Energy & Utilities", ("oil", "gas", "power", "energy", "utility", "utilities", "electric", "renewable")),
    ("Technology & Telecom", ("information technology", "software", "telecom", "communication", "technology")),
    ("Real Estate", ("realty", "real estate")),
    ("Diversified", ("diversified",)),
)


def parse_hhmm(value):
    hour, minute = value.split(":", 1)
    return int(hour), int(minute)


def market_window_status(now=None):
    now = now or pd.Timestamp.now(tz=ZoneInfo(MARKET_TIMEZONE))
    scan_hour, scan_minute = parse_hhmm(ALERT_SCAN_START)
    cutoff_hour, cutoff_minute = parse_hhmm(STRATEGY_CUTOFF)
    market_open = now.replace(hour=scan_hour, minute=scan_minute, second=0, microsecond=0)
    market_close = now.replace(hour=cutoff_hour, minute=cutoff_minute, second=0, microsecond=0)
    holiday_text = os.getenv("NSE_HOLIDAYS", "")
    holidays = {item.strip() for item in holiday_text.split(",") if item.strip()}
    is_session = now.weekday() < 5 and now.date().isoformat() not in holidays
    return is_session and market_open <= now <= market_close, now, market_open, market_close


def has_current_session_data(watchlist, now=None):
    """Reject stale previous-session data before producing executable alerts.

    A single symbol failing to fetch (delisted ticker, transient API hiccup)
    must not blank the entire scan - only a majority-stale feed indicates a
    real systemic staleness problem worth skipping the whole run for.
    """
    now = now or pd.Timestamp.now(tz=ZoneInfo(MARKET_TIMEZONE))
    available = 0
    current = 0
    for symbol in watchlist:
        data = MARKET_DATA.get(symbol)
        if data is None or data.empty or "Datetime" not in data.columns:
            continue
        try:
            latest = _localized_datetimes(data).iloc[-1]
        except Exception:
            continue
        available += 1
        if latest.date() == now.date():
            current += 1
    if available == 0:
        return False
    return current / available >= 0.5


def load_state():
    if not STATE_FILE.exists():
        return {}

    try:
        with STATE_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state):
    with STATE_FILE.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)


def record_delivered_zone_alert(result, zone_type, zone, distance_pct, message, now_ts):
    """Persist only alerts confirmed as delivered to Discord.

    This log is the source of truth for the later outcome evaluator. It is
    append-only so a scanner state rewrite cannot erase delivery history.
    """
    score = result.get(f"{zone_type}_score")
    if score is None and SHOW_ZONE_RATINGS and TIMEFRAME == "30m":
        score = zone_rating(zone, distance_pct)

    record = {
        "delivered_at_utc": pd.Timestamp.fromtimestamp(now_ts, tz="UTC").isoformat(),
        "symbol": result["symbol"],
        "timeframe": TIMEFRAME,
        "side": "short" if zone_type == "supply" else "long",
        "zone_type": zone_type,
        "distance_pct": float(distance_pct),
        "alert_price": float(result["price"]),
        "level": float(zone["top"] if zone_type == "supply" else zone["bottom"]),
        "zone_bottom": float(zone["bottom"]),
        "zone_top": float(zone["top"]),
        "body_entry": zone.get("body_entry"),
        "planned_entry": planned_entry_price(zone_type, zone),
        "stop_price": planned_stop_price(zone_type, zone),
        "stop_distance_pct": planned_stop_distance_pct(zone_type, zone),
        "stop_too_tight": stop_is_too_tight(planned_stop_distance_pct(zone_type, zone)),
        "score": score,
        # Raw score_wick_zone inputs, logged so a future validation pass can
        # tell which criterion actually predicts outcomes instead of only
        # seeing the capped 4-10 total (see rating_validation_report.py).
        "wick_to_body": zone.get("wick_to_body"),
        "wick_atr": zone.get("wick_atr"),
        "departure_atr": zone.get("departure_atr"),
        "touch_count": zone.get("touch_count"),
        "zone_age_candles": zone.get("zone_age_candles"),
        "message": message,
    }
    record["trade_id"] = delivered_alert_id(record)
    try:
        with ALERT_RECORD_FILE.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError as error:
        # Delivery already succeeded; surface the audit-log problem without
        # turning a valid Discord alert into a scanner failure.
        print(f"Alert record write failed: {error}")


def get_env_or_config(env_name, config_value):
    value = os.getenv(env_name, "").strip()
    return value if value else config_value


def normalize_nse_symbol(symbol):
    text = str(symbol).strip().upper()
    return text if text.endswith(".NS") else f"{text}.NS"


def classify_nse_sector(raw_industry):
    text = str(raw_industry or "").strip().lower()
    for sector, keywords in NSE_SECTOR_BUCKETS:
        if any(keyword in text for keyword in keywords):
            return sector
    return "Unclassified"


def build_sector_map_from_constituents(csv):
    symbol_column = "Symbol"
    industry_column = next(
        (
            column
            for column in csv.columns
            if str(column).strip().lower() in {"industry", "sector", "macro-economic sector", "basic industry"}
        ),
        None,
    )
    if symbol_column not in csv.columns or industry_column is None:
        return {}

    sector_map = {}
    for _, row in csv[[symbol_column, industry_column]].dropna(subset=[symbol_column]).iterrows():
        sector_map[normalize_nse_symbol(row[symbol_column])] = classify_nse_sector(row.get(industry_column))
    return sector_map


def load_watchlist():
    global NSE_SECTOR_MAP
    try:
        response = requests.get(
            NSE_INDEX_CSV_URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        response.raise_for_status()
        csv = pd.read_csv(StringIO(response.text))
        if "Symbol" not in csv.columns:
            raise RuntimeError("NSE index CSV did not include Symbol column")

        symbols = [normalize_nse_symbol(symbol) for symbol in csv["Symbol"].dropna()]
        symbols = list(dict.fromkeys(symbols))
        if len(symbols) < 50:
            raise RuntimeError(f"NSE index CSV returned only {len(symbols)} symbols")
        NSE_SECTOR_MAP = build_sector_map_from_constituents(csv)
        # The CSV lists constituents alphabetically by company name, not by size,
        # so sort against the market-cap ranking before slicing the window -
        # otherwise the cut is "first N alphabetically", not "rank N-M by market cap".
        # A symbol not in the ranking (listed since it was captured) sorts last.
        rank_index = {symbol: i for i, symbol in enumerate(NSE_MARKET_CAP_RANK)}
        symbols.sort(key=lambda symbol: rank_index.get(symbol, len(NSE_MARKET_CAP_RANK)))
        return symbols[NSE_RANK_START:NSE_RANK_END]
    except Exception as error:
        print(f"Using fallback NSE watchlist because index CSV failed: {error}")
        # FALLBACK_WATCHLIST only covers rank ~1-100 - returning it directly
        # here used to be fine when the live path also took the top of the
        # list, but now the live path deliberately SKIPS rank 1-100 for
        # rank 101-300. Returning FALLBACK_WATCHLIST unsliced on a CSV outage
        # would silently scan exactly the top-100 names the live path exists
        # to exclude. NSE_MARKET_CAP_RANK already runs to rank 399, so slice
        # it the same way the live path does instead of falling back to a
        # differently-scoped list.
        symbols = NSE_MARKET_CAP_RANK[NSE_RANK_START:NSE_RANK_END]
        NSE_SECTOR_MAP = {symbol: "Unclassified" for symbol in symbols}
        return symbols


# --- Zone engine -------------------------------------------------------------
# NSE does not build zones itself. It uses the crypto scanner's engine - the one
# tests/test_indicator_scanner_parity.py holds to Shiva_Indicator_v7.pine and
# tests/test_six_worked_examples.py holds to six hand-measured charts. NSE used
# to keep a private copy of these nine functions: a fixed ATR band, a plain
# "drop the oldest" buffer, an age counted from creation, a close-through break.
# When crypto moved to the v7 wick rules the copy stayed behind, and the two
# markets quietly ran different strategies. These are aliases, not wrappers:
# `nse_scanner.build_zones is scanner.build_zones`, and a test says so.
atr = zone_engine.atr
find_pivots = zone_engine.find_pivots
zone_center = zone_engine.zone_center
add_zone_if_not_overlapping = zone_engine.add_zone_if_not_overlapping
record_zone_touch = zone_engine.record_zone_touch
qualify_wick_zone = zone_engine.qualify_wick_zone
build_zones = zone_engine.build_zones
too_young_to_alert = zone_engine.too_young_to_alert
nearest_active_zone = zone_engine.nearest_active_zone


def bind_zone_engine(timeframe=None):
    """Point the shared engine at this scanner's timeframe; returns the base.

    The engine reads exactly one timeframe-dependent number, ZONE_BASE_EXTRA -
    how many bars either side of a pivot form its base (5 on 30m, 1 on 4h). The
    crypto scanner fixes it at import from VICTUS_TIMEFRAME, but NSE chooses its
    timeframe afterwards (nse_scanner_30m patches it in), so it is set here,
    when NSE actually scans, rather than at import - which would reach into the
    crypto engine of every process that merely imports this module. An explicit
    VICTUS_ZONE_BASE_EXTRA still wins, as it does for crypto.
    """
    from config import TIMEFRAME_MINUTES, auto_base_extra

    override = os.getenv("VICTUS_ZONE_BASE_EXTRA", "").strip()
    if override:
        zone_engine.ZONE_BASE_EXTRA = int(override)
    else:
        minutes = TIMEFRAME_MINUTES.get(str(timeframe or TIMEFRAME).strip().lower())
        zone_engine.ZONE_BASE_EXTRA = auto_base_extra(minutes)
    return zone_engine.ZONE_BASE_EXTRA


def get_range_filter_signals(df):
    src = df["close"]
    period = 100
    multiplier = 3.0

    def smoothrng(series, length, mult):
        weighted_period = length * 2 - 1
        average_range = series.diff().abs().ewm(span=length, adjust=False).mean()
        return average_range.ewm(span=weighted_period, adjust=False).mean() * mult

    smooth_range = smoothrng(src, period, multiplier)
    filt = src.copy()
    filt.iloc[0] = src.iloc[0]
    upward = 0.0
    downward = 0.0
    condition_state = 0
    buy_signal = False
    sell_signal = False

    for index in range(1, len(src)):
        previous = filt.iloc[index - 1]
        price = src.iloc[index]
        range_value = smooth_range.iloc[index] if not pd.isna(smooth_range.iloc[index]) else 0

        if price > previous:
            filt.iloc[index] = previous if price - range_value < previous else price - range_value
        else:
            filt.iloc[index] = previous if price + range_value > previous else price + range_value

        if filt.iloc[index] > filt.iloc[index - 1]:
            upward += 1
        elif filt.iloc[index] < filt.iloc[index - 1]:
            upward = 0

        if filt.iloc[index] < filt.iloc[index - 1]:
            downward += 1
        elif filt.iloc[index] > filt.iloc[index - 1]:
            downward = 0

        long_condition = (
            (src.iloc[index] > filt.iloc[index] and src.iloc[index] > src.iloc[index - 1] and upward > 0)
            or (src.iloc[index] > filt.iloc[index] and src.iloc[index] < src.iloc[index - 1] and upward > 0)
        )
        short_condition = (
            (src.iloc[index] < filt.iloc[index] and src.iloc[index] < src.iloc[index - 1] and downward > 0)
            or (src.iloc[index] < filt.iloc[index] and src.iloc[index] > src.iloc[index - 1] and downward > 0)
        )

        previous_state = condition_state
        if long_condition:
            condition_state = 1
        elif short_condition:
            condition_state = -1

        buy_signal = long_condition and previous_state == -1
        sell_signal = short_condition and previous_state == 1

    return buy_signal, sell_signal


def normalize_yfinance_columns(data):
    if not isinstance(data.columns, pd.MultiIndex):
        return {None: data}

    tickers = set(data.columns.get_level_values(1))
    if tickers and all(str(ticker).endswith(".NS") for ticker in tickers):
        return {ticker: data.xs(ticker, axis=1, level=1, drop_level=True) for ticker in tickers}

    tickers = set(data.columns.get_level_values(0))
    return {ticker: data.xs(ticker, axis=1, level=0, drop_level=True) for ticker in tickers}


def yfinance_time_range(now=None):
    if SOURCE_INTERVAL != "1h":
        return {"period": SOURCE_PERIOD}

    # Yahoo can ignore an intraday period for newer listings and request from
    # the IPO date, which its API rejects when that date is over 730 days old.
    end = now or (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1))
    start = end - pd.Timedelta(days=700)
    return {"start": start.to_pydatetime(), "end": end.to_pydatetime()}


def resample_for_timeframe(data):
    if TIMEFRAME == "30m" and SOURCE_INTERVAL == "15m":
        return data.resample("30min", origin="start_day", offset="15min").agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        ).dropna()

    if TIMEFRAME == "4h":
        # Anchor four-hour candles to the NSE open (09:15), not 08:15.
        return data.resample("4h", origin="start_day", offset="1h15min").agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        ).dropna()

    return data


def confirmed_candles(data, now=None):
    if data.empty or "Datetime" not in data.columns:
        return data

    durations = {"30m": pd.Timedelta(minutes=30), "4h": pd.Timedelta(hours=4)}
    duration = durations.get(TIMEFRAME)
    if duration is None:
        return data

    candle_start = pd.Timestamp(data["Datetime"].iloc[-1])
    timezone = candle_start.tz
    now = now or pd.Timestamp.now(tz=timezone)
    close_hour, close_minute = parse_hhmm(MARKET_CLOSE)
    session_close = candle_start.replace(hour=close_hour, minute=close_minute, second=0, microsecond=0)
    candle_close = min(candle_start + duration, session_close)

    if now < candle_close:
        return data.iloc[:-1].copy()
    return data


def prepare_ohlcv(data):
    if data.empty:
        raise RuntimeError("empty candle data")

    data = data.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    data = data[["open", "high", "low", "close", "volume"]].dropna()

    data = resample_for_timeframe(data)

    if len(data) < ATR_PERIOD + SWING_LENGTH * 2:
        raise RuntimeError(f"not enough candles after resample: {len(data)}")

    return data.tail(OHLCV_LIMIT).reset_index()


def fetch_market_data(watchlist):
    global MARKET_DATA
    MARKET_DATA = {}
    chunk_size = 50

    for start in range(0, len(watchlist), chunk_size):
        chunk = watchlist[start:start + chunk_size]
        try:
            raw = yf.download(
                tickers=" ".join(chunk),
                interval=SOURCE_INTERVAL,
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="column",
                **yfinance_time_range(),
            )
        except Exception as error:
            print(f"chunk starting at {chunk[0]} -> yf.download failed: {error}")
            continue
        grouped = normalize_yfinance_columns(raw)

        if None in grouped and len(chunk) == 1:
            grouped = {chunk[0]: grouped[None]}

        for symbol in chunk:
            symbol_data = grouped.get(symbol)
            if symbol_data is None or symbol_data.empty:
                continue

            try:
                MARKET_DATA[symbol] = prepare_ohlcv(symbol_data)
            except Exception as error:
                print(f"{symbol} -> data preparation failed: {error}")


def fetch_stock_ohlcv(symbol):
    cached = MARKET_DATA.get(symbol)
    if cached is not None:
        return cached

    data = yf.download(
        symbol,
        interval=SOURCE_INTERVAL,
        auto_adjust=False,
        progress=False,
        threads=False,
        **yfinance_time_range(),
    )
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    return prepare_ohlcv(data)


def _localized_datetimes(df):
    datetimes = pd.to_datetime(df["Datetime"])
    if getattr(datetimes.dt, "tz", None) is None:
        return datetimes.dt.tz_localize(MARKET_TIMEZONE)
    return datetimes.dt.tz_convert(MARKET_TIMEZONE)


def stock_session_move_pct(df):
    if df is None or df.empty or "Datetime" not in df.columns or len(df) < 2:
        return None

    try:
        localized = _localized_datetimes(df)
        latest_date = localized.iloc[-1].date()
        same_session = df.loc[localized.dt.date == latest_date]
        if same_session.empty:
            return None

        base = float(same_session["open"].iloc[0])
        latest = float(df["close"].iloc[-1])
        if base <= 0:
            return None
        return (latest - base) / base * 100.0
    except Exception:
        return None


def build_sector_context(watchlist):
    grouped_moves = {}
    for symbol in watchlist:
        sector = NSE_SECTOR_MAP.get(symbol, "Unclassified")
        move = stock_session_move_pct(MARKET_DATA.get(symbol))
        if move is None:
            continue
        grouped_moves.setdefault(sector, []).append(move)

    return {
        sector: {
            "session_pct": median(moves),
            "members": len(moves),
        }
        for sector, moves in grouped_moves.items()
    }


def attach_sector_context(result, sector_context):
    sector = NSE_SECTOR_MAP.get(result["symbol"], "Unclassified")
    context = sector_context.get(sector)
    result["sector"] = sector
    result["sector_session_pct"] = context["session_pct"] if context else None
    result["sector_member_count"] = context["members"] if context else 0
    return result


def sector_bias_line(result, zone_type):
    sector = result.get("sector")
    move = result.get("sector_session_pct")
    if not sector or move is None:
        return None

    if abs(move) < NSE_SECTOR_BIAS_THRESHOLD_PCT:
        label = "OK"
    else:
        wants_up = zone_type == "demand"
        supports_trade = move > 0 if wants_up else move < 0
        label = "Good" if supports_trade else "Risk"

    return f"{sector}: {move:+.2f}% | {label}"


def sector_coverage_summary(watchlist):
    counts = {}
    for symbol in watchlist:
        sector = NSE_SECTOR_MAP.get(symbol, "Unclassified")
        counts[sector] = counts.get(sector, 0) + 1
    return ", ".join(f"{sector}: {counts[sector]}" for sector in sorted(counts))


def scan_symbol(symbol):
    bind_zone_engine()
    df = fetch_stock_ohlcv(symbol)
    price = float(df["close"].iloc[-1])
    if len(df) < ATR_PERIOD + SWING_LENGTH * 2:
        raise RuntimeError(f"not enough candles: {len(df)}")

    # Zones are built on EVERY candle, the one still forming included - exactly
    # as the crypto scanner does and as the chart draws them. Pine evaluates the
    # forming bar on every tick, so a wick through a zone's far edge kills it the
    # moment it happens, and a pivot's tenth following bar can be the forming
    # one. This used to build on confirmed candles only and then kill zones on
    # the last CLOSE, which misses a wick that pokes through and pulls back.
    #
    # A half-finished candle cannot kill a zone the finished one would not: its
    # range sits inside the full candle's. Replayed over 700 mid-bar snapshots
    # of 20 real stocks (19,804 zone comparisons) there were no false kills.
    # The engine's own wick rule does the killing, so the separate close-based
    # pass that used to follow build_zones is gone.
    supply_zones, demand_zones = build_zones(df)
    latest_index = len(df) - 1
    nearest_supply, supply_dist = nearest_active_zone(price, supply_zones, "supply", latest_index)
    nearest_demand, demand_dist = nearest_active_zone(price, demand_zones, "demand", latest_index)
    # The range-filter signal is a different animal: unlike a zone it can appear
    # on the forming bar and be gone by the close, so it stays on confirmed
    # candles rather than alerting on something that may not survive the bar.
    indicator_df = confirmed_candles(df)
    buy_signal, sell_signal = get_range_filter_signals(indicator_df)
    supply_score = None
    demand_score = None
    should_score_zones = (SHOW_4H_ZONE_SCORES and TIMEFRAME == "4h") or (
        SHOW_ZONE_RATINGS and TIMEFRAME == "30m"
    )
    if should_score_zones:
        supply_score = score_wick_zone(
            nearest_supply, supply_dist, MIN_DISTANCE_PCT, MAX_DISTANCE_PCT
        )
        demand_score = score_wick_zone(
            nearest_demand, demand_dist, MIN_DISTANCE_PCT, MAX_DISTANCE_PCT
        )

    return {
        "symbol": symbol,
        "price": price,
        "supply": nearest_supply,
        "supply_dist": supply_dist,
        "supply_score": supply_score,
        "demand": nearest_demand,
        "demand_dist": demand_dist,
        "demand_score": demand_score,
        "buy_signal": buy_signal,
        "sell_signal": sell_signal,
    }


def build_state_key(symbol, zone_type, zone):
    return f"{symbol}|{zone_type}|{zone['bottom']:.4f}|{zone['top']:.4f}"


def build_signal_state_key(symbol, signal_type):
    return f"{symbol}|range_filter|{signal_type}"


def display_symbol(symbol):
    text = str(symbol).strip().upper()
    if text.endswith(".NS"):
        return text[:-3]
    return text


def planned_entry_price(zone_type, zone):
    """Use the near/body edge as the practical planned entry."""
    return float(zone["top"] if zone_type == "demand" else zone["bottom"])


def planned_stop_price(zone_type, zone, buffer_pct=SL_BUFFER_PCT):
    """Place SL beyond the far zone edge with a small fixed buffer."""
    if zone_type == "demand":
        return float(zone["bottom"]) * (1 - buffer_pct / 100.0)
    return float(zone["top"]) * (1 + buffer_pct / 100.0)


def planned_stop_distance_pct(zone_type, zone, buffer_pct=SL_BUFFER_PCT):
    entry = planned_entry_price(zone_type, zone)
    if entry == 0:
        return 0.0
    stop = planned_stop_price(zone_type, zone, buffer_pct)
    return abs(entry - stop) / abs(entry) * 100.0


def delivered_alert_id(record):
    """Stable ID carried from alert log into daily/weekly backtest summaries."""
    parts = [
        str(record.get("symbol", "")).upper(),
        str(record.get("timeframe", "")),
        str(record.get("side", "")),
        f"{float(record.get('zone_bottom', 0.0)):.10f}",
        f"{float(record.get('zone_top', 0.0)):.10f}",
        str(record.get("delivered_at_utc", "")),
    ]
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def stop_is_too_tight(stop_distance_pct):
    """True when +0.5R arrives before the trade is even net positive.

    Reaching +0.5R only moves price half the stop distance. If that is
    less than the round-trip cost cushion, moving the stop up at +0.5R
    still locks in a loss, so the capital-protection rule cannot work on
    this setup at all.
    """
    return float(stop_distance_pct) < MIN_SAFE_STOP_PCT


def format_alert(result, zone_type, zone, distance_pct):
    side = "SELL" if zone_type == "supply" else "BUY"
    score = result.get(f"{zone_type}_score")
    score_text = ""
    if score is not None:
        score_text = f" | {score}/10"
    elif SHOW_ZONE_RATINGS and TIMEFRAME == "30m":
        score_text = f" | {zone_rating(zone, distance_pct)}/10"
    stop = planned_stop_price(zone_type, zone)
    stop_distance = planned_stop_distance_pct(zone_type, zone)
    lines = [
        f"{display_symbol(result['symbol'])} | {side}{score_text}\n"
        f"Price: {result['price']:.2f} | {distance_pct:.2f}%\n"
        f"Zone: {zone['bottom']:.2f} - {zone['top']:.2f}\n"
        f"SL: {stop:.2f} | {stop_distance:.2f}%"
    ]
    if stop_is_too_tight(stop_distance):
        lines.append(
            f"WARNING SL under {MIN_SAFE_STOP_PCT:.2f}% - at +0.5R the move "
            f"is only {stop_distance / 2:.3f}%, under the {ROUND_TRIP_COST_PCT:.4f}% "
            f"round trip, so moving the stop up cannot protect capital here"
        )
    bias = sector_bias_line(result, zone_type)
    if bias:
        lines.append(bias)
    return "\n".join(lines)


def zone_rating(zone, distance_pct):
    """Return a transparent display score, not a validated predictor."""
    score = ZONE_RATING_BASE
    midpoint = (MIN_DISTANCE_PCT + MAX_DISTANCE_PCT) / 2
    if distance_pct <= midpoint:
        score += 1
    if zone.get("max_touch_streak", 0) == 0:
        score += 1
    return min(10, score)


def format_signal_alert(result, signal_type):
    label = "BUY" if signal_type == "buy" else "SELL"

    def display_distance(zone_key, distance_key):
        if result.get(zone_key) is None or result.get(distance_key, 999.0) >= 999.0:
            return "N/A"
        return f"{result[distance_key]:.2f}%"

    return (
        f"{display_symbol(result['symbol'])} Range Filter {label} signal\n"
        f"Price: {result['price']:.2f}\n"
        f"Nearest Demand Distance: {display_distance('demand', 'demand_dist')}\n"
        f"Nearest Supply Distance: {display_distance('supply', 'supply_dist')}"
    )


def send_discord_message(message, webhook_env_name="DISCORD_WEBHOOK_URL", webhook_config_value=DISCORD_WEBHOOK_URL):
    webhook_url = get_env_or_config(webhook_env_name, webhook_config_value)
    if not webhook_url:
        raise RuntimeError(f"{webhook_env_name} is not configured")

    for attempt in range(6):
        response = requests.post(webhook_url, json={"content": message}, timeout=15)
        if response.status_code != 429:
            response.raise_for_status()
            return

        try:
            retry_after = float(response.json().get("retry_after", 1.0))
        except (TypeError, ValueError, requests.JSONDecodeError):
            retry_after = 1.0

        if attempt == 5:
            response.raise_for_status()

        time.sleep(max(0.25, min(retry_after, 30.0)))


def send_alert(message):
    if PRINT_ALERTS_TO_CONSOLE:
        print("\n" + "=" * 80)
        print(message)
        print("=" * 80)

    try:
        if get_env_or_config("DISCORD_NSE_WEBHOOK_URL", DISCORD_NSE_WEBHOOK_URL):
            send_discord_message(
                message,
                webhook_env_name="DISCORD_NSE_WEBHOOK_URL",
                webhook_config_value=DISCORD_NSE_WEBHOOK_URL,
            )
        else:
            send_discord_message(message)
        return True
    except (RuntimeError, requests.RequestException) as error:
        print(f"Discord alert failed: {error}")
        return False


def send_status_message(message):
    print(message)

    try:
        status_webhook = get_env_or_config("DISCORD_STATUS_WEBHOOK_URL", DISCORD_STATUS_WEBHOOK_URL)
        alert_webhook = get_env_or_config("DISCORD_WEBHOOK_URL", DISCORD_WEBHOOK_URL)

        if status_webhook:
            send_discord_message(
                message,
                webhook_env_name="DISCORD_STATUS_WEBHOOK_URL",
                webhook_config_value=DISCORD_STATUS_WEBHOOK_URL,
            )
        elif alert_webhook:
            send_discord_message("NSE STATUS WEBHOOK MISSING - sending status to alert channel.\n\n" + message)
    except requests.RequestException as error:
        print(f"Discord status message failed: {error}")


def stop_too_wide(zone_type, zone):
    """True when the planned stop is further than MAX_ALERT_STOP_PCT from entry.

    The crypto scanner's rule, applied here too so both markets send the same
    alerts from the same zones. It reads the crypto scanner's limit rather than
    a second copy of the number.
    """
    limit = zone_engine.MAX_ALERT_STOP_PCT
    if limit <= 0:
        return False
    return planned_stop_distance_pct(zone_type, zone) > limit


def process_candidate(state, result, zone_type, zone, distance_pct, now_ts):
    if zone is None:
        return None

    if stop_too_wide(zone_type, zone):
        return None

    state_key = build_state_key(result["symbol"], zone_type, zone)
    entry = state.setdefault(
        state_key,
        {"in_zone": False, "last_alert_at": 0.0, "last_attempt_at": 0.0},
    )
    noise_state = state.setdefault("_noise_control", {})
    noise_key = exact_zone_identity(result["symbol"], zone_type, zone)
    alert_sent = None

    if MIN_DISTANCE_PCT <= distance_pct <= MAX_DISTANCE_PCT:
        last_attempt_at = max(entry.get("last_alert_at", 0.0), entry.get("last_attempt_at", 0.0))
        should_alert = (not entry["in_zone"]) or (now_ts - last_attempt_at >= ALERT_COOLDOWN_SECONDS)
        last_success = float(noise_state.get(noise_key, 0.0) or 0.0)
        noise_open = not last_success or now_ts - last_success >= ZONE_REPEAT_SUPPRESSION_SECONDS
        if should_alert and noise_open:
            entry["last_attempt_at"] = now_ts
            message = format_alert(result, zone_type, zone, distance_pct)
            alert_sent = send_alert(message)
            if alert_sent:
                entry["last_alert_at"] = now_ts
                noise_state[noise_key] = now_ts
                record_delivered_zone_alert(
                    result, zone_type, zone, distance_pct, message, now_ts
                )
        elif should_alert and last_success:
            remaining = max(0, int(ZONE_REPEAT_SUPPRESSION_SECONDS - (now_ts - last_success)))
            print(f"Suppressed repeat alert: {noise_key} | {remaining // 60}m remaining")
        entry["in_zone"] = True
    # Keep the successful-delivery timestamp through a zone touch.  A touch
    # must not re-arm the same zone before the suppression window expires.
    elif distance_pct > MAX_DISTANCE_PCT * REARM_FACTOR:
        entry["in_zone"] = False

    return alert_sent


def exact_zone_identity(symbol, zone_type, zone):
    """Identify a zone across scans, so a repeat can be recognised.

    Ten decimals made this unique per scan rather than per zone. A zone's
    edges drift in the far decimals as ATR moves with each new candle -
    one BANKINDIA level came through as 141.1720310348 and then
    141.1721010741 - so every delivery minted a fresh key, the repeat
    suppression below never matched, and the same zone alerted every
    twenty minutes for hours. Six significant figures is far finer than
    any real zone is wide and far coarser than the drift.
    """
    side = "long" if zone_type == "demand" else "short"
    return (
        f"{str(symbol).upper()}|{TIMEFRAME}|{side}|"
        f"{float(zone['bottom']):.6g}|{float(zone['top']):.6g}"
    )


def process_signal_candidate(state, result, signal_type, now_ts):
    if not ALERT_RANGE_FILTER_SIGNALS:
        return None

    # A range-filter signal is useful only as confirmation of a nearby,
    # directionally relevant zone. Do not send standalone signals for distant
    # zones or for missing distances (which previously produced N/A alerts).
    if signal_type == "buy":
        zone = result.get("demand")
        distance_pct = result.get("demand_dist", 999.0)
    else:
        zone = result.get("supply")
        distance_pct = result.get("supply_dist", 999.0)

    if zone is None or not (MIN_DISTANCE_PCT <= distance_pct <= MAX_DISTANCE_PCT):
        return None

    signal_active = result["buy_signal"] if signal_type == "buy" else result["sell_signal"]
    if not signal_active:
        return None

    state_key = build_signal_state_key(result["symbol"], signal_type)
    entry = state.setdefault(state_key, {"last_alert_at": 0.0, "last_attempt_at": 0.0})
    last_attempt_at = max(entry.get("last_alert_at", 0.0), entry.get("last_attempt_at", 0.0))
    if now_ts - last_attempt_at < SIGNAL_ALERT_COOLDOWN_SECONDS:
        return None

    entry["last_attempt_at"] = now_ts
    alert_sent = send_alert(format_signal_alert(result, signal_type))
    if alert_sent:
        entry["last_alert_at"] = now_ts
    return alert_sent


def print_summary(results):
    ranked = sorted(results, key=lambda item: min(item["supply_dist"], item["demand_dist"]))
    print("\n" + "=" * 80)
    print(f"VICTUS NSE SCAN - {TIMEFRAME}")
    print("=" * 80)

    for index, result in enumerate(ranked, start=1):
        closest = min(result["supply_dist"], result["demand_dist"])
        bias = "BUY" if result["demand_dist"] < result["supply_dist"] else "SELL"
        print(f"\n{index}. {result['symbol']} | Closest {closest:.2f}% | Bias {bias}")
        print(f"Price: {result['price']:.2f}")

        if result["supply"]:
            print(
                "Supply: "
                f"{result['supply']['bottom']:.2f} - {result['supply']['top']:.2f} "
                f"({result['supply_dist']:.2f}%)"
            )
        else:
            print("Supply: none")

        if result["demand"]:
            print(
                "Demand: "
                f"{result['demand']['bottom']:.2f} - {result['demand']['top']:.2f} "
                f"({result['demand_dist']:.2f}%)"
            )
        else:
            print("Demand: none")

        print(f"Buy Signal: {result['buy_signal']}")
        print(f"Sell Signal: {result['sell_signal']}")


LAST_SCAN_KEY = "__last_scan_started__"


def scan_too_soon(state, now=None):
    """True when the previous scan of this timeframe is still recent."""
    if MIN_SCAN_INTERVAL_SECONDS <= 0:
        return False
    previous = (state.get(LAST_SCAN_KEY) or {}).get(TIMEFRAME)
    if previous is None:
        return False
    elapsed = (now if now is not None else time.time()) - float(previous)
    return 0 <= elapsed < MIN_SCAN_INTERVAL_SECONDS


def mark_scan_started(state, now=None):
    stamps = state.setdefault(LAST_SCAN_KEY, {})
    stamps[TIMEFRAME] = now if now is not None else time.time()


def run_scan_once(state):
    if scan_too_soon(state):
        print(
            f"A {TIMEFRAME} scan already ran within the last "
            f"{MIN_SCAN_INTERVAL_SECONDS // 60} minutes; standing down."
        )
        return

    mark_scan_started(state)
    save_state(state)

    watchlist = load_watchlist()
    results = []
    failures = []
    alerts_sent = 0
    alert_delivery_failures = 0
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    run_number = os.getenv("GITHUB_RUN_NUMBER", "local")
    trigger = os.getenv("GITHUB_EVENT_NAME", "local")
    is_market_open, market_now, market_open, market_close = market_window_status()

    if not is_market_open:
        send_status_message(
            f"Victus NSE scanner skipped - market closed\n"
            f"Time: {market_now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            f"Run: {run_number}\n"
            f"Trigger: {trigger}\n"
            f"Market window: {market_open.strftime('%H:%M')} - {market_close.strftime('%H:%M')} IST"
        )
        return

    trade_start_hour, trade_start_minute = parse_hhmm(MARKET_OPEN)
    trade_start = market_now.replace(
        hour=trade_start_hour,
        minute=trade_start_minute,
        second=0,
        microsecond=0,
    )
    if market_now < trade_start:
        send_status_message(
            "Victus NSE scanner context-only pre-open update\n"
            f"Time: {market_now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            "Reference Price: Previous Close\n"
            "Executable alerts begin at 09:15 IST."
        )
        return

    send_status_message(
        f"Victus NSE scanner started\n"
        f"Time: {started_at}\n"
        f"Run: {run_number}\n"
        f"Trigger: {trigger}\n"
        f"Timeframe: {TIMEFRAME}\n"
        f"Watchlist: {len(watchlist)} symbols\n"
        f"Sectors: {sector_coverage_summary(watchlist)}"
    )

    fetch_market_data(watchlist)
    if not has_current_session_data(watchlist, market_now):
        send_status_message(
            "Victus NSE scanner skipped - stale or incomplete session data\n"
            f"Time: {market_now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            "Reference Price: Previous Close\n"
            "No executable alerts were generated."
        )
        return
    sector_context = build_sector_context(watchlist)
    scanned_by_symbol = {}
    for symbol in watchlist:
        try:
            scanned_by_symbol[symbol] = attach_sector_context(scan_symbol(symbol), sector_context)
        except Exception as error:
            error_message = f"{symbol} -> {error}"
            failures.append(error_message)
            print(error_message)

    for symbol in watchlist:
        result = scanned_by_symbol.get(symbol)
        if result is None:
            continue

        results.append(result)
        now_ts = time.time()
        alert_results = [
            process_signal_candidate(state, result, "buy", now_ts),
            process_signal_candidate(state, result, "sell", now_ts),
            process_candidate(state, result, "supply", result["supply"], result["supply_dist"], now_ts),
            process_candidate(state, result, "demand", result["demand"], result["demand_dist"], now_ts),
        ]
        alerts_sent += sum(1 for alert_result in alert_results if alert_result is True)
        alert_delivery_failures += sum(1 for alert_result in alert_results if alert_result is False)

    save_state(state)

    if PRINT_SCAN_SUMMARY and results:
        print_summary(results)

    finished_at = time.strftime("%Y-%m-%d %H:%M:%S")
    status = "OK" if not failures else "WARN"
    message = (
        f"Victus NSE scanner finished ({status})\n"
        f"Time: {finished_at}\n"
        f"Run: {run_number}\n"
        f"Trigger: {trigger}\n"
        f"Scanned: {len(results)}/{len(watchlist)} symbols\n"
        f"Alerts sent: {alerts_sent}\n"
        f"Alert delivery failures: {alert_delivery_failures}\n"
        f"Failures: {len(failures)}"
    )
    if failures:
        message += "\n" + "\n".join(failures[:5])

    send_status_message(message)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Scan NSE stocks for nearby Victus levels.")
    parser.add_argument("--once", action="store_true", help="Run a single scan and exit.")
    return parser.parse_args(argv)


def main():
    args = parse_args()
    state = load_state()

    if args.once:
        run_scan_once(state)
        return

    while True:
        run_scan_once(state)
        print("\n" + "=" * 80)
        print(f"Waiting {SCAN_SLEEP} seconds...")
        print("=" * 80)
        time.sleep(SCAN_SLEEP)


if __name__ == "__main__":
    main()
