"""Weekly audit, 2026-11-15 (run 16 Nov): coindcx_live.py, the real-money CoinDCX bot."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import coindcx_live as live
from tests.test_coindcx_live import HOOKS, NOW, FakeExchange, record, state


class TickExchange(FakeExchange):
    def instrument(self, pair):
        return dict(super().instrument(pair), price_increment=0.05)


class LiveAuditTests(unittest.TestCase):
    def test_first_stop_is_sent_on_the_price_step(self):
        ex, s = TickExchange(), state()
        rec = record(entry=100.0, sl=98.0)
        live.tick(s, ex, [rec], NOW, **dict(HOOKS, daily=lambda sym, now: [[NOW - NOW % 86400 - 86400, 100.2, 101, 97.03, 100.3]]))
        o = s["orders"][rec["id"]]
        self.assertEqual(o["sl"], 97.03)                       # off the 0.05 step
        ex.pos["B-BTC_USDT"] = {"id": "p1", "pair": "B-BTC_USDT", "active_pos": 0.3, "avg_price": 100.0}
        live.tick(s, ex, [], NOW + 300, candles=lambda *a: [])
        self.assertEqual(ex.stops[-1], ("p1", 97.0))           # was 97.03: CoinDCX refuses off-step prices

    def test_short_stop_rounds_up_away_from_price(self):
        o = {"side": "short", "entry": 100.0, "sl": 103.02, "stop_pct": 3.02, "tick": 0.05, "stop_r": None}
        self.assertAlmostEqual(live.stop_level(o), 103.05)

    def test_market_fill_moves_r_to_the_fill(self):
        ex, s = FakeExchange(), state()
        rec = record(side="short", entry=100.0, sl=104.0, broken=True)
        live.tick(s, ex, [rec], NOW, **dict(HOOKS, price_now=lambda sym: 99.0))
        o = s["orders"][rec["id"]]
        ex.pos["B-BTC_USDT"] = {"id": "p1", "pair": "B-BTC_USDT", "active_pos": -o["qty"], "avg_price": 98.0}
        live.tick(s, ex, [], NOW + 300, candles=lambda *a: [])
        self.assertEqual(o["entry"], 98.0)                     # slipped from 99 to 98
        self.assertAlmostEqual(o["stop_pct"], (o["sl"] - 98.0) / 98.0 * 100)
        self.assertAlmostEqual(o["risk"], round(o["qty"] * (o["sl"] - 98.0), 4))
        self.assertEqual(o["plan_entry"], 99.0)

    def test_fill_past_the_stop_keeps_the_plan(self):
        o = {"side": "long", "entry": 100.0, "sl": 97.0, "stop_pct": 3.0, "qty": 1.0, "risk": 3.0}
        live.rebase_on_fill(o, 96.5)
        self.assertEqual((o["entry"], o["stop_pct"]), (100.0, 3.0))

    def test_order_with_no_id_is_not_left_pending(self):
        ex, s = FakeExchange(), state()
        ex.create_order = lambda *a, **k: {"status": "open"}
        rec = record()
        live.tick(s, ex, [rec], NOW, **HOOKS)
        o = s["orders"][rec["id"]]
        self.assertEqual(o["status"], "error")                 # was pending, then "order gone" next tick
        self.assertIn("check CoinDCX", o["reason"])

    def test_no_key_saves_nothing(self):
        with tempfile.TemporaryDirectory() as d, \
                patch.object(live, "STATE_FILE", Path(d) / "live.json"), \
                patch.object(live.config, "COINDCX_LIVE_ENABLED", True), \
                patch.dict(os.environ, {"COINDCX_API_KEY": "", "COINDCX_API_SECRET": ""}), \
                patch.object(live.demo, "load_records", return_value=[record(sent=NOW - 60)]), \
                patch.object(live.demo, "send") as send:
            live.run_tick(NOW)
            self.assertFalse((Path(d) / "live.json").exists())  # dry orders used to be saved as pending
            send.assert_not_called()

    def test_dry_orders_on_file_are_dropped_once_keys_exist(self):
        s = state()
        s["orders"] = {"a": {"exchange_id": "dry-B-BTC_USDT-1", "status": "pending"},
                       "b": {"exchange_id": "o1", "status": "pending"}}
        self.assertEqual(live.drop_dry_orders(s), ["a"])
        self.assertEqual(list(s["orders"]), ["b"])


if __name__ == "__main__":
    unittest.main()
