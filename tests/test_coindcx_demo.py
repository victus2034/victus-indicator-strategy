"""CoinDCX demo account (coindcx_demo.py): 1D crypto fib alerts as pretend orders."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import coindcx_demo as demo
import config
import fib_trendline_trades as trades

T0 = 1_794_000_000 // 60 * 60          # an alert's minute
DAY = 86400


def record(symbol="BTCUSD", side="long", entry=100.0, sl=98.0, sent=T0 + 10, tf="1d", kind="fib",
           level="L3", market="crypto", rid=None):
    return {"market": market, "symbol": symbol, "tf": tf, "kind": kind, "level": level,
            "plan": {"side": side, "entry": entry, "sl": sl},
            "id": rid or f"fib|{symbol}|{tf}|{level}@{sent}", "sent_ts": sent}


def fake_fetch(candles):
    """candles: {symbol: [[ts, o, h, l, c], ...]} served like klines: opening in [start, end)."""
    def fetch(symbol, start, end):
        return [c for c in candles.get(symbol, []) if start <= c[0] < end]
    return fetch


class SizingMatchesJournal(unittest.TestCase):
    def test_fixed_risk(self):
        risk, position, lev, capped = demo.size(1000, 100, 98, 50, 10)      # 2% stop
        self.assertAlmostEqual(risk, 50)
        self.assertAlmostEqual(position, 2500)
        self.assertAlmostEqual(lev, 2.5)
        self.assertFalse(capped)

    def test_cap_lowers_risk(self):
        risk, position, lev, capped = demo.size(1000, 100, 99.8, 50, 10)    # 0.2% stop needs 25x
        self.assertTrue(capped)
        self.assertAlmostEqual(lev, 10)
        self.assertAlmostEqual(position, 10000)
        self.assertAlmostEqual(risk, 20)                                     # journal: bal * cap * stop%

    def test_risk_never_above_balance(self):
        risk, *_ = demo.size(30, 100, 90, 50, 10)
        self.assertAlmostEqual(risk, 30)


class Eligibility(unittest.TestCase):
    def test_only_1d_crypto_fib_on_coindcx_coins_after_start(self):
        self.assertTrue(demo.eligible(record(), T0))
        self.assertTrue(demo.eligible(record(tf="1D"), T0))
        self.assertFalse(demo.eligible(record(sent=T0 - 1), T0))          # before the demo began
        self.assertFalse(demo.eligible(record(tf="4h"), T0))
        self.assertFalse(demo.eligible(record(tf="1w"), T0))
        self.assertFalse(demo.eligible(record(kind="trendline"), T0))
        self.assertFalse(demo.eligible(record(symbol="TSLAXUSD"), T0))     # xStock: not on CoinDCX
        self.assertFalse(demo.eligible(record(symbol="XAUTUSD"), T0))
        self.assertFalse(demo.eligible(record(market="nse", symbol="RELIANCE.NS"), T0))
        self.assertFalse(demo.eligible(record(sl=100.0), T0))              # no stop distance
        self.assertFalse(demo.eligible({"kind": "fib"}, T0))

    def test_pair_names(self):
        self.assertEqual(demo.coindcx_pair("BTCUSD"), "B-BTC_USDT")
        self.assertEqual(demo.coindcx_pair("1000PEPEUSD"), "B-1000PEPE_USDT")
        for symbol in config.CRYPTO_WATCHLIST:
            self.assertTrue(demo.coindcx_pair(symbol).endswith("_USDT"), symbol)


class Trades(unittest.TestCase):
    def run_demo(self, records, candles, now):
        state = demo.new_state(T0, 1000)
        demo.tick(state, records, now, fake_fetch(candles))
        return state

    def test_target_locks_then_trails(self):
        # long 100, stop 98: 1R = 2.0, first target 1.5R = 103
        candles = {"BTCUSD": [
            [T0, 100, 100, 99, 100],               # the alert's own minute: not used
            [T0 + 60, 101, 101, 100.5, 101],       # above the limit
            [T0 + 120, 100.5, 100.6, 99.9, 100],   # fills
            [T0 + 180, 100, 103.1, 99.5, 103],     # 1.55R: stop locked at +1.5R, target 1.75R
            [T0 + 240, 103, 104.6, 103.2, 104],    # 2.3R: targets 1.75 / 2.0 / 2.25 -> stop +1.75R
            [T0 + 300, 104, 104.1, 103.4, 103.5],  # back to 103.4: the +1.75R stop (103.5) is hit
        ]}
        state = self.run_demo([record()], candles, T0 + 600)
        o = next(iter(state["orders"].values()))
        self.assertEqual(o["status"], "won")
        self.assertEqual(o["exit_why"], "Trail TP")
        self.assertEqual(o["fill_ts"], T0 + 120)
        # by hand, as the journal's exit(): 1.75 - (1 + 1.75 x 2/100) x 0.05/2 - 0.0826/2
        r = 1.75 - (1 + 1.75 * 0.02) * 0.05 / 2 - config.COINDCX_DEMO_ROUND_TRIP_COST_PCT / 2
        self.assertAlmostEqual(o["r"], r, places=4)
        self.assertAlmostEqual(o["pnl"], 75 * r, places=2)
        self.assertAlmostEqual(state["balance"], 1000 + o["pnl"], places=3)
        events = [(e["event"], e.get("r")) for e in state["unposted"]]
        self.assertEqual(events, [("placed", None), ("filled", None), ("stop", 1.5), ("stop", 1.75), ("won", None)])

    def test_sl_shift_at_1r(self):
        candles = {"BTCUSD": [
            [T0 + 60, 100.5, 100.6, 99.9, 100],    # fills
            [T0 + 120, 100, 102.1, 99.5, 102],     # +1.05R: stop to +0.75R (101.5)
            [T0 + 180, 102, 102.2, 101.4, 101.6],  # 101.4: stopped at +0.75R
        ]}
        state = self.run_demo([record()], candles, T0 + 600)
        o = next(iter(state["orders"].values()))
        self.assertEqual(o["status"], "won")
        self.assertEqual(o["exit_why"], "SL shift")
        self.assertAlmostEqual(o["r"], demo.moved_stop_r(o, 0.75), places=4)
        self.assertGreater(o["r"], 0.6)

    def test_stop_moves_only_from_the_next_candle(self):
        candles = {"BTCUSD": [
            [T0 + 60, 100.5, 100.6, 99.9, 100],    # fills
            [T0 + 120, 100, 102.1, 101.0, 102],    # reaches 1R and dips to 101.0 in the same candle
        ]}
        state = self.run_demo([record()], candles, T0 + 600)
        self.assertEqual(next(iter(state["orders"].values()))["status"], "open")

    def test_alert_minute_never_fills(self):
        candles = {"BTCUSD": [[T0, 100, 100, 99, 100]]}
        state = self.run_demo([record()], candles, T0 + 600)
        self.assertEqual(next(iter(state["orders"].values()))["status"], "pending")

    def test_candle_touching_stop_and_target_is_the_stop(self):
        candles = {"BTCUSD": [
            [T0 + 60, 100.5, 100.6, 99.9, 100],
            [T0 + 120, 100, 103.5, 97.5, 100],
        ]}
        state = self.run_demo([record()], candles, T0 + 600)
        o = next(iter(state["orders"].values()))
        self.assertEqual(o["status"], "lost")
        plan = {"side": "long", "entry": 100.0, "sl": 98.0}
        expect = trades.stop_r(plan) - config.COINDCX_DEMO_ROUND_TRIP_COST_PCT / 2
        self.assertAlmostEqual(o["r"], expect, places=4)
        self.assertLess(o["pnl"], -75)

    def test_short(self):
        candles = {"ETHUSD": [
            [T0 + 60, 99.5, 100.1, 99.4, 100],     # sell limit at 100 fills
            [T0 + 120, 100, 100.2, 96.9, 97],      # 1.55R: stop locked at +1.5R (97)
            [T0 + 180, 97, 97.1, 96.95, 97],       # back to 97.1: stopped at +1.5R
        ]}
        state = self.run_demo([record("ETHUSD", "short", 100.0, 102.0)], candles, T0 + 600)
        self.assertEqual(next(iter(state["orders"].values()))["status"], "won")

    def test_no_fill_in_twenty_days_is_cancelled(self):
        candles = {"BTCUSD": [[T0 + 60 * i, 101, 101.5, 100.5, 101] for i in range(1, 5)]
                   + [[T0 + 20 * DAY + 60, 101, 101.5, 100.5, 101]]}
        state = self.run_demo([record()], candles, T0 + 19 * DAY)
        self.assertEqual(next(iter(state["orders"].values()))["status"], "pending")
        state = self.run_demo([record()], candles, T0 + 20 * DAY + 600)
        o = next(iter(state["orders"].values()))
        self.assertEqual(o["status"], "cancelled")
        self.assertAlmostEqual(state["balance"], 1000)

    def test_cancelled_on_the_clock_when_candles_stop(self):
        state = self.run_demo([record()], {}, T0 + 20 * DAY + demo.CANCEL_GRACE_SECONDS + 60)
        self.assertEqual(next(iter(state["orders"].values()))["status"], "cancelled")

    def test_margin_that_does_not_fit_is_skipped(self):
        # 0.5% stop: 75 / 0.5% = 15,000 position, 15x, margin 750 of the 1,000 at the 20x max
        first = record(entry=100.0, sl=99.5, rid="a")
        second = record(symbol="ETHUSD", entry=100.0, sl=99.5, sent=T0 + 30, rid="b")
        state = self.run_demo([first, second], {}, T0 + 600)
        self.assertEqual(state["orders"]["a"]["status"], "pending")
        self.assertAlmostEqual(state["orders"]["a"]["margin"], 750)
        self.assertEqual(state["orders"]["b"]["status"], "skipped")
        self.assertIn("margin", state["orders"]["b"]["reason"])

    def test_a_close_frees_margin_for_a_later_alert(self):
        first = record(entry=100.0, sl=99.5, rid="a")
        later = record(symbol="ETHUSD", entry=100.0, sl=99.5, sent=T0 + 600, rid="b")
        candles = {"BTCUSD": [[T0 + 60, 100, 100.1, 99.9, 100], [T0 + 120, 100, 100.1, 99.4, 99.5]]}
        state = self.run_demo([first, later], candles, T0 + 900)
        self.assertEqual(state["orders"]["a"]["status"], "lost")
        self.assertLess(state["balance"], 925)
        # without BTC's close its 750 margin would have left no room
        self.assertEqual(state["orders"]["b"]["status"], "pending")

    def test_an_order_is_made_once(self):
        state = demo.new_state(T0, 1000)
        demo.tick(state, [record()], T0 + 120, fake_fetch({}))
        demo.tick(state, [record()], T0 + 240, fake_fetch({}))
        self.assertEqual(len(state["orders"]), 1)
        self.assertEqual([e["event"] for e in state["unposted"]], ["placed"])


class Ticks(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = Path(self.dir.name)
        self.state_file = d / "coindcx_demo_state.json"
        self.records_file = d / "records.jsonl"
        self.patches = [patch.object(demo, "STATE_FILE", self.state_file),
                        patch.object(demo, "RECORDS_FILE", self.records_file)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.dir.cleanup()

    def write_records(self, rows):
        self.records_file.write_text("".join(json.dumps(r) + "\n" for r in rows) + "{torn", encoding="utf-8")

    def test_first_tick_starts_the_demo_without_the_backlog(self):
        self.write_records([record(sent=T0 - DAY)])
        with patch.object(demo, "send") as send:
            demo.run_tick(now=T0)
            state = demo.load_state()
            self.assertEqual(state["started_ts"], T0)
            demo.run_tick(now=T0 + 300, fetch=fake_fetch({}))
        self.assertEqual(demo.load_state()["orders"], {})
        send.assert_not_called()

    def test_events_kept_until_discord_takes_them(self):
        demo.save_state(demo.new_state(T0, 1000))
        self.write_records([record()])
        with patch.object(demo, "send", return_value=False):
            demo.run_tick(now=T0 + 300, fetch=fake_fetch({}))
        self.assertEqual(len(demo.load_state()["unposted"]), 1)
        with patch.object(demo, "send", return_value=True) as send:
            demo.run_tick(now=T0 + 600, fetch=fake_fetch({}))
        text = send.call_args[0][0]
        self.assertIn("BTC · FIB L3 · BUY", text)
        self.assertIn("order placed", text)
        self.assertIn("no real orders", text)
        self.assertEqual(demo.load_state()["unposted"], [])

    def test_dry_run_saves_nothing(self):
        demo.save_state(demo.new_state(T0, 1000))
        self.write_records([record()])
        with patch.object(demo, "send") as send:
            demo.run_tick(now=T0 + 300, dry_run=True, fetch=fake_fetch({}))
        send.assert_not_called()
        self.assertEqual(demo.load_state()["orders"], {})

    def test_off_switch(self):
        with patch.object(config, "COINDCX_DEMO_ENABLED", False):
            self.assertIsNone(demo.run_tick(now=T0))
        self.assertFalse(self.state_file.exists())


class NoRealOrders(unittest.TestCase):
    def test_module_never_talks_to_coindcx(self):
        source = Path(demo.__file__).read_text(encoding="utf-8")
        self.assertNotIn("api.coindcx.com", source)
        self.assertNotIn("X-AUTH", source)


if __name__ == "__main__":
    unittest.main()
