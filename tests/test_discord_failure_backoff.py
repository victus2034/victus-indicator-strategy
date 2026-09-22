"""A failed Discord delivery must back off, or a persistent outage gets
retried every single scan forever.

send_alert only returns True on an actual delivery. Before this fix,
process_candidate only stamped last_alert_at on success, so a zone still in
band with a failed send stayed should_alert=True on the very next scan -
no backoff at all for as long as Discord kept 429ing. nse_scanner.py already
carries this fix (last_attempt_at, re-armed on ANY attempt); this is the
crypto-path mirror of it.

Being outside the 08:00-01:00 IST alert window is a deliberate hold, not a
delivery failure, and must NOT count as an attempt - a genuine alert has to
fire the instant the window reopens, not wait out a backoff for something
that was never actually tried.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import scanner

RESULT = {"symbol": "BTCUSD", "price": 100.0}
ZONE = {"bottom": 99.0, "top": 99.5}  # stop well inside the alert-stop cap


class DiscordFailureBackoffTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self._record_patch = patch.object(
            scanner, "ALERT_RECORD_FILE", Path(self._tmp.name) / "crypto_alert_records.jsonl"
        )
        self._record_patch.start()
        self.addCleanup(self._record_patch.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_a_failed_send_is_not_retried_before_the_cooldown(self):
        state = {}
        with patch.object(scanner, "in_alert_window", return_value=True), \
             patch.object(scanner, "send_alert", return_value=False) as send:
            scanner.process_candidate(state, dict(RESULT), "demand", ZONE, 0.15, 1_700_000_000.0)
            # Same zone, still in band, well inside ALERT_COOLDOWN_SECONDS later.
            scanner.process_candidate(state, dict(RESULT), "demand", ZONE, 0.15, 1_700_000_010.0)
        self.assertEqual(send.call_count, 1, "a second attempt fired before the cooldown elapsed")

    def test_it_retries_again_once_the_cooldown_has_passed(self):
        state = {}
        with patch.object(scanner, "in_alert_window", return_value=True), \
             patch.object(scanner, "send_alert", return_value=False) as send:
            scanner.process_candidate(state, dict(RESULT), "demand", ZONE, 0.15, 1_700_000_000.0)
            scanner.process_candidate(
                state, dict(RESULT), "demand", ZONE, 0.15,
                1_700_000_000.0 + scanner.ALERT_COOLDOWN_SECONDS + 1,
            )
        self.assertEqual(send.call_count, 2)

    def test_a_hold_outside_the_alert_window_is_not_an_attempt(self):
        # send_alert itself would return False here too (its own internal
        # window check), but process_candidate must not treat that as a
        # failed attempt - it never touches send_alert's Discord path.
        state = {}
        with patch.object(scanner, "in_alert_window", return_value=False), \
             patch.object(scanner, "send_alert", wraps=lambda message: False) as send:
            scanner.process_candidate(state, dict(RESULT), "demand", ZONE, 0.15, 1_700_000_000.0)
            scanner.process_candidate(state, dict(RESULT), "demand", ZONE, 0.15, 1_700_000_010.0)
        self.assertEqual(send.call_count, 2, "held-by-window calls were suppressed like a failure")

    def test_the_window_reopening_alerts_immediately_with_no_backoff_owed(self):
        state = {}
        with patch.object(scanner, "in_alert_window", return_value=False), \
             patch.object(scanner, "send_alert", return_value=False):
            scanner.process_candidate(state, dict(RESULT), "demand", ZONE, 0.15, 1_700_000_000.0)
        # Window reopens a moment later - nowhere near a full cooldown - and
        # this time delivery succeeds.
        with patch.object(scanner, "in_alert_window", return_value=True), \
             patch.object(scanner, "send_alert", return_value=True) as send:
            sent = scanner.process_candidate(state, dict(RESULT), "demand", ZONE, 0.15, 1_700_000_005.0)
        self.assertTrue(sent)
        send.assert_called_once()

    def test_a_success_still_arms_the_cooldown_as_before(self):
        state = {}
        with patch.object(scanner, "in_alert_window", return_value=True), \
             patch.object(scanner, "send_alert", return_value=True) as send:
            scanner.process_candidate(state, dict(RESULT), "demand", ZONE, 0.15, 1_700_000_000.0)
            scanner.process_candidate(state, dict(RESULT), "demand", ZONE, 0.15, 1_700_000_010.0)
        self.assertEqual(send.call_count, 1)


if __name__ == "__main__":
    unittest.main()
