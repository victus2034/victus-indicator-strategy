"""Fib level SL on the nearest wick past each level (lakky, 2026-11-03, METAUSDT 4H "wrong sl").

His chart: a SELL fib 635.64 (29 Oct 16:00 UTC) -> 605.73. His SLs: L2 619.19 -> 620.83 (2 Nov 04:00
high), L3 622.18 -> 622.78 (2 Nov 12:00 high), L4 625.47 -> 626.56 (30 Oct 16:00 high). The "next"
rule put L2's at 623.00, past L3. Candles: Bitunix, since the fib origin.
"""
import csv
import unittest
from pathlib import Path

import fib_trendline_scanner as fts

FIXTURE = Path(__file__).parent / "fixtures" / "meta_usdt_4h_bitunix_fib_sl.csv"
META = (-1, 635.64, 605.73)


def wicks():
    with open(FIXTURE) as fh:
        return [(float(r["high"]), float(r["low"])) for r in csv.DictReader(fh)]


class WickStops(unittest.TestCase):
    def test_meta_4h_matches_his_lines(self):
        d, base, top = META
        stops = fts.fib_level_stops(d, base, top, "wick", wicks())
        self.assertAlmostEqual(stops["L2"], 620.83)
        self.assertAlmostEqual(stops["L3"], 622.78)
        self.assertAlmostEqual(stops["L4"], 626.56)
        fts.check_level_stops(d, fts.fib_levels(d, base, top), stops)

    def test_each_stop_sits_between_its_level_and_the_next(self):
        d, base, top = META
        lv = fts.fib_levels(d, base, top)
        stops = fts.wick_stops(d, lv, wicks(), 0)
        names = ("L1", "L2", "L3", "L4")
        for n, k in enumerate(names[:3]):
            self.assertTrue(lv[k] < stops[k] < lv[names[n + 1]], (k, stops[k]))

    def test_gap_skips_a_wick_too_close(self):
        d, base, top = META
        lv = fts.fib_levels(d, base, top)
        self.assertAlmostEqual(fts.wick_stops(d, lv, wicks(), 0)["L1"], 615.98)       # 0.01% past L1
        self.assertAlmostEqual(fts.wick_stops(d, lv, wicks(), 0.05)["L1"], 616.47)

    def test_buy_mirror_and_fallback(self):
        lv = fts.fib_levels(1, 90.0, 110.0)
        own = fts.stops_for_levels(1, lv, "own")
        self.assertEqual(fts.wick_stops(1, lv, [], 0), own)                           # no candles: just past the level
        low = lv["L2"] - 0.1
        self.assertAlmostEqual(fts.wick_stops(1, lv, [(200.0, low)], 0)["L2"], low)
        fts.check_level_stops(1, lv, fts.wick_stops(1, lv, [(200.0, low)], 0))


if __name__ == "__main__":
    unittest.main()
