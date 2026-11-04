"""Research (lakky, 2026-11-04): hand-check 10 recent live fib trades - is the SL the one the chart
draws, and is the stored result what the candles say?

For each trade:
  1. SL: recomputed from the record's four levels with the timeframe's live rule
     (fib_trendline_scanner.stops_for_levels / sl_rule_for; 1W/1M "body" reads the chart's
     closed candles since the fib origin).
  2. Result: walked again on the same evaluation candles the daily report uses, by a separate
     loop written here from the rules (limit fill within 5 candles of the timeframe, SL / +0.5R
     breakeven / 1R / 2R, 20-candle hold, a candle touching stop and target = stop), and
     compared with fib_trendline_results.json. Prints the fill and exit candles for the chart.

    python research/fib_spot_check.py --state /tmp/rt
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bitunix_data  # noqa: E402
import fib_trendline_daily_report as report  # noqa: E402
import fib_trendline_scanner as fts  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE, crypto_charts, nse_charts  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_spot_check"
SINCE = 1793145600            # 2026-10-28 00:00 UTC, after per-level SLs went live (PR #70)
PICKS = [(CRYPTO, "4h", "SL"), (CRYPTO, "4h", "2R"), (CRYPTO, "4h", "BE"), (CRYPTO, "4h", "1R"),
         (CRYPTO, "4h", "no fill"), (CRYPTO, "1d", "SL"), (CRYPTO, "1d", "BE"), (CRYPTO, "1w", "2R"),
         (NSE, "4h", "SL"), (NSE, "1d", "2R")]


def ist(ts):
    return datetime.fromtimestamp(ts, IST).strftime("%d %b %H:%M")


def body_candles(rec):
    """(open, close) of the alert timeframe's closed candles from the fib origin to the alert."""
    origin = int(rec["key"].split("|")[4])
    tf = rec["tf"]
    if rec["market"] == CRYPTO:
        pair = bitunix_data.pair_for(rec["symbol"], rec["symbol"])
        candles = crypto_charts(pair, [tf], rec["sent_ts"], source="bitunix")[tf]
    else:
        candles = nse_charts([rec["symbol"]], [tf])[rec["symbol"]][tf]
    step = {"4h": 14400, "1d": 86400, "1w": 7 * 86400, "1M": 31 * 86400}[tf]
    return [(c[1], c[4]) for c in candles if origin <= c[0] and c[0] + step <= rec["sent_ts"]]


def expected_sl(rec):
    d = 1 if rec["plan"]["side"] == "long" else -1
    rule = fts.sl_rule_for(rec["tf"])
    bodies = body_candles(rec) if rule == "body" else None
    return fts.stops_for_levels(d, rec["levels"], rule, bodies)[rec["level"]], rule


def walk(plan, market, tf, sent_ts, candles):
    """Independent re-walk. Returns (outcome, fill candle, exit candle)."""
    long = plan["side"] == "long"
    entry, sl = plan["entry"], plan["sl"]
    risk = abs(entry - sl)
    sgn = 1 if long else -1
    t1, t2, half = entry + sgn * risk, entry + 2 * sgn * risk, entry + 0.5 * sgn * risk
    be = entry + sgn * entry * trades.BREAK_EVEN_PCT[market] / 100
    be_ok = (half >= be) if long else (half <= be)
    per = trades.EVAL_PER_BAR[market][tf]
    after = [c for c in candles if c[0] > sent_ts]
    fill = None
    for n, c in enumerate(after[:5 * per]):
        if (c[3] <= entry) if long else (c[2] >= entry):
            fill = n
            break
    if fill is None:
        return ("no fill" if len(after) >= 5 * per else "open"), None, None
    fc = after[fill]
    if (fc[3] <= sl) if long else (fc[2] >= sl):
        return "SL", fc, fc
    got_half = got_1r = False
    for c in after[fill + 1: fill + 1 + 20 * per]:
        stop = be if (got_half and be_ok) else sl
        through = lambda p, above: (c[2] >= p) if above else (c[3] <= p)   # noqa: E731
        if through(stop, not long):
            return ("1R" if got_1r else "BE" if stop == be else "SL"), fc, c
        if through(half, long):
            got_half = True
        if through(t1, long):
            got_1r = True
        if through(t2, long):
            return "2R", fc, c
    if len(after) < fill + 1 + 20 * per:
        return ("1R" if got_1r else "open"), fc, None
    return ("1R" if got_1r else "timeout"), fc, after[fill + 20 * per]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default=".")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    state = Path(args.state)
    results = json.loads((state / "fib_trendline_results.json").read_text())
    records = []
    for line in (state / "fib_trendline_alert_records.jsonl").read_text().splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    pool = [r for r in records if r.get("kind") == "fib" and r.get("sent_ts", 0) >= SINCE
            and r.get("levels") and r.get("level") and results.get(r["id"], {}).get("resolved")]
    chosen = []
    for market, tf, outcome in PICKS:
        hit = [r for r in pool if r["market"] == market and r["tf"] == tf
               and results[r["id"]]["outcome"] == outcome]
        if hit:
            chosen.append(hit[-1])
    rows, detail = [], []
    for rec in chosen:
        plan, stored = rec["plan"], results[rec["id"]]
        try:
            exp, rule = expected_sl(rec)
        except Exception as error:  # noqa: BLE001
            exp, rule = None, f"error {error}"
        res = trades.EVAL_RESOLUTION[rec["market"]][rec["tf"]]
        try:
            candles = report.eval_candles(rec["market"], rec["symbol"], res, rec["sent_ts"], rec["sent_ts"] + 60 * 86400)
        except Exception as error:  # noqa: BLE001
            print(f"{rec['symbol']}: no candles - {error}")
            candles = []
        mine, fc, xc = walk(plan, rec["market"], rec["tf"], rec["sent_ts"], candles)
        sl_ok = exp is not None and abs(exp - plan["sl"]) <= 1e-9 * max(1.0, plan["sl"])
        rows.append(f"| {rec['symbol']} | {rec['market']} {rec['tf'].upper()} | {plan['side']} {rec['level']} | "
                    f"{plan['entry']:.6g} | {plan['sl']:.6g} | {exp if exp is None else f'{exp:.6g}'} ({rule}) | "
                    f"{'yes' if sl_ok else 'NO'} | {stored['outcome']} | {mine} | {'yes' if mine == stored['outcome'] else 'NO'} |")
        detail.append(f"- **{rec['symbol']} {rec['tf'].upper()} {rec['level']}** sent {ist(rec['sent_ts'])} IST, "
                      f"{res} candles: fill "
                      + (f"{ist(fc[0])} (H {fc[2]:.6g} L {fc[3]:.6g})" if fc else "none")
                      + ", exit " + (f"{ist(xc[0])} (H {xc[2]:.6g} L {xc[3]:.6g})" if xc else "none"))
    text = ["# Fib spot check: 10 live trades since 28 Oct", "",
            "| symbol | chart | side | entry | SL stored | SL recomputed (rule) | SL ok | result stored | result re-walked | match |",
            "|---|---|---|---|---|---|---|---|---|---|", *rows, "", "Fill and exit candles (times IST):", "", *detail, ""]
    (OUT / "SPOT_CHECK.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
