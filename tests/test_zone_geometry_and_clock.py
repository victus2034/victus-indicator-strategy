"""The two v7 fixes ported into the scanner, plus the geometry switch.

Backtest behind these: ZONE_GEOMETRY_BACKTEST_FINDINGS.md.
"""
import unittest
from unittest.mock import patch

import pandas as pd

import scanner


def frame(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"]).assign(
        time=range(len(rows)), volume=1.0
    )


class TrimKeepsTheStrongZone(unittest.TestCase):
    """A full buffer must drop the weakest zone, not the oldest."""

    def zones(self, now):
        # index 0 is oldest and untouched for 500 bars - the strong one.
        # index 1 was touched last bar - the weak one.
        return [
            {"created_idx": 0, "clock": now - 500, "active": True, "id": "old_quiet"},
            {"created_idx": 400, "clock": now - 1, "active": True, "id": "new_busy"},
            {"created_idx": 450, "clock": now, "active": True, "id": "newest"},
        ]

    def test_weakest_first_keeps_the_old_untouched_zone(self):
        now = 600
        zones = self.zones(now)
        with patch.object(scanner, "HISTORY_OF_ZONES_TO_KEEP", 2), \
             patch.object(scanner, "ZONE_EVICT_WEAKEST", True):
            scanner.trim_zone_history(zones, now)
        kept = [z["id"] for z in zones]
        self.assertIn("old_quiet", kept, "the strongest zone was evicted")
        self.assertNotIn("new_busy", kept)

    def test_fifo_still_available_and_drops_the_oldest(self):
        now = 600
        zones = self.zones(now)
        with patch.object(scanner, "HISTORY_OF_ZONES_TO_KEEP", 2), \
             patch.object(scanner, "ZONE_EVICT_WEAKEST", False):
            scanner.trim_zone_history(zones, now)
        self.assertEqual([z["id"] for z in zones], ["new_busy", "newest"])

    def test_the_zone_just_created_is_never_the_victim(self):
        now = 600
        zones = self.zones(now)
        with patch.object(scanner, "HISTORY_OF_ZONES_TO_KEEP", 2), \
             patch.object(scanner, "ZONE_EVICT_WEAKEST", True):
            scanner.trim_zone_history(zones, now)
        self.assertIn("newest", [z["id"] for z in zones])

    def test_broken_zones_go_before_live_ones(self):
        now = 600
        zones = [
            {"created_idx": 0, "clock": now - 900, "active": False, "id": "dead"},
            {"created_idx": 10, "clock": now - 500, "active": True, "id": "live_quiet"},
            {"created_idx": 450, "clock": now, "active": True, "id": "newest"},
        ]
        with patch.object(scanner, "HISTORY_OF_ZONES_TO_KEEP", 2), \
             patch.object(scanner, "ZONE_EVICT_WEAKEST", True):
            scanner.trim_zone_history(zones, now)
        self.assertNotIn("dead", [z["id"] for z in zones])


class ClockRestartsOnTouch(unittest.TestCase):
    """MIN_ZONE_AGE_CANDLES should mean untouched, not merely old."""

    def zone(self):
        return {
            "bottom": 100.0, "top": 101.0, "active": True, "over_touched": False,
            "created_idx": 0, "clock": 0, "last_gap": None,
        }

    def test_old_but_constantly_touched_zone_is_too_young(self):
        z = self.zone()
        with patch.object(scanner, "MIN_ZONE_AGE_CANDLES", 15), \
             patch.object(scanner, "ZONE_CLOCK_RESTARTS_ON_TOUCH", True):
            for i in range(1, 60):                      # touched every bar
                scanner.record_zone_touch(z, 100.5, 100.2, i)
            self.assertTrue(scanner.too_young_to_alert(z, 60))

    def test_old_and_left_alone_zone_qualifies(self):
        z = self.zone()
        with patch.object(scanner, "MIN_ZONE_AGE_CANDLES", 15), \
             patch.object(scanner, "ZONE_CLOCK_RESTARTS_ON_TOUCH", True):
            scanner.record_zone_touch(z, 100.5, 100.2, 5)   # one touch early on
            for i in range(6, 60):                          # then silence
                scanner.record_zone_touch(z, 99.0, 98.0, i)
            self.assertFalse(scanner.too_young_to_alert(z, 60))

    def test_touch_now_is_judged_on_the_silence_it_earned_first(self):
        z = self.zone()
        with patch.object(scanner, "MIN_ZONE_AGE_CANDLES", 15), \
             patch.object(scanner, "ZONE_CLOCK_RESTARTS_ON_TOUCH", True):
            for i in range(1, 40):
                scanner.record_zone_touch(z, 99.0, 98.0, i)  # quiet for 39 bars
            scanner.record_zone_touch(z, 100.5, 100.2, 40)   # touching right now
            # A gap of zero must not disqualify it - it earned 40 quiet bars.
            self.assertFalse(scanner.too_young_to_alert(z, 40))

    def test_flag_off_restores_created_idx_behaviour(self):
        z = self.zone()
        with patch.object(scanner, "MIN_ZONE_AGE_CANDLES", 15), \
             patch.object(scanner, "ZONE_CLOCK_RESTARTS_ON_TOUCH", False):
            for i in range(1, 60):
                scanner.record_zone_touch(z, 100.5, 100.2, i)
            self.assertFalse(scanner.too_young_to_alert(z, 60))


class GeometrySwitch(unittest.TestCase):
    """wick geometry = [low, body bottom] for demand, mirrored for supply."""

    def build(self, geometry):
        # The rescue is off here: this synthetic zone is 8.9% wide, so it would
        # fire and move the near edge these assertions are about.
        rows = [(10.0, 10.2, 9.9, 10.1)] * 12
        # pivot low at index 12: a long lower wick under a green body
        rows.append((9.8, 9.9, 9.0, 9.85))
        rows += [(10.0, 10.2, 9.9, 10.1)] * 12
        df = frame(rows)
        atr_series = scanner.atr(df, 5)
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.0):
            return scanner.qualify_wick_zone(df, 12, 22, atr_series, "demand", geometry)

    def test_wick_uses_the_body_edge_not_the_close(self):
        z = self.build("wick")
        self.assertAlmostEqual(z["bottom"], 9.0, places=6)
        # green candle: body bottom is the OPEN (9.8), not the close (9.85)
        self.assertLessEqual(z["top"], 9.85)
        self.assertAlmostEqual(z["top"], 9.8, places=6)

    def test_atr_geometry_is_unchanged(self):
        z = self.build("atr")
        self.assertAlmostEqual(z["bottom"], 9.0, places=6)
        self.assertGreater(z["top"], 9.0)
        self.assertEqual(z["geometry"], "atr")

    def test_wick_window_never_reaches_past_confirmation(self):
        rows = [(10.0, 10.2, 9.9, 10.1)] * 30
        df = frame(rows)
        atr_series = scanner.atr(df, 5)
        with patch.object(scanner, "ZONE_BASE_EXTRA", 50):
            z = scanner.qualify_wick_zone(df, 10, 12, atr_series, "demand", "wick")
        self.assertIsNotNone(z)


class ShadowNeverDelivers(unittest.TestCase):
    """The shadow stream must be incapable of sending a real alert."""

    def result(self):
        return {
            "symbol": "BTCUSD", "exchange": "delta", "price": 100.0,
            "supply_rating": None, "demand_rating": None,
            "supply_score": None, "demand_score": None,
        }

    def zone(self):
        return {
            "type": "demand", "top": 100.5, "bottom": 99.0, "body_entry": 100.5,
            "active": True, "over_touched": False, "created_idx": 0, "clock": 0,
            "last_gap": None, "atr": 1.0, "geometry": "wick",
            "wick_to_body": 1.0, "wick_atr": 1.0, "departure_atr": 1.0,
            "touch_count": 0,
        }

    def test_shadow_writes_its_own_log_and_never_calls_send_alert(self):
        import json, tempfile
        from pathlib import Path

        def explode(*_args, **_kwargs):
            raise AssertionError("shadow path reached send_alert")

        with tempfile.TemporaryDirectory() as tmp:
            shadow = Path(tmp) / "shadow.jsonl"
            live = Path(tmp) / "live.jsonl"
            with patch.object(scanner, "send_alert", explode), \
                 patch.object(scanner, "SHADOW_ALERT_RECORD_FILE", shadow), \
                 patch.object(scanner, "ALERT_RECORD_FILE", live), \
                 patch.object(scanner, "MIN_DISTANCE_PCT", 0.0), \
                 patch.object(scanner, "MAX_DISTANCE_PCT", 100.0), \
                 patch.object(scanner, "TIMEFRAME", "4h"):
                sent = scanner.process_candidate(
                    {}, self.result(), "demand", self.zone(), 0.5, 1.0, shadow=True
                )
            self.assertTrue(sent)
            self.assertTrue(shadow.exists(), "shadow record was not written")
            self.assertFalse(live.exists(), "shadow leaked into the live log")
            record = json.loads(shadow.read_text(encoding="utf-8").splitlines()[0])
            self.assertTrue(record["shadow"])
            self.assertEqual(record["geometry"], "wick")

    def test_shadow_state_cannot_suppress_a_live_alert(self):
        live_key = scanner.build_state_key("BTCUSD", "demand", self.zone())
        self.assertFalse(live_key.startswith("shadow:"))


class WatchBandDoesNotOverlapTheAlertBand(unittest.TestCase):
    """A watch row must never exist for a zone the alert path already covers.

    The watch band used to start at MIN_DISTANCE_PCT (0), the same floor as
    the alert band, so a zone already inside 0.20% whose alert was
    suppressed by cooldown or noise control on this scan still got a watch
    row on its own separate cooldown clock. entry_confirm would then ping
    GET READY or ENTRY NOW for a zone #crypto-30m-alerts never mentioned at
    that moment - 14 of 46 in-band watch rows measured had no alert within
    5 minutes either side. The watch band now starts strictly above
    MAX_DISTANCE_PCT, so it only ever covers distance the alert path cannot
    see at all.
    """

    def result(self):
        return {
            "symbol": "BTCUSD", "exchange": "delta", "price": 100.0,
            "supply_rating": None, "demand_rating": None,
            "supply_score": None, "demand_score": None,
        }

    def zone(self, top=100.5):
        return {
            "type": "demand", "top": top, "bottom": 99.0, "body_entry": top,
            "active": True, "over_touched": False, "created_idx": 0, "clock": 0,
            "last_gap": None, "atr": 1.0, "geometry": "wick",
            "wick_to_body": 1.0, "wick_atr": 1.0, "departure_atr": 1.0,
            "touch_count": 0,
        }

    def _run(self, distance_pct, state=None):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "live.jsonl"
            watch = Path(tmp) / "watch.jsonl"
            with patch.object(scanner, "send_alert", return_value=False),                  patch.object(scanner, "ALERT_RECORD_FILE", live),                  patch.object(scanner, "WATCH_RECORD_FILE", watch),                  patch.object(scanner, "MIN_DISTANCE_PCT", 0.0),                  patch.object(scanner, "MAX_DISTANCE_PCT", 0.20),                  patch.object(scanner, "WATCH_DISTANCE_PCT", 0.75),                  patch.object(scanner, "TIMEFRAME", "30m"):
                scanner.process_candidate(
                    state if state is not None else {},
                    self.result(), "demand", self.zone(), distance_pct, 1.0,
                )
            return watch.exists()

    def test_a_zone_inside_the_alert_band_gets_no_watch_row(self):
        # 0.10% is inside the alert band. send_alert is stubbed to fail, the
        # same shape as a suppressed alert, so no alert row is written -
        # this must not fall back to writing a watch row instead.
        self.assertFalse(self._run(0.10))

    def test_a_zone_between_the_two_bands_gets_a_watch_row(self):
        # 0.40% is above MAX_DISTANCE_PCT (0.20) and within WATCH_DISTANCE_PCT
        # (0.75) - the range the alert path never sees at all.
        self.assertTrue(self._run(0.40))

    def test_a_zone_beyond_the_watch_band_gets_neither(self):
        self.assertFalse(self._run(1.50))


class BreakRule(unittest.TestCase):
    """A wick through the far edge kills the zone when the flag is set.

    Not cosmetic. Measured over 187 days of 30m, the wick construction nets
    0.020 per trade under the close rule and 0.055 under this one, so the two
    ship together - see ZONE_GEOMETRY_BACKTEST_FINDINGS.md.

    ATR_PERIOD is patched down because config's 50 over a 31-bar synthetic
    frame gives an all-NaN atr, and qualify_wick_zone then builds nothing.
    """

    def frame_with_wick_raid(self):
        rows = [(10.0, 10.2, 9.9, 10.1)] * 12
        rows.append((9.8, 9.9, 9.0, 9.85))       # pivot low at 9.0
        rows += [(10.0, 10.2, 9.9, 10.1)] * 12
        rows.append((10.0, 10.2, 8.5, 10.1))     # spikes under 9.0, closes above
        rows += [(10.0, 10.2, 9.9, 10.1)] * 5
        return frame(rows)

    def build(self, break_on_wick):
        with patch.object(scanner, "ZONE_BREAK_ON_WICK", break_on_wick), \
             patch.object(scanner, "ZONE_GEOMETRY", "wick"), \
             patch.object(scanner, "ATR_PERIOD", 5):
            _, demand = scanner.build_zones(self.frame_with_wick_raid())
        return demand

    def test_wick_raid_kills_the_zone(self):
        demand = self.build(break_on_wick=True)
        self.assertTrue(demand, "no demand zone was built")
        # The rebuild puts a fresh live zone in the list right after the break,
        # so check the ORIGINAL - the one anchored on the 9.0 pivot - rather
        # than asserting nothing in the list is alive.
        original = [z for z in demand if not z.get("rebuilt")]
        self.assertTrue(original, "the original zone vanished from the list")
        self.assertTrue(
            all(not z["active"] for z in original),
            "a wick through the far edge left the original zone alive",
        )

    def test_close_rule_leaves_it_alive(self):
        demand = self.build(break_on_wick=False)
        self.assertTrue(demand, "no demand zone was built")
        self.assertTrue(
            any(z["active"] for z in demand),
            "close rule should survive a wick that closed back above",
        )


class WideZoneRescue(unittest.TestCase):
    """EX 6: a zone can be right by the geometry and still untradeable.

    "WE CAN NOT TAKE ANY TRADE WITH SL LIKE 2%". The near edge re-anchors to a
    neighbouring candle's own extreme - the "candle end" - rather than being cut
    to an arbitrary width, so the box still sits on something real.
    """

    def window(self, highs=None, lows=None):
        n = len(highs or lows)
        return pd.DataFrame({
            "high": highs or [0.0] * n, "low": lows or [0.0] * n,
            "open": [0.0] * n, "close": [0.0] * n,
        })

    def test_ex6_reproduces_the_hand_drawn_fix(self):
        # LTC 4h: far 55.559, body-based near 54.446 -> 2.05%. Shiva moved the
        # near edge to 55.130, the neighbouring candle's high, giving 0.78%.
        w = self.window(highs=[55.130, 55.559])
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.80):
            near = scanner.tighten_wide_zone(w, "supply", 55.559, 54.446)
        self.assertAlmostEqual(near, 55.130, places=3)

    def test_ex5_is_left_alone_at_the_shipped_limit(self):
        # 0.777% as drawn. The shipped 0.80 limit must not re-cut it; a 0.75
        # limit would, which is why 0.80 is the default.
        w = self.window(lows=[78.345, 77.112, 76.747, 77.181, 76.995])
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.80):
            near = scanner.tighten_wide_zone(w, "demand", 76.747, 77.343)
        self.assertAlmostEqual(near, 77.343, places=3)

    def test_narrow_zones_are_never_touched(self):
        w = self.window(highs=[84.316, 84.558, 85.253, 85.032, 83.947])
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.80):
            near = scanner.tighten_wide_zone(w, "supply", 85.253, 84.716)
        self.assertAlmostEqual(near, 84.716, places=3)

    def test_prefers_the_widest_level_still_inside_the_limit(self):
        # Three candidates all inside the limit: take the one leaving the widest
        # zone, not the tightest.
        # 100.2 -> 0.798%, 100.4 -> 0.598%, 100.7 -> 0.298%. All three are
        # inside the limit, so the widest of them wins.
        w = self.window(highs=[100.7, 100.4, 100.2, 101.0])
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.80):
            near = scanner.tighten_wide_zone(w, "supply", 101.0, 98.0)
        self.assertAlmostEqual(near, 100.2, places=3)

    def test_falls_back_to_cutting_when_the_window_offers_no_level(self):
        w = self.window(highs=[90.0, 101.0])            # nothing between
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.80):
            near = scanner.tighten_wide_zone(w, "supply", 101.0, 98.0)
        self.assertAlmostEqual((101.0 - near) / near * 100, 0.80, places=6)

    def test_zero_disables_the_rescue(self):
        w = self.window(highs=[55.130, 55.559])
        with patch.object(scanner, "ZONE_MAX_WIDTH_PCT", 0.0):
            near = scanner.tighten_wide_zone(w, "supply", 55.559, 54.446)
        self.assertAlmostEqual(near, 54.446, places=3)


if __name__ == "__main__":
    unittest.main()
