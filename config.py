import math
import os
from datetime import time as datetime_time


def env_int(name, default):
    value = os.getenv(name, "").strip()
    try:
        return int(value) if value else default
    except ValueError:
        return default


def env_float(name, default):
    value = os.getenv(name, "").strip()
    try:
        return float(value) if value else default
    except ValueError:
        return default


def env_flag(name, default=False):
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


# Cut to the Delta contracts worth scanning, 2026-09-01. The watchlist had
# grown to 119 scanned symbols, 30% of which traded under $50,000 a day on
# Delta - a zone drawn on a book that thin is a level nobody can be filled
# in. Ranked every Delta perpetual by seven-day traded value (a single
# session misranks badly: TAC printed 6% of its weekly average that day)
# and kept the 31 that earn the scan.
#
# Every symbol not listed on Delta India came out on 2026-09-15, when Shiva
# stopped trading anywhere else; what is left is DELTA_LISTED_SYMBOLS's crypto half.
CRYPTO_WATCHLIST = [
    # 2026-10-16 (lakky): kept only coins averaging >= 100M USDT a day over
    # BOTH the last 7 and the last 30 days on CoinDCX or Delta, with a Bitunix
    # perp (research/volume_7d_30d_probe.py, part volume; research/out/volume/).
    # Removed 19: BCH, AKE, ARB, LTC, TRUMP, INJ, APT, MAGIC, GTC, ZRO, TIA,
    # OGN, W, S, BAT, CAP, RSR, CT, DOS. Added RLC. Delta alone passes only
    # BTC, ETH and SOL; CoinDCX decides the rest.
    "BTCUSD",
    "ETHUSD",
    "ZECUSD",
    "SOLUSD",
    "XRPUSD",
    "NEARUSD",
    "HYPEUSD",
    "DOGEUSD",
    "QNTUSD",
    "SUIUSD",
    "UNIUSD",
    "BNBUSD",
    "ENAUSD",
    "1000PEPEUSD",
    "WLDUSD",
    "ADAUSD",
    "AVAXUSD",
    "LINKUSD",
    "ONDOUSD",
    "TAOUSD",
    "STRKUSD",
    "BTWUSD",
    "FILUSD",
    "AAVEUSD",
    "RLCUSD",
]

# Crypto Bitunix lists but Delta does not. The 2026-10-13 six (W, OGN, DOS,
# MAGIC, BAT, CT) all left in the 2026-10-16 volume cut, so it is empty.
NOT_DELTA_LISTED_CRYPTO: set[str] = set()

# Non-crypto contracts, kept apart from the crypto list.
# XAUT replaced PAXG here: both are gold, and XAUT traded $3.0B over seven days
# against PAXG's $749M.
OTHER_WATCHLIST = [
    "SLVONUSD",
    "XAUTUSD",
]

# NVDAXUSD is back. It was dropped with QQQX, EWYB, DRAMB and CBRSB for having
# no live data, but a re-audit on 2026-09-01 - two rounds 30s apart, the same
# method that removed them - had all five answering from delta_india. The
# fetch chain reaches Delta directly now, so that finding no longer holds.
#
# BZ, SAMSUNG, AXTI, SLX and MSFT dropped 2026-09-16: not listed on Delta.
XSTOCK_WATCHLIST = [
    "TSLAXUSD",
    "METAXUSD",
    "SOXLBUSD",
    "SNDKBUSD",
    "MRVL/USDT:USDT",
    "NVDAXUSD",
    # Dropped earlier for thin volume: FLNC, IBM, PHAROS, SOXX, NVDL, BABA,
    # DELL, AVGO, TAIKO, TQQQ, OPENAI, AMZN, VANRY, SPY (SPY stays in the
    # rating registry as its own sector marker).
    #
    # Dropped in the 2026-09-01 cut for thin seven-day Delta volume, keeping
    # the six xStocks above: AAPLX, CRCLX, GOOGLX, COINX, MUB, SPCXX, INTCB,
    # MSTRB, SKHYNIX, NBIS, HOOD.
]

WATCHLIST = CRYPTO_WATCHLIST + OTHER_WATCHLIST + XSTOCK_WATCHLIST

# Which venue each scanned symbol is actually traded on, so an alert can say
# where to go and place it. Delta India lists all 33.
#
# This is a static list on purpose. Delta's listings drift, but a live lookup
# on every run would make an alert depend on a third API being up, and the
# venue of a symbol is not something that should change mid-session. Re-audit
# it against /v2/products when the watchlist is next reviewed.
DELTA_LISTED_SYMBOLS = {
    "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "HYPEUSD",
    "ZECUSD", "DOGEUSD", "AAVEUSD", "UNIUSD", "LINKUSD",
    "AVAXUSD", "BNBUSD", "SLVONUSD",
    "XAUTUSD", "TSLAXUSD", "METAXUSD", "SOXLBUSD", "SNDKBUSD",
    "MRVL/USDT:USDT", "NVDAXUSD",
    # 2026-10-13 CoinDCX 100M+ additions that Delta lists too (/v2/products).
    "NEARUSD", "STRKUSD", "SUIUSD", "ENAUSD", "WLDUSD",
    "FILUSD", "1000PEPEUSD", "ADAUSD", "BTWUSD", "TAOUSD", "ONDOUSD",
    "QNTUSD",
    # 2026-10-16 volume cut addition; Delta lists RLCUSD (live perp).
    "RLCUSD",
}

DELTA_API_BASE_URL = "https://api.india.delta.exchange"
# Where the crypto alert candles come from: "bitunix" (default since
# 2026-10-05, Lakky's call) or "delta". Delta prints thin and zero-volume
# candles on the small coins (ZORA: 478 zero-volume 30m bars in 60 days) that
# TradingView's other books do not; Bitunix had none. Backtest in
# research/out/bitunix/: zone alerts -82R on Bitunix vs -87R on Delta, fib/TL
# ~100R better, both graded on Delta candles with Delta fees.
# Delta stays the venue the trades are taken on, so the backtest still grades
# on Delta candles and the fees stay Delta's whichever source draws the zones.
# Covers the zone scanners (4h and 30m), entry_confirm and the fib/trendline
# scanner. Since 2026-10-09 (Lakky) the xStocks too, off the stock futures
# Bitunix lists under the plain ticker (BITUNIX_XSTOCK_PAIRS). "Other" stays on
# Delta: SLVON is a silver ETF token Bitunix does not list (its XAG is spot
# silver, a different price), and XAUT is not an xStock.
CRYPTO_CANDLE_SOURCE = (os.getenv("VICTUS_CRYPTO_CANDLE_SOURCE", "bitunix").strip().lower() or "bitunix")
if CRYPTO_CANDLE_SOURCE not in {"delta", "bitunix"}:
    raise ValueError(f"VICTUS_CRYPTO_CANDLE_SOURCE must be delta or bitunix, not {CRYPTO_CANDLE_SOURCE!r}")
BITUNIX_API_BASE_URL = "https://fapi.bitunix.com"
# Bitunix allows 10 requests a second per IP; stay a little under it.
BITUNIX_MIN_REQUEST_GAP_SECONDS = env_float("VICTUS_BITUNIX_MIN_REQUEST_GAP_SECONDS", 0.12)
# Every crypto watchlist symbol, checked against Bitunix's trading_pairs on
# 2026-10-05 (all 23 listed as <base>USDT); the 27 CoinDCX additions all OPEN on
# 2026-10-13; RLC listed on 2026-10-16. Re-check when CRYPTO_WATCHLIST changes.
# The xStocks are not "<Delta name>T" on Bitunix but the stock's own ticker,
# so each has its pair here. All six listed and OPEN on 2026-10-09
# (research/xstock_bitunix_probe.py, research/out/xstock/).
BITUNIX_XSTOCK_PAIRS = {
    "TSLAXUSD": "TSLAUSDT",
    "METAXUSD": "METAUSDT",
    "SOXLBUSD": "SOXLUSDT",
    "SNDKBUSD": "SNDKUSDT",
    "MRVL/USDT:USDT": "MRVLUSDT",
    "NVDAXUSD": "NVDAUSDT",
}
BITUNIX_SYMBOLS = set(CRYPTO_WATCHLIST) | set(BITUNIX_XSTOCK_PAIRS)
USE_LIVE_TICKER = env_flag("VICTUS_USE_LIVE_TICKER")
PRIMARY_EXCHANGE_ID = "binance"
# Last-resort venues after Bitunix and Delta. Binance is geo-blocked from
# GitHub Actions runners, so the rest are what a CI scan actually reaches.
EXCHANGE_IDS = ["binance", "kucoin", "okx", "bybit", "mexc", "bitget", "lbank", "coinex"]
TIMEFRAME = os.getenv("VICTUS_TIMEFRAME", "4h").strip() or "4h"
# Crypto trades around the clock, so 500 30m candles is only ten days.
# A zone from three weeks ago was not being ignored - it was not in the
# data at all, and no amount of zone logic can find a candle that was
# never fetched. Measured over sixty days on ten majors: at 500 bars the
# oldest level price actually returned to was 6 days old and 65 zones
# were alertable; at 1500 it was 29 days and 76. Going further to 2880
# bought only three more, so this is where the curve flattens.
#
# Bitunix pages 200 candles per request, Delta 4000.
OHLCV_LIMIT = env_int("VICTUS_OHLCV_LIMIT", 1500)

SWING_LENGTH = 10
ATR_PERIOD = 50
BOX_WIDTH = 2.5
# Raised with the lookback above. The cap keeps the NEWEST zones, so at
# 20 it discarded precisely the old levels the longer window exists to
# find - every one of six majors produced 19-32 zones a side at 1500
# bars. 60 leaves headroom above that.
HISTORY_OF_ZONES_TO_KEEP = env_int("VICTUS_HISTORY_OF_ZONES_TO_KEEP", 60)
# Matches the Pine indicator's f_check_overlapping, which rejects a new zone
# whose midpoint sits within atr * 2 of an existing one.
OVERLAP_ATR = 2.0

# Distance is measured to the entry edge - the one price reaches first -
# so this is "how far is price from the level I would actually trade".
# Alert as soon as a symbol comes within MAX_DISTANCE_PCT of it.
MIN_DISTANCE_PCT = env_float("VICTUS_MIN_DISTANCE_PCT", 0.0)
MAX_DISTANCE_PCT = env_float("VICTUS_MAX_DISTANCE_PCT", 0.20)
REARM_FACTOR = 1.25
# 0 disables the over-touch veto. The Pine indicator counts no touches and
# never retires a zone for being revisited - only a close through it kills the
# zone - so any positive value here drops levels the chart still shows.
# Back-to-back candles sitting on a zone mean price is grinding through it
# rather than reacting to it - thin volume, no rejection. Two consecutive
# touching candles retire the zone. This is deliberately stricter than the
# Pine indicator, which has no touch veto at all: the indicator draws every
# level, this decides which are worth an alert.
# ---------------------------------------------------------------------------
# Zone construction. Backtested 2026-09-06 over 42 symbols / 187 days of 30m;
# see ZONE_GEOMETRY_BACKTEST_FINDINGS.md for the table behind each default.
#
# ZONE_GEOMETRY "atr"  the fixed atr * (BOX_WIDTH/10) band. Production, and still
#                      the best arm on total net R.
#              "wick"  Shiva_Indicator_v7.pine's geometry - the pivot candle's
#                      wick, with the near edge pulled to the nearest body edge
#                      within ZONE_BASE_EXTRA bars. LIVE since 2026-09-06, on
#                      Shiva's call after reading it on chart. The ATR band still
#                      shows more total R in backtest (67.5 vs 54.3 over 187 days
#                      of 30m) but the same net expectancy per trade, on ~15%
#                      fewer trades and with less than half the same-bar
#                      stop/target collisions - so its number rests on far less
#                      that bar data cannot verify.
#
# The wick geometry is NOT a drop-in. Flipping this flag alone, leaving the close
# break rule and OVERLAP_ATR 2.0 in place, was the single worst configuration
# measured - 0.020 net expectancy against 0.058 for the ATR band. It needs
# ZONE_BREAK_ON_WICK and the tighter overlap below to reach 0.055. Change these
# together or not at all.
ZONE_GEOMETRY = os.getenv("VICTUS_ZONE_GEOMETRY", "wick").strip().lower() or "wick"

# base_extra was tuned by eye on a 30m chart: 5 bars each side of the pivot. It
# was never re-derived for 4h - 5 bars means 2.5 hours on 30m and 20 hours on
# 4h, an 8x difference in what the window actually searches, and only the 30m
# figure has five worked examples behind it (EX1-EX5). EX6, the one 4h example,
# does not independently pin the count: its own base window holds exactly one
# real neighbouring candle, so anything from 1 to 10 reproduces it identically
# and the base=5 default was never actually exercised by that example either.
#
# Fix: derive the bar count from a fixed real-world window instead of a flat
# bar count, so every timeframe gets the same-DURATION search rather than the
# same bar count. The window is BASE_WINDOW_MINUTES = 150 - exactly what 5 bars
# on 30m already is (5 * 30 = 150), so the 30m default is unchanged: this is a
# re-derivation of the untested case, not a retuning of the tested one.
#
#   30m (30 min/bar):  round(150/30)  = 5   <- unchanged, still what EX1-EX5 pin
#   4h  (240 min/bar): round(150/240) = 1   <- was 5 (20h window), now 1 (2.5h)
#   15m:               round(150/15) = 10  (clamped at the ceiling)
#   1h:                round(150/60) = 3
#   1d:                round(150/1440) = 0 -> floored to 1
#
# Floored at 1, never 0: 0 is the one value proven wrong on 30m (misses EX5 by
# 0.18, see Shiva_Indicator_v7.pine) and EX6 needs at least 1 to find its own
# neighbouring candle. Ceiling at 10 matches the original manual input's range.
# This is a principled default, not a second independently-tuned constant - 4h
# has one worked example, not five, so treat it as a starting point rather than
# a measured value the way 30m's 5 is.
TIMEFRAME_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "12h": 720,
    "1d": 1440, "d": 1440, "1w": 10080, "w": 10080,
}
BASE_WINDOW_MINUTES = 150  # = 5 bars * 30 min - the 30m default, unchanged


def auto_base_extra(timeframe_minutes):
    if not timeframe_minutes or timeframe_minutes <= 0:
        return 5
    bars = math.floor(BASE_WINDOW_MINUTES / timeframe_minutes + 0.5)  # round half up
    return max(1, min(10, int(bars)))


ZONE_BASE_EXTRA = env_int(
    "VICTUS_ZONE_BASE_EXTRA",
    auto_base_extra(TIMEFRAME_MINUTES.get(TIMEFRAME.strip().lower())),
)

# When the ring buffer is full, drop the weakest zone rather than the oldest.
# The original FIFO throws away exactly the old untouched zones the strategy
# calls strongest. Measured effect on P&L is nil - it evicts zones already spent
# - but it is what keeps long-dormant levels alive, which is the point.
# A wick through the far edge kills the zone, rather than a close through it.
# Essential to the wick geometry rather than cosmetic: with the close rule the
# wick construction nets 0.020 per trade, with this it nets 0.055. Zones die
# sooner and there are ~30% fewer of them, which is where the gain comes from.
# Meaningless under "atr", which is why it follows the geometry by default.
ZONE_BREAK_ON_WICK = env_flag("VICTUS_ZONE_BREAK_ON_WICK", ZONE_GEOMETRY == "wick")

ZONE_EVICT_WEAKEST = env_flag("VICTUS_ZONE_EVICT_WEAKEST", True)

# Restart the minimum-age clock on every touch, so MIN_ZONE_AGE_CANDLES means
# "untouched for this long" rather than "created this long ago". Worth +7% on net
# expectancy, and it gets there by removing trades on zones price is already
# working rather than by adding any.
ZONE_CLOCK_RESTARTS_ON_TOUCH = env_flag("VICTUS_ZONE_CLOCK_RESTARTS_ON_TOUCH", True)

# Wick zones are thinner than ATR bands, so their midpoints crowd this filter
# harder and real structure goes undrawn at the original 2.0. Measured over 187
# days: 1.0 gives 983 trades for 54.3 net R against 855 for 46.7 at 2.0, same
# expectancy per trade. Kept at 2.0 for the ATR band, which was tuned around it.
OVERLAP_ATR = env_float("VICTUS_OVERLAP_ATR", 1.0 if ZONE_GEOMETRY == "wick" else OVERLAP_ATR)

# ---------------------------------------------------------------------------
# Matching Shiva_Indicator_v7.pine exactly. The point of running the wick
# geometry live is to see its mistakes in the alerts, which only works if the
# alerts are the ones the chart would fire. Each value below tracks the
# indicator's own default when the geometry is "wick", and keeps the scanner's
# long-standing value when it is "atr".

# Pine's ta.atr is Wilder's RMA. This module used a simple rolling mean, which
# is a different number - it feeds the overlap filter, so the two disagreed
# about which zones to reject. "sma" restores the old behaviour.
ATR_METHOD = os.getenv("VICTUS_ATR_METHOD", "rma").strip().lower() or "rma"

# v7 keeps 50 per side; the scanner kept 60. v7 waits 15 untouched candles; the
# scanner waited 20. v7 has no over-touch veto at all - a zone that keeps being
# touched simply never matures, which the restarted clock already handles, so a
# second mechanism on top of it drops zones the chart still shows.
# v7 puts the stop a share of the ZONE HEIGHT beyond the far edge - measured at
# 30%, 17% and 25% of height on EX2, EX4 and EX3 - not a fixed share of price.
# On a wick zone those differ by a lot, because wick heights vary where an ATR
# band's do not. "price_pct" is the scanner's original 0.10%-of-price rule.
ZONE_SL_MODE = os.getenv(
    "VICTUS_ZONE_SL_MODE", "zone_pct" if ZONE_GEOMETRY == "wick" else "price_pct"
).strip().lower()
ZONE_SL_HEIGHT_PCT = env_float("VICTUS_ZONE_SL_HEIGHT_PCT", 25.0)

# v7 retires a broken zone and builds its replacement off a short pivot, so a
# new level appears within a few bars instead of waiting a full swing_length.
# Screenshot (44): "we retire the ZONE 1 and create a new and updated zone".
# The 30m ML rating gate (MIN_CRYPTO_ZONE_SCORE) was trained on the ATR band.
# Several of its inputs move with the wick geometry - distance_pct, distance_atr,
# atr_pct, zone_age_bars, touches_before_alert, max_touch_streak_before_alert -
# and its own success_definition says "reaches 1R before the configured stop",
# which is now a different stop. Both its features and its label have shifted, so
# on 30m it would be filtering v7's alerts by a model of a world that no longer
# exists - and filtering is exactly what you do not want when the whole point is
# to see the faults. The rating is still computed and still written to every
# alert record, so nothing is lost for later analysis; it just stops vetoing.
# Retrain on wick-geometry outcomes and turn this back on.
ZONE_RATING_GATE = env_flag("VICTUS_ZONE_RATING_GATE", ZONE_GEOMETRY != "wick")

# Daily trend filter, crypto only (Lakky, 2026-10-04). A demand zone alerts
# only while the last closed daily candle is above its EMA50, a supply zone
# only while it is below. Measured on 564 recorded crypto trades, 2026-08-11
# to 2026-10-04 (research/out/RESULTS.md): with-trend -8R, counter-trend
# -79R, and the gap held in both halves of the period. It did nothing for
# NSE or xStocks, so they are left alone. The zones themselves are not
# touched - this only decides which of them is worth a ping.
CRYPTO_TREND_FILTER = env_flag("VICTUS_CRYPTO_TREND_FILTER", True)
CRYPTO_TREND_EMA = env_int("VICTUS_CRYPTO_TREND_EMA", 50)

# EX 6, 2026-09-06. A zone can be right by the geometry and still untradeable:
# LTC 4h came out 54.446-55.559, which is 2.05% wide. "WE CAN NOT TAKE ANY TRADE
# WITH SL LIKE 2% SO WE NEED TO REDUCE THE LEVEL OF ZONE."
#
# The fix is not to shrink the box to a number. It is to re-anchor the near edge
# to a real level - "I USE CANDLE END" - the top of the neighbouring candle's
# wick, the highest point everything else in the base actually reached, leaving
# the origin candle's wick standing alone above it. On LTC that is 55.130, and
# the zone becomes 0.78%: "THE ZONE SIZE 0.78% WHICH I WANTED".
#
# Only fires when the zone is over the limit. Applied always it would contradict
# EX1-EX5, which are all under it already - it would give 0.26% on EX3 where
# 0.63% was drawn. 0 disables the rescue entirely.
#
# The limit is 0.80, not the 0.75 asked for, and the reason is EX5. That zone was
# drawn by hand at 0.777% and a 0.75 trigger re-cuts it to 0.57% - it would break
# one of the six worked examples. EX6's own accepted answer is 0.78%, so 0.78 is
# demonstrably a width that passes: it appears twice, once as a zone drawn from
# scratch and once as the fix for a zone that was too wide. 0.80 clears both and
# still fires on EX6's 2.05%. Set VICTUS_ZONE_MAX_WIDTH_PCT=0.75 for the strict
# reading, accepting that EX5 then gets re-cut.
ZONE_MAX_WIDTH_PCT = env_float("VICTUS_ZONE_MAX_WIDTH_PCT", 0.80)

# No alert - and no pre-alert watch row, so no GET READY / ENTRY NOW either - for
# a zone whose planned stop sits further than this from its entry. Asked for on
# 2026-09-20: a stop that wide makes the trade too big a risk per R to be worth
# an alert. Zone geometry is untouched (the chart still draws the zone); only the
# alert is withheld. Set VICTUS_MAX_ALERT_STOP_PCT=0 to switch it off.
MAX_ALERT_STOP_PCT = env_float("VICTUS_MAX_ALERT_STOP_PCT", 1.5)

ZONE_REBUILD_AFTER_BREAK = env_flag("VICTUS_ZONE_REBUILD_AFTER_BREAK", ZONE_GEOMETRY == "wick")

MAX_CONSECUTIVE_ZONE_TOUCHES = 2

# A zone has to stand before it means anything. A level confirmed a candle
# or two ago that price is already sitting on was never defended - it is
# just the recent high or low, and alerting on it produces the small, risky
# levels that are not worth a trade. Age is counted from confirmation, so a
# 30m zone must survive twenty candles - about ten hours - before it can
# raise an alert, and a 4h zone a little over three days.
# Twenty rather than fifteen because both markets said so: replayed on 5m
# candles, the alerts this blocks earned 0.054R on NSE and 0.389R on
# crypto, against 0.122R and 0.564R for the ones that survive it.
MIN_ZONE_AGE_CANDLES = env_int("VICTUS_MIN_ZONE_AGE_CANDLES", 20)

# These three are defined above with the scanner's own values, then overridden
# here when the wick geometry is running so the alerts track what v7 draws.
# Placed after their definitions on purpose - an override written before them
# is silently clobbered, which is exactly what happened the first time.
if ZONE_GEOMETRY == "wick":
    HISTORY_OF_ZONES_TO_KEEP = env_int("VICTUS_HISTORY_OF_ZONES_TO_KEEP", 50)
    MIN_ZONE_AGE_CANDLES = env_int("VICTUS_MIN_ZONE_AGE_CANDLES", 15)
    # v7 has no over-touch veto. The restarted age clock already stops a zone
    # price keeps working from maturing, so a second mechanism on top of it
    # only drops levels the chart still shows.
    MAX_CONSECUTIVE_ZONE_TOUCHES = env_int("VICTUS_MAX_CONSECUTIVE_ZONE_TOUCHES", 0)
# Shortest gap between two scans of the same timeframe. Every workflow is
# also dispatched by an external scheduler, so adding cron meant each scan
# ran twice - once on each trigger, minutes apart. Rather than depend on
# that scheduler being found and switched off, a scan that starts too soon
# after the last one steps aside. Zero disables the guard.
MIN_SCAN_INTERVAL_SECONDS = env_int("VICTUS_MIN_SCAN_INTERVAL_SECONDS", 8 * 60)

# How many candles a feed may be behind before it counts as dead. Some
# venues omit buckets with no trades or publish late, so two bars was too
# tight; four still catches a genuinely dead feed (VANRY was ten days behind).
STALE_BARS_ALLOWED = env_int("VICTUS_STALE_BARS_ALLOWED", 4)

# Crypto trades around the clock, but the user does not. Alerts are held
# outside 08:00-01:00 IST so nothing fires while nobody is awake to take
# it - an alert at 04:00 is not an opportunity, it is a missed trade in
# the morning's scrollback. The window wraps midnight, so the end hour is
# earlier than the start hour on the clock.
CRYPTO_ALERT_START = datetime_time(8, 0)
CRYPTO_ALERT_END = datetime_time(1, 0)

SCAN_SLEEP = 300
SCAN_WORKERS = 8
ALERT_COOLDOWN_SECONDS = env_int("VICTUS_ALERT_COOLDOWN_SECONDS", 4 * 60 * 60)
# Off since 2026-10-10 (lakky): alerts are S/R zones, fibs and trendlines only.
ALERT_RANGE_FILTER_SIGNALS = False
# Money line on the daily backtest cards (lakky, 2026-10-18: "a budget of 10000 ... with
# 5x leverage"). Every trade is sized at the full budget x leverage (a 50,000 position),
# so a trade's money result = BUDGET x LEVERAGE x its net % move (net R x stop %).
# Display only: it changes no trade, grade or alert.
ACCOUNT_BUDGET = 10000
ACCOUNT_LEVERAGE = 5
# S/R zone timeframes that scan and alert, crypto and NSE. 30m off since 2026-10-16
# (lakky: "remove 30m for now"); 4h stays on (lakky, 2026-10-18: "keep 4h on for fib,
# trendline and support and resistance"). 1D / 1W / 1M zones: ZONE_HTF_TIMEFRAMES, below.
# A scanner whose timeframe is not listed exits at once and posts nothing; its workflow
# can stay dispatched. Add "30m" back to turn it on.
ZONE_ALERT_TIMEFRAMES = [
    tf.strip() for tf in os.getenv("VICTUS_ZONE_ALERT_TIMEFRAMES", "4h").split(",") if tf.strip()
]


def zone_timeframe_enabled(timeframe):
    return str(timeframe).strip() in ZONE_ALERT_TIMEFRAMES


# S/R zones on 1D / 1W / 1M (lakky, 2026-10-16: "add 1d, 1w and 1month ... in the 30m
# crypto and nse channels"). Scanned by fib_trendline_scanner.py on the same charts
# as fibs and trendlines, posted to the old 30m zone channels (DISCORD_30M_WEBHOOK_URL,
# DISCORD_NSE_30M_WEBHOOK_URL). Empty turns them off.
ZONE_HTF_TIMEFRAMES = [
    tf.strip() for tf in os.getenv("VICTUS_ZONE_HTF_TIMEFRAMES", "1d,1w,1M").split(",") if tf.strip()
]
SIGNAL_ALERT_COOLDOWN_SECONDS = env_int("VICTUS_SIGNAL_ALERT_COOLDOWN_SECONDS", 4 * 60 * 60)
# After a send that failed (Discord down, every retry spent), try again this
# soon rather than waiting out the full cooldown. The full cooldown after a
# failure muted a real level for four hours over one failed request; retrying
# every scan had no backoff at all. Ten minutes is the middle ground.
FAILED_ALERT_RETRY_SECONDS = env_int("VICTUS_FAILED_ALERT_RETRY_SECONDS", 10 * 60)
# The previous model was trained on the old ATR-strip zones. Keep ratings off
# until a model trained on the polished wick zones passes out-of-sample checks.
ENABLE_CRYPTO_ZONE_RATINGS = env_flag(
    "VICTUS_ENABLE_CRYPTO_ZONE_RATINGS",
    default=True,
)
# Only validated crypto zone ratings above 5/10 are eligible for live alerts.
MIN_CRYPTO_ZONE_SCORE = env_int("VICTUS_MIN_CRYPTO_ZONE_SCORE", 6)
# Show the transparent rule-based quality score on every 4h crypto/xstock zone.
SHOW_4H_ZONE_SCORES = env_flag("VICTUS_SHOW_4H_ZONE_SCORES", default=True)
ENABLE_XSTOCK_HYBRID_RATINGS = env_flag(
    "VICTUS_ENABLE_XSTOCK_HYBRID_RATINGS",
    default=True,
)
XSTOCK_REGULAR_MIN_SCORE = env_int("VICTUS_XSTOCK_REGULAR_MIN_SCORE", 5)
XSTOCK_EXTENDED_MIN_SCORE = env_int("VICTUS_XSTOCK_EXTENDED_MIN_SCORE", 5)

PRINT_SCAN_SUMMARY = True
PRINT_ALERTS_TO_CONSOLE = True

TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
DISCORD_WEBHOOK_URL = ""
DISCORD_STATUS_WEBHOOK_URL = ""

# ---- Fib + trendline alerts (fib_trendline_scanner.py), added 2026-09-29 ----
# Their own two Discord channels, apart from the zone alerts: fib zone entries
# go to one webhook, trendline touches and breaks to the other. Leave empty
# here like the rest - the workflow reads them from repo secrets of the same
# name.
DISCORD_FIB_WEBHOOK_URL = ""
DISCORD_TRENDLINE_WEBHOOK_URL = ""
# Higher timeframes only. "1w" is Delta's own weekly candle (Monday 00:00
# UTC, like TradingView); "1M" has no Delta candle and is built from daily
# ones by calendar month.
#
# 30m is supported but off (Shiva, 2026-09-29): at the 1.5% band the history
# backtest counted ~530 30m alerts a day across crypto and NSE - 90% of all of
# them - against ~75 a day for 4H to 1M. It can come back with a tighter band;
# reports/FIB_TRENDLINE_BACKTEST.md still scores it.
FIB_TL_TIMEFRAMES = [
    tf.strip() for tf in os.getenv("VICTUS_FIB_TL_TIMEFRAMES", "4h,1d,1w,1M").split(",") if tf.strip()
]
# Which fib zones alert (Lakky, 2026-10-08, Notion 20): only Zone 2, the deeper
# one - the lower box for a buy, the upper box for a sell. Zone 1, the shallow
# box (upper for a buy, lower for a sell), no longer alerts on either market.
# Sep 1 - Oct 8 replay (research/fib_zone_preference.py): crypto both zones
# -33.8R / 131 trades, Zone 2 only -4.6R / 47; NSE -151.7R / 394 vs -71.7R / 151
# (NSE's Zone 2 is worse per trade, -0.49R vs -0.33R - kept on his call).
FIB_ALERT_ZONES = (2,)
# Which fib levels alert, per timeframe (lakky, 2026-10-20, "for testing"): L1/L2 are the weaker
# box's near/far edge, L3/L4 the stronger box's; each level alerts once, on its own entry, with
# the fib's one stop (FIB_SL_HEIGHT_PCT beyond L4). L3 is the old alert and keeps its key. Sep 1 -
# Oct 20 replay (research/fib_levels_all_backtest.py, part fib-levels-all): crypto 4H -0.03R -> -0.14R
# a trade, 1D +0.42R -> +0.07R; NSE worse; L4 and 1W/1M L1-L2 the weakest. Empty = L3 only.
FIB_ALERT_LEVELS = {
    "4h": ("L2", "L3", "L4"),
    "1d": ("L1", "L2", "L3", "L4"),
    "1w": ("L1", "L2", "L3", "L4"),
    "1M": ("L1", "L2", "L3", "L4"),
}
# Fib stop = the support/resistance zone rule (Lakky, 2026-10-08, Notion 20):
# ZONE_SL_HEIGHT_PCT (25%) of the fib box's height beyond its far edge, in place
# of the inner fib's 0.55 line inside the box. Sep 1 - Oct 8, deeper zone only
# (research/fib_sr_logic_backtest.py): crypto -5.7R -> -3.1R, NSE -72.8R -> -30.5R,
# about the same number of alerts. The S/R 1.5% stop cap and daily trend filter
# were tested too and are not applied to fibs.
FIB_SL_HEIGHT_PCT = ZONE_SL_HEIGHT_PCT
# The indicator's own lengths: fib_len 10, tl_len 10, tl_keep 6.
FIB_SWING_LENGTH = 10
TRENDLINE_SWING_LENGTH = 10
TRENDLINES_KEEP = 6
# Alert from 0.75% away down to touching, the same band on every timeframe and
# for both. Fib distance is to the near edge of a zone (0 once price is inside
# it); trendline distance is to the line, approach side only.
#
# Shiva set 1.5% first, then 0.75% (both 2026-09-29). The backtest at each:
# 79 -> 68 alerts a day on 4H-1M, filled 61-74% -> 76-84% of the time on
# 4H/1D, win rates 1-2 points lower - the band decides when he is told, not
# where the entry is. It is a preference, not an edge.
FIB_TL_MIN_DISTANCE_PCT = env_float("VICTUS_FIB_TL_MIN_DISTANCE_PCT", 0.0)
FIB_TL_MAX_DISTANCE_PCT = env_float("VICTUS_FIB_TL_MAX_DISTANCE_PCT", 0.75)
# 1W / 1M alert early (lakky, 2026-10-21: "alert space of 3% ... to get ready for big timeframe
# trades", crypto and NSE). Fibs, trendlines and S/R zones on these timeframes alert from
# EARLY_ALERT_BAND_PCT away instead of 0.75% (fib/TL) / MAX_DISTANCE_PCT (zones); the 0.75% alert
# often came after the candle had already touched the entry. Entry, stop and target are unchanged,
# and entry confirm's GET READY (0.50%) still follows. Backtest: research/early_band_backtest.py,
# part early-band.
EARLY_ALERT_BAND_PCT = env_float("VICTUS_EARLY_ALERT_BAND_PCT", 3.0)
EARLY_ALERT_TIMEFRAMES = tuple(
    tf.strip() for tf in os.getenv("VICTUS_EARLY_ALERT_TIMEFRAMES", "1w,1M").split(",") if tf.strip()
)


def alert_band_pct(tf, default):
    """The alert band (%) on timeframe tf: EARLY_ALERT_BAND_PCT on 1W / 1M, else default."""
    return EARLY_ALERT_BAND_PCT if tf in EARLY_ALERT_TIMEFRAMES else default


# Risk warning line (lakky, 2026-10-17), crypto fib + trendline touch alerts only:
# the title shows the coin's 24h % ("SOL -5.2% · FIB L3 · BUY"), and a 4th line
# "⚠️ **Big 24h move · Market down: BTC ↓ ETH ↓ SOL ↑**" when it moved this % either way
# and/or the market is against the trade (below). The alert still sends. Sep 1 - Oct 17 (research/risk_warning_backtest.py,
# part risk-warn): fib 4H unwarned +0.03R vs warned -0.16R, 1D+ +1.21R vs -0.20R;
# TL 4H -0.38R vs -0.46R. Zones were the other way round, so they get no warning.
# 2% (lakky, 2026-10-17, "for testing"): at 2% ~85% of fib/TL alerts warn vs ~65% at 4%, and the
# split is weaker (fib 4H +0.44% vs -0.42% a trade; 4%: +0.38% vs -0.65%). He watches it live.
RISK_WARN_MOVE_PCT = env_float("VICTUS_RISK_WARN_MOVE_PCT", 2.0)
# The market is judged on BTC, ETH and SOL (lakky, 2026-10-17): warn when this many of the three
# are against the trade. Fib 4H against / with: BTC alone -0.35% / -0.26% a trade, 2 of 3 -0.69% / -0.05%.
RISK_WARN_MARKET_SYMBOLS = ("BTCUSD", "ETHUSD", "SOLUSD")
RISK_WARN_MARKET_MIN_AGAINST = 2
# Trade rules the alerts print and the backtests score (Shiva's choice,
# 2026-09-29). Fib: entry at the zone's near edge (his EX 2 ETH trades), SL
# FIB_SL_HEIGHT_PCT beyond the far edge (since 2026-10-08). Trendline: entry at the line, SL this % on the far side of it.
TRENDLINE_SL_PCT = {"30m": 0.5, "4h": 1.0, "1d": 1.5, "1w": 2.5, "1M": 3.0}
# Trendline trades, Lakky's way (2026-10-11, from his hand-marked charts): the
# stop sits on the most recent candle whose wick, or body, is at least this % past
# the entry - whichever of the two is closer; TRENDLINE_SL_PCT only when there is
# none. One target at 1R, no breakeven, no hold limit.
TRENDLINE_STOP_MIN_PCT = 0.75
# An alert that has not filled within ENTRY_WAIT_BARS candles of its own
# timeframe is "no fill"; a filled trade still open after MAX_HOLD_BARS is
# "timeout". Counted in trading candles, not clock time - an NSE 30m trade's
# clock stops overnight - so 1M waits five months.
FIB_TL_ENTRY_WAIT_BARS = 5
FIB_TL_MAX_HOLD_BARS = 20
