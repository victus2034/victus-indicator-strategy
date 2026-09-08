"""Every venue in the chain must be able to hand back a live price.

EXCHANGES_BY_ID holds ccxt exchanges only, so live_ticker_price used to return
the candle close - silently - on CoinSwitch and Delta, which are the two venues
the production chain reaches first. Both scan_30m.yml and entry_confirm.yml set
VICTUS_USE_LIVE_TICKER=true, so both were running on a stale price while their
configuration said otherwise.
"""
import time
import unittest
from unittest.mock import patch

import scanner


class LiveTickerCoversEveryVenue(unittest.TestCase):
    def setUp(self):
        scanner._FINE_PRICES.clear()

    tearDown = setUp

    def test_disabled_always_returns_the_candle_close(self):
        with patch.object(scanner, "USE_LIVE_TICKER", False):
            scanner._remember_fine_price("DOGEUSD", [[0, 0, 0, 0, 0.0917, 0]])
            self.assertEqual(
                scanner.live_ticker_price("coinswitch", "DOGEUSD", 0.0899),
                (0.0899, "candle_close"),
            )

    def test_coinswitch_uses_the_price_the_top_up_already_fetched(self):
        with patch.object(scanner, "USE_LIVE_TICKER", True):
            scanner._remember_fine_price("DOGEUSD", [[0, 0, 0, 0, 0.09169, 0]])
            price, source = scanner.live_ticker_price("coinswitch", "DOGEUSD", 0.090989)
        self.assertEqual(source, "coinswitch_fine")
        self.assertAlmostEqual(price, 0.09169)

    def test_a_stale_fine_price_is_not_a_live_price(self):
        with patch.object(scanner, "USE_LIVE_TICKER", True):
            scanner._FINE_PRICES["DOGEUSD"] = (time.time() - 3600, 0.09169)
            self.assertEqual(
                scanner.live_ticker_price("coinswitch", "DOGEUSD", 0.090989),
                (0.090989, "candle_close"),
            )

    def test_a_fine_price_belongs_only_to_its_own_symbol(self):
        with patch.object(scanner, "USE_LIVE_TICKER", True):
            scanner._remember_fine_price("DOGEUSD", [[0, 0, 0, 0, 0.09169, 0]])
            self.assertEqual(
                scanner.live_ticker_price("coinswitch", "BTCUSD", 79000.0),
                (79000.0, "candle_close"),
            )

    def test_a_zero_or_broken_fine_candle_is_ignored(self):
        with patch.object(scanner, "USE_LIVE_TICKER", True):
            for bad in ([], [[0, 0, 0, 0, 0.0, 0]], [[0, 0, 0, 0, "n/a", 0]], [[0]]):
                scanner._FINE_PRICES.clear()
                scanner._remember_fine_price("DOGEUSD", bad)
                self.assertEqual(
                    scanner.live_ticker_price("coinswitch", "DOGEUSD", 0.0899),
                    (0.0899, "candle_close"),
                    bad,
                )

    def test_delta_uses_its_own_ticker(self):
        with patch.object(scanner, "USE_LIVE_TICKER", True), \
             patch.object(scanner, "fetch_delta_ticker_price", return_value=79082.5):
            self.assertEqual(
                scanner.live_ticker_price("delta_india", "BTCUSD", 78000.0),
                (79082.5, "delta_ticker"),
            )

    def test_a_failing_delta_ticker_falls_back_rather_than_raising(self):
        with patch.object(scanner, "USE_LIVE_TICKER", True), \
             patch.object(scanner, "fetch_delta_ticker_price", side_effect=RuntimeError("down")):
            self.assertEqual(
                scanner.live_ticker_price("delta_india", "BTCUSD", 78000.0),
                (78000.0, "candle_close"),
            )

    def test_a_ccxt_venue_still_uses_its_ticker(self):
        with patch.object(scanner, "USE_LIVE_TICKER", True), \
             patch.object(scanner, "fetch_exchange_ticker", return_value={"last": 79100.0}):
            self.assertEqual(
                scanner.live_ticker_price("binance", "BTCUSD", 78000.0),
                (79100.0, "live_ticker"),
            )

    def test_an_unknown_venue_falls_back(self):
        with patch.object(scanner, "USE_LIVE_TICKER", True):
            self.assertEqual(
                scanner.live_ticker_price("some_new_venue", "BTCUSD", 78000.0),
                (78000.0, "candle_close"),
            )


class DeltaTickerParsing(unittest.TestCase):
    def response(self, payload, status=200):
        class Fake:
            status_code = status

            def raise_for_status(self):
                if status >= 400:
                    raise RuntimeError(status)

            def json(self):
                return payload

        return Fake()

    def test_prefers_close_then_mark_then_spot(self):
        cases = [
            ({"close": 10.0, "mark_price": "11", "spot_price": "12"}, 10.0),
            ({"mark_price": "11", "spot_price": "12"}, 11.0),
            ({"spot_price": "12"}, 12.0),
        ]
        for result, expected in cases:
            with patch.object(
                scanner.requests, "get",
                return_value=self.response({"success": True, "result": result}),
            ):
                self.assertEqual(scanner.fetch_delta_ticker_price("BTCUSD"), expected)

    def test_an_unsuccessful_payload_raises(self):
        with patch.object(
            scanner.requests, "get",
            return_value=self.response({"success": False, "error": "no such symbol"}),
        ):
            with self.assertRaises(RuntimeError):
                scanner.fetch_delta_ticker_price("NOPEUSD")


if __name__ == "__main__":
    unittest.main()
