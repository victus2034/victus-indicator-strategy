"""CoinDCX LIVE account: 1D crypto trendline BREAK alerts as REAL futures orders.

Since 2026-11-22 (lakky, decision card "Breaks only + own SL + kill fix"; replay in
research/live_upgrade_replay.py, Jan 2025 - Nov 2026 under the account rules below):
  - TL BROKEN alerts only (+0.17R a trade); touches lost -0.22R (0.00R with the 1h confirm), so they
    are not traded and a touch still waiting for its 1h candle is called off.
    VICTUS_COINDCX_LIVE_TOUCHES=1 trades touches again, as below.
  - a break's stop stays the wick-or-body rule. VICTUS_COINDCX_LIVE_BREAK_SL=alert uses the alert's own
    SL, past the candle before the break candle: better a trade (+0.21R vs +0.18R), but its wider stops
    hold the 5 slots longer, so fewer trades (277 vs 393) and less in total (+58R vs +69R)
  - the kill switch counts from the best point: no new trade once the realized P&L is
    COINDCX_LIVE_MAX_DRAWDOWN_R (15) x COINDCX_LIVE_RISK below its peak (the replay's worst: 13.2R).
    The loss-from-start rule (10 USDT until then) is off unless VICTUS_COINDCX_LIVE_MAX_LOSS is set.

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
       none 0.75% away -> skipped. With BREAK_SL=alert a break uses the alert's own SL when it is at
       least COINDCX_LIVE_SL_GAP_PCT past the price, else the wick-or-body rule
     - touch: no order yet - it waits for a closed 1h candle that trades the line (at the
       line's price at that hour) and closes back on the trade's side, then enters at
       market (lakky, 2026-11-16; COINDCX_LIVE_TOUCH_ENTRY=limit is the old limit at the
       line). The wait ends when a daily candle closes through the line or after
       COINDCX_DEMO_FILL_DAYS days. break: market
     - quantity = COINDCX_LIVE_RISK / stop distance, rounded down to the instrument's
       step; under the minimum -> the minimum if that risks <= 2x the plan, else skipped
     - leverage = min(COINDCX_LIVE_MAX_LEVERAGE, the instrument's max, 70 / stop %) so the stop
       is always closer than the liquidation price
     - skipped while that coin already has a bot order or position, at
       COINDCX_LIVE_MAX_OPEN active trades, or once the kill switch trips (see above)
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
import delta_live
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

    def exit(self, position_id):
        """Close the whole position at market."""
        return self.post("/exchange/v1/derivatives/futures/positions/exit", {"id": position_id})

    def set_stop(self, position_id, stop):
        try:        # 422 "No open orders found" when there is no stop yet: that used to stop the stop going in
            self.post("/exchange/v1/derivatives/futures/positions/cancel_all_open_orders_for_position", {"id": position_id})
        except RuntimeError as error:
            if "422" not in str(error):
                raise
        return self.post("/exchange/v1/derivatives/futures/positions/create_tpsl", {
            "id": position_id, "stop_loss": {"stop_price": stop, "order_type": "stop_market"}})


class Router:
    """CoinDCX and Delta as one exchange: a "DELTA:" pair (or an order id "product:order") goes to Delta."""

    def __init__(self, coindcx, delta):
        self.dcx, self.delta = coindcx, delta

    def venue(self, pair_or_id):
        return self.delta if str(pair_or_id).startswith(delta_live.PREFIX) or ":" in str(pair_or_id) else self.dcx

    def instrument(self, pair):
        return self.venue(pair).instrument(pair)

    def create_order(self, pair, *args, **kwargs):
        return self.venue(pair).create_order(pair, *args, **kwargs)

    def cancel(self, order_id):
        return self.venue(order_id).cancel(order_id)

    def open_orders(self):
        return self.dcx.open_orders() + self.delta.open_orders()

    def positions(self):
        return {**self.dcx.positions(), **self.delta.positions()}

    def set_stop(self, position_id, stop):
        return self.venue(position_id).set_stop(position_id, stop)

    def exit(self, position_id):
        return self.venue(position_id).exit(position_id)


def venue_pair(symbol):
    """Where a new trade goes: Delta for a Delta-listed coin when the Delta key is set, else CoinDCX."""
    if delta_on() and symbol in config.DELTA_LISTED_SYMBOLS:
        return delta_live.pair_for(symbol)
    return demo.coindcx_pair(symbol)


def delta_on():
    return config.LIVE_DELTA and bool(os.getenv("DELTA_API_KEY") and os.getenv("DELTA_API_SECRET"))


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

    def exit(self, position_id):
        print(f"coindcx live DRY RUN: exit {position_id} at market")


# ---------------------------------------------------------------- the rules

LIQUIDATION_ROOM = 70.0     # leverage x stop % stays under this, so the stop is hit before liquidation


def wick_body_stop(daily, t0, entry, side, gap_pct=None):
    """His "Wick or body" SL: walking back from the newest daily candle closed before t0,
    the first wick (low for a buy, high for a sell) and the first body (open / close) at
    least gap_pct past the entry; the closer of the two. None when nothing is that far
    (300 candles back). daily = [[ts, o, h, l, c], ...]."""
    gap = config.COINDCX_LIVE_SL_GAP_PCT if gap_pct is None else gap_pct
    s = 1 if side == "long" else -1
    edge = entry * (1 - s * gap / 100)
    wick = body = None
    for c in reversed([c for c in daily if c[0] + DAY <= t0 and min(c[1:5]) > 0][-300:]):
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
        entry = float(record["plan"]["entry"])          # a record with no usable entry used to crash the tick
        return (math.isfinite(sent) and math.isfinite(entry) and entry > 0
                and record.get("kind") == "trendline" and record.get("market") == "crypto"
                and (bool(record.get("broken")) or config.COINDCX_LIVE_TOUCHES)
                and str(record.get("tf", "")).lower() == "1d"
                and record.get("symbol") in config.CRYPTO_WATCHLIST
                and record["plan"].get("side") in ("long", "short")
                and bool(record.get("id")) and record["id"] not in state["orders"]
                and state["started_ts"] <= sent
                and (state.get("until_ts") is None or sent < state["until_ts"])
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
    return {"version": 1, "started_ts": int(now), "until_ts": int(now + config.COINDCX_LIVE_DAYS * DAY) if config.COINDCX_LIVE_DAYS > 0 else None,
            "orders": {}, "realized": 0.0, "events": []}


class StateUnreadable(RuntimeError):
    """The state file is there but cannot be read: never start over on top of it."""


def load_state(path=None):
    """The saved state, or None when there is no state file yet (the first tick).

    Weekly audit 2026-11-22: an unreadable file (cut short, a merge-conflict marker) used to
    read as "no state" - the bot started fresh and saved over it, forgetting every open
    trade: no trailing stop, the same coin traded twice, the loss so far (kill switch) at 0."""
    path = path or STATE_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as error:
        raise StateUnreadable(f"{path.name}: {error}") from error
    try:
        state = json.loads(text)
    except json.JSONDecodeError as error:
        raise StateUnreadable(f"{path.name} is not valid JSON ({error})") from error
    if not isinstance(state, dict) or not isinstance(state.get("orders"), dict):
        raise StateUnreadable(f"{path.name} has no orders")
    state.setdefault("events", [])
    state.setdefault("realized", 0.0)
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
    """Bitunix daily candles, bad rows dropped: a zero low used to make the wick stop 0 (weekly audit 2026-11-22)."""
    pair = bitunix_data.bitunix_pair(symbol)
    return scanner.clean_candles(bitunix_data.klines(pair, "1d", int(now - 320 * DAY), int(now)))


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
    pair = venue_pair(symbol)
    head = f"{demo.coin(symbol)} {'TL BR' if broken else 'TL'} {'BUY' if side == 'long' else 'SELL'}"
    order = {"id": record["id"], "symbol": symbol, "pair": pair, "side": side, "broken": broken,
             "sent_ts": int(float(record["sent_ts"])), "placed_ts": int(now), "status": "skipped"}
    if broken and config.COINDCX_LIVE_BREAK_SL == "alert":
        order["alert_sl"] = alert_sl(plan)
    state["orders"][record["id"]] = order
    order["reason"] = blocked(state, order, now, btc_move)
    if order["reason"] is None:
        del order["reason"]
    if order.get("reason"):
        note(state, f"⏭️ {head} skipped: {order['reason']}", now)
        return order
    line = None if broken or config.COINDCX_LIVE_TOUCH_ENTRY != "confirm_1h" else line_points(record)
    if line:
        # counts against no limit while it waits; the limits are checked when it confirms
        order.update(status="waiting", line=line, plan_entry=float(plan["entry"]),
                     checked_hour=-(-order["sent_ts"] // 3600) * 3600)
        note(state, f"⏳ {head} near the line {scanner.price_text(line_at(line, now))}: waiting for a 1h candle to hold it", now)
        return order
    return submit(state, ex, order, head, float(plan["entry"]), broken, now, daily, price_now)


def alert_sl(plan):
    """The alert's own stop as a float, or None when the record has no usable one."""
    try:
        sl = float(plan.get("sl"))
    except (TypeError, ValueError):
        return None
    return sl if math.isfinite(sl) and sl > 0 else None


def rules_text():
    """The trading rules in one line: posted once whenever they change (22 Nov: breaks only)."""
    kinds = "1D TL breaks + touches" if config.COINDCX_LIVE_TOUCHES else "1D TL breaks only"
    sl = "alert's SL" if config.COINDCX_LIVE_BREAK_SL == "alert" else "wick/body SL"
    kill = []
    if config.COINDCX_LIVE_MAX_DRAWDOWN_R > 0:
        kill.append(f"{config.COINDCX_LIVE_MAX_DRAWDOWN_R:g}R from the best point")
    if config.COINDCX_LIVE_MAX_LOSS > 0:
        kill.append(f"{config.COINDCX_LIVE_MAX_LOSS:g} lost from the start")
    return f"{kinds}, {sl} on breaks, kill switch " + (" or ".join(kill) if kill else "off")


def drawdown(state):
    """How far the realized P&L sits below its best point so far (the start counts as 0), in money:
    the path is the closed orders' pnl in exit order, the end point state["realized"]."""
    equity = peak = 0.0
    closed = [o for o in state["orders"].values() if isinstance(o.get("pnl"), (int, float)) and o.get("exit_ts")]
    for o in sorted(closed, key=lambda o: o["exit_ts"]):
        equity += o["pnl"]
        peak = max(peak, equity)
    return round(max(peak, state["realized"]) - state["realized"], 4)


def break_stop(order, entry, side):
    """(stop, reason to skip) for a break with the alert's SL. Price already past that stop: the break
    has failed, no trade (the replay drops those too). Closer than COINDCX_LIVE_SL_GAP_PCT (1 break in
    500 in the replay; a stop that close is mostly fees) or no alert SL: (None, None), and the caller
    uses the wick-or-body rule."""
    sl = order.get("alert_sl")
    if sl is None:
        return None, None
    gap = (1 if side == "long" else -1) * (entry - sl) / entry * 100
    if gap <= 0:
        return None, "price already past the alert's stop"
    return (sl, None) if gap >= config.COINDCX_LIVE_SL_GAP_PCT else (None, None)


def blocked(state, order, now, btc_move=btc_move_today):
    """Why a new order may not go in now, or None."""
    active = [o for o in state["orders"].values() if o["status"] in ACTIVE and o is not order]
    dd = drawdown(state)
    if config.COINDCX_LIVE_MAX_DRAWDOWN_R > 0 and dd >= config.COINDCX_LIVE_MAX_DRAWDOWN_R * config.COINDCX_LIVE_RISK - 1e-9:
        return (f"kill switch: {dd:.2f} down from the best point "
                f"(limit {config.COINDCX_LIVE_MAX_DRAWDOWN_R:g}R = {config.COINDCX_LIVE_MAX_DRAWDOWN_R * config.COINDCX_LIVE_RISK:g})")
    if config.COINDCX_LIVE_MAX_LOSS > 0 and state["realized"] <= -config.COINDCX_LIVE_MAX_LOSS:
        return f"kill switch: loss so far {state['realized']:.2f}"
    if len(active) >= config.COINDCX_LIVE_MAX_OPEN:
        return f"{len(active)} trades already active"
    if any(o["symbol"] == order["symbol"] for o in active):
        return "this coin already has a bot trade"
    if config.COINDCX_LIVE_BTC_FILTER == "so_far":
        move = btc_move(now)
        if move is None or abs(move) > 1.5:
            return "BTC not sideways today" + ("" if move is None else f" ({move:+.2f}% since 05:30 IST)")
    return None


def submit(state, ex, order, head, entry, market, now, daily=daily_candles, price_now=last_price):
    """Size and send one order: a market order at the price now, or a limit at `entry`."""
    symbol, side, pair, broken = order["symbol"], order["side"], order["pair"], market
    sending = False
    try:
        entry = price_now(symbol) if market else entry
        sl, why = break_stop(order, entry, side) if order.get("broken") else (None, None)
        if why:
            order.update(status="skipped", reason=why)
            note(state, f"⏭️ {head} skipped: {why}", now)
            return order
        if sl is None:
            sl = wick_body_stop(daily(symbol, now), int(now) if order.get("line") else order["sent_ts"], entry, side)
        if sl is None:
            order.update(status="skipped", reason="no wick or body 0.75% past entry")
            note(state, f"⏭️ {head} skipped: {order['reason']}", now)
            return order
        ins = ex.instrument(pair)
        qty, risk = quantity(entry, sl, ins)
        if not qty:
            order.update(status="skipped", reason=risk)
            note(state, f"⏭️ {head} skipped: {risk}", now)
            return order
        lev = min(config.COINDCX_LIVE_MAX_LEVERAGE, float(ins.get("max_leverage_long" if side == "long" else "max_leverage_short")
                                                           or ins.get("max_leverage") or config.COINDCX_LIVE_MAX_LEVERAGE))
        # liquidation must sit past the stop: at 20x a position is liquidated ~4.5% away, and both
        # HYPE trades of 14-15 Nov (stops 14% and 8% away) were closed by liquidation, not the stop
        lev = max(1, min(lev, int(LIQUIDATION_ROOM / (abs(entry - sl) / entry * 100))))
        tick_size = float(ins.get("price_increment") or 0)
        price = step_round(entry, tick_size) if tick_size else entry
        sending = True
        got = ex.create_order(pair, "buy" if side == "long" else "sell",
                              "market_order" if broken else "limit_order", qty, int(lev), None if broken else price)
    except Exception as error:  # noqa: BLE001 - one alert must not stop the rest
        if sending and isinstance(error, requests.RequestException):
            # Weekly audit 2026-11-22: the order went out and no answer came back (timeout, dropped
            # connection), so it may be on the book. It used to be sent to CoinDCX as well when Delta
            # timed out: two positions, the Delta one with no stop and no bot watching it.
            venue = "Delta" if pair.startswith(delta_live.PREFIX) else "CoinDCX"
            order.update(status="error", reason=f"no answer to the order ({str(error)[:120]}): check {venue}")
            note(state, f"⚠️ {head} order UNCONFIRMED: {order['reason']}", now)
            return order
        if pair.startswith(delta_live.PREFIX):
            # Delta refused (e.g. too little margin in the Delta wallet): the trade goes to CoinDCX instead
            order["pair"] = demo.coindcx_pair(symbol)
            note(state, f"↪️ {head} Delta refused ({str(error)[:120]}), sent to CoinDCX", now)
            return submit(state, ex, order, head, entry, market, now, daily=daily, price_now=price_now)
        order.update(status="error", reason=str(error)[:200])
        note(state, f"⚠️ {head} order FAILED: {order['reason']}", now)
        return order
    if not isinstance(got, dict) or not got.get("id"):
        # an order with no id would read as "gone" next tick while it may sit on the book
        order.update(status="error", reason=f"no order id returned ({str(got)[:120]}): check CoinDCX")
        note(state, f"⚠️ {head} order UNCONFIRMED: {order['reason']}", now)
        return order
    stop_pct = abs(entry - sl) / entry * 100
    order.update(status="pending", exchange_id=got.get("id"), entry=price, tick=tick_size, sl=sl, qty=qty, risk=round(risk, 4),
                 leverage=int(lev), stop_pct=stop_pct, best_r=0.0, stop_r=None, tgt_r=config.COINDCX_DEMO_TARGET_R,
                 checked_until=int(now) // 60 * 60)
    p = scanner.price_text
    note(state, f"🟢 **{head}** · {'market' if broken else 'limit ' + p(price)} · qty {qty:g} · SL {p(sl)} ({stop_pct:.2f}%) · "
                f"risk {risk:.2f} USDT · {int(lev)}x", now)
    return order


def line_points(record):
    """[t1, y1, t2, y2] of a touch record's line (its `from` / `to`: price, "YYYY-MM-DD HH:MM" IST), or None."""
    try:
        out = []
        for price, stamp in (record["from"], record["to"]):
            out += [int(datetime.strptime(stamp, "%Y-%m-%d %H:%M").replace(tzinfo=scanner.IST).timestamp()), float(price)]
        return out if out[2] > out[0] and out[1] > 0 and out[3] > 0 else None
    except (KeyError, TypeError, ValueError):
        return None


def line_at(line, ts):
    t1, y1, t2, y2 = line
    return y1 + (y2 - y1) * (ts - t1) / (t2 - t1)


def hour_candles(symbol, start, end):
    return demo.fetch_candles(symbol, start, end, "1h")


CONFIRM_FRESH_SECONDS = 15 * 60     # a confirming candle seen later than this is not chased


def confirm_waiting(state, ex, now, hourly=hour_candles, daily=daily_candles, price_now=last_price, btc_move=btc_move_today):
    """Touch alerts waiting for their 1h candle (research/tl_lower_tf_entry_backtest.py, "confirm 1h, SL day":
    Jan 2025 - Nov 2026 touches -0.21R -> 0.00R a trade, Sep 1 - now -0.30R -> -0.19R)."""
    p = scanner.price_text
    for o in [o for o in state["orders"].values() if o["status"] == "waiting"]:
        head = f"{demo.coin(o['symbol'])} TL {'BUY' if o['side'] == 'long' else 'SELL'}"
        sign = 1 if o["side"] == "long" else -1
        try:
            if not config.COINDCX_LIVE_TOUCHES:
                o.update(status="cancelled", exit_ts=int(now), reason="touch trades are off (breaks only since 22 Nov)")
                note(state, f"⏭️ {head} wait called off: {o['reason']}", now)
                continue
            if now >= o["sent_ts"] + config.COINDCX_DEMO_FILL_DAYS * DAY:
                o.update(status="cancelled", exit_ts=int(now), reason=f"no 1h confirm in {config.COINDCX_DEMO_FILL_DAYS} days")
                note(state, f"⌛ {head} wait over: {o['reason']}", now)
                continue
            for c in hourly(o["symbol"], o["checked_hour"], now):
                end = int(c[0]) + 3600
                if c[0] < o["checked_hour"] or end > now:
                    continue
                o["checked_hour"] = end
                touched = sign * (line_at(o["line"], c[0]) - (c[3] if sign > 0 else c[2])) >= 0
                held = sign * (c[4] - line_at(o["line"], end)) > 0
                if touched and held:
                    if now - end > CONFIRM_FRESH_SECONDS:
                        o.update(status="cancelled", exit_ts=int(now), reason="1h confirm candle seen too late")
                        note(state, f"⏭️ {head} skipped: {o['reason']}", now)
                        break
                    why = blocked(state, o, now, btc_move)
                    if why:
                        o.update(status="skipped", reason=why)
                        note(state, f"⏭️ {head} confirmed but skipped: {why}", now)
                        break
                    note(state, f"🕐 {head} 1h candle held the line {p(line_at(o['line'], end))} (close {p(c[4])})", now)
                    submit(state, ex, o, head, o["plan_entry"], True, now, daily, price_now)
                    break
                day_open = end - DAY
                if end % DAY == 0 and sign * (c[4] - line_at(o["line"], day_open)) < 0:
                    o.update(status="cancelled", exit_ts=int(now), reason="daily close through the line")
                    note(state, f"⏭️ {head} wait over: {o['reason']}", now)
                    break
        except Exception as error:  # noqa: BLE001 - one coin's candles must not stop the rest
            print(f"coindcx live: {head} confirm check failed: {str(error)[:160]}")


def ensure_tick(ex, order):
    """The instrument's price step on the order (orders placed before 16 Nov have none, and an
    unrounded stop is refused by CoinDCX)."""
    if not order.get("tick"):
        order["tick"] = float(ex.instrument(order["pair"]).get("price_increment") or 0)


def stop_level(order):
    """The stop to send: on the instrument's price step, rounded away from price (a price
    off the step is refused by CoinDCX; until 16 Nov the first stop was sent unrounded)."""
    return step_round(demo.stop_price(order), order.get("tick") or 0, up=order["side"] == "short")


def rebase_on_fill(order, fill):
    """Count R from the price actually filled (a market break order fills off the alert's
    price): entry, stop % and risk follow the fill when it is on the right side of the stop."""
    sign = 1 if order["side"] == "long" else -1
    if not fill or sign * (fill - order["sl"]) <= 0 or abs(fill - order["entry"]) < 1e-12:
        return
    order.update(plan_entry=order["entry"], entry=fill, stop_pct=abs(fill - order["sl"]) / fill * 100,
                 risk=round(order["qty"] * abs(fill - order["sl"]), 4))


def seen_gone(order, now):
    """True once an order / position has been missing for LIVE_GONE_GRACE_SECONDS: a fill that the
    exchange's position list has not caught up with yet is not booked as closed."""
    since = order.setdefault("gone_since", int(now))
    return now - since >= config.LIVE_GONE_GRACE_SECONDS


EXIT_RETRY_SECONDS = 300     # a market exit is sent again only if the position is still there after this


def manage(state, ex, now, positions, open_ids, candles=minute_candles):
    p = scanner.price_text
    for o in [o for o in state["orders"].values() if o["status"] in ACTIVE]:
        head = f"{demo.coin(o['symbol'])} {'TL BR' if o.get('broken') else 'TL'} {'BUY' if o['side'] == 'long' else 'SELL'}"
        pos = positions.get(o["pair"])
        held = pos is not None and float(pos.get("active_pos") or 0) != 0
        if held or (o["status"] == "pending" and o.get("exchange_id") in open_ids):
            o.pop("gone_since", None)
        try:
            if o["status"] == "pending":
                if held:
                    o.update(status="open", fill_ts=int(now), fill_price=float(pos.get("avg_price") or o["entry"]),
                             position_id=pos.get("id"))
                    rebase_on_fill(o, o["fill_price"])
                    ensure_tick(ex, o)
                    ex.set_stop(o["position_id"], stop_level(o))
                    o["stop_sent"] = stop_level(o)
                    note(state, f"📥 **{head}** filled at {p(o['fill_price'])} · stop {p(o['sl'])} set", now)
                elif o.get("exchange_id") not in open_ids and not str(o.get("exchange_id", "")).startswith("dry-"):
                    if not seen_gone(o, now):
                        continue
                    o.update(status="closed", exit_ts=int(now), r=None, exit_why="order gone (filled and closed, or cancelled)")
                    note(state, f"❔ **{head}** order no longer open and no position: check CoinDCX", now)
                elif now >= o["sent_ts"] + config.COINDCX_DEMO_FILL_DAYS * DAY:
                    ex.cancel(o["exchange_id"])
                    o.update(status="cancelled", exit_ts=int(now))
                    note(state, f"⌛ **{head}** cancelled, no fill in {config.COINDCX_DEMO_FILL_DAYS} days", now)
                else:
                    # still waiting to fill: the trade's best move starts from here, not from when it was
                    # placed (weekly audit 2026-11-22: a limit that filled hours later counted the run-up
                    # before its fill, and moved its stop to +0.75R / +1.5R the moment it filled)
                    o["checked_until"] = max(int(o.get("checked_until") or 0), int(now) // 60 * 60)
                continue
            if not held:
                if not seen_gone(o, now):
                    continue
                if o.get("exit_price"):          # closed at market past its moved stop: R at that price, fees off
                    r = demo.move_r(o, o["exit_price"]) - config.COINDCX_DEMO_ROUND_TRIP_COST_PCT / o["stop_pct"]
                else:
                    r = demo.full_stop_r(o) if o.get("stop_r") is None else demo.moved_stop_r(o, o["stop_r"])
                money = o["risk"] * r
                state["realized"] = round(state["realized"] + money, 4)
                o.update(status="closed", exit_ts=int(now), r=round(r, 3), pnl=round(money, 4),
                         exit_why=o.get("stop_why") or "SL")
                o.pop("last_error", None)
                note(state, f"{'✅' if r > 0 else '🛑'} **{head}** closed at {o['exit_why']} ≈ {r:+.2f}R "
                            f"({money:+.2f} USDT) · total {state['realized']:+.2f}", now)
                continue
            if o.get("exit_sent") and now - o["exit_sent"] < EXIT_RETRY_SECONDS:
                continue                    # closed at market a moment ago: the position list lags
            before, last = o.get("stop_r"), None
            for c in candles(o["symbol"], o["checked_until"], now):
                if c[0] + 60 > now:
                    break
                o["checked_until"] = int(c[0]) + 60
                o["best_r"] = max(o["best_r"], demo.move_r(o, c[2] if o["side"] == "long" else c[3]))
                last = c[4]
            demo.apply_best({"unposted": []}, o, now)
            ensure_tick(ex, o)
            want = stop_level(o)
            on_exchange = pos.get("stop_loss_trigger")
            if o.get("stop_sent") is None and on_exchange:
                o["stop_sent"] = float(on_exchange)          # orders from before 21 Nov: read what is there
            if want != o.get("stop_sent") or not on_exchange:
                # a move that failed (SUI 18-21 Nov: 422 off the price step) is sent again every tick until taken
                pid = o.get("position_id") or pos.get("id")
                sign = 1 if o["side"] == "long" else -1
                crossed = last is not None and o.get("stop_r") is not None and sign * (last - want) <= 0
                try:
                    if crossed:
                        raise RuntimeError("Trigger price already passed by the last close")
                    ex.set_stop(pid, want)
                except RuntimeError as error:
                    if "Trigger price" not in str(error) or o.get("stop_r") is None:
                        raise
                    # price is already past the moved stop: the trail / shift stop is hit, so the trade
                    # exits at market (SUI 21 Nov: +1.5R stop refused, price back above it)
                    ex.exit(pid)
                    o.update(exit_sent=int(now), exit_price=last if last is not None else want,
                             stop_why=f"{o.get('stop_why') or 'stop'} passed, market exit")
                    note(state, f"🔒 **{head}** price already past the {o['stop_r']:+.2f}R stop ({p(want)}): "
                                f"closed at market", now)
                    continue
                o["stop_sent"] = want
                if o.pop("exit_sent", None):
                    # the market exit sent earlier did not close it and the stop went in after all
                    o.pop("exit_price", None)
                    o["stop_why"] = str(o.get("stop_why") or "").replace(" passed, market exit", "") or None
                if o.get("stop_r") != before or o.get("last_error"):
                    note(state, f"🔒 **{head}** stop moved to {o['stop_r']:+.2f}R ({p(want)})" if o.get("stop_r") is not None
                          else f"🔒 **{head}** stop set at {p(want)}", now)
                else:
                    note(state, f"🔁 **{head}** stop re-placed at {p(want)}", now)
        except Exception as error:  # noqa: BLE001
            text = str(error)[:160]
            if o.get("last_error") != text:                # once per error, not every tick
                note(state, f"⚠️ **{head}** manage FAILED: {text}", now)
            else:
                print(f"coindcx live: {head} manage still failing: {text}")
            o["last_error"] = text
        else:
            o.pop("last_error", None)


def tick(state, ex, records, now, **hooks):
    manage_hooks = {k: v for k, v in hooks.items() if k == "candles"}
    place_hooks = {k: v for k, v in hooks.items() if k in ("daily", "price_now", "btc_move")}
    confirm_hooks = {k: v for k, v in hooks.items() if k in ("hourly", "daily", "price_now", "btc_move")}
    try:
        positions = ex.positions()
        open_ids = {o.get("id") for o in ex.open_orders()}
    except Exception as error:  # noqa: BLE001 - no view of the account: place nothing new either
        text = str(error)[:160]
        if state.get("account_error") != text:     # once per error, not every tick (weekly audit 2026-11-22)
            note(state, f"⚠️ account read FAILED, nothing done: {text}", now)
        else:
            print(f"coindcx live: account read still failing: {text}")
        state["account_error"] = text
        return state
    if state.pop("account_error", None):
        note(state, "✅ account read working again", now)
    manage(state, ex, now, positions, open_ids, **manage_hooks)
    confirm_waiting(state, ex, now, **confirm_hooks)
    fresh = {}
    for r in records:
        if eligible(r, state, now):
            fresh.setdefault(r["id"], r)
    for record in sorted(fresh.values(), key=lambda r: float(r["sent_ts"])):
        try:
            place(state, ex, record, now, **place_hooks)
        except Exception as error:  # noqa: BLE001 - nothing was sent yet (submit catches its own): one bad
            # record must not stop the tick, or the state of every open trade goes unsaved for hours
            o = state["orders"].setdefault(record["id"], {"id": record["id"], "symbol": record.get("symbol"),
                                                          "side": record["plan"].get("side"), "placed_ts": int(now)})
            o.update(status="error", reason=f"alert unreadable: {str(error)[:160]}")
            note(state, f"⚠️ {demo.coin(str(record.get('symbol')))} TL alert skipped: {o['reason']}", now)
    return state


POST_HEADER = "**CoinDCX LIVE · 1D TL breaks · REAL orders**"
MAX_EVENTS = 200            # Discord down for days: keep the newest lines, not an ever-growing state


def post(state):
    """Post the events a Discord message at a time; a message's events are dropped once Discord
    takes it. Weekly audit 2026-11-22: the whole list was one text that demo.send split, and a
    failure on the second part kept every event, so the first part was posted again each tick."""
    events = state["events"]
    if len(events) > MAX_EVENTS:
        dropped = len(events) - MAX_EVENTS
        events[:] = [{"ts": events[-MAX_EVENTS]["ts"], "text": f"({dropped} older lines not posted)"}] + events[-MAX_EVENTS:]
    while events:
        part, size = [], len(POST_HEADER) + 1
        for e in events:
            line = str(e.get("text", ""))[:1500]
            if part and size + len(line) + 1 > demo.DISCORD_LIMIT:
                break
            part.append(line)
            size += len(line) + 1
        result = demo.send(POST_HEADER + "\n" + "\n".join(part))
        if result is False:
            return False
        del events[:len(part)]
        if result is None:          # no channel set up: nowhere to post
            events.clear()
    return True


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


def drop_dry_orders(state):
    """Orders a keyless run saved ("dry-" ids) never existed on CoinDCX: forget them."""
    gone = [k for k, o in state["orders"].items() if str(o.get("exchange_id", "")).startswith("dry-")]
    for k in gone:
        del state["orders"][k]
    return gone


def run_tick(now=None, dry_run=False, remote=False):
    now = int(time.time()) if now is None else int(now)
    if not config.COINDCX_LIVE_ENABLED:
        print("coindcx live is off (repository variable VICTUS_COINDCX_LIVE)")
        return None
    key, secret = os.getenv("COINDCX_API_KEY", ""), os.getenv("COINDCX_API_SECRET", "")
    if not (key and secret):
        dry_run = True      # no key: dry-run orders saved as pending blocked their coins for 20 days
        print("coindcx live: COINDCX_API_KEY / COINDCX_API_SECRET not set - dry run, nothing saved or posted")
    ex = CoinDCX(key, secret) if not dry_run else DryRun()
    if not dry_run and delta_on():
        ex = Router(ex, delta_live.Delta(os.environ["DELTA_API_KEY"], os.environ["DELTA_API_SECRET"]))
    try:
        state = load_state()
    except StateUnreadable as error:
        print(f"coindcx live: STOPPED - state file unreadable, nothing done or saved: {error}")
        if not dry_run and now % 3600 < 180:          # about once an hour, not every tick
            demo.send(f"{POST_HEADER}\n⛔ bot STOPPED: state file unreadable ({str(error)[:150]}). "
                      "Open trades keep their exchange stops but are not trailed. Fix coindcx_live_state.json.")
        return None
    if state is not None and not dry_run:
        drop_dry_orders(state)
    if state is None:
        state = new_state(now)
        until = state.get("until_ts")
        note(state, f"started: trades {rules_text()} "
                    + (f"until {datetime.fromtimestamp(until, scanner.IST):%d %b %H:%M IST}, " if until else "with no end date, ")
                    + f"risk {config.COINDCX_LIVE_RISK:g} USDT a trade"
                    + ("" if isinstance(ex, CoinDCX) else " (DRY RUN: no API key)"), now)
    if state.get("rules") != rules_text():
        if state.get("rules") is not None or state["orders"]:
            note(state, f"⚙️ rules now: {rules_text()} (realized {state['realized']:+.2f}, "
                        f"{drawdown(state):.2f} below the best point)", now)
        state["rules"] = rules_text()
    if config.COINDCX_LIVE_DAYS <= 0 and state.get("until_ts") is not None:
        state["until_ts"] = None                         # the test week's end date lifted (lakky, 21 Nov)
        note(state, "trading on with no end date (kill switch still on, "
                    f"{state['realized']:+.2f} so far)", now)
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
