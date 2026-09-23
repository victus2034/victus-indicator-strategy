"""The NSE weekly must tell a market holiday from a session that was never graded.

weekly_readiness used to expect every Monday-Friday unless NSE_HOLIDAYS listed
it, and nothing ever set that - so any week containing a holiday was withheld
for a "missing" session that never existed (14 Sep 2026: zero NSE alerts). The
same rule wrongly withheld 4h on ordinary days that simply had no 4h alerts.
Sessions are now the days the scanner actually delivered alerts on.
"""
import json
import pathlib
import tempfile
import unittest
from datetime import date

import pandas as pd

import weekly_backtest_summary as weekly

MON, TUE, WED, THU, FRI = (date(2026, 8, d) for d in (3, 4, 5, 6, 7))
WEEK = (MON, FRI)  # a past week, so every weekday counts as completed


def graded(*days):
    return pd.DataFrame([{"date": d.isoformat(), "final_result": "+1R"} for d in days])


def ready(finalized, alert_dates, timeframe="30m"):
    return weekly.weekly_readiness(
        finalized, pd.DataFrame(), *WEEK, timeframe=timeframe, alert_dates=alert_dates
    )


class HolidayWeekTests(unittest.TestCase):
    def test_a_holiday_is_not_a_missing_session(self):
        # Monday had no alerts at all: a closed market.
        ok, message = ready(graded(TUE, WED, THU, FRI), {TUE, WED, THU, FRI})
        self.assertTrue(ok, message)

    def test_without_the_alert_days_the_holiday_still_withholds(self):
        # The old behaviour, kept as the fallback when the file is unavailable.
        ok, message = ready(graded(TUE, WED, THU, FRI), None)
        self.assertFalse(ok)
        self.assertIn("missing_sessions=2026-08-03", message)

    def test_a_day_with_alerts_that_was_never_graded_still_blocks(self):
        # This is what the check exists for: Friday's alerts came in but the
        # daily run has not finalized them yet.
        ok, message = ready(graded(MON, TUE, WED, THU), {MON, TUE, WED, THU, FRI})
        self.assertFalse(ok)
        self.assertIn("missing_sessions=2026-08-07", message)

    def test_a_quiet_4h_day_is_not_a_missing_session(self):
        # 4h fires a handful a week. Tue, Thu and Fri had none.
        ok, message = ready(graded(MON, WED), {MON, WED}, timeframe="4h")
        self.assertTrue(ok, message)

    def test_a_week_with_no_alerts_at_all_has_nothing_to_wait_for(self):
        ok, message = ready(pd.DataFrame(), set())
        self.assertTrue(ok, message)


class AlertDatesTests(unittest.TestCase):
    def write(self, lines):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = pathlib.Path(tmp.name) / "nse_alert_records_30m.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def alert(self, utc, timeframe="30m"):
        return json.dumps({"delivered_at_utc": utc, "timeframe": timeframe})

    def test_days_are_ist_days_not_utc_days(self):
        # 20:00 UTC on the 14th is 01:30 IST on the 15th.
        path = self.write([self.alert("2026-09-14T20:00:00+00:00")])
        self.assertEqual(weekly.nse_alert_dates("30m", path), {date(2026, 9, 15)})

    def test_only_the_asked_timeframe_counts(self):
        path = self.write([
            self.alert("2026-09-15T05:00:00+00:00", "30m"),
            self.alert("2026-09-16T05:00:00+00:00", "4h"),
        ])
        self.assertEqual(weekly.nse_alert_dates("30m", path), {date(2026, 9, 15)})

    def test_a_malformed_line_is_skipped_not_fatal(self):
        path = self.write([
            "not json",
            json.dumps({"timeframe": "30m"}),
            self.alert("2026-09-15T05:00:00+00:00"),
        ])
        self.assertEqual(weekly.nse_alert_dates("30m", path), {date(2026, 9, 15)})

    def test_a_missing_file_is_unknown_not_empty(self):
        # "No file" must never read as "no sessions" - that would let an
        # incomplete week publish.
        self.assertIsNone(weekly.nse_alert_dates("30m", pathlib.Path("does-not-exist.jsonl")))


class WorkflowRestoresTheAlertFilesTests(unittest.TestCase):
    def test_the_weekly_workflow_restores_what_the_readiness_check_reads(self):
        text = pathlib.Path(".github/workflows/weekly_backtest_summary.yml").read_text(encoding="utf-8")
        for name in ("nse_alert_records.jsonl", "nse_alert_records_30m.jsonl"):
            self.assertIn(name, text, f"{name} is read by nse_alert_dates but never restored")


if __name__ == "__main__":
    unittest.main()
