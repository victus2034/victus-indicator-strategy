"""CoinDCX demo account: 1D crypto fib alerts traded as if they were real orders.

lakky, 2026-11-07: "i want to trade 1d fib ... for next week do a demo for
testing and after that go with real money". This is the demo. It places NO
orders - there is no CoinDCX order code in this repo - and moves no money.

Each 1D crypto fib alert (every level, L1-L4) becomes a pretend CoinDCX USDT
futures order the moment the bot sees it, sized the way the journal's Demo
account sizes it (lakky's screenshot: start 1,000, fixed risk 50 a trade, max
leverage 10x):

- a limit order at the alert's entry, with the alert's stop and one target at 1R
  (the journal's "Exit at 1R": same stop, no breakeven, no time limit);
- risk = min(COINDCX_DEMO_RISK, balance); position = risk / stop distance;
  leverage = position / balance, and above COINDCX_DEMO_MAX_LEVERAGE the trade
  is taken at the cap, so it risks less (the journal's demoRun);
- a real account has to hold the margin of every working order: position /
  max leverage. An order whose margin does not fit in what is left of the
  balance is SKIPPED, as the exchange would reject it. The journal's demo has
  no such limit, so this is where the two can differ;
- not filled within FIB_TL_ENTRY_WAIT_BARS days (5): cancelled;
- filled: the stop or 1R, whichever trades first, on Bitunix 1m candles (the
  alerts' own feed); a candle touching both is the stop. The stop pays the
  scanner's slip, and every trade pays a round trip of
  COINDCX_DEMO_ROUND_TRIP_COST_PCT (Delta's number until CoinDCX's is known).

The state (coindcx_demo_state.json, runtime-state branch) starts on the first
tick: alerts sent before it are ignored, so it never trades a backlog. Each
tick posts what happened as one digest to DISCORD_COINDCX_DEMO_WEBHOOK_URL
(falling back to the crypto entry-confirm channel).

  --tick                advance the demo (entry_confirm.yml, every ~5 minutes)
  --report              print (with --send, post) the account so far
  --replay-since DATE   rebuild a demo from DATE on a scratch state file, no Discord
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import bitunix_data
import config
import fib_trendline_trades as trades
import scanner

STATE_FILE = Path(__file__).with_name(os.getenv("VICTUS_COINDCX_DEMO_STATE_FILE", "coindcx_demo_state.json"))
RECORDS_FILE = Path(__file__).with_name(os.getenv("VICTUS_FIB_TL_RECORDS_FILE", "fib_trendline_alert_records.jsonl"))
WEBHOOK_ENV = "DISCORD_COINDCX_DEMO_WEBHOOK_URL"
FALLBACK_WEBHOOK_ENV = "DISCORD_ENTRY_CONFIRM_CRYPTO_WEBHOOK_URL"
WAIT_SECONDS = config.FIB_TL_ENTRY_WAIT_BARS * 86400
ACTIVE = ("pending", "open")
CLOSED = ("won", "lost", "cancelled", "skipped")
DISCORD_LIMIT = 1900


# ---------------------------------------------------------------- selection

def coindcx_pair(symbol):
    """Watchlist symbol -> CoinDCX USDT futures pair: BTCUSD -> B-BTC_USDT,
    1000PEPEUSD -> B-1000PEPE_USDT (CoinDCX's own base, research/out/coindcx)."""
    return f"B-{symbol[:-3]}_USDT" if symbol.endswith("USD") else None


def eligible(record, started_ts):
    """A 1D crypto fib alert, on a coin CoinDCX lists, sent after the demo started."""
    if not isinstance(record, dict):
        return False
    plan = record.get("plan")
    try:
        ok = (record.get("kind") in config.COINDCX_DEMO_KINDS
              and record.get("market") == "crypto"
              and str(record.get("tf", "")).lower() in config.COINDCX_DEMO_TIMEFRAMES
              and record.get("symbol") in config.CRYPTO_WATCHLIST
              and (record.get("level") or "L3") in config.COINDCX_DEMO_LEVELS
              and not record.get("broken")
              and isinstance(plan, dict) and plan.get("side") in ("long", "short")
              and float(plan["entry"]) > 0 and float(plan["sl"]) > 0
              and float(plan["entry"]) != float(plan["sl"])
              and bool(record.get("id"))
              and float(record["sent_ts"]) >= started_ts)
    except (KeyError, TypeError, ValueError):
        return False
    return ok


def load_records():
    try:
        lines = RECORDS_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


# ---------------------------------------------------------------- state

def new_state(now, start_balance=None):
    return {"version": 1, "started_ts": int(now),
            "start_balance": float(config.COINDCX_DEMO_START_BALANCE if start_balance is None else start_balance),
            "balance": float(config.COINDCX_DEMO_START_BALANCE if start_balance is None else start_balance),
            "orders": {}, "unposted": []}


def load_state(path=None):
    path = STATE_FILE if path is None else path
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(state, dict) or "orders" not in state:
        return None
    state.setdefault("unposted", [])
    return state


def save_state(state, path=None):
    path = STATE_FILE if path is None else path
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def margin_in_use(state):
    return sum(o["margin"] for o in state["orders"].values() if o["status"] in ACTIVE)


# ---------------------------------------------------------------- the trade

def size(balance, entry, sl, risk_setting=None, max_leverage=None):
    """The journal's demoRun sizing: (risk, position, leverage, capped)."""
    risk_setting = config.COINDCX_DEMO_RISK if risk_setting is None else risk_setting
    max_leverage = config.COINDCX_DEMO_MAX_LEVERAGE if max_leverage is None else max_leverage
    stop_pct = abs(entry - sl) / entry * 100
    risk = min(risk_setting, balance)
    position = risk / (stop_pct / 100)
    leverage = position / balance if balance > 0 else float("inf")
    capped = False
    if max_leverage and leverage > max_leverage:
        risk = balance * max_leverage * stop_pct / 100
        position = balance * max_leverage
        leverage = max_leverage
        capped = True
    return risk, position, leverage, capped


def open_order(state, record, now):
    """Turn an alert into a demo order (pending), or a skipped one if its margin does not fit."""
    plan = record["plan"]
    entry, sl = float(plan["entry"]), float(plan["sl"])
    long = plan["side"] == "long"
    risk_dist = abs(entry - sl)
    balance = state["balance"]
    risk, position, leverage, capped = size(balance, entry, sl)
    margin = position / config.COINDCX_DEMO_MAX_LEVERAGE
    free = balance - margin_in_use(state)
    order = {
        "id": record["id"], "symbol": record["symbol"], "pair": coindcx_pair(record["symbol"]),
        "side": plan["side"], "level": record.get("level") or "L3", "tf": "1D",
        "entry": entry, "sl": sl, "tp": entry + risk_dist if long else entry - risk_dist,
        "stop_pct": risk_dist / entry * 100, "sent_ts": int(float(record["sent_ts"])),
        "placed_ts": int(now), "risk": round(risk, 4), "position": round(position, 2),
        "leverage": round(leverage, 3), "capped": capped, "margin": round(margin, 2),
        "status": "pending", "checked_until": (int(float(record["sent_ts"])) // 60 + 1) * 60,
    }
    if config.COINDCX_DEMO_MARGIN_LIMIT and margin > free + 1e-9:
        order.update(status="skipped", margin=0.0,
                     reason=f"margin {money(margin)} > free {money(max(free, 0))}")
    state["orders"][order["id"]] = order
    state["unposted"].append({"event": "skipped" if order["status"] == "skipped" else "placed",
                              "id": order["id"], "ts": int(now)})
    return order


def net_r(order, won):
    plan = {"side": order["side"], "entry": order["entry"], "sl": order["sl"]}
    gross = 1.0 if won else trades.stop_r(plan)
    return gross - config.COINDCX_DEMO_ROUND_TRIP_COST_PCT / order["stop_pct"]


def close(state, order, status, ts, won=None):
    order.update(status=status, exit_ts=int(ts))
    if status in ("won", "lost"):
        r = net_r(order, won)
        pnl = order["risk"] * r
        if state["balance"] + pnl < 0:
            pnl = -state["balance"]
        state["balance"] = round(state["balance"] + pnl, 4)
        order.update(r=round(r, 4), pnl=round(pnl, 4), balance_after=state["balance"])
    state["unposted"].append({"event": status, "id": order["id"], "ts": int(ts)})


def step(state, order, candle, width=60):
    """Advance one order by one closed candle [ts, open, high, low, close] of `width` seconds."""
    ts, _o, h, l = candle[0], candle[1], candle[2], candle[3]
    if ts < order["checked_until"]:
        return
    order["checked_until"] = int(ts) + width
    long = order["side"] == "long"
    hit_sl = (l <= order["sl"]) if long else (h >= order["sl"])
    hit_tp = (h >= order["tp"]) if long else (l <= order["tp"])
    if order["status"] == "pending":
        if ts >= order["sent_ts"] + WAIT_SECONDS:
            close(state, order, "cancelled", ts)
            return
        if (l <= order["entry"]) if long else (h >= order["entry"]):
            order.update(status="open", fill_ts=int(ts))
            state["unposted"].append({"event": "filled", "id": order["id"], "ts": int(ts)})
            if hit_sl:      # filled and stopped in the same candle; a target there is not counted
                close(state, order, "lost", ts, won=False)
        return
    if order["status"] == "open":
        if hit_sl:
            close(state, order, "lost", ts, won=False)
        elif hit_tp:
            close(state, order, "won", ts, won=True)


# A pending order whose candles stop coming is still cancelled, this long after its wait.
CANCEL_GRACE_SECONDS = 6 * 3600


def cancel_due(state, order, now):
    """A pending order past its wait that no candle closed: cancel on the clock."""
    deadline = order["sent_ts"] + WAIT_SECONDS
    if order["status"] == "pending" and (
            order["checked_until"] >= deadline or now >= deadline + CANCEL_GRACE_SECONDS):
        close(state, order, "cancelled", deadline)


# ---------------------------------------------------------------- candles

def fetch_candles(symbol, start, end, interval="1m"):
    pair = bitunix_data.bitunix_pair(symbol)
    rows = bitunix_data.klines(pair, interval, int(start), int(end))
    return [r for r in rows if r[1] > 0 and r[2] > 0 and r[3] > 0 and r[4] > 0]


def advance(state, until, fetch=fetch_candles, width=60):
    """Walk every active order through the closed candles up to `until`, in time
    order across orders, so a close frees margin and moves the balance before the
    next one is judged. A symbol whose candles fail is left for the next tick."""
    active = [o for o in state["orders"].values() if o["status"] in ACTIVE]
    by_symbol = {}
    for o in active:
        by_symbol.setdefault(o["symbol"], []).append(o)
    events = []
    for symbol, orders in by_symbol.items():
        start = min(o["checked_until"] for o in orders)
        if start >= until:
            continue
        try:
            candles = fetch(symbol, start, until)
        except Exception as error:     # one coin's feed must not stop the others
            print(f"coindcx demo: {symbol} candles unavailable: {str(error)[:80]}")
            continue
        for c in candles:
            if c[0] + width <= until:
                events.append((c[0], symbol, c))
    events.sort(key=lambda e: (e[0], e[1]))
    for ts, symbol, candle in events:
        for o in by_symbol[symbol]:
            if o["status"] in ACTIVE:
                step(state, o, candle, width)
    for o in active:
        if o["status"] == "pending":
            cancel_due(state, o, until)


def tick(state, records, now, fetch=fetch_candles, width=60):
    """Bring the demo up to `now`: new alerts become orders in the order they
    were sent, each after every older order has been walked up to its send time."""
    known = state["orders"]
    new = sorted((r for r in records if eligible(r, state["started_ts"]) and r["id"] not in known),
                 key=lambda r: float(r["sent_ts"]))
    for record in new:
        sent = int(float(record["sent_ts"]))
        advance(state, min(sent, now), fetch, width)
        open_order(state, record, sent)
    advance(state, now, fetch, width)


# ---------------------------------------------------------------- text

def money(value):
    sign = "-" if value < 0 else ""
    return f"{sign}₹{abs(value):,.2f}"


def coin(symbol):
    return symbol[:-3] if symbol.endswith("USD") else symbol


def event_line(order, event):
    side = "BUY" if order["side"] == "long" else "SELL"
    head = f"**{coin(order['symbol'])} · FIB {order['level']} · {side}**"
    p = scanner.price_text
    if event == "placed":
        cap = " (capped)" if order["capped"] else ""
        return (f"🧪 {head} · order placed\n"
                f"Limit {p(order['entry'])} · SL {p(order['sl'])} ({order['stop_pct']:.2f}%) · TP {p(order['tp'])} (1R)\n"
                f"Size {money(order['position'])} · {order['leverage']:.1f}x{cap} · margin {money(order['margin'])} · risk {money(order['risk'])}")
    if event == "skipped":
        return f"⏭️ {head} · skipped: {order.get('reason', 'no margin')}"
    if event == "filled":
        return f"📥 {head} · filled at {p(order['entry'])}"
    if event == "cancelled":
        return f"⌛ {head} · cancelled, no fill in {config.FIB_TL_ENTRY_WAIT_BARS} days"
    if event in ("won", "lost"):
        icon, what = ("✅", "TP hit") if event == "won" else ("🛑", "SL hit")
        return f"{icon} {head} · {what} · {money(order['pnl'])} ({order['r']:+.2f}R) · balance {money(order['balance_after'])}"
    return f"{head} · {event}"


def summary(state):
    orders = list(state["orders"].values())
    done = [o for o in orders if o["status"] in ("won", "lost")]
    won = sum(o["status"] == "won" for o in done)
    pending = sum(o["status"] == "pending" for o in orders)
    open_ = sum(o["status"] == "open" for o in orders)
    ret = (state["balance"] - state["start_balance"]) / state["start_balance"] * 100
    rate = f" · {won / len(done) * 100:.0f}% won" if done else ""
    return (f"Balance **{money(state['balance'])}** ({ret:+.2f}%) · {len(done)} closed ({won}W / {len(done) - won}L{rate})"
            f" · {open_} open · {pending} waiting · margin in use {money(margin_in_use(state))}")


def digest(state, now):
    if not state["unposted"]:
        return ""
    stamp = datetime.fromtimestamp(now, scanner.IST).strftime("%d %b %H:%M IST")
    lines = [f"**CoinDCX demo · 1D fib** · {stamp} · no real orders"]
    for e in sorted(state["unposted"], key=lambda e: e["ts"]):
        order = state["orders"].get(e["id"])
        if order:
            lines.append(event_line(order, e["event"]))
    lines.append(summary(state))
    return "\n".join(lines)


def chunks(text):
    out, cur = [], ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) + 1 > DISCORD_LIMIT:
            out.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        out.append(cur)
    return out


def send(text):
    env = WEBHOOK_ENV if scanner.get_env_or_config(WEBHOOK_ENV, "") else FALLBACK_WEBHOOK_ENV
    sent = False
    for part in chunks(text):
        sent = scanner.send_discord_message(part.rstrip(), webhook_env_name=env, webhook_config_value="")
        if not sent:
            return False
    return sent


# ---------------------------------------------------------------- main

def run_tick(now=None, dry_run=False, fetch=fetch_candles):
    now = int(time.time()) if now is None else int(now)
    if not config.COINDCX_DEMO_ENABLED:
        print("coindcx demo is off (VICTUS_COINDCX_DEMO)")
        return None
    state = load_state()
    if state is None:
        state = new_state(now)
        print(f"coindcx demo: started at {datetime.fromtimestamp(now, timezone.utc):%Y-%m-%d %H:%M} UTC "
              f"with {money(state['balance'])}; alerts before now are not traded")
        if not dry_run:
            save_state(state)
        return state
    tick(state, load_records(), now, fetch)
    text = digest(state, now)
    if text:
        print(text)
        if dry_run:
            return state
        if send(text):
            state["unposted"] = []
    if not dry_run:
        save_state(state)
    return state


def replay(since, now=None, start_balance=None, interval="5m"):
    """Rebuild a demo from `since` on the alerts on file - nothing posted, the
    live state file untouched. Candles at `interval` (5m keeps it to a few
    hundred requests a coin a month)."""
    now = int(time.time()) if now is None else int(now)
    state = new_state(since, start_balance)
    width = bitunix_data.INTERVAL_SECONDS.get(interval, 60)
    tick(state, load_records(), now, lambda s, a, b: fetch_candles(s, a, b, interval), width)
    state["unposted"] = []
    return state


def report_text(state):
    lines = [f"**CoinDCX demo · 1D fib** · since {datetime.fromtimestamp(state['started_ts'], scanner.IST):%d %b %H:%M IST}",
             summary(state)]
    for o in sorted(state["orders"].values(), key=lambda o: o["sent_ts"]):
        when = datetime.fromtimestamp(o["sent_ts"], scanner.IST).strftime("%d %b")
        side = "BUY" if o["side"] == "long" else "SELL"
        tail = f"{money(o['pnl'])} ({o['r']:+.2f}R)" if "pnl" in o else o["status"]
        lines.append(f"{when} {coin(o['symbol'])} {o['level']} {side} · {o['status']} · {tail}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tick", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--send", action="store_true", help="with --report: post it")
    parser.add_argument("--dry-run", action="store_true", help="with --tick: print, post nothing, save nothing")
    parser.add_argument("--replay-since", help="YYYY-MM-DD (UTC): rebuild a scratch demo from this day")
    parser.add_argument("--interval", default="5m", help="candles for --replay-since")
    parser.add_argument("--out", help="with --replay-since: write the scratch state here")
    parser.add_argument("--no-margin-limit", action="store_true",
                        help="with --replay-since: take every alert, like the journal's demo")
    args = parser.parse_args(argv)
    if args.replay_since:
        if args.no_margin_limit:
            config.COINDCX_DEMO_MARGIN_LIMIT = False
        since = int(datetime.strptime(args.replay_since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        state = replay(since, interval=args.interval)
        print(report_text(state))
        if args.out:
            save_state(state, Path(args.out))
        return 0
    if args.tick:
        run_tick(dry_run=args.dry_run)
    if args.report:
        state = load_state()
        if state is None:
            print("coindcx demo: no state yet")
            return 0
        text = report_text(state)
        print(text)
        if args.send:
            send(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
