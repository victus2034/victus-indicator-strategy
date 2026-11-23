"""Which 1D crypto trendline setups the live bot missed since it started (lakky, 2026-11-23: "check how many
trades it misses so far since we started auto trade"), and what each would have done.

Two lists, both scored the bot's way (coindcx_live.py today):
  sent     - every 1D crypto TL record on the runtime-state branch since the bot's first tick, each as the
             bot trades it now: a touch waits for a closed 1h candle that trades the line and closes back
             (entry at the next 15m open, his wick/body 0.75% stop; the wait ends on a daily close through
             the line or after 20 days), a break enters at the next 15m open with the wick/body stop.
             Exits: 1.5R, SL shift +1R -> +0.75R, trail TP, fees 0.0826%, stop slip 0.05% (jfs.walk).
  unsent   - 1D TL touches / breaks today's rules replay (scanner awake all night) that no record matches
             (same coin, side, type, within a day): alerts the scanner never sent, e.g. asleep 01:00-08:00
             IST before 15 Nov.
Which "sent" ones the bot traded / skipped comes from its state file (trading-journal), joined by hand.

    PYTHONPATH=research python research/live_bot_miss_audit.py RUNTIME_STATE_DIR --since-ts 1794560717
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_data  # noqa: E402
import coindcx_live as live  # noqa: E402
import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import scanner  # noqa: E402
import tl_broken_alert_backtest as tlb  # noqa: E402
import tl_lower_tf_entry_backtest as lower  # noqa: E402
from fib_trendline_data import CRYPTO, HISTORY_START, bitunix_candles  # noqa: E402
from journal_fib_setup_backtest import DAY, ist, news_overlap, walk, wick_body_stop  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "live_bot_miss_audit"
BREAK_RULE = (("live", "close", "before", 1),)


def candles(symbol, now, since):
    pair = bitunix_data.pair_for(symbol, scanner.delta_contract(symbol))
    get = lambda res, start: fbt._cached(f"lbm_{pair}_{res}_{int(start) // DAY}", lambda: bitunix_candles(pair, res, start, now))
    daily, four = get("1d", HISTORY_START), get("4h", HISTORY_START)
    raw = get("15m", since - 3 * DAY)
    return daily, four, [[c[0], c[2], c[3], c[4], 900] for c in raw], {c[0]: c[1] for c in raw}


def score(kind, side, t0, anchors, daily, fine, opens):
    """The bot's trade for one alert: entry ts, entry, stop, walk result (or a reason it never entered)."""
    s = -1 if side == "short" else 1
    if kind == "touch":
        got = lower.confirm_fill(lower.group(fine, 3600), daily, anchors, s, t0, 3600) if anchors else None
        if got is None:
            return {"outcome": "no 1h confirm"}
        ts = got[0]
    else:
        ts = next((b[0] for b in fine if b[0] >= t0), None)
    if ts is None or ts not in opens:
        return {"outcome": "no candles yet"}
    entry = opens[ts]
    stop, _ = wick_body_stop(daily, ts, entry, s)
    if stop is None or ((stop >= entry) if s > 0 else (stop <= entry)):
        return {"outcome": "no stop", "entry_ts": ts, "entry": entry}
    w = walk(entry, stop, s, fine, ts, False)
    w["news"] = w.get("fill_ts") is not None and news_overlap(w["fill_ts"], w["fill_ts"] + 900)
    return {**w, "entry_ts": ts, "entry": entry, "sl": stop}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("state_dir")
    ap.add_argument("--since-ts", type=int, default=1794560717)        # the bot's first tick, 13 Nov 14:35 IST
    a = ap.parse_args()
    now, since = int(time.time()), a.since_ts
    config.FIB_TL_CRYPTO_NIGHT = True
    records = []
    for line in (Path(a.state_dir) / "fib_trendline_alert_records.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if (isinstance(r, dict) and r.get("kind") == "trendline" and r.get("market") == "crypto"
                and str(r.get("tf", "")).lower() == "1d" and float(r.get("sent_ts") or 0) >= since - DAY
                and isinstance(r.get("plan"), dict)):
            records.append(r)
    rows = []
    for symbol in config.CRYPTO_WATCHLIST:
        try:
            daily, four, fine, opens = candles(symbol, now, since - DAY)
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} failed: {error!r}")
            continue
        mine = [r for r in records if r["symbol"] == symbol]
        seen = set()
        for r in mine:
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            kind = "break" if r.get("broken") else "touch"
            rows.append({"list": "sent", "id": r["id"], "symbol": symbol, "kind": kind, "side": r["plan"]["side"],
                         "alert_ts": int(float(r["sent_ts"])),
                         **score(kind, r["plan"]["side"], int(float(r["sent_ts"])), live.line_points(r), daily, fine, opens)})
        replay = [("touch", t["alert_ts"], t["plan"]["side"], t.get("anchors"))
                  for t in fbt.replay(CRYPTO, symbol, "1d", daily, four, now) if t["kind"] == "trendline"]
        replay += [("break", t["alert_ts"], t["plan"]["side"], None)
                   for t in tlb.breaks(CRYPTO, symbol, "1d", daily, four, now, since, rules=BREAK_RULE)]
        for kind, ts, side, anchors in replay:
            if ts < since:
                continue
            if any(r["plan"]["side"] == side and bool(r.get("broken")) == (kind == "break")
                   and abs(float(r["sent_ts"]) - ts) < DAY for r in mine):
                continue
            rows.append({"list": "unsent", "symbol": symbol, "kind": kind, "side": side, "alert_ts": int(ts),
                         **score(kind, side, int(ts), anchors, daily, fine, opens)})
    rows.sort(key=lambda x: x["alert_ts"])
    text = [f"# Live bot misses - 1D crypto TL since {ist(since)} to {ist(now)}", "",
            "Bot's rules today (1h confirm for touches, market for breaks, wick/body SL, 1.5R + SL shift + trail TP, "
            "fees + slip), Bitunix 15m. 'news' = fill within 15 min of US CPI / PPI / FOMC.", "",
            "| list | alert (IST) | coin | type | side | entry (IST) | outcome | R | news |", "|---|---|---|---|---|---|---|---|---|"]
    for x in rows:
        r = x.get("r")
        text.append(f"| {x['list']} | {ist(x['alert_ts'])} | {x['symbol']} | {x['kind']} | {x['side']} | "
                    f"{ist(x['entry_ts']) if x.get('entry_ts') else '-'} | {x['outcome']} | "
                    f"{'' if r is None else f'{r:+.2f}'} | {'yes' if x.get('news') else ''} |")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rows.json").write_text(json.dumps(rows, indent=0, default=str))
    (OUT / "SUMMARY.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text))


if __name__ == "__main__":
    main()
