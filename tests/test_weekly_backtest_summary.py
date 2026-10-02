import unittest

from datetime import date

import pandas as pd

import weekly_backtest_summary as weekly


class WeeklyBacktestSummaryTests(unittest.TestCase):

    def test_weekly_readiness_withholds_unresolved_rows(self):
        pending = pd.DataFrame([{"trade_id": "pending-1"}])
        ready, message = weekly.weekly_readiness(
            pd.DataFrame(),
            pending,
            date(2026, 8, 3),
            date(2026, 8, 7),
        )
        self.assertFalse(ready)
        self.assertIn("final report withheld", message)

    def test_weekly_readiness_withholds_missing_completed_sessions(self):
        finalized = pd.DataFrame(
            [
                {"date": "2026-08-03", "final_result": "+1R"},
                {"date": "2026-08-04", "final_result": "+1R"},
                {"date": "2026-08-05", "final_result": "+1R"},
                {"date": "2026-08-06", "final_result": "+1R"},
            ]
        )
        ready, message = weekly.weekly_readiness(
            finalized,
            pd.DataFrame(),
            date(2026, 8, 3),
            date(2026, 8, 7),
        )

        self.assertFalse(ready)
        self.assertIn("missing_sessions=2026-08-07", message)

    def rows(self):
        return pd.DataFrame(
            [
                {
                    "market": "NSE",
                    "timeframe": "30m",
                    "date": "2026-08-03",
                    "symbol": "A.NS",
                    "display_symbol": "A",
                    "side": "long",
                    "rating": 5,
                    "filled": False,
                    "outcome": "zone_not_touched",
                    "final_result": "",
                    "net_realized_r": float("nan"),
                },
                {
                    "market": "NSE",
                    "timeframe": "30m",
                    "date": "2026-08-03",
                    "symbol": "B.NS",
                    "display_symbol": "B",
                    "side": "short",
                    "rating": 5,
                    "filled": False,
                    "outcome": "data_missing",
                    "final_result": "",
                    "net_realized_r": float("nan"),
                },
                {
                    "market": "NSE",
                    "timeframe": "30m",
                    "date": "2026-08-04",
                    "symbol": "A.NS",
                    "display_symbol": "A",
                    "side": "long",
                    "rating": 6,
                    "filled": True,
                    "outcome": "+1R",
                    "final_result": "+1R",
                    "net_realized_r": 1.0,
                },
            ]
        )

    def test_weekly_no_touch_uses_explicit_outcome_only(self):
        message = weekly.build_weekly_summary(
            self.rows(),
            "30m",
            pd.Timestamp("2026-08-03").date(),
            pd.Timestamp("2026-08-07").date(),
        )

        self.assertIn("Stocks - 2", message)
        self.assertIn("No Touch - 1", message)
        self.assertNotIn("No Touch - 2", message)

    def test_weekly_rating_blocks_use_explicit_no_touch_only(self):
        blocks = weekly.format_weekly_rating_blocks(self.rows())

        self.assertIn("No Entries - 5/10", blocks)
        self.assertNotIn("No Touch", blocks)


class WeekBoundsTests(unittest.TestCase):
    def test_nse_week_is_monday_to_friday(self):
        self.assertEqual(weekly.week_bounds(date(2026, 10, 2), "nse"), (date(2026, 9, 28), date(2026, 10, 2)))

    def test_crypto_week_includes_the_weekend(self):
        for market in ("crypto", "xstock", "other"):
            self.assertEqual(
                weekly.week_bounds(date(2026, 10, 2), market), (date(2026, 9, 26), date(2026, 10, 2))
            )


if __name__ == "__main__":
    unittest.main()


class AmbiguousGraceTests(unittest.TestCase):
    def _run(self, today):
        days = ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"]
        finalized = pd.DataFrame([{"date": d, "final_result": "+1R"} for d in days])
        pending = pd.DataFrame(
            [{"trade_id": "a", "date": "2026-08-05", "final_result": weekly.daily.DATA_QUALITY_AMBIGUOUS}]
        )
        return weekly.weekly_readiness(
            finalized, pending, date(2026, 8, 3), date(2026, 8, 7), today=today
        )

    def test_an_ambiguous_trade_holds_the_report_during_the_grace(self):
        ready, message = self._run(date(2026, 8, 8))
        self.assertFalse(ready)
        self.assertIn("pending=1", message)

    def test_an_ambiguous_trade_no_longer_blocks_after_the_grace(self):
        ready, _ = self._run(date(2026, 8, 7) + pd.Timedelta(days=weekly.AMBIGUOUS_GRACE_DAYS + 1))
        self.assertTrue(ready)
