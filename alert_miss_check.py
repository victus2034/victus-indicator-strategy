"""Daily check: 1D crypto fib / trendline alerts the replay finds that the live scanner never recorded.

lakky, 2026-11-23: "Make sure no trade now misses as well as alerts". Once a day this replays the last
--hours of 1D crypto charts the way the history backtest does (fib_trendline_backtest.replay for fib levels
and TL touches, tl_broken_alert_backtest.breaks for TL BROKEN - the bot's trades) and lists every alert with
no live record of the same coin, kind, side (and fib level) within a day. Nothing missed: one quiet line in
the log, nothing posted. Anything missed: one short message to DISCORD_STATUS_WEBHOOK_URL. Posts nothing else
and changes no state. The bot's own skips (one per coin, smallest order, kill switch) are in its LIVE digest.

    python alert_miss_check.py RUNTIME_STATE_DIR [--hours 48] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "research"))

import bitunix_data  # noqa: E402
import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, HISTORY_START, bitunix_candles  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
DAY = 86400
BREAK_RULE = (("live", "close", "before", 1),)


def ist(ts):
    return datetime.fromtimestamp(ts, IST).strftime("%d %b %H:%M")


def load_records(state_dir, since):
    out = []
    path = Path(state_dir) / "fib_trendline_alert_records.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if (isinstance(r, dict) and r.get("market") == "crypto" and str(r.get("tf", "")).lower() == "1d"
                and r.get("kind") in ("fib", "trendline") and float(r.get("sent_ts") or 0) >= since - DAY
                and isinstance(r.get("plan"), dict)):
            out.append(r)
    return out


def kind_of(record):
    if record["kind"] == "fib":
        return "fib " + str(record.get("level") or "L3")
    return "TL BROKEN" if record.get("broken") else "TL touch"


def replay_alerts(symbol, now, since):
    import tl_broken_alert_backtest as tlb
    pair = bitunix_data.pair_for(symbol, scanner.delta_contract(symbol))
    daily = bitunix_candles(pair, "1d", HISTORY_START, now)
    four = bitunix_candles(pair, "4h", HISTORY_START, now)
    found = []
    for t in fbt.replay(CRYPTO, symbol, "1d", daily, four, now):
        if t["alert_ts"] < since:
            continue
        kind = ("fib " + str(t.get("level") or "L3")) if t["kind"] == "fib" else "TL touch"
        found.append((kind, t["plan"]["side"], int(t["alert_ts"])))
    for t in tlb.breaks(CRYPTO, symbol, "1d", daily, four, now, since, rules=BREAK_RULE):
        if t["alert_ts"] >= since:
            found.append(("TL BROKEN", t["plan"]["side"], int(t["alert_ts"])))
    return found


def misses(records, found_by_symbol):
    out = []
    for symbol, found in found_by_symbol.items():
        mine = [r for r in records if r["symbol"] == symbol]
        for kind, side, ts in found:
            if not any(kind_of(r) == kind and r["plan"]["side"] == side and abs(float(r["sent_ts"]) - ts) < DAY
                       for r in mine):
                out.append((ts, symbol, kind, side))
    return sorted(out)


def message(missed, hours):
    lines = [f"⚠️ **Alert miss check** · {len(missed)} 1D crypto alert(s) the replay found and the scanner "
             f"never sent (last {hours}h)"]
    for ts, symbol, kind, side in missed[:15]:
        lines.append(f"`{scanner.alert_symbol(symbol)}` {kind} {'BUY' if side == 'long' else 'SELL'} · {ist(ts)} IST")
    if len(missed) > 15:
        lines.append(f"... and {len(missed) - 15} more")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("state_dir")
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    config.FIB_TL_CRYPTO_NIGHT = True
    now = int(time.time())
    # alerts the scanner may still be about to send are not misses yet
    since, until = now - a.hours * 3600, now - 3600
    records = load_records(a.state_dir, since)
    found = {}
    for symbol in config.CRYPTO_WATCHLIST:
        try:
            found[symbol] = [f for f in replay_alerts(symbol, now, since) if f[2] < until]
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} failed: {error!r}")
    missed = misses(records, found)
    total = sum(len(v) for v in found.values())
    print(f"replay {total} alerts, {len(records)} live records, {len(missed)} missed")
    if a.dry_run:
        for symbol, items in found.items():
            for kind, side, ts in sorted(items, key=lambda f: f[2]):
                print(f"  replay {ist(ts)} {symbol} {kind} {side}")
    for ts, symbol, kind, side in missed:
        print(f"  MISSED {ist(ts)} {symbol} {kind} {side}")
    if missed and not a.dry_run:
        if not scanner.send_discord_message(message(missed, a.hours), "DISCORD_STATUS_WEBHOOK_URL", ""):
            print("DISCORD_STATUS_WEBHOOK_URL not set: nothing posted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
