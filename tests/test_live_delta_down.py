"""Delta down (2026-11-25: Delta's keys take India IPs only and dropped the runner's): with no live
trade on Delta the tick runs on CoinDCX alone; with one, the account read still fails loudly."""
import unittest
from unittest.mock import patch

import coindcx_live as live
import config
from tests.test_coindcx_live import NOW, FakeExchange, state


class DeadDelta:
    def positions(self):
        raise RuntimeError('Delta GET /v2/positions/margined: HTTP 401 {"code": "ip_not_whitelisted_for_api_key"}')

    open_orders = positions


class DeltaDown(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict("os.environ", {"DELTA_API_KEY": "k", "DELTA_API_SECRET": "s"})
        self.env.start()
        self.flag = patch.object(config, "LIVE_DELTA", True)
        self.flag.start()

    def tearDown(self):
        live.DELTA_DOWN = False
        self.flag.stop()
        self.env.stop()

    def test_no_delta_trade_runs_on_coindcx_only(self):
        s, dcx = state(), FakeExchange()
        ex = live.drop_dead_delta(s, live.Router(dcx, DeadDelta()), NOW)
        self.assertIs(ex, dcx)
        self.assertFalse(live.delta_on())
        sym = sorted(config.DELTA_LISTED_SYMBOLS)[0]
        self.assertFalse(live.venue_pair(sym).startswith("DELTA:"))         # new trades go to CoinDCX
        self.assertEqual([e["kind"] for e in s["events"]], ["warn"])
        live.drop_dead_delta(s, live.Router(dcx, DeadDelta()), NOW + 120)
        self.assertEqual(len(s["events"]), 1)                               # said once, not every tick

    def test_open_delta_trade_keeps_the_router(self):
        s = state()
        s["orders"]["x"] = {"id": "123:456", "pair": "DELTA:XRPUSD", "status": "open"}
        router = live.Router(FakeExchange(), DeadDelta())
        self.assertIs(live.drop_dead_delta(s, router, NOW), router)
        self.assertTrue(live.delta_on())
        self.assertEqual(s["events"], [])

    def test_delta_back(self):
        s, dcx = state(), FakeExchange()
        live.drop_dead_delta(s, live.Router(dcx, DeadDelta()), NOW)
        router = live.Router(dcx, FakeExchange())
        self.assertIs(live.drop_dead_delta(s, router, NOW + 120), router)
        self.assertTrue(live.delta_on())
        self.assertNotIn("delta_down", s)
        self.assertIn("answers again", s["events"][-1]["text"])


if __name__ == "__main__":
    unittest.main()
