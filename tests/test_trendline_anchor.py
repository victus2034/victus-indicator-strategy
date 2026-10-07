"""v12.5 trendlines (Lakky, 2026-10-07): a line only between rising swing lows /
falling swing highs, starting at the candle it rests on.

Two halves, like the zone parity tests:
- HYPEUSDT 1D on Bitunix (real candles, tests/fixtures): the support Lakky drew
  by hand, Aug 19 58.039 -> Sep 15 75.132, is the line we draw; Aug 2 51.111
  (the v12.4 anchor) gets none.
- pine_6b() below is a bar-by-bar transcription of Shiva_Indicator_v12.5.pine
  section 6b, written from the Pine and not from trendlines.py. Both must draw
  the same lines on real and generated candles.
"""
import csv
import random
import unittest
from datetime import datetime, timezone
from pathlib import Path

from trendlines import SUPPORT, build_trendlines

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name):
    with open(FIXTURES / name) as f:
        rows = list(csv.DictReader(f))
    return ([int(r["time"]) for r in rows], [float(r["high"]) for r in rows],
            [float(r["low"]) for r in rows], [float(r["close"]) for r in rows])


def day(ts):
    ts = ts / 1000 if ts > 1e11 else ts
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def pine_6b(highs, lows, closes, tl_len=10, tl_keep=6):
    """Shiva_Indicator_v12.5.pine section 6b, statement by statement."""
    def pivot(src, i, high):
        # ta.pivothigh/low(src, tl_len, tl_len) on bar i: the bar tl_len back,
        # strictly beyond every bar tl_len either side of it
        c = i - tl_len
        if c - tl_len < 0:
            return None
        for j in range(c - tl_len, c + tl_len + 1):
            if j != c and ((src[j] >= src[c]) if high else (src[j] <= src[c])):
                return None
        return src[c]

    plX, plY, phX, phY = [], [], [], []
    tl = []        # [kind, x1, y1, x2, y2, alive, broken_at]
    drawn = []

    def f_tl_add(kind, x1, y1, x2, y2):
        rec = [kind, x1, y1, x2, y2, True, None]
        tl.append(rec)
        drawn.append(rec)
        cnt = 0
        for i in range(len(tl) - 1, -1, -1):
            if tl[i][0] == kind:
                cnt += 1
                if cnt > tl_keep:
                    del tl[i]

    for bar_index in range(len(closes)):
        def series(src, off):
            return src[bar_index - off]

        tl_pl = pivot(lows, bar_index, False)
        tl_ph = pivot(highs, bar_index, True)
        if tl_pl is not None:
            nx = bar_index - tl_len
            n = len(plX)
            bx, by = -1, 0.0
            if n > 0 and plY[n - 1] < tl_pl:
                bs = 0.0
                for k in range(max(plX[n - 1], bar_index - 499), nx - 1 + 1):
                    tv = series(lows, bar_index - k)
                    ts = (tl_pl - tv) / (nx - k)
                    if bx < 0 or ts > bs:
                        bx, by, bs = k, tv, ts
            if bx >= 0:
                f_tl_add(0, bx, by, nx, tl_pl)
            plX.append(nx)
            plY.append(tl_pl)
            if len(plX) > 30:
                plX.pop(0)
                plY.pop(0)
        if tl_ph is not None:
            nx = bar_index - tl_len
            n = len(phX)
            bx, by = -1, 0.0
            if n > 0 and phY[n - 1] > tl_ph:
                bs = 0.0
                for k in range(max(phX[n - 1], bar_index - 499), nx - 1 + 1):
                    tv = series(highs, bar_index - k)
                    ts = (tl_ph - tv) / (nx - k)
                    if bx < 0 or ts < bs:
                        bx, by, bs = k, tv, ts
            if bx >= 0:
                f_tl_add(1, bx, by, nx, tl_ph)
            phX.append(nx)
            phY.append(tl_ph)
            if len(phX) > 30:
                phX.pop(0)
                phY.pop(0)
        for rec in tl:
            if rec[5] and bar_index > rec[3]:
                yb = rec[2] + (rec[4] - rec[2]) * (bar_index - rec[1]) / (rec[3] - rec[1])
                if (closes[bar_index] < yb) if rec[0] == 0 else (closes[bar_index] > yb):
                    rec[5] = False
                    rec[6] = bar_index
    return drawn


def as_tuples(lines):
    return [(l.kind, l.x1, l.y1, l.x2, l.y2, l.broken_at) for l in lines]


class HypeDailyTests(unittest.TestCase):
    def setUp(self):
        self.t, self.h, self.l, self.c = load("hype_usdt_1d_bitunix_300.csv")
        self.lines = build_trendlines(self.h, self.l, self.c, 10, 6, history=True)

    def test_lakkys_line_aug19_to_sep15(self):
        sup = [l for l in self.lines if l.kind == SUPPORT and day(self.t[l.x2]) == "2026-09-15"]
        self.assertEqual(len(sup), 1)
        self.assertEqual((day(self.t[sup[0].x1]), sup[0].y1, sup[0].y2),
                         ("2026-08-19", 58.039, 75.132))
        self.assertTrue(sup[0].alive)

    def test_a_lower_swing_low_draws_nothing(self):
        # Aug 2 (51.111) is under the Jun 25 swing low (58.52): no line ends there
        self.assertFalse([l for l in self.lines if day(self.t[l.x2]) == "2026-08-02"])
        self.assertFalse([l for l in self.lines if day(self.t[l.x1]) == "2026-08-02"])

    def test_no_candle_between_the_ends_is_through_the_line(self):
        for line in self.lines:
            for k in range(line.x1, line.x2 + 1):
                y = line.price_at(k)
                if line.kind == SUPPORT:
                    self.assertGreaterEqual(self.l[k], y - 1e-9)
                else:
                    self.assertLessEqual(self.h[k], y + 1e-9)


class PineParityTests(unittest.TestCase):
    def check(self, highs, lows, closes, length=10, keep=6):
        ours = as_tuples(build_trendlines(highs, lows, closes, length, keep, history=True))
        pine = [tuple(r[:5]) + (r[6],) for r in pine_6b(highs, lows, closes, length, keep)]
        self.assertEqual(ours, pine)
        return ours

    def test_hype_daily(self):
        _, h, l, c = load("hype_usdt_1d_bitunix_300.csv")
        self.assertTrue(self.check(h, l, c))

    def test_coti_30m(self):
        _, h, l, c = load("coti_usdt_30m_800.csv")
        self.assertTrue(self.check(h, l, c))

    def test_random_walks_with_far_apart_swings(self):
        rng = random.Random(7)
        total = 0
        for run in range(30):
            price, highs, lows, closes = 100.0, [], [], []
            drift = rng.choice([0.0, 0.002, -0.002])
            for _ in range(1500):
                price *= 1 + drift + rng.gauss(0, 0.01)
                o, c = price, price * (1 + rng.gauss(0, 0.005))
                highs.append(max(o, c) * (1 + abs(rng.gauss(0, 0.004))))
                lows.append(min(o, c) * (1 - abs(rng.gauss(0, 0.004))))
                closes.append(c)
            total += len(self.check(highs, lows, closes, rng.choice([3, 5, 10, 20])))
        self.assertGreater(total, 300)


if __name__ == "__main__":
    unittest.main()
