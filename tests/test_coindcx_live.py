"""CoinDCX live account (coindcx_live.py): 1D crypto trendline alerts as real orders."""
import hashlib
import hmac
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import coindcx_live as live
import config

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))

DAY = 86400
NOW = 1_794_000_000 // DAY * DAY + 10 * 3600


def record(symbol="BTCUSD", side="long", entry=100.0, sl=98.0, sent=NOW - 600, broken=False, kind="trendline", tf="1d"):
    r = {"market": "crypto", "symbol": symbol, "tf": tf, "kind": kind, "plan": {"side": side, "entry": entry, "sl": sl},
         "id": f"tl|{symbol}|{tf}|{side}@{sent}" + ("|br" if broken else ""), "sent_ts": sent}
    if broken:
        r["broken"] = True
    return r


def daily(lows=(97.0, 99.5, 99.8), highs=(103.0, 102.0, 101.0)):
    """Closed daily candles before NOW: the stop for a 100 buy is the 97 wick (body 99+ too close)."""
    out = []
    for i, (lo, hi) in enumerate(zip(lows, highs)):
        ts = NOW - NOW % DAY - (len(lows) - i) * DAY
        out.append([ts, 100.2, hi, lo, 100.3])
    return out


class FakeExchange:
    def __init__(self):
        self.orders, self.stops, self.cancelled = [], [], []
        self.pos, self.open = {}, set()

    def instrument(self, pair):
        return {"quantity_increment": 0.001, "min_quantity": 0.001, "max_leverage_long": 50, "max_leverage_short": 50,
                "price_increment": 0.1}

    def create_order(self, pair, side, order_type, qty, leverage, price=None):
        oid = f"o{len(self.orders)}"
        self.orders.append({"id": oid, "pair": pair, "side": side, "type": order_type, "qty": qty, "lev": leverage, "price": price})
        self.open.add(oid)
        return {"id": oid}

    def cancel(self, oid):
        self.cancelled.append(oid)
        self.open.discard(oid)

    def open_orders(self):
        return [{"id": o} for o in self.open]

    def positions(self):
        return dict(self.pos)

    def set_stop(self, pid, stop):
        self.stops.append((pid, round(stop, 6)))


def state():
    s = live.new_state(NOW - 3600)
    s["events"] = []
    return s


HOOKS = {"daily": lambda sym, now: daily(), "price_now": lambda sym: 100.0, "btc_move": lambda now: 0.5}


class Rules(unittest.TestCase):
    def test_off_by_default(self):
        self.assertFalse(config.COINDCX_LIVE_ENABLED)
        with patch.object(live, "load_state") as ls:
            self.assertIsNone(live.run_tick(NOW))
            ls.assert_not_called()

    def test_wick_body_matches_research_scorer(self):
        import journal_fib_setup_backtest as jfs
        for side, entry in (("long", 100.0), ("long", 101.2), ("short", 100.0), ("short", 98.6)):
            s = 1 if side == "long" else -1
            want, _ = jfs.wick_body_stop(daily(), NOW, entry, s)
            self.assertEqual(live.wick_body_stop(daily(), NOW, entry, side), want, (side, entry))

    def test_no_candle_far_enough(self):
        self.assertIsNone(live.wick_body_stop(daily(lows=(99.6, 99.7, 99.8)), NOW, 100.0, "long"))

    def test_quantity(self):
        ins = {"quantity_increment": 0.01, "min_quantity": 0.01}
        self.assertEqual(live.quantity(100, 97, ins, risk=1.0)[0], 0.33)          # 1 / 3 rounded down
        self.assertEqual(live.quantity(100, 99.9, {"quantity_increment": 1, "min_quantity": 1}, risk=0.5)[0], 5)
        qty, why = live.quantity(100, 90, {"quantity_increment": 1, "min_quantity": 1}, risk=1.0)
        self.assertEqual(qty, 0)                                                   # min order risks 10 > 2x
        self.assertIn("2x", why)

    def test_only_fresh_1d_crypto_trendlines(self):
        s = state()
        self.assertTrue(live.eligible(record(), s, NOW))
        self.assertTrue(live.eligible(record(broken=True), s, NOW))
        self.assertFalse(live.eligible(record(kind="fib"), s, NOW))
        self.assertFalse(live.eligible(record(tf="4h"), s, NOW))
        self.assertFalse(live.eligible(record(sent=NOW - 7 * 3600), s, NOW))       # too old: never chase
        self.assertFalse(live.eligible(record(sent=NOW - 6 * 3600 - 60), s, NOW))
        self.assertFalse(live.eligible(record(symbol="XAUTUSD"), s, NOW))
        late = dict(s, until_ts=NOW - 700)
        self.assertFalse(live.eligible(record(), late, NOW))                        # the week is over


class Flow(unittest.TestCase):
    def test_touch_limit_fill_stop_trail_close(self):
        ex, s = FakeExchange(), state()
        live.tick(s, ex, [record()], NOW, **HOOKS)
        o = s["orders"][record()["id"]]
        self.assertEqual(o["status"], "pending")
        self.assertEqual(ex.orders[0]["type"], "limit_order")
        self.assertEqual(ex.orders[0]["price"], 100.0)
        self.assertEqual(o["sl"], 97.0)
        self.assertAlmostEqual(ex.orders[0]["qty"], 0.333)                         # risk 1 / 3 a unit
        self.assertEqual(ex.orders[0]["lev"], 20)
        # filled: the position shows up, the exchange stop goes in
        ex.pos["B-BTC_USDT"] = {"id": "p1", "pair": "B-BTC_USDT", "active_pos": 0.333, "avg_price": 100.0}
        live.tick(s, ex, [], NOW + 300, candles=lambda *a: [])
        self.assertEqual(o["status"], "open")
        self.assertEqual(ex.stops[-1], ("p1", 97.0))
        # +1R (103) trades: stop to +0.75R = 102.25
        ex.pos["B-BTC_USDT"]["stop_loss_trigger"] = 97.0
        bars = [[NOW + 300, 100, 103.1, 100, 102.5]]
        live.tick(s, ex, [], NOW + 600, candles=lambda sym, a, b: [c for c in bars if a <= c[0] < b])
        self.assertAlmostEqual(o["stop_r"], 0.75)
        self.assertEqual(ex.stops[-1], ("p1", 102.25))
        # stopped out: the position is gone
        del ex.pos["B-BTC_USDT"]
        live.tick(s, ex, [], NOW + 900, candles=lambda *a: [])
        self.assertEqual(o["status"], "closed")
        self.assertTrue(0.6 < o["r"] < 0.75)                                       # fees and slip off
        self.assertAlmostEqual(s["realized"], o["pnl"])

    def test_break_is_market(self):
        ex, s = FakeExchange(), state()
        live.tick(s, ex, [record(side="short", entry=100.0, sl=104.0, broken=True)], NOW,
                  **dict(HOOKS, price_now=lambda sym: 99.0))
        self.assertEqual(ex.orders[0]["type"], "market_order")
        self.assertEqual(ex.orders[0]["side"], "sell")
        o = next(iter(s["orders"].values()))
        self.assertEqual(o["sl"], 100.3)          # body top 100.3 is 0.75%+ above 99 and closer than the 101 wick

    def test_skips(self):
        ex, s = FakeExchange(), state()
        recs = [record(), record(sent=NOW - 500)]                                   # same coin twice
        live.tick(s, ex, recs, NOW, **HOOKS)
        self.assertEqual(len(ex.orders), 1)
        self.assertIn("already", s["orders"][recs[1]["id"]]["reason"])
        s2 = state()
        s2["realized"] = -config.COINDCX_LIVE_MAX_LOSS
        live.tick(s2, FakeExchange(), [record()], NOW, **HOOKS)
        self.assertIn("kill switch", s2["orders"][record()["id"]]["reason"])
        with patch.object(config, "COINDCX_LIVE_BTC_FILTER", "so_far"):
            s3, ex3 = state(), FakeExchange()
            live.tick(s3, ex3, [record()], NOW, **dict(HOOKS, btc_move=lambda now: 2.4))
            self.assertEqual(ex3.orders, [])
            self.assertIn("BTC not sideways", s3["orders"][record()["id"]]["reason"])

    def test_unfilled_limit_cancelled_after_wait(self):
        ex, s = FakeExchange(), state()
        live.tick(s, ex, [record()], NOW, **HOOKS)
        later = NOW + config.COINDCX_DEMO_FILL_DAYS * DAY
        live.tick(s, ex, [], later, candles=lambda *a: [])
        self.assertEqual(ex.cancelled, ["o0"])

    def test_account_read_failure_places_nothing(self):
        class Down(FakeExchange):
            def positions(self):
                raise RuntimeError("503")
        ex, s = Down(), state()
        live.tick(s, ex, [record()], NOW, **HOOKS)
        self.assertEqual(ex.orders, [])
        self.assertEqual(s["orders"], {})


def fib_record(symbol="ETHUSD", side="long", entry=100.0, sl=91.0, level="L3", sent=NOW - 600):
    return {"market": "crypto", "symbol": symbol, "tf": "1d", "kind": "fib", "level": level,
            "plan": {"side": side, "entry": entry, "sl": sl}, "id": f"fib|{symbol}|1d|{level}@{sent}", "sent_ts": sent}


class Fibs(unittest.TestCase):
    """lakky, 2026-11-14: "Start building live mode" for the 1D fib demo - off until switched on."""

    def setUp(self):
        on = patch.object(config, "COINDCX_LIVE_KINDS", ("trendline", "fib"))
        on.start()
        self.addCleanup(on.stop)

    def test_off_unless_listed(self):
        s = state()
        self.assertTrue(live.eligible(fib_record(), s, NOW))
        with patch.object(config, "COINDCX_LIVE_KINDS", ("trendline",)):
            self.assertFalse(live.eligible(fib_record(), s, NOW))
            self.assertTrue(live.eligible(record(), s, NOW))
        with patch.object(config, "COINDCX_LIVE_KINDS", ("fib",)):
            self.assertTrue(live.eligible(fib_record(), s, NOW))
            self.assertFalse(live.eligible(record(), s, NOW))
            self.assertFalse(live.eligible(record(broken=True), s, NOW))
        with patch.object(config, "COINDCX_DEMO_LEVELS", ("L2", "L3", "L4")):
            self.assertFalse(live.eligible(fib_record(level="L1"), s, NOW))
            self.assertTrue(live.eligible(fib_record(level="L4"), s, NOW))
        self.assertFalse(live.eligible(dict(fib_record(), tf="4h"), s, NOW))
        self.assertFalse(live.eligible(fib_record(sent=NOW - 7 * 3600), s, NOW))

    def test_limit_at_entry_with_the_alerts_own_stop(self):
        ex, s = FakeExchange(), state()
        live.tick(s, ex, [fib_record()], NOW, **HOOKS)
        o = s["orders"][fib_record()["id"]]
        self.assertEqual((o["status"], o["kind"], o["level"]), ("pending", "fib", "L3"))
        self.assertEqual(ex.orders[0]["type"], "limit_order")
        self.assertEqual((ex.orders[0]["pair"], ex.orders[0]["side"], ex.orders[0]["price"]), ("B-ETH_USDT", "buy", 100.0))
        self.assertEqual(o["sl"], 91.0)                                 # not the wick-or-body 97
        self.assertAlmostEqual(ex.orders[0]["qty"], 0.111)              # risk 1 / 9 a unit, step 0.001
        self.assertIn("ETH FIB L3 BUY", s["events"][-1]["text"])
        # filled -> the exchange stop at the alert's SL; +1R (109) -> stop to +0.75R (106.75)
        ex.pos["B-ETH_USDT"] = {"id": "p9", "pair": "B-ETH_USDT", "active_pos": 0.111, "avg_price": 100.0}
        live.tick(s, ex, [], NOW + 300, candles=lambda *a: [])
        self.assertEqual(ex.stops[-1], ("p9", 91.0))
        self.assertIn("ETH FIB L3 BUY", s["events"][-1]["text"])
        ex.pos["B-ETH_USDT"]["stop_loss_trigger"] = 91.0
        bars = [[NOW + 300, 100, 109.2, 100, 108]]
        live.tick(s, ex, [], NOW + 600, candles=lambda sym, a, b: [c for c in bars if a <= c[0] < b])
        self.assertAlmostEqual(o["stop_r"], 0.75)
        self.assertEqual(ex.stops[-1], ("p9", 106.75))

    def test_short_fib(self):
        ex, s = FakeExchange(), state()
        live.tick(s, ex, [fib_record(side="short", entry=100.0, sl=106.0, level="L4")], NOW, **HOOKS)
        self.assertEqual((ex.orders[0]["side"], ex.orders[0]["type"], ex.orders[0]["price"]), ("sell", "limit_order", 100.0))
        self.assertEqual(next(iter(s["orders"].values()))["sl"], 106.0)

    def test_skipped_when_price_is_already_through_the_stop(self):
        ex, s = FakeExchange(), state()
        live.tick(s, ex, [fib_record()], NOW, **dict(HOOKS, price_now=lambda sym: 90.5))
        self.assertEqual(ex.orders, [])
        self.assertIn("already through the stop", next(iter(s["orders"].values()))["reason"])
        ex2, s2 = FakeExchange(), state()
        live.tick(s2, ex2, [fib_record(sl=101.0)], NOW, **HOOKS)
        self.assertEqual(ex2.orders, [])
        self.assertIn("wrong side", next(iter(s2["orders"].values()))["reason"])

    def test_fib_and_trendline_share_the_limits(self):
        ex, s = FakeExchange(), state()
        live.tick(s, ex, [record("ETHUSD"), fib_record("ETHUSD", sent=NOW - 500)], NOW, **HOOKS)
        self.assertEqual(len(ex.orders), 1)
        self.assertIn("already", s["orders"][fib_record("ETHUSD", sent=NOW - 500)["id"]]["reason"])

    def test_orders_from_before_keep_their_trendline_name(self):
        old = {"symbol": "HYPEUSD", "side": "long", "broken": False}
        self.assertEqual(live.head_of(old), "HYPE TL BUY")
        self.assertEqual(live.head_of(dict(old, broken=True)), "HYPE TL BR BUY")
        self.assertEqual(live.head_of(dict(old, kind="fib", level="L2")), "HYPE FIB L2 BUY")


class DefaultKinds(unittest.TestCase):
    def test_trendlines_only_unless_set(self):
        import os
        if os.getenv("VICTUS_COINDCX_LIVE_KINDS"):
            self.skipTest("set in this environment")
        self.assertEqual(config.COINDCX_LIVE_KINDS, ("trendline",))
        self.assertEqual(live.kinds_text(), "trendlines")


class Signing(unittest.TestCase):
    def test_hmac_of_compact_json(self):
        sent = {}

        class Session:
            def post(self, url, data, timeout, headers):
                sent.update(url=url, data=data, headers=headers)

                class R:
                    status_code = 200

                    def json(self):
                        return {"ok": 1}
                return R()
        ex = live.CoinDCX("k", "s3cret", Session())
        ex.post("/x", {"a": 1})
        body = json.loads(sent["data"])
        self.assertIn("timestamp", body)
        self.assertNotIn(" ", sent["data"])
        want = hmac.new(b"s3cret", sent["data"].encode(), hashlib.sha256).hexdigest()
        self.assertEqual(sent["headers"]["X-AUTH-SIGNATURE"], want)
        self.assertEqual(sent["headers"]["X-AUTH-APIKEY"], "k")


if __name__ == "__main__":
    unittest.main()


class RemoteRecords(unittest.TestCase):
    def test_reads_lines_and_survives_failure(self):
        class R:
            text = '{"id": "a"}\nnot json\n{"id": "b"}\n'

            def raise_for_status(self):
                pass
        with patch.object(live.requests, "get", return_value=R()):
            self.assertEqual([r["id"] for r in live.remote_records()], ["a", "b"])
        with patch.object(live.requests, "get", side_effect=live.requests.ConnectionError("down")):
            self.assertEqual(live.remote_records(), [])
