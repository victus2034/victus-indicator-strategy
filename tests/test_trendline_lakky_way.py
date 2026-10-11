"""Trendline trades, Lakky's way (2026-10-11): the candle stop, one 1R target, no breakeven, no hold limit."""
import unittest

import fib_trendline_data as ftd
import fib_trendline_trades as ftt

HOUR = 3600


def candles(rows, start=HOUR):
    """(high, low) pairs -> evaluation candles one hour apart, after alert_ts=0."""
    return [(start + i * HOUR, (h + l) / 2, h, l, (h + l) / 2) for i, (h, l) in enumerate(rows)]


class CandleStopTests(unittest.TestCase):
    # Candles 0..4 closed, the alert on bar 5 at entry 100 (0.75% gap -> 99.25 / 100.75).
    opens = [101, 98, 101, 100.5, 101]
    closes = [102, 99.5, 101.5, 100.8, 101.2]
    highs = [103, 100.2, 102, 101.2, 101.6]
    lows = [100.5, 97, 98.9, 100.1, 100.6]

    def stop(self, long, entry=100.0):
        return ftt.candle_stop(long, entry, 5, self.opens, self.highs, self.lows, self.closes)

    def test_buy_takes_the_closer_of_last_wick_and_last_body(self):
        # last wick under 99.25 is bar 2 (98.9); last body under it is bar 1 (98) -> 98.9
        self.assertEqual(self.stop(True), 98.9)

    def test_body_can_be_the_closer_one(self):
        lows = [100.5, 97, 100.0, 100.1, 100.6]          # no later wick: bar 1's wick 97, body 98
        self.assertEqual(ftt.candle_stop(True, 100.0, 5, self.opens, self.highs, lows, self.closes), 98)

    def test_sell_mirrors(self):
        # last high over 100.75 is bar 4 (101.6); last body top over it is bar 4 (101.2) -> 101.2
        self.assertEqual(self.stop(False), 101.2)

    def test_forming_candle_is_never_read(self):
        self.assertIsNone(ftt.candle_stop(True, 100.0, 0, self.opens, self.highs, self.lows, self.closes))

    def test_plan_uses_it_and_falls_back_to_the_fixed_stop(self):
        plan = ftt.trendline_plan(True, 100.0, "1d", 5, self.opens, self.highs, self.lows, self.closes)
        self.assertEqual(plan, {"side": "long", "entry": 100.0, "sl": 98.9, "target_r": 1})
        self.assertAlmostEqual(ftt.target_price(plan), 101.1)
        flat = [100.0] * 5
        fallback = ftt.trendline_plan(True, 100.0, "1d", 5, flat, flat, flat, flat)
        self.assertAlmostEqual(fallback["sl"], 98.5)                  # TRENDLINE_SL_PCT 1d = 1.5%
        self.assertEqual(fallback["target_r"], 1)


class OneRTests(unittest.TestCase):
    plan = {"side": "long", "entry": 100.0, "sl": 98.0, "target_r": 1}

    def run_(self, rows, plan=None):
        return ftt.simulate(plan or self.plan, ftd.CRYPTO, "4h", 0, candles(rows))

    def test_target_hit(self):
        r = self.run_([(101, 99.9), (101.5, 100.5), (102.1, 101)])
        self.assertEqual((r["outcome"], r["r1"], r["resolved"], r["be"]), ("1R", True, True, False))
        at1, at2 = ftt.booked_r(self.plan, ftd.CRYPTO, r)
        self.assertEqual(at1, at2)
        self.assertLess(at1, 1)                                      # costs come off

    def test_no_breakeven(self):
        # +0.5R (101) trades, then price comes back to the original stop: a full SL, not BE
        r = self.run_([(100.5, 99.9), (101.5, 100.5), (100.5, 97.9)])
        self.assertEqual((r["outcome"], r["sl"], r["be"]), ("SL", True, False))
        self.assertLess(ftt.booked_r(self.plan, ftd.CRYPTO, r)[0], -1)

    def test_no_hold_limit(self):
        rows = [(100.5, 99.9)] + [(101, 99)] * 500 + [(102.5, 101)]
        self.assertEqual(self.run_(rows)["outcome"], "1R")

    def test_open_until_decided(self):
        r = self.run_([(100.5, 99.9)] + [(101, 99)] * 200)
        self.assertEqual((r["outcome"], r["resolved"]), ("open", False))
        self.assertEqual(ftt.booked_r(self.plan, ftd.CRYPTO, r), (None, None))

    def test_both_in_one_candle_is_the_stop(self):
        r = self.run_([(100.5, 99.9), (102.5, 97.5)])
        self.assertEqual((r["outcome"], r["ambiguous"]), ("SL", True))

    def test_entry_wait_still_applies(self):
        wait = ftt.FIB_TL_ENTRY_WAIT_BARS * ftt.EVAL_PER_BAR[ftd.CRYPTO]["4h"]
        r = self.run_([(102, 100.5)] * (wait + 1))
        self.assertEqual(r["outcome"], "no fill")

    def test_short(self):
        plan = {"side": "short", "entry": 100.0, "sl": 103.0, "target_r": 1}
        self.assertEqual(self.run_([(100.2, 99.5), (99.5, 96.9)], plan)["outcome"], "1R")
        self.assertEqual(self.run_([(100.2, 99.5), (103.1, 99)], plan)["outcome"], "SL")

    def test_old_records_keep_the_old_rules(self):
        old = {"side": "long", "entry": 100.0, "sl": 98.0}            # no target_r: BE and 2R as before
        r = ftt.simulate(old, ftd.CRYPTO, "4h", 0, candles([(100.5, 99.9), (101.5, 100.5), (100.5, 99.0)]))
        self.assertEqual(r["outcome"], "BE")


if __name__ == "__main__":
    unittest.main()
