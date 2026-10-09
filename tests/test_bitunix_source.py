"""The Bitunix candle source: on by default for crypto and xStocks, Delta behind it."""
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
    """Serves the API's real shape (research/bitunix_window_probe.py, 2026-10-07):
    newest first, at most `limit`, opening before endTime; never the candle still
    forming at `now`; and each candle slot after the forming one, up to endTime,
    uses up one of the `limit`, so a page ending in the future comes back short.
    `minutes` maps a 1m open time to its price, for the forming-candle requests.
    An endTime off a candle open is refused: the real API then drops a candle
    and merges two (research/bitunix_page_probe.py, 2026-10-09)."""

    def __init__(self, first, last, step, now=None):
        self.series = list(range(first, last + 1, step))
        self.step = step
        self.now = int(time.time()) if now is None else now
        self.minutes = {}
        self.calls = []

    def __call__(self, pair, interval, start_ms, end_ms, limit, attempts=3):
        self.calls.append((pair, interval, start_ms, end_ms))
        step, series = (60, sorted(self.minutes)) if interval == "1m" else (self.step, self.series)
        if end_ms % (step * 1000):
            raise AssertionError(f"endTime {end_ms} is not on a {interval} candle open")
        forming = self.now // step * step
        closed = [ts for ts in series if ts < forming and start_ms <= ts * 1000 < end_ms]
        take = limit - max(0, (end_ms // 1000 - forming) // step)
        if take <= 0:
            return []
        return [_row(ts, self.minutes.get(ts, 100.0)) for ts in reversed(closed[-take:])]


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

    def test_crypto_and_xstocks_use_bitunix_other_stays_on_delta(self):
        self.assertTrue(bitunix_data.uses_bitunix("BTCUSD"))
        for symbol in config.XSTOCK_WATCHLIST:
            self.assertTrue(bitunix_data.uses_bitunix(symbol), symbol)
        for symbol in config.OTHER_WATCHLIST:
            self.assertFalse(bitunix_data.uses_bitunix(symbol), symbol)

    def test_xstocks_map_to_the_stock_ticker(self):
        # Delta's token names would map to pairs Bitunix does not list
        # (TSLAXUSDT, MRVLBUSDT); Bitunix trades the stock as TSLAUSDT.
        pairs = {s: bitunix_data.pair_for(s, scanner.delta_contract(s)) for s in config.XSTOCK_WATCHLIST}
        self.assertEqual(pairs, {
            "TSLAXUSD": "TSLAUSDT", "METAXUSD": "METAUSDT", "SOXLBUSD": "SOXLUSDT",
            "SNDKBUSD": "SNDKUSDT", "MRVL/USDT:USDT": "MRVLUSDT", "NVDAXUSD": "NVDAUSDT",
        })
        self.assertEqual(bitunix_data.pair_for("BTCUSD", "BTCUSD"), "BTCUSDT")

    def test_xstock_zone_scan_asks_bitunix_for_its_own_pair(self):
        fake, now, forming, step = self._scan_fake()
        with patch.object(bitunix_data, "_request", fake), patch("time.time", return_value=now):
            scanner.fetch_bitunix_ohlcv("MRVL/USDT:USDT")
        self.assertEqual({c[0] for c in fake.calls}, {"MRVLUSDT"})

    def test_klines_pages_back_and_returns_oldest_first(self):
        fake = FakeBitunix(1_000_800, 1_000_800 + 499 * 1800, 1800)
        with patch.object(bitunix_data, "_request", fake):
            rows = bitunix_data.klines("BTCUSDT", "30m", 1_000_800, 1_000_800 + 500 * 1800)
        self.assertEqual([r[0] for r in rows], fake.series)
        self.assertEqual(len(fake.calls), 3)
        self.assertEqual(rows[0][1:], [100.0, 101.0, 99.0, 100.0, 5.0])

    def test_pages_end_on_candle_opens_and_lose_nothing(self):
        # UNI 30m, 2026-10-08: paging by "oldest - 1ms" lost a candle at every
        # page edge, so a demand zone did not rebuild. Odd start and end too.
        fake = FakeBitunix(1_000_800, 1_000_800 + 999 * 1800, 1800)
        with patch.object(bitunix_data, "_request", fake):
            rows = bitunix_data.klines("BTCUSDT", "30m", 1_000_800 + 7, 1_000_800 + 999 * 1800 + 5)
        self.assertEqual([r[0] for r in rows], fake.series[1:])
        self.assertTrue(all(c[3] % 1_800_000 == 0 for c in fake.calls))

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

    def test_other_never_asks_bitunix(self):
        with patch.object(scanner, "fetch_bitunix_ohlcv") as bitunix, \
             patch.object(scanner, "require_fresh_ohlcv", side_effect=lambda o, n: o), \
             patch.object(scanner, "fetch_delta_ohlcv", return_value=[[1, 1, 1, 1, 1, 1]]):
            _, venue = scanner.fetch_symbol_ohlcv("SLVONUSD")
        self.assertEqual(venue, "delta_india")
        bitunix.assert_not_called()

    def _scan_fake(self):
        """A symbol 2000 candles old, 25 minutes into its forming candle."""
        step = scanner.TIMEFRAME_SECONDS[scanner.TIMEFRAME]
        now = 1_790_000_000 // 14400 * 14400 + 3 * 3600 + 25 * 60 + 17
        forming = now // step * step
        fake = FakeBitunix(forming - 2000 * step, forming, step, now=now)
        fake.minutes = {forming + 60 * i: 100.0 + i % 7 for i in range((now - forming) // 60 + 1)}
        return fake, now, forming, step

    def test_zone_scan_gets_the_full_history_and_the_forming_candle(self):
        # Live 2026-10-05..07: 199 candles and no forming one, because the page
        # was asked to end a candle in the future.
        fake, now, forming, step = self._scan_fake()
        with patch.object(bitunix_data, "_request", fake), patch("time.time", return_value=now):
            candles = scanner.fetch_bitunix_ohlcv("BTCUSD")
        self.assertEqual(len(candles), scanner.OHLCV_LIMIT)
        times = [c[0] // 1000 for c in candles]
        self.assertEqual(times, list(range(forming - (scanner.OHLCV_LIMIT - 1) * step, forming + 1, step)))
        prices = [fake.minutes[t] for t in sorted(fake.minutes) if t < now // 60 * 60]
        self.assertEqual(candles[-1][1:], [prices[0], max(prices) + 1, min(prices) - 1, prices[-1],
                                           5.0 * len(prices)])

    def test_second_scan_asks_only_for_the_newest_page(self):
        fake, now, forming, step = self._scan_fake()
        with patch.object(bitunix_data, "_request", fake), patch("time.time", return_value=now):
            first = scanner.fetch_bitunix_ohlcv("BTCUSD")
            calls = [c for c in fake.calls if c[1] != "1m"]
            second = scanner.fetch_bitunix_ohlcv("BTCUSD")
        self.assertEqual(first, second)
        self.assertGreater(len(calls), 1)
        self.assertEqual(len([c for c in fake.calls if c[1] != "1m"]) - len(calls), 1)
        self.assertEqual(first[-1][0], forming * 1000)

    def test_a_page_never_ends_in_the_future(self):
        fake, now, forming, step = self._scan_fake()
        with patch.object(bitunix_data, "_request", fake), patch("time.time", return_value=now):
            rows = bitunix_data.klines("BTCUSDT", scanner.TIMEFRAME, forming - 1500 * step, now + 3 * step)
        self.assertEqual(len(rows), 1500)
        self.assertTrue(all(c[3] <= now * 1000 for c in fake.calls))

    def test_no_forming_candle_in_its_first_minute(self):
        fake, _, forming, step = self._scan_fake()
        fake.now = forming + 30
        with patch.object(bitunix_data, "_request", fake):
            self.assertIsNone(bitunix_data.forming_candle("BTCUSDT", scanner.TIMEFRAME, now=forming + 30))
        self.assertIsNone(bitunix_data.forming_candle("BTCUSDT", "1w"))

    def test_fib_trendline_price_is_live_on_bitunix(self):
        import fib_trendline_scanner as fts
        charts = {"4h": [[0, 1, 2, 0.5, 1.5]]}
        seen = {}

        def analyse(market, symbol, tf, candles, now, price=None):
            seen[symbol] = price
            return {}

        with patch.object(fts.scanner, "active_watchlist", return_value=["BTCUSD"]), \
             patch.object(fts, "crypto_charts", return_value=charts), \
             patch.object(fts, "analyse", analyse), \
             patch.object(bitunix_data, "last_price", return_value=123.0) as live:
            fts.scan_crypto(["4h"], 10_000_000)
            live.assert_called_once_with("BTCUSDT")
            self.assertEqual(seen["BTCUSD"], 123.0)
            live.side_effect = RuntimeError("down")
            fts.scan_crypto(["4h"], 10_000_000)
            self.assertEqual(seen["BTCUSD"], 1.5)

    def test_fib_trendline_xstock_reads_its_bitunix_pair(self):
        import fib_trendline_scanner as fts
        charts = {"4h": [[0, 1, 2, 0.5, 1.5]]}
        with patch.object(fts.scanner, "active_watchlist", return_value=["TSLAXUSD"]), \
             patch.object(fts, "crypto_charts", return_value=charts) as fetch, \
             patch.object(fts, "analyse", return_value={}), \
             patch.object(bitunix_data, "last_price", return_value=123.0) as live:
            fts.scan_crypto(["4h"], 10_000_000)
        self.assertEqual(fetch.call_args.args[0], "TSLAUSDT")
        live.assert_called_once_with("TSLAUSDT")

    def test_fib_trendline_skips_a_symbol_when_bitunix_is_down(self):
        # Delta's shorter history draws different fibs (new keys, re-alerts).
        import fib_trendline_scanner as fts

        def fetch(contract, timeframes, now, source="delta"):
            if source == "bitunix":
                raise RuntimeError("down")
            return {"4h": [[0, 1, 2, 0.5, 1.5]]}

        with patch.object(fts.scanner, "active_watchlist", return_value=["TSLAXUSD"]), \
             patch.object(fts, "crypto_charts", side_effect=fetch) as charts_mock, \
             patch.object(fts, "analyse", return_value={}) as analyse:
            results = fts.scan_crypto(["4h"], 10_000_000)
        self.assertEqual(charts_mock.call_count, 1)
        analyse.assert_not_called()
        self.assertEqual(results[0][:2], ("TSLAXUSD", None))

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
