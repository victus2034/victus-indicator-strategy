"""Weekly audit, 2026-11-08: the CoinDCX demo's Discord delivery and edge cases."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

import coindcx_demo as demo

T0 = 1_794_000_000 // 60 * 60
HOOK = {demo.WEBHOOK_ENV: "https://example.invalid/hook"}


def record(symbol="BTCUSD", entry=100.0, sl=98.0, sent=T0 + 10, level="L3", rid=None):
    return {"market": "crypto", "symbol": symbol, "tf": "1d", "kind": "fib", "level": level,
            "plan": {"side": "long", "entry": entry, "sl": sl},
            "id": rid or f"fib|{symbol}|1d|{level}@{sent}", "sent_ts": sent}


def no_candles(symbol, start, end):
    return []


class DemoDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = Path(self.dir.name)
        self.patches = [patch.object(demo, "STATE_FILE", d / "state.json"),
                        patch.object(demo, "RECORDS_FILE", d / "records.jsonl"),
                        patch.dict(os.environ, {demo.WEBHOOK_ENV: "", demo.FALLBACK_WEBHOOK_ENV: ""})]
        for p in self.patches:
            p.start()
        self.addCleanup(self.dir.cleanup)
        for p in self.patches:
            self.addCleanup(p.stop)
        demo.save_state(demo.new_state(T0, 1000))

    def write(self, rows):
        demo.RECORDS_FILE.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def test_discord_error_does_not_lose_the_tick(self):
        self.write([record()])
        with patch.dict(os.environ, HOOK), \
                patch.object(demo.scanner, "send_discord_message", side_effect=requests.ConnectionError("down")):
            demo.run_tick(now=T0 + 300, fetch=no_candles)          # raised before the fix
        state = demo.load_state()
        self.assertEqual(len(state["orders"]), 1)                   # the order is saved
        self.assertEqual(len(state["unposted"]), 1)                 # and still to be posted

    def test_a_split_digest_never_posts_its_first_half_twice(self):
        rows = [record(symbol=s, sent=T0 + 10 + i, level=lv)
                for i, (s, lv) in enumerate((s, lv) for s in ("BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "DOGEUSD")
                                            for lv in ("L1", "L2", "L3", "L4"))]
        self.write(rows)
        posted, calls = [], {"n": 0}

        def flaky(message, **_):
            calls["n"] += 1
            if calls["n"] == 2:
                return False                                        # the second message fails
            posted.append(message)
            return True

        with patch.dict(os.environ, HOOK), patch.object(demo.scanner, "send_discord_message", side_effect=flaky):
            demo.run_tick(now=T0 + 300, fetch=no_candles)
            first = list(posted)
            self.assertEqual(len(first), 1)
            demo.run_tick(now=T0 + 600, fetch=no_candles)
        self.assertEqual(demo.load_state()["unposted"], [])
        text = "\n".join(posted)
        for row in rows:                                            # every order said exactly once
            name = f"**{row['symbol'][:-3]} · FIB {row['level']} · BUY**"
            self.assertEqual(text.count(name), 1, name)
        self.assertTrue(all(len(m) <= 2000 for m in posted))

    def test_no_channel_drops_the_events_instead_of_piling_them_up(self):
        self.write([record()])
        demo.run_tick(now=T0 + 300, fetch=no_candles)
        state = demo.load_state()
        self.assertEqual(len(state["orders"]), 1)
        self.assertEqual(state["unposted"], [])

    def test_an_empty_account_takes_no_orders(self):
        state = demo.new_state(T0, 0)
        demo.tick(state, [record()], T0 + 300, no_candles)
        order = next(iter(state["orders"].values()))
        self.assertEqual((order["status"], order["reason"], order["risk"]), ("skipped", "account empty", 0.0))

    def test_an_alert_on_file_twice_is_one_order(self):
        state = demo.new_state(T0, 1000)
        demo.tick(state, [record(), record()], T0 + 300, no_candles)
        self.assertEqual(len(state["orders"]), 1)
        self.assertEqual([e["event"] for e in state["unposted"]], ["placed"])


if __name__ == "__main__":
    unittest.main()
