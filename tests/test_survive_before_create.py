"""The indicator's v10.0 survival gate, as an opt-in for the scanner.

Pine (require_survival_before_create) holds a confirmed pivot as a candidate:
a break kills it before it is drawn, a touch restarts its wait, and it is
created only after min_untouched quiet candles, already mature.
"""
import csv
import pathlib
import unittest
from unittest.mock import patch

import pandas as pd

import config
import scanner

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "coti_usdt_30m_800.csv"
WAIT = 15


def real_tape():
    with FIXTURE.open(newline="", encoding="utf-8") as handle:
        rows = [
            (float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]))
            for r in csv.DictReader(handle)
        ]
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"]).assign(volume=1.0)


def zones(gate):
    with patch.object(scanner, "ZONE_SURVIVE_BEFORE_CREATE", gate), \
            patch.object(scanner, "MIN_ZONE_AGE_CANDLES", WAIT):
        supply, demand = scanner.build_zones(real_tape())
    return supply + demand


class SurviveBeforeCreateTests(unittest.TestCase):
    def test_off_by_default(self):
        self.assertFalse(config.ZONE_SURVIVE_BEFORE_CREATE)
        self.assertFalse(scanner.ZONE_SURVIVE_BEFORE_CREATE)

    def test_a_created_zone_sat_untouched_for_the_wait(self):
        df = real_tape()
        created = zones(True)
        self.assertTrue(created)
        for zone in created:
            with self.subTest(created_idx=zone["created_idx"]):
                start = zone["created_idx"] - WAIT + 1
                window = df.iloc[start: zone["created_idx"] + 1]
                touched = (window["high"] >= zone["bottom"]) & (window["low"] <= zone["top"])
                self.assertFalse(touched.any())

    def test_a_created_zone_is_mature_at_birth(self):
        for zone in zones(True):
            # touches after birth move the clock forward, never back
            self.assertGreaterEqual(zone["clock"], zone["created_idx"] - WAIT)
            at_birth = {**zone, "clock": zone["created_idx"] - WAIT, "last_gap": None}
            with patch.object(scanner, "MIN_ZONE_AGE_CANDLES", WAIT):
                self.assertFalse(scanner.too_young_to_alert(at_birth, zone["created_idx"]))

    def test_the_gate_changes_which_zones_exist(self):
        key = lambda z: (z["type"], round(z["bottom"], 8), round(z["top"], 8))
        self.assertNotEqual({key(z) for z in zones(False)}, {key(z) for z in zones(True)})

    def test_the_research_hook_sees_every_candle(self):
        seen = []
        scanner.build_zones(real_tape(), on_candle=lambda i, s, d: seen.append(i))
        self.assertEqual(seen, list(range(scanner.SWING_LENGTH, len(real_tape()))))


if __name__ == "__main__":
    unittest.main()
