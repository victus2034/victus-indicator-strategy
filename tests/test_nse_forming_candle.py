"""NSE builds zones on the candle that is still forming, as crypto and the chart do.

It used to build on confirmed candles only and then kill zones on the last
CLOSE. That misses the case the chart handles: a wick that pokes through a
zone's far edge and pulls back. Pine evaluates the forming bar on every tick,
so the zone dies the moment the wick does.

A half-finished candle cannot kill a zone the finished one would not - its range
sits inside the full candle's - so building on it cannot invent a kill. (Replayed
over 700 mid-bar snapshots of 20 real stocks: no false kills.)
"""
import csv
import pathlib
import unittest
from unittest.mock import patch

import pandas as pd

import nse_scanner
import scanner

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "coti_usdt_30m_800.csv"


def real_tape():
    with FIXTURE.open(newline="", encoding="utf-8") as handle:
        rows = [
            (float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]))
            for r in csv.DictReader(handle)
        ]
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"]).assign(volume=1.0)


def key(zone):
    return (zone["created_idx"], round(zone["top"], 9), round(zone["bottom"], 9))


class ScanSymbolUsesTheFormingCandleTests(unittest.TestCase):
    def setUp(self):
        original = scanner.ZONE_BASE_EXTRA
        self.addCleanup(setattr, scanner, "ZONE_BASE_EXTRA", original)
        self.tape = real_tape()
        timeframe = patch.object(nse_scanner, "TIMEFRAME", "30m")
        timeframe.start()
        self.addCleanup(timeframe.stop)

    def scan(self):
        """Run scan_symbol with the last candle treated as still forming."""
        seen = {}

        def spy_zones(frame):
            seen["zones"] = len(frame)
            return [], []

        def spy_signals(frame):
            seen["signals"] = len(frame)
            return False, False

        with patch.object(nse_scanner, "fetch_stock_ohlcv", return_value=self.tape), \
             patch.object(nse_scanner, "confirmed_candles", side_effect=lambda d: d.iloc[:-1]), \
             patch.object(nse_scanner, "build_zones", side_effect=spy_zones), \
             patch.object(nse_scanner, "get_range_filter_signals", side_effect=spy_signals):
            nse_scanner.scan_symbol("TEST.NS")
        return seen

    def test_zones_are_built_on_every_candle_the_forming_one_included(self):
        seen = self.scan()
        self.assertEqual(seen["zones"], len(self.tape), "the forming candle was left out of the zones")

    def test_the_range_filter_signal_stays_on_confirmed_candles(self):
        # Unlike a zone, a signal can appear on the forming bar and be gone by
        # the close, so it must not alert on a candle that may not survive.
        seen = self.scan()
        self.assertEqual(seen["signals"], len(self.tape) - 1)


class WickThroughTheFarEdgeTests(unittest.TestCase):
    """The case the old close-based kill missed."""

    def setUp(self):
        original = scanner.ZONE_BASE_EXTRA
        self.addCleanup(setattr, scanner, "ZONE_BASE_EXTRA", original)
        # scan_symbol re-binds the engine from nse_scanner.TIMEFRAME on every
        # call, so the test has to be the 30m process too - otherwise it builds
        # the same zone with a different base window and the keys never match.
        timeframe = patch.object(nse_scanner, "TIMEFRAME", "30m")
        timeframe.start()
        self.addCleanup(timeframe.stop)
        nse_scanner.bind_zone_engine("30m")
        self.prefix = real_tape().iloc[:600].reset_index(drop=True)
        supply, _ = nse_scanner.build_zones(self.prefix)
        live = [z for z in supply if z["active"] and z["created_idx"] < len(self.prefix) - 20]
        self.assertTrue(live, "the fixture has no live supply zone to test against")
        self.zone = live[0]

    def forming(self, high):
        price = float(self.prefix["close"].iloc[-1])
        return pd.DataFrame(
            [{"open": price, "high": high, "low": price * 0.999, "close": price, "volume": 1.0}]
        )

    def zone_after(self, forming):
        frame = pd.concat([self.prefix, forming], ignore_index=True)
        supply, _ = nse_scanner.build_zones(frame)
        return next(z for z in supply if key(z) == key(self.zone))

    def test_a_wick_through_the_far_edge_kills_the_zone_though_the_close_stays_below(self):
        forming = self.forming(high=self.zone["top"] * 1.002)
        self.assertLess(forming["close"].iloc[0], self.zone["top"], "the close must not be what kills it")
        self.assertFalse(self.zone_after(forming)["active"])

    def test_a_forming_candle_that_stays_clear_leaves_the_zone_alone(self):
        forming = self.forming(high=self.zone["top"] * 0.998)
        self.assertTrue(self.zone_after(forming)["active"])

    def offered_supply(self, wick):
        """What scan_symbol offers as the nearest supply zone, end to end.

        The nearest zone is found first, then a forming candle is added whose
        high is chosen relative to it: "through" pokes past the far edge and
        pulls back; "clear" stays wholly below the zone, so it cannot touch it
        (a touch would restart the zone's age clock and muddy the comparison).
        """
        price = float(self.prefix["close"].iloc[-1])
        supply, _ = nse_scanner.build_zones(self.prefix)
        near, _ = nse_scanner.nearest_active_zone(price, supply, "supply", len(self.prefix) - 1)
        self.assertIsNotNone(near, "no nearest supply zone to test against")
        high = near["top"] * 1.002 if wick == "through" else max(near["bottom"] * 0.999, price)
        frame = pd.concat([self.prefix, self.forming(high=high)], ignore_index=True)
        with patch.object(nse_scanner, "fetch_stock_ohlcv", return_value=frame), \
             patch.object(nse_scanner, "confirmed_candles", side_effect=lambda d: d.iloc[:-1]):
            result = nse_scanner.scan_symbol("TEST.NS")
        return near, result["supply"]

    def test_end_to_end_the_scanner_stops_offering_a_zone_the_forming_wick_killed(self):
        # The old scanner built on the confirmed candles, saw price still below
        # the zone, and went on offering it.
        near, offered = self.offered_supply("through")
        self.assertTrue(
            offered is None or key(offered) != key(near),
            "scan_symbol still offers a zone the forming candle's wick has broken",
        )

    def test_end_to_end_a_forming_candle_that_stays_clear_changes_nothing(self):
        near, offered = self.offered_supply("clear")
        self.assertIsNotNone(offered)
        self.assertEqual(key(offered), key(near))

    def test_without_the_forming_candle_the_same_zone_is_still_alive(self):
        # What the old scanner saw: the wick was in the unbuilt candle.
        supply, _ = nse_scanner.build_zones(self.prefix)
        self.assertTrue(next(z for z in supply if key(z) == key(self.zone))["active"])


if __name__ == "__main__":
    unittest.main()
