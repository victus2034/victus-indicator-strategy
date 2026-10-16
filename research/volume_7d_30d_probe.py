"""Research only: average daily traded value (USDT) over the last 7 and 30
complete days, on Delta India perpetuals and CoinDCX USDT futures.

For every base coin on either venue this prints the 7d and 30d daily average
on each venue, whether Bitunix lists a perp for it (alerts run on Bitunix
candles) and whether it is already scanned. A coin passes when one venue
averages >= --min over both 7 and 30 days. Posts nothing, touches no state.

Daily candles are converted to USDT as base volume x close. Each venue's unit
is checked against its own 24h ticker value and printed (calibration lines),
so a unit mix-up shows up in the output instead of in the lists.
"""
import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config        # noqa: E402
from coindcx_volume_probe import bitunix_pairs, watched_bases   # noqa: E402

COINDCX_RT = "https://public.coindcx.com/market_data/v3/current_prices/futures/rt"
COINDCX_CANDLES = "https://public.coindcx.com/market_data/candlesticks"
OUT = Path(__file__).resolve().parent / "out" / "volume"
DAY = 86400


def get(url, params=None, tries=4):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(2 * (i + 1))
                continue
            return r.json()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
    return {}


def day_of(t):
    t = int(t)
    if t > 10**11:          # milliseconds
        t //= 1000
    return t // DAY * DAY


def norm_base(b):
    return b[4:] if b.startswith("1000") and len(b) > 4 else b


def window(days_back):
    today = int(time.time()) // DAY * DAY      # 00:00 UTC today; today's candle excluded
    return today - days_back * DAY, today


def averages(daily):
    """daily: {day_ts: usdt}. -> (avg7, avg30, days)"""
    start7, end = window(7)
    start30, _ = window(30)
    d7 = [v for t, v in daily.items() if start7 <= t < end]
    d30 = [v for t, v in daily.items() if start30 <= t < end]
    a7 = sum(d7) / 7 if d7 else 0.0       # missing days count as zero
    a30 = sum(d30) / 30 if d30 else 0.0
    return a7, a30, len(d30)


def pick_multiplier(samples):
    """samples: [(ticker_24h_usdt, last_day_volume, last_close)]. Pick whether the
    candle volume is already USDT (x1) or base units (x close), by median log error."""
    best = None
    for name, f in (("x1", lambda v, c: v), ("x close", lambda v, c: v * c)):
        errs = [abs(math.log(f(v, c) / t)) for t, v, c in samples if t > 0 and f(v, c) > 0]
        if not errs:
            continue
        m = statistics.median(errs)
        if best is None or m < best[1]:
            best = (name, m, f)
    return best or ("x close (no calibration data)", float("nan"), lambda v, c: v * c)


# ---- CoinDCX -------------------------------------------------------------
def coindcx():
    j = get(COINDCX_RT)
    prices = j.get("prices", j)
    tick = {}
    for key, rec in prices.items():
        if isinstance(rec, dict) and key.endswith("_USDT"):
            try:
                tick[key] = float(rec.get("v") or 0)
            except (TypeError, ValueError):
                tick[key] = 0.0
    start, end = window(31)
    raw = {}
    for key in tick:
        p = get(COINDCX_CANDLES, {"pair": key, "from": start, "to": end + DAY,
                                  "resolution": "1D", "pcode": "f"})
        rows = p if isinstance(p, list) else (p.get("data") or [])
        raw[key] = [(day_of(r["time"]), float(r.get("volume") or 0), float(r["close"]))
                    for r in rows if isinstance(r, dict) and "time" in r]
        time.sleep(0.05)
    samples = []
    for key, rows in raw.items():
        done = sorted(r for r in rows if r[0] < end)
        if done and tick[key] > 1e7:
            samples.append((tick[key], done[-1][1], done[-1][2]))
    best = pick_multiplier(samples)
    out = {}
    for key, rows in raw.items():
        daily = {t: best[2](v, c) for t, v, c in rows}
        base = key.removeprefix("B-").removesuffix("_USDT")
        out[base] = (*averages(daily), tick[key])
    return out, f"CoinDCX: {len(tick)} USDT futures; candle volume {best[0]} (median |log err| vs 24h ticker {best[1]:.2f}, {len(samples)} coins)"


# ---- Delta ---------------------------------------------------------------
def delta():
    prods = get(config.DELTA_API_BASE_URL + "/v2/products",
                {"contract_types": "perpetual_futures", "page_size": 1000}).get("result") or []
    tick = {t["symbol"]: float(t.get("turnover_usd") or 0)
            for t in get(config.DELTA_API_BASE_URL + "/v2/tickers",
                         {"contract_types": "perpetual_futures"}).get("result") or []}
    start, end = window(31)
    raw, bases = {}, {}
    for p in prods:
        if p.get("contract_type") != "perpetual_futures" or p.get("state") != "live":
            continue
        sym = p["symbol"]
        cv = float(p.get("contract_value") or 1)
        r = get(config.DELTA_API_BASE_URL + "/v2/history/candles",
                {"symbol": sym, "resolution": "1d", "start": start, "end": end + DAY})
        raw[sym] = [(day_of(c["time"]), float(c.get("volume") or 0) * cv, float(c["close"]))
                    for c in (r.get("result") or [])]
        bases[sym] = (p.get("underlying_asset") or {}).get("symbol") or sym.removesuffix("USD")
        time.sleep(0.05)
    samples = []
    for sym, rows in raw.items():
        done = sorted(r for r in rows if r[0] < end)
        if done and tick.get(sym, 0) > 1e6:
            samples.append((tick[sym], done[-1][1], done[-1][2]))
    best = pick_multiplier(samples)
    out = {}
    for sym, rows in raw.items():
        daily = {t: best[2](v, c) for t, v, c in rows}
        out[bases[sym]] = (*averages(daily), tick.get(sym, 0.0), sym)
    return out, f"Delta: {len(raw)} live perps; candle volume (contracts x value) {best[0]} (median |log err| vs 24h ticker {best[1]:.2f}, {len(samples)} coins)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=100e6)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    cd, cd_note = coindcx()
    dl, dl_note = delta()
    bx = bitunix_pairs()
    watched = {norm_base(b): s for b, s in watched_bases().items()}
    crypto = {norm_base(b) for b, s in watched_bases().items() if s in config.CRYPTO_WATCHLIST}

    keys = {}
    for b in list(cd) + list(dl):
        keys.setdefault(norm_base(b), set()).add(b)
    rows = []
    m = args.min
    for nb in sorted(keys):
        c = next((cd[b] for b in keys[nb] if b in cd), None)
        d = next((dl[b] for b in keys[nb] if b in dl), None)
        bpair = next((p for p in (nb + "USDT", "1000" + nb + "USDT") if p in bx), None)
        c7, c30 = (c[0], c[1]) if c else (0, 0)
        d7, d30 = (d[0], d[1]) if d else (0, 0)
        pass_c = c7 >= m and c30 >= m
        pass_d = d7 >= m and d30 >= m
        rows.append({
            "base": nb, "dcx_7d": round(c7 / 1e6, 1), "dcx_30d": round(c30 / 1e6, 1),
            "delta_7d": round(d7 / 1e6, 1), "delta_30d": round(d30 / 1e6, 1),
            "delta_symbol": d[4] if d else None, "dcx_days": c[2] if c else 0,
            "bitunix": bpair, "watched": watched.get(nb), "crypto_watched": nb in crypto,
            "pass": pass_c or pass_d, "pass_dcx": pass_c, "pass_delta": pass_d,
            "commodity": nb in {"XAU", "XAG", "CL", "BZ", "NATGAS", "XPT", "XPD", "COPPER"},
        })
    for nb in crypto - set(keys):
        rows.append({"base": nb, "dcx_7d": 0, "dcx_30d": 0, "delta_7d": 0, "delta_30d": 0,
                     "delta_symbol": None, "dcx_days": 0, "bitunix": nb + "USDT", "watched": watched[nb],
                     "crypto_watched": True, "pass": False, "pass_dcx": False, "pass_delta": False,
                     "commodity": False})
    (OUT / "volume_7d_30d.json").write_text(json.dumps(rows, indent=1))

    def table(sel, title):
        sel = sorted(sel, key=lambda r: -max(r["dcx_30d"], r["delta_30d"]))
        lines = [f"## {title} ({len(sel)})", "",
                 "| Coin | CoinDCX 7d | CoinDCX 30d | Delta 7d | Delta 30d | Bitunix | Scanned as |",
                 "|---|---|---|---|---|---|---|"]
        for r in sel:
            lines.append(f"| {r['base']} | {r['dcx_7d']} | {r['dcx_30d']} | {r['delta_7d']} | {r['delta_30d']} | "
                         f"{r['bitunix'] or '-'} | {r['watched'] or '-'} |")
        return lines + [""]

    keep = [r for r in rows if r["crypto_watched"] and r["pass"]]
    drop = [r for r in rows if r["crypto_watched"] and not r["pass"]]
    add = [r for r in rows if not r["watched"] and r["pass"] and r["bitunix"] and not r["commodity"]]
    nobx = [r for r in rows if not r["watched"] and r["pass"] and not r["bitunix"] and not r["commodity"]]
    comm = [r for r in rows if not r["watched"] and r["pass"] and r["commodity"]]
    text = "\n".join(
        [f"# Daily traded value, M USDT (avg of last 7 / 30 complete UTC days)", "",
         f"Pass = one venue >= {m / 1e6:.0f}M a day on BOTH the 7d and the 30d average.", "",
         f"- {cd_note}", f"- {dl_note}", f"- Bitunix: {len(bx)} pairs", ""]
        + table(keep, "Scanned crypto that passes: keep")
        + table(drop, "Scanned crypto that fails: remove")
        + table(add, "Not scanned, passes, Bitunix lists it: add")
        + table(nobx, "Not scanned, passes, no Bitunix perp (can't alert)")
        + table(comm, "Commodities that pass (left out)"))
    (OUT / "VOLUME_7D_30D.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
