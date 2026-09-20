import unittest
from unittest.mock import patch

import scanner


def _fresh(*_args, **_kwargs):
    return [[1, 1, 1, 1, 1, 1]]


class DeltaContractTests(unittest.TestCase):
    def test_unmapped_symbols_use_their_alias(self):
        self.assertEqual(scanner.delta_contract("AKE/USDT"), "AKEUSD")
        self.assertEqual(scanner.delta_contract("BEAT/USDT"), "BEATUSD")
        self.assertEqual(scanner.delta_contract("TRUMP/USDT"), "TRUMPUSD")
        self.assertEqual(scanner.delta_contract("MRVL/USDT:USDT"), "MRVLBUSD")

    def test_plain_delta_symbol_maps_to_itself(self):
        symbol = next(s for s in scanner.WATCHLIST if scanner.is_delta_symbol(s))
        self.assertEqual(scanner.delta_contract(symbol), symbol)

    def test_non_delta_symbol_has_no_contract(self):
        self.assertIsNone(scanner.delta_contract("NOTAREAL/USDT"))

    def test_every_watchlist_symbol_resolves_to_a_contract(self):
        missing = [s for s in scanner.WATCHLIST if scanner.delta_contract(s) is None]
        self.assertEqual(missing, [])


class DeltaFirstOrderTests(unittest.TestCase):
    def test_delta_wins_over_coinswitch_when_both_work(self):
        with patch.object(scanner, "fetch_delta_ohlcv", return_value=_fresh()) as delta, \
             patch.object(scanner, "require_fresh_ohlcv", side_effect=lambda o, n: o), \
             patch.object(scanner, "fetch_coinswitch_ohlcv", return_value=_fresh()) as cs:
            _, venue = scanner.fetch_symbol_ohlcv("BTC/USDT")
        self.assertEqual(venue, "delta_india")
        delta.assert_called_once()
        cs.assert_not_called()

    def test_falls_through_when_delta_raises(self):
        with patch.object(scanner, "fetch_delta_ohlcv", side_effect=RuntimeError("outage")), \
             patch.object(scanner, "require_fresh_ohlcv", side_effect=lambda o, n: o), \
             patch.object(scanner, "splice_deep_history", side_effect=lambda s, o: o), \
             patch.object(scanner, "fetch_coinswitch_ohlcv", return_value=_fresh()):
            _, venue = scanner.fetch_symbol_ohlcv("BTC/USDT")
        self.assertEqual(venue, "coinswitch")

    def test_falls_through_when_delta_returns_none(self):
        with patch.object(scanner, "fetch_delta_ohlcv", return_value=None), \
             patch.object(scanner, "require_fresh_ohlcv", side_effect=lambda o, n: o), \
             patch.object(scanner, "splice_deep_history", side_effect=lambda s, o: o), \
             patch.object(scanner, "fetch_coinswitch_ohlcv", return_value=_fresh()):
            _, venue = scanner.fetch_symbol_ohlcv("BTC/USDT")
        self.assertEqual(venue, "coinswitch")


if __name__ == "__main__":
    unittest.main()
