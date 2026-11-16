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
        self.assertEqual(ex.orders[0]["lev"], 20)                                  # stop 3%: 20x liquidates ~4.5% away
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
        self.assertEqual(ex.stops[-1], ("p1", 102.2))                         # on the 0.1 price step, away from price
        # stopped out: the position is gone
        del ex.pos["B-BTC_USDT"]
        live.tick(s, ex, [], NOW + 900, candles=lambda *a: [])
        self.assertEqual(o["status"], "open")                                 # one missing read is not a close
        live.tick(s, ex, [], NOW + 1020, candles=lambda *a: [])
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


class Safety(unittest.TestCase):
    def test_leverage_keeps_liquidation_past_the_stop(self):
        ex, s = FakeExchange(), state()
        far = dict(HOOKS, daily=lambda sym, now: daily(lows=(88.0, 99.5, 99.8)))    # stop 12% away
        live.tick(s, ex, [record()], NOW, **far)
        self.assertEqual(s["orders"][record()["id"]]["sl"], 88.0)
        self.assertEqual(ex.orders[0]["lev"], 5)                                    # 70 / 12

    def test_stop_goes_in_when_there_is_nothing_to_cancel(self):
        calls = []

        class C(live.CoinDCX):
            def post(self, path, body):
                calls.append(path.rsplit("/", 1)[-1])
                if path.endswith("cancel_all_open_orders_for_position"):
                    raise RuntimeError('CoinDCX x: HTTP 422 {"message":"No open orders found for this position"}')
                return {"ok": 1}
        C("k", "s").set_stop("p1", 97.0)
        self.assertEqual(calls, ["cancel_all_open_orders_for_position", "create_tpsl"])

    def test_other_cancel_errors_still_raise(self):
        class C(live.CoinDCX):
            def post(self, path, body):
                raise RuntimeError("CoinDCX x: HTTP 500 down")
        with self.assertRaises(RuntimeError):
            C("k", "s").set_stop("p1", 97.0)

    def test_a_failing_stop_is_reported_once(self):
        class NoStop(FakeExchange):
            def set_stop(self, pid, stop):
                raise RuntimeError("HTTP 400 bad stop")
        ex, s = NoStop(), state()
        live.tick(s, ex, [record()], NOW, **HOOKS)
        ex.pos["B-BTC_USDT"] = {"id": "p1", "pair": "B-BTC_USDT", "active_pos": 0.333, "avg_price": 100.0}
        s["events"] = []
        for i in (1, 2, 3):
            live.tick(s, ex, [], NOW + 300 * i, candles=lambda *a: [])
        self.assertEqual(sum("manage FAILED" in e["text"] for e in s["events"]), 1)


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


def touch(side="long", sent=NOW - 600, line=(100.0, 100.0)):
    """A touch record whose line runs flat (or sloped) at `line` prices, anchored well before NOW."""
    r = record(side=side, entry=line[1], sl=97.0 if side == "long" else 103.0, sent=sent)
    stamp = lambda ts: live.datetime.fromtimestamp(ts, live.scanner.IST).strftime("%Y-%m-%d %H:%M")
    r["from"], r["to"] = [line[0], stamp(NOW - 40 * DAY)], [line[1], stamp(NOW - 20 * DAY)]
    return r


class ConfirmEntry(unittest.TestCase):
    """Touch alerts wait for a closed 1h candle that trades the line and closes back (lakky, 2026-11-16)."""

    def run_hours(self, bars, rec=None, now=None):
        ex, s = FakeExchange(), state()
        rec = rec or touch()
        live.tick(s, ex, [rec], NOW, **HOOKS, hourly=lambda *a: [])
        o = s["orders"][rec["id"]]
        live.tick(s, ex, [], now or NOW + 3 * 3600 + 60, **HOOKS, candles=lambda *a: [],
                  hourly=lambda sym, a, b: [c for c in bars if a <= c[0] < b])
        return ex, s, o

    def test_waits_then_enters_at_market_on_a_held_hour(self):
        h = NOW - NOW % 3600 + 3600                          # first full hour after the alert
        bars = [[h, 100.5, 100.8, 100.2, 100.4],             # never reached the line: wait
                [h + 3600, 100.4, 100.6, 99.6, 99.8],         # through the line, closed under: wait
                [h + 7200, 99.8, 100.9, 99.7, 100.6]]         # traded the line, closed above: enter
        ex, s, o = self.run_hours(bars, now=h + 3 * 3600 + 60)
        self.assertEqual(len(ex.orders), 1)
        self.assertEqual(ex.orders[0]["type"], "market_order")
        self.assertEqual(o["status"], "pending")
        self.assertEqual(o["sl"], 97.0)

    def test_nothing_sent_while_waiting(self):
        ex, s = FakeExchange(), state()
        live.tick(s, ex, [touch()], NOW, **HOOKS, hourly=lambda *a: [])
        self.assertEqual(ex.orders, [])
        self.assertEqual(s["orders"][touch()["id"]]["status"], "waiting")

    def test_short_mirrors(self):
        h = NOW - NOW % 3600 + 3600
        bars = [[h, 99.5, 100.3, 99.4, 99.6]]                 # wick above a resistance at 100, closed under
        ex, s, o = self.run_hours(bars, rec=touch(side="short"), now=h + 3600 + 60)
        self.assertEqual(ex.orders[0]["side"], "sell")

    def test_daily_close_through_the_line_ends_the_wait(self):
        end = NOW - NOW % DAY + DAY
        bars = [[end - 3600, 99.9, 100.0, 98.0, 98.5]]        # last hour of the day closes under the line
        ex, s, o = self.run_hours(bars, now=end + 60)
        self.assertEqual(ex.orders, [])
        self.assertEqual(o["status"], "cancelled")
        self.assertIn("daily close", o["reason"])

    def test_a_late_confirm_is_not_chased(self):
        h = NOW - NOW % 3600 + 3600
        bars = [[h, 99.8, 100.9, 99.7, 100.6]]
        ex, s, o = self.run_hours(bars, now=h + 3600 + 3600)
        self.assertEqual(ex.orders, [])
        self.assertIn("too late", o["reason"])

    def test_limit_mode_keeps_the_old_order(self):
        with patch.object(config, "COINDCX_LIVE_TOUCH_ENTRY", "limit"):
            ex, s = FakeExchange(), state()
            live.tick(s, ex, [touch()], NOW, **HOOKS)
            self.assertEqual(ex.orders[0]["type"], "limit_order")

    def test_a_record_without_its_line_keeps_the_limit(self):
        ex, s = FakeExchange(), state()
        live.tick(s, ex, [record()], NOW, **HOOKS)
        self.assertEqual(ex.orders[0]["type"], "limit_order")


class FakeDeltaHttp:
    """Delta India's REST API as the bot uses it: products, leverage, orders, margined positions."""

    PRODUCTS = {"XRPUSD": {"id": 14969, "symbol": "XRPUSD", "state": "live", "contract_value": "1",
                           "tick_size": "0.0001", "initial_margin": "1"}}

    def __init__(self):
        self.calls, self.orders, self.positions, self.next_id = [], {}, [], 100

    def request(self, method, url, data=None, headers=None, timeout=None):
        path = url.split("india.delta.exchange", 1)[1].split("?")[0]
        body = json.loads(data) if data else None
        self.calls.append((method, path, body, headers))
        if path.startswith("/v2/products/") and method == "GET":
            result = self.PRODUCTS.get(path.rsplit("/", 1)[1])
        elif path.endswith("/orders/leverage"):
            result = {"leverage": body["leverage"]}
        elif path == "/v2/orders" and method == "POST":
            self.next_id += 1
            o = {**body, "id": self.next_id, "state": "open"}
            if body.get("stop_order_type"):
                o["stop_order_type"] = body["stop_order_type"]
                o["reduce_only"] = True
            self.orders[self.next_id] = o
            result = o
        elif path == "/v2/orders" and method == "DELETE":
            result = self.orders.pop(body["id"])
        elif path == "/v2/orders":
            result = list(self.orders.values())
        elif path == "/v2/positions/margined":
            result = self.positions
        else:
            raise AssertionError(f"unexpected {method} {path}")
        return type("R", (), {"status_code": 200, "json": lambda self_: {"success": True, "result": result},
                              "text": ""})()


class DeltaVenue(unittest.TestCase):
    def setUp(self):
        import delta_live
        self.dl = delta_live
        self.http = FakeDeltaHttp()
        self.delta = delta_live.Delta("k", "s", session=self.http)

    def test_instrument_is_in_coins_with_leverage_from_margin(self):
        ins = self.delta.instrument("DELTA:XRPUSD")
        self.assertEqual(ins["quantity_increment"], 1.0)
        self.assertEqual(ins["price_increment"], 0.0001)
        self.assertEqual(ins["max_leverage_long"], 100.0)

    def test_order_is_whole_contracts_on_the_tick_and_signed(self):
        got = self.delta.create_order("DELTA:XRPUSD", "buy", "limit_order", 12.0, 7, 2.123456789)
        self.assertEqual(got["id"], "14969:101")
        lev, order = self.http.calls[-2], self.http.calls[-1]
        self.assertEqual(lev[2], {"leverage": "7"})
        self.assertEqual(order[2], {"product_id": 14969, "size": 12, "side": "buy", "order_type": "limit_order",
                                    "reduce_only": "false", "limit_price": "2.1235"})
        h = order[3]
        want = hmac.new(b"s", ("POST" + h["timestamp"] + "/v2/orders" + json.dumps(order[2], separators=(",", ":"))).encode(),
                        hashlib.sha256).hexdigest()
        self.assertEqual(h["signature"], want)
        with self.assertRaises(RuntimeError):
            self.delta.create_order("DELTA:XRPUSD", "buy", "market_order", 0.4, 5)        # under one contract

    def test_short_position_and_stop_move_never_leave_it_bare(self):
        self.delta.product("XRPUSD")
        self.http.positions = [{"product_id": 14969, "product_symbol": "XRPUSD", "size": -30, "entry_price": "2.5"}]
        self.delta.set_stop("DELTA:XRPUSD", 2.6)
        first = self.delta.stop_orders()
        self.assertEqual([(o["side"], o["size"], o["stop_price"]) for o in first], [("buy", 30, "2.6000")])
        pos = self.delta.positions()["DELTA:XRPUSD"]
        self.assertEqual((pos["active_pos"], pos["avg_price"], pos["stop_loss_trigger"]), (-30.0, 2.5, "2.6000"))
        self.delta.set_stop("DELTA:XRPUSD", 2.55)
        posts = [i for i, c in enumerate(self.http.calls) if c[0] == "POST" and c[1] == "/v2/orders"]
        dels = [i for i, c in enumerate(self.http.calls) if c[0] == "DELETE"]
        self.assertLess(posts[-1], dels[-1])                                        # new stop in before the old one goes
        self.assertEqual([o["stop_price"] for o in self.delta.stop_orders()], ["2.5500"])
        self.assertEqual(self.delta.open_orders(), [])                                # stops are not entry orders

    def test_cancel_takes_product_and_order(self):
        self.delta.create_order("DELTA:XRPUSD", "sell", "limit_order", 5, 5, 3.0)
        self.delta.cancel("14969:101")
        self.assertEqual(self.http.calls[-1][2], {"id": 101, "product_id": 14969})

    def test_router_and_venue(self):
        dcx = FakeExchange()
        r = live.Router(dcx, self.delta)
        r.create_order("B-BTC_USDT", "buy", "limit_order", 0.01, 5, 100.0)
        self.assertEqual(len(dcx.orders), 1)
        got = r.create_order("DELTA:XRPUSD", "buy", "market_order", 3, 5)
        self.assertEqual(len(dcx.orders), 1)
        self.assertEqual(got["id"], "14969:101")
        self.assertEqual({o["id"] for o in r.open_orders()}, {"o0", "14969:101"})
        r.cancel("14969:101")
        r.cancel("o0")
        self.assertEqual(dcx.cancelled, ["o0"])
        with patch.dict("os.environ", {"DELTA_API_KEY": "k", "DELTA_API_SECRET": "s"}):
            self.assertEqual(live.venue_pair("XRPUSD"), "DELTA:XRPUSD")
            with patch.object(config, "LIVE_DELTA", False):
                self.assertNotIn("DELTA", live.venue_pair("XRPUSD"))
        with patch.dict("os.environ", {"DELTA_API_KEY": "", "DELTA_API_SECRET": ""}):
            self.assertNotIn("DELTA", live.venue_pair("XRPUSD"))

    def test_bot_flow_on_delta_fill_lag_stop_close(self):
        """A break order on Delta: the position shows up a tick late (no false close), the stop
        goes in on the fill, and the close is booked only once the position stays gone."""
        s = state()
        r = live.Router(FakeExchange(), self.delta)
        with patch.dict("os.environ", {"DELTA_API_KEY": "k", "DELTA_API_SECRET": "s"}):
            live.tick(s, r, [record(symbol="XRPUSD", entry=2.0, sl=1.9, broken=True)], NOW, **{
                **HOOKS, "price_now": lambda sym: 2.0,
                "daily": lambda sym, now: [[c[0], c[1] / 50, c[2] / 50, c[3] / 50, c[4] / 50] for c in daily()]})
        o = next(iter(s["orders"].values()))
        self.assertEqual((o["status"], o["pair"]), ("pending", "DELTA:XRPUSD"))
        self.http.orders.pop(int(o["exchange_id"].split(":")[1]))                  # filled: off the book ...
        live.tick(s, r, [], NOW + 120, candles=lambda *a: [])
        self.assertEqual(o["status"], "pending")                                     # ... position not listed yet
        self.http.positions = [{"product_id": 14969, "product_symbol": "XRPUSD", "size": int(o["qty"]), "entry_price": "2.0"}]
        live.tick(s, r, [], NOW + 240, candles=lambda *a: [])
        self.assertEqual(o["status"], "open")
        self.assertEqual([x["stop_price"] for x in self.delta.stop_orders()], [f"{o['sl']:.4f}"])
        self.http.positions = []
        live.tick(s, r, [], NOW + 360, candles=lambda *a: [])
        self.assertEqual(o["status"], "open")
        live.tick(s, r, [], NOW + 480, candles=lambda *a: [])
        self.assertEqual((o["status"], o["exit_why"]), ("closed", "SL"))

    def test_delta_refusal_falls_back_to_coindcx(self):
        s = state()
        dcx = FakeExchange()
        r = live.Router(dcx, self.delta)
        def broke(*a, **k):
            raise RuntimeError("Delta POST /v2/orders: HTTP 400 insufficient_margin")
        self.delta.create_order = broke
        with patch.dict("os.environ", {"DELTA_API_KEY": "k", "DELTA_API_SECRET": "s"}):
            live.tick(s, r, [record(symbol="XRPUSD", entry=2.0, sl=1.9, broken=True)], NOW, **{
                **HOOKS, "price_now": lambda sym: 2.0,
                "daily": lambda sym, now: [[c[0], c[1] / 50, c[2] / 50, c[3] / 50, c[4] / 50] for c in daily()]})
        o = next(iter(s["orders"].values()))
        self.assertEqual(o["status"], "pending")
        self.assertNotIn("DELTA", o["pair"])
        self.assertEqual(len(dcx.orders), 1)
        self.assertTrue(any("sent to CoinDCX" in e["text"] for e in s["events"]))
