"""Fib + trendline alerts: the engines, the 0-0.75% band, trade scoring, replay and the once-only rules."""
import os
import pathlib
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

import fib_engine
import fib_trendline_backtest as ftb
import fib_trendline_data as ftd
import fib_trendline_scanner as fts
import fib_trendline_trades as ftt
from trendlines import RESISTANCE, SUPPORT, build_trendlines

REFERENCE = pathlib.Path(__file__).resolve().parents[2] / "indicator improvent by claude" / "fib_reference.py"
MARKER = "# ---- copied from fib_reference.py below this line ----\n"


class FibEngineIsTheIndicatorsTests(unittest.TestCase):
    @unittest.skipUnless(REFERENCE.exists(), "indicator folder is not beside this repo (CI)")
    def test_fib_engine_is_fib_reference_unchanged(self):
        ours = pathlib.Path(fib_engine.__file__).read_text(encoding="utf-8").split(MARKER, 1)[1]
        theirs = REFERENCE.read_text(encoding="utf-8")
        self.assertEqual(
            ours.replace("\r\n", "\n"), theirs.replace("\r\n", "\n"),
            "fib_reference.py changed - copy it into fib_engine.py below the marker again",
        )

    def test_levels_are_shivas_ex1_labels(self):
        self.assertEqual([round(v, 2) for v in fib_engine.levels(94.89, 110.55)], [105.23, 103.50, 101.94, 100.21])


def zones_by_number(d, base, top):
    return {z["zone"]: z for z in fts.fib_zones(d, base, top)}


class FibZoneNumberingTests(unittest.TestCase):
    def test_zone_2_is_the_lower_box_on_an_up_move(self):
        z = zones_by_number(1, 94.89, 110.55)
        self.assertLess(z[2]["high"], z[1]["low"])

    def test_zone_2_is_the_upper_box_on_a_down_move(self):
        z = zones_by_number(-1, 110.55, 94.89)
        self.assertGreater(z[2]["low"], z[1]["high"])

    def test_entry_and_sl_are_shivas_ex2_trades(self):
        # EX 2/278 ETH, fib 2562.8 -> 2806.6. His trades: entry 2723.94 / SL 2711.79 (zone 1),
        # 2672.86 / 2660.74 (zone 2) - entry at the zone top, SL on the inner 0.55 line.
        # (Read off his chart, so within 0.02% - fib_examples_check.py uses a tolerance too.)
        z = zones_by_number(1, 2562.8, 2806.6)
        got = (z[1]["entry"], z[1]["sl"], z[2]["entry"], z[2]["sl"])
        for g, want in zip(got, (2723.94, 2711.79, 2672.86, 2660.74)):
            self.assertLess(abs(g - want) / want, 0.0002)

    def test_short_entry_is_the_zone_bottom(self):
        z = zones_by_number(-1, 110.55, 94.89)[1]
        self.assertEqual(z["entry"], z["low"])
        self.assertGreater(z["sl"], z["entry"])


class DistanceBandTests(unittest.TestCase):
    """Shiva: alerts from 0.75% away down to 0.00% (1.5% at first)."""

    zone = {"low": 100.0, "high": 110.0}

    def test_long_fib_distance_is_down_to_the_zone_top(self):
        self.assertAlmostEqual(fts.fib_distance(1, self.zone, 111.1), 1.0)
        self.assertEqual(fts.fib_distance(1, self.zone, 105.0), 0.0)
        self.assertIsNone(fts.fib_distance(1, self.zone, 99.0))       # already past it

    def test_short_fib_distance_is_up_to_the_zone_bottom(self):
        self.assertAlmostEqual(fts.fib_distance(-1, self.zone, 99.0), 1.0)
        self.assertIsNone(fts.fib_distance(-1, self.zone, 111.0))

    def test_band_is_zero_to_three_quarters(self):
        self.assertTrue(fts.in_band(0.75))
        self.assertEqual(fts.FIB_TL_MAX_DISTANCE_PCT, 0.75)
        self.assertTrue(fts.in_band(0.0))
        self.assertFalse(fts.in_band(-0.4))         # through the line before the close: a break, not a BUY
        self.assertFalse(fts.in_band(0.76))
        self.assertFalse(fts.in_band(1.2))
        self.assertFalse(fts.in_band(None))

    def test_line_distance_is_on_the_approach_side(self):
        self.assertAlmostEqual(fts.line_distance(SUPPORT, 100.0, 101.0), 1.0)
        self.assertAlmostEqual(fts.line_distance(RESISTANCE, 100.0, 99.0), 1.0)


class CurrentPriceTests(unittest.TestCase):
    def test_every_timeframe_uses_the_freshest_candle(self):
        charts = {"4h": [[100, 0, 0, 0, 10.0], [200, 0, 0, 0, 11.0]],
                  "1d": [[50, 0, 0, 0, 9.0]],            # a lagging daily candle
                  "1M": [[10, 0, 0, 0, 8.0]]}
        self.assertEqual(fts.current_price(charts), 11.0)


class AlertTextTests(unittest.TestCase):
    def test_every_alert_names_its_timeframe_and_market(self):
        z = {**zones_by_number(1, 90, 110)[2], "d": 1, "base": 90, "top": 110, "distance": 0.8}
        z["plan"] = ftt.fib_plan(1, z)
        text = fts.format_fib_alert(ftd.NSE, "RELIANCE.NS", "4h", 100.0, z)
        self.assertIn("Timeframe: 4H | NSE", text)
        self.assertIn("RELIANCE | FIB LOWER ZONE | LONG", text)      # zone 2 of an up move
        self.assertIn(f"Lower zone: bottom {z['low']:.6f} - top {z['high']:.6f} (deeper)", text)
        self.assertIn(f"Entry: {z['high']:.6f} (zone top)", text)                # a long buys the top
        short = {**zones_by_number(-1, 110, 90)[1], "d": -1, "base": 110, "top": 90, "distance": 0.5}
        short["plan"] = ftt.fib_plan(-1, short)
        self.assertIn(f"Entry: {short['low']:.6f} (zone bottom)",
                      fts.format_fib_alert(ftd.CRYPTO, "BTCUSD", "1d", 95.0, short))   # a short sells the bottom
        self.assertIn("0.80% away", text)
        t = {"kind": SUPPORT, "level": 100.0, "distance": 1.2, "from": (90, "a"), "to": (95, "b"),
             "plan": ftt.trendline_plan(True, 100.0, "1d")}
        text = fts.format_touch_alert(ftd.CRYPTO, "BTCUSD", "1d", 101.2, t)
        self.assertIn("Timeframe: 1D | Crypto", text)
        self.assertIn("SL: 98.500000 | 1.50%", text)
        self.assertIn("BTC | SUP TL | BUY", text)

    def test_zone_names_follow_the_chart(self):
        self.assertEqual([fts.zone_name(1, 1), fts.zone_name(1, 2)], ["UPPER", "LOWER"])
        self.assertEqual([fts.zone_name(-1, 1), fts.zone_name(-1, 2)], ["LOWER", "UPPER"])
        for d, base, top in ((1, 90, 110), (-1, 110, 90)):
            z = zones_by_number(d, base, top)
            upper = 1 if fts.zone_name(d, 1) == "UPPER" else 2
            self.assertGreater(z[upper]["low"], z[3 - upper]["high"])     # "UPPER" really is higher

    def test_broken_line_wording(self):
        b = {"kind": RESISTANCE, "level": 100.0, "close": 101.0, "time": "t", "from": (90, "a"), "to": (95, "b")}
        self.assertIn("ETH | RES TL BR", fts.format_break_alert(ftd.CRYPTO, "ETHUSD", "4h", b))


def rising_lows_then_break():
    """Two swing lows at 100 and 110, higher prices between, then a close under the line."""
    lows = [130.0] * 60
    lows[10] = 100.0
    lows[35] = 110.0
    highs = [v + 5 for v in lows]
    closes = [v + 2 for v in lows]
    return highs, lows, closes


class TrendlineTests(unittest.TestCase):
    def test_two_rising_swing_lows_make_a_support_line(self):
        highs, lows, closes = rising_lows_then_break()
        lines = [l for l in build_trendlines(highs, lows, closes, 10, 6) if l.kind == SUPPORT]
        self.assertEqual([(l.x1, l.y1, l.x2, l.y2) for l in lines], [(10, 100.0, 35, 110.0)])
        self.assertTrue(lines[0].alive)
        self.assertEqual(lines[0].created, 45)

    def test_a_close_through_ends_the_line(self):
        highs, lows, closes = rising_lows_then_break()
        closes[50] = 100.0            # line is at 116 by bar 50
        line = [l for l in build_trendlines(highs, lows, closes, 10, 6) if l.kind == SUPPORT][0]
        self.assertEqual(line.broken_at, 50)
        self.assertTrue(line.live_during(50))       # still on the chart while bar 50 forms
        self.assertFalse(line.live_during(51))
        self.assertFalse(line.live_during(45))      # drawn at bar 45's close

    def test_a_close_before_the_line_is_drawn_is_not_checked(self):
        highs, lows, closes = rising_lows_then_break()
        closes[40] = 90.0             # between swing (35) and confirm (45) - the Pine never looks
        line = [l for l in build_trendlines(highs, lows, closes, 10, 6) if l.kind == SUPPORT][0]
        self.assertTrue(line.alive)

    def test_falling_swing_highs_make_a_resistance_line(self):
        highs = [100.0] * 60
        highs[10], highs[35] = 150.0, 140.0
        lows = [v - 5 for v in highs]
        lines = build_trendlines(highs, lows, [v - 2 for v in highs], 10, 6)
        self.assertEqual([(l.kind, l.y1, l.y2) for l in lines], [(RESISTANCE, 150.0, 140.0)])

    def test_history_keeps_lines_pushed_out_by_newer_ones(self):
        lows = [200.0] * 200
        for k, i in enumerate(range(10, 190, 12)):
            lows[i] = 100.0 + k       # rising swing lows: a new support line on each
        highs = [v + 5 for v in lows]
        closes = [v + 50 for v in lows]
        kept = build_trendlines(highs, lows, closes, 5, 3)
        everything = build_trendlines(highs, lows, closes, 5, 3, history=True)
        self.assertEqual(len([l for l in kept if l.kind == SUPPORT]), 3)
        self.assertGreater(len(everything), len(kept))
        self.assertTrue(all(l.trimmed_at is not None for l in everything if l not in kept))


class CandleTests(unittest.TestCase):
    def test_monthly_candles_group_by_calendar_month(self):
        day = lambda y, m, d: int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())
        daily = [[day(2026, 8, 30), 1, 5, 1, 2], [day(2026, 8, 31), 2, 6, 0.5, 3], [day(2026, 9, 1), 3, 4, 2, 3.5]]
        months = ftd.monthly_from_daily(daily)
        self.assertEqual(months[0], [day(2026, 8, 1), 1, 6, 0.5, 3])
        self.assertEqual(months[1], [day(2026, 9, 1), 3, 4, 2, 3.5])

    def test_the_current_month_is_still_forming(self):
        sept = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp())
        self.assertFalse(ftd.candle_is_closed(ftd.CRYPTO, sept, "1M", datetime(2026, 9, 29, tzinfo=timezone.utc).timestamp()))
        self.assertTrue(ftd.candle_is_closed(ftd.CRYPTO, sept, "1M", datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp()))

    def test_nse_candles_close_with_the_session(self):
        at = lambda h, m: datetime(2026, 9, 29, h, m, tzinfo=ftd.IST).timestamp()
        # the 13:15 4h candle ends at the 15:30 close, not 17:15
        self.assertTrue(ftd.candle_is_closed(ftd.NSE, int(at(13, 15)), "4h", at(15, 31)))
        self.assertFalse(ftd.candle_is_closed(ftd.NSE, int(at(13, 15)), "4h", at(15, 0)))
        self.assertFalse(ftd.candle_is_closed(ftd.NSE, int(at(0, 0)), "1d", at(14, 0)))


class SimulateTests(unittest.TestCase):
    plan = {"side": "long", "entry": 100.0, "sl": 99.0}

    def run_bars(self, *bars, tf="30m"):
        candles = [[1000 + 300 * (k + 1), 0, h, l, 0] for k, (h, l) in enumerate(bars)]
        return ftt.simulate(self.plan, ftd.CRYPTO, tf, 1000, candles)

    def test_fill_then_two_r(self):
        r = self.run_bars((101, 99.9), (101.5, 100.2), (102.1, 101))
        self.assertEqual((r["outcome"], r["r1"], r["r2"]), ("2R", True, True))

    def test_sl_before_1r(self):
        self.assertEqual(self.run_bars((101, 99.9), (100.5, 98.9))["outcome"], "SL")

    def test_one_r_then_stop_is_1r_with_the_stop_counted(self):
        r = self.run_bars((100.5, 99.9), (101.2, 100.1), (100.5, 98.8))
        self.assertEqual((r["outcome"], r["r1"], r["sl"]), ("1R", True, True))

    def test_a_candle_with_both_is_the_stop(self):
        r = self.run_bars((100.5, 99.9), (102.5, 98.5))
        self.assertEqual((r["outcome"], r["ambiguous"]), ("SL", True))

    def test_no_fill_after_the_wait(self):
        bars = [(102, 101)] * 31      # 5 x 30m = 30 five-minute candles
        self.assertEqual(self.run_bars(*bars)["outcome"], "no fill")
        self.assertEqual(self.run_bars(*bars[:30])["outcome"], "open")

    def test_nse_holds_count_trading_candles_not_the_night(self):
        # 20 x 30m hold = 120 five-minute candles, however many hours apart they are
        plan = {"side": "long", "entry": 100.0, "sl": 99.0}
        candles = [[1000 + 86400 * k, 0, 100.5, 99.5 if k == 1 else 100.1, 0] for k in range(1, 100)]
        self.assertEqual(ftt.simulate(plan, ftd.NSE, "30m", 1000, candles)["outcome"], "open")
        candles += [[1000 + 86400 * k, 0, 100.5, 100.1, 0] for k in range(100, 130)]
        self.assertEqual(ftt.simulate(plan, ftd.NSE, "30m", 1000, candles)["outcome"], "timeout")

    def test_candles_up_to_the_alert_are_ignored(self):
        candles = [[1000, 0, 101, 99.5, 0], [1300, 0, 101, 100.5, 0]]
        self.assertFalse(ftt.simulate(self.plan, ftd.CRYPTO, "30m", 1000, candles)["filled"])

    def test_summary_counts_and_costs(self):
        trades = [
            {"market": ftd.CRYPTO, "kind": "fib", "tf": "4h", "plan": self.plan,
             "result": {"outcome": o, "filled": True, "r1": o in ("1R", "2R"), "r2": o == "2R", "sl": o == "SL"}}
            for o in ("SL", "1R", "2R", "2R")
        ]
        row = ftt.summarise(trades)[0]
        self.assertEqual((row["SL"], row["1R"], row["2R"]), (1, 1, 2))
        self.assertAlmostEqual(row["win_1r"], 0.75)
        self.assertAlmostEqual(row["win_2r"], 2 / 3)
        self.assertAlmostEqual(row["net_r_1r"], (1 + 1 + 1 - 1) / 4 - 0.1)   # 0.10% cost on a 1% risk


class ReplayTests(unittest.TestCase):
    def test_a_support_line_alerts_once_and_scores(self):
        # 4h bars; swing lows 100 (bar 10) and 110 (bar 35) -> support rising 0.4 a bar.
        highs, lows, closes = rising_lows_then_break()
        n = len(lows)
        t0 = int(datetime(2026, 1, 1, 12, tzinfo=ftd.IST).timestamp())
        base = [[t0 + i * 14400, closes[i], highs[i], lows[i], closes[i]] for i in range(n)]
        # line at bar 50 is 116: price dips to it, then rallies
        base[50][3] = 116.5
        evalc = []
        for i, b in enumerate(base):
            for k in range(4):        # 1h evaluation candles
                evalc.append([b[0] + k * 3600, b[1], b[2], b[3], b[4]])
        now = base[-1][0] + 10 * 14400
        out = ftb.replay(ftd.NSE, "X.NS", "4h", base, evalc, now)
        touches = [t for t in out if t["kind"] == "trendline"]
        self.assertTrue(touches)
        self.assertEqual(len({t["alert_ts"] // 14400 for t in touches}), len(touches))   # one per band entry
        self.assertTrue(all(t["plan"]["side"] == "long" for t in touches))


class OnceOnlyTests(unittest.TestCase):
    def fib(self, key="fib|X|4h|1|0|110|2"):
        return {"key": key, "d": 1, "zone": 2, "low": 100, "high": 101, "entry": 100.8, "sl": 100.7,
                "base": 90, "top": 110, "distance": 0.4, "plan": {"side": "long", "entry": 100.8, "sl": 100.7}}

    def touch(self, key="tl|X|4h|0|1|2"):
        return {"key": key, "kind": SUPPORT, "level": 100.0, "distance": 0.1, "from": (90, "a"), "to": (95, "b"),
                "plan": {"side": "long", "entry": 100.0, "sl": 99.0}}

    def analysis(self, fib=(), touch=()):
        return {"fib": list(fib), "touch": list(touch), "break": [], "price": 100.5}

    def plan(self, state, analysis, now):
        return fts.plan_alerts(state, ftd.CRYPTO, "X", "4h", analysis, now)

    def test_a_fib_zone_alerts_once(self):
        state = {}
        first = self.plan(state, self.analysis(fib=[self.fib()]), 0)
        self.assertEqual(len(first), 1)
        fts.mark_sent(state, first[0][1], 0)
        self.assertEqual(self.plan(state, self.analysis(fib=[self.fib()]), 10**6), [])

    def test_fib_and_trendline_go_to_different_channels(self):
        planned = self.plan({}, self.analysis(fib=[self.fib()], touch=[self.touch()]), 0)
        self.assertEqual(sorted(c for c, *_ in planned), ["fib", "trendline"])

    def test_alerts_carry_a_record_to_score(self):
        (_, _, _, record), = self.plan({}, self.analysis(fib=[self.fib()]), 0)
        self.assertEqual((record["kind"], record["tf"], record["plan"]["sl"]), ("fib", "4h", 100.7))

    def test_a_touch_rearms_only_after_leaving_the_band_and_a_candle(self):
        state = {}
        (_, key, _, _), = self.plan(state, self.analysis(touch=[self.touch()]), 0)
        fts.mark_sent(state, key, 0)
        self.assertEqual(self.plan(state, self.analysis(touch=[self.touch()]), 20000), [])
        self.plan(state, self.analysis(), 100)
        self.assertEqual(self.plan(state, self.analysis(touch=[self.touch()]), 200), [])
        self.plan(state, self.analysis(), 20000)
        self.assertEqual(len(self.plan(state, self.analysis(touch=[self.touch()]), 20001)), 1)


class SeedingTests(unittest.TestCase):
    """A channel's first pass under a rule, per market, seeds silently; before a webhook nothing is recorded."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sent, self.status = [], []
        self.fibs = [OnceOnlyTests().fib("fib|X|4h|1|0|110|2")]
        self.touches = [OnceOnlyTests().touch("tl|X|4h|0|1|2")]
        tmp = pathlib.Path(self.tmp.name)
        analysis = lambda: {"4h": {"fib": list(self.fibs), "touch": list(self.touches), "break": [], "price": 100.5}}
        patches = [
            mock.patch.object(fts, "STATE_FILE", tmp / "state.json"),
            mock.patch.object(fts, "RECORDS_FILE", tmp / "records.jsonl"),
            mock.patch.object(fts, "scan_crypto", lambda tfs, now: [("X", analysis(), None)]),
            mock.patch.object(fts, "nse_session_open", lambda now: False),
            mock.patch.object(fts.scanner, "in_alert_window", lambda: True),
            mock.patch.object(fts.scanner, "send_discord_message",
                              lambda message, webhook_env_name, webhook_config_value: self.sent.append(webhook_env_name) or True),
            mock.patch.object(fts.scanner, "send_status_message", self.status.append),
            mock.patch("fib_trendline_daily_report.maybe_send", lambda state, now: None),
            mock.patch.dict(os.environ, {fts.FIB_ENV: "https://example.invalid/fib", fts.TL_ENV: ""}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_seeds_each_channel_only_once_its_webhook_exists(self):
        fts.run_once()
        self.assertEqual(self.sent, [])                                  # fib seeded, not posted
        self.assertEqual(len(self.status), 1)
        self.assertNotIn(self.touches[0]["key"], fts.load_state())      # no webhook: nothing recorded

        self.fibs.append(OnceOnlyTests().fib("fib|X|4h|1|0|120|1"))     # a new fib zone
        fts.run_once()
        self.assertEqual(self.sent, [fts.FIB_ENV])
        self.assertEqual(len(fts.RECORDS_FILE.read_text().splitlines()), 1)   # recorded for the daily report

        os.environ[fts.TL_ENV] = "https://example.invalid/tl"           # trendline webhook added later
        fts.run_once()
        self.assertEqual(self.sent, [fts.FIB_ENV])                      # seeded, still no burst
        self.assertIn(self.touches[0]["key"], fts.load_state())
        self.assertEqual(len(self.status), 2)

    def test_a_failing_daily_report_cannot_lose_the_alerts_it_follows(self):
        fts.run_once()                                                   # seed
        self.fibs.append(OnceOnlyTests().fib("fib|X|4h|1|0|130|1"))
        with mock.patch("fib_trendline_daily_report.maybe_send", side_effect=RuntimeError("boom")):
            fts.run_once()                                               # must not raise
        self.assertIn("fib|X|4h|1|0|130|1", fts.load_state())             # the sent alert is saved
        fts.run_once()
        self.assertEqual(self.sent, [fts.FIB_ENV])                       # and never sent twice

    def test_a_new_rule_version_reseeds(self):
        fts.run_once()
        state = fts.load_state()
        self.assertIn(f"fib:crypto:{fts.SEED_VERSION}", state[fts.SEEDED_KEY])


class DailyReportTests(unittest.TestCase):
    def setUp(self):
        import fib_trendline_daily_report as report

        self.report = report
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = pathlib.Path(self.tmp.name)
        for p in (mock.patch.object(report, "RECORDS_FILE", tmp / "records.jsonl"),
                  mock.patch.object(report, "RESULTS_FILE", tmp / "results.json")):
            p.start()
            self.addCleanup(p.stop)
        self.sent_ts = int(datetime(2026, 9, 29, 10, 0, tzinfo=ftd.IST).timestamp())
        record = {"id": "a", "market": ftd.CRYPTO, "symbol": "BTCUSD", "tf": "30m", "kind": "fib", "zone": 2,
                  "sent_ts": self.sent_ts, "plan": {"side": "long", "entry": 100.0, "sl": 99.0}}
        report.RECORDS_FILE.write_text(__import__("json").dumps(record) + "\n")
        self.candles = [[self.sent_ts + 300, 0, 100.5, 99.9, 0], [self.sent_ts + 600, 0, 102.2, 100.1, 0]]

    def test_scores_yesterdays_alerts_and_keeps_final_results(self):
        with mock.patch.object(self.report, "eval_candles", lambda *a: self.candles) as _:
            text = self.report.run(datetime(2026, 9, 29).date(), self.sent_ts + 86400)
        self.assertIn("FIB BACKTEST · 29 SEP 2026", text)
        self.assertIn("Alerts 1 · Entries 1\n+2R 1\nWin rate 100.0%", text)
        self.assertIn("30m CRYPTO - Alerts 1 | Entries 1 | +2R 1 | 100.0%", text)
        self.assertIn("10:00 - Alerts 1 | Entries 1 | +2R 1 | 100.0%", text)
        self.assertIn("Lower zone - Alerts 1", text)     # zone 2 on a long, named as the alert names it
        self.assertNotIn("TRENDLINE", text)
        self.assertTrue(self.report.load_results()["a"]["resolved"])
        with mock.patch.object(self.report, "eval_candles", side_effect=AssertionError("re-scored")):
            self.report.run(datetime(2026, 9, 29).date(), self.sent_ts + 2 * 86400)

    def test_posts_once_a_day_after_eight(self):
        state = {}
        calls = []
        at = lambda h: datetime(2026, 9, 30, h, 0, tzinfo=ftd.IST).timestamp()
        with mock.patch.object(self.report, "run", lambda day, now, send: calls.append(day)), \
                mock.patch.dict(os.environ, {self.report.WEBHOOK_ENV: "https://example.invalid/bt"}):
            self.report.maybe_send(state, at(7))
            self.report.maybe_send(state, at(9))
            self.report.maybe_send(state, at(12))
        self.assertEqual(calls, [datetime(2026, 9, 29).date()])


if __name__ == "__main__":
    unittest.main()


class FailedSendBackoffTests(unittest.TestCase):
    """A failed Discord send must back off, yet still alert once Discord is back."""

    def run_pass(self, state, sent_ok, now):
        analysis = {"price": 100.0, "fib": [], "touch": [], "break": [
            {"key": "brk|X|4h|1", "kind": SUPPORT}]}
        with mock.patch.object(fts, "load_state", return_value=state), \
             mock.patch.object(fts, "save_state"), \
             mock.patch.object(fts, "scan_crypto", return_value=[("X", {"4h": analysis}, None)]), \
             mock.patch.object(fts, "plan_alerts", wraps=fts.plan_alerts), \
             mock.patch.object(fts, "format_break_alert", return_value="msg"), \
             mock.patch.object(fts, "send", return_value=sent_ok) as send, \
             mock.patch.object(fts.scanner, "get_env_or_config", return_value="http://hook"), \
             mock.patch.object(fts.scanner, "in_alert_window", return_value=True), \
             mock.patch.object(fts.scanner, "send_status_message"), \
             mock.patch.object(fts.time, "time", return_value=now), \
             mock.patch.dict("sys.modules", {"fib_trendline_daily_report": mock.MagicMock()}):
            fts.run_once()
        return send.call_count

    def test_failure_backs_off_then_retries_and_never_suppresses(self):
        seeded = {f"{c}:{m}:{fts.SEED_VERSION}": 1 for c in ("fib", "trendline") for m in (fts.CRYPTO, fts.NSE)}
        state = {fts.SEEDED_KEY: seeded}
        t = 1_000_000.0
        self.assertEqual(self.run_pass(state, False, t), 1)
        self.assertNotIn("brk|X|4h|1", state)                     # still alertable
        self.assertEqual(self.run_pass(state, False, t + 60), 0)  # backed off
        later = t + fts.RETRY_BACKOFF_SECONDS + 1
        self.assertEqual(self.run_pass(state, True, later), 1)    # retried, delivered
        self.assertIn("brk|X|4h|1", state)
        self.assertEqual(self.run_pass(state, True, later + 60), 0)


class DailyReportFetchFailureTests(unittest.TestCase):
    def test_failed_download_keeps_the_alert_in_the_tally_as_open(self):
        import fib_trendline_daily_report as fdr
        record = {"id": "a", "market": fts.CRYPTO, "symbol": "X", "tf": "4h", "sent_ts": 1_000_000,
                  "plan": {"side": "long", "entry": 1.0, "sl": 0.9}}
        with mock.patch.object(fdr, "eval_candles", side_effect=RuntimeError("down")):
            results = fdr.score([record], {}, 2_000_000)
        self.assertEqual(results["a"]["outcome"], "open")
        self.assertFalse(results["a"]["resolved"])


class AtomicStateWriteTests(unittest.TestCase):
    def test_a_crash_mid_write_leaves_the_old_state_intact(self):
        import scanner
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "alert_state.json"
            with mock.patch.object(scanner, "STATE_FILE", path):
                scanner.save_state({"a": 1})
                with mock.patch.object(scanner.json, "dump", side_effect=RuntimeError("killed")):
                    with self.assertRaises(RuntimeError):
                        scanner.save_state({"a": 2})
                self.assertEqual(scanner.load_state(), {"a": 1})
