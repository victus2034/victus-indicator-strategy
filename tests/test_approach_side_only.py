"""Zone alerts fire only while price is still approaching the entry.

Distance is measured in both directions, so price already through the entry
used to read as "0.15% away" and alert after the entry had traded.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import nse_scanner
import scanner

DEMAND = {"bottom": 99.0, "top": 100.0, "created_idx": 0}
SUPPLY = {"bottom": 100.0, "top": 101.0, "created_idx": 0}


def result(symbol, price, zone_type, zone):
    return {"symbol": symbol, "price": price, zone_type: zone, f"{zone_type}_rating": None}


class ApproachSideOnlyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._patches = [
            patch.object(scanner, "ALERT_RECORD_FILE", tmp / "crypto.jsonl"),
            patch.object(nse_scanner, "ALERT_RECORD_FILE", tmp / "nse.jsonl"),
            patch.object(scanner, "in_alert_window", return_value=True),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def test_past_entry_by_side(self):
        self.assertTrue(scanner.price_past_entry("demand", DEMAND, 99.85))
        self.assertFalse(scanner.price_past_entry("demand", DEMAND, 100.15))
        self.assertFalse(scanner.price_past_entry("demand", DEMAND, 100.0))
        self.assertTrue(scanner.price_past_entry("supply", SUPPLY, 100.15))
        self.assertFalse(scanner.price_past_entry("supply", SUPPLY, 99.85))
        self.assertIs(nse_scanner.zone_engine.price_past_entry, scanner.price_past_entry)

    def check(self, module, zone_type, zone, price, expect_sent):
        state = {}
        with patch.object(module, "send_alert", return_value=True) as send:
            sent = module.process_candidate(
                state, result("BTCUSD" if module is scanner else "INFY.NS", price, zone_type, zone),
                zone_type, zone, 0.15, 1_000_000,
            )
        self.assertEqual(bool(sent), expect_sent)
        self.assertEqual(send.called, expect_sent)
        key = module.build_state_key(
            "BTCUSD" if module is scanner else "INFY.NS", zone_type, zone
        )
        # Either way the band is consumed, so a bounce back out cannot fire late.
        self.assertTrue(state[key]["in_zone"])

    def test_crypto(self):
        self.check(scanner, "demand", DEMAND, 100.15, True)
        self.check(scanner, "demand", DEMAND, 99.85, False)
        self.check(scanner, "supply", SUPPLY, 99.85, True)
        self.check(scanner, "supply", SUPPLY, 100.15, False)

    def test_nse(self):
        self.check(nse_scanner, "demand", DEMAND, 100.15, True)
        self.check(nse_scanner, "demand", DEMAND, 99.85, False)
        self.check(nse_scanner, "supply", SUPPLY, 99.85, True)
        self.check(nse_scanner, "supply", SUPPLY, 100.15, False)


if __name__ == "__main__":
    unittest.main()
