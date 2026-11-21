"""1D crypto trendline touches: does a lower-timeframe entry help? (lakky, 2026-11-15: "as time
goes trendline shifts ... for more clear entry go with lower timeframe for entry accuracy only";
XRP 1D, the lower line touched 15 Nov 03:15 IST with no trade.)

Same alerts as journal_tl_setup_backtest (today's rules, 1D TL touches, whole watchlist), same
exits (1.5R, SL shift +1R -> +0.75R, trail TP, fees, slip), Bitunix 15m, fills within 15 min of
US CPI / PPI / FOMC left out. Only the entry changes:

  day line     - today's: a limit at the line's price on the alert's daily candle, never moved
  line now     - the limit follows the line: each 15m candle is tested against the line's price
                 at that candle's own time
  confirm X    - wait for an X candle (15m / 1h / 4h) that trades the line at its own time and
                 closes back on the trade's side; enter at that close. Waiting ends when a daily
                 candle closes through the line (the line is broken) or after 20 days.
                 SL "day": his wick-or-body 0.75% daily rule. SL "candle": past the confirming
                 candle's wick (left out under 0.25% risk).

--night also replays with the scanner awake 01:00-08:00 IST (live since 2026-11-15).

    PYTHONPATH=research python research/tl_lower_tf_entry_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_data  # noqa: E402
import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import journal_fib_setup_backtest as jfs  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, HISTORY_START, bitunix_candles, delta_candles  # noqa: E402
from journal_fib_setup_backtest import DAY, HEAD, IST, ist, line, news_overlap, walk, wick_body_stop  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "tl_lower_tf_entry"
CONFIRM = (("15m", 900), ("1h", 3600), ("4h", 14400))
MIN_RISK_PCT = 0.25


def line_at(anchors, ts):
    t1, y1, t2, y2 = anchors
    return y1 + (y2 - y1) * (ts - t1) / (t2 - t1)


def group(fine, seconds):
    """15m [ts, h, l, c, 900] -> [ts, h, l, c, seconds], only whole candles."""
    out = {}
    for b in fine:
        k = b[0] - b[0] % seconds
        g = out.setdefault(k, [k, b[1], b[2], b[3], 0])
        g[1], g[2], g[3], g[4] = max(g[1], b[1]), min(g[2], b[2]), b[3], g[4] + b[4]
    return [g for g in sorted(out.values()) if g[4] == seconds]


def moving_fill(fine, anchors, s, t0):
    """First 15m candle from t0 that trades the line at its own time: (ts, line price)."""
    for b in fine:
        if b[0] < t0:
            continue
        if b[0] >= t0 + jfs.FILL_SECONDS:
            return None
        lvl = line_at(anchors, b[0])
        if lvl > 0 and ((b[2] <= lvl) if s > 0 else (b[1] >= lvl)):
            return b[0], lvl
    return None


def confirm_fill(bars, daily, anchors, s, t0, seconds):
    """First candle from t0 that trades the line and closes back: (entry ts, candle)."""
    dead = next((c[0] + DAY for c in daily if c[0] + DAY > t0
                 and ((c[4] < line_at(anchors, c[0])) if s > 0 else (c[4] > line_at(anchors, c[0])))), None)
    for b in bars:
        if b[0] < t0:
            continue
        end = b[0] + seconds
        if end > t0 + jfs.FILL_SECONDS or (dead is not None and end > dead):
            return None
        a, z = line_at(anchors, b[0]), line_at(anchors, end)
        touched = (b[2] <= a) if s > 0 else (b[1] >= a)
        back = (b[3] > z) if s > 0 else (b[3] < z)
        if touched and back:
            return end, b
    return None


def scored(base, entry, stop, s, fine, t0, stop_candle=None):
    if stop is None or ((stop >= entry) if s > 0 else (stop <= entry)):
        return {**base, "entry": entry, "sl": 0.0, "outcome": "no stop", "risk_pct": 0.0}
    w = walk(entry, stop, s, fine, t0, False)
    w["news"] = w.get("fill_ts") is not None and news_overlap(w["fill_ts"], w["fill_ts"] + 900)
    return {**base, "entry": entry, "sl": stop, "stop_candle": stop_candle, **w}


def symbol_trades(symbol, since, now):
    contract = scanner.delta_contract(symbol)
    if bitunix_data.uses_bitunix(symbol):
        pair = bitunix_data.pair_for(symbol, contract)
        get = lambda res, start: fbt._cached(f"jf_{pair}_{res}_{int(start) // DAY}", lambda: bitunix_candles(pair, res, start, now))
    else:
        get = lambda res, start: fbt._cached(f"jf_{contract}_{res}_{int(start) // DAY}", lambda: delta_candles(contract, res, max(start, now - 2000 * DAY), now))
    daily, four = get("1d", HISTORY_START), get("4h", HISTORY_START)
    raw = get("15m", since - 3 * DAY)
    fine = [[c[0], c[2], c[3], c[4], 900] for c in raw]
    opens = {c[0]: c[1] for c in raw}
    grouped = {name: group(fine, sec) for name, sec in CONFIRM}
    band = fbt.band_for("1d")
    out = {}
    for t in fbt.replay(CRYPTO, symbol, "1d", daily, four, now):
        if t["kind"] != "trendline" or t["alert_ts"] < since:
            continue
        p, anchors = t["plan"], t["anchors"]
        s = -1 if p["side"] == "short" else 1
        edge = p["entry"] * (1 + s * band)
        t0 = next((b[0] + 900 for b in fine if t["alert_ts"] <= b[0] < t["alert_ts"] + 4 * 3600
                   and ((b[2] <= edge) if s > 0 else (b[1] >= edge))), t["alert_ts"] + 4 * 3600)
        base = {"symbol": symbol, "level": "touch", "side": p["side"], "alert_sl": p["sl"], "alert_ts": t0}
        stop, sc = wick_body_stop(daily, t0, p["entry"], s)
        out.setdefault("day line (today)", []).append(scored(base, p["entry"], stop, s, fine, t0, sc))
        got = moving_fill(fine, anchors, s, t0)
        if got is None:
            out.setdefault("line now (moving limit)", []).append({**base, "entry": p["entry"], "sl": 0.0, "outcome": "no fill", "risk_pct": 0.0})
        else:
            ts, lvl = got
            stop, sc = wick_body_stop(daily, ts, lvl, s)
            out.setdefault("line now (moving limit)", []).append(scored(base, lvl, stop, s, fine, ts, sc))
        for name, sec in CONFIRM:
            got = confirm_fill(grouped[name], daily, anchors, s, t0, sec)
            for sl_name in ("day", "candle"):
                key = f"confirm {name}, SL {sl_name}"
                if got is None or got[0] not in opens:
                    out.setdefault(key, []).append({**base, "entry": p["entry"], "sl": 0.0, "outcome": "no fill", "risk_pct": 0.0})
                    continue
                ts, bar = got
                entry = opens[ts]
                if sl_name == "day":
                    stop, sc = wick_body_stop(daily, ts, entry, s)
                else:
                    stop, sc = (bar[2] if s > 0 else bar[1]), None
                    if abs(entry - stop) / entry * 100 < MIN_RISK_PCT:
                        stop = None
                out.setdefault(key, []).append(scored(base, entry, stop, s, fine, ts, sc))
    return out


def _safe(symbol, since, now):
    try:
        return symbol_trades(symbol, since, now)
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} failed: {error!r}")
        return None


def run(since, now):
    ways, failed = {}, []
    symbols = list(config.WATCHLIST)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for symbol, res in zip(symbols, pool.map(lambda x: _safe(x, since, now), symbols)):
            if res is None:
                failed.append(symbol)
                continue
            for k, rows in res.items():
                ways.setdefault(k, []).extend(rows)
    return ways, failed


def table(ways):
    keep = lambda rows: [t for t in rows if t["outcome"] != "no stop" and not t.get("news")]
    return [HEAD] + [line(name, keep(rows)) for name, rows in ways.items()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-09-01")
    ap.add_argument("--night", action="store_true", help="also replay with the scanner awake 01:00-08:00 IST")
    a = ap.parse_args()
    since = int(datetime.fromisoformat(a.since).replace(tzinfo=IST).timestamp())
    now = int(time.time())
    config.FIB_TL_CRYPTO_NIGHT = False          # the scanner as it was until 2026-11-15
    ways, failed = run(since, now)
    crypto = set(config.CRYPTO_WATCHLIST)
    text = [f"# 1D trendline touches, lower-timeframe entry - {a.since} to {ist(now)[:10]}", "",
            "1D TL touch alerts, today's rules, whole watchlist; his exits (1.5R, SL shift, trail TP), fees 0.0826%, "
            "stop slip 0.05%, Bitunix 15m. Fills within 15 min of US CPI / PPI / FOMC and trades with no usable stop left out."
            + (f" FAILED symbols: {', '.join(failed)}." if failed else ""), "",
            "## Scanner asleep 01:00-08:00 IST (until 15 Nov)", ""] + table(ways)
    text += ["", "## Same, crypto coins only", ""] + table({k: [t for t in v if t["symbol"] in crypto] for k, v in ways.items()})
    if a.night:
        config.FIB_TL_CRYPTO_NIGHT = True
        night, failed2 = run(since, now)
        text += ["", "## Scanner awake all night (live now)" + (f" (FAILED: {', '.join(failed2)})" if failed2 else ""), ""] + table(night)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"SUMMARY_{a.since}.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text))
