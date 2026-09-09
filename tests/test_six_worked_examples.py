"""The six worked examples, replayed through the production zone builder.

Shiva drew these by hand and measured them off the chart. They are the spec:
if scanner.qualify_wick_zone stops reproducing one of them, the scanner has
stopped drawing what the indicator draws, whatever else still passes.

Every OHLC value here was measured from the screenshots in
TRADINGVIEW SCRIPT INDICATOR IMG EXAMPLE by calibrating each chart off its own
price-axis labels and reading the candle bodies and wicks by pixel. The drawn
box edges were measured the same way, so both sides of each assertion come from
the image rather than from the code.

Bars either side of the base are padded so the +/- base_extra window is filled
without the padding ever winning a min or max - a demand pad sits above the
near edge, a supply pad below it. Only the real bars can decide the answer.
"""
import unittest
from unittest.mock import patch

import pandas as pd

import config
import scanner


# name, zone_type, real bars (o, h, l, c) with the pivot marked, drawn box, timeframe
#
# The timeframe matters as of the auto-derived ZONE_BASE_EXTRA fix: EX1-EX5 are
# 30m (base_extra auto-derives to 5, unchanged) and EX6 is 4h (base_extra now
# auto-derives to 1, was flatly 5 before the fix). Each example is replayed
# under the base_extra its OWN timeframe actually produces, not a blanket 5 -
# so this is the test that would have caught the never-re-derived-for-4h gap.
EXAMPLES = [
    (
        "EX1/31 supply  BTCUSD 30m",
        "supply",
        [
            (79824.7, 81065.2, 79745.8, 81008.2),
            (80999.5, 81253.7, 80434.0, 80631.2),   # pivot - red, high 81253.7
            (80626.8, 80938.1, 80504.1, 80644.4),
            (80473.4, 80863.6, 80311.2, 80618.1),
            (80241.1, 80591.8, 80232.3, 80469.0),
        ],
        1,
        (80999.5, 81253.7),
        "30m",
    ),
    (
        "EX2/36 demand  BTCUSD 30m",
        "demand",
        [
            (77132.2, 77532.2, 77132.2, 77480.0),
            (77128.7, 77167.0, 76937.4, 76940.9),
            (77226.1, 77257.4, 76944.3, 76944.3),
            (77229.6, 77236.5, 76676.5, 76902.6),   # pivot - low 76676.5
            (77076.5, 77240.0, 76850.4, 76902.6),
            (77173.9, 77191.3, 76860.9, 77073.0),
            (77361.7, 77466.1, 77080.0, 77163.5),
        ],
        3,
        (76676.5, 76902.6),
        "30m",
    ),
    (
        "EX3/40 supply  HYPEUSDT 30m",
        "supply",
        [
            (83.053, 84.147, 83.021, 84.011),
            (84.000, 84.316, 83.558, 83.958),
            (83.947, 84.558, 82.589, 83.358),
            (83.326, 85.253, 82.958, 84.716),       # pivot - green, high 85.253
            (84.726, 85.032, 83.484, 83.832),
            (83.821, 83.947, 81.284, 81.768),
            (81.747, 81.989, 80.179, 81.526),
        ],
        3,
        (84.716, 85.253),
        "30m",
    ),
    (
        "EX4/43 demand  HYPEUSDT 30m",
        "demand",
        [
            (78.837, 78.931, 77.749, 77.944),
            (77.944, 78.031, 77.527, 77.944),
            (77.944, 78.535, 77.581, 78.253),
            (78.253, 78.253, 77.003, 77.453),       # pivot - red, low 77.003
            (77.453, 78.797, 77.352, 78.401),
            (78.401, 78.602, 77.809, 77.809),
        ],
        3,
        (77.003, 77.453),
        "30m",
    ),
    (
        "EX5/48 demand  HYPEUSDT 30m",
        "demand",
        [
            (78.700, 78.700, 78.345, 78.355),
            (78.362, 78.700, 77.112, 77.529),
            (77.532, 77.642, 76.747, 77.522),       # pivot - the spike, low 76.747
            (77.529, 77.890, 77.181, 77.343),       # the close Shiva actually used
            (77.346, 77.735, 76.995, 77.649),
            (77.653, 77.839, 77.026, 77.350),
        ],
        2,
        (76.747, 77.343),
        "30m",
    ),
    (
        "EX6/73 supply  LTCUSD 4h",
        "supply",
        [
            (53.169, 55.130, 52.836, 54.446),       # "candle end" - high 55.130
            (52.836, 55.559, 52.836, 54.299),       # pivot - high 55.559
        ],
        1,
        (55.130, 55.559),                            # after the width rescue
        "4h",
    ),
]


def build(zone_type, bars, pivot_offset):
    """Pad the base out to a full window without letting the padding decide."""
    lows = [b[2] for b in bars]
    highs = [b[1] for b in bars]
    if zone_type == "demand":
        # well above every real low and every real body bottom
        pad_at = max(highs) * 1.05
    else:
        pad_at = min(lows) * 0.95
    pad = (pad_at, pad_at, pad_at, pad_at)

    lead = 30
    rows = [pad] * lead + list(bars)
    pivot = lead + pivot_offset
    # out to the confirmation bar, plus room for the ATR to warm up
    rows += [pad] * (pivot + scanner.SWING_LENGTH + 5 - len(rows) + 1)
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df["time"] = range(len(df))
    df["volume"] = 1.0
    return df, pivot


class SixWorkedExamples(unittest.TestCase):
    """Each zone the production builder draws must match the one drawn by hand."""

    def test_every_example_reproduces(self):
        for name, zone_type, bars, pivot_offset, (want_lo, want_hi), tf in EXAMPLES:
            with self.subTest(example=name):
                df, pivot = build(zone_type, bars, pivot_offset)
                confirmation = pivot + scanner.SWING_LENGTH
                # The REAL per-timeframe value, not a hardcoded 5 - this is what
                # makes the test exercise the auto-derivation rather than assume
                # its answer.
                base_extra = config.auto_base_extra(config.TIMEFRAME_MINUTES[tf])
                with patch.object(scanner, "ATR_PERIOD", 5), \
                     patch.object(scanner, "ZONE_GEOMETRY", "wick"), \
                     patch.object(scanner, "ZONE_BASE_EXTRA", base_extra), \
                     patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.80):
                    atr_series = scanner.atr(df, 5)
                    zone = scanner.qualify_wick_zone(
                        df, pivot, confirmation, atr_series, zone_type, "wick"
                    )
                self.assertIsNotNone(zone, f"{name}: no zone was built at all")
                # tolerance is the 2px border width the boxes were measured to
                tol = max(want_hi * 0.0002, 1e-6)
                self.assertAlmostEqual(
                    zone["bottom"], want_lo, delta=tol,
                    msg=f"{name}: bottom {zone['bottom']} != drawn {want_lo}",
                )
                self.assertAlmostEqual(
                    zone["top"], want_hi, delta=tol,
                    msg=f"{name}: top {zone['top']} != drawn {want_hi}",
                )

    def test_no_example_exceeds_the_width_cap(self):
        """The cap is a cap. EX6 is the case that made this a rule."""
        for name, zone_type, bars, pivot_offset, _, tf in EXAMPLES:
            with self.subTest(example=name):
                df, pivot = build(zone_type, bars, pivot_offset)
                base_extra = config.auto_base_extra(config.TIMEFRAME_MINUTES[tf])
                with patch.object(scanner, "ATR_PERIOD", 5), \
                     patch.object(scanner, "ZONE_GEOMETRY", "wick"), \
                     patch.object(scanner, "ZONE_BASE_EXTRA", base_extra), \
                     patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.80):
                    atr_series = scanner.atr(df, 5)
                    zone = scanner.qualify_wick_zone(
                        df, pivot, pivot + scanner.SWING_LENGTH, atr_series, zone_type, "wick"
                    )
                width = (zone["top"] - zone["bottom"]) / zone["bottom"] * 100
                self.assertLessEqual(round(width, 6), 0.80, f"{name}: {width:.3f}% wide")

    def test_base_extra_is_not_flatly_five_on_4h(self):
        """The regression this whole fix is about: 5 bars means 2.5h on 30m and
        20h on 4h - an 8x difference that was never re-derived. Pin that it no
        longer is."""
        self.assertEqual(config.auto_base_extra(config.TIMEFRAME_MINUTES["30m"]), 5)
        self.assertEqual(config.auto_base_extra(config.TIMEFRAME_MINUTES["4h"]), 1)


if __name__ == "__main__":
    unittest.main()
