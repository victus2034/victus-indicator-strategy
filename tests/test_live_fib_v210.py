"""Live bot: 1D crypto fib alerts as real trades, the journal v210 Signals setup (lakky, 2026-11-24:
"no demo go with real account"). L2 / L4 only, BTC flat at the alert, body SL 1%+ past the alert's
entry, limit 0.05% early, 2R + Trail TP (+1R step, 1R behind), SL shift +1R -> +0.25R, 20-day hold.
Replay: research/journal_v210_fib_backtest.py (part journal-v210)."""
import unittest
from unittest.mock import patch

import coindcx_live as live
import config
from tests.test_coindcx_live import DAY, NOW, FakeExchange, record, state

PAIR = "B-BTC_USDT"


def fib(level="L2", side="long", entry=100.0, sl=95.0, sent=NOW - 600):
    r = record(side=side, entry=entry, sl=sl, sent=sent, kind="fib")
    r.update(level=level, id=f"fib|BTCUSD|1d|{side}|{level}@{sent}")
    return r


def bodies(*pairs):
    """Closed daily candles before NOW with these (open, close) bodies, oldest first."""
    out = []
    for i, (o, c) in enumerate(pairs):
        ts = NOW - NOW % DAY - (len(pairs) - i) * DAY
        out.append([ts, o, max(o, c) + 5, min(o, c) - 5, c])
    return out


DAILY = bodies((98.6, 98.9), (99.6, 99.5))        # 99.5 is 0.5% under 100 (too close), 98.6 is 1.4%: the stop
HOOKS = {"daily": lambda sym, now: DAILY, "price_now": lambda sym: 100.8, "btc_move": lambda now: 0.0,
         "btc_at": lambda ts: 0.4}


def bars_from(rows):
    return lambda sym, a, b: [c for c in rows if a <= c[0] < b]


class Pick(unittest.TestCase):
    def test_defaults(self):
        self.assertTrue(config.COINDCX_LIVE_FIB)
        self.assertEqual(config.COINDCX_LIVE_FIB_LEVELS, ("L2", "L4"))
        self.assertIn("1D fib L2+L4 when BTC flat, body 1% SL, 2R + trail, 20d hold", live.rules_text())

    def test_only_l2_and_l4(self):
        s = state()
        self.assertTrue(live.eligible(fib("L2"), s, NOW))
        self.assertTrue(live.eligible(fib("L4"), s, NOW))
        self.assertFalse(live.eligible(fib("L3"), s, NOW))
        self.assertFalse(live.eligible(fib("L1"), s, NOW))
        with patch.object(config, "COINDCX_LIVE_FIB", False):
            self.assertFalse(live.eligible(fib("L2"), s, NOW))

    def test_body_stop(self):
        self.assertEqual(live.body_stop(DAILY, NOW, 100.0, "long"), 98.6)
        self.assertIsNone(live.body_stop(bodies((99.6, 99.5)), NOW, 100.0, "long"))
        self.assertEqual(live.body_stop(bodies((101.5, 102.0), (100.4, 100.6)), NOW, 100.0, "short"), 102.0)

    def test_btc_move_at_uses_closed_15m_against_the_utc_open(self):
        day = NOW - NOW % DAY
        rows = [[day, 100.0, 0, 0, 100.5], [day + 900, 100.5, 0, 0, 101.2], [day + 1800, 101.2, 0, 0, 103.0]]
        with patch.object(live.demo, "fetch_candles", lambda sym, a, b, res: [r for r in rows if a <= r[0] < b]):
            self.assertAlmostEqual(live.btc_move_at(day + 1800), 1.2)      # the 3rd candle is still forming
            self.assertEqual(live.btc_move_at(day + 300), 0.0)


class Place(unittest.TestCase):
    def test_early_limit_body_stop(self):
        s, ex = state(), FakeExchange()
        live.tick(s, ex, [fib()], NOW, **HOOKS)
        o = s["orders"][fib()["id"]]
        self.assertEqual(o["status"], "pending")
        self.assertEqual(ex.orders[0]["type"], "limit_order")
        self.assertEqual(ex.orders[0]["price"], 100.1)                  # 100.05 rounded up to the 0.1 step
        self.assertEqual(o["sl"], 98.6)                                   # not the alert's 95
        self.assertEqual(o["tgt_r"], 2.0)
        self.assertEqual(o["level"], "L2")
        self.assertAlmostEqual(ex.orders[0]["qty"], 0.689)               # risk 1 / 1.45 a unit (from 100.05)
        self.assertEqual(live.head_of(o), "BTC FIB L2 BUY")

    def test_short_mirrors(self):
        s, ex = state(), FakeExchange()
        daily = bodies((101.6, 101.2), (100.3, 100.4))
        live.tick(s, ex, [fib(side="short", sl=105.0)], NOW, **dict(HOOKS, daily=lambda *a: daily, price_now=lambda sym: 99.0))
        o = s["orders"][fib(side="short")["id"]]
        self.assertEqual(ex.orders[0]["side"], "sell")
        self.assertEqual(ex.orders[0]["price"], 99.9)                    # 99.95 rounded down
        self.assertEqual(o["sl"], 101.6)

    def test_btc_not_flat_is_skipped(self):
        for move in (1.6, -1.5, None):
            s, ex = state(), FakeExchange()
            live.tick(s, ex, [fib()], NOW, **dict(HOOKS, btc_at=lambda ts, m=move: m))
            self.assertEqual(ex.orders, [])
            self.assertIn("BTC not flat", s["orders"][fib()["id"]]["reason"])

    def test_no_body_far_enough_or_price_past_stop(self):
        s, ex = state(), FakeExchange()
        live.tick(s, ex, [fib()], NOW, **dict(HOOKS, daily=lambda *a: bodies((99.6, 99.5))))
        self.assertIn("no body 1%", s["orders"][fib()["id"]]["reason"])
        s, ex = state(), FakeExchange()
        live.tick(s, ex, [fib()], NOW, **dict(HOOKS, price_now=lambda sym: 98.5))
        self.assertIn("past the stop", s["orders"][fib()["id"]]["reason"])
        self.assertEqual(ex.orders, [])

    def test_trendline_breaks_still_use_the_tl_exits(self):
        s, ex = state(), FakeExchange()
        live.tick(s, ex, [record(side="short", entry=100.0, sl=104.0, broken=True)], NOW,
                  **dict(HOOKS, price_now=lambda sym: 99.0, daily=lambda *a: bodies((100.2, 100.3))))
        o = next(iter(s["orders"].values()))
        self.assertEqual(o["tgt_r"], config.COINDCX_DEMO_TARGET_R)
        self.assertNotIn("rules", o)


class Manage(unittest.TestCase):
    def open_trade(self):
        s, ex = state(), FakeExchange()
        live.tick(s, ex, [fib()], NOW, **HOOKS)
        o = s["orders"][fib()["id"]]
        ex.pos[PAIR] = {"id": "p1", "pair": PAIR, "active_pos": 0.666, "avg_price": 100.1, "stop_loss_trigger": 98.6}
        live.tick(s, ex, [], NOW + 300, candles=lambda *a: [])
        self.assertEqual(o["status"], "open")
        return s, ex, o

    def test_shift_then_trail(self):
        s, ex, o = self.open_trade()
        risk = 100.1 - 98.6                                              # 1R = 1.5
        t = NOW + 300
        steps = [(1.1, 0.25), (2.05, 2.0), (3.05, 2.0), (4.05, 3.0)]     # best R reached -> stop R
        for best, want in steps:
            high = 100.1 + best * risk
            bars = [[t, 100.1, high, 100.1 + (want + 0.1) * risk if o.get("stop_r") else 100.0, high]]
            live.tick(s, ex, [], t + 120, candles=bars_from(bars))
            self.assertAlmostEqual(o["stop_r"], want, msg=best)
            t += 120
        self.assertEqual(o["stop_why"], "Trail TP")

    def test_time_exit_after_20_days(self):
        s, ex, o = self.open_trade()
        later = o["fill_ts"] + 20 * DAY
        bars = [[later - 120, 100.4, 100.6, 100.3, 100.5]]
        live.tick(s, ex, [], later - 60 + 1, candles=bars_from(bars))
        self.assertEqual(ex.exits, [])                                   # 20 days not over yet
        bars = [[later - 60, 100.4, 100.9, 100.3, 100.8]]
        live.tick(s, ex, [], later + 60, candles=bars_from(bars))
        self.assertEqual(ex.exits, ["p1"])
        self.assertEqual(o["stop_why"], "Time exit")
        del ex.pos[PAIR]
        live.tick(s, ex, [], later + 400, candles=lambda *a: [])
        live.tick(s, ex, [], later + 600, candles=lambda *a: [])
        self.assertEqual(o["status"], "closed")
        self.assertEqual(o["exit_why"], "Time exit")
        want = (100.8 - 100.1) / 1.5 - config.COINDCX_DEMO_ROUND_TRIP_COST_PCT / o["stop_pct"]
        self.assertAlmostEqual(o["r"], round(want, 3))


if __name__ == "__main__":
    unittest.main()
