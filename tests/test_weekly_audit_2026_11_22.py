"""Weekly audit, 2026-11-22: coindcx_live.py / delta_live.py, the real-money bot."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

import coindcx_live as live
import config
from tests.test_coindcx_live import DAY, HOOKS, NOW, FakeExchange, StopMoves, record, state
from tests.test_coindcx_live import setUpModule, tearDownModule  # noqa: F401 - pre-22 Nov rules pinned


def xrp_daily(sym, now):
    from tests.test_coindcx_live import daily
    return [[c[0], c[1] / 50, c[2] / 50, c[3] / 50, c[4] / 50] for c in daily()]


class StateFile(unittest.TestCase):
    """An unreadable state used to read as "no state": the bot started over and saved on top of it."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "coindcx_live_state.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file_is_a_first_start(self):
        self.assertIsNone(live.load_state(self.path))

    def test_broken_files_raise(self):
        for text in ('{"orders": {"x": {"status": "open"', "<<<<<<< HEAD\n{}\n=======\n", "[]", '{"events": []}', ""):
            self.path.write_text(text, encoding="utf-8")
            with self.assertRaises(live.StateUnreadable, msg=text[:20]):
                live.load_state(self.path)

    def test_good_file_loads(self):
        s = state()
        s["orders"]["x"] = {"status": "open"}
        live.save_state(s, self.path)
        self.assertEqual(live.load_state(self.path)["orders"], {"x": {"status": "open"}})

    def test_run_tick_stops_and_saves_nothing_over_it(self):
        broken = '{"orders": {"tl|INJUSD@1": {"status": "open", "symbol": "INJUSD"'
        self.path.write_text(broken, encoding="utf-8")
        sent = []
        with patch.object(live, "STATE_FILE", self.path), patch.object(config, "COINDCX_LIVE_ENABLED", True), \
                patch.dict("os.environ", {"COINDCX_API_KEY": "k", "COINDCX_API_SECRET": "s"}), \
                patch.object(live, "tick") as tick, patch.object(live.demo, "send", side_effect=sent.append):
            self.assertIsNone(live.run_tick(NOW - NOW % 3600 + 60))
            tick.assert_not_called()
        self.assertEqual(self.path.read_text(encoding="utf-8"), broken)          # not overwritten
        self.assertEqual(len(sent), 1)
        self.assertIn("STOPPED", sent[0])


class Posting(unittest.TestCase):
    """A digest Discord split in two re-posted its first half every tick the second half failed."""

    def events(self, n):
        return [{"ts": NOW, "text": f"line {i} " + "x" * 300} for i in range(n)]

    def test_each_message_drops_its_own_events(self):
        s = state()
        s["events"] = self.events(12)                         # ~3,700 characters: two messages
        posted, answers = [], iter([True, False])
        def send(text):
            posted.append(text)
            return next(answers)
        with patch.object(live.demo, "send", side_effect=send):
            self.assertFalse(live.post(s))
        self.assertEqual(len(posted), 2)
        self.assertTrue(all(len(p) <= live.demo.DISCORD_LIMIT for p in posted))
        first = posted[0].count("line ")
        self.assertEqual(len(s["events"]), 12 - first)        # the posted half is gone ...
        self.assertTrue(s["events"][0]["text"].startswith(f"line {first} "))
        posted.clear()
        with patch.object(live.demo, "send", side_effect=lambda t: posted.append(t) or True):
            self.assertTrue(live.post(s))
        self.assertNotIn("line 0 ", "".join(posted))          # ... and never posted again
        self.assertEqual(s["events"], [])

    def test_no_channel_drops_events(self):
        s = state()
        s["events"] = self.events(3)
        with patch.object(live.demo, "send", return_value=None):
            live.post(s)
        self.assertEqual(s["events"], [])

    def test_events_are_capped_while_discord_is_down(self):
        s = state()
        s["events"] = self.events(500)
        with patch.object(live.demo, "send", return_value=False):
            live.post(s)
        self.assertEqual(len(s["events"]), live.MAX_EVENTS + 1)
        self.assertIn("300 older lines", s["events"][0]["text"])


class NoAnswer(unittest.TestCase):
    """Delta timing out on an order used to send the same trade to CoinDCX: two positions."""

    def setUp(self):
        import delta_live
        from tests.test_coindcx_live import FakeDeltaHttp
        self.http = FakeDeltaHttp()
        self.delta = delta_live.Delta("k", "s", session=self.http)
        self.dcx = FakeExchange()
        self.router = live.Router(self.dcx, self.delta)

    def place(self, error):
        def fail(*a, **k):
            raise error
        self.delta.create_order = fail
        s = state()
        with patch.dict("os.environ", {"DELTA_API_KEY": "k", "DELTA_API_SECRET": "s"}):
            live.tick(s, self.router, [record(symbol="XRPUSD", entry=2.0, sl=1.9, broken=True)], NOW,
                      **{**HOOKS, "price_now": lambda sym: 2.0, "daily": xrp_daily})
        return s, next(iter(s["orders"].values()))

    def test_timeout_is_not_sent_again_elsewhere(self):
        s, o = self.place(requests.ReadTimeout("read timed out"))
        self.assertEqual(self.dcx.orders, [])
        self.assertEqual(o["status"], "error")
        self.assertIn("check Delta", o["reason"])
        self.assertIn("UNCONFIRMED", s["events"][-1]["text"])

    def test_refusal_still_goes_to_coindcx(self):
        s, o = self.place(RuntimeError("Delta POST /v2/orders: HTTP 400 insufficient_margin"))
        self.assertEqual(len(self.dcx.orders), 1)
        self.assertEqual(o["status"], "pending")

    def test_coindcx_timeout_says_check_coindcx(self):
        class Slow(FakeExchange):
            def create_order(self, *a, **k):
                raise requests.ConnectionError("connection aborted")
        s = state()
        live.tick(s, Slow(), [record(broken=True)], NOW, **HOOKS)
        o = next(iter(s["orders"].values()))
        self.assertEqual(o["status"], "error")
        self.assertIn("check CoinDCX", o["reason"])

    def test_a_price_read_failure_is_not_unconfirmed(self):
        s = state()
        def down(sym):
            raise requests.ConnectionError("bitunix down")
        live.tick(s, FakeExchange(), [record(broken=True)], NOW, **dict(HOOKS, price_now=down))
        o = next(iter(s["orders"].values()))
        self.assertEqual(o["status"], "error")
        self.assertIn("FAILED", s["events"][-1]["text"])


class LimitFill(unittest.TestCase):
    """A limit that filled hours after it was placed counted the run-up before its fill."""

    def test_moves_before_the_fill_do_not_move_the_stop(self):
        ex, s = FakeExchange(), state()
        rec = record()                                         # no line: the limit at 100, stop 97
        live.tick(s, ex, [rec], NOW, **HOOKS)
        o = s["orders"][rec["id"]]
        bars = [[NOW + 60, 100.6, 103.5, 100.5, 103.2],        # +1.17R before any fill
                [NOW + 7200, 100.4, 100.5, 99.9, 100.1]]       # back down: the limit fills
        hourly = lambda sym, a, b: [c for c in bars if a <= c[0] < b]
        live.tick(s, ex, [], NOW + 3600, candles=hourly)       # still pending
        self.assertEqual(o["status"], "pending")
        ex.pos["B-BTC_USDT"] = {"id": "p1", "pair": "B-BTC_USDT", "active_pos": o["qty"], "avg_price": 100.0}
        live.tick(s, ex, [], NOW + 7260, candles=hourly)       # filled
        ex.pos["B-BTC_USDT"]["stop_loss_trigger"] = 97.0
        live.tick(s, ex, [], NOW + 7380, candles=hourly)
        self.assertEqual(o["status"], "open")
        self.assertLess(o["best_r"], 0.2)                      # only the fill hour's 100.5 (was 1.17R)
        self.assertIsNone(o["stop_r"])                         # was +0.75R: stop above price, closed at once
        self.assertEqual(ex.exits, [])
        self.assertEqual(ex.stops[-1], ("p1", 97.0))


class ExitOnce(unittest.TestCase):
    """A market exit is not sent again while the exchange still lists the position."""

    def setUp(self):
        self.s, self.ex, self.o = StopMoves.open_order(StopMoves())
        self.o.update(stop_r=1.5, best_r=1.6, stop_why="Trail TP", tick=0.1, stop_sent=110.1)
        self.bars = [[NOW - 60, 90, 91, 89, 90.5]]             # past the +1.5R stop (~85)

    def candles(self, sym, a, b):
        return [c for c in self.bars if a <= c[0] < b]

    def test_one_exit_while_the_list_lags(self):
        def refuse(pid, stop):
            raise RuntimeError("CoinDCX create_tpsl: HTTP 422 Trigger price should be greater than the current price")
        self.ex.set_stop = refuse
        live.tick(self.s, self.ex, [], NOW, candles=self.candles)
        live.tick(self.s, self.ex, [], NOW + 120, candles=self.candles)
        self.assertEqual(self.ex.exits, ["p1"])
        live.tick(self.s, self.ex, [], NOW + 360, candles=self.candles)
        self.assertEqual(self.ex.exits, ["p1", "p1"])          # still there after 5 minutes: again

    def test_stop_that_goes_in_later_drops_the_market_exit(self):
        live.tick(self.s, self.ex, [], NOW, candles=self.candles)
        self.bars.append([NOW + 300, 84, 84.5, 83.8, 84.0])     # back under the stop: it can go in
        live.tick(self.s, self.ex, [], NOW + 420, candles=self.candles)
        self.assertNotIn("exit_price", self.o)
        self.assertEqual(self.o["stop_why"], "Trail TP")
        self.assertEqual(self.o["stop_sent"], self.ex.stops[-1][1])


class AccountDown(unittest.TestCase):
    def test_reported_once_then_back(self):
        class Down(FakeExchange):
            up = False
            def positions(self):
                if not self.up:
                    raise RuntimeError("HTTP 503")
                return {}
        ex, s = Down(), state()
        for i in range(5):
            live.tick(s, ex, [], NOW + 120 * i)
        self.assertEqual(sum("account read FAILED" in e["text"] for e in s["events"]), 1)
        ex.up = True
        live.tick(s, ex, [], NOW + 900, candles=lambda *a: [])
        self.assertIn("working again", s["events"][-1]["text"])
        self.assertNotIn("account_error", s)


class ClosedClean(unittest.TestCase):
    def test_close_clears_the_last_error(self):
        s, ex, o = StopMoves.open_order(StopMoves())
        o["last_error"] = "CoinDCX create_tpsl: HTTP 422"
        del ex.pos["B-BTC_USDT"]
        live.tick(s, ex, [], NOW, candles=lambda *a: [])
        live.tick(s, ex, [], NOW + 120, candles=lambda *a: [])
        self.assertEqual(o["status"], "closed")
        self.assertNotIn("last_error", o)


class BadAlerts(unittest.TestCase):
    """A record with no usable entry crashed the whole tick: every open trade went unsaved for hours."""

    def test_unusable_entry_is_not_eligible(self):
        s = state()
        for entry in (None, "x", 0, -1, float("nan"), float("inf")):
            r = record()
            r["plan"]["entry"] = entry
            self.assertFalse(live.eligible(r, s, NOW), entry)
        r = record()
        del r["plan"]["entry"]
        self.assertFalse(live.eligible(r, s, NOW))

    def test_one_failing_alert_does_not_stop_the_rest(self):
        ex, s = FakeExchange(), state()
        bad, good = record(symbol="ETHUSD", sent=NOW - 900, broken=True), record(broken=True)
        real = live.place
        def place(state_, ex_, rec, now, **k):
            if rec["symbol"] == "ETHUSD":
                raise KeyError("line")
            return real(state_, ex_, rec, now, **k)
        with patch.object(live, "place", side_effect=place):
            live.tick(s, ex, [bad, good], NOW, **HOOKS)
        self.assertEqual(s["orders"][bad["id"]]["status"], "error")
        self.assertEqual(s["orders"][good["id"]]["status"], "pending")
        self.assertEqual(len(ex.orders), 1)

    def test_zero_row_never_makes_a_zero_stop(self):
        from tests.test_coindcx_live import daily
        rows = daily()
        rows[-1] = [rows[-1][0], 0, 0, 0, 0]                   # a bad newest candle
        self.assertEqual(live.wick_body_stop(rows, NOW, 100.0, "long"), 97.0)
        with patch.object(live.bitunix_data, "klines", return_value=[[NOW - 2 * DAY, 100, 101, 0, 100.5]] + daily()):
            self.assertTrue(all(min(c[1:5]) > 0 for c in live.daily_candles("BTCUSD", NOW)))


class PriceText(unittest.TestCase):
    def test_not_a_number_prints_instead_of_raising(self):
        import scanner
        self.assertEqual(scanner.price_text(float("nan")), "nan")
        self.assertEqual(scanner.price_text(float("inf")), "inf")
        self.assertEqual(scanner.price_text(1.23456), "1.235")


if __name__ == "__main__":
    unittest.main()
