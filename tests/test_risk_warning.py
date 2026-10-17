"""The ⚠️ risk line on crypto fib + trendline alerts (lakky, 2026-10-17)."""
import unittest

import fib_trendline_data as ftd
import fib_trendline_scanner as fts
from trendlines import SUPPORT

HOUR = 3600
NOW = 1_000 * 86400 + 30 * 60          # 30 minutes into an hour


def hourly(closes_by_hours_ago):
    """1h candles whose close is `closes_by_hours_ago[h]` for the candle that closed h hours before the hour."""
    top = NOW // HOUR * HOUR
    return [[top - (h + 1) * HOUR, 0, 0, 0, c] for h, c in sorted(closes_by_hours_ago.items(), reverse=True)]


class MoveTests(unittest.TestCase):
    def test_move_is_price_now_vs_the_close_24h_ago(self):
        rows = hourly({h: 100.0 for h in range(0, 27)} | {24: 95.0})
        self.assertAlmostEqual(fts.move_24h(rows, 100.0, NOW), (100 / 95 - 1) * 100)

    def test_no_candle_near_24h_ago_gives_no_move(self):
        self.assertIsNone(fts.move_24h(hourly({h: 100.0 for h in range(0, 10)}), 100.0, NOW))
        self.assertIsNone(fts.move_24h([], 100.0, NOW))


class WarningTests(unittest.TestCase):
    def test_parts(self):
        w = fts.risk_warning
        self.assertEqual(w(ftd.CRYPTO, "SOLUSD", "long", {"move": -5.24, "btc": -1}),
                         "⚠️ **SOL -5.2% in 24h · BTC downtrend**")
        self.assertEqual(w(ftd.CRYPTO, "SOLUSD", "short", {"move": 4.0, "btc": -1}), "⚠️ **SOL +4.0% in 24h**")
        self.assertEqual(w(ftd.CRYPTO, "SOLUSD", "short", {"move": 1.0, "btc": 1}), "⚠️ **BTC uptrend**")
        self.assertIsNone(w(ftd.CRYPTO, "SOLUSD", "long", {"move": 3.9, "btc": 1}))
        self.assertIsNone(w(ftd.CRYPTO, "SOLUSD", "long", {"move": None, "btc": None}))   # unknown never warns
        self.assertIsNone(w(ftd.NSE, "RELIANCE.NS", "long", {"move": -9.0, "btc": -1}))  # crypto only
        self.assertIsNone(w(ftd.CRYPTO, "SOLUSD", "long", None))

    def test_fib_and_touch_alerts_get_the_line_breaks_do_not(self):
        fib = {"key": "fib|X|4h|1|0|110|2", "d": 1, "zone": 2, "low": 100, "high": 101, "entry": 100.8,
               "sl": 100.7, "base": 90, "top": 110, "distance": 0.4,
               "plan": {"side": "long", "entry": 100.8, "sl": 100.7}}
        touch = {"key": "tl|X|4h|0|1|2", "kind": SUPPORT, "level": 100.0, "distance": 0.1,
                 "from": (90, "2026-08-06 00:00"), "to": (95, "2026-09-16 00:00"),
                 "plan": {"side": "long", "entry": 100.0, "sl": 99.0}}
        brk = {"key": "tlb|X|4h|1", "kind": SUPPORT, "close": 98.0, "level": 99.0, "closed_at": None}
        analysis = {"fib": [fib], "touch": [touch], "break": [brk], "price": 100.5,
                    "risk": {"move": -6.0, "btc": -1}}
        planned = fts.plan_alerts({}, ftd.CRYPTO, "SOLUSD", "4h", analysis, 0)
        by = {key.split("|")[0]: (message, record) for _, key, message, record in planned}
        for kind in ("fib", "tl"):
            message, record = by[kind]
            self.assertEqual(message.splitlines()[-1], "⚠️ **SOL -6.0% in 24h · BTC downtrend**")
            self.assertEqual(len(message.splitlines()), 4)
            self.assertEqual(record["warning"], "⚠️ **SOL -6.0% in 24h · BTC downtrend**")
        self.assertNotIn("in 24h", by["tlb"][0])

    def test_no_risk_no_line(self):
        fib = {"key": "fib|X|4h|1|0|110|2", "d": 1, "zone": 2, "low": 100, "high": 101, "entry": 100.8,
               "sl": 100.7, "base": 90, "top": 110, "distance": 0.4,
               "plan": {"side": "long", "entry": 100.8, "sl": 100.7}}
        (_, _, message, record), = fts.plan_alerts({}, ftd.CRYPTO, "SOLUSD", "4h",
                                                   {"fib": [fib], "touch": [], "break": [], "price": 100.5}, 0)
        self.assertEqual(len(message.splitlines()), 3)
        self.assertNotIn("warning", record)


if __name__ == "__main__":
    unittest.main()
