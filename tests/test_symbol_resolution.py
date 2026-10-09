import unittest
from unittest.mock import patch

import scanner


class FakeExchange:
    def __init__(self, working_symbol):
        self.working_symbol = working_symbol
        self.ohlcv_calls = []
        self.ticker_calls = []

    def fetch_ohlcv(self, symbol, **kwargs):
        self.ohlcv_calls.append(symbol)
        if symbol != self.working_symbol:
            raise RuntimeError(f"unknown symbol: {symbol}")
        return [[1, 1, 1, 1, 1, 1]]

    def fetch_ticker(self, symbol):
        self.ticker_calls.append(symbol)
        if symbol != self.working_symbol:
            raise RuntimeError(f"unknown symbol: {symbol}")
        return {"last": 123.0}


class SymbolResolutionTests(unittest.TestCase):
    def test_fallback_symbol_does_not_mangle_xstock_tickers(self):
        # QQQXUSD/MSTRBUSD are Delta-native xStock symbols, not "<base>USD"
        # crypto pairs - stripping "USD" would produce a bogus ccxt symbol
        # (QQQX/USDT) that could coincidentally match an unrelated token.
        for symbol in ["QQQXUSD", "MSTRBUSD", "AAPLXUSD", "SOXLBUSD"]:
            with self.subTest(symbol=symbol):
                self.assertEqual(scanner.fallback_symbol(symbol), symbol)

    def test_fallback_symbol_still_converts_real_crypto_delta_symbols(self):
        for symbol, expected in [
            ("BTCUSD", "BTC/USDT"),
            ("ETHUSD", "ETH/USDT"),
            ("DOTUSD", "DOT/USDT"),
        ]:
            with self.subTest(symbol=symbol):
                self.assertEqual(scanner.fallback_symbol(symbol), expected)

    def test_delta_eligibility_is_unaffected_by_xstock_suffix(self):
        # fallback_symbol excludes XUSD/BUSD from the "USD"->"USDT"
        # transform, but is_delta_symbol (used to route fetch_delta_ohlcv)
        # must keep matching them - that's the correct Delta-native path.
        self.assertTrue(scanner.is_delta_symbol("QQQXUSD"))
        self.assertTrue(scanner.is_delta_symbol("MSTRBUSD"))

    def test_perpetual_alias_is_tried_before_spot_alias(self):
        self.assertEqual(
            scanner.exchange_symbol_candidates("HYPE/USDT"),
            ["HYPE/USDT:USDT", "HYPE/USDT"],
        )

    def test_ohlcv_uses_perpetual_alias(self):
        exchange = FakeExchange("HYPE/USDT:USDT")
        candles = scanner.fetch_exchange_ohlcv(exchange, "HYPE/USDT")
        self.assertEqual(candles[0][4], 1)
        self.assertEqual(exchange.ohlcv_calls, ["HYPE/USDT:USDT"])

    def test_ticker_falls_back_when_exchange_has_no_settlement_alias(self):
        exchange = FakeExchange("HYPE/USDT")
        ticker = scanner.fetch_exchange_ticker(exchange, "HYPE/USDT")
        self.assertEqual(ticker["last"], 123.0)
        self.assertEqual(
            exchange.ticker_calls,
            ["HYPE/USDT:USDT", "HYPE/USDT"],
        )


class FetchRetryTests(unittest.TestCase):
    def test_delta_recovers_from_a_transient_failure(self):
        calls = {"n": 0}

        def flaky(symbol, timeframe_seconds):
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("Delta returned no candles for TEST")
            return [[1, 1, 1, 1, 1, 1]]

        with patch.object(scanner, "_fetch_delta_ohlcv_once", side_effect=flaky), \
                patch.object(scanner.time, "sleep", return_value=None):
            result = scanner.fetch_delta_ohlcv("BTCUSD")
        self.assertEqual(result, [[1, 1, 1, 1, 1, 1]])
        self.assertEqual(calls["n"], 2)


if __name__ == "__main__":
    unittest.main()
