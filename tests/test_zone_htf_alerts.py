"""1D / 1W / 1M S/R zone alerts in fib_trendline_scanner (lakky, 2026-10-16).

The zone scanner's engine and rules on the 1D+ charts, posted to the old 30m zone
channels and recorded for the daily report. HYPE 1D (Bitunix fixture): the nearest
live demand zone is 51.111 - 51.5, entry 51.5.
"""
from pathlib import Path

import pandas as pd
import pytest

import config
import fib_trendline_daily_report as report
import fib_trendline_scanner as fts
import scanner
from fib_trendline_data import CRYPTO, NSE

FIXTURE = Path(__file__).parent / "fixtures" / "hype_usdt_1d_bitunix_300.csv"
DAY = 86400


@pytest.fixture(scope="module")
def candles():
    df = pd.read_csv(FIXTURE)
    return [[int(t), o, h, l, c] for t, o, h, l, c in zip(df.time, df.open, df.high, df.low, df.close)]


def chart_with_forming(candles):
    # the last fixture candle plays the forming one: analyse drops it as not closed
    return candles + [[candles[-1][0] + DAY, 0, 0, 0, 0]]


def now_for(candles):
    return candles[-1][0] + DAY + 3600       # an hour into the forming candle


def test_timeframes_and_channels():
    assert config.ZONE_HTF_TIMEFRAMES == ["1d", "1w", "1M"]
    assert fts.webhook_env("zone", CRYPTO) == "DISCORD_30M_WEBHOOK_URL"
    assert fts.webhook_env("zone", NSE) == "DISCORD_NSE_30M_WEBHOOK_URL"


def test_demand_zone_alerts_inside_the_band(candles):
    zones = fts.zone_candidates("HYPEUSD", "1d", candles, 51.55, None)
    assert [(z["zone_type"], z["entry"], z["alert"]) for z in zones] == [("demand", 51.5, True)]
    plan = zones[0]["plan"]
    assert plan["side"] == "long" and plan["sl"] == pytest.approx(51.111 - 0.389 * 0.25)


def test_no_alert_outside_band_past_entry_or_against_trend(candles):
    assert not any(z["alert"] for z in fts.zone_candidates("HYPEUSD", "1d", candles, 51.65, None))  # 0.29% away
    assert fts.zone_candidates("HYPEUSD", "1d", candles, 51.45, None) == []    # through the entry
    assert fts.zone_candidates("HYPEUSD", "1d", candles, 51.55, None, trend=-1) == []
    assert fts.zone_candidates("HYPEUSD", "1d", candles, 51.55, (51.0, 92.0)) == []  # forming wick killed it


def test_only_1d_and_up(candles):
    now = now_for(candles)
    chart = chart_with_forming(candles)
    assert fts.analyse(CRYPTO, "HYPEUSD", "1d", chart, now, 51.55)["zone"]
    assert fts.analyse(CRYPTO, "HYPEUSD", "4h", chart, now, 51.55)["zone"] == []


def test_alert_once_then_rearm_after_leaving_band(candles):
    now = now_for(candles)
    chart = chart_with_forming(candles)
    state = {}

    def zone_alerts(price, t):
        planned = fts.plan_alerts(state, CRYPTO, "HYPEUSD", "1d",
                                  fts.analyse(CRYPTO, "HYPEUSD", "1d", chart, t, price), t)
        return [p for p in planned if p[0] == "zone"]

    first = zone_alerts(51.55, now)
    assert len(first) == 1
    channel, key, message, record = first[0]
    assert message.splitlines()[0] == "**HYPE | BUY | 1D**"
    assert record["kind"] == "zone" and record["plan"]["entry"] == 51.5
    fts.mark_sent(state, key, now)
    assert zone_alerts(51.55, now + 5 * 3600) == []          # still in the band
    assert zone_alerts(60.0, now + 6 * 3600) == []           # left it
    assert state[key]["in_band"] is False
    assert len(zone_alerts(51.55, now + 7 * 3600)) == 1     # back in, cooldown passed


def test_daily_report_has_a_zone_card():
    record = {"id": "z@1", "kind": "zone", "market": CRYPTO, "symbol": "HYPEUSD", "tf": "1d",
              "sent_ts": 1792000000, "plan": {"side": "long", "entry": 51.5, "sl": 51.0}}
    result = {"outcome": "SL", "filled": True, "sl": True, "be": False, "r1": False, "r2": False,
              "half": False, "resolved": True}
    cards = report.build_report(report.ist_date(record["sent_ts"]), [record], {"z@1": result})
    assert len(cards) == 1 and cards[0].startswith("S/R ZONE 1D+ BACKTEST")


def test_1w_and_1m_zones_alert_from_3_percent(candles):
    """lakky (2026-10-21): 1W / 1M alert from 3% away (config.EARLY_ALERT_BAND_PCT), 1D stays 0.20%."""
    for tf in ("1w", "1M"):
        zones = fts.zone_candidates("HYPEUSD", tf, candles, 52.9, None)     # 2.7% above entry 51.5
        assert [(z["entry"], z["alert"]) for z in zones if z["zone_type"] == "demand"] == [(51.5, True)]
        assert not any(z["alert"] for z in fts.zone_candidates("HYPEUSD", tf, candles, 53.2, None))   # 3.3%
    assert fts.zone_candidates("HYPEUSD", "1d", candles, 52.9, None) == []
