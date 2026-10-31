"""TL BROKEN alerts are recorded as trades (lakky, 2026-10-31) and backtest cards are off Discord."""
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import config
import daily_backtest_summary as dbs
import entry_confirm
import fib_trendline_daily_report as fdr
import fib_trendline_data as ftd
import fib_trendline_scanner as fts
import fib_trendline_trades as ftt
from trendlines import RESISTANCE, SUPPORT


class BreakPlanTests(unittest.TestCase):
    # bar 0 = the candle before the break, bar 1 = the break candle
    highs, lows, closes = [105.0, 101.0], [99.0, 94.0], [100.0, 95.0]

    def test_support_broken_sells_with_the_stop_above_the_previous_candle(self):
        plan = ftt.break_plan(True, 1, self.highs, self.lows, self.closes)
        self.assertEqual(plan, {"side": "short", "entry": 95.0, "sl": 105.0, "target_r": 1, "fill": "market"})

    def test_resistance_broken_buys_with_the_stop_below_the_previous_candle(self):
        plan = ftt.break_plan(False, 1, [100.0, 108.0], [96.0, 99.0], [98.0, 107.0], entry=107.5)
        self.assertEqual((plan["side"], plan["entry"], plan["sl"]), ("long", 107.5, 96.0))

    def test_no_plan_when_the_stop_is_on_the_wrong_side(self):
        self.assertIsNone(ftt.break_plan(True, 1, self.highs, self.lows, self.closes, entry=106.0))
        self.assertIsNone(ftt.break_plan(True, 0, self.highs, self.lows, self.closes))


class MarketFillTests(unittest.TestCase):
    plan = {"side": "short", "entry": 95.0, "sl": 105.0, "target_r": 1, "fill": "market"}

    def test_filled_on_the_first_candle_even_without_trading_back_to_entry(self):
        candles = [(10, 94, 94.5, 90, 91), (20, 91, 92, 84.9, 85)]
        res = ftt.simulate(self.plan, ftd.CRYPTO, "4h", 0, candles)
        self.assertEqual((res["filled"], res["fill_ts"], res["outcome"]), (True, 10, "1R"))

    def test_target_counts_from_the_candle_after_the_fill(self):
        res = ftt.simulate(self.plan, ftd.CRYPTO, "4h", 0, [(10, 94, 94.5, 84, 85)])
        self.assertEqual(res["outcome"], "open")

    def test_stop_on_the_fill_candle(self):
        res = ftt.simulate(self.plan, ftd.CRYPTO, "4h", 0, [(10, 94, 106, 90, 91)])
        self.assertEqual(res["outcome"], "SL")

    def test_a_limit_plan_still_waits_for_its_entry(self):
        limit = {k: v for k, v in self.plan.items() if k != "fill"}
        res = ftt.simulate(limit, ftd.CRYPTO, "4h", 0, [(10, 94, 94.5, 90, 91)])
        self.assertFalse(res["filled"])


class BreakRecordTests(unittest.TestCase):
    def brk(self, plan):
        return {"key": "tlbreak|BTCUSD|4h|0|1|2", "kind": SUPPORT, "level": 100.0, "close": 95.0,
                "time": "2026-10-31 00:00", "from": (110, "a"), "to": (105, "b"), "closed_at": 0, "plan": plan}

    def plan(self, plan):
        analysis = {"fib": [], "touch": [], "break": [self.brk(plan)], "price": 95.2}
        return fts.plan_alerts({}, ftd.CRYPTO, "BTCUSD", "4h", analysis, 10, None)

    def test_a_break_with_a_plan_is_recorded_with_the_message_unchanged(self):
        plan = {"side": "short", "entry": 95.2, "sl": 105.0, "target_r": 1, "fill": "market"}
        (channel, key, message, record), = self.plan(plan)
        self.assertEqual((channel, key), ("trendline", "tlbreak|BTCUSD|4h|0|1|2"))
        self.assertIn("S TL BROKEN", message)
        self.assertNotIn("Entry", message)
        self.assertEqual((record["kind"], record["plan"], record["line"], record["broken"]), ("trendline", plan, 0, True))
        self.assertEqual(key.split("|")[3], "0")        # the journal reads the line from field 3

    def test_a_break_without_a_plan_still_alerts_unrecorded(self):
        (_, _, _, record), = self.plan(None)
        self.assertIsNone(record)

    def test_breaks_are_never_merged_with_a_touch_at_the_same_price(self):
        plan = {"side": "short", "entry": 95.2, "sl": 105.0, "target_r": 1, "fill": "market"}
        brk = ("trendline", "tlbreak|X|4h|0|1|2", "a\nb", {"plan": plan, "broken": True})
        touch = ("trendline", "tl|X|1d|1|1|2", "c\nd\ne", {"plan": dict(plan)})
        self.assertEqual(len(fts.merge_same_price(ftd.CRYPTO, [brk, touch])), 2)

    def test_analyse_puts_the_plan_on_a_fresh_break(self):
        from trendlines import Trendline
        t, n = 1_700_000_000, fts.MIN_BARS + 20
        candles = [[t + i * 14400, 100.0, 101.0, 99.0, 100.0] for i in range(n)]
        candles[-2] = [candles[-2][0], 100.0, 104.0, 98.0, 103.0]        # the break candle, closed above 102
        line = Trendline(RESISTANCE, 0, 102.0, 10, 102.0, created=20, broken_at=n - 2)
        with mock.patch.object(fts, "build_trendlines", lambda *a, **k: [line]):
            res = fts.analyse(ftd.CRYPTO, "BTCUSD", "4h", candles, t + n * 14400 - 60, price=103.5)
        (b,) = res["break"]
        self.assertEqual(b["plan"], {"side": "long", "entry": 103.5, "sl": 99.0, "target_r": 1, "fill": "market"})


class EntryConfirmSkipsBreaks(unittest.TestCase):
    def test_broken_records_are_not_watched(self):
        import pandas as pd
        now = pd.Timestamp.now(tz=entry_confirm.IST)
        rows = [{"market": "crypto", "symbol": "BTCUSD", "tf": "1d", "kind": "trendline", "broken": True,
                 "plan": {"side": "short", "entry": 95.0, "sl": 105.0}, "sent_ts": int(now.timestamp()) - 60},
                {"market": "crypto", "symbol": "BTCUSD", "tf": "1d", "kind": "trendline",
                 "plan": {"side": "long", "entry": 95.0, "sl": 90.0}, "sent_ts": int(now.timestamp()) - 60}]
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "r.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows))
            got = entry_confirm.load_fib_tl_alerts("crypto", "1d", now, records_path=path)
        self.assertEqual([r["side"] for r in got], ["long"])


class BacktestCardsOffTests(unittest.TestCase):
    def test_off_by_default(self):
        self.assertFalse(config.DISCORD_BACKTEST_CARDS)

    def test_daily_and_weekly_cards_post_nothing_when_off(self):
        with mock.patch.object(config, "DISCORD_BACKTEST_CARDS", False), \
                mock.patch.object(dbs.requests, "post") as post:
            dbs.send_discord_message("x")
            dbs.send_discord_message_with_attachment("x", "a.xlsx", b"1")
        post.assert_not_called()

    def test_fib_trendline_card_posts_nothing_when_off(self):
        with mock.patch.object(config, "DISCORD_BACKTEST_CARDS", False), \
                mock.patch.dict("os.environ", {fdr.WEBHOOK_ENV: "https://discord.invalid/api/webhooks/1/x"}), \
                mock.patch.object(fdr.requests, "post") as post:
            fdr.send_card("x")
        post.assert_not_called()

    def test_paper_table_posts_nothing_when_off(self):
        import paper_trading
        with mock.patch.object(config, "DISCORD_BACKTEST_CARDS", False), \
                mock.patch.dict("os.environ", {paper_trading.WEBHOOK_ENV: "https://discord.invalid/api/webhooks/1/x"}), \
                mock.patch.object(paper_trading.requests, "post") as post:
            paper_trading.post_report("x")
        post.assert_not_called()

    def test_back_on_posts_again(self):
        with mock.patch.object(config, "DISCORD_BACKTEST_CARDS", True), \
                mock.patch.dict("os.environ", {fdr.WEBHOOK_ENV: "https://discord.invalid/api/webhooks/1/x"}), \
                mock.patch.object(fdr.requests, "post") as post:
            post.return_value.status_code = 200
            fdr.send_card("x")
        post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
