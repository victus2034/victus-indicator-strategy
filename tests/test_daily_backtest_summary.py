import datetime
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import pandas as pd

import daily_backtest_summary as summary


def base_alert(**overrides):
    alert = {
        "event_time": pd.Timestamp("2026-08-04 10:00", tz=summary.IST),
        "event_time_ist": pd.Timestamp("2026-08-04 10:00", tz=summary.IST),
        "timeframe": "30m",
        "symbol": "TCS.NS",
        "side": "long",
        "distance_pct": 0.5,
        "alert_price": 100.0,
        "level": 99.0,
        "zone_bottom": 99.0,
        "zone_top": 100.0,
        "body_entry": 100.0,
        "rating": 6,
        "zone_id": "TCS.NS|long|99.00000000|100.00000000",
        "source_line": 1,
    }
    alert.update(overrides)
    return alert


def crypto_alert(**overrides):
    alert = base_alert(
        symbol="BTCUSDT",
        event_time=pd.Timestamp("2026-08-04 10:00", tz=summary.IST),
        event_time_ist=pd.Timestamp("2026-08-04 10:00", tz=summary.IST),
        zone_id="BTCUSDT|long|99.00000000|100.00000000",
    )
    alert.update(overrides)
    return alert


def xstock_alert(**overrides):
    alert = crypto_alert(
        symbol="AAPLXUSD",
        zone_id="AAPLXUSD|long|99.00000000|100.00000000",
    )
    alert.update(overrides)
    return alert


def other_alert(**overrides):
    alert = crypto_alert(
        symbol="SLVONUSD",
        zone_id="SLVONUSD|long|99.00000000|100.00000000",
    )
    alert.update(overrides)
    return alert


def crypto_frame(start="2026-08-04 10:00", rows=None):
    rows = rows or [
        (101.0, 101.2, 100.8, 101.0),
        (100.0, 100.2, 100.0, 100.1),
        (100.1, 100.4, 99.9, 100.2),
        (100.2, 100.6, 100.0, 100.5),
        (100.5, 101.0, 100.3, 100.9),
        (100.9, 102.0, 100.7, 101.8),
        (101.8, 102.2, 101.5, 102.0),
    ]
    index = pd.date_range(start, periods=len(rows), freq="30min", tz=summary.IST)
    return pd.DataFrame(
        {
            "open": [row[0] for row in rows],
            "high": [row[1] for row in rows],
            "low": [row[2] for row in rows],
            "close": [row[3] for row in rows],
            "volume": [1] * len(rows),
        },
        index=index,
    )


class DailyBacktestSummaryTests(unittest.TestCase):

    def test_xstock_backtest_uses_the_same_window_as_crypto(self):
        # They trade on the same venues, around the clock, and are alerted
        # on the same cadence. Tracking every available bar instead let a
        # trade run for days before it resolved.
        alerts = pd.DataFrame([xstock_alert()])
        frame = crypto_frame()
        with patch.object(
            summary, "crypto_tracking_end", wraps=summary.crypto_tracking_end
        ) as window:
            results, _ = summary.run_backtest(
                alerts,
                {"AAPLXUSD": frame},
                market="xstock",
            )
        window.assert_called()
        self.assertEqual(len(results), 1)

    def test_nse_tracking_stops_on_same_trading_day(self):
        index = pd.DatetimeIndex(
            [
                "2026-07-22 09:15",
                "2026-07-22 10:15",
                "2026-07-22 11:15",
                "2026-07-23 09:15",
            ],
            tz=summary.IST,
        )
        frame = pd.DataFrame(
            {
                "open": [100.0, 101.0, 102.0, 120.0],
                "high": [102.0, 103.0, 104.0, 130.0],
                "low": [99.0, 100.0, 101.0, 110.0],
                "close": [101.0, 102.0, 103.0, 125.0],
                "volume": [1, 1, 1, 1],
            },
            index=index,
        )

        end_index, mature = summary.same_day_tracking_end(
            frame,
            pd.Timestamp("2026-07-22 10:00", tz=summary.IST),
        )

        self.assertTrue(mature)
        self.assertEqual(end_index, 2)

    def test_infer_bar_duration_uses_minimum_not_median_gap(self):
        # NSE 4h has only ~2 bars/session, split evenly between the short
        # intraday gap (4h) and the long overnight gap (~20h) - the median
        # of alternating 4h/20h diffs is unstable and can land on the
        # overnight side, making every candle appear to "end" almost a day
        # later than it really does. The minimum gap reliably picks the
        # true bar interval since session breaks are always larger.
        index = pd.DatetimeIndex(
            [
                "2026-08-11 09:15",
                "2026-08-11 13:15",
                "2026-08-12 09:15",
                "2026-08-12 13:15",
                "2026-08-13 09:15",
                "2026-08-13 13:15",
            ],
            tz=summary.IST,
        )
        frame = pd.DataFrame(
            {
                "open": [100.0] * 6,
                "high": [101.0] * 6,
                "low": [99.0] * 6,
                "close": [100.5] * 6,
                "volume": [1] * 6,
            },
            index=index,
        )
        self.assertEqual(summary.infer_bar_duration(frame), pd.Timedelta(hours=4))

    def test_same_day_tracking_end_stops_at_1510_not_market_close(self):
        # The user personally stops trading at 15:10, not real market
        # close (15:30), because of unpredictable volume/moves in the
        # last ~20 minutes of the session. A candle ending after 15:10
        # must never be treated as usable for evaluation, even though the
        # exchange itself is still open.
        index = pd.DatetimeIndex(
            [
                "2026-08-14 09:15",
                "2026-08-14 13:15",
                "2026-08-14 14:15",
            ],
            tz=summary.IST,
        )
        frame = pd.DataFrame(
            {
                "open": [100.0] * 3,
                "high": [102.0] * 3,
                "low": [99.0] * 3,
                "close": [101.0] * 3,
                "volume": [1] * 3,
            },
            index=index,
        )
        end_index, mature = summary.same_day_tracking_end(
            frame, pd.Timestamp("2026-08-14 09:22", tz=summary.IST)
        )
        self.assertTrue(mature)
        # 14:15 candle ends 15:15 - past the 15:10 cutoff, excluded.
        # 13:15 candle ends 14:15 - the last usable one.
        self.assertEqual(end_index, 1)

    def test_nse_4h_alert_resolves_same_day_not_next_session(self):
        # NSE 4h backtest evaluation runs against raw 1h source candles
        # (see configure_nse_data), not resampled 4h bars, so the day's
        # zone touch must resolve using those finer same-day candles, not
        # by spilling into the next trading session.
        alerts = pd.DataFrame([base_alert(timeframe="4h")])
        index = pd.DatetimeIndex(
            [
                "2026-08-04 09:15",
                "2026-08-04 10:15",
                "2026-08-04 11:15",
                "2026-08-05 09:15",
            ],
            tz=summary.IST,
        )
        frame = pd.DataFrame(
            {
                "open": [102.0, 100.0, 100.0, 200.0],
                "high": [103.0, 100.5, 100.5, 201.0],
                "low": [101.5, 98.5, 98.5, 199.0],
                "close": [102.5, 99.5, 99.5, 200.5],
                "volume": [1, 1, 1, 1],
            },
            index=index,
        )
        results, _ = summary.run_backtest(alerts, {"TCS.NS": frame}, market="nse")
        self.assertTrue(bool(results.iloc[0]["filled"]))
        self.assertEqual(results.iloc[0]["entry_time"], index[1])

    def test_reaching_half_r_then_reversing_exits_at_breakeven(self):
        index = pd.DatetimeIndex(
            ["2026-08-04 10:00", "2026-08-04 10:30", "2026-08-04 11:00"],
            tz=summary.IST,
        )
        frame = pd.DataFrame(
            {
                "open": [101.0, 100.0, 100.1],
                "high": [101.2, 100.6, 100.2],
                "low": [100.8, 100.0, 99.7],
                "close": [101.0, 100.4, 99.9],
                "volume": [1, 1, 1],
            },
            index=index,
        )

        # +0.5R moves the stop to entry rather than closing the trade, so
        # giving it back exits flat instead of banking half a risk unit
        # that was never taken off the table.
        result = summary.simulate_alert(frame, base_alert(), 0, 2)

        self.assertEqual(result["final_result"], summary.BREAK_EVEN)
        # The stop sits past entry to clear the round trip; it is still a
        # stop order, so it pays the same slip as an SL. Net it is a scratch.
        be_stop = 100.0 * (1 + summary.BREAK_EVEN_OFFSET_PCT / 100)
        self.assertAlmostEqual(
            result["exit_price"], be_stop * (1 - summary.SL_FILL_SLIPPAGE_PCT / 100)
        )
        self.assertAlmostEqual(result["net_realized_r"], 0.0, delta=0.05)


    def test_a_stop_tighter_than_the_offset_leaves_the_stop_alone(self):
        # entry 100.00, stop 99.78 -> +0.5R lands at 100.11, but the
        # breakeven stop would sit at 100.12, above its own trigger. Placing
        # it there fills instantly and forces the trade out at the offset,
        # so the stop must stay put and let the trade run.
        alert = base_alert(
            zone_bottom=99.78, zone_top=100.0, body_entry=100.0,
            planned_entry=100.0, stop_price=99.78,
        )
        index = pd.date_range("2026-08-04 10:00", periods=5, freq="5min", tz=summary.IST)
        frame = pd.DataFrame(
            {
                "open": [100.5, 100.0, 100.2, 100.3, 100.4],
                "high": [100.6, 100.12, 100.30, 100.45, 100.60],
                "low": [100.4, 99.99, 100.15, 100.25, 100.35],
                "close": [100.5, 100.10, 100.28, 100.40, 100.55],
                "volume": [1] * 5,
            },
            index=index,
        )

        result = summary.simulate_alert(frame, alert, 0, 4)

        # Price ran past +2R (100.44); a forced exit at 100.12 would have
        # capped it at the offset instead.
        self.assertEqual(result["final_result"], "+2R")

    def test_price_running_clean_past_entry_still_fills(self):
        # A resting buy limit at 100 fills when price trades down through
        # it, even if no single bar happens to straddle the level. The old
        # low <= entry <= high test missed exactly these, and they are the
        # common case since alerts fire with price already inside the zone.
        index = pd.date_range("2026-08-04 10:00", periods=4, freq="5min", tz=summary.IST)
        frame = pd.DataFrame(
            {
                "open": [101.0, 99.0, 98.5, 98.0],
                "high": [101.2, 99.2, 98.8, 98.3],
                "low": [100.9, 98.8, 98.2, 97.8],
                "close": [101.0, 98.9, 98.4, 98.0],
                "volume": [1] * 4,
            },
            index=index,
        )
        self.assertEqual(
            summary.find_entry(frame, 0, 100.0, 3, "TCS.NS", "30m", "long"), 1
        )

    def test_short_side_fills_when_price_runs_up_through_entry(self):
        index = pd.date_range("2026-08-04 10:00", periods=3, freq="5min", tz=summary.IST)
        frame = pd.DataFrame(
            {
                "open": [99.0, 101.0, 102.0],
                "high": [99.2, 101.5, 102.5],
                "low": [98.8, 100.8, 101.8],
                "close": [99.0, 101.2, 102.2],
                "volume": [1] * 3,
            },
            index=index,
        )
        self.assertEqual(
            summary.find_entry(frame, 0, 100.0, 2, "TCS.NS", "30m", "short"), 1
        )

    def test_entry_window_is_a_duration_not_a_raw_bar_count(self):
        # ENTRY_WAIT_BARS means three bars of the *alert's* timeframe. Since
        # evaluation runs on finer candles, counting raw bars would shrink a
        # 30m alert's 90-minute window down to 15 minutes of 5m bars.
        five_min = pd.DataFrame(
            {"open": [1.0] * 40, "high": [1.0] * 40, "low": [1.0] * 40,
             "close": [1.0] * 40, "volume": [1] * 40},
            index=pd.date_range("2026-08-04 09:15", periods=40, freq="5min", tz=summary.IST),
        )
        self.assertEqual(summary.entry_window_bars(five_min, "30m"), 18)  # 90 min

        one_hour = pd.DataFrame(
            {"open": [1.0] * 12, "high": [1.0] * 12, "low": [1.0] * 12,
             "close": [1.0] * 12, "volume": [1] * 12},
            index=pd.date_range("2026-08-04 09:15", periods=12, freq="1h", tz=summary.IST),
        )
        self.assertEqual(summary.entry_window_bars(one_hour, "4h"), 12)  # 12 hours

    def test_entry_is_found_within_the_scaled_window_on_fine_candles(self):
        # The touch lands 45 minutes after the alert - inside a 30m alert's
        # 90-minute window, but well past a naive 3-bar count on 5m candles.
        index = pd.date_range("2026-08-04 10:00", periods=12, freq="5min", tz=summary.IST)
        highs = [101.0] * 12
        lows = [100.5] * 12
        lows[9] = 99.5  # 10:45, nine 5m bars after the alert bar
        frame = pd.DataFrame(
            {"open": highs, "high": highs, "low": lows, "close": highs, "volume": [1] * 12},
            index=index,
        )

        self.assertEqual(
            summary.find_entry(frame, 0, 100.0, 11, "TCS.NS", "30m"), 9
        )
        # Without the timeframe the old three-bar count applies and misses it.
        self.assertIsNone(summary.find_entry(frame, 0, 100.0, 11, "TCS.NS", None))
    def test_a_stopped_out_trade_cannot_be_upgraded_by_a_later_recovery(self):
        # Touches +0.5R, then trades through the stop, then recovers to
        # +2R. The position was flat well before that +2R print, so it must
        # close at the milestone it actually secured. Previously the loop
        # skipped the stop once an outcome was set and let the recovery
        # upgrade the trade all the way to +2R.
        index = pd.DatetimeIndex(
            [
                "2026-08-04 10:00",
                "2026-08-04 10:30",
                "2026-08-04 11:00",
                "2026-08-04 11:30",
            ],
            tz=summary.IST,
        )
        # entry 100.00, stop 98.901 -> +0.5R at 100.55, +2R at 102.20.
        # Bar 1 fills at its open and secures +0.5R, bar 2 trades through the stop,
        # bar 3 recovers past +2R.
        frame = pd.DataFrame(
            {
                "open": [101.0, 100.0, 99.5, 100.0],
                "high": [101.2, 100.8, 99.5, 103.0],
                "low": [100.9, 99.8, 98.5, 99.5],
                "close": [101.0, 100.2, 98.8, 102.5],
                "volume": [1, 1, 1, 1],
            },
            index=index,
        )

        result = summary.simulate_alert(frame, base_alert(), 0, 3)

        self.assertEqual(result["final_result"], summary.BREAK_EVEN)
        self.assertEqual(result["exit_time"], index[2])

    def test_stop_before_half_r_is_sl(self):
        index = pd.DatetimeIndex(["2026-08-04 10:00", "2026-08-04 10:30"], tz=summary.IST)
        frame = pd.DataFrame(
            {
                "open": [101.0, 100.0],
                "high": [101.2, 100.2],
                "low": [100.8, 98.9],
                "close": [101.0, 99.2],
                "volume": [1, 1],
            },
            index=index,
        )

        result = summary.simulate_alert(frame, base_alert(), 0, 1)

        self.assertEqual(result["final_result"], "SL")
        # Slightly worse than a flat -1.0R: SL fills assume a small adverse
        # slip beyond the stop trigger (see SL_FILL_SLIPPAGE_PCT).
        # Worse than -1R on two counts: the stop slips past its trigger,
        # and the round-trip charges land on top.
        self.assertLess(result["net_realized_r"], -1.1)
        self.assertAlmostEqual(result["realized_r"], -1.0449959053685223)
        self.assertAlmostEqual(result["stop_price"], 98.901)

    def test_same_candle_stop_and_target_is_ambiguous_without_resolution_data(self):
        index = pd.DatetimeIndex(["2026-08-04 10:00", "2026-08-04 10:30"], tz=summary.IST)
        frame = pd.DataFrame(
            {
                "open": [101.0, 100.0],
                "high": [101.2, 100.7],
                "low": [100.8, 98.8],
                "close": [101.0, 100.1],
                "volume": [1, 1],
            },
            index=index,
        )

        result = summary.simulate_alert(frame, base_alert(), 0, 1)

        self.assertEqual(result["final_result"], summary.DATA_QUALITY_AMBIGUOUS)
        self.assertTrue(pd.isna(result["net_realized_r"]))
        self.assertFalse(result["half_r_hit"])
        self.assertIsNone(result["time_to_sl"])

    def test_resolution_windows_preserve_exact_ambiguous_interval(self):
        results = pd.DataFrame(
            [
                {
                    "symbol": "BTCUSDT",
                    "final_result": summary.DATA_QUALITY_AMBIGUOUS,
                    "ambiguous_interval_start": pd.Timestamp("2026-08-04 10:30", tz=summary.IST),
                    "ambiguous_interval_end": pd.Timestamp("2026-08-04 11:00", tz=summary.IST),
                }
            ]
        )

        self.assertEqual(
            summary.resolution_windows(results)["BTCUSDT"],
            (
                pd.Timestamp("2026-08-04 10:30", tz=summary.IST),
                pd.Timestamp("2026-08-04 11:00", tz=summary.IST),
            ),
        )

    def test_reconciliation_diagnostics_detects_missing_finalization(self):
        delivered = pd.DataFrame([{"trade_id": "trade-1"}])
        backtested = pd.DataFrame([{"trade_id": "trade-1", "final_result": "+1R"}])

        with tempfile.TemporaryDirectory() as tmp:
            diagnostics = summary.reconciliation_diagnostics(
                delivered,
                backtested,
                Path(tmp) / "finalized.jsonl",
            )

        self.assertIn("backtest_without_finalized=1", diagnostics["issues"])

    def test_same_candle_order_uses_resolution_frame_when_available(self):
        index = pd.DatetimeIndex(["2026-08-04 10:00", "2026-08-04 10:30"], tz=summary.IST)
        frame = pd.DataFrame(
            {
                "open": [101.0, 100.0],
                "high": [101.2, 100.7],
                "low": [100.8, 98.8],
                "close": [101.0, 100.1],
                "volume": [1, 1],
            },
            index=index,
        )
        resolution_index = pd.date_range("2026-08-04 10:30", periods=3, freq="1min", tz=summary.IST)
        resolution_frame = pd.DataFrame(
            {
                "open": [100.0, 100.6, 99.5],
                "high": [100.1, 100.7, 99.6],
                "low": [99.9, 100.2, 98.8],
                "close": [100.0, 100.3, 99.0],
                "volume": [1, 1, 1],
            },
            index=resolution_index,
        )

        # The fine data shows +0.5R printing before the stop, so the stop
        # had already moved to entry - the trade exits flat, not at -1R.
        result = summary.simulate_alert(frame, base_alert(), 0, 1, resolution_frame)

        self.assertEqual(result["final_result"], summary.BREAK_EVEN)
        self.assertAlmostEqual(result["net_realized_r"], 0.0, delta=0.05)

    def test_same_candle_target_then_two_r_before_stop_is_two_r(self):
        # Inside one bar the fine candles go +1R, then +2R, then the stop.
        # The first event alone read this as a breakeven exit.
        index = pd.DatetimeIndex(["2026-08-04 10:00", "2026-08-04 10:30"], tz=summary.IST)
        frame = pd.DataFrame(
            {"open": [101.0, 100.0], "high": [101.2, 102.3], "low": [100.8, 98.8],
             "close": [101.0, 99.0], "volume": [1, 1]},
            index=index,
        )
        fine = pd.DataFrame(
            {"open": [100.0, 101.0, 101.5], "high": [101.15, 102.3, 101.6],
             "low": [99.9, 100.9, 98.8], "close": [101.0, 101.5, 99.0], "volume": [1, 1, 1]},
            index=pd.date_range("2026-08-04 10:30", periods=3, freq="1min", tz=summary.IST),
        )
        result = summary.simulate_alert(frame, base_alert(), 0, 1, fine)
        self.assertEqual(result["final_result"], "+2R")

    def test_same_candle_target_first_without_reachable_breakeven_is_a_stop(self):
        # A stop so tight that the breakeven offset sits past +0.5R: the stop
        # never moves, so +0.5R then the stop inside one bar is a full SL,
        # not a breakeven exit at a level nobody could have placed.
        index = pd.DatetimeIndex(["2026-08-04 10:00", "2026-08-04 10:30"], tz=summary.IST)
        alert = base_alert()
        alert["stop_price"] = 99.78         # 0.22% risk; +0.5R = 100.11 < BE 100.12
        frame = pd.DataFrame(
            {"open": [101.0, 100.0], "high": [101.2, 100.15], "low": [100.8, 99.7],
             "close": [101.0, 99.8], "volume": [1, 1]},
            index=index,
        )
        fine = pd.DataFrame(
            {"open": [100.0, 100.1], "high": [100.15, 100.1], "low": [99.95, 99.7],
             "close": [100.1, 99.8], "volume": [1, 1]},
            index=pd.date_range("2026-08-04 10:30", periods=2, freq="1min", tz=summary.IST),
        )
        result = summary.simulate_alert(frame, alert, 0, 1, fine)
        self.assertEqual(result["final_result"], "SL")

    def test_report_shows_trades_settled_from_earlier_days(self):
        results = pd.DataFrame([
            {**base_alert(), "trade_id": tid, "filled": True, "outcome": res, "final_result": res,
             "net_realized_r": net, "entry_time": pd.Timestamp("2026-08-04 10:05", tz=summary.IST)}
            for tid, res, net in (("old", "SL", -1.1), ("new", "+2R", 1.9), ("still", "Pending", None))
        ])
        pending = pd.DataFrame([
            {"trade_id": "old", "report_date": datetime.date(2026, 8, 3)},
            {"trade_id": "still", "report_date": datetime.date(2026, 8, 3)},
        ])
        settled = summary.settled_from_earlier_days(results, pending, "2026-08-04")
        self.assertEqual(list(settled["trade_id"]), ["old"])
        records = pd.DataFrame([base_alert(trade_id="new")])
        message = summary.build_summary(
            records, "2026-08-04", results[results["trade_id"] == "new"], {}, 0, "4h", "crypto",
            settled_earlier=settled,
        )
        self.assertIn("Settled from earlier days 1 · -1.10R", message)

    def test_old_pending_row_with_a_different_id_is_still_the_same_delivery(self):
        moment = pd.Timestamp("2026-08-04 10:00:01.5", tz=summary.IST)
        records = pd.DataFrame([{"zone_id": "Z", "event_time_ist": moment, "trade_id": "scanner-id"},
                                {"zone_id": "Z", "event_time_ist": moment + pd.Timedelta(hours=1),
                                 "trade_id": "other"}])
        pending = pd.DataFrame([{"zone_id": "Z", "alert_time": moment.isoformat(), "trade_id": "stable-id"}])
        self.assertEqual(list(summary.same_delivery_as_pending(records, pending)), [True, False])

    def test_crypto_cost_is_delta_maker_in_taker_out_with_gst(self):
        self.assertAlmostEqual(summary.CRYPTO_ROUND_TRIP_COST_PCT, round((0.02 + 0.05) * 1.18, 4))

    def test_immature_rows_wait_in_pending_with_their_stop(self):
        alert = base_alert()
        alert["stop_price"] = 99.4
        row = summary.unfilled(alert, "immature")
        self.assertEqual(row["stop_price"], 99.4)
        with tempfile.TemporaryDirectory() as tmp:
            finalized = Path(tmp) / "f.jsonl"
            pending = Path(tmp) / "p.jsonl"
            payload = summary.lifecycle_payload(row, "2026-08-04", "4h", "crypto")
            summary.write_lifecycle_rows({payload["trade_id"]: payload}, finalized, pending)
            self.assertEqual(finalized.read_text(), "")
            stored = json.loads(pending.read_text())
            self.assertEqual(stored["stop_price"], 99.4)
            self.assertEqual(stored["timing_status"], "")

    def test_same_candle_resolution_accepts_timezone_naive_fine_data(self):
        index = pd.DatetimeIndex(["2026-08-04 10:00", "2026-08-04 10:30"], tz=summary.IST)
        frame = pd.DataFrame(
            {
                "open": [101.0, 100.0],
                "high": [101.2, 100.7],
                "low": [100.8, 98.8],
                "close": [101.0, 100.1],
                "volume": [1, 1],
            },
            index=index,
        )
        resolution_index = pd.date_range("2026-08-04 10:30", periods=2, freq="1min")
        resolution_frame = pd.DataFrame(
            {
                "open": [100.0, 99.5],
                "high": [100.7, 99.6],
                "low": [100.0, 98.8],
                "close": [100.4, 99.0],
                "volume": [1, 1],
            },
            index=resolution_index,
        )

        # The fine data shows +0.5R printing before the stop, so the stop
        # had already moved to entry - the trade exits flat, not at -1R.
        result = summary.simulate_alert(frame, base_alert(), 0, 1, resolution_frame)

        self.assertEqual(result["final_result"], summary.BREAK_EVEN)

    def test_mobile_summary_removes_tradable_be_and_verdict(self):
        records = pd.DataFrame(
            [
                base_alert(symbol="BTCUSDT", rating=4),
                base_alert(symbol="SBIN.NS", rating=6, side="short"),
            ]
        )
        results = pd.DataFrame(
            [
                {**records.iloc[0].to_dict(), "filled": True, "outcome": "+2R", "final_result": "+2R", "net_realized_r": 2.0},
                {**records.iloc[1].to_dict(), "filled": False, "outcome": "zone_not_touched", "final_result": "", "net_realized_r": float("nan")},
            ]
        )

        message = summary.build_summary(records, pd.Timestamp("2026-08-04").date(), results, {}, 0, "30m")

        self.assertIn("NSE 30m BACKTEST", message)
        self.assertIn("04 AUG 2026", message)
        self.assertIn("Alerts 2", message)
        self.assertIn("No Touch 1", message)
        self.assertIn("4/10 - 1 entries | +2R 1 | 100.0%", message)
        self.assertIn("No Entries - 6/10", message)
        # BEST/WORST were removed from the daily report; the weekly
        # one still carries them.
        self.assertNotIn("BEST", message)
        self.assertNotIn("Tradable", message)
        self.assertNotIn("BE:", message)
        self.assertNotIn("Verdict", message)

    def test_missing_rating_is_reported_as_unrated_not_rating_four(self):
        records = pd.DataFrame(
            [
                base_alert(symbol="LEGACY.NS", rating=float("nan")),
            ]
        )
        results = pd.DataFrame(
            [
                {
                    **records.iloc[0].to_dict(),
                    "filled": False,
                    "outcome": "zone_not_touched",
                    "final_result": "",
                    "net_realized_r": float("nan"),
                },
            ]
        )

        message = summary.build_summary(records, pd.Timestamp("2026-08-04").date(), results, {}, 0, "30m")

        self.assertIn("No Entries - Unrated/N/A", message)
        self.assertNotIn("4/10", message)

    def test_no_touch_excludes_data_errors(self):
        records = pd.DataFrame(
            [
                base_alert(symbol="A.NS", rating=5),
                base_alert(symbol="B.NS", rating=5),
                base_alert(symbol="C.NS", rating=5),
            ]
        )
        results = pd.DataFrame(
            [
                {**records.iloc[0].to_dict(), "filled": False, "outcome": "zone_not_touched", "final_result": "", "net_realized_r": float("nan")},
                {**records.iloc[1].to_dict(), "filled": False, "outcome": "data_missing", "final_result": "", "net_realized_r": float("nan")},
                {**records.iloc[2].to_dict(), "filled": False, "outcome": "alert_before_data", "final_result": "", "net_realized_r": float("nan")},
            ]
        )

        message = summary.build_summary(records, pd.Timestamp("2026-08-04").date(), results, {}, 0, "30m")

        self.assertIn("No Touch 1", message)

    def test_report_results_fall_back_to_report_date_when_trade_ids_change(self):
        target = pd.Timestamp("2026-08-04").date()
        records = pd.DataFrame(
            [
                {**base_alert(symbol="A.NS", rating=5), "trade_id": "current-a", "report_date": target},
                {**base_alert(symbol="B.NS", rating=6, side="short"), "trade_id": "current-b", "report_date": target},
            ]
        )
        results = pd.DataFrame(
            [
                {
                    **records.iloc[0].to_dict(),
                    "trade_id": "old-a",
                    "filled": False,
                    "outcome": "zone_not_touched",
                    "final_result": "",
                    "net_realized_r": float("nan"),
                    "report_date": target,
                },
                {
                    **records.iloc[1].to_dict(),
                    "trade_id": "old-b",
                    "filled": True,
                    "outcome": "+1R",
                    "final_result": "+1R",
                    "net_realized_r": 1.0,
                    "report_date": target,
                },
            ]
        )

        filtered = summary.report_results_for_current_day(results, records, target)
        message = summary.build_summary(records, target, filtered, {}, 0, "30m")

        self.assertEqual(len(filtered), 2)
        self.assertIn("No Touch 1", message)
        self.assertIn("No Touch 1", message)
        self.assertIn("Entries 1", message)
        self.assertIn("+1R 1", message)

    def test_report_excludes_a_repeat_delivery_that_really_belongs_to_yesterday(self):
        # stable_trade_id is keyed on the zone, not the delivery time, so a
        # still-open zone re-alerting today shares its trade_id with
        # yesterday's still-pending row for the same zone. Graded, that row
        # is persisted under the day it actually belongs to (yesterday) -
        # paper_trading's own comparison reads exactly that date - so this
        # report must not count the re-delivery as one of today's own
        # fresh entries, or Alerts/Entries/win rate silently double up a
        # trade that already existed.
        today = pd.Timestamp("2026-08-05").date()
        yesterday = pd.Timestamp("2026-08-04").date()
        records = pd.DataFrame(
            [
                # A genuinely new alert, first seen today.
                {**base_alert(symbol="A.NS", rating=5), "trade_id": "repeat-zone", "report_date": today},
                {**base_alert(symbol="B.NS", rating=6, side="short"), "trade_id": "fresh-today", "report_date": today},
            ]
        )
        results = pd.DataFrame(
            [
                {
                    # Same trade_id as the alert above, but this is the
                    # reconciled PENDING row - it belongs to yesterday.
                    **records.iloc[0].to_dict(),
                    "trade_id": "repeat-zone",
                    "filled": True,
                    "outcome": "+2R",
                    "final_result": "+2R",
                    "net_realized_r": 2.0,
                    "report_date": yesterday,
                },
                {
                    **records.iloc[1].to_dict(),
                    "trade_id": "fresh-today",
                    "filled": True,
                    "outcome": "+1R",
                    "final_result": "+1R",
                    "net_realized_r": 1.0,
                    "report_date": today,
                },
            ]
        )

        filtered = summary.report_results_for_current_day(results, records, today)

        self.assertEqual(list(filtered["trade_id"]), ["fresh-today"])

    def test_report_falls_back_to_report_date_when_every_id_match_is_a_repeat(self):
        # Same shape as above, but ALL of today's alerts turn out to be
        # repeats of older trades - nothing id-matched is genuinely today's.
        # Must fall through to the report_date fallback rather than quietly
        # returning the stale (yesterday-dated) id-matched rows.
        today = pd.Timestamp("2026-08-05").date()
        yesterday = pd.Timestamp("2026-08-04").date()
        records = pd.DataFrame(
            [{**base_alert(symbol="A.NS", rating=5), "trade_id": "repeat-zone", "report_date": today}]
        )
        results = pd.DataFrame(
            [
                {
                    **records.iloc[0].to_dict(),
                    "trade_id": "repeat-zone",
                    "filled": True,
                    "outcome": "+2R",
                    "final_result": "+2R",
                    "net_realized_r": 2.0,
                    "report_date": yesterday,
                }
            ]
        )

        filtered = summary.report_results_for_current_day(results, records, today)

        self.assertTrue(filtered.empty)

    def test_discord_payload_uses_embeds_without_truncating_long_reports(self):
        message = "\n".join([f"Line {index}" for index in range(900)])

        payload = summary.discord_payload(message)
        joined = "\n".join(embed["description"] for embed in payload["embeds"])

        self.assertEqual(joined, message)
        self.assertGreater(len(payload["embeds"]), 1)

    def test_discord_wait_url_requests_message_response(self):
        url = "https://discord.com/api/webhooks/123/token?foo=bar"

        self.assertEqual(
            summary.discord_wait_url(url),
            "https://discord.com/api/webhooks/123/token?foo=bar&wait=true",
        )

    def test_report_state_blocks_duplicate_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sent.json"
            key = summary.report_key(pd.Timestamp("2026-08-04").date(), "30m")

            self.assertNotIn(key, summary.load_sent_reports(path))
            summary.mark_sent_report(key, path)
            self.assertIn(key, summary.load_sent_reports(path))

    def test_crypto_report_key_does_not_collide_with_nse(self):
        day = pd.Timestamp("2026-08-04").date()
        self.assertNotEqual(
            summary.report_key(day, "30m", "nse"),
            summary.report_key(day, "30m", "crypto"),
        )

    def test_crypto_report_date_uses_ist_boundary_day(self):
        # Boundary is 04:00 IST, inside the scanner's own 01:00-08:00 dark
        # gap - no alert can fire there, so 02:00 (still the tail of the
        # prior session's dark hours) stays on the same calendar date and
        # anything from 04:00 onward rolls to the next one.
        small_hours = pd.Timestamp("2026-08-04 02:00", tz=summary.IST)
        evening = pd.Timestamp("2026-08-04 23:59", tz=summary.IST)

        self.assertEqual(summary.crypto_report_date(small_hours), pd.Timestamp("2026-08-04").date())
        self.assertEqual(summary.crypto_report_date(evening), pd.Timestamp("2026-08-05").date())

    def test_crypto_default_report_date_uses_completed_bucket(self):
        # Pinned past the 16:30 IST boundary. Reading the real clock
        # made this pass or fail depending on the time of day.
        now = pd.Timestamp("2026-08-23 18:00", tz=summary.IST)
        today = now.date()
        yesterday = today - pd.Timedelta(days=1)
        tomorrow = today + pd.Timedelta(days=1)
        records = pd.DataFrame(
            [
                {"report_date": yesterday},
                {"report_date": today},
                {"report_date": tomorrow},
            ]
        )

        self.assertEqual(
            summary.select_target_date(records, None, "crypto", "30m", now), today
        )

    def test_crypto_default_report_date_skips_when_no_bucket_is_complete(self):
        # Before the boundary (04:00 IST) the day is still running, so
        # there is nothing complete to report and the answer is None.
        now = pd.Timestamp("2026-08-23 02:00", tz=summary.IST)
        records = pd.DataFrame([{"report_date": now.date()}])

        self.assertIsNone(
            summary.select_target_date(records, None, "crypto", "4h", now)
        )

    def test_crypto_reports_the_day_once_its_bucket_closes(self):
        now = pd.Timestamp("2026-08-23 18:00", tz=summary.IST)
        records = pd.DataFrame([{"report_date": now.date()}])

        self.assertEqual(
            summary.select_target_date(records, None, "crypto", "4h", now),
            now.date(),
        )

    def test_nse_cutoff_uses_only_bars_ending_before_cutoff(self):
        index = pd.DatetimeIndex(
            [
                "2026-08-04 14:30",
                "2026-08-04 15:00",
            ],
            tz=summary.IST,
        )
        frame = pd.DataFrame(
            {
                "open": [100.0, 100.0],
                "high": [101.0, 130.0],
                "low": [99.0, 80.0],
                "close": [100.0, 100.0],
                "volume": [1, 1],
            },
            index=index,
        )

        end_index, mature = summary.same_day_tracking_end(
            frame,
            pd.Timestamp("2026-08-04 14:00", tz=summary.IST),
        )

        self.assertTrue(mature)
        self.assertEqual(end_index, 0)

    def test_nse_preopen_alert_cannot_fill_before_trade_start(self):
        index = pd.DatetimeIndex(
            [
                "2026-08-04 09:00",
                "2026-08-04 09:05",
                "2026-08-04 09:10",
                "2026-08-04 09:15",
            ],
            tz=summary.IST,
        )
        frame = pd.DataFrame(
            {
                "open": [101.0, 100.0, 100.0, 101.0],
                "high": [101.2, 100.2, 100.2, 101.5],
                "low": [100.8, 99.8, 99.8, 100.8],
                "close": [101.0, 100.1, 100.1, 101.2],
                "volume": [1, 1, 1, 1],
            },
            index=index,
        )

        result = summary.simulate_alert(
            frame,
            base_alert(event_time=index[0], event_time_ist=index[0]),
            0,
            len(frame) - 1,
        )

        self.assertEqual(result["outcome"], "zone_not_touched")

    def test_crypto_sl_before_half_r_is_sl(self):
        frame = crypto_frame(
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 100.2, 98.9, 99.1),
            ]
        )

        result = summary.simulate_alert(frame, crypto_alert(), 0, 1)

        self.assertEqual(result["final_result"], "SL")

    def test_crypto_half_r_then_reversal_exits_at_breakeven(self):
        frame = crypto_frame(
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 100.6, 100.0, 100.5),
                (100.5, 100.6, 99.7, 99.9),
            ]
        )

        result = summary.simulate_alert(frame, crypto_alert(), 0, 2, market="crypto")

        self.assertEqual(result["final_result"], summary.BREAK_EVEN)
        # Crypto pays charges too, so the stop moves past entry far enough
        # to cover them and the exit is a scratch (less the stop's slip)
        # rather than a loss the size of the round trip.
        self.assertAlmostEqual(result["net_realized_r"], 0.0, places=1)

    def test_crypto_reaching_one_r_then_reversing_exits_at_breakeven(self):
        frame = crypto_frame(
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 101.2, 100.0, 101.0),
                (101.0, 101.1, 99.7, 99.9),
            ]
        )

        result = summary.simulate_alert(frame, crypto_alert(), 0, 2)

        # Only +2R is an exit. Touching +1R and coming back is closed by the
        # breakeven stop, not credited a full 1R that was never banked.
        self.assertEqual(result["final_result"], summary.BREAK_EVEN)
        self.assertTrue(result["target_1_hit"])
        self.assertLess(result["realized_r"], 0.5)

    def test_crypto_one_r_at_the_time_limit_is_priced_at_the_close(self):
        frame = crypto_frame(
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 101.2, 100.0, 101.0),
                (101.0, 101.1, 100.5, 100.6),
            ]
        )

        result = summary.simulate_alert(frame, crypto_alert(), 0, 2)

        self.assertEqual(result["final_result"], "+1R")
        self.assertAlmostEqual(result["exit_price"], 100.6)
        self.assertLess(result["realized_r"], 1.0)

    def test_trail_shadow_follows_the_best_price(self):
        # Runs to 101.6, then falls back: the trail sits 0.25R under the
        # best price and the slipped stop there is the exit.
        frame = crypto_frame(
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 100.4, 100.0, 100.3),
                (100.3, 101.6, 100.3, 101.5),
                (101.5, 101.5, 100.5, 100.6),
            ]
        )

        result = summary.simulate_alert(frame, crypto_alert(), 0, 3)

        risk = result["entry_price"] - result["stop_price"]
        level = 101.6 - summary.TRAIL_DISTANCE_R * risk
        expected_exit = level * (1 - summary.SL_FILL_SLIPPAGE_PCT / 100)
        expected = (expected_exit - result["entry_price"]) / risk
        self.assertAlmostEqual(result["trail_net_r"], expected - result["cost_r"], places=6)
        self.assertGreater(result["trail_net_r"], 1.0)

    def test_trail_shadow_takes_the_full_stop_before_it_starts(self):
        frame = crypto_frame(
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 100.3, 98.8, 99.0),
            ]
        )

        result = summary.simulate_alert(frame, crypto_alert(), 0, 1)

        self.assertLess(result["trail_net_r"], -1.0)

    def test_crypto_two_r_stops_tracking(self):
        frame = crypto_frame(
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 102.2, 100.0, 102.0),
                (102.0, 102.1, 98.5, 99.0),
            ]
        )

        result = summary.simulate_alert(frame, crypto_alert(), 0, 2)

        self.assertEqual(result["final_result"], "+2R")
        self.assertEqual(result["exit_time"], frame.index[1])

    def test_crypto_expired_without_half_r_is_neither(self):
        frame = crypto_frame(
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 100.3, 100.0, 100.1),
                (100.1, 100.38, 99.8, 100.2),
                (100.2, 100.3, 99.8, 100.1),
                (100.1, 100.2, 99.8, 100.0),
                (100.0, 100.3, 99.8, 100.1),
                (100.1, 100.2, 99.8, 100.0),
                (100.0, 100.2, 99.8, 100.1),
                (100.1, 100.2, 99.8, 100.0),
                (100.0, 100.2, 99.8, 100.1),
                (100.1, 100.2, 99.8, 100.0),
                (100.0, 100.2, 99.8, 100.1),
                (100.1, 100.2, 99.8, 100.0),
                (100.0, 100.2, 99.8, 100.1),
            ]
        )

        result = summary.simulate_alert(frame, crypto_alert(), 0, len(frame) - 1)

        self.assertEqual(result["final_result"], "Neither")

    def test_crypto_open_trade_inside_six_hours_is_pending(self):
        future_start = (pd.Timestamp.now(tz=summary.IST) + pd.Timedelta(hours=1)).floor("30min")
        frame = crypto_frame(
            start=future_start,
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 100.3, 100.0, 100.1),
            ],
        )
        alert = crypto_alert(event_time=frame.index[0], event_time_ist=frame.index[0])

        result = summary.simulate_alert(frame, alert, 0, 1)

        self.assertEqual(result["final_result"], "Pending")

    def test_crypto_no_entry_waits_until_entry_window_closes(self):
        future_start = (pd.Timestamp.now(tz=summary.IST) + pd.Timedelta(hours=1)).floor("30min")
        frame = crypto_frame(
            start=future_start,
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (101.0, 101.2, 100.8, 101.0),
            ],
        )
        alert = crypto_alert(event_time=frame.index[0], event_time_ist=frame.index[0])

        result = summary.simulate_alert(frame, alert, 0, 1)

        self.assertEqual(result["outcome"], "immature")

    def test_crypto_tracking_is_not_forced_by_midnight(self):
        frame = crypto_frame(
            start="2026-08-04 23:00",
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 100.2, 100.0, 100.1),
                (100.1, 100.2, 99.8, 100.0),
                (100.0, 100.2, 99.8, 100.1),
                (100.1, 100.2, 99.8, 100.0),
                (100.0, 100.2, 99.8, 100.1),
                (100.1, 100.2, 99.8, 100.0),
                (100.0, 100.2, 99.8, 100.1),
                (100.1, 100.2, 99.8, 100.0),
                (100.0, 100.2, 99.8, 100.1),
                (100.1, 100.2, 99.8, 100.0),
                (100.0, 100.2, 99.8, 100.1),
                (100.1, 100.2, 99.8, 100.0),
                (100.0, 100.2, 99.8, 100.1),
            ],
        )

        result = summary.simulate_alert(frame, crypto_alert(event_time=frame.index[0], event_time_ist=frame.index[0]), 0, len(frame) - 1)

        self.assertEqual(result["final_result"], "Neither")
        self.assertGreater(result["exit_time"].date(), frame.index[0].date())

    def test_crypto_candle_starting_at_expiry_cannot_affect_result(self):
        rows = [(101.0, 101.2, 100.8, 101.0), (100.0, 100.2, 100.0, 100.1)]
        rows.extend([(100.1, 100.2, 99.8, 100.0)] * 23)
        rows.append((100.0, 103.0, 99.8, 102.5))
        frame = crypto_frame(start="2026-08-04 10:00", rows=rows)

        result = summary.simulate_alert(frame, crypto_alert(), 0, len(frame) - 1)

        self.assertEqual(result["final_result"], "Neither")
        self.assertLess(result["exit_time"], frame.index[-1])

    def test_xstock_trades_resolve_instead_of_waiting_forever(self):
        # Every xStock used to come back Pending, so the market totalled
        # 0.00R however it actually traded.
        frame = crypto_frame(
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 101.2, 100.0, 101.0),
            ]
        )

        result = summary.simulate_alert(frame, xstock_alert(), 0, 1)

        self.assertNotEqual(result["final_result"], "Pending")
        self.assertNotEqual(result.get("timing_status"), "xstock_timing_tbd")

    def test_xstock_open_trade_inside_six_hours_is_pending(self):
        future_start = (pd.Timestamp.now(tz=summary.IST) + pd.Timedelta(hours=1)).floor("30min")
        frame = crypto_frame(
            start=future_start,
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 100.3, 100.0, 100.1),
            ],
        )
        alert = xstock_alert(event_time=frame.index[0], event_time_ist=frame.index[0])

        result = summary.simulate_alert(frame, alert, 0, 1)

        self.assertEqual(result["final_result"], "Pending")

    def test_xstock_candle_starting_at_expiry_cannot_affect_result(self):
        rows = [(101.0, 101.2, 100.8, 101.0), (100.0, 100.2, 100.0, 100.1)]
        rows.extend([(100.1, 100.2, 99.8, 100.0)] * 23)
        rows.append((100.0, 103.0, 99.8, 102.5))
        frame = crypto_frame(start="2026-08-04 10:00", rows=rows)

        result = summary.simulate_alert(frame, xstock_alert(), 0, len(frame) - 1)

        # The rally arrives twelve hours after entry, well past the six-hour
        # horizon, so it must not be credited.
        self.assertNotIn(result["final_result"], {"+1R", "+2R"})

    def test_other_market_uses_the_same_six_hour_window_as_crypto(self):
        # SLVONUSD (market "other") was missing from uses_six_hour_evaluation():
        # run_backtest() already gives it the same provisional window as
        # crypto via crypto_tracking_end(), but simulate_alert() skipped the
        # real six-hour maturity gate and re-scope entirely, so a filled
        # trade could be graded within minutes of the alert instead of
        # after six real hours actually passed.
        future_start = (pd.Timestamp.now(tz=summary.IST) + pd.Timedelta(hours=1)).floor("30min")
        frame = crypto_frame(
            start=future_start,
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 100.3, 100.0, 100.1),
            ],
        )
        alert = other_alert(event_time=frame.index[0], event_time_ist=frame.index[0])

        result = summary.simulate_alert(frame, alert, 0, 1)

        self.assertEqual(result["final_result"], "Pending")

    def test_other_market_no_entry_waits_until_entry_window_closes(self):
        # Without the fix this graded "zone_not_touched" - a finished,
        # negative outcome - even though real time hadn't reached the end
        # of the provisional window yet.
        future_start = (pd.Timestamp.now(tz=summary.IST) + pd.Timedelta(hours=1)).floor("30min")
        frame = crypto_frame(
            start=future_start,
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (101.0, 101.2, 100.8, 101.0),
            ],
        )
        alert = other_alert(event_time=frame.index[0], event_time_ist=frame.index[0])

        result = summary.simulate_alert(frame, alert, 0, 1)

        self.assertEqual(result["outcome"], "immature")

    def test_finalized_records_include_stable_id_and_timing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            frame = crypto_frame(
                rows=[
                    (101.0, 101.2, 100.8, 101.0),
                    (100.0, 101.2, 100.0, 101.0),
                ]
            )
            result = summary.simulate_alert(frame, crypto_alert(), 0, 1)
            results = pd.DataFrame([result])

            summary.persist_finalized_records(
                pd.Timestamp("2026-08-04").date(),
                "30m",
                results,
                "crypto",
                path,
            )

            payload = __import__("json").loads(path.read_text(encoding="utf-8").strip())
            self.assertRegex(payload["trade_id"], r"^[0-9a-f]{16}$")
            self.assertEqual(payload["entry_time"], frame.index[1].isoformat())
            self.assertEqual(payload["time_to_half_r"], frame.index[1].isoformat())
            self.assertEqual(payload["time_to_1r"], frame.index[1].isoformat())
            self.assertIsNone(payload["time_to_2r"])
            # +1R is passed, not exited at, so the trade resolves when the
            # time limit closes it - the end of the last candle.
            self.assertEqual(
                payload["final_resolution_time"],
                (frame.index[1] + pd.Timedelta(minutes=30)).isoformat(),
            )

    def test_neither_resolution_time_uses_last_usable_candle_end(self):
        frame = crypto_frame(
            rows=[
                (101.0, 101.2, 100.8, 101.0),
                (100.0, 100.2, 100.0, 100.1),
                (100.1, 100.2, 99.8, 100.0),
            ]
        )

        result = summary.simulate_alert(frame, crypto_alert(), 0, 2)

        self.assertEqual(result["final_result"], "Neither")
        self.assertEqual(result["final_resolution_time"], frame.index[2] + pd.Timedelta(minutes=30))

    def test_format_rating_table_handles_no_results_yet(self):
        records = pd.DataFrame([
            {"symbol": "BTCUSDT", "rating": 7},
        ])
        results = pd.DataFrame()

        table = summary.format_rating_table(records, results)

        self.assertIsInstance(table, str)
        self.assertIn("7/10", table)

    def test_display_symbol_simplifies_common_forms(self):
        cases = {
            "TCS.NS": "TCS",
            "AAPL.USD": "AAPL",
            "AAPLXUSD": "AAPL",
            "AVGO/USDT:USDT": "AVGO",
            "BTCUSDT": "BTC",
            "BTC/USD": "BTC",
            "BTC-USD": "BTC",
            "MSTRBUSD": "MSTR",
        }
        for raw, expected in cases.items():
            self.assertEqual(summary.display_symbol(raw), expected)





class EvaluationDataConfigTests(unittest.TestCase):
    """Backtest evaluation runs on fine candles regardless of the alert's
    timeframe, and keeps enough of them that a multi-day run is not
    silently truncated to a few sessions.
    """

    def test_both_timeframes_evaluate_on_five_minute_candles(self):
        for timeframe in ("30m", "4h"):
            self.assertEqual(
                summary.TIMEFRAME_SETTINGS[timeframe]["eval_interval"], "5m"
            )

    def test_evaluation_keeps_more_bars_than_the_live_scanner(self):
        import nse_scanner

        original = nse_scanner.OHLCV_LIMIT
        try:
            summary.configure_nse_data("30m")
            self.assertEqual(nse_scanner.OHLCV_LIMIT, summary.EVALUATION_OHLCV_LIMIT)
            # ~75 five-minute bars per NSE session, so this must clear a
            # couple of weeks rather than the ~7 sessions 500 would give.
            self.assertGreater(summary.EVALUATION_OHLCV_LIMIT / 75, 20)
        finally:
            nse_scanner.OHLCV_LIMIT = original

class DataWindowTests(unittest.TestCase):
    # Yahoo serves intraday history for a limited window per interval and
    # fails the whole request past it, rather than returning what it has.
    MAX_DAYS = {"1m": 7, "5m": 60, "15m": 60, "30m": 60, "1h": 730}

    def test_every_timeframe_asks_for_a_window_its_interval_can_serve(self):
        # 4h asked for 700 days of 5m candles - a leftover from when it
        # evaluated on 1h - so every symbol came back empty and the whole
        # report read as data issues.
        for timeframe, settings in summary.TIMEFRAME_SETTINGS.items():
            with self.subTest(timeframe=timeframe):
                interval = settings["eval_interval"]
                period = settings["source_period"]
                self.assertTrue(period.endswith("d"), period)
                self.assertLessEqual(
                    int(period[:-1]),
                    self.MAX_DAYS[interval],
                    f"{timeframe} asks for {period} of {interval} candles",
                )

class QuietDayTests(unittest.TestCase):
    def test_the_note_names_the_market_timeframe_and_last_report(self):
        line = summary.quiet_day_line("2026-08-23", "4h", "xstock")

        self.assertIn("XSTOCK", line)
        self.assertIn("4h", line)
        self.assertIn("23 AUG 2026", line)
        self.assertNotIn(chr(10), line)

    def test_the_key_moves_with_today_not_the_reported_date(self):
        # A quiet timeframe keeps reporting the same old date for days.
        # Keying on that would post the note once and then go silent
        # again, which is the problem it exists to solve.
        first = summary.quiet_day_key(
            "4h", "xstock", datetime.date(2026, 8, 24)
        )
        second = summary.quiet_day_key(
            "4h", "xstock", datetime.date(2026, 8, 25)
        )

        self.assertNotEqual(first, second)

    def test_it_cannot_collide_with_a_real_report_key(self):
        real = summary.report_key("2026-08-24", "4h", "xstock")
        quiet = summary.quiet_day_key(
            "4h", "xstock", datetime.date(2026, 8, 24)
        )

        self.assertNotEqual(real, quiet)

class ClosedMarketTests(unittest.TestCase):
    SATURDAY = "2026-08-29 16:30"
    WEDNESDAY = "2026-08-26 16:30"

    def _records(self, day):
        return pd.DataFrame([{"report_date": day}])

    def test_no_nse_note_at_the_weekend(self):
        # A Saturday quiet note went out saying nothing new had happened,
        # on a day nothing could have happened.
        saturday = pd.Timestamp(self.SATURDAY, tz=summary.IST)
        records = self._records(pd.Timestamp(self.WEDNESDAY, tz=summary.IST).date())

        self.assertFalse(summary.market_traded_today("nse", records, saturday))

    def test_a_weekday_with_no_alerts_reads_as_a_holiday(self):
        # The scanner delivers 58-75 NSE alerts on a normal session, so a
        # weekday with none is a closed market rather than a quiet one.
        wednesday = pd.Timestamp(self.WEDNESDAY, tz=summary.IST)

        self.assertFalse(
            summary.market_traded_today("nse", pd.DataFrame(), wednesday)
        )

    def test_a_normal_session_still_reports(self):
        wednesday = pd.Timestamp(self.WEDNESDAY, tz=summary.IST)
        records = self._records(wednesday.date())

        self.assertTrue(summary.market_traded_today("nse", records, wednesday))

    def test_crypto_is_never_closed(self):
        saturday = pd.Timestamp(self.SATURDAY, tz=summary.IST)

        for market in ("crypto", "xstock", "other"):
            with self.subTest(market=market):
                self.assertTrue(
                    summary.market_traded_today(market, pd.DataFrame(), saturday)
                )

class RepeatDeliveryTests(unittest.TestCase):
    def _write(self, directory, rows):
        path = Path(directory) / "records.jsonl"
        path.write_text(
            "\n".join(json.dumps(row) for row in rows), encoding="utf-8"
        )
        return path

    def _record(self, when, top, symbol="TCS.NS"):
        return {
            "delivered_at_utc": when,
            "symbol": symbol,
            "timeframe": "30m",
            "side": "long",
            "alert_price": 100.0,
            "distance_pct": 0.05,
            "level": 99.0,
            "zone_bottom": 99.0,
            "zone_top": top,
            "planned_entry": top,
            "stop_price": 98.9,
        }

    def test_one_zone_realerted_all_day_is_one_trade(self):
        # The scanner re-alerts a live zone every scan and its edges drift
        # in the far decimals as ATR moves, so an exact match never caught
        # them: 44% of eight days of NSE records were the same zone again.
        rows = [
            self._record("2026-08-26T04:00:00+00:00", 100.17203103477016),
            self._record("2026-08-26T04:20:00+00:00", 100.17210107412592),
            self._record("2026-08-26T04:40:00+00:00", 100.17203142238878),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            frame = summary.load_records(self._write(tmp, rows), "30m")

        self.assertEqual(len(frame), 1)

    def test_the_same_level_on_a_later_session_is_its_own_trade(self):
        rows = [
            self._record("2026-08-26T04:00:00+00:00", 100.172),
            self._record("2026-08-27T04:00:00+00:00", 100.172),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            frame = summary.load_records(self._write(tmp, rows), "30m")

        self.assertEqual(len(frame), 2)

    def test_crypto_same_level_within_six_hours_is_one_trade(self):
        rows = [
            self._record("2026-08-26T17:45:00+00:00", 100.172, symbol="HYPEUSD"),
            self._record("2026-08-26T19:15:00+00:00", 100.1720001, symbol="HYPEUSD"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            frame = summary.load_records(self._write(tmp, rows), "30m")

        self.assertEqual(len(frame), 1)

    def test_crypto_same_level_after_six_hours_is_new_trade(self):
        rows = [
            self._record("2026-08-26T04:00:00+00:00", 100.172, symbol="HYPEUSD"),
            self._record("2026-08-26T10:30:00+00:00", 100.1720001, symbol="HYPEUSD"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            frame = summary.load_records(self._write(tmp, rows), "30m")

        self.assertEqual(len(frame), 2)

    def test_a_genuinely_different_zone_survives(self):
        rows = [
            self._record("2026-08-26T04:00:00+00:00", 100.172),
            self._record("2026-08-26T04:20:00+00:00", 101.500),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            frame = summary.load_records(self._write(tmp, rows), "30m")

        self.assertEqual(len(frame), 2)

    def test_the_first_delivery_is_the_one_kept(self):
        # The first is the one the user could have acted on.
        rows = [
            self._record("2026-08-26T04:00:00+00:00", 100.172),
            self._record("2026-08-26T04:20:00+00:00", 100.1720001),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            frame = summary.load_records(self._write(tmp, rows), "30m")

        self.assertEqual(len(frame), 1)
        kept = pd.Timestamp(frame.iloc[0]["event_time"]).tz_convert("UTC")
        self.assertEqual(kept.hour, 4)
        self.assertEqual(kept.minute, 0)

    def test_a_venue_flipped_repeat_is_still_caught_as_one_trade(self):
        # A venue flip shifts a real zone's edges
        # by up to ~0.7%, measured on the real alert log - far past an
        # exact/6-sig-fig match but still the same trade. bottom AND top
        # both drift here, not just top like the exact-match tests above.
        rows = [
            self._record("2026-08-26T17:45:00+00:00", 100.0, symbol="HYPEUSD"),
            {**self._record("2026-08-26T18:15:00+00:00", 100.3, symbol="HYPEUSD"), "zone_bottom": 99.3},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            frame = summary.load_records(self._write(tmp, rows), "30m")

        self.assertEqual(len(frame), 1)

    def test_a_genuinely_different_zone_survives_even_with_drift_tolerance(self):
        # 5% apart is well past the 1% tolerance - two real, distinct zones.
        rows = [
            self._record("2026-08-26T17:45:00+00:00", 100.0, symbol="HYPEUSD"),
            {**self._record("2026-08-26T18:15:00+00:00", 105.0, symbol="HYPEUSD"), "zone_bottom": 104.0},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            frame = summary.load_records(self._write(tmp, rows), "30m")

        self.assertEqual(len(frame), 2)

    def test_nse_edge_drift_within_a_session_is_still_one_trade(self):
        # NSE has no venue flip, but the comment on load_records() says the
        # scanner's ATR-driven edges drift scan to scan too - same-day NSE
        # dedup needs the same tolerance, not just crypto's.
        rows = [
            self._record("2026-08-26T04:00:00+00:00", 100.0),
            {**self._record("2026-08-26T04:20:00+00:00", 100.4), "zone_bottom": 99.4},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            frame = summary.load_records(self._write(tmp, rows), "30m")

        self.assertEqual(len(frame), 1)


class DeltaVenueTests(unittest.TestCase):
    """The backtest grades trades on Delta - where they are taken - first."""

    DELTA_ROWS = [[1_780_000_000_000, 100.0, 101.0, 99.0, 100.5, 10.0]]
    OTHER_ROWS = [[1_780_000_000_000, 90.0, 91.0, 89.0, 90.5, 10.0]]

    def test_delta_candles_are_used_before_any_other_exchange(self):
        with patch.object(
            summary.crypto_scanner, "fetch_delta_ohlcv", return_value=self.DELTA_ROWS
        ), patch.object(
            summary.crypto_scanner, "require_fresh_ohlcv", side_effect=lambda rows, name: rows
        ), patch.object(
            summary.crypto_scanner,
            "fetch_exchange_ohlcv",
            side_effect=AssertionError("another exchange was asked while Delta had the data"),
        ):
            rows = summary.crypto_fetch_ohlcv("NVDAXUSD")

        self.assertEqual(rows, self.DELTA_ROWS)

    def test_a_non_delta_symbol_falls_through_to_the_old_chain(self):
        with patch.object(
            summary.crypto_scanner, "fetch_delta_ohlcv", return_value=None
        ), patch.object(
            summary.crypto_scanner, "require_fresh_ohlcv", side_effect=lambda rows, name: rows
        ), patch.object(
            summary.crypto_scanner, "fetch_exchange_ohlcv", return_value=self.OTHER_ROWS
        ):
            rows = summary.crypto_fetch_ohlcv("SOMECOIN/USDT")

        self.assertEqual(rows, self.OTHER_ROWS)

    def test_a_delta_outage_falls_back_instead_of_failing_the_report(self):
        with patch.object(
            summary.crypto_scanner, "fetch_delta_ohlcv", side_effect=RuntimeError("delta down")
        ), patch.object(
            summary.crypto_scanner, "require_fresh_ohlcv", side_effect=lambda rows, name: rows
        ), patch.object(
            summary.crypto_scanner, "fetch_exchange_ohlcv", return_value=self.OTHER_ROWS
        ):
            rows = summary.crypto_fetch_ohlcv("BTCUSD")

        self.assertEqual(rows, self.OTHER_ROWS)

    def test_delta_window_fetch_returns_only_candles_inside_the_window(self):
        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"success": True, "result": [
                    {"time": 1000, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 3},
                    {"time": 1060, "open": 1.5, "high": 2.5, "low": 1, "close": 2, "volume": 4},
                    {"time": 1120, "open": 2, "high": 3, "low": 1.5, "close": 2.5, "volume": 5},
                ]}

        start = pd.Timestamp(1000, unit="s", tz="UTC")
        end = pd.Timestamp(1120, unit="s", tz="UTC")  # end is exclusive
        with patch.object(summary.crypto_scanner, "is_delta_symbol", return_value=True), \
                patch.object(summary.requests, "get", return_value=Resp()) as get:
            rows = summary.delta_fetch_window("NVDAXUSD", "1m", start, end)

        self.assertEqual([row[0] for row in rows], [1_000_000, 1_060_000])
        self.assertEqual(get.call_args.kwargs["params"]["resolution"], "1m")
        self.assertEqual(get.call_args.kwargs["params"]["start"], 1000)

    def test_delta_window_fetch_skips_a_symbol_delta_does_not_list(self):
        with patch.object(summary.crypto_scanner, "is_delta_symbol", return_value=False):
            self.assertIsNone(
                summary.delta_fetch_window(
                    "X/USDT", "1m",
                    pd.Timestamp("2026-09-01", tz=summary.IST),
                    pd.Timestamp("2026-09-02", tz=summary.IST),
                )
            )

    def test_tie_break_candles_come_from_delta_too(self):
        rows = [[1_780_000_000_000, 1, 2, 0.5, 1.5, 1]]
        with patch.object(summary, "delta_fetch_window", return_value=rows):
            got = summary.crypto_fetch_resolution_ohlcv(
                "BTCUSD",
                start=pd.Timestamp("2026-09-01 10:00", tz=summary.IST),
                end=pd.Timestamp("2026-09-01 10:30", tz=summary.IST),
            )

        self.assertEqual(got, rows)

    def test_xstocks_can_now_be_tie_broken_instead_of_staying_ambiguous(self):
        rows = [
            [1_780_000_000_000, 1, 2, 0.5, 1.5, 1],
            [1_780_000_060_000, 1.5, 2, 1, 1.8, 1],
        ]
        with patch.object(summary, "crypto_fetch_resolution_ohlcv", return_value=rows):
            frames, failures = summary.fetch_resolution_frames(["NVDAXUSD"], "xstock")

        self.assertIn("NVDAXUSD", frames)
        self.assertEqual(failures, {})


class MarketClassTests(unittest.TestCase):
    def test_every_watchlist_symbol_lands_in_its_market(self):
        # XAUT replaced PAXG on the watchlist but was graded as crypto until
        # 2026-10-09: market_class still named PAXG.
        import config
        for symbol in config.OTHER_WATCHLIST:
            self.assertEqual(summary.market_class(symbol), summary.MARKET_OTHER, symbol)
        for symbol in config.XSTOCK_WATCHLIST:
            self.assertEqual(summary.market_class(symbol), summary.MARKET_XSTOCK, symbol)
        for symbol in config.CRYPTO_WATCHLIST:
            self.assertEqual(summary.market_class(symbol), summary.MARKET_CRYPTO, symbol)
        self.assertEqual(summary.market_class("RELIANCE.NS"), summary.MARKET_NSE)


class OutcomeLabelTests(unittest.TestCase):
    def test_the_internal_ambiguous_name_never_reaches_a_report(self):
        # A dry run caught this leaking as data_quality_ambiguous into
        # the summary line while the rating block said Ambiguous.
        records = pd.DataFrame([{
            "symbol": "TCS.NS", "side": "long", "rating": 8,
            "event_time_ist": pd.Timestamp("2026-08-28 09:15", tz=summary.IST),
        }])
        results = records.copy()
        results["filled"] = [True]
        results["outcome"] = [summary.DATA_QUALITY_AMBIGUOUS]
        results["final_result"] = [summary.DATA_QUALITY_AMBIGUOUS]
        results["net_realized_r"] = [0.0]

        message = summary.build_summary(
            records, pd.Timestamp("2026-08-28").date(), results, {}, 0, "30m", "nse"
        )

        self.assertNotIn(summary.DATA_QUALITY_AMBIGUOUS, message)
        self.assertIn("Ambiguous", message)



class StopTooTightTests(unittest.TestCase):
    def test_charges_over_half_a_risk_unit_is_too_tight(self):
        # crypto fee 0.10% of 100 = 0.10; a 0.15 risk makes that 0.67R
        self.assertTrue(summary.stop_too_tight(100.0, 99.85, 1.0, "crypto"))
        self.assertTrue(summary.stop_too_tight(100.0, 100.15, -1.0, "crypto"))

    def test_a_normal_stop_is_left_alone(self):
        self.assertFalse(summary.stop_too_tight(100.0, 99.5, 1.0, "crypto"))
        self.assertFalse(summary.stop_too_tight(100.0, 100.5, -1.0, "crypto"))

    def test_a_micro_stop_is_not_taken_instead_of_losing_multiple_r(self):
        alert = crypto_alert(
            zone_bottom=99.98, zone_top=100.0, body_entry=100.0,
            planned_entry=100.0, stop_price=99.98,
        )
        index = pd.date_range("2026-08-04 10:00", periods=4, freq="5min", tz=summary.IST)
        frame = pd.DataFrame(
            {
                "open": [101.0, 100.0, 99.0, 99.0],
                "high": [101.2, 100.1, 99.5, 99.5],
                "low": [100.8, 99.0, 98.5, 98.5],
                "close": [101.0, 99.5, 99.0, 99.0],
                "volume": [1, 1, 1, 1],
            },
            index=index,
        )
        result = summary.simulate_alert(frame, alert, 0, 3, market="crypto")
        self.assertFalse(result["filled"])
        self.assertEqual(result["outcome"], "stop_too_tight")


class CooldownDtypeTests(unittest.TestCase):
    def test_cooldown_writes_text_into_all_nan_float_columns(self):
        # A day whose fills carry NaN in final_result / timing_status makes
        # those columns float64; pandas 3 then rejects the "" that the
        # zone_cooldown replacement writes, which crashed a whole report group.
        rows = []
        for minute in (0, 5):
            rows.append(
                {
                    "symbol": "AAPLXUSD",
                    "side": "long",
                    "filled": True,
                    "trade_id": f"t{minute}",
                    "entry_time": pd.Timestamp(f"2026-09-01 10:{minute:02d}", tz=summary.IST),
                    "zone_bottom": 99.0,
                    "zone_top": 100.0,
                    "final_result": float("nan"),
                    "timing_status": float("nan"),
                    "net_realized_r": 1.0,
                }
            )
        results, blocked = summary.apply_same_day_zone_cooldown(pd.DataFrame(rows), "xstock")
        self.assertEqual(blocked, 1)
        self.assertEqual(list(results["outcome"].fillna("")).count("zone_cooldown"), 1)


class FillCandleTests(unittest.TestCase):
    """Targets count from the candle after the fill, never the fill candle itself."""

    def setUp(self):
        # entry 96, stop 95 (1R = 1.0). Bar 1 runs up to 98.6 (+2.6R) BEFORE
        # dropping to fill at 96; afterwards price never clears 96.4.
        self.index = pd.date_range("2026-08-04 10:00", periods=6, freq="5min", tz=summary.IST)
        self.alert = base_alert(
            zone_bottom=95.2, zone_top=96.0, body_entry=96.0, planned_entry=96.0, stop_price=95.0
        )

    def frame(self, later_high=96.4, fill_open=97.0):
        return pd.DataFrame(
            {
                "open": [97.0, fill_open, 96.1, 96.1, 96.1, 96.1],
                "high": [97.2, 98.6, later_high, 96.4, 96.4, 96.4],
                "low": [96.8, 95.95, 95.9, 95.9, 95.9, 95.9],
                "close": [97.0, 96.1, 96.2, 96.2, 96.2, 96.2],
                "volume": [1] * 6,
            },
            index=self.index,
        )

    def test_a_target_on_the_fill_candle_is_not_credited(self):
        result = summary.simulate_alert(self.frame(), self.alert, 0, 5)
        self.assertEqual(result["final_result"], "Neither")
        self.assertLess(result["mfe_r"], 0.5)

    def test_a_target_on_the_next_candle_is_credited(self):
        result = summary.simulate_alert(self.frame(later_high=98.1), self.alert, 0, 5)
        self.assertEqual(result["final_result"], "+2R")

    def test_a_candle_that_opens_at_the_entry_fills_first(self):
        result = summary.simulate_alert(self.frame(fill_open=96.0), self.alert, 0, 5)
        self.assertEqual(result["final_result"], "+2R")

    def test_the_stop_still_counts_on_the_fill_candle(self):
        frame = self.frame()
        frame.iloc[1, frame.columns.get_loc("low")] = 94.8
        result = summary.simulate_alert(frame, self.alert, 0, 5)
        self.assertEqual(result["final_result"], "SL")


class PendingStopTests(unittest.TestCase):
    def test_a_pending_trade_keeps_the_alerts_stop(self):
        frame = crypto_frame(rows=[(101.0, 101.2, 100.8, 101.0), (100.0, 100.6, 100.0, 100.5)])
        alert = crypto_alert(stop_price=99.25)
        pending = summary.pending_trade(alert, frame, 1, 100.0)
        self.assertEqual(pending["stop_price"], 99.25)
        self.assertEqual(summary.original_stop_price(pending), 99.25)


class TradeIdTests(unittest.TestCase):
    def test_results_carry_the_scanners_trade_id(self):
        frame = crypto_frame(rows=[(101.0, 101.2, 100.8, 101.0), (100.0, 100.6, 100.0, 100.5)])
        alert = crypto_alert(stop_price=99.25)
        alert["trade_id"] = "scanner-id-1"
        self.assertEqual(summary.pending_trade(alert, frame, 1, 100.0)["trade_id"], "scanner-id-1")
        self.assertEqual(summary.unfilled(alert, "zone_not_touched")["trade_id"], "scanner-id-1")

    def test_records_without_one_fall_back_to_the_stable_id(self):
        alert = crypto_alert(stop_price=99.25)
        alert.pop("trade_id", None)
        self.assertEqual(summary.alert_trade_id(alert), summary.stable_trade_id(alert))


class CryptoEvaluationCandleTests(unittest.TestCase):
    def test_crypto_is_graded_on_five_minute_candles(self):
        saved = summary.crypto_scanner.TIMEFRAME, summary.crypto_scanner.OHLCV_LIMIT
        self.addCleanup(lambda: setattr(summary.crypto_scanner, "TIMEFRAME", saved[0]))
        self.addCleanup(lambda: setattr(summary.crypto_scanner, "OHLCV_LIMIT", saved[1]))
        for timeframe in ("30m", "4h"):
            summary.configure_crypto_data(timeframe)
            self.assertEqual(summary.crypto_scanner.TIMEFRAME, "5m")
            self.assertEqual(summary.crypto_scanner.OHLCV_LIMIT, summary.EVALUATION_OHLCV_LIMIT)

    def test_a_4h_alerts_window_covers_its_whole_entry_window(self):
        index = pd.date_range("2026-08-04 00:00", periods=30 * 12, freq="5min", tz=summary.IST)
        frame = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=index)
        event = index[0]
        end_30m, _ = summary.crypto_tracking_end(frame, event, "30m")
        end_4h, _ = summary.crypto_tracking_end(frame, event, "4h")
        # 90-minute entry window + 6 hours of evaluation after it.
        self.assertEqual(frame.index[end_30m], event + pd.Timedelta(hours=7, minutes=30))
        # 12-hour entry window + 6 hours of evaluation after it.
        self.assertEqual(frame.index[end_4h], event + pd.Timedelta(hours=18))


if __name__ == "__main__":
    unittest.main()


class NseQuietNoteTests(unittest.TestCase):
    def test_a_30m_alert_today_marks_nse_open_for_the_4h_note(self):
        wednesday = pd.Timestamp("2026-08-05 16:00", tz=summary.IST)
        with tempfile.TemporaryDirectory() as tmp:
            path_30m = Path(tmp) / "nse30.jsonl"
            path_4h = Path(tmp) / "nse4h.jsonl"
            path_30m.write_text(json.dumps({
                "symbol": "TCS.NS", "timeframe": "30m", "side": "long",
                "delivered_at_utc": "2026-08-05T05:00:00+00:00",
                "zone_bottom": 99.0, "zone_top": 100.0,
            }) + "\n", encoding="utf-8")
            settings = {
                "30m": dict(summary.TIMEFRAME_SETTINGS["30m"], nse_records=path_30m),
                "4h": dict(summary.TIMEFRAME_SETTINGS["4h"], nse_records=path_4h),
            }
            with patch.object(summary, "TIMEFRAME_SETTINGS", settings):
                self.assertTrue(summary.nse_alerted_today_on_any_timeframe("nse", wednesday))
                self.assertFalse(
                    summary.nse_alerted_today_on_any_timeframe("nse", wednesday + pd.Timedelta(days=1))
                )


class AmbiguousRerunTests(unittest.TestCase):
    """Re-running only the ambiguous rows gives exactly the full re-run's answer."""

    def _case(self, seed):
        import numpy as np

        rng = np.random.default_rng(seed)
        frames, fine, alerts = {}, {}, []
        for s in range(4):
            symbol = f"S{s}.NS"
            idx = pd.date_range("2026-08-04 09:15", periods=24, freq="15min", tz=summary.IST)
            close = 100 + np.cumsum(rng.normal(0, 0.6, len(idx)))
            open_ = np.r_[close[0], close[:-1]]
            high = np.maximum(open_, close) + rng.uniform(0.2, 1.5, len(idx))
            low = np.minimum(open_, close) - rng.uniform(0.2, 1.5, len(idx))
            frames[symbol] = pd.DataFrame(
                {"open": open_, "high": high, "low": low, "close": close, "volume": 1.0}, index=idx
            )
            fidx = pd.date_range(idx[0], idx[-1] + pd.Timedelta(minutes=14), freq="1min", tz=summary.IST)
            fc = np.interp(np.arange(len(fidx)), np.arange(0, len(fidx), 15)[: len(close)], close)
            fine[symbol] = pd.DataFrame(
                {"open": fc, "high": fc + 0.05, "low": fc - 0.05, "close": fc, "volume": 1.0}, index=fidx
            )
            for a in range(3):
                t = idx[int(rng.integers(1, 8))]
                level = float(close[0] + rng.normal(0, 1))
                side = "long" if rng.random() < 0.5 else "short"
                bottom, top = level - 0.5, level + 0.5
                alerts.append(base_alert(
                    symbol=symbol, side=side, event_time=t, event_time_ist=t,
                    zone_bottom=bottom, zone_top=top, body_entry=top if side == "long" else bottom,
                    stop_price=(bottom - 0.3) if side == "long" else (top + 0.3),
                    zone_id=f"{symbol}|{side}|{bottom:.8f}|{top:.8f}|{a}",
                ))
        return pd.DataFrame(alerts), frames, fine

    def test_rerun_matches_the_full_second_pass(self):
        ambiguous_seen = 0
        for seed in range(40):
            alerts, frames, fine = self._case(seed)
            full, _ = summary.run_backtest(alerts, frames, "nse", resolution_frames=fine)
            rows = summary.simulate_alerts(alerts, frames, "nse")
            ambiguous_seen += sum(r.get("final_result") == summary.DATA_QUALITY_AMBIGUOUS for r in rows)
            rows = summary.rerun_ambiguous(alerts, rows, frames, "nse", fine)
            fast, _ = summary.apply_same_day_zone_cooldown(pd.DataFrame(rows), "nse")
            pd.testing.assert_frame_equal(full.reset_index(drop=True), fast.reset_index(drop=True))
        self.assertGreater(ambiguous_seen, 0)
