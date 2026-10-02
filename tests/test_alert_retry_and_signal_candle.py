import unittest
from unittest.mock import patch

import pandas as pd

import nse_scanner
import scanner


class AlertDueTests(unittest.TestCase):
    """A failed send retries soon; a delivered one waits out the cooldown."""

    def test_delivered_alert_waits_for_the_cooldown(self):
        entry = {"in_zone": True, "last_alert_at": 1000.0, "last_attempt_at": 1000.0}
        self.assertFalse(scanner.alert_due(entry, 1000.0 + 3600, 4 * 3600))
        self.assertTrue(scanner.alert_due(entry, 1000.0 + 4 * 3600, 4 * 3600))

    def test_failed_send_retries_after_the_short_wait_not_the_cooldown(self):
        entry = {"in_zone": True, "last_alert_at": 0.0, "last_attempt_at": 1000.0}
        retry = scanner.FAILED_ALERT_RETRY_SECONDS
        self.assertFalse(scanner.alert_due(entry, 1000.0 + retry - 1, 4 * 3600))
        self.assertTrue(scanner.alert_due(entry, 1000.0 + retry, 4 * 3600))

    def test_nse_zone_retries_after_a_failed_send(self):
        state = {}
        result = {"symbol": "TCS.NS", "price": 100.0}
        zone = {"bottom": 99.0, "top": 99.9, "created_idx": 1}
        with (
            patch.object(nse_scanner, "stop_too_wide", return_value=False),
            patch.object(nse_scanner, "format_alert", return_value="msg"),
            patch.object(nse_scanner, "record_delivered_zone_alert"),
            patch.object(nse_scanner, "send_alert", side_effect=[False, True]) as send,
        ):
            self.assertFalse(nse_scanner.process_candidate(state, result, "demand", zone, 0.1, 1000.0))
            self.assertTrue(
                nse_scanner.process_candidate(
                    state, result, "demand", zone, 0.1, 1000.0 + scanner.FAILED_ALERT_RETRY_SECONDS
                )
            )
        self.assertEqual(send.call_count, 2)


class ConfirmedCandleTests(unittest.TestCase):
    def _frame(self, last_open_s):
        return pd.DataFrame(
            {
                "time": [(last_open_s - 1800) * 1000, last_open_s * 1000],
                "open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0],
            }
        )

    def test_forming_candle_is_dropped(self):
        df = self._frame(10_000)
        out = scanner.confirmed_candles(df, now_ts=10_000 + 600, timeframe="30m")
        self.assertEqual(len(out), 1)

    def test_closed_candle_is_kept(self):
        df = self._frame(10_000)
        out = scanner.confirmed_candles(df, now_ts=10_000 + 1800, timeframe="30m")
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
