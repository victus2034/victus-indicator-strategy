"""Live bot Discord: entries and exits only (lakky, 2026-11-23: "In discord only punch alerts which is
traded as buy or sell entry and exit thats it no other alert"). Every other line - order sent, skips,
waits, stop moves, rules, failures - goes to the run log only. VICTUS_COINDCX_LIVE_DISCORD=warnings
adds failures back, =all posts every line as before."""
import unittest
from unittest.mock import patch

import coindcx_live as live
import config
from tests.test_coindcx_live import HOOKS, NOW, FakeExchange, record, state


def sent_texts(s):
    out = []
    with patch.object(live.demo, "send", side_effect=lambda text: out.append(text) or True):
        live.post(s)
    return "\n".join(out)


class TradesOnly(unittest.TestCase):
    def test_default(self):
        self.assertEqual(config.COINDCX_LIVE_DISCORD, "trades")

    def full_trade(self):
        """A short break: sent at market, filled, stop moved to +0.75R, stopped out. Returns the
        Discord text of each tick."""
        ex, s = FakeExchange(), state()
        rec = record(side="short", entry=100.0, sl=104.0, broken=True)
        live.tick(s, ex, [rec], NOW, **dict(HOOKS, price_now=lambda sym: 99.0))
        posts = [sent_texts(s)]
        ex.pos["B-BTC_USDT"] = {"id": "p1", "pair": "B-BTC_USDT", "active_pos": -1.0, "avg_price": 99.0}
        live.tick(s, ex, [], NOW + 120, candles=lambda *a: [])
        posts.append(sent_texts(s))
        ex.pos["B-BTC_USDT"]["stop_loss_trigger"] = 100.3
        bars = [[NOW + 120, 99.0, 99.0, 97.6, 97.8]]                         # +1R (97.7) traded
        live.tick(s, ex, [], NOW + 240, candles=lambda sym, a, b: [c for c in bars if a <= c[0] < b])
        posts.append(sent_texts(s))
        del ex.pos["B-BTC_USDT"]
        live.tick(s, ex, [], NOW + 360, candles=lambda *a: [])
        live.tick(s, ex, [], NOW + 480, candles=lambda *a: [])
        posts.append(sent_texts(s))
        return s, s["orders"][rec["id"]], posts

    def test_only_entry_and_exit_are_posted(self):
        s, o, (placed, filled, moved, closed) = self.full_trade()
        self.assertEqual(o["status"], "closed")
        self.assertEqual(placed, "")                                        # order sent: log only
        self.assertEqual(filled.count("\n"), 1)                             # header + one line
        self.assertIn("🔴 **BTC TL BR SELL** ENTRY 99", filled)
        self.assertIn("SL 100.3", filled)
        self.assertIn("CoinDCX", filled)
        self.assertEqual(moved, "")                                         # stop moved: log only
        self.assertEqual(closed.count("\n"), 1)
        self.assertIn("**BTC TL BR SELL** EXIT", closed)
        self.assertIn(f"{o['r']:+.2f}R", closed)
        self.assertIn("total", closed)
        self.assertEqual(s["events"], [])                                   # nothing left behind

    def test_run_log_keeps_every_line(self):
        printed = []
        with patch("builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(map(str, a)))):
            self.full_trade()
        log = "\n".join(printed)
        for text in ("order sent", "ENTRY", "stop moved", "EXIT"):
            self.assertIn(text, log)

    def test_skips_and_failures_stay_off_discord(self):
        s, ex = state(), FakeExchange()
        recs = [record(broken=True), record(broken=True, sent=NOW - 500)]  # same coin twice: one skipped
        live.tick(s, ex, recs, NOW, **HOOKS)
        live.note(s, "⚠️ account read FAILED, nothing done: 500", NOW, "warn")
        live.note(s, "⚙️ rules now: ...", NOW)
        self.assertEqual(sent_texts(s), "")
        self.assertEqual(s["events"], [])

    def test_old_events_without_a_kind_are_not_posted(self):
        s = state()
        s["events"] = [{"ts": NOW, "text": "📥 old line"}]
        self.assertEqual(sent_texts(s), "")

    def test_stopped_message_is_not_sent(self):
        sent = []
        with patch.object(config, "COINDCX_LIVE_ENABLED", True), \
                patch.dict("os.environ", {"COINDCX_API_KEY": "k", "COINDCX_API_SECRET": "s"}), \
                patch.object(live, "load_state", side_effect=live.StateUnreadable("cut short")), \
                patch.object(live.demo, "send", side_effect=lambda t: sent.append(t) or True):
            self.assertIsNone(live.run_tick(NOW - NOW % 3600 + 60))
        self.assertEqual(sent, [])


class OtherModes(unittest.TestCase):
    def lines(self, mode):
        s = state()
        for kind in ("entry", "exit", "warn", "info"):
            live.note(s, f"{kind} line", NOW, kind)
        with patch.object(config, "COINDCX_LIVE_DISCORD", mode):
            return sent_texts(s)

    def test_warnings_adds_failures(self):
        text = self.lines("warnings")
        self.assertIn("warn line", text)
        self.assertNotIn("info line", text)

    def test_all_posts_everything(self):
        text = self.lines("all")
        for kind in ("entry", "exit", "warn", "info"):
            self.assertIn(f"{kind} line", text)

    def test_trades(self):
        text = self.lines("trades")
        self.assertIn("entry line", text)
        self.assertIn("exit line", text)
        self.assertNotIn("warn line", text)
        self.assertNotIn("info line", text)


if __name__ == "__main__":
    unittest.main()
