"""Replay entry confirm, old rules vs new (2026-10-21), on the 1D/1W/1M fib/TL
alerts in research/entry_confirm_alerts_in.json, on real 5m candles.

A check every 5 minutes inside entry confirm's hours (crypto 08:00-01:00 IST,
NSE 09:15-15:10 IST), from each alert to the end of its window. At each check
the live price is the close of the last finished 5m candle.

old: NSE sees only that price; crypto sweeps the last two 30m candles (built
     from 5m, so it can reach back before the alert); first-seen LATE silent.
new: resolve_pings as now (sweep since the later of alert and last check).

Writes research/out/entry_confirm/REPLAY.md. Posts nothing.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import entry_confirm as ec  # noqa: E402
from entry_confirm_audit import crypto_5m, in_hours  # noqa: E402
import fib_trendline_data as data  # noqa: E402

OUT = ROOT / "research" / "out" / "entry_confirm"
STEP = 300


def old_resolve(record, info, state, now):
    """The rules before 2026-10-21: first-seen LATE silent, a stop silent."""
    key = ec.watch_key(record)
    entry_state = state.get(key, {})
    last_stage = int(entry_state.get("stage", 0))
    side = record["side"]
    price = info["price"]
    extreme = info.get("recent_low" if side == "long" else "recent_high", price)
    reached = bool(entry_state.get("reached_entry"))
    s1, r1 = ec.classify(price, record, reached)
    s2, r2 = ec.classify(extreme, record, reached)
    entry_state["reached_entry"] = r1 or r2
    stage = s2 if ec._rank(s2) > ec._rank(s1) else s1
    stopped = entry_state.get("stopped_out", False) or max(
        ec.risk_progress(price, record["_entry"], record["_stop"], side),
        ec.risk_progress(extreme, record["_entry"], record["_stop"], side)) >= 1.0
    entry_state["stopped_out"] = stopped
    pings = []
    if stopped:
        stage = None
    if stage is not None and stage > last_stage:
        if not (last_stage == 0 and stage == ec.STAGE_LATE):
            pings.append(stage)
        entry_state["stage"] = stage
    state[key] = entry_state
    return pings


def main():
    alerts = json.loads((ROOT / "research" / "entry_confirm_alerts_in.json").read_text())
    touches = {(a["key"], a["sent_ts"]): a for a in json.loads((OUT / "touches.json").read_text())}
    nse = data.nse_download(sorted({a["symbol"] for a in alerts if a["market"] == "nse"}), "5m")
    cache = {}
    rows = []
    now_ts = int(pd.Timestamp.now(tz="UTC").timestamp())
    for a in alerts:
        if a["sent_ts"] < pd.Timestamp("2026-10-12", tz="UTC").timestamp():
            continue        # trendline plans rewritten by the Oct 11 rebuild
        risk = abs(a["entry"] - a["sl"])
        prog = (a["entry"] - a["price"]) / risk if a["side"] == "long" else (a["price"] - a["entry"]) / risk
        if prog > 0:
            continue        # past entry when sent: never watched
        if a["market"] == "nse":
            candles = nse.get(a["symbol"], [])
        else:
            if a["symbol"] not in cache:
                first = min(x["sent_ts"] for x in alerts if x["symbol"] == a["symbol"])
                cache[a["symbol"]] = crypto_5m(a["symbol"], first - 3600, now_ts)
            candles = cache[a["symbol"]]
        candles = sorted(candles)
        window = ec.fib_tl_window(a["market"], a["tf"]).total_seconds()
        end = min(now_ts, a["sent_ts"] + window)
        record = {
            "symbol": a["symbol"], "timeframe": a["tf"], "side": a["side"], "kind": a["kind"],
            "level": a.get("level") or "L3", "_entry": a["entry"], "_stop": a["sl"],
            "_delivered": pd.Timestamp(a["sent_ts"], unit="s", tz="UTC").tz_convert(ec.IST),
            "_market": a["market"],
        }
        old_state, new_state = {}, {}
        old_first = new_first = None
        new_note = ""
        t = (a["sent_ts"] // STEP + 1) * STEP + 60
        i = 0
        while t <= end and candles:
            if not in_hours(a["market"], t):
                t += STEP
                continue
            done = [c for c in candles if c[0] + STEP <= t]
            if not done:
                t += STEP
                continue
            price = float(done[-1][4])
            now = pd.Timestamp(t, unit="s", tz="UTC").tz_convert(ec.IST)
            # old
            info = {"price": price}
            if a["market"] == "crypto":
                recent = [c for c in done if c[0] >= (t // 1800 - 1) * 1800]
                info["recent_low"] = min([price] + [c[3] for c in recent])
                info["recent_high"] = max([price] + [c[2] for c in recent])
            if old_first is None and ec.STAGE_ENTRY in old_resolve(record, info, old_state, now):
                old_first = t
            # new
            since = ec.sweep_since(record, new_state, now)
            fine = {"price": price, "candles": [[c[0], c[2], c[3]] for c in done[-400:]], "candle_seconds": STEP}
            pings, _ = ec.resolve_pings(record, fine, new_state, now, since)
            new_state[ec.LAST_CHECK_KEY.format(market=a["market"])] = t
            for stage, line in pings:
                if stage == ec.STAGE_ENTRY and new_first is None:
                    new_first = t
                    new_note = line.split(" · ")[-1] if "since the last check" in line else ""
            t += STEP
            i += 1
        touch = touches.get((a["key"], a["sent_ts"]), {})
        rows.append(dict(market=a["market"], symbol=a["symbol"], tf=a["tf"], kind=a["kind"],
                         level=a.get("level"), touched=bool(touch.get("any_touch_in_hours_ts")),
                         touch_ts=touch.get("touch_ts"), old=old_first, new=new_first, note=new_note))

    def fmt(ts):
        return pd.Timestamp(ts, unit="s", tz="UTC").tz_convert(ec.IST).strftime("%d %b %H:%M") if ts else "-"

    lines = ["# Entry confirm replay, old vs new (alerts 12-21 Oct, 1D/1W/1M)", "",
             "| Market | Alerts | Entry touched in hours | ENTRY sent, old | ENTRY sent, new | Touched, no ENTRY (old / new) | ENTRY w/o touch (new) |",
             "|---|---|---|---|---|---|---|"]
    for market in ("crypto", "nse"):
        part = [r for r in rows if r["market"] == market]
        t = [r for r in part if r["touched"]]
        lines.append(f"| {market} | {len(part)} | {len(t)} | {sum(1 for r in part if r['old'])} | "
                     f"{sum(1 for r in part if r['new'])} | {sum(1 for r in t if not r['old'])} / "
                     f"{sum(1 for r in t if not r['new'])} | {sum(1 for r in part if r['new'] and not r['touched'])} |")
    lines += ["", "## Alerts the old rules missed", "", "| Alert | Touched | New ENTRY | Note |", "|---|---|---|---|"]
    for r in rows:
        if r["touched"] and not r["old"]:
            name = f"{r['symbol']} {r['tf']} {r['kind']} {r['level'] or ''}".strip()
            lines.append(f"| {name} | {fmt(r['touch_ts'])} | {fmt(r['new'])} | {r['note']} |")
    lines += ["", "## Still missed with the new rules", ""]
    for r in rows:
        if r["touched"] and not r["new"]:
            lines.append(f"- {r['symbol']} {r['tf']} {r['kind']} touched {fmt(r['touch_ts'])}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "REPLAY.md").write_text("\n".join(lines) + "\n")
    (OUT / "replay.json").write_text(json.dumps(rows, indent=0))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
