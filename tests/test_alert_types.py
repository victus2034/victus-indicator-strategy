"""Alerts are S/R zones, fibs and trendlines only (lakky, 2026-10-10)."""
import unittest

import config
import nse_config
import nse_scanner
import scanner


class RangeFilterOffTests(unittest.TestCase):
    def test_range_filter_alerts_are_off_for_crypto_and_nse(self):
        self.assertFalse(config.ALERT_RANGE_FILTER_SIGNALS)
        self.assertFalse(nse_config.ALERT_RANGE_FILTER_SIGNALS)

    def test_a_range_filter_signal_sends_nothing(self):
        result = {"symbol": "BTCUSD", "price": 100.0}
        self.assertFalse(scanner.process_signal_candidate({}, result, "buy", 1_000_000))
        self.assertFalse(nse_scanner.process_signal_candidate({}, {**result, "symbol": "TCS.NS"}, "buy", 1_000_000))


if __name__ == "__main__":
    unittest.main()
