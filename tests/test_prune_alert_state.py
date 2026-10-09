"""Pruning the alert state must never change an alert decision.

Entries for every nearest zone piled up forever (36,000 keys in the 30m file).
prune_alert_state drops only entries that would decide the same way if they
were recreated from the default - checked here against process_candidate.
"""
import unittest
from unittest import mock

import scanner

ZONE = {"top": 101.0, "bottom": 100.0, "type": "supply"}
RESULT = {"symbol": "BTCUSD", "price": 99.9, "supply_rating": None, "supply_score": None}
COOLDOWN = scanner.ALERT_COOLDOWN_SECONDS
SUPPRESS = scanner.ZONE_REPEAT_SUPPRESSION_SECONDS


def prune(state, now):
    return scanner.prune_alert_state(state, now, COOLDOWN, 3600, SUPPRESS)


class PruneAlertStateTests(unittest.TestCase):
    def decide(self, state, now, distance=0.1):
        with mock.patch.object(scanner, "send_alert", return_value=True) as send, \
                mock.patch.object(scanner, "record_delivered_zone_alert"), \
                mock.patch.object(scanner, "in_alert_window", return_value=True):
            scanner.process_candidate(state, RESULT, "supply", ZONE, distance, now)
            return send.called

    def test_pruned_state_decides_like_the_full_state(self):
        start = 1_000_000.0
        key = scanner.build_state_key("BTCUSD", "supply", ZONE)
        noise = scanner.exact_zone_identity("BTCUSD", "supply", ZONE)
        cases = [
            {key: {"in_zone": True, "last_alert_at": start, "last_attempt_at": start},
             "_noise_control": {noise: start}},
            {key: {"in_zone": False, "last_alert_at": start, "last_attempt_at": start},
             "_noise_control": {noise: start}},
            {key: {"in_zone": True, "last_alert_at": 0.0, "last_attempt_at": 0.0}},
        ]
        for case in cases:
            for later in (60, COOLDOWN - 1, COOLDOWN, SUPPRESS + 1, 10 * COOLDOWN):
                now = start + later
                with self.subTest(case=case, later=later):
                    import copy
                    full, pruned = copy.deepcopy(case), prune(copy.deepcopy(case), now)
                    self.assertEqual(self.decide(full, now), self.decide(pruned, now))

    def test_stale_entries_are_dropped_and_live_ones_kept(self):
        now = 1_000_000.0
        state = {
            "__last_scan_started__": {"30m": now},
            "A|supply|1|2": {"in_zone": False, "last_alert_at": 0.0, "last_attempt_at": 0.0},
            "B|supply|1|2": {"in_zone": True, "last_alert_at": now - 60, "last_attempt_at": now - 60},
            "C|range_filter|buy": {"last_alert_at": now - 7200},
            "D|range_filter|buy": {"last_alert_at": now - 60},
            "_noise_control": {"old": now - SUPPRESS, "new": now - 60},
            "_watch": {"old": now - 1800, "new": now - 60},
        }
        prune(state, now)
        self.assertEqual(
            sorted(state), ["B|supply|1|2", "D|range_filter|buy", "__last_scan_started__", "_noise_control"]
        )
        self.assertEqual(state["_noise_control"], {"new": now - 60})


if __name__ == "__main__":
    unittest.main()
