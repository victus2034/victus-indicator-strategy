"""Crypto fib / trendline alerts at night (lakky, 2026-11-15): scanned and recorded for the
bot and the journal, never posted to Discord - XRP's lower 1D line was touched at 03:15 IST
on 15 Nov while the scanner was asleep (01:00-08:00 IST) and the CoinDCX bot had no trade."""
import unittest
from unittest import mock

import fib_trendline_backtest as fbt
import fib_trendline_scanner as fts
from trendlines import SUPPORT


class NightPassTests(unittest.TestCase):
    def run_pass(self, state, in_window, night, now=1_000_000.0):
        analysis = {"price": 100.0, "fib": [], "touch": [], "break": [{"key": "brk|X|4h|1", "kind": SUPPORT}]}
        with mock.patch.object(fts, "load_state", return_value=state), \
             mock.patch.object(fts, "save_state"), \
             mock.patch.object(fts, "scan_crypto", return_value=[("X", {"4h": analysis}, None)]), \
             mock.patch.object(fts, "plan_alerts", return_value=[("trendline", "brk|X|4h|1", "msg", {"id": "r"})]), \
             mock.patch.object(fts, "append_record") as record, \
             mock.patch.object(fts, "send", return_value=True) as send, \
             mock.patch.object(fts.scanner, "get_env_or_config", return_value="http://hook"), \
             mock.patch.object(fts.scanner, "in_alert_window", return_value=in_window), \
             mock.patch.object(fts.scanner, "send_status_message"), \
             mock.patch.object(fts.config, "FIB_TL_CRYPTO_NIGHT", night), \
             mock.patch.object(fts.time, "time", return_value=now), \
             mock.patch.dict("sys.modules", {"fib_trendline_daily_report": mock.MagicMock()}):
            fts.run_once()
        return send.call_count, record.call_count

    def state(self):
        return {fts.SEEDED_KEY: {f"{c}:{m}:{fts.SEED_VERSION}": 1
                                 for c in fts.CHANNELS for m in (fts.CRYPTO, fts.NSE)}}

    def test_night_alert_is_recorded_and_not_posted(self):
        state = self.state()
        self.assertEqual(self.run_pass(state, in_window=False, night=True), (0, 1))
        self.assertIn("brk|X|4h|1", state)                       # spent: the morning does not post it
        self.assertEqual(state[fts.LAST_SCAN_KEY][fts.CRYPTO], 1_000_000.0)   # a night pass is a scan

    def test_day_alert_still_posts(self):
        state = self.state()
        self.assertEqual(self.run_pass(state, in_window=True, night=True), (1, 1))

    def test_switched_off_the_night_holds_as_before(self):
        state = self.state()
        self.assertEqual(self.run_pass(state, in_window=False, night=False), (0, 0))
        self.assertNotIn("brk|X|4h|1", state)                    # still alertable in the morning
        self.assertNotIn(fts.CRYPTO, state.get(fts.LAST_SCAN_KEY, {}))


class ReplayNightTests(unittest.TestCase):
    NIGHT = 1_794_780_000 - 1_794_780_000 % 86400 + 21 * 3600    # 02:30 IST

    def test_replay_has_no_night_hold(self):
        with mock.patch.object(fbt.config, "FIB_TL_CRYPTO_NIGHT", True):
            self.assertFalse(fbt.crypto_held(self.NIGHT, 900))

    def test_replay_keeps_the_hold_when_switched_off(self):
        with mock.patch.object(fbt.config, "FIB_TL_CRYPTO_NIGHT", False):
            self.assertTrue(fbt.crypto_held(self.NIGHT, 900))


if __name__ == "__main__":
    unittest.main()
