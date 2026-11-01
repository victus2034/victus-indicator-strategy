"""Weekly audit, 2026-11-01: bad candles, torn record lines, an all-failed pass."""
import json
import math
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import fib_trendline_daily_report as fdr
import fib_trendline_scanner as fts
import nse_scanner
import scanner

NOW = 1_793_500_000


def walk(n, tf=86400, seed=1):
    rng = random.Random(seed)
    price, t, out = 100.0, NOW - n * tf, []
    for _ in range(n):
        o = price
        c = price * (1 + rng.gauss(0, 0.02))
        h = max(o, c) * (1 + abs(rng.gauss(0, 0.01)))
        l = min(o, c) * (1 - abs(rng.gauss(0, 0.01)))
        out.append([t, o, h, l, c])
        price, t = c, t + tf
    return out


class CleanCandlesTests(unittest.TestCase):
    def test_bad_rows_dropped_and_good_rows_unchanged(self):
        good = [[1, 10, 11, 9, 10.5], [2, 10.5, 12, 10, 11]]
        rows = [good[1], [3, 0, 0, 0, 0], [4, 1, float("nan"), 1, 1], [5, -1, 1, 1, 1],
                [6, None, 1, 1, 1], [7, 1, 1], good[0]]
        self.assertEqual(scanner.clean_candles(rows), good)

    def test_high_low_cover_open_close_and_one_row_per_time(self):
        rows = [[1, 10, 9, 11, 10.5, 7.0], [1, 10, 12, 9, 11, 8.0]]
        self.assertEqual(scanner.clean_candles([[1, 10, 9, 11, 10.5, 7.0]]), [[1, 10, 11, 9, 10.5, 7.0]])
        self.assertEqual(scanner.clean_candles(rows), [[1, 10, 12, 9, 11, 8.0]])   # later copy wins

    def test_a_zero_candle_no_longer_skips_the_symbol(self):
        base = walk(600)
        broken = [list(c) for c in base]
        broken[400] = [base[400][0], 0, 0, 0, 0]
        for tf in ("1d", "1w", "1M"):
            want = fts.analyse(fts.CRYPTO, "BTCUSD", tf, base[:400] + base[401:], NOW)
            got = fts.analyse(fts.CRYPTO, "BTCUSD", tf, broken, NOW)     # raised ZeroDivisionError
            self.assertEqual(json.dumps(got, sort_keys=True), json.dumps(want, sort_keys=True))

    def test_nan_rows_do_not_reach_the_engines(self):
        base = walk(600)
        broken = [list(c) for c in base]
        broken[550][2] = float("nan")
        got = fts.analyse(fts.NSE, "X.NS", "1d", broken, NOW)
        self.assertEqual(got["bars"], fts.analyse(fts.NSE, "X.NS", "1d", base[:550] + base[551:], NOW)["bars"])
        for alert in got["fib"] + got["touch"]:
            self.assertTrue(all(math.isfinite(v) for v in (alert["plan"]["entry"], alert["plan"]["sl"])))

    def test_a_zero_low_in_the_sweep_is_not_a_wick(self):
        rows = [[100, 10, 10.2, 9.9, 10.1], [160, 10.1, 10.3, 0, 10.2]]
        self.assertEqual(fts.swept_since(rows, 50), (9.9, 10.2))

    def test_nse_zone_scanner_drops_zero_prints(self):
        index = pd.date_range("2026-01-01", periods=400, freq="D")
        rows = walk(400)
        frame = pd.DataFrame([[o, h, l, c, 1000] for _, o, h, l, c in rows], index=index,
                             columns=["Open", "High", "Low", "Close", "Volume"])
        frame.iloc[200] = [0, 0, 0, 0, 0]
        with mock.patch.object(nse_scanner, "resample_for_timeframe", side_effect=lambda d: d):
            data = nse_scanner.prepare_ohlcv(frame)
        self.assertTrue((data[["open", "high", "low", "close"]] > 0).all().all())


class RecordFileTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "records.jsonl"
        self.addCleanup(self.dir.cleanup)

    def test_append_after_a_torn_line_keeps_the_new_record(self):
        good = {"id": "a", "market": fts.CRYPTO, "symbol": "X", "tf": "4h", "sent_ts": 1,
                "plan": {"side": "long", "entry": 1.0, "sl": 0.9}}
        self.path.write_text(json.dumps(good) + "\n" + '{"id": "torn", "plan": {"si', encoding="utf-8")
        with mock.patch.object(fts, "RECORDS_FILE", self.path):
            fts.append_record({"market": fts.CRYPTO, "symbol": "Y", "tf": "4h",
                               "plan": {"side": "short", "entry": 2.0, "sl": 2.1}}, "k", 5)
            fts.append_record({"market": fts.CRYPTO, "symbol": "Z", "tf": "4h",
                               "plan": {"side": "short", "entry": 2.0, "sl": 2.1}}, "k2", 6)
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 4)                                   # no extra blank line after a clean one
        with mock.patch.object(fdr, "RECORDS_FILE", self.path):
            records = fdr.load_records()                                  # raised JSONDecodeError
        self.assertEqual([r.get("symbol") for r in records], ["X", "Y", "Z"])

    def test_score_skips_a_record_without_a_plan(self):
        good = {"id": "a", "market": fts.CRYPTO, "symbol": "X", "tf": "4h", "sent_ts": 1_000_000,
                "plan": {"side": "long", "entry": 1.0, "sl": 0.9}}
        bad = [dict(good, id="b", plan=None), dict(good, id="c", tf="2h"), dict(good, id="d", market="fx"),
               {k: v for k, v in good.items() if k != "sent_ts"} | {"id": "e"},
               dict(good, id="f", plan={"side": "long", "entry": "x", "sl": 0.9})]
        with mock.patch.object(fdr, "eval_candles", side_effect=RuntimeError("down")):
            results = fdr.score([good] + bad, {}, 2_000_000)
        self.assertEqual(sorted(results), ["a"])


class AllFailedPassTests(unittest.TestCase):
    """A pass where every chart failed must not count as a scan for the break freshness."""

    def run_pass(self, state, results, now):
        with mock.patch.object(fts, "load_state", return_value=state), \
             mock.patch.object(fts, "save_state"), \
             mock.patch.object(fts, "scan_crypto", return_value=results), \
             mock.patch.object(fts, "send", return_value=True), \
             mock.patch.object(fts.scanner, "get_env_or_config", return_value="http://hook"), \
             mock.patch.object(fts.scanner, "in_alert_window", return_value=True), \
             mock.patch.object(fts.scanner, "send_status_message"), \
             mock.patch.object(fts.time, "time", return_value=now), \
             mock.patch.dict("sys.modules", {"fib_trendline_daily_report": mock.MagicMock()}):
            fts.run_once()

    def test_outage_keeps_the_last_good_scan_time(self):
        seeded = {f"{c}:{m}:{fts.SEED_VERSION}": 1 for c in fts.CHANNELS for m in (fts.CRYPTO, fts.NSE)}
        state = {fts.SEEDED_KEY: seeded}
        empty = {"price": 1.0, "fib": [], "touch": [], "break": [], "zone": []}
        self.run_pass(state, [("X", {"4h": empty}, None)], 1_000_000)
        self.assertEqual(state[fts.LAST_SCAN_KEY][fts.CRYPTO], 1_000_000)
        with self.assertRaises(RuntimeError):            # the job still fails loudly, state saved first
            self.run_pass(state, [("X", None, "down"), ("Y", None, "down")], 1_009_000)
        self.assertEqual(state[fts.LAST_SCAN_KEY][fts.CRYPTO], 1_000_000)
        self.run_pass(state, [("X", None, "down"), ("Y", {"4h": empty}, None)], 1_018_000)
        self.assertEqual(state[fts.LAST_SCAN_KEY][fts.CRYPTO], 1_018_000)


if __name__ == "__main__":
    unittest.main()
