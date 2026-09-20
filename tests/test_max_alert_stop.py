import unittest
from unittest.mock import patch

import scanner


RESULT = {"symbol": "BTCUSD", "price": 100.0}
NORMAL = {"bottom": 99.0, "top": 99.5}   # stop well inside 1.5%
WIDE = {"bottom": 96.0, "top": 99.5}     # stop more than 3% away


class MaxAlertStopTests(unittest.TestCase):
    def test_stop_distance_of_the_fixtures(self):
        self.assertLess(scanner.planned_stop_distance_pct("demand", NORMAL), 1.5)
        self.assertGreater(scanner.planned_stop_distance_pct("demand", WIDE), 1.5)

    def test_wide_stop_sends_nothing(self):
        with patch.object(scanner, "send_alert", return_value=True) as send:
            sent = scanner.process_candidate({}, dict(RESULT), "demand", WIDE, 0.15, 1000)
        self.assertFalse(sent)
        send.assert_not_called()

    def test_wide_stop_leaves_no_watch_row_either(self):
        with patch.object(scanner, "send_alert", return_value=True), \
             patch.object(scanner, "record_watch_candidate") as watch:
            scanner.process_candidate({}, dict(RESULT), "demand", WIDE, 0.6, 1000)
        watch.assert_not_called()

    def test_normal_stop_still_alerts(self):
        with patch.object(scanner, "send_alert", return_value=True) as send, \
             patch.object(scanner, "record_delivered_zone_alert"):
            sent = scanner.process_candidate({}, dict(RESULT), "demand", NORMAL, 0.15, 1000)
        self.assertTrue(sent)
        send.assert_called_once()

    def test_zero_switches_the_filter_off(self):
        with patch.object(scanner, "MAX_ALERT_STOP_PCT", 0), \
             patch.object(scanner, "send_alert", return_value=True) as send, \
             patch.object(scanner, "record_delivered_zone_alert"):
            sent = scanner.process_candidate({}, dict(RESULT), "demand", WIDE, 0.15, 1000)
        self.assertTrue(sent)
        send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
