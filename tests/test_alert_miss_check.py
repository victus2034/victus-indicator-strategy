"""alert_miss_check: replay alerts with no live record are listed (lakky, 2026-11-23)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import alert_miss_check as amc

NOW = 1_795_400_000


def rec(symbol, kind="trendline", side="long", ts=NOW - 3 * 3600, broken=False, level=None):
    r = {"market": "crypto", "tf": "1d", "kind": kind, "symbol": symbol, "sent_ts": ts,
         "plan": {"side": side, "entry": 1.0, "sl": 0.9}}
    if broken:
        r["broken"] = True
    if level:
        r["level"] = level
    return r


class MissCheck(unittest.TestCase):
    def test_matches_on_coin_kind_side_and_day(self):
        records = [rec("SUIUSD"), rec("BTCUSD", side="short", broken=True), rec("ETHUSD", kind="fib", level="L3")]
        found = {"SUIUSD": [("TL touch", "long", NOW - 5 * 3600)],
                 "BTCUSD": [("TL BROKEN", "short", NOW - 4 * 3600), ("TL touch", "long", NOW - 4 * 3600)],
                 "ETHUSD": [("fib L3", "long", NOW - 3 * 3600), ("fib L4", "long", NOW - 3 * 3600)]}
        self.assertEqual(amc.misses(records, found),
                         [(NOW - 4 * 3600, "BTCUSD", "TL touch", "long"), (NOW - 3 * 3600, "ETHUSD", "fib L4", "long")])

    def test_records_filter_and_message(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [rec("SUIUSD"), {**rec("SUIUSD"), "tf": "4h"}, {**rec("SUIUSD"), "market": "nse"},
                    rec("SUIUSD", ts=NOW - 9 * 86400)]
            Path(d, "fib_trendline_alert_records.jsonl").write_text("\n".join(map(json.dumps, rows)) + "\n{torn")
            self.assertEqual(len(amc.load_records(d, NOW - 48 * 3600)), 1)
        text = amc.message([(NOW, "SUIUSD", "TL touch", "long")], 48)
        self.assertIn("`SUI` TL touch BUY", text)

    def test_posts_only_when_something_is_missed(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "fib_trendline_alert_records.jsonl").write_text(json.dumps(rec("SUIUSD", ts=NOW - 5 * 3600)) + "\n")
            with patch.object(amc.time, "time", return_value=NOW), \
                    patch.object(amc.config, "CRYPTO_WATCHLIST", ["SUIUSD"]), \
                    patch.object(amc.scanner, "send_discord_message", return_value=True) as send:
                with patch.object(amc, "replay_alerts", return_value=[("TL touch", "long", NOW - 5 * 3600)]):
                    amc.main([d])
                send.assert_not_called()
                with patch.object(amc, "replay_alerts", return_value=[("TL BROKEN", "short", NOW - 5 * 3600),
                                                                      ("TL BROKEN", "short", NOW - 600)]):
                    amc.main([d])
                send.assert_called_once()
                self.assertIn("1 1D crypto alert", send.call_args[0][0])      # the last hour is not a miss yet
