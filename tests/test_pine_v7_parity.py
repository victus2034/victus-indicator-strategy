"""The places scanner.build_zones and Shiva_Indicator_v7.pine had drifted apart.

Each case here is a rule the chart applies that the scanner did not, found by
replaying both constructions bar by bar over 42 symbols of 30m candles and
diffing the surviving zone sets. Before these fixes the two agreed on 96.5% of
live zones; after them, on 100%.
"""
import unittest
from unittest.mock import patch

import pandas as pd

import scanner


def frame(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"]).assign(
        time=range(len(rows)), volume=1.0
    )


class OverlapUsesTheConfirmationBarAtr(unittest.TestCase):
    """v7 reads ta.atr() on the confirmation bar and hands THAT to f_addZone.

    The scanner used the pivot bar's ATR, swing_length bars earlier. Both are
    valid numbers; only one is the one the chart rejects zones with.
    """

    def zone(self):
        # A rising range, so ATR at the pivot and ATR ten bars later differ.
        rows = [(10.0 + i * 0.1, 10.2 + i * 0.1, 9.9 + i * 0.1, 10.1 + i * 0.1) for i in range(12)]
        rows.append((11.0, 11.1, 9.0, 10.9))          # the pivot low
        rows += [(12.0 + i, 13.0 + i, 11.0 + i, 12.5 + i) for i in range(12)]
        df = frame(rows)
        atr_series = scanner.atr(df, 5)
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.0):
            z = scanner.qualify_wick_zone(df, 12, 22, atr_series, "demand", "wick")
        return z, atr_series

    def test_overlap_atr_is_the_confirmation_bar_reading(self):
        z, atr_series = self.zone()
        self.assertIsNotNone(z)
        self.assertAlmostEqual(z["overlap_atr"], float(atr_series.iloc[22]), places=10)

    def test_zone_metrics_still_use_the_pivot_bar_reading(self):
        # wick_atr and departure_atr describe the pivot candle and feed rating
        # models trained on them, so they must not move with this.
        z, atr_series = self.zone()
        self.assertAlmostEqual(z["atr"], float(atr_series.iloc[12]), places=10)
        self.assertNotAlmostEqual(z["overlap_atr"], z["atr"], places=6)


class PivotZoneSpendsTheArmedRebuild(unittest.TestCase):
    """v7's f_tryCreate clears pendS/pendD when a pivot zone is created.

    Without it the scanner builds the short-pivot replacement as well, landing a
    zone up to base_extra bars before the chart draws one - and the real pivot
    zone is then rejected as overlapping its own early copy.
    """

    def test_a_pivot_zone_and_its_rebuild_cannot_both_exist(self):
        # The symptom this caused in the field: the short-pivot replacement
        # landed base_extra bars before the chart's pivot zone, and the pivot
        # zone was then rejected for overlapping its own early copy - so the
        # scanner held a zone at a bar the chart never drew one at.
        rows = [(10.0, 10.2, 9.9, 10.1)] * 12
        rows.append((9.8, 9.9, 9.0, 9.85))        # pivot low -> demand zone
        rows += [(10.0, 10.2, 9.9, 10.1)] * 12
        rows.append((10.0, 10.2, 8.0, 8.1))       # wick through the far edge
        rows += [(8.2, 8.4, 8.1, 8.3)] * 40
        df = frame(rows)

        with patch.object(scanner, "ZONE_GEOMETRY", "wick"), \
             patch.object(scanner, "ZONE_BREAK_ON_WICK", True), \
             patch.object(scanner, "ZONE_REBUILD_AFTER_BREAK", True):
            _, demand = scanner.build_zones(df)

        by_pivot = {}
        for zone in demand:
            by_pivot.setdefault(zone["pivot_idx"], []).append(zone)
        for pivot_idx, built in by_pivot.items():
            self.assertEqual(
                len(built), 1,
                f"pivot {pivot_idx} produced {len(built)} zones - the rebuild "
                f"was not disarmed by the pivot zone",
            )


class DegenerateWickIsNotARebuild(unittest.TestCase):
    """v7 tests `rfS > near` before building a replacement.

    A bar that closes on its own extreme has a wick of no height. On the pivot
    path the chart floors such a box; on the REBUILD path it refuses it and
    leaves the rebuild armed for the next short pivot. Flooring it there put a
    hairline zone on the chart's level several bars early.
    """

    def test_qualify_flags_a_zero_height_wick(self):
        rows = [(10.0, 10.2, 9.9, 10.1)] * 12
        # green candle opening exactly on its own low: no lower wick at all
        rows.append((9.0, 9.9, 9.0, 9.85))
        rows += [(10.0, 10.2, 9.9, 10.1)] * 12
        df = frame(rows)
        atr_series = scanner.atr(df, 5)
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.0), \
             patch.object(scanner, "ZONE_BASE_EXTRA", 0):
            z = scanner.qualify_wick_zone(df, 12, 22, atr_series, "demand", "wick")
        self.assertTrue(z["degenerate"])
        self.assertGreater(z["top"], z["bottom"], "a floored box still has height")

    def test_a_real_wick_is_not_flagged(self):
        rows = [(10.0, 10.2, 9.9, 10.1)] * 12
        rows.append((9.8, 9.9, 9.0, 9.85))
        rows += [(10.0, 10.2, 9.9, 10.1)] * 12
        df = frame(rows)
        atr_series = scanner.atr(df, 5)
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.0):
            z = scanner.qualify_wick_zone(df, 12, 22, atr_series, "demand", "wick")
        self.assertFalse(z["degenerate"])


class WideZoneRescueActuallyCaps(unittest.TestCase):
    """The rescue must leave the zone INSIDE the limit, or it has not rescued it.

    It used to prefer the tightest candle level that existed over cutting at the
    limit, however wide that level left the zone. A spike wick nearly always
    leaves some level in between, so the rescue fired, nudged the edge, and
    handed back a zone as untradeable as the one it was given - 14% of live
    zones came out over the limit, the worst at 19.6%.
    """

    def window(self, highs=None, lows=None):
        n = len(highs or lows)
        return pd.DataFrame({
            "high": highs or [0.0] * n, "low": lows or [0.0] * n,
            "open": [0.0] * n, "close": [0.0] * n,
        })

    def test_a_spike_wick_is_cut_to_the_limit(self):
        # HOME/USDT 4h, the zone that alerted at 21.9% stop distance. The only
        # lows between the spike low and the body edge are 0.005965 and
        # 0.005993, both still ~21% above the far edge.
        far, near = 0.004920, 0.006033
        w = self.window(lows=[0.006212, 0.006314, 0.004920, 0.005965, 0.005993])
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.80):
            out = scanner.tighten_wide_zone(w, "demand", far, near)
        width = (out - far) / far * 100.0
        self.assertLessEqual(width, 0.80 + 1e-9)
        self.assertAlmostEqual(width, 0.80, places=6)

    def test_supply_side_is_cut_the_same_way(self):
        far, near = 101.0, 90.0
        w = self.window(highs=[95.0, 97.0, 101.0])     # nothing inside the limit
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.80):
            out = scanner.tighten_wide_zone(w, "supply", far, near)
        self.assertAlmostEqual((far - out) / out * 100.0, 0.80, places=6)

    def test_a_real_level_inside_the_limit_still_wins(self):
        # EX 6 unchanged: 55.130 is inside 0.80, so the box keeps a real level.
        w = self.window(highs=[55.130, 55.559])
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.80):
            out = scanner.tighten_wide_zone(w, "supply", 55.559, 54.446)
        self.assertAlmostEqual(out, 55.130, places=3)

    def test_no_live_zone_exceeds_the_limit(self):
        # End to end: a tape full of spike wicks must still produce only
        # tradeable boxes.
        rows = []
        for i in range(200):
            base = 100.0 + (i % 7) * 0.3
            if i % 23 == 0:
                rows.append((base, base + 0.4, base - 12.0, base + 0.1))
            elif i % 29 == 0:
                rows.append((base, base + 14.0, base - 0.4, base - 0.1))
            else:
                rows.append((base, base + 0.5, base - 0.5, base + 0.2))
        df = frame(rows)
        with patch.object(scanner, "ZONE_GEOMETRY", "wick"), \
             patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.80):
            supply, demand = scanner.build_zones(df)
        checked = 0
        for side, zones in (("supply", supply), ("demand", demand)):
            for z in zones:
                if not z["active"]:
                    continue
                checked += 1
                if side == "supply":
                    width = (z["top"] - z["bottom"]) / z["bottom"] * 100.0
                else:
                    width = (z["top"] - z["bottom"]) / z["bottom"] * 100.0
                self.assertLessEqual(
                    width, 0.80 + 1e-6,
                    f"{side} zone {z['bottom']}-{z['top']} is {width:.2f}% wide",
                )
        self.assertGreater(checked, 0, "the fixture produced no live zones")


if __name__ == "__main__":
    unittest.main()
