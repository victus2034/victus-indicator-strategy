"""Old vs new trendlines, line by line - does v12.5 draw better lines?

Lakky, 2026-10-07, after v12.5 went live: "test the new and previous one so we
know did it work or not". trendline_anchor_backtest.py scores the alerts as
trades; this scores the LINES themselves on the same candles, both rules:

- cut-through: a candle between the two anchors is through the line (a low
  under a support, a high over a resistance) - what Lakky called wrong on
  HYPE 1D (the Aug 19 candle under Aug 2 -> Sep 15).
- twins: another line on the same side starts from the same candle.
- span: bars between the two anchors; "far" = more than 100 bars back.
- first touch after the line appears: held = no close through it on the touch
  candle or the next HOLD_BARS candles.

    python research/trendline_anchor_quality.py
"""
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fib_trendline_data import CRYPTO, NSE, candle_is_closed  # noqa: E402
from trendline_length_backtest import LIVE_TFS, load  # noqa: E402
from trendlines import SUPPORT, build_trendlines  # noqa: E402
import config  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "trendline_anchor"
RULES = (("old (v12.4)", "oldest"), ("new (v12.5)", "tangent"), ("last lower", "last_lower"),
         ("last lower, no twins", "last_lower_unique"))
HOLD_BARS = 3
FAR_BARS = 100


def score(highs, lows, closes, anchor):
    lines = build_trendlines(highs, lows, closes, config.TRENDLINE_SWING_LENGTH,
                             config.TRENDLINES_KEEP, history=True, anchor=anchor)
    starts = Counter((l.kind, l.x1) for l in lines)
    by_start = defaultdict(list)
    for l in lines:
        by_start[(l.kind, l.x1)].append(l)
    s = defaultdict(int)
    spans = []
    for l in lines:
        sup = l.kind == SUPPORT
        s["lines"] += 1
        spans.append(l.x2 - l.x1)
        s["far"] += (l.x2 - l.x1) > FAR_BARS
        s["twins"] += starts[(l.kind, l.x1)] > 1
        gone = l.trimmed_at if l.trimmed_at is not None else len(closes)
        s["shown_twins"] += any(o is not l and o.kind == l.kind and o.x1 == l.x1 and o.created < gone
                                and (o.trimmed_at if o.trimmed_at is not None else len(closes)) > l.created
                                for o in by_start[(l.kind, l.x1)])
        tol = 1e-9 * abs(l.y2)
        s["cut"] += any((lows[k] < l.price_at(k) - tol) if sup else (highs[k] > l.price_at(k) + tol)
                        for k in range(l.x1 + 1, l.x2))
        end = l.broken_at if l.broken_at is not None else len(closes) - 1
        for k in range(l.created + 1, end + 1):
            y = l.price_at(k)
            if (lows[k] <= y) if sup else (highs[k] >= y):
                s["touched"] += 1
                window = range(k, min(k + HOLD_BARS, len(closes) - 1) + 1)
                s["held"] += all((closes[j] >= l.price_at(j)) if sup else (closes[j] <= l.price_at(j))
                                 for j in window)
                break
    return s, spans


def main():
    now = time.time()
    data = load(now)
    agg = {(m, tf, r): defaultdict(int) for m in (CRYPTO, NSE) for tf in LIVE_TFS + ["all"] for r, _ in RULES}
    spans = defaultdict(list)
    for market, symbol, (base, _evals) in data:
        for tf in LIVE_TFS:
            candles = base.get(tf, [])
            if candles and not candle_is_closed(market, candles[-1][0], tf, now):
                candles = candles[:-1]
            if len(candles) < 50:
                continue
            h = [c[2] for c in candles]; lo = [c[3] for c in candles]; cl = [c[4] for c in candles]
            for name, anchor in RULES:
                s, sp = score(h, lo, cl, anchor)
                for key in ((market, tf, name), (market, "all", name)):
                    for k, v in s.items():
                        agg[key][k] += v
                    spans[key] += sp
    pct = lambda a, b: f"{100 * a / b:.0f}%" if b else "-"
    lines = ["# Trendline lines: old (v12.4) vs new (v12.5) vs last lower (candidate)", "",
             f"Same candles as the backtests (Delta for crypto, Yahoo for NSE), length "
             f"{config.TRENDLINE_SWING_LENGTH}, live timeframes. Cut-through = a candle between the two "
             f"anchors is through the line. Twins = another line starts from the same candle; on chart together = both shown at once. Far = anchors "
             f"more than {FAR_BARS} bars apart. Held = first touch after the line appears, no close through "
             f"it on that candle or the next {HOLD_BARS}.", "",
             "| market | tf | rule | lines | cut-through | twins | twins on chart together | far | median span | touched | held at 1st touch |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for market in (CRYPTO, NSE):
        for tf in LIVE_TFS + ["all"]:
            for name, _ in RULES:
                a = agg[(market, tf, name)]
                sp = spans[(market, tf, name)]
                lines.append(f"| {market} | {tf} | {name} | {a['lines']} | {pct(a['cut'], a['lines'])} | "
                             f"{pct(a['twins'], a['lines'])} | {pct(a['shown_twins'], a['lines'])} | {pct(a['far'], a['lines'])} | "
                             f"{statistics.median(sp) if sp else '-'} | {a['touched']} | {pct(a['held'], a['touched'])} |")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "QUALITY.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
