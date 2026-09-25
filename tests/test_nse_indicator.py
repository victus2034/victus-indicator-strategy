import unittest
from unittest.mock import patch

import pandas as pd

import nse_scanner


class NseIndicatorParityTests(unittest.TestCase):
    # The ATR, pivot, zone-geometry, touch-veto and zone-break tests that used to
    # live here pinned NSE's private copy of the zone engine (a fixed ATR band, a
    # plain "drop the oldest" buffer, a close-through break). NSE no longer has
    # one: it uses the crypto scanner's, which tests/test_indicator_scanner_parity.py
    # holds to the Pine indicator and tests/test_six_worked_examples.py holds to
    # six hand-measured charts. tests/test_nse_shares_crypto_engine.py pins that
    # the two really are the same functions with the same numbers.

    def test_30m_resample_is_anchored_to_nse_open(self):
        index = pd.date_range("2026-07-22 09:15", periods=4, freq="15min", tz="Asia/Kolkata")
        data = pd.DataFrame(
            {
                "open": [10.0, 11.0, 12.0, 13.0],
                "high": [11.0, 12.0, 13.0, 14.0],
                "low": [9.0, 10.0, 11.0, 12.0],
                "close": [10.5, 11.5, 12.5, 13.5],
                "volume": [1, 2, 3, 4],
            },
            index=index,
        )

        with (
            patch.object(nse_scanner, "TIMEFRAME", "30m"),
            patch.object(nse_scanner, "SOURCE_INTERVAL", "15m"),
        ):
            result = nse_scanner.resample_for_timeframe(data)

        self.assertEqual(list(result.index.minute), [15, 45])
        self.assertEqual(result.iloc[0]["open"], 10.0)
        self.assertEqual(result.iloc[0]["close"], 11.5)
        self.assertEqual(result.iloc[0]["volume"], 3)

    def test_4h_resample_is_anchored_to_nse_open(self):
        index = pd.date_range("2026-07-22 09:15", periods=8, freq="1h", tz="Asia/Kolkata")
        data = pd.DataFrame(
            {
                "open": range(10, 18),
                "high": range(11, 19),
                "low": range(9, 17),
                "close": [value + 0.5 for value in range(10, 18)],
                "volume": [1] * 8,
            },
            index=index,
        )

        with (
            patch.object(nse_scanner, "TIMEFRAME", "4h"),
            patch.object(nse_scanner, "SOURCE_INTERVAL", "1h"),
        ):
            result = nse_scanner.resample_for_timeframe(data)

        self.assertEqual(list(result.index), list(index[[0, 4]]))
        self.assertEqual(result.iloc[0]["open"], 10)
        self.assertEqual(result.iloc[0]["close"], 13.5)
        self.assertEqual(result.iloc[0]["volume"], 4)

    def test_incomplete_candle_is_excluded_from_indicator(self):
        data = pd.DataFrame(
            {
                "Datetime": pd.to_datetime(
                    ["2026-07-22 09:15", "2026-07-22 09:45"]
                ).tz_localize("Asia/Kolkata"),
                "close": [100.0, 101.0],
            }
        )
        now = pd.Timestamp("2026-07-22 10:00", tz="Asia/Kolkata")

        with patch.object(nse_scanner, "TIMEFRAME", "30m"):
            result = nse_scanner.confirmed_candles(data, now=now)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[-1]["close"], 100.0)

    def test_hourly_download_uses_bounded_explicit_range(self):
        now = pd.Timestamp("2026-07-22 16:00", tz="UTC")

        with patch.object(nse_scanner, "SOURCE_INTERVAL", "1h"):
            result = nse_scanner.yfinance_time_range(now=now)

        self.assertNotIn("period", result)
        self.assertEqual(result["end"] - result["start"], pd.Timedelta(days=700))


if __name__ == "__main__":
    unittest.main()
