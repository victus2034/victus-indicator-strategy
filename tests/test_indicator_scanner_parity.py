"""The scanner must draw the zones the chart draws.

Replays scanner.build_zones and a transcription of Shiva_Indicator_v7.pine over
the same synthetic tapes and asserts the surviving zone sets are identical - the
whole point of running the wick geometry live is that an alert is one the chart
would have fired.

The reference in pine_v7_reference.py is written from the Pine source rather
than from the scanner, so agreement means something. Measured against 42 real
symbols of 30m candles the two now match on 100% of live zones; these tapes are
the part that can run without a network.

Two kinds of tape are replayed:

  * random walks with spike wicks, which cover the geometry, the break rule and
    the overlap filter in bulk; and
  * 800 real 30m candles (COTI/USDT, Apr-Jul 2026, in fixtures/), because two of
    the rules below are not reachable from a smooth random walk at all. Over
    24,000 synthetic bars neither the pivot-disarms-rebuild path nor the
    degenerate-rebuild refusal fired once; on 42 real symbols they fire 121 and
    several hundred times. Real tape consolidates and gaps, and those rules live
    in exactly that structure.

The random tapes deliberately avoid a bar that opens or closes exactly on its
own extreme, which is the one case where the two implementations legitimately
differ: the chart floors a zero-height wick at syminfo.mintick, and the scanner
- which has no tick size for a symbol - floors it at 1% of ATR. The real-candle
tape does contain such bars, so it is compared on the far edge, which no floor
can move, plus the near edge wherever the wick had height to begin with.
"""
import csv
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import pine_v7_reference as pine
import scanner

FIXTURES = Path(__file__).parent / "fixtures"

SWING = 10
BASE = 5
ATR_LEN = 50
OVERLAP = 1.0
MAX_WIDTH = 0.80
KEEP = 50
MIN_AGE = 15


def tape(seed, bars=900, start=100.0):
    """A random walk with occasional spike wicks, and no zero-height wicks."""
    rng = np.random.default_rng(seed)
    rows = []
    price = start
    for i in range(bars):
        drift = rng.normal(0, 0.004)
        price = max(price * (1 + drift), 1.0)
        open_ = price
        close = max(price * (1 + rng.normal(0, 0.003)), 0.5)
        body_hi, body_lo = max(open_, close), min(open_, close)
        # Wicks are strictly positive, so no bar sits on its own extreme.
        up = abs(rng.normal(0, 0.002)) + 1e-4
        down = abs(rng.normal(0, 0.002)) + 1e-4
        if i % 37 == 0:
            down += abs(rng.normal(0, 0.05)) + 0.01
        if i % 41 == 0:
            up += abs(rng.normal(0, 0.05)) + 0.01
        rows.append((open_, body_hi * (1 + up), body_lo * (1 - down), close))
        price = close
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"]).assign(
        time=range(bars), volume=1.0
    )


def real_tape():
    """800 real 30m candles. Structure a random walk does not produce."""
    with (FIXTURES / "coti_usdt_30m_800.csv").open(newline="", encoding="utf-8") as handle:
        rows = [
            (float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), int(r["time"]))
            for r in csv.DictReader(handle)
        ]
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close", "time"])
    return frame.assign(volume=1.0)


def scanner_zones(df):
    with patch.object(scanner, "ZONE_GEOMETRY", "wick"), \
         patch.object(scanner, "SWING_LENGTH", SWING), \
         patch.object(scanner, "ZONE_BASE_EXTRA", BASE), \
         patch.object(scanner, "ATR_PERIOD", ATR_LEN), \
         patch.object(scanner, "ATR_METHOD", "rma"), \
         patch.object(scanner, "OVERLAP_ATR", OVERLAP), \
         patch.object(scanner, "ZONE_MAX_WIDTH_PCT", MAX_WIDTH), \
         patch.object(scanner, "HISTORY_OF_ZONES_TO_KEEP", KEEP), \
         patch.object(scanner, "ZONE_EVICT_WEAKEST", True), \
         patch.object(scanner, "ZONE_BREAK_ON_WICK", True), \
         patch.object(scanner, "ZONE_REBUILD_AFTER_BREAK", True), \
         patch.object(scanner, "MAX_CONSECUTIVE_ZONE_TOUCHES", 0):
        supply, demand = scanner.build_zones(df)
    return {
        (1 if z["type"] == "supply" else -1, z["created_idx"],
         round(z["top"], 9), round(z["bottom"], 9))
        for z in supply + demand
        if z["active"]
    }


def chart_zones(df):
    return {
        (z["type"], z["created_idx"], round(z["top"], 9), round(z["bottom"], 9))
        for z in pine.live_zones(
            df, swing_length=SWING, base_extra=BASE, atr_len=ATR_LEN,
            overlap_mult=OVERLAP, max_width_pct=MAX_WIDTH, history_keep=KEEP,
            keep_strongest=True, break_on_wick=True, do_rebuild=True,
            min_untouched=MIN_AGE,
        )
    }


class ScannerMatchesTheChart(unittest.TestCase):
    def test_live_zone_sets_are_identical(self):
        for seed in range(6):
            with self.subTest(seed=seed):
                df = tape(seed)
                chart = chart_zones(df)
                scan = scanner_zones(df)
                self.assertTrue(chart, "the tape produced no zones to compare")
                missing = sorted(chart - scan)
                extra = sorted(scan - chart)
                self.assertEqual(
                    (missing, extra), ([], []),
                    f"seed {seed}: {len(missing)} drawn by the chart and not by "
                    f"the scanner, {len(extra)} the other way",
                )

    def test_real_candles_agree_on_every_far_edge(self):
        # The far edge is the SL side and the level that kills the zone, and no
        # zero-height floor can move it - so on real tape, which does contain
        # bars sitting on their own extreme, this is the exact comparison.
        df = real_tape()
        chart = {(k, c, top if k == 1 else bottom) for k, c, top, bottom in chart_zones(df)}
        scan = {(k, c, top if k == 1 else bottom) for k, c, top, bottom in scanner_zones(df)}
        self.assertTrue(chart, "the fixture produced no zones to compare")
        self.assertEqual(
            (sorted(chart - scan), sorted(scan - chart)), ([], []),
            "the scanner and the chart disagree about which zones are live on "
            "real candles",
        )

    def test_real_candles_agree_on_near_edges_that_had_height(self):
        df = real_tape()
        chart = {(k, c, top if k == 1 else bottom): (bottom if k == 1 else top)
                 for k, c, top, bottom in chart_zones(df)}
        scan = {(k, c, top if k == 1 else bottom): (bottom if k == 1 else top)
                for k, c, top, bottom in scanner_zones(df)}
        compared = 0
        for key in chart.keys() & scan.keys():
            far = key[2]
            if chart[key] == far:
                continue          # zero-height wick: the two floors differ by design
            compared += 1
            self.assertAlmostEqual(
                chart[key], scan[key], places=9,
                msg=f"near edge differs for the zone created at bar {key[1]}",
            )
        self.assertGreater(compared, 0, "no zone with a real wick was compared")

    def test_the_comparison_can_fail(self):
        # A guard on the guard: if the reference and the scanner were wired to
        # the same code this test file would pass while proving nothing.
        df = tape(0)
        with patch.object(scanner, "ZONE_BASE_EXTRA", 2):
            with patch.object(scanner, "ZONE_GEOMETRY", "wick"), \
                 patch.object(scanner, "SWING_LENGTH", SWING), \
                 patch.object(scanner, "ATR_PERIOD", ATR_LEN), \
                 patch.object(scanner, "OVERLAP_ATR", OVERLAP), \
                 patch.object(scanner, "ZONE_MAX_WIDTH_PCT", MAX_WIDTH), \
                 patch.object(scanner, "MAX_CONSECUTIVE_ZONE_TOUCHES", 0):
                supply, demand = scanner.build_zones(df)
        mismatched = {
            (1 if z["type"] == "supply" else -1, z["created_idx"],
             round(z["top"], 9), round(z["bottom"], 9))
            for z in supply + demand if z["active"]
        }
        self.assertNotEqual(mismatched, chart_zones(df))


class NoLiveZoneIsUntradeable(unittest.TestCase):
    """Every zone the chart keeps must be inside max_width_pct."""

    def test_chart_and_scanner_both_respect_the_limit(self):
        for seed in range(4):
            df = tape(seed)
            for label, zones in (("chart", chart_zones(df)), ("scanner", scanner_zones(df))):
                for kind, created, top, bottom in zones:
                    far, near = (top, bottom) if kind == 1 else (bottom, top)
                    width = abs(far - near) / min(far, near) * 100.0
                    self.assertLessEqual(
                        width, MAX_WIDTH + 1e-6,
                        f"{label} seed {seed}: zone created at {created} is "
                        f"{width:.2f}% wide against a {MAX_WIDTH}% limit",
                    )


if __name__ == "__main__":
    unittest.main()
