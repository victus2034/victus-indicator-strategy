"""The Bitunix candle source: off by default, opt-in per crypto symbol, Delta behind it."""
import time
import unittest
from unittest.mock import patch

import bitunix_data
import config
import fib_trendline_data
import scanner


def _row(ts_s, price=100.0):
    return {"time": str(ts_s * 1000), "open": str(price), "high": str(price + 1),
            "low": str(price - 1), "close": str(price), "baseVol": "5", "quoteVol": "500"}


class FakeBitunix:
    """Serves the API's real shape: newest first, at most `limit`, ending at endTime."""

    def __init__(self, first, last, step):
        self.series = list(range(first, last + 1, step))
        self.calls = []

    def __call__(self, pair, interval, start_ms, end_ms, limit, attempts=3):
        self.calls.append((pair, interval, start_ms, end_ms))
        inside = [ts for ts in self.series if start_ms <= ts * 1000 <= end_ms]
        return [_row(ts) for ts in reversed(inside[-limit:])]


class DefaultTests(unittest.TestCase):
    def test_default_source_is_bitunix(self):
        self.assertEqual(config.CRYPTO_CANDLE_SOURCE, "bitunix")

    def test_delta_setting_turns_it_off(self):
        with patch.object(bitunix_data, "CRYPTO_CANDLE_SOURCE", "delta"):
            self.assertFalse(bitunix_data.uses_bitunix("BTCUSD"))

    def test_every_crypto_symbol_maps_to_a_bitunix_pair(self):
        pairs = {s: bitunix_data.bitunix_pair(scanner.delta_contract(s)) for s in config.CRYPTO_WATCHLIST}
        self.assertEqual(pairs["BTCUSD"], "BTCUSDT")
        self.assertEqual(pairs["HUSD"], "HUSDT")
        self.assertEqual(pairs["TRUMP/USDT"], "TRUMPUSDT")
        self.assertTrue(all(p.endswith("USDT") for p in pairs.values()))


class OnTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(bitunix_data, "CRYPTO_CANDLE_SOURCE", "bitunix")
        patcher.start()
        self.addCleanup(patcher.stop)
        scanner._BITUNIX_HISTORY.clear()

    def test_only_listed_crypto_uses_bitunix(self):
        self.assertTrue(bitunix_data.uses_bitunix("BTCUSD"))
        self.assertFalse(bitunix_data.uses_bitunix("TSLAXUSD"))
        self.assertFalse(bitunix_data.uses_bitunix("XAUTUSD"))

    def test_klines_pages_back_and_returns_oldest_first(self):
        fake = FakeBitunix(1_000_000, 1_000_000 + 499 * 1800, 1800)
        with patch.object(bitunix_data, "_request", fake):
            rows = bitunix_data.klines("BTCUSDT", "30m", 1_000_000, 1_000_000 + 500 * 1800)
        self.assertEqual([r[0] for r in rows], fake.series)
        self.assertEqual(len(fake.calls), 3)
        self.assertEqual(rows[0][1:], [100.0, 101.0, 99.0, 100.0, 5.0])

    def test_scanner_takes_bitunix_first(self):
        with patch.object(scanner, "fetch_bitunix_ohlcv", return_value=[[1, 1, 1, 1, 1, 1]]), \
             patch.object(scanner, "require_fresh_ohlcv", side_effect=lambda o, n: o), \
             patch.object(scanner, "fetch_delta_ohlcv") as delta:
            _, venue = scanner.fetch_symbol_ohlcv("BTCUSD")
        self.assertEqual(venue, "bitunix")
        delta.assert_not_called()

    def test_bitunix_failure_falls_back_to_delta(self):
        with patch.object(scanner, "fetch_bitunix_ohlcv", side_effect=RuntimeError("down")), \
             patch.object(scanner, "require_fresh_ohlcv", side_effect=lambda o, n: o), \
             patch.object(scanner, "fetch_delta_ohlcv", return_value=[[1, 1, 1, 1, 1, 1]]):
            _, venue = scanner.fetch_symbol_ohlcv("BTCUSD")
        self.assertEqual(venue, "delta_india")

    def test_xstock_never_asks_bitunix(self):
        with patch.object(scanner, "fetch_bitunix_ohlcv") as bitunix, \
             patch.object(scanner, "require_fresh_ohlcv", side_effect=lambda o, n: o), \
             patch.object(scanner, "fetch_delta_ohlcv", return_value=[[1, 1, 1, 1, 1, 1]]):
            _, venue = scanner.fetch_symbol_ohlcv("TSLAXUSD")
        self.assertEqual(venue, "delta_india")
        bitunix.assert_not_called()

    def test_second_scan_asks_only_for_the_newest_page(self):
        step = scanner.TIMEFRAME_SECONDS[scanner.TIMEFRAME]
        now = int(time.time()) // step * step
        fake = FakeBitunix(now - 2000 * step, now, step)
        with patch.object(bitunix_data, "_request", fake):
            first = scanner.fetch_bitunix_ohlcv("BTCUSD")
            calls = len(fake.calls)
            second = scanner.fetch_bitunix_ohlcv("BTCUSD")
        self.assertEqual(len(first), scanner.OHLCV_LIMIT)
        self.assertEqual(first, second)
        self.assertGreater(calls, 1)
        self.assertEqual(len(fake.calls) - calls, 1)
        self.assertEqual(first[-1][0], now * 1000)

    def test_live_price_from_bitunix(self):
        with patch.object(scanner, "USE_LIVE_TICKER", True), \
             patch.object(bitunix_data, "last_price", return_value=123.0):
            price, source = scanner.live_ticker_price("bitunix", "BTCUSD", 1.0)
        self.assertEqual((price, source), (123.0, "bitunix_1m"))

    def test_fib_charts_use_the_requested_source(self):
        with patch.object(fib_trendline_data, "bitunix_candles", return_value=[[0, 1, 2, 0.5, 1]]) as b, \
             patch.object(fib_trendline_data, "delta_candles") as d:
            charts = fib_trendline_data.crypto_charts("BTCUSD", ["4h", "1d"], 10_000_000, source="bitunix")
        self.assertEqual(charts["4h"], [[0, 1, 2, 0.5, 1]])
        self.assertEqual(b.call_count, 2)
        d.assert_not_called()


if __name__ == "__main__":
    unittest.main()
