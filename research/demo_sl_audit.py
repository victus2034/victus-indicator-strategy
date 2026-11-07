"""Delta specs and candles for the journal's Demo account audit (lakky, 2026-11-07).

The journal's Demo account sizes each alert as risk / stop distance. Whether that
trade could really be placed on Delta depends on the contract size (the smallest
order is one contract), the tick size and the most leverage Delta allows. This
saves those for every perpetual, the bid/ask spread now, and the candles the
journal's "Exit at" reads for a sample of graded alerts (research/in/
demo_sl_audit_sample.json, picked across stop distances), so the journal's numbers
can be checked by hand from the sandbox, which can't reach Delta. Read only.
Part `demo-sl` of bitunix_research.yml.
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.parse
import urllib.request

BASE = "https://api.india.delta.exchange"
OUT = "research/out/demo_sl_audit"
SAMPLE = "research/in/demo_sl_audit_sample.json"
SYMBOLS = "research/in/demo_sl_audit_symbols.json"
# The journal's tgtOne: the finest resolution that covers 2 x 20 candles of the
# alert's timeframe in at most 1900 candles, from one candle before the alert.
RES = [(1, "1m"), (5, "5m"), (15, "15m"), (60, "1h"), (240, "4h"), (1440, "1d")]
TF_MIN = {"30m": 30, "4h": 240, "1d": 1440, "1w": 10080, "1M": 43200}
KEEP = ["symbol", "id", "state", "contract_type", "contract_value", "contract_unit_currency",
        "tick_size", "initial_margin", "maintenance_margin", "default_leverage",
        "position_size_limit", "initial_margin_scaling_factor", "maintenance_margin_scaling_factor",
        "notional_type", "maker_commission_rate", "taker_commission_rate", "max_leverage_notional",
        "impact_size", "price_band", "launch_time", "short_description"]


def get(path: str, params: dict) -> dict:
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    err = None
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "victus-research"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001 - retried, then raised
            err = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url}: {err}")


def coindcx() -> None:
    """CoinDCX futures specs (min order, steps, max leverage) for the bases alerts used."""
    want = {s.removesuffix("USD") for s in json.load(open(SYMBOLS))}
    url = "https://api.coindcx.com/exchange/v1/derivatives/futures/data/active_instruments"
    req = urllib.request.Request(url, headers={"User-Agent": "victus-research"})
    with urllib.request.urlopen(req, timeout=30) as r:
        pairs = json.loads(r.read().decode())
    out, raw = {}, {}
    for pair in pairs:
        base = str(pair).removeprefix("B-").split("_")[0]
        if base not in want:
            continue
        q = urllib.parse.urlencode({"pair": pair, "margin_currency_short_name": "USDT"})
        try:
            req = urllib.request.Request(url.replace("active_instruments", "instrument") + "?" + q, headers={"User-Agent": "victus-research"})
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            j = {"error": str(e)}
        if base in ("BTC", "ETH", "DOGE"):
            raw[pair] = j
        ins = j.get("instrument") if isinstance(j, dict) else None
        out[base] = ins if isinstance(ins, dict) else j
        time.sleep(0.1)
    with open(f"{OUT}/coindcx_specs.json", "w") as f:
        json.dump({"fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "instruments": out, "raw_sample": raw}, f, indent=1, sort_keys=True)
    print(f"CoinDCX: {len(out)} of {len(want)} bases listed")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    if os.environ.get("DEMO_SL_PART") == "coindcx":
        coindcx()
        return
    prods = get("/v2/products", {"contract_types": "perpetual_futures", "page_size": 1000}).get("result") or []
    raw = {p["symbol"]: p for p in prods if p.get("symbol") in ("BTCUSD", "ETHUSD", "DOGEUSD", "XAUTUSD", "TSLAXUSD")}
    with open(f"{OUT}/products_raw_sample.json", "w") as f:
        json.dump(raw, f, indent=1, sort_keys=True)
    specs = {p["symbol"]: {k: p.get(k) for k in KEEP} for p in prods if p.get("symbol")}
    tick = {t["symbol"]: t for t in get("/v2/tickers", {"contract_types": "perpetual_futures"}).get("result") or []}
    for sym, s in specs.items():
        t = tick.get(sym) or {}
        q = t.get("quotes") or {}
        s["mark_price"] = t.get("mark_price")
        s["best_bid"] = q.get("best_bid")
        s["best_ask"] = q.get("best_ask")
        s["turnover_usd"] = t.get("turnover_usd")
    with open(f"{OUT}/delta_specs.json", "w") as f:
        json.dump({"fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "products": specs}, f, indent=1, sort_keys=True)
    print(f"{len(specs)} perpetuals")
    for sym in sorted(specs):
        s = specs[sym]
        try:
            px = float(s["mark_price"] or 0)
            lot = float(s["contract_value"] or 0) * px
            sp = (float(s["best_ask"]) - float(s["best_bid"])) / px * 100 if px and s["best_ask"] and s["best_bid"] else None
            tk = float(s["tick_size"]) / px * 100 if px else None
            print(f"{sym:14} lot ${lot:10.4f}  tick {tk if tk is None else round(tk, 5)}%  spread {sp if sp is None else round(sp, 4)}%  IM {s['initial_margin']}  lev {s['default_leverage']}")
        except (TypeError, ValueError):
            print(sym, "unreadable", s)

    sample = json.load(open(SAMPLE))
    now_ms = time.time() * 1000
    out = []
    for a in sample:
        tf = TF_MIN.get(a["tf"])
        t0 = math.floor(a["sent_ts"] / 60) * 60 * 1000  # the journal keeps the minute
        span = 2 * 20 * tf * 60000
        res = next((r for r in RES if span / (r[0] * 60000) <= 1900), RES[-1])
        start, end = math.floor((t0 - res[0] * 60000) / 1000), math.ceil(min(now_ms, t0 + span) / 1000)
        params = {"resolution": res[1], "symbol": a["symbol"], "start": start, "end": end}
        try:
            j = get("/v2/history/candles", params)
        except RuntimeError as e:
            j = {"error": str(e)}
        out.append({"alert": a, "res_min": res[0], "params": params, "reply": j})
        print(a["symbol"], a["tf"], res[1], len((j.get("result") or [])) if isinstance(j, dict) else "?")
        time.sleep(0.1)
    with open(f"{OUT}/candles.json", "w") as f:
        json.dump(out, f)


if __name__ == "__main__":
    main()
