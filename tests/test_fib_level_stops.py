"""Every fib level has its own stop (lakky, 2026-10-27, ENA 4H: all of L1-L4 showed one SL)."""
import unittest

import fib_trendline_scanner as fts

# ENA 4H BUY fib read off his chart: L3 0.20492, L4 0.20303 -> range 0.01718 from 0.19719.
ENA = (1, 0.19719, 0.21437)


class LevelStops(unittest.TestCase):
    def cases(self):
        for d, base, top in (ENA, (-1, 0.21437, 0.19719), (1, 90.0, 110.0), (-1, 110.0, 90.0),
                             (1, 0.0001, 0.00013), (1, 60000.0, 126000.0)):
            yield d, base, top

    def test_no_two_levels_share_a_stop(self):
        for d, base, top in self.cases():
            for rule in ("next", "own"):
                stops = fts.fib_level_stops(d, base, top, rule)
                self.assertEqual(len(set(round(v, 12) for v in stops.values())), 4, (d, base, top, rule, stops))
                fts.check_level_stops(d, fts.fib_levels(d, base, top), stops)

    def test_live_legs_each_have_their_own_stop(self):
        for d, base, top in self.cases():
            for tf in ("4h", "1d", "1w", "1M"):
                legs = fts.fib_legs(d, base, top, tf)
                stops = [z["sl"] for _, z in legs]
                self.assertEqual(len(set(stops)), len(stops), (tf, legs))
                for level, z in legs:
                    self.assertTrue(z["sl"] < z["entry"] if d == 1 else z["sl"] > z["entry"], (level, z))

    def test_guard_rejects_a_shared_stop(self):
        d, base, top = ENA
        with self.assertRaises(ValueError):
            fts.check_level_stops(d, fts.fib_levels(d, base, top), fts.fib_level_stops(d, base, top, "shared"))

    def test_next_rule_on_ena(self):
        d, base, top = ENA
        lv = fts.fib_levels(d, base, top)
        stops = fts.fib_level_stops(d, base, top, "next")
        pad = (top - base) * 0.11 * 0.25
        self.assertAlmostEqual(stops["L1"], lv["L2"] - pad)
        self.assertAlmostEqual(stops["L2"], lv["L3"] - pad)
        # L3 keeps the stop every fib alert had until now
        self.assertAlmostEqual(stops["L3"], fts.fib_level_stops(d, base, top, "shared")["L3"])
        self.assertAlmostEqual(stops["L4"], lv["L4"] - (top - base) * 0.11 - pad)
        # none of them the ~0.2% stop just past the level he called too tight
        for k in lv:
            self.assertGreater((lv[k] - stops[k]) / lv[k] * 100, 0.9, k)


class BodyStops(unittest.TestCase):
    """lakky's hand SLs on HYPE 1D (2026-10-27): SELL fib 98.0 (Sep 23) -> 74.411 (Oct 24)."""

    def bodies(self):
        import csv
        from pathlib import Path
        rows = list(csv.DictReader(open(Path(__file__).parent / "fixtures" / "hype_usdt_1d_bitunix_fib_sl.csv")))
        return [(float(r["open"]), float(r["close"])) for r in rows]

    def test_hype_1d_matches_his_chart(self):
        stops = fts.fib_level_stops(-1, 98.0, 74.411, "body", self.bodies())
        self.assertAlmostEqual(stops["L1"], 84.17, places=3)    # his line 84.193 (Oct 8 close; Oct 9 close 84.17)
        self.assertAlmostEqual(stops["L2"], 86.031, places=3)   # his line, Sep 29 close
        self.assertAlmostEqual(stops["L3"], 88.488, places=3)   # his line, Oct 7 close
        self.assertAlmostEqual(stops["L4"], 90.964, places=3)   # his line 91.211 (Oct 6 low); nearest body Sep 30 close
        fts.check_level_stops(-1, fts.fib_levels(-1, 98.0, 74.411), stops)

    def test_never_shared_whatever_the_candles(self):
        import random
        rnd = random.Random(7)
        for d, base, top in self.cases():
            lo, hi = min(base, top), max(base, top)
            for _ in range(200):
                bodies = [(rnd.uniform(lo, hi), rnd.uniform(lo, hi)) for _ in range(rnd.randint(0, 40))]
                stops = fts.fib_level_stops(d, base, top, "body", bodies)
                fts.check_level_stops(d, fts.fib_levels(d, base, top), stops)

    cases = LevelStops.cases


if __name__ == "__main__":
    unittest.main()
