"""CoinDCX demo account: 1D crypto fib and trendline alerts traded as if they were real orders.

lakky, 2026-11-07: "i want to trade 1d fib ... for next week do a demo for
testing and after that go with real money". This is the demo. It places NO
orders - there is no CoinDCX order code in this repo - and moves no money.

Each 1D crypto fib alert (every level, L1-L4) becomes a pretend CoinDCX USDT
futures order the moment the bot sees it; since 2026-11-08 (lakky: "also in demo
trades in coindcx put this strategy also") so does each 1D crypto trendline alert -
touches (S TL / R TL, a limit at the line) and TL BROKEN trades (in at the price
when the alert went out, filled on the next candle) - with the same exits
(COINDCX_DEMO_KINDS). Since 2026-11-08 the rules are lakky's
"so far final strategy" from his journal (Signals, Fib alerts, CRYPTO 1D):

- a limit order at the alert's entry with the alert's stop, filled within
  COINDCX_DEMO_FILL_DAYS (20) days or cancelled;
- Exit at 1.5R with Trail TP: at 1.5R the stop locks at +1.5R and the target steps
  +0.25R; the stop then trails 0.5R behind the highest target reached (never under
  +1.5R). Move SL "SL shift": at +1R the stop goes to +0.75R. Held till the stop -
  no time limit. A moved stop counts from the next candle; a candle touching the
  stop is the stop (the journal's tgtScore);
- sized like the journal's Demo account: risk = min(COINDCX_DEMO_RISK (75),
  balance); position = risk / stop distance; above COINDCX_DEMO_MAX_LEVERAGE (20x)
  the trade is taken at the cap, so it risks less;
- a real account has to hold the margin of every working order (position / max
  leverage): an order that does not fit is SKIPPED (the journal's demo has no
  such limit);
- graded on Bitunix 1m candles (the alerts' own feed); stops slip 0.05%; every
  trade pays COINDCX_DEMO_ROUND_TRIP_COST_PCT (CoinDCX 0.02% maker in + 0.05%
  taker out + 18% GST = 0.0826%).

Research: research/coindcx_strategy_backtest.py (part coindcx-strategy).

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

import requests

import bitunix_data
import config
import fib_trendline_trades as trades
import scanner

STATE_FILE = Path(__file__).with_name(os.getenv("VICTUS_COINDCX_DEMO_STATE_FILE", "coindcx_demo_state.json"))
RECORDS_FILE = Path(__file__).with_name(os.getenv("VICTUS_FIB_TL_RECORDS_FILE", "fib_trendline_alert_records.jsonl"))
WEBHOOK_ENV = "DISCORD_COINDCX_DEMO_WEBHOOK_URL"
FALLBACK_WEBHOOK_ENV = "DISCORD_ENTRY_CONFIRM_CRYPTO_WEBHOOK_URL"
WAIT_SECONDS = config.COINDCX_DEMO_FILL_DAYS * 86400
ACTIVE = ("pending", "open")
CLOSED = ("won", "lost", "cancelled", "skipped")
DISCORD_LIMIT = 1900


# ---------------------------------------------------------------- selection

def coindcx_pair(symbol):
    """Watchlist symbol -> CoinDCX USDT futures pair: BTCUSD -> B-BTC_USDT,
    1000PEPEUSD -> B-1000PEPE_USDT (CoinDCX's own base, research/out/coindcx)."""
    return f"B-{symbol[:-3]}_USDT" if symbol.endswith("USD") else None


def kind_of(record):
    """fib / trendline (a touch) / break (TL BROKEN)."""
    return "break" if record.get("broken") else record.get("kind")


def label(record):
    """The alert's name on Discord: FIB L3, S TL, R TL BROKEN."""
    if record.get("kind") == "fib":
        return f"FIB {record.get('level') or 'L3'}"
    line = "S" if record.get("line") in (0, "0", "support") else "R"
    return f"{line} TL BROKEN" if record.get("broken") else f"{line} TL"


def eligible(record, started_ts):
    """A 1D crypto fib or trendline alert, on a coin CoinDCX lists, sent after the demo started."""
    if not isinstance(record, dict):
        return False
    plan = record.get("plan")
    try:
        ok = (kind_of(record) in config.COINDCX_DEMO_KINDS
              and record.get("kind") in ("fib", "trendline")
              and record.get("market") == "crypto"
              and str(record.get("tf", "")).lower() in config.COINDCX_DEMO_TIMEFRAMES
              and record.get("symbol") in config.CRYPTO_WATCHLIST
              and (record.get("kind") != "fib" or (record.get("level") or "L3") in config.COINDCX_DEMO_LEVELS)
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
    if balance <= 0:            # an empty account takes no orders (weekly audit 2026-11-08)
        risk = position = leverage = 0.0
        capped = False
    else:
        risk, position, leverage, capped = size(balance, entry, sl)
    margin = position / config.COINDCX_DEMO_MAX_LEVERAGE
    free = balance - margin_in_use(state)
    tp_r = config.COINDCX_DEMO_TARGET_R
    order = {
        "id": record["id"], "symbol": record["symbol"], "pair": coindcx_pair(record["symbol"]),
        "side": plan["side"], "kind": kind_of(record), "label": label(record),
        "level": (record.get("level") or "L3") if record.get("kind") == "fib" else None, "tf": "1D",
        # a TL BROKEN trade goes in at market: filled on the next candle, at the alert's price
        "market_fill": plan.get("fill") == "market",
        "entry": entry, "sl": sl, "tp": entry + tp_r * risk_dist if long else entry - tp_r * risk_dist,
        "stop_pct": risk_dist / entry * 100, "sent_ts": int(float(record["sent_ts"])),
        "placed_ts": int(now), "risk": round(risk, 4), "position": round(position, 2),
        "leverage": round(leverage, 3), "capped": capped, "margin": round(margin, 2),
        "status": "pending", "checked_until": (int(float(record["sent_ts"])) // 60 + 1) * 60,
        # the trade's walk, in R: best move so far, the moved stop (None = the alert's), next target
        "best_r": 0.0, "stop_r": None, "tgt_r": tp_r,
    }
    if balance <= 0:
        order.update(status="skipped", margin=0.0, reason="account empty")
    elif config.COINDCX_DEMO_MARGIN_LIMIT and margin > free + 1e-9:
        order.update(status="skipped", margin=0.0,
                     reason=f"margin {money(margin)} > free {money(max(free, 0))}")
    state["orders"][order["id"]] = order
    state["unposted"].append({"event": "skipped" if order["status"] == "skipped" else "placed",
                              "id": order["id"], "ts": int(now)})
    return order


def full_stop_r(order):
    """Net R of the alert's own stop: slip and fees included, a little worse than -1."""
    plan = {"side": order["side"], "entry": order["entry"], "sl": order["sl"]}
    return trades.stop_r(plan) - config.COINDCX_DEMO_ROUND_TRIP_COST_PCT / order["stop_pct"]


def moved_stop_r(order, level_r):
    """Net R of a moved stop at +level_r (the journal's tgtScore exit): slip and fees off."""
    sign = 1 if order["side"] == "long" else -1
    risk_pct = order["stop_pct"]
    return (level_r - (1 + sign * level_r * risk_pct / 100) * trades.SL_FILL_SLIPPAGE_PCT / risk_pct
            - config.COINDCX_DEMO_ROUND_TRIP_COST_PCT / risk_pct)


def stop_price(order):
    if order.get("stop_r") is None:
        return order["sl"]
    sign = 1 if order["side"] == "long" else -1
    return order["entry"] * (1 + sign * order["stop_r"] * order["stop_pct"] / 100)


def move_r(order, price):
    sign = 1 if order["side"] == "long" else -1
    return sign * (price - order["entry"]) / order["entry"] * 100 / order["stop_pct"]


def raise_stop(state, order, level_r, why, ts):
    if order.get("stop_r") is None or level_r > order["stop_r"] + 1e-9:
        order.update(stop_r=round(level_r, 6), stop_why=why)
        state["unposted"].append({"event": "stop", "id": order["id"], "ts": int(ts), "r": order["stop_r"], "why": why})


def apply_best(state, order, ts):
    """Journal Exit at 1.5R + Move SL + Trail TP: each target reached locks the stop at
    max(first target, target - gap) and steps the target up; at +SHIFT_AT R the stop
    goes to +SHIFT_TO R. A stop moved here counts from the next candle."""
    first, step_r, gap = config.COINDCX_DEMO_TARGET_R, config.COINDCX_DEMO_TRAIL_STEP_R, config.COINDCX_DEMO_TRAIL_GAP_R
    best = order["best_r"]
    while best >= order["tgt_r"] - 1e-9:
        raise_stop(state, order, max(first, order["tgt_r"] - gap), "Trail TP", ts)
        order["tgt_r"] = round(order["tgt_r"] + step_r, 6)
    at, to = config.COINDCX_DEMO_SHIFT_AT_R, config.COINDCX_DEMO_SHIFT_TO_R
    if at and at < first and best >= at - 1e-9:
        raise_stop(state, order, to, "SL shift", ts)


def close(state, order, status, ts, r=None, why=None):
    order.update(status=status, exit_ts=int(ts))
    if r is not None:
        pnl = order["risk"] * r
        if state["balance"] + pnl < 0:
            pnl = -state["balance"]
        state["balance"] = round(state["balance"] + pnl, 4)
        order.update(r=round(r, 4), pnl=round(pnl, 4), balance_after=state["balance"], exit_why=why)
    state["unposted"].append({"event": status, "id": order["id"], "ts": int(ts)})


def stopped(state, order, ts):
    if order.get("stop_r") is None:
        close(state, order, "lost", ts, full_stop_r(order), "SL")
    else:
        r = moved_stop_r(order, order["stop_r"])
        close(state, order, "won" if r > 0 else "lost", ts, r, order.get("stop_why"))


def step(state, order, candle, width=60):
    """Advance one order by one closed candle [ts, open, high, low, close] of `width` seconds."""
    ts, _o, h, l, c = candle[0], candle[1], candle[2], candle[3], candle[4]
    if ts < order["checked_until"]:
        return
    order["checked_until"] = int(ts) + width
    for key, value in (("best_r", 0.0), ("stop_r", None), ("tgt_r", config.COINDCX_DEMO_TARGET_R)):
        order.setdefault(key, value)       # orders placed before 2026-11-08
    long = order["side"] == "long"
    hit = lambda price: (l <= price) if long else (h >= price)
    if order["status"] == "pending":
        if ts >= order["sent_ts"] + WAIT_SECONDS:
            close(state, order, "cancelled", ts)
            return
        if hit(order["entry"]) or order.get("market_fill"):
            order.update(status="open", fill_ts=int(ts))
            state["unposted"].append({"event": "filled", "id": order["id"], "ts": int(ts)})
            if hit(order["sl"]):      # filled and stopped in the same candle
                stopped(state, order, ts)
                return
            # on the fill candle only its close is known to come after the fill
            order["best_r"] = max(0.0, move_r(order, c))
            apply_best(state, order, ts)
        return
    if order["status"] == "open":
        if hit(stop_price(order)):
            stopped(state, order, ts)
            return
        order["best_r"] = max(order["best_r"], move_r(order, h if long else l))
        apply_best(state, order, ts)


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
    fresh = {}
    for r in records:              # one order per alert id, even if a line is on file twice
        if eligible(r, state["started_ts"]) and r["id"] not in known:
            fresh.setdefault(r["id"], r)
    new = sorted(fresh.values(), key=lambda r: float(r["sent_ts"]))
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


def event_line(order, event, e=None):
    e = e or {}
    side = "BUY" if order["side"] == "long" else "SELL"
    name = order.get("label") or f"FIB {order['level']}"      # orders placed before 2026-11-08: fibs
    head = f"**{coin(order['symbol'])} · {name} · {side}**"
    p = scanner.price_text
    if event == "placed":
        cap = " (capped)" if order["capped"] else ""
        how = "Market" if order.get("market_fill") else "Limit"
        return (f"🧪 {head} · order placed\n"
                f"{how} {p(order['entry'])} · SL {p(order['sl'])} ({order['stop_pct']:.2f}%) · TP {p(order['tp'])} ({config.COINDCX_DEMO_TARGET_R:g}R, then trails)\n"
                f"Size {money(order['position'])} · {order['leverage']:.1f}x{cap} · margin {money(order['margin'])} · risk {money(order['risk'])}")
    if event == "skipped":
        return f"⏭️ {head} · skipped: {order.get('reason', 'no margin')}"
    if event == "filled":
        return f"📥 {head} · filled at {p(order['entry'])}"
    if event == "cancelled":
        return f"⌛ {head} · cancelled, no fill in {config.COINDCX_DEMO_FILL_DAYS} days"
    if event == "stop":
        what = "TP reached, stop locked" if e.get("why") == "Trail TP" else "stop moved"
        return f"🔒 {head} · {what} at {e['r']:+.2f}R"
    if event in ("won", "lost"):
        icon = "✅" if event == "won" else "🛑"
        why = {"SL": "SL hit", "SL shift": "stopped at +0.75R", "Trail TP": "trailing stop hit"}.get(order.get("exit_why"), "closed")
        return f"{icon} {head} · {why} · {money(order['pnl'])} ({order['r']:+.2f}R) · balance {money(order['balance_after'])}"
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


def digest_lines(state, now):
    """[(line, event or None)] for the unposted events: a title, one line each, the account."""
    if not state["unposted"]:
        return []
    stamp = datetime.fromtimestamp(now, scanner.IST).strftime("%d %b %H:%M IST")
    lines = [(f"**CoinDCX demo · 1D fib + TL** · {stamp} · no real orders", None)]
    for e in sorted(state["unposted"], key=lambda e: e["ts"]):
        order = state["orders"].get(e["id"])
        lines.append((event_line(order, e["event"], e) if order else None, e))
    lines.append((summary(state), None))
    return lines


def digest(state, now):
    return "\n".join(line for line, _ in digest_lines(state, now) if line)


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
    """True when Discord took it, False when it failed (kept for the next tick),
    None when no channel is set up (nowhere to post: the events are dropped)."""
    env = WEBHOOK_ENV if scanner.get_env_or_config(WEBHOOK_ENV, "") else FALLBACK_WEBHOOK_ENV
    if not scanner.get_env_or_config(env, ""):
        return None
    sent = False
    for part in chunks(text):
        try:
            sent = scanner.send_discord_message(part.rstrip(), webhook_env_name=env, webhook_config_value="")
        except requests.RequestException as error:     # weekly audit 2026-11-01: it used to raise
            print(f"coindcx demo: Discord post failed: {str(error)[:80]}")
            sent = False
        if not sent:
            return False
    return sent


def deliver(state, now, save=None):
    """Post the digest a message at a time; each message's events are dropped once
    Discord takes it (and the state saved), so a later failure, or the run being
    cancelled, never posts them twice. A failed post leaves the rest for the next tick.
    Weekly audit 2026-11-08: one failed post used to raise past save_state, and a
    digest split in two re-posted its first half on every failure of the second."""
    lines = digest_lines(state, now)
    parts, cur, cur_events = [], [], []
    for line, event in lines:
        if not line:
            if event:
                cur_events.append(event)          # its order is gone: nothing to say
            continue
        if cur and sum(len(x) + 1 for x in cur) + len(line) + 1 > DISCORD_LIMIT:
            parts.append((cur, cur_events))
            cur, cur_events = [], []
        cur.append(line)
        if event:
            cur_events.append(event)
    if cur:
        parts.append((cur, cur_events))
    for text_lines, events in parts:
        result = send("\n".join(text_lines))
        if result is None:
            print("coindcx demo: no Discord channel set up - events not posted")
            state["unposted"] = []
            return False
        if not result:
            return False
        done = {id(e) for e in events}
        state["unposted"] = [e for e in state["unposted"] if id(e) not in done]
        if save:
            save(state)
    return True


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
        deliver(state, now, save_state)
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
    lines = [f"**CoinDCX demo · 1D fib + TL** · since {datetime.fromtimestamp(state['started_ts'], scanner.IST):%d %b %H:%M IST}",
             summary(state)]
    for o in sorted(state["orders"].values(), key=lambda o: o["sent_ts"]):
        when = datetime.fromtimestamp(o["sent_ts"], scanner.IST).strftime("%d %b")
        side = "BUY" if o["side"] == "long" else "SELL"
        tail = f"{money(o['pnl'])} ({o['r']:+.2f}R)" if "pnl" in o else o["status"]
        name = o.get("label") or o["level"]
        lines.append(f"{when} {coin(o['symbol'])} {name} {side} · {o['status']} · {tail}")
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
