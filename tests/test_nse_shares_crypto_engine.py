"""NSE and crypto must run the same zones and the same alert logic.

NSE used to carry a private copy of the zone engine - a fixed ATR band, a plain
"drop the oldest" buffer, an age counted from creation, a close-through break -
and its own copies of the numbers that drive it. When crypto moved to the v7
wick rules those copies stayed behind, and the two markets quietly ran different
strategies: different zone shapes, different stop distances, different alerts,
and nothing anywhere said so.

There is now one engine (scanner.py's, held to Shiva_Indicator_v7.pine by
tests/test_indicator_scanner_parity.py and to six hand-measured charts by
tests/test_six_worked_examples.py) and one source for its numbers (config.py).
These tests are what stops it drifting apart again.
"""
import csv
import pathlib
import unittest
from unittest.mock import patch

import pandas as pd

import config
import nse_config
import nse_scanner
import scanner

ENGINE_FUNCTIONS = (
    "atr",
    "find_pivots",
    "zone_center",
    "add_zone_if_not_overlapping",
    "record_zone_touch",
    "qualify_wick_zone",
    "build_zones",
    "too_young_to_alert",
    "nearest_active_zone",
)

# Every number the engine reads that NSE used to keep its own copy of.
SHARED_NUMBERS = (
    "ATR_PERIOD",
    "SWING_LENGTH",
    "BOX_WIDTH",
    "OVERLAP_ATR",
    "HISTORY_OF_ZONES_TO_KEEP",
    "MAX_CONSECUTIVE_ZONE_TOUCHES",
    "MIN_ZONE_AGE_CANDLES",
)

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "coti_usdt_30m_800.csv"


def real_tape():
    with FIXTURE.open(newline="", encoding="utf-8") as handle:
        rows = [
            (float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]))
            for r in csv.DictReader(handle)
        ]
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"]).assign(volume=1.0)


class SameEngineTests(unittest.TestCase):
    def test_every_engine_function_is_the_crypto_one(self):
        for name in ENGINE_FUNCTIONS:
            with self.subTest(function=name):
                self.assertIs(
                    getattr(nse_scanner, name),
                    getattr(scanner, name),
                    f"nse_scanner.{name} is a separate copy - the two markets can drift again",
                )

    def test_the_numbers_come_from_one_place(self):
        for name in SHARED_NUMBERS:
            with self.subTest(setting=name):
                self.assertEqual(getattr(nse_config, name), getattr(config, name))
                self.assertEqual(getattr(nse_scanner, name), getattr(config, name))

    def test_nse_runs_the_v7_values_not_the_old_ones(self):
        # The four the wick geometry overrides. NSE used to sit on the older
        # 2.0 / 2 / 20 / 60.
        self.assertEqual(nse_scanner.OVERLAP_ATR, 1.0)
        self.assertEqual(nse_scanner.MAX_CONSECUTIVE_ZONE_TOUCHES, 0)
        self.assertEqual(nse_scanner.MIN_ZONE_AGE_CANDLES, 15)
        self.assertEqual(nse_scanner.HISTORY_OF_ZONES_TO_KEEP, 50)

    def test_the_alert_stop_limit_is_the_crypto_one(self):
        self.assertEqual(scanner.MAX_ALERT_STOP_PCT, config.MAX_ALERT_STOP_PCT)


class TimeframeBindingTests(unittest.TestCase):
    """The engine reads one timeframe-dependent number: ZONE_BASE_EXTRA."""

    def setUp(self):
        original = scanner.ZONE_BASE_EXTRA
        self.addCleanup(setattr, scanner, "ZONE_BASE_EXTRA", original)

    def test_30m_gets_a_five_bar_base(self):
        with patch.dict("os.environ", {}, clear=False):
            self.assertEqual(nse_scanner.bind_zone_engine("30m"), 5)
            self.assertEqual(scanner.ZONE_BASE_EXTRA, 5)

    def test_4h_gets_a_one_bar_base(self):
        self.assertEqual(nse_scanner.bind_zone_engine("4h"), 1)
        self.assertEqual(scanner.ZONE_BASE_EXTRA, 1)

    def test_it_matches_what_crypto_derives_for_the_same_timeframe(self):
        for timeframe in ("30m", "4h"):
            expected = config.auto_base_extra(config.TIMEFRAME_MINUTES[timeframe])
            self.assertEqual(nse_scanner.bind_zone_engine(timeframe), expected)

    def test_an_explicit_override_still_wins_as_it_does_for_crypto(self):
        with patch.dict("os.environ", {"VICTUS_ZONE_BASE_EXTRA": "3"}):
            self.assertEqual(nse_scanner.bind_zone_engine("30m"), 3)

    def test_it_follows_the_scanners_own_timeframe_by_default(self):
        with patch.object(nse_scanner, "TIMEFRAME", "30m"):
            self.assertEqual(nse_scanner.bind_zone_engine(), 5)
        with patch.object(nse_scanner, "TIMEFRAME", "4h"):
            self.assertEqual(nse_scanner.bind_zone_engine(), 1)

    def test_binding_is_lazy_so_merely_importing_nse_leaves_crypto_alone(self):
        # scan_symbol binds, import does not: a crypto-only process (the crypto
        # backtest, paper trading) imports nse_scanner and must not have its
        # engine reconfigured behind its back.
        import inspect

        source = inspect.getsource(nse_scanner)
        module_level = source.split("def bind_zone_engine", 1)[0]
        self.assertNotIn("bind_zone_engine(", module_level)


class RealCandleTests(unittest.TestCase):
    """NSE now builds v7 wick zones. Run it over 800 real candles, not a toy."""

    def setUp(self):
        original = scanner.ZONE_BASE_EXTRA
        self.addCleanup(setattr, scanner, "ZONE_BASE_EXTRA", original)
        nse_scanner.bind_zone_engine("30m")

    def test_nse_builds_the_same_zones_as_crypto_on_the_same_candles(self):
        tape = real_tape()
        nse_supply, nse_demand = nse_scanner.build_zones(tape)
        crypto_supply, crypto_demand = scanner.build_zones(tape)
        edges = lambda zones: [(z["created_idx"], z["top"], z["bottom"], z["active"]) for z in zones]
        self.assertEqual(edges(nse_supply), edges(crypto_supply))
        self.assertEqual(edges(nse_demand), edges(crypto_demand))
        self.assertGreater(len(nse_supply) + len(nse_demand), 0, "no zones on 800 real candles")

    def test_the_zones_are_v7_wick_zones_not_atr_bands(self):
        supply, demand = nse_scanner.build_zones(real_tape())
        zones = supply + demand
        self.assertTrue(zones)
        for zone in zones:
            self.assertEqual(zone["geometry"], "wick")
            # The touch clock and its bookkeeping exist only on the v7 engine.
            self.assertIn("clock", zone)
            self.assertIn("last_gap", zone)

    def test_no_zone_is_wider_than_the_cap(self):
        # The old ATR band had no cap at all - 14% of live zones once came out
        # over the limit. Degenerate wicks are floored by design and exempt.
        supply, demand = nse_scanner.build_zones(real_tape())
        for zone in supply + demand:
            if zone.get("degenerate"):
                continue
            width = (zone["top"] - zone["bottom"]) / zone["bottom"] * 100.0
            self.assertLessEqual(width, config.ZONE_MAX_WIDTH_PCT + 1e-6, zone)


class AlertLogicTests(unittest.TestCase):
    RESULT = {"symbol": "TCS.NS", "price": 100.0}
    NORMAL = {"bottom": 99.0, "top": 99.5}  # stop well inside 1.5%
    WIDE = {"bottom": 96.0, "top": 99.5}    # stop more than 3% from entry

    def send(self, zone):
        with patch.object(nse_scanner, "send_alert", return_value=True) as send, \
             patch.object(nse_scanner, "record_delivered_zone_alert"):
            sent = nse_scanner.process_candidate({}, dict(self.RESULT), "demand", zone, 0.15, 1000)
        return sent, send

    def test_a_zone_with_too_wide_a_stop_sends_nothing(self):
        # Crypto withholds it; NSE used to send it.
        sent, send = self.send(self.WIDE)
        self.assertFalse(sent)
        send.assert_not_called()

    def test_a_normal_zone_still_alerts(self):
        sent, send = self.send(self.NORMAL)
        self.assertTrue(sent)
        send.assert_called_once()

    def test_the_limit_can_be_switched_off_the_same_way(self):
        with patch.object(scanner, "MAX_ALERT_STOP_PCT", 0):
            sent, send = self.send(self.WIDE)
        self.assertTrue(sent)


class RepeatSuppressionTests(unittest.TestCase):
    def test_it_follows_the_alert_cooldown_like_crypto(self):
        self.assertEqual(nse_scanner.ZONE_REPEAT_SUPPRESSION_SECONDS, nse_scanner.ALERT_COOLDOWN_SECONDS)

    def test_the_30m_process_follows_its_own_cooldown(self):
        # nse_scanner_30m patches the cooldown to 30 minutes after import, so
        # the suppression has to be patched with it or it stays at the 4h value.
        import importlib

        import nse_scanner_30m

        importlib.reload(nse_scanner_30m)
        try:
            self.assertEqual(nse_scanner.ALERT_COOLDOWN_SECONDS, 30 * 60)
            self.assertEqual(nse_scanner.ZONE_REPEAT_SUPPRESSION_SECONDS, 30 * 60)
        finally:
            importlib.reload(nse_scanner)


if __name__ == "__main__":
    unittest.main()
