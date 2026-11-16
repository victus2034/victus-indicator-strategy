"""Delta Exchange India for the live bot (coindcx_live.py): the same five calls as its CoinDCX
class, so a Delta-listed coin trades on Delta (lakky, 2026-11-15: "those cryptos which are
available in delta you will trade it because in delta fees is very less").

Body fields and signing are those of Delta's own client (delta-rest-client 1.0.14):
HMAC-SHA256 hex of method + timestamp + path + query + compact JSON body, headers api-key /
timestamp / signature. Sizes are whole contracts (contract_value coins each). The stop is a
reduce-only stop-market order for the position's size; a moved stop is placed first and the old
one cancelled after, so the position is never without one.

The key is whitelisted for the AWS server's IPv4 (trading-journal secrets DELTA_API_KEY /
DELTA_API_SECRET), so like CoinDCX it only runs there.

  python delta_live.py --self-test XRPUSD     # one real 1-contract round trip: buy, stop, move, close
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
import urllib.parse

import requests

BASE = "https://api.india.delta.exchange"
PREFIX = "DELTA:"


def price_str(price, tick):
    """A price as Delta takes it: the tick's own number of decimals ("0.0001" -> 4)."""
    places = len(f"{tick:.12f}".rstrip("0").split(".")[1]) if tick < 1 else 0
    return f"{price:.{places}f}"


def pair_for(symbol):
    return PREFIX + symbol


def symbol_of(pair):
    return pair[len(PREFIX):] if pair.startswith(PREFIX) else pair


class Delta:
    def __init__(self, key, secret, session=None):
        import socket
        import urllib3.util.connection
        urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET   # whitelisted IPv4 only
        self.key, self.secret = key, secret.encode()
        self.http = session or requests.Session()
        self.products = {}          # symbol -> product
        self.by_id = {}             # product id -> symbol

    # ------------------------------------------------------------ http
    def call(self, method, path, body=None, query=None, auth=True):
        qs = ("?" + "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in query.items())) if query else ""
        raw = json.dumps(body, separators=(",", ":")) if body is not None else ""
        headers = {"Content-Type": "application/json", "User-Agent": "victus-live-bot"}
        if auth:
            ts = str(int(time.time()))
            headers.update({"api-key": self.key, "timestamp": ts,
                            "signature": hmac.new(self.secret, (method + ts + path + qs + raw).encode(), hashlib.sha256).hexdigest()})
        r = self.http.request(method, BASE + path + qs, data=raw or None, headers=headers, timeout=20)
        try:
            got = r.json()
        except ValueError:
            got = {}
        if r.status_code >= 400 or got.get("success") is False:
            raise RuntimeError(f"Delta {method} {path}: HTTP {r.status_code} {json.dumps(got.get('error') or r.text)[:200]}")
        return got.get("result")

    def product(self, symbol):
        if symbol not in self.products:
            p = self.call("GET", f"/v2/products/{symbol}", auth=False) or {}
            if not p.get("id") or p.get("state") != "live":
                raise RuntimeError(f"Delta has no live {symbol}")
            self.products[symbol] = p
            self.by_id[int(p["id"])] = symbol
        return self.products[symbol]

    # ------------------------------------------------------------ the bot's five calls
    def instrument(self, pair):
        p = self.product(symbol_of(pair))
        cv = float(p["contract_value"])
        lev = 100.0 / float(p.get("initial_margin") or 100)
        return {"quantity_increment": cv, "min_quantity": cv, "price_increment": float(p["tick_size"]),
                "max_leverage_long": lev, "max_leverage_short": lev}

    def contracts(self, pair, qty):
        return int(round(qty / float(self.product(symbol_of(pair))["contract_value"])))

    def create_order(self, pair, side, order_type, qty, leverage, price=None):
        p = self.product(symbol_of(pair))
        self.call("POST", f"/v2/products/{p['id']}/orders/leverage", {"leverage": str(int(leverage))})
        order = {"product_id": int(p["id"]), "size": self.contracts(pair, qty), "side": side,
                 "order_type": order_type, "reduce_only": "false"}
        if order["size"] < 1:
            raise RuntimeError(f"{qty} is under one {symbol_of(pair)} contract")
        if order_type == "limit_order":
            order["limit_price"] = price_str(price, float(p["tick_size"]))
        got = self.call("POST", "/v2/orders", order) or {}
        return {"id": f"{p['id']}:{got['id']}"} if got.get("id") else got

    def cancel(self, order_id):
        pid, oid = str(order_id).split(":")
        return self.call("DELETE", "/v2/orders", {"id": int(oid), "product_id": int(pid)})

    def live_orders(self):
        got = self.call("GET", "/v2/orders", query={"states": "open,pending", "page_size": 100}) or []
        return got if isinstance(got, list) else []

    def open_orders(self):
        return [{"id": f"{o['product_id']}:{o['id']}"} for o in self.live_orders() if not o.get("stop_order_type")]

    def stop_orders(self, product_id=None):
        return [o for o in self.live_orders() if o.get("stop_order_type") and o.get("reduce_only")
                and (product_id is None or int(o["product_id"]) == int(product_id))]

    def positions(self):
        got = self.call("GET", "/v2/positions/margined") or []
        stops = {}
        for o in self.stop_orders():
            stops[int(o["product_id"])] = o.get("stop_price")
        out = {}
        for x in got:
            size = int(x.get("size") or 0)
            if not size:
                continue
            sym = x.get("product_symbol") or self.by_id.get(int(x["product_id"]))
            p = self.product(sym)
            pair = pair_for(sym)
            out[pair] = {"id": pair, "pair": pair, "active_pos": size * float(p["contract_value"]), "size": size,
                         "avg_price": float(x.get("entry_price") or 0), "stop_loss_trigger": stops.get(int(p["id"])),
                         "liquidation_price": x.get("liquidation_price")}
        return out

    def set_stop(self, position_id, stop):
        """position_id = the pair. New stop first, then the old ones off: never a moment without one."""
        sym = symbol_of(position_id)
        p = self.product(sym)
        pos = next((x for x in (self.call("GET", "/v2/positions/margined") or [])
                    if int(x["product_id"]) == int(p["id"]) and int(x.get("size") or 0)), None)
        if pos is None:
            raise RuntimeError(f"no open {sym} position to stop")
        size = int(pos["size"])
        old = self.stop_orders(p["id"])
        got = self.call("POST", "/v2/orders", {
            "product_id": int(p["id"]), "size": abs(size), "side": "sell" if size > 0 else "buy",
            "order_type": "market_order", "stop_order_type": "stop_loss_order",
            "stop_price": price_str(stop, float(p["tick_size"])), "reduce_only": "true"})
        for o in old:
            self.call("DELETE", "/v2/orders", {"id": int(o["id"]), "product_id": int(p["id"])})
        return got

    def close(self, pair):
        """Market-close the whole position and drop its stops (self-test and manual use)."""
        p = self.product(symbol_of(pair))
        pos = next((x for x in (self.call("GET", "/v2/positions/margined") or [])
                    if int(x["product_id"]) == int(p["id"]) and int(x.get("size") or 0)), None)
        if pos:
            size = int(pos["size"])
            self.call("POST", "/v2/orders", {"product_id": int(p["id"]), "size": abs(size), "side": "sell" if size > 0 else "buy",
                                             "order_type": "market_order", "reduce_only": "true"})
        for o in self.stop_orders(p["id"]):
            self.call("DELETE", "/v2/orders", {"id": int(o["id"]), "product_id": int(p["id"])})


def self_test(symbol):
    """One real round trip on the smallest size: what the bot does, step by step."""
    ex = Delta(os.environ["DELTA_API_KEY"], os.environ["DELTA_API_SECRET"])
    pair = pair_for(symbol)
    ok = True

    def step(name, good, detail=""):
        nonlocal ok
        ok = ok and good
        print(f"{'PASS' if good else 'FAIL'}  {name}  {detail}")

    def wait_pos(want, tries=12):
        for _ in range(tries):
            pos = ex.positions().get(pair)
            if bool(pos) == want:
                return pos
            time.sleep(5)
        return ex.positions().get(pair)

    ins = ex.instrument(pair)
    step("instrument", ins["quantity_increment"] > 0, json.dumps(ins))
    if ex.positions().get(pair):
        step("no position before the test", False, "a position is already open - test not run")
        return False
    price = float((ex.call("GET", f"/v2/tickers/{symbol}", auth=False) or {}).get("mark_price") or 0)
    step("price", price > 0, str(price))
    try:
        got = ex.create_order(pair, "buy", "market_order", ins["min_quantity"], 2)
        step("market buy 1 contract at 2x", bool(got.get("id")), str(got))
        pos = wait_pos(True)
        step("position shows up", bool(pos), json.dumps(pos))
        if not pos:
            return False
        s1 = price * 0.95
        ex.set_stop(pair, s1)
        stops = ex.stop_orders(ex.product(symbol)["id"])
        step("stop placed 5% below", len(stops) == 1 and abs(float(stops[0]["stop_price"]) - s1) / s1 < 0.001,
             json.dumps([(o["id"], o["stop_price"], o["side"], o["size"]) for o in stops]))
        pos = ex.positions().get(pair) or {}
        step("position reads its stop", bool(pos.get("stop_loss_trigger")), str(pos.get("stop_loss_trigger")))
        s2 = price * 0.97
        ex.set_stop(pair, s2)
        stops = ex.stop_orders(ex.product(symbol)["id"])
        step("stop moved to 3% below, old one gone", len(stops) == 1 and abs(float(stops[0]["stop_price"]) - s2) / s2 < 0.001,
             json.dumps([(o["id"], o["stop_price"]) for o in stops]))
    finally:
        ex.close(pair)
        gone = not wait_pos(False)
        step("closed, flat", gone)
        left = ex.stop_orders(ex.product(symbol)["id"])
        step("no stop left behind", not left, str(len(left)))
    print("SELF-TEST " + ("PASSED" if ok else "FAILED"))
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", metavar="SYMBOL")
    a = ap.parse_args()
    if a.self_test:
        raise SystemExit(0 if self_test(a.self_test) else 1)
