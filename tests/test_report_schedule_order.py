"""The weekly report must be scheduled after the daily run that finalizes its data.

weekly_readiness withholds an NSE week unless every completed NSE session in it
is already in the finalized records. The daily backtest is what finalizes them,
and it runs at 07:30 the morning AFTER a session. Scheduling the weekly for
Friday 17:00 - where it used to sit, when the daily ran at 16:35 the same
afternoon - would withhold it every week, and a withheld run is never retried
because the catch-up counts it as having run.
"""
import pathlib
import re
import unittest

SCRIPT = pathlib.Path(".github/scripts/dispatch_overdue.sh")


def schedule():
    """{workflow: (minutes since midnight, set of ISO weekdays or None)}"""
    found = {}
    pattern = re.compile(r'^dispatch_if_overdue\s+(\S+\.yml)\s+"(\d\d):(\d\d)"\s*(?:"([\d,]+)"|(\d))?')
    for line in SCRIPT.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        name, hh, mm, several, single = match.groups()
        days = set((several or single).split(",")) if (several or single) else None
        found[name] = (int(hh) * 60 + int(mm), days)
    return found


class ReportScheduleOrderTests(unittest.TestCase):
    def test_both_reports_are_scheduled(self):
        found = schedule()
        self.assertIn("daily_backtest_summary.yml", found)
        self.assertIn("weekly_backtest_summary.yml", found)

    def test_the_daily_runs_every_day_in_the_morning(self):
        minutes, days = schedule()["daily_backtest_summary.yml"]
        self.assertIsNone(days, "the daily also reports crypto, which trades weekends")
        self.assertLess(minutes, 12 * 60, "the daily is a morning job")

    def test_the_weekly_runs_the_morning_after_friday_not_on_friday(self):
        minutes, days = schedule()["weekly_backtest_summary.yml"]
        self.assertEqual(days, {"6"}, "Saturday - Friday's session is only finalized then")
        self.assertLess(minutes, 12 * 60, "the weekly is a morning job too")

    def test_the_weekly_leaves_the_daily_time_to_finish(self):
        daily_at, _ = schedule()["daily_backtest_summary.yml"]
        weekly_at, _ = schedule()["weekly_backtest_summary.yml"]
        self.assertGreaterEqual(
            weekly_at - daily_at, 30,
            "the weekly must start well after the daily has finalized Friday",
        )


if __name__ == "__main__":
    unittest.main()
