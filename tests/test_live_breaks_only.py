"""Live bot rules of 2026-11-22 (lakky, decision card "Breaks only + own SL + kill fix"), unpinned:
TL BROKEN alerts only, the kill switch counted from the best point, and the alert's own SL on breaks
as an option (VICTUS_COINDCX_LIVE_BREAK_SL=alert; the replay kept wick/body as the default).
Replay behind them: research/live_upgrade_replay.py."""
import os
import unittest
from unittest.mock import patch

import coindcx_live as live
import config
from tests.test_coindcx_live import DAY, HOOKS, NOW, FakeExchange, daily, record, state, touch


def closed(s, oid, pnl, exit_ts):
    s["orders"][oid] = {"id": oid, "symbol": oid, "status": "closed", "pnl": pnl, "exit_ts": exit_ts, "r": pnl}
    s["realized"] = round(s["realized"] + pnl, 4)


class Defaults(unittest.TestCase):
    def test_defaults(self):
        self.assertFalse(config.COINDCX_LIVE_TOUCHES)
        self.assertEqual(config.COINDCX_LIVE_BREAK_SL, "wick_body")
        self.assertEqual(config.COINDCX_LIVE_MAX_DRAWDOWN_R, 15.0)
        self.assertEqual(config.COINDCX_LIVE_MAX_LOSS, 0.0)            # the loss-from-start rule is off
        self.assertEqual(live.rules_text(), "1D TL breaks only, wick/body SL on breaks, kill switch 15R from the best point")

    def test_default_break_stop_is_wick_body(self):
        s, ex = state(), FakeExchange()
        rec = record(side="short", entry=100.0, sl=104.0, broken=True)
        live.tick(s, ex, [rec], NOW, **dict(HOOKS, price_now=lambda sym: 99.0))
        o = s["orders"][rec["id"]]
        self.assertEqual(o["sl"], 100.3)                               # body top 0.75%+ above 99, not the 104 alert SL
        self.assertNotIn("alert_sl", o)


class BreaksOnly(unittest.TestCase):
    def test_touch_alerts_are_not_traded(self):
        s, ex = state(), FakeExchange()
        self.assertFalse(live.eligible(record(), s, NOW))
        self.assertTrue(live.eligible(record(broken=True), s, NOW))
        live.tick(s, ex, [record(), touch()], NOW, **HOOKS, hourly=lambda *a: [])
        self.assertEqual(ex.orders, [])
        self.assertEqual(s["orders"], {})                              # not even recorded as skipped

    def test_a_waiting_touch_is_called_off(self):
        s, ex = state(), FakeExchange()
        with patch.object(config, "COINDCX_LIVE_TOUCHES", True):
            live.tick(s, ex, [touch()], NOW, **HOOKS, hourly=lambda *a: [])
        o = s["orders"][touch()["id"]]
        self.assertEqual(o["status"], "waiting")                       # 1000PEPE's touch of 21 Nov
        h = NOW - NOW % 3600 + 3600
        held = [[h, 99.8, 100.9, 99.7, 100.6]]                         # would have confirmed
        live.tick(s, ex, [], h + 3600 + 60, **HOOKS, candles=lambda *a: [],
                  hourly=lambda sym, a, b: [c for c in held if a <= c[0] < b])
        self.assertEqual(ex.orders, [])
        self.assertEqual(o["status"], "cancelled")
        self.assertIn("breaks only", o["reason"])

    def test_touches_back_on_with_the_variable(self):
        with patch.object(config, "COINDCX_LIVE_TOUCHES", True):
            self.assertTrue(live.eligible(record(), state(), NOW))


class AlertStop(unittest.TestCase):
    """VICTUS_COINDCX_LIVE_BREAK_SL=alert."""

    def setUp(self):
        self.pin = patch.object(config, "COINDCX_LIVE_BREAK_SL", "alert")
        self.pin.start()
        self.addCleanup(self.pin.stop)

    def test_rules_line(self):
        self.assertIn("alert's SL on breaks", live.rules_text())

    def place(self, rec, price):
        s, ex = state(), FakeExchange()
        live.tick(s, ex, [rec], NOW, **dict(HOOKS, price_now=lambda sym: price))
        return s, ex, s["orders"][rec["id"]]

    def test_short_break_uses_the_alerts_stop(self):
        s, ex, o = self.place(record(side="short", entry=100.0, sl=104.0, broken=True), 99.0)
        self.assertEqual(ex.orders[0]["type"], "market_order")
        self.assertEqual(o["sl"], 104.0)                               # not the 100.3 body of the wick/body rule
        self.assertEqual(o["alert_sl"], 104.0)
        self.assertAlmostEqual(o["stop_pct"], 5 / 99 * 100)
        self.assertEqual(ex.orders[0]["lev"], 13)                      # 70 / 5.05%: liquidation past the stop
        self.assertAlmostEqual(ex.orders[0]["qty"], 0.2)               # risk 1 / 5 a unit

    def test_long_break_mirrors(self):
        s, ex, o = self.place(record(side="long", entry=100.0, sl=91.0, broken=True), 101.0)
        self.assertEqual(o["sl"], 91.0)
        self.assertEqual(ex.orders[0]["side"], "buy")

    def test_price_past_the_alerts_stop_is_no_trade(self):
        s, ex, o = self.place(record(side="short", entry=100.0, sl=104.0, broken=True), 104.5)
        self.assertEqual(ex.orders, [])
        self.assertEqual(o["status"], "skipped")
        self.assertIn("past the alert's stop", o["reason"])

    def test_a_stop_closer_than_the_gap_uses_wick_body(self):
        s, ex, o = self.place(record(side="short", entry=100.0, sl=99.5, broken=True), 99.0)   # 0.5% away
        self.assertEqual(o["sl"], 100.3)                               # wick/body rule, as before 22 Nov

    def test_no_usable_alert_stop_uses_wick_body(self):
        rec = record(side="short", entry=100.0, sl=104.0, broken=True)
        rec["plan"]["sl"] = None
        s, ex, o = self.place(rec, 99.0)
        self.assertEqual(o["sl"], 100.3)

    def test_wick_body_variable_is_the_old_way(self):
        with patch.object(config, "COINDCX_LIVE_BREAK_SL", "wick_body"):
            s, ex, o = self.place(record(side="short", entry=100.0, sl=104.0, broken=True), 99.0)
        self.assertEqual(o["sl"], 100.3)
        self.assertNotIn("alert_sl", o)


class KillSwitch(unittest.TestCase):
    def blocked(self, s):
        return live.blocked(s, {"symbol": "NEW"}, NOW, btc_move=lambda now: 0.0)

    def test_counts_from_the_best_point(self):
        s = state()
        closed(s, "a", 5.0, NOW - 5 * DAY)
        for i in range(19):
            closed(s, f"l{i}", -1.0, NOW - 4 * DAY + i)
        self.assertEqual(s["realized"], -14.0)
        self.assertAlmostEqual(live.drawdown(s), 19.0)                 # 5 up, then 19 down
        self.assertIn("kill switch", self.blocked(s))

    def test_a_loss_from_the_start_under_the_limit_trades_on(self):
        s = state()
        for i in range(14):
            closed(s, f"l{i}", -1.0, NOW - DAY + i)
        self.assertAlmostEqual(live.drawdown(s), 14.0)
        self.assertIsNone(self.blocked(s))                             # the old 10 USDT rule would have stopped here
        closed(s, "l14", -1.0, NOW - 10)
        self.assertIn("15.00 down", self.blocked(s))

    def test_scales_with_the_risk(self):
        s = state()
        for i in range(15):
            closed(s, f"l{i}", -1.0, NOW - DAY + i)
        with patch.object(config, "COINDCX_LIVE_RISK", 2.0):
            self.assertIsNone(self.blocked(s))                         # 15 USDT is 7.5R at 2 USDT a trade

    def test_live_state_of_22_nov(self):
        """The real closed trades to 22 Nov: realized -3.32, never above 0, so 3.32 below the best point."""
        s = state()
        for i, pnl in enumerate((-1.009, -1.017, -1.02, 0.701, -1.011, -1.011, 1.05)):
            closed(s, f"t{i}", pnl, NOW - 7 * DAY + i * DAY)
        self.assertAlmostEqual(live.drawdown(s), 3.317)
        self.assertIsNone(self.blocked(s))

    def test_old_rule_still_works_when_set(self):
        s = state()
        closed(s, "a", -10.0, NOW - DAY)
        with patch.object(config, "COINDCX_LIVE_MAX_LOSS", 10.0):
            self.assertIn("loss so far", self.blocked(s))

    def test_trips_on_new_breaks_in_a_tick(self):
        s, ex = state(), FakeExchange()
        for i in range(15):
            closed(s, f"l{i}", -1.0, NOW - DAY + i)
        live.tick(s, ex, [record(side="short", entry=100.0, sl=104.0, broken=True)], NOW,
                  **dict(HOOKS, price_now=lambda sym: 99.0))
        self.assertEqual(ex.orders, [])


class RulesNote(unittest.TestCase):
    def run_tick(self, s):
        saved = {}
        with patch.object(config, "COINDCX_LIVE_ENABLED", True), \
                patch.dict(os.environ, {"COINDCX_API_KEY": "k", "COINDCX_API_SECRET": "s", "DELTA_API_KEY": ""}), \
                patch.object(live, "CoinDCX", lambda k, sec: FakeExchange()), \
                patch.object(live, "load_state", return_value=s), \
                patch.object(live, "save_state", side_effect=lambda st: saved.update(st)), \
                patch.object(live, "post", return_value=True), \
                patch.object(live.demo, "load_records", return_value=[]):
            live.run_tick(NOW)
        return saved

    def test_posted_once_when_the_rules_change(self):
        s = state()
        closed(s, "a", -1.0, NOW - DAY)
        got = self.run_tick(s)
        self.assertEqual(got["rules"], live.rules_text())
        self.assertEqual(sum("rules now" in e["text"] for e in got["events"]), 1)
        got = self.run_tick(got)
        self.assertEqual(sum("rules now" in e["text"] for e in got["events"]), 1)   # not again

    @patch.object(config, "COINDCX_LIVE_BREAK_SL", "alert")
    def test_daily_candles_unused_for_an_alert_stop(self):
        calls = []
        s, ex = state(), FakeExchange()
        live.tick(s, ex, [record(side="short", entry=100.0, sl=104.0, broken=True)], NOW,
                  **dict(HOOKS, price_now=lambda sym: 99.0, daily=lambda sym, now: calls.append(sym) or daily()))
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
