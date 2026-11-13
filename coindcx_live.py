"""CoinDCX LIVE account: 1D crypto trendline alerts as REAL futures orders.

lakky, 2026-11-13 (decision card "Run this TL setup on CoinDCX for a week: real money or
demo?" -> "Real money, full setup as on screen"). His journal Signals setup:
Trendline alerts, CRYPTO 1D, all coins, type All (S / R TL touches and SP / RS TL BR),
SL "Wick or body" at least 0.75% past entry, Exit 1.5R with Trail TP (+0.25R steps, stop
0.5R behind, locked at +1.5R), SL shift +1R -> +0.75R, held till the stop, every BTC day.
The backtest (research/journal_tl_setup_backtest.py, PR #89) said about -0.07R a trade
over Jan 2025 - Nov 2026; he chose to run it for a week anyway.

OFF unless BOTH are set: the repository variable VICTUS_COINDCX_LIVE=1 and the secrets
COINDCX_API_KEY / COINDCX_API_SECRET (a futures-trading key, NO withdrawal permission,
NOT bound to an IP - GitHub's runners change IP). With the flag on and no key it runs
as a dry run: it prints the orders it would place and sends nothing to CoinDCX.

Where it runs: CoinDCX locks every API key to one IPv4 address, so not on GitHub's
runners. victus2034/trading-journal's coindcx-live.yml runs it on lakky's AWS Lightsail
server (self-hosted runner "aws", static IP, the same key the CoinDCX import uses), with
--remote (alerts read from this repo's runtime-state branch), every ~2 minutes.

What it does every tick:
  1. a new 1D crypto trendline alert (touch or break, sent in the last
     COINDCX_LIVE_MAX_ALERT_AGE seconds, inside the live window) becomes an order:
     - stop = the wick-or-body rule on Bitunix daily candles closed before the alert;
       none 0.75% away -> skipped
     - touch: limit at the line's price; break: market
     - quantity = COINDCX_LIVE_RISK / stop distance, rounded down to the instrument's
       step; under the minimum -> the minimum if that risks <= 2x the plan, else skipped
     - leverage = min(COINDCX_LIVE_MAX_LEVERAGE, the instrument's max)
     - skipped while that coin already has a bot order or position, at
       COINDCX_LIVE_MAX_OPEN active trades, or once the loss so far reaches
       COINDCX_LIVE_MAX_LOSS (kill switch)
  2. a filled order gets an exchange stop-market at its stop (create_tpsl)
  3. an open trade's best move is read from Bitunix 1m candles; the journal's walk
     (coindcx_demo.apply_best) moves the stop, and the exchange stop is replaced
  4. a position that is gone is closed in the state (exit = the stop it had)
  5. a limit not filled in COINDCX_DEMO_FILL_DAYS days is cancelled
Everything that happened is posted to the CoinDCX demo channel, marked LIVE.

  python coindcx_live.py --tick [--dry-run]
  python coindcx_live.py --report
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import bitunix_data
import coindcx_demo as demo
import config
import scanner

BASE = "https://api.coindcx.com"
STATE_FILE = Path(__file__).with_name(os.getenv("VICTUS_COINDCX_LIVE_STATE_FILE", "coindcx_live_state.json"))
DAY = 86400
ACTIVE = ("pending", "open")


# ---------------------------------------------------------------- the exchange

class CoinDCX:
    """The few futures endpoints the bot needs (CoinDCX Futures API: HMAC-SHA256 of the
    compact JSON body with the secret, in X-AUTH-SIGNATURE; the key in X-AUTH-APIKEY)."""

    def __init__(self, key, secret, session=None):
        # The key is locked to the server's IPv4 address: never reach CoinDCX over IPv6.
        import socket
        import urllib3.util.connection
        urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET
        self.key, self.secret = key, secret.encode()
        self.http = session or requests.Session()

    def post(self, path, body):
        body = dict(body, timestamp=int(time.time() * 1000))
        raw = json.dumps(body, separators=(",", ":"))
        sig = hmac.new(self.secret, raw.encode(), hashlib.sha256).hexdigest()
        r = self.http.post(BASE + path, data=raw, timeout=20, headers={
            "Content-Type": "application/json", "X-AUTH-APIKEY": self.key, "X-AUTH-SIGNATURE": sig})
        if r.status_code >= 400:
            raise RuntimeError(f"CoinDCX {path}: HTTP {r.status_code} {r.text[:200]}")
        return r.json()

    def instrument(self, pair):
        r = self.http.get(BASE + "/exchange/v1/derivatives/futures/data/instrument", timeout=20,
                          params={"pair": pair, "margin_currency_short_name": config.COINDCX_LIVE_MARGIN_CCY})
        r.raise_for_status()
        return r.json().get("instrument") or {}

    def create_order(self, pair, side, order_type, qty, leverage, price=None):
        order = {"side": side, "pair": pair, "order_type": order_type, "total_quantity": qty,
                 "leverage": leverage, "notification": "no_notification",
                 "margin_currency_short_name": config.COINDCX_LIVE_MARGIN_CCY}
        if order_type == "limit_order":
            order.update(price=price, time_in_force="good_till_cancel", hidden=False, post_only=False)
        got = self.post("/exchange/v1/derivatives/futures/orders/create", {"order": order})
        return got[0] if isinstance(got, list) else got

    def cancel(self, order_id):
        return self.post("/exchange/v1/derivatives/futures/orders/cancel", {"id": order_id})

    def open_orders(self):
        got = self.post("/exchange/v1/derivatives/futures/orders",
                        {"status": "open", "side": "buy,sell", "page": "1", "size": "100",
                         "margin_currency_short_name": [config.COINDCX_LIVE_MARGIN_CCY]})
        return got if isinstance(got, list) else []

    def positions(self):
        got = self.post("/exchange/v1/derivatives/futures/positions",
                        {"page": "1", "size": "100", "margin_currency_short_name": [config.COINDCX_LIVE_MARGIN_CCY]})
        return {p["pair"]: p for p in (got if isinstance(got, list) else []) if p.get("pair")}

    def set_stop(self, position_id, stop):
        self.post("/exchange/v1/derivatives/futures/positions/cancel_all_open_orders_for_position", {"id": position_id})
        return self.post("/exchange/v1/derivatives/futures/positions/create_tpsl", {
            "id": position_id, "stop_loss": {"stop_price": stop, "order_type": "stop_market"}})


class DryRun:
    """No key: every call is printed and answered as an exchange that never fills."""

    def instrument(self, pair):
        return {}

    def create_order(self, pair, side, order_type, qty, leverage, price=None):
        print(f"coindcx live DRY RUN: {side} {qty} {pair} {order_type} {price or ''} {leverage}x")
        return {"id": f"dry-{pair}-{int(time.time())}", "status": "open"}

    def cancel(self, order_id):
        print(f"coindcx live DRY RUN: cancel {order_id}")

    def open_orders(self):
        return []

    def positions(self):
        return {}

    def set_stop(self, position_id, stop):
        print(f"coindcx live DRY RUN: stop {position_id} -> {stop}")


# ---------------------------------------------------------------- the rules

def wick_body_stop(daily, t0, entry, side, gap_pct=None):
    """His "Wick or body" SL: walking back from the newest daily candle closed before t0,
    the first wick (low for a buy, high for a sell) and the first body (open / close) at
    least gap_pct past the entry; the closer of the two. None when nothing is that far
    (300 candles back). daily = [[ts, o, h, l, c], ...]."""
    gap = config.COINDCX_LIVE_SL_GAP_PCT if gap_pct is None else gap_pct
    s = 1 if side == "long" else -1
    edge = entry * (1 - s * gap / 100)
    wick = body = None
    for c in reversed([c for c in daily if c[0] + DAY <= t0][-300:]):
        w = c[3] if s > 0 else c[2]
        b = min(c[1], c[4]) if s > 0 else max(c[1], c[4])
        if wick is None and ((w <= edge) if s > 0 else (w >= edge)):
            wick = w
        if body is None and ((b <= edge) if s > 0 else (b >= edge)):
            body = b
        if wick is not None and body is not None:
            break
    found = [x for x in (wick, body) if x is not None]
    if not found:
        return None
    return max(found) if s > 0 else min(found)


def eligible(record, state, now):
    if not isinstance(record, dict) or not isinstance(record.get("plan"), dict):
        return False
    try:
        sent = float(record["sent_ts"])
        return (record.get("kind") == "trendline" and record.get("market") == "crypto"
                and str(record.get("tf", "")).lower() == "1d"
                and record.get("symbol") in config.CRYPTO_WATCHLIST
                and record["plan"].get("side") in ("long", "short")
                and bool(record.get("id")) and record["id"] not in state["orders"]
                and state["started_ts"] <= sent < state["until_ts"]
                and now - sent <= config.COINDCX_LIVE_MAX_ALERT_AGE)
    except (KeyError, TypeError, ValueError):
        return False


def step_round(value, step, up=False):
    if not step or step <= 0:
        return value
    n = value / step
    n = math.ceil(n - 1e-9) if up else math.floor(n + 1e-9)
    decimals = max(0, -int(math.floor(math.log10(step)))) if step < 1 else 0
    return round(n * step, decimals + 2)


def quantity(entry, sl, ins, risk=None):
    """(qty, risk taken) or (0, reason)."""
    risk = config.COINDCX_LIVE_RISK if risk is None else risk
    per_unit = abs(entry - sl)
    step = float(ins.get("quantity_increment") or 0)
    least = float(ins.get("min_quantity") or 0)
    qty = step_round(risk / per_unit, step)
    if least and qty < least:
        if least * per_unit <= 2 * risk:
            qty = least
        else:
            return 0, f"min order {least:g} risks {least * per_unit:.2f} > 2x plan"
    if qty <= 0:
        return 0, "quantity rounds to 0"
    notional = float(ins.get("min_notional") or 0)
    if notional and qty * entry < notional:
        qty = step_round(notional / entry, step, up=True)
        if qty * per_unit > 2 * risk:
            return 0, f"min notional {notional:g} risks {qty * per_unit:.2f} > 2x plan"
    return qty, qty * per_unit


# ---------------------------------------------------------------- state

def new_state(now):
    return {"version": 1, "started_ts": int(now), "until_ts": int(now + config.COINDCX_LIVE_DAYS * DAY),
            "orders": {}, "realized": 0.0, "events": []}


def load_state(path=None):
    try:
        state = json.loads((path or STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(state, dict) or "orders" not in state:
        return None
    state.setdefault("events", [])
    return state


def save_state(state, path=None):
    path = path or STATE_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def note(state, text, now):
    print("coindcx live: " + text)
    state["events"].append({"ts": int(now), "text": text})


def daily_candles(symbol, now):
    pair = bitunix_data.bitunix_pair(symbol)
    return bitunix_data.klines(pair, "1d", int(now - 320 * DAY), int(now))


def last_price(symbol):
    return float(bitunix_data.last_price(bitunix_data.bitunix_pair(symbol)))


def btc_move_today(now):
    """BTC's % move from today's 00:00 UTC open to now (Bitunix 15m), or None."""
    day = int(now) - int(now) % DAY
    rows = demo.fetch_candles("BTCUSD", day, int(now), "15m")
    return (rows[-1][4] - rows[0][1]) / rows[0][1] * 100 if rows and rows[0][0] == day else None


def minute_candles(symbol, start, end):
    return demo.fetch_candles(symbol, start, end, "1m")


# ---------------------------------------------------------------- the tick

def place(state, ex, record, now, daily=daily_candles, price_now=last_price, btc_move=btc_move_today):
    plan, symbol = record["plan"], record["symbol"]
    side = plan["side"]
    broken = bool(record.get("broken"))
    pair = demo.coindcx_pair(symbol)
    head = f"{demo.coin(symbol)} {'TL BR' if broken else 'TL'} {'BUY' if side == 'long' else 'SELL'}"
    order = {"id": record["id"], "symbol": symbol, "pair": pair, "side": side, "broken": broken,
             "sent_ts": int(float(record["sent_ts"])), "placed_ts": int(now), "status": "skipped"}
    state["orders"][record["id"]] = order
    active = [o for o in state["orders"].values() if o["status"] in ACTIVE]
    if state["realized"] <= -config.COINDCX_LIVE_MAX_LOSS:
        order["reason"] = f"kill switch: loss so far {state['realized']:.2f}"
    elif len(active) >= config.COINDCX_LIVE_MAX_OPEN:
        order["reason"] = f"{len(active)} trades already active"
    elif any(o["pair"] == pair for o in active):
        order["reason"] = "this coin already has a bot trade"
    elif config.COINDCX_LIVE_BTC_FILTER == "so_far":
        move = btc_move(now)
        if move is None or abs(move) > 1.5:
            order["reason"] = "BTC not sideways today" + ("" if move is None else f" ({move:+.2f}% since 05:30 IST)")
    if order.get("reason"):
        note(state, f"⏭️ {head} skipped: {order['reason']}", now)
        return order
    try:
        entry = price_now(symbol) if broken else float(plan["entry"])
        sl = wick_body_stop(daily(symbol, now), order["sent_ts"], entry, side)
        if sl is None:
            order["reason"] = "no wick or body 0.75% past entry"
            note(state, f"⏭️ {head} skipped: {order['reason']}", now)
            return order
        ins = ex.instrument(pair)
        qty, risk = quantity(entry, sl, ins)
        if not qty:
            order["reason"] = risk
            note(state, f"⏭️ {head} skipped: {risk}", now)
            return order
        lev = min(config.COINDCX_LIVE_MAX_LEVERAGE, float(ins.get("max_leverage_long" if side == "long" else "max_leverage_short")
                                                           or ins.get("max_leverage") or config.COINDCX_LIVE_MAX_LEVERAGE))
        tick_size = float(ins.get("price_increment") or 0)
        price = step_round(entry, tick_size) if tick_size else entry
        got = ex.create_order(pair, "buy" if side == "long" else "sell",
                              "market_order" if broken else "limit_order", qty, int(lev), None if broken else price)
    except Exception as error:  # noqa: BLE001 - one alert must not stop the rest
        order.update(status="error", reason=str(error)[:200])
        note(state, f"⚠️ {head} order FAILED: {order['reason']}", now)
        return order
    stop_pct = abs(entry - sl) / entry * 100
    order.update(status="pending", exchange_id=got.get("id"), entry=price, sl=sl, qty=qty, risk=round(risk, 4),
                 leverage=int(lev), stop_pct=stop_pct, best_r=0.0, stop_r=None, tgt_r=config.COINDCX_DEMO_TARGET_R,
                 checked_until=int(now) // 60 * 60)
    p = scanner.price_text
    note(state, f"🟢 **{head}** · {'market' if broken else 'limit ' + p(price)} · qty {qty:g} · SL {p(sl)} ({stop_pct:.2f}%) · "
                f"risk {risk:.2f} USDT · {int(lev)}x", now)
    return order


def stop_level(order):
    return demo.stop_price(order)


def manage(state, ex, now, positions, open_ids, candles=minute_candles):
    p = scanner.price_text
    for o in [o for o in state["orders"].values() if o["status"] in ACTIVE]:
        head = f"{demo.coin(o['symbol'])} {'TL BR' if o.get('broken') else 'TL'} {'BUY' if o['side'] == 'long' else 'SELL'}"
        pos = positions.get(o["pair"])
        held = pos is not None and float(pos.get("active_pos") or 0) != 0
        try:
            if o["status"] == "pending":
                if held:
                    o.update(status="open", fill_ts=int(now), fill_price=float(pos.get("avg_price") or o["entry"]),
                             position_id=pos.get("id"))
                    ex.set_stop(o["position_id"], step_round(o["sl"], 0))
                    note(state, f"📥 **{head}** filled at {p(o['fill_price'])} · stop {p(o['sl'])} set", now)
                elif o.get("exchange_id") not in open_ids and not str(o.get("exchange_id", "")).startswith("dry-"):
                    o.update(status="closed", exit_ts=int(now), r=None, exit_why="order gone (filled and closed, or cancelled)")
                    note(state, f"❔ **{head}** order no longer open and no position: check CoinDCX", now)
                elif now >= o["sent_ts"] + config.COINDCX_DEMO_FILL_DAYS * DAY:
                    ex.cancel(o["exchange_id"])
                    o.update(status="cancelled", exit_ts=int(now))
                    note(state, f"⌛ **{head}** cancelled, no fill in {config.COINDCX_DEMO_FILL_DAYS} days", now)
                continue
            if not held:
                r = demo.full_stop_r(o) if o.get("stop_r") is None else demo.moved_stop_r(o, o["stop_r"])
                money = o["risk"] * r
                state["realized"] = round(state["realized"] + money, 4)
                o.update(status="closed", exit_ts=int(now), r=round(r, 3), pnl=round(money, 4),
                         exit_why=o.get("stop_why") or "SL")
                note(state, f"{'✅' if r > 0 else '🛑'} **{head}** closed at {o['exit_why']} ≈ {r:+.2f}R "
                            f"({money:+.2f} USDT) · total {state['realized']:+.2f}", now)
                continue
            before = o.get("stop_r")
            for c in candles(o["symbol"], o["checked_until"], now):
                if c[0] + 60 > now:
                    break
                o["checked_until"] = int(c[0]) + 60
                o["best_r"] = max(o["best_r"], demo.move_r(o, c[2] if o["side"] == "long" else c[3]))
            demo.apply_best({"unposted": []}, o, now)
            if o.get("stop_r") != before:
                ex.set_stop(o.get("position_id") or pos.get("id"), stop_level(o))
                note(state, f"🔒 **{head}** stop moved to {o['stop_r']:+.2f}R ({p(stop_level(o))})", now)
            elif not pos.get("stop_loss_trigger") and o.get("position_id"):
                ex.set_stop(o["position_id"], stop_level(o))      # the exchange stop went missing
                note(state, f"🔁 **{head}** stop re-placed at {p(stop_level(o))}", now)
        except Exception as error:  # noqa: BLE001
            note(state, f"⚠️ **{head}** manage FAILED: {str(error)[:160]}", now)


def tick(state, ex, records, now, **hooks):
    manage_hooks = {k: v for k, v in hooks.items() if k == "candles"}
    place_hooks = {k: v for k, v in hooks.items() if k in ("daily", "price_now", "btc_move")}
    try:
        positions = ex.positions()
        open_ids = {o.get("id") for o in ex.open_orders()}
    except Exception as error:  # noqa: BLE001 - no view of the account: place nothing new either
        note(state, f"⚠️ account read FAILED, nothing done: {str(error)[:160]}", now)
        return state
    manage(state, ex, now, positions, open_ids, **manage_hooks)
    fresh = {}
    for r in records:
        if eligible(r, state, now):
            fresh.setdefault(r["id"], r)
    for record in sorted(fresh.values(), key=lambda r: float(r["sent_ts"])):
        place(state, ex, record, now, **place_hooks)
    return state


def post(state):
    if not state["events"]:
        return
    text = "**CoinDCX LIVE · 1D trendlines · REAL orders**\n" + "\n".join(e["text"] for e in state["events"])
    if demo.send(text) is not False:
        state["events"] = []


RECORDS_URL = ("https://raw.githubusercontent.com/victus2034/victus-indicator-strategy/"
               "scanner-runtime-state/fib_trendline_alert_records.jsonl")


def remote_records(url=RECORDS_URL):
    """The alert records from the runtime-state branch, for a machine that is not the
    GitHub runner (CoinDCX keys need a fixed IP). GITHUB_TOKEN is sent when set (a
    private repo); a failed read gives [] - nothing new is placed, open trades still managed."""
    headers = {"Authorization": f"token {os.environ['GITHUB_TOKEN']}"} if os.getenv("GITHUB_TOKEN") else {}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
    except requests.RequestException as error:
        print(f"coindcx live: alert records unavailable: {str(error)[:120]}")
        return []
    out = []
    for line in r.text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def run_tick(now=None, dry_run=False, remote=False):
    now = int(time.time()) if now is None else int(now)
    if not config.COINDCX_LIVE_ENABLED:
        print("coindcx live is off (repository variable VICTUS_COINDCX_LIVE)")
        return None
    key, secret = os.getenv("COINDCX_API_KEY", ""), os.getenv("COINDCX_API_SECRET", "")
    ex = CoinDCX(key, secret) if key and secret and not dry_run else DryRun()
    state = load_state()
    if state is None:
        state = new_state(now)
        note(state, f"started: trades 1D TL alerts until {datetime.fromtimestamp(state['until_ts'], scanner.IST):%d %b %H:%M IST}, "
                    f"risk {config.COINDCX_LIVE_RISK:g} USDT a trade"
                    + ("" if isinstance(ex, CoinDCX) else " (DRY RUN: no API key)"), now)
    tick(state, ex, remote_records() if remote else demo.load_records(), now)
    if not dry_run:
        post(state)
        save_state(state)
    return state


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tick", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--remote", action="store_true",
                    help="read the alerts from GitHub (a PC or server with the key's fixed IP)")
    a = ap.parse_args(argv)
    if a.tick:
        run_tick(dry_run=a.dry_run, remote=a.remote)
    if a.report:
        state = load_state()
        print(json.dumps(state, indent=1) if state else "coindcx live: no state yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
