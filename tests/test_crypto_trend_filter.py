"""Crypto zone alerts follow the daily EMA50 trend (research/out/RESULTS.md).

Demand alerts only while the last closed daily candle is above its EMA50,
supply only while below. An unknown trend never blocks an alert, and the
filter is crypto-only: xStocks, "other" and NSE are untouched.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import nse_scanner
import scanner

DEMAND = {"bottom": 99.0, "top": 100.0, "created_idx": 0}
SUPPLY = {"bottom": 100.0, "top": 101.0, "created_idx": 0}


def candles(closes, end_ts, day=86400):
    start = end_ts - len(closes) * day
    return [{"time": start + i * day, "close": c} for i, c in enumerate(closes)]


class TrendFilterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self._patches = [
            patch.object(scanner, "ALERT_RECORD_FILE", Path(self._tmp.name) / "crypto.jsonl"),
            patch.object(scanner, "in_alert_window", return_value=True),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def send(self, zone_type, zone, price, trend):
        state = {}
        result = {"symbol": "BTCUSD", "price": price, zone_type: zone,
                  f"{zone_type}_rating": None, "daily_trend": trend}
        with patch.object(scanner, "send_alert", return_value=True) as send:
            scanner.process_candidate(state, result, zone_type, zone, 0.15, 1_000_000)
        return send.called, state

    def test_with_trend_alerts_against_trend_does_not(self):
        self.assertTrue(self.send("demand", DEMAND, 100.15, 1)[0])
        self.assertTrue(self.send("supply", SUPPLY, 99.85, -1)[0])
        sent, state = self.send("demand", DEMAND, 100.15, -1)
        self.assertFalse(sent)
        # Nothing recorded, so it alerts the moment the trend turns its way.
        self.assertEqual(state, {})
        self.assertFalse(self.send("supply", SUPPLY, 99.85, 1)[0])

    def test_unknown_trend_never_blocks(self):
        self.assertTrue(self.send("demand", DEMAND, 100.15, None)[0])
        self.assertTrue(self.send("supply", SUPPLY, 99.85, None)[0])

    def test_applies_to_crypto_watchlist_only(self):
        self.assertTrue(scanner.trend_filter_applies(scanner.CRYPTO_WATCHLIST[0]))
        for symbol in ("TSLAXUSD", "XAUTUSD", "MRVL/USDT:USDT"):
            self.assertFalse(scanner.trend_filter_applies(symbol), symbol)
        with patch.object(scanner, "CRYPTO_TREND_FILTER", False):
            self.assertFalse(scanner.trend_filter_applies(scanner.CRYPTO_WATCHLIST[0]))

    def test_nse_has_no_trend_filter(self):
        import inspect
        self.assertIsNot(nse_scanner.process_candidate, scanner.process_candidate)
        self.assertNotIn("daily_trend", inspect.getsource(nse_scanner.process_candidate))

    def daily(self, closes, now=10_000_000):
        response = MagicMock()
        response.json.return_value = {"success": True, "result": candles(closes, now)}
        with patch.object(scanner.requests, "get", return_value=response), \
                patch.object(scanner.time, "time", return_value=now):
            return scanner.daily_trend("BTCUSD")

    def test_daily_trend_reads_closed_candles(self):
        self.assertEqual(self.daily([100.0] * 60 + [110.0]), 1)
        self.assertEqual(self.daily([100.0] * 60 + [90.0]), -1)
        # The candle still forming (opened less than a day ago) is ignored.
        now = 10_000_000
        rows = candles([100.0] * 60 + [110.0], now)
        rows.append({"time": now - 3600, "close": 50.0})
        response = MagicMock()
        response.json.return_value = {"success": True, "result": rows}
        with patch.object(scanner.requests, "get", return_value=response), \
                patch.object(scanner.time, "time", return_value=now):
            self.assertEqual(scanner.daily_trend("BTCUSD"), 1)

    def test_daily_trend_unknown_on_short_history_or_error(self):
        self.assertIsNone(self.daily([100.0] * 20))
        with patch.object(scanner.requests, "get", side_effect=RuntimeError("down")):
            self.assertIsNone(scanner.daily_trend("BTCUSD"))
        self.assertIsNone(scanner.daily_trend("MRVL/USDT:USDT".replace("MRVL", "NOPE")))


if __name__ == "__main__":
    unittest.main()
