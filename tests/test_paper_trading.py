import unittest
from unittest.mock import patch

import pandas as pd

import daily_backtest_summary as backtest
import paper_trading


IST = paper_trading.IST
# Mid-session: before the 15:10 cut-off, so fills are allowed.
NOW = pd.Timestamp("2026-08-17 11:00", tz=paper_trading.IST)


def bars(rows, start="2026-08-17 10:00"):
    index = pd.date_range(start, periods=len(rows), freq="5min", tz=IST)
    return pd.DataFrame(rows, index=index, columns=["high", "low", "close"])


def alert(side="long", entry=100.0, stop=98.0, delivered="2026-08-17 09:55", trade_id="t1"):
    return {
        "symbol": "TCS.NS",
        "timeframe": "30m",
        "side": side,
        "score": 8,
        "trade_id": trade_id,
        "_entry": entry,
        "_stop": stop,
        "_delivered": pd.Timestamp(delivered, tz=IST),
    }


def fresh_state():
    return {"open": {}, "closed": [], "handled": {}}


class FillTests(unittest.TestCase):
    def test_position_opens_only_when_price_reaches_entry(self):
        state = fresh_state()
        # Never trades down to 100, so a resting buy limit never fills.
        frames = {"TCS.NS": bars([[101.5, 100.8, 101.0], [101.2, 100.5, 100.9]])}
        self.assertEqual(paper_trading.open_new_positions(state, [alert()], frames, NOW), [])
        self.assertEqual(state["open"], {})

        frames = {"TCS.NS": bars([[101.5, 100.8, 101.0], [101.0, 99.5, 99.8]])}
        opened = paper_trading.open_new_positions(state, [alert()], frames, NOW)
        self.assertEqual(len(opened), 1)
        self.assertAlmostEqual(state["open"][opened[0]]["entry"], 100.0)

    def test_bars_before_the_alert_cannot_fill_it(self):
        state = fresh_state()
        # The touch happens at 10:00, but the alert only landed at 10:30.
        frames = {"TCS.NS": bars([[101.0, 99.0, 99.5]])}
        opened = paper_trading.open_new_positions(
            state, [alert(delivered="2026-08-17 10:30")], frames, NOW
        )
        self.assertEqual(opened, [])

    def test_a_filled_alert_is_not_reopened(self):
        state = fresh_state()
        frames = {"TCS.NS": bars([[101.0, 99.5, 99.8]])}
        paper_trading.open_new_positions(state, [alert()], frames, NOW)
        state["open"].clear()  # simulate it having closed
        self.assertEqual(paper_trading.open_new_positions(state, [alert()], frames, NOW), [])

    def test_the_same_zone_re_alerted_with_a_different_scanner_trade_id_opens_once(self):
        # The scanner's own "trade_id" embeds delivered_at_utc, so it is
        # unique on every single delivery even when it is the same real
        # zone re-alerted (which daily_backtest_summary.load_records()
        # measured as 44% of NSE deliveries). Preferring that field here
        # used to open a fresh paper position for each re-alert of the same
        # zone, overcounting against the backtest.
        state = fresh_state()
        frames = {"TCS.NS": bars([[101.0, 99.5, 99.8]])}
        first = alert(trade_id="scan-run-1")
        second = alert(trade_id="scan-run-2", delivered="2026-08-17 09:56")

        opened_first = paper_trading.open_new_positions(state, [first], frames, NOW)
        opened_second = paper_trading.open_new_positions(state, [second], frames, NOW)

        self.assertEqual(len(opened_first), 1)
        self.assertEqual(opened_second, [])
        self.assertEqual(len(state["open"]), 1)


class OutcomeTests(unittest.TestCase):
    def _open(self, side="long", entry=100.0, stop=98.0):
        state = fresh_state()
        frames = {"TCS.NS": bars([[100.5, 99.9, 100.0]])}
        paper_trading.open_new_positions(
            state, [alert(side=side, entry=entry, stop=stop)], frames, NOW
        )
        return state

    def test_stop_closes_with_slippage_worse_than_minus_one_r(self):
        state = self._open()
        frames = {"TCS.NS": bars([[100.2, 97.5, 97.8]])}
        closed = paper_trading.evaluate_open_positions(
            state, frames, pd.Timestamp("2026-08-17 11:00", tz=IST)
        )
        self.assertEqual(closed[0]["outcome"], "SL")
        self.assertLess(closed[0]["realized_r"], -1.0)

    def test_target_two_closes_at_plus_two_r(self):
        state = self._open()
        frames = {"TCS.NS": bars([[104.5, 100.0, 104.0]])}
        closed = paper_trading.evaluate_open_positions(
            state, frames, pd.Timestamp("2026-08-17 11:00", tz=IST)
        )
        self.assertEqual(closed[0]["outcome"], "+2R")
        self.assertAlmostEqual(closed[0]["realized_r"], 2.0)

    def test_stop_and_target_in_one_bar_is_reported_ambiguous(self):
        state = self._open()
        frames = {"TCS.NS": bars([[102.5, 97.5, 100.0]])}
        closed = paper_trading.evaluate_open_positions(
            state, frames, pd.Timestamp("2026-08-17 11:00", tz=IST)
        )
        self.assertEqual(closed[0]["outcome"], backtest.DATA_QUALITY_AMBIGUOUS)
        self.assertIsNone(closed[0]["realized_r"])

    def test_unresolved_position_squares_off_at_1510_not_market_close(self):
        state = self._open()
        frames = {"TCS.NS": bars([[100.4, 99.8, 99.7]], start="2026-08-17 10:00")}
        # Before 15:10 the position must stay open.
        self.assertEqual(
            paper_trading.evaluate_open_positions(
                state, frames, pd.Timestamp("2026-08-17 14:00", tz=IST)
            ),
            [],
        )
        closed = paper_trading.evaluate_open_positions(
            state, frames, pd.Timestamp("2026-08-17 15:10", tz=IST)
        )
        self.assertEqual(closed[0]["outcome"], "Neither")
        # Priced off the real close, so a drift against the position is a
        # small loss rather than a free breakeven.
        self.assertLess(closed[0]["realized_r"], 0.0)

    def test_still_open_at_square_off_is_priced_off_the_real_close(self):
        # Touched +0.5R but never came back to entry and never reached +1R,
        # so it is still open at 15:10 and exits at whatever it is actually
        # worth - not a flat +0.5R credit.
        state = self._open()
        frames = {"TCS.NS": bars([[101.2, 99.9, 100.1]])}
        closed = paper_trading.evaluate_open_positions(
            state, frames, pd.Timestamp("2026-08-17 15:10", tz=IST)
        )
        self.assertEqual(closed[0]["outcome"], "Neither")
        self.assertAlmostEqual(closed[0]["realized_r"], 0.05)

    def test_half_r_moves_the_stop_past_entry_to_clear_costs(self):
        # Reaching +0.5R moves the stop above entry rather than closing the
        # trade, far enough to cover the round trip - so giving it back
        # scratches a hair positive instead of losing the charges. Paper
        # must match daily_backtest_summary or the two measure different
        # strategies.
        state = self._open()
        frames = {"TCS.NS": bars([[101.2, 99.9, 100.1], [100.0, 97.0, 97.2]])}
        closed = paper_trading.evaluate_open_positions(
            state, frames, pd.Timestamp("2026-08-17 11:00", tz=IST)
        )
        self.assertEqual(closed[0]["outcome"], backtest.BREAK_EVEN)
        self.assertGreater(closed[0]["net_realized_r"], 0.0)
        self.assertLess(closed[0]["net_realized_r"], 0.05)

    def test_a_stop_before_any_milestone_still_closes_as_sl(self):
        state = self._open()
        frames = {"TCS.NS": bars([[100.2, 97.0, 97.2], [101.5, 100.0, 101.2]])}
        closed = paper_trading.evaluate_open_positions(
            state, frames, pd.Timestamp("2026-08-17 11:00", tz=IST)
        )
        self.assertEqual(closed[0]["outcome"], "SL")

    def test_price_action_after_1510_cannot_decide_the_trade(self):
        # yfinance keeps printing to 15:25, but the user is flat by 15:10 -
        # a stop that only trades after the cut-off never happened to them.
        state = self._open()
        frames = {
            "TCS.NS": pd.DataFrame(
                [[100.4, 99.8, 100.0], [100.2, 97.0, 97.5]],
                index=pd.DatetimeIndex(
                    ["2026-08-17 15:05", "2026-08-17 15:15"], tz=IST
                ),
                columns=["high", "low", "close"],
            )
        }
        only_trade_id = next(iter(state["open"]))
        state["open"][only_trade_id]["entry_time"] = "2026-08-17 15:05:00+05:30"
        closed = paper_trading.evaluate_open_positions(
            state, frames, pd.Timestamp("2026-08-17 15:30", tz=IST)
        )
        self.assertEqual(closed[0]["outcome"], "Neither")

    def test_short_side_stop_and_target_mirror_the_long_side(self):
        state = self._open(side="short", entry=100.0, stop=102.0)
        frames = {"TCS.NS": bars([[102.5, 100.0, 102.2]])}
        closed = paper_trading.evaluate_open_positions(
            state, frames, pd.Timestamp("2026-08-17 11:00", tz=IST)
        )
        self.assertEqual(closed[0]["outcome"], "SL")

        state = self._open(side="short", entry=100.0, stop=102.0)
        frames = {"TCS.NS": bars([[100.1, 95.5, 96.0]])}
        closed = paper_trading.evaluate_open_positions(
            state, frames, pd.Timestamp("2026-08-17 11:00", tz=IST)
        )
        self.assertEqual(closed[0]["outcome"], "+2R")


class PaperWindowTests(unittest.TestCase):
    def test_window_stays_open_past_1510_so_square_off_can_run(self):
        # The cron fires at 15:10 but the runner needs a minute or two to
        # boot. A guard that closed at 15:10 would reject the tick that
        # squares off the day's open positions, orphaning them.
        monday = "2026-08-17"
        self.assertTrue(
            paper_trading.in_paper_window(pd.Timestamp(f"{monday} 15:12", tz=IST))
        )
        self.assertTrue(
            paper_trading.in_paper_window(pd.Timestamp(f"{monday} 10:00", tz=IST))
        )
        self.assertFalse(
            paper_trading.in_paper_window(pd.Timestamp(f"{monday} 09:00", tz=IST))
        )
        self.assertFalse(
            paper_trading.in_paper_window(pd.Timestamp(f"{monday} 16:30", tz=IST))
        )

    def test_no_fill_after_1510_even_inside_the_grace_tail(self):
        state = fresh_state()
        frames = {
            "TCS.NS": pd.DataFrame(
                [[101.0, 99.0, 99.5]],
                index=pd.DatetimeIndex(["2026-08-17 15:15"], tz=IST),
                columns=["high", "low", "close"],
            )
        }
        opened = paper_trading.open_new_positions(
            state, [alert()], frames, pd.Timestamp("2026-08-17 15:20", tz=IST)
        )
        self.assertEqual(opened, [])


class ReportTests(unittest.TestCase):
    def _stats(self, entries, wins, decided, total):
        return {"entries": entries, "wins": wins, "decided": decided, "total_r": total}

    def test_report_states_plainly_when_nothing_closed(self):
        with patch.object(paper_trading, "backtest_day_stats", lambda *a, **k: None):
            message = paper_trading.build_report("2026-08-17", "30m", fresh_state())

        self.assertIn("Nothing closed", message)

    def test_one_row_per_market_and_timeframe(self):
        state = fresh_state()
        state["closed"] = [
            {"date": "2026-08-17", "market": "crypto", "timeframe": "30m",
             "outcome": "+1R", "net_realized_r": 1.0, "symbol": "BTCUSDT"},
            {"date": "2026-08-17", "market": "crypto", "timeframe": "30m",
             "outcome": "SL", "net_realized_r": -1.04, "symbol": "ETHUSDT"},
            {"date": "2026-08-16", "market": "crypto", "timeframe": "30m",
             "outcome": "+2R", "net_realized_r": 2.0, "symbol": "SOLUSDT"},
        ]
        with patch.object(paper_trading, "backtest_day_stats", lambda *a, **k: None):
            message = paper_trading.build_report("2026-08-17", "30m", state)

        self.assertIn("CRYPTO 30m", message)
        # The 16 Aug row belongs to another day.
        self.assertIn("2 · 50.0% · -0.04R", message)
        self.assertNotIn("NSE", message)

    def test_the_gap_is_paper_minus_backtest(self):
        state = fresh_state()
        state["closed"] = [
            {"date": "2026-08-17", "market": "crypto", "timeframe": "30m",
             "outcome": "SL", "net_realized_r": -2.0, "symbol": "BTCUSDT"},
        ]
        reference = self._stats(1, 1, 1, 1.0)
        with patch.object(
            paper_trading, "backtest_day_stats",
            lambda d, t, market="nse": reference if market == "crypto" else None,
        ):
            message = paper_trading.build_report("2026-08-17", "30m", state)

        self.assertIn("-3.00R", message)

    def test_markets_that_did_nothing_are_left_out(self):
        state = fresh_state()
        state["closed"] = [
            {"date": "2026-08-17", "market": "crypto", "timeframe": "30m",
             "outcome": "+1R", "net_realized_r": 1.0, "symbol": "BTCUSDT"},
        ]
        with patch.object(paper_trading, "backtest_day_stats", lambda *a, **k: None):
            message = paper_trading.build_report("2026-08-17", "30m", state)

        self.assertNotIn("XSTOCK", message)
        self.assertNotIn("4h", message)



class CommandLineTests(unittest.TestCase):
    def test_the_scheduled_invocation_parses(self):
        # The workflow runs exactly this. The choices used to be derived
        # from entry_confirm.ALERT_RECORDS, so adding a market layer to
        # that dict turned them into {crypto, nse} and every scheduled
        # tick died on its own default.
        for timeframe in ("30m", "4h"):
            with self.subTest(timeframe=timeframe):
                args = paper_trading.parse_args(
                    ["--tick", "--timeframe", timeframe]
                )
                self.assertEqual(args.timeframe, timeframe)
                self.assertTrue(args.tick)




def summary_cutoff():
    import daily_backtest_summary as backtest

    return backtest.NSE_BACKTEST_CLOSE_CUTOFF


class CryptoPaperTests(unittest.TestCase):
    def test_crypto_follows_the_alert_window_not_market_hours(self):
        # NSE closes; crypto does not. Applying the 09:15-16:00 guard to
        # crypto would silence it for most of the day.
        saturday = pd.Timestamp("2026-08-29 22:00", tz=paper_trading.IST)

        self.assertFalse(paper_trading.paper_window_open("nse", saturday))
        self.assertTrue(paper_trading.paper_window_open("crypto", saturday))

    def test_crypto_is_quiet_outside_the_alert_window(self):
        # Nothing alerts between 01:00 and 08:00, so nothing can fill.
        night = pd.Timestamp("2026-08-29 04:00", tz=paper_trading.IST)

        self.assertFalse(paper_trading.paper_window_open("crypto", night))

    def test_nse_is_judged_to_the_square_off_and_crypto_to_six_hours(self):
        # Diverging from the backtest here would compare two different
        # strategies rather than one strategy against live prices.
        now = pd.Timestamp("2026-08-28 11:00", tz=paper_trading.IST)
        entry = pd.Timestamp("2026-08-28 10:00", tz=paper_trading.IST)

        nse_end = paper_trading.horizon_end("nse", entry, now)
        crypto_end = paper_trading.horizon_end("crypto", entry, now)

        self.assertEqual(nse_end.time(), summary_cutoff())
        self.assertEqual(crypto_end - entry, pd.Timedelta(hours=6))

class MarketScopeTests(unittest.TestCase):
    def test_a_crypto_run_files_xstocks_under_xstock(self):
        # The crypto alert records carry xStocks too, so a run told
        # "crypto" covers both - which is what the user means by the
        # word. Stamping the flag would leave the xStock row empty.
        self.assertEqual(paper_trading.market_of("AAPLXUSD", "crypto"), "xstock")
        self.assertEqual(paper_trading.market_of("BTCUSDT", "crypto"), "crypto")

    def test_an_nse_run_stays_nse(self):
        self.assertEqual(paper_trading.market_of("TCS.NS", "nse"), "nse")

    def test_paxg_and_slvon_are_not_lost(self):
        # Neither crypto nor an xStock, but they trade, so their results
        # have to land somewhere visible.
        self.assertEqual(paper_trading.market_of("PAXG/USDT", "crypto"), "other")
        self.assertIn("other", [m for m, _ in paper_trading.MARKETS])

    def test_both_timeframes_are_reported(self):
        state = fresh_state()
        state["closed"] = [
            {"date": "2026-08-28", "market": "crypto", "timeframe": "30m",
             "outcome": "+1R", "net_realized_r": 1.0, "symbol": "BTCUSDT"},
            {"date": "2026-08-28", "market": "crypto", "timeframe": "4h",
             "outcome": "SL", "net_realized_r": -1.0, "symbol": "ETHUSDT"},
        ]
        with patch.object(paper_trading, "backtest_day_stats", lambda *a, **k: None):
            message = paper_trading.build_report("2026-08-28", "both", state)

        self.assertIn("CRYPTO 30m", message)
        self.assertIn("CRYPTO 4h", message)



class EntryWaitTests(unittest.TestCase):
    def test_wait_is_three_bars_of_the_alerts_own_timeframe(self):
        t = pd.Timestamp("2026-09-10 10:00", tz="UTC")
        self.assertEqual(paper_trading.entry_wait_end(t, "30m"), t + pd.Timedelta(minutes=90))
        self.assertEqual(paper_trading.entry_wait_end(t, "4h"), t + pd.Timedelta(hours=12))

    def test_unknown_timeframe_falls_back_to_30m(self):
        t = pd.Timestamp("2026-09-10 10:00", tz="UTC")
        self.assertEqual(paper_trading.entry_wait_end(t, "??"), t + pd.Timedelta(minutes=90))


class ReportDayTests(unittest.TestCase):
    """The comparison must ask for the same day the backtest reports.

    The backtest files crypto, xStock and "other" under a session day
    (CRYPTO_REPORT_BOUNDARY, 04:00 IST) while a closed paper trade stores the
    calendar day it was entered. When the daily report moved to 07:30 it asked
    for "today" - a day with no trading yet - so every paper column came back
    empty and last night's session, filed under yesterday, went unreported.
    """

    # Shaped like a real closed trade from the live state file.
    EVENING_TRADE = {
        "alert_time": "2026-09-22T19:51:27.159747+05:30",
        "entry_time": "2026-09-22T19:55:00+05:30",
        "date": "2026-09-22",
        "market": "crypto",
        "timeframe": "30m",
        "outcome": "+1R",
        "net_realized_r": 0.9,
        "symbol": "ETHUSD",
    }

    def test_an_evening_trade_is_reported_under_the_next_session_day(self):
        self.assertEqual(paper_trading.paper_report_date(self.EVENING_TRADE), "2026-09-23")

    def test_a_trade_after_midnight_stays_in_the_same_session_day(self):
        # 00:30 is still the tail of the session that began the evening
        # before, and sits before the 04:00 boundary.
        row = {**self.EVENING_TRADE, "alert_time": "2026-09-23T00:30:00+05:30"}
        self.assertEqual(paper_trading.paper_report_date(row), "2026-09-23")

    def test_it_lands_on_the_same_day_as_its_backtest_twin(self):
        alert_time = pd.Timestamp(self.EVENING_TRADE["alert_time"])
        self.assertEqual(
            paper_trading.paper_report_date(self.EVENING_TRADE),
            backtest.crypto_report_date(alert_time).isoformat(),
        )

    def test_nse_stays_a_calendar_day(self):
        row = {**self.EVENING_TRADE, "market": "nse"}
        self.assertEqual(paper_trading.paper_report_date(row), "2026-09-22")

    def test_a_row_without_a_timestamp_keeps_its_stored_date(self):
        row = {"market": "crypto", "date": "2026-09-22"}
        self.assertEqual(paper_trading.paper_report_date(row), "2026-09-22")

    def test_last_nights_paper_trade_shows_in_the_0730_report(self):
        state = fresh_state()
        state["closed"] = [dict(self.EVENING_TRADE)]
        with patch.object(paper_trading, "backtest_day_stats", lambda *a, **k: None):
            message = paper_trading.build_report("2026-09-23", "30m", state)
        self.assertIn("CRYPTO 30m", message)
        self.assertNotIn("Nothing closed", message)

    def test_default_days_at_0730_are_last_nights_session_and_the_prior_nse_day(self):
        # Wednesday 07:32: the crypto bucket closed at 04:00, NSE has not opened.
        dates = paper_trading.default_report_dates(pd.Timestamp("2026-09-23 07:32", tz=IST))
        self.assertEqual(dates["crypto"], "2026-09-23")
        self.assertEqual(dates["xstock"], "2026-09-23")
        self.assertEqual(dates["nse"], "2026-09-22")

    def test_before_the_boundary_the_crypto_day_is_still_yesterdays(self):
        dates = paper_trading.default_report_dates(pd.Timestamp("2026-09-23 03:00", tz=IST))
        self.assertEqual(dates["crypto"], "2026-09-22")

    def test_monday_morning_reports_fridays_nse_session(self):
        dates = paper_trading.default_report_dates(pd.Timestamp("2026-09-21 07:32", tz=IST))
        self.assertEqual(dates["nse"], "2026-09-18")
        self.assertEqual(dates["crypto"], "2026-09-21")

    def test_after_the_nse_session_the_nse_day_is_today(self):
        dates = paper_trading.default_report_dates(pd.Timestamp("2026-09-23 16:30", tz=IST))
        self.assertEqual(dates["nse"], "2026-09-23")

    def test_a_row_for_a_different_day_is_labelled(self):
        state = fresh_state()
        state["closed"] = [{
            "date": "2026-09-22", "market": "nse", "timeframe": "30m",
            "outcome": "+1R", "net_realized_r": 1.0, "symbol": "TCS.NS",
        }]
        with patch.object(paper_trading, "backtest_day_stats", lambda *a, **k: None):
            message = paper_trading.build_report(
                "2026-09-23", "30m", state, {"nse": "2026-09-22", "crypto": "2026-09-23"}
            )
        self.assertIn("NSE 30m (22 Sep)", message)



if __name__ == "__main__":
    unittest.main()
