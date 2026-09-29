"""Fib + trendline alerts: the engines, the zone numbering and the once-only rules."""
import pathlib
import unittest
from datetime import datetime, timezone

import fib_engine
import fib_trendline_scanner as fts
from trendlines import RESISTANCE, SUPPORT, build_trendlines

REFERENCE = pathlib.Path(__file__).resolve().parents[2] / "indicator improvent by claude" / "fib_reference.py"
MARKER = "# ---- copied from fib_reference.py below this line ----\n"


class FibEngineIsTheIndicatorsTests(unittest.TestCase):
    @unittest.skipUnless(REFERENCE.exists(), "indicator folder is not beside this repo (CI)")
    def test_fib_engine_is_fib_reference_unchanged(self):
        ours = pathlib.Path(fib_engine.__file__).read_text(encoding="utf-8").split(MARKER, 1)[1]
        theirs = REFERENCE.read_text(encoding="utf-8")
        self.assertEqual(
            ours.replace("\r\n", "\n"), theirs.replace("\r\n", "\n"),
            "fib_reference.py changed - copy it into fib_engine.py below the marker again",
        )

    def test_levels_are_shivas_ex1_labels(self):
        self.assertEqual([round(v, 2) for v in fib_engine.levels(94.89, 110.55)], [105.23, 103.50, 101.94, 100.21])


class FibZoneNumberingTests(unittest.TestCase):
    def test_zone_2_is_the_lower_box_on_an_up_move(self):
        zones = {n: (lo, hi) for n, lo, hi, _, _ in fts.fib_zones(1, 94.89, 110.55)}
        self.assertLess(zones[2][1], zones[1][0])

    def test_zone_2_is_the_upper_box_on_a_down_move(self):
        zones = {n: (lo, hi) for n, lo, hi, _, _ in fts.fib_zones(-1, 110.55, 94.89)}
        self.assertGreater(zones[2][0], zones[1][1])

    def test_ex2_entry_and_sl_inside_zone(self):
        # EX 2 ETH: 2562.8 -> 2806.6, SL fibs 2714.87/2711.85 and 2663.51/2660.49
        # (labels read off his chart, so within 0.02% - fib_examples_check.py uses a tolerance too)
        zones = {n: (e, s) for n, _, _, e, s in fts.fib_zones(1, 2562.8, 2806.6)}
        for got, want in zip(zones[1] + zones[2], (2714.87, 2711.85, 2663.51, 2660.49)):
            self.assertLess(abs(got - want) / want, 0.0002)


def rising_lows_then_break():
    """Two swing lows at 100 and 110, higher prices between, then a close under the line."""
    lows = [130.0] * 60
    lows[10] = 100.0
    lows[35] = 110.0
    highs = [v + 5 for v in lows]
    closes = [v + 2 for v in lows]
    return highs, lows, closes


class TrendlineTests(unittest.TestCase):
    def test_two_rising_swing_lows_make_a_support_line(self):
        highs, lows, closes = rising_lows_then_break()
        lines = [l for l in build_trendlines(highs, lows, closes, 10, 6) if l.kind == SUPPORT]
        self.assertEqual([(l.x1, l.y1, l.x2, l.y2) for l in lines], [(10, 100.0, 35, 110.0)])
        self.assertTrue(lines[0].alive)
        self.assertEqual(lines[0].created, 45)

    def test_a_close_through_ends_the_line(self):
        highs, lows, closes = rising_lows_then_break()
        closes[50] = 100.0            # line is at 116 by bar 50
        line = [l for l in build_trendlines(highs, lows, closes, 10, 6) if l.kind == SUPPORT][0]
        self.assertEqual(line.broken_at, 50)

    def test_a_close_before_the_line_is_drawn_is_not_checked(self):
        highs, lows, closes = rising_lows_then_break()
        closes[40] = 90.0             # between swing (35) and confirm (45) - the Pine never looks
        line = [l for l in build_trendlines(highs, lows, closes, 10, 6) if l.kind == SUPPORT][0]
        self.assertTrue(line.alive)

    def test_falling_swing_highs_make_a_resistance_line(self):
        highs = [100.0] * 60
        highs[10], highs[35] = 150.0, 140.0
        lows = [v - 5 for v in highs]
        lines = build_trendlines(highs, lows, [v - 2 for v in highs], 10, 6)
        self.assertEqual([(l.kind, l.y1, l.y2) for l in lines], [(RESISTANCE, 150.0, 140.0)])


class CandleTests(unittest.TestCase):
    def test_monthly_candles_group_by_calendar_month(self):
        day = lambda y, m, d: int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())
        daily = [[day(2026, 8, 30), 1, 5, 1, 2], [day(2026, 8, 31), 2, 6, 0.5, 3], [day(2026, 9, 1), 3, 4, 2, 3.5]]
        months = fts.monthly_from_daily(daily)
        self.assertEqual(months[0], [day(2026, 8, 1), 1, 6, 0.5, 3])
        self.assertEqual(months[1], [day(2026, 9, 1), 3, 4, 2, 3.5])

    def test_the_current_month_is_still_forming(self):
        sept = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp())
        self.assertFalse(fts.candle_is_closed(sept, "1M", datetime(2026, 9, 29, tzinfo=timezone.utc).timestamp()))
        self.assertTrue(fts.candle_is_closed(sept, "1M", datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp()))


class OnceOnlyTests(unittest.TestCase):
    def fib(self, key="fib|X|4h|1|0|110|2"):
        return {"key": key, "d": 1, "zone": 2, "low": 100, "high": 101, "entry": 100.8, "sl": 100.7,
                "base": 90, "top": 110, "base_time": "a", "top_time": "b"}

    def touch(self, key="tl|X|4h|0|1|2"):
        return {"key": key, "kind": SUPPORT, "level": 100.0, "distance": 0.1, "from": (90, "a"), "to": (95, "b")}

    def analysis(self, fib=(), touch=()):
        return {"fib": list(fib), "touch": list(touch), "break": [], "price": 100.5}

    def test_a_fib_zone_alerts_once(self):
        state = {}
        first = fts.plan_alerts(state, "X", "4h", self.analysis(fib=[self.fib()]), 0)
        self.assertEqual(len(first), 1)
        fts.mark_sent(state, first[0][1], 0)
        self.assertEqual(fts.plan_alerts(state, "X", "4h", self.analysis(fib=[self.fib()]), 10**6), [])

    def test_fib_and_trendline_go_to_different_channels(self):
        planned = fts.plan_alerts({}, "X", "4h", self.analysis(fib=[self.fib()], touch=[self.touch()]), 0)
        self.assertEqual(sorted(c for c, _, _ in planned), ["fib", "trendline"])

    def test_a_touch_rearms_only_after_leaving_the_band_and_a_candle(self):
        state = {}
        (_, key, _), = fts.plan_alerts(state, "X", "4h", self.analysis(touch=[self.touch()]), 0)
        fts.mark_sent(state, key, 0)
        # still in the band: nothing
        self.assertEqual(fts.plan_alerts(state, "X", "4h", self.analysis(touch=[self.touch()]), 20000), [])
        # leaves the band, comes back within the same candle: nothing
        fts.plan_alerts(state, "X", "4h", self.analysis(), 100)
        self.assertEqual(fts.plan_alerts(state, "X", "4h", self.analysis(touch=[self.touch()]), 200), [])
        # leaves again, comes back a candle later: alerts
        fts.plan_alerts(state, "X", "4h", self.analysis(), 20000)
        self.assertEqual(len(fts.plan_alerts(state, "X", "4h", self.analysis(touch=[self.touch()]), 20001)), 1)


class SeedingTests(unittest.TestCase):
    """A channel's first pass with its webhook seeds silently; before that nothing is recorded."""

    def setUp(self):
        import os
        import tempfile
        from unittest import mock

        self.tmp = tempfile.TemporaryDirectory()
        self.sent, self.status = [], []
        self.fibs = [OnceOnlyTests().fib("fib|X|4h|1|0|110|2")]
        self.touches = [OnceOnlyTests().touch("tl|X|4h|0|1|2")]
        patches = [
            mock.patch.object(fts, "STATE_FILE", pathlib.Path(self.tmp.name) / "state.json"),
            mock.patch.object(fts.scanner, "active_watchlist", lambda: ["X"]),
            mock.patch.object(fts, "scan_symbol", lambda s, tfs, now: (s, {"4h": {
                "fib": list(self.fibs), "touch": list(self.touches), "break": [], "price": 100.5}}, None)),
            mock.patch.object(fts.scanner, "in_alert_window", lambda: True),
            mock.patch.object(fts.scanner, "send_discord_message",
                              lambda message, webhook_env_name, webhook_config_value: self.sent.append(webhook_env_name) or True),
            mock.patch.object(fts.scanner, "send_status_message", self.status.append),
            mock.patch.dict(os.environ, {fts.FIB_ENV: "https://example.invalid/fib", fts.TL_ENV: ""}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_seeds_each_channel_only_once_its_webhook_exists(self):
        import os

        fts.run_once()
        self.assertEqual(self.sent, [])                                  # fib seeded, not posted
        self.assertEqual(len(self.status), 1)
        self.assertNotIn(self.touches[0]["key"], fts.load_state())      # no webhook: nothing recorded

        self.fibs.append(OnceOnlyTests().fib("fib|X|4h|1|0|120|1"))     # a new fib zone
        fts.run_once()
        self.assertEqual(self.sent, [fts.FIB_ENV])

        os.environ[fts.TL_ENV] = "https://example.invalid/tl"           # trendline webhook added later
        fts.run_once()
        self.assertEqual(self.sent, [fts.FIB_ENV])                      # seeded, still no burst
        self.assertIn(self.touches[0]["key"], fts.load_state())
        self.assertEqual(len(self.status), 2)


if __name__ == "__main__":
    unittest.main()
