"""Research only: re-check the crypto and xStock watchlists (lakky, 2026-11-08).

"recheck all the coindcx and delta symbols and remove those with less volume
and add with more volume but make sure check the chart as it should not like a
massive pump or dump sort of crypto and xstock"

Volume: the 2026-10-16 rule, from volume_7d_30d_probe - average traded value
over BOTH the last 7 and 30 complete UTC days on CoinDCX or Delta, plus a
Bitunix perp. Crypto needs 100M USDT a day (--min). xStocks never come near
that on either venue, so they are ranked against their own bar (--xstock-min).

Chart check, on Bitunix daily candles (the alert feed), last 90 complete days:
  day   biggest one-day close-to-close move, either way
  week  biggest 7-day close-to-close move, either way
  spike biggest day's traded value / median day's, over the 90 days
  age   days since the pair's first Bitunix daily candle
A coin is a pump/dump chart when day >= --max-day (moves measured as |log|, so
a fall counts like the rise that undoes it), spike >= --max-spike, or age <
--min-age. The week column is shown, not a fail: the first run (2026-11-08)
flagged ZEC, NEAR, ENA, UNI and AAVE on it - big coins in a steady trend, with
no pump day (max 29%) and no volume spike (max 8.8x) - while every coin with a
40%+ day or a 10x volume day (QNT, RLC, STRK, BTW, AIN, JCT, AKE, SOXL, KORU)
was a one-off spike. Posts nothing, touches no state.
"""
import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_data                                         # noqa: E402
import config                                               # noqa: E402
from coindcx_volume_probe import bitunix_pairs              # noqa: E402
from volume_7d_30d_probe import DAY, coindcx, delta, get, norm_base, window   # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "coin_list"
COMMODITIES = {"XAU", "XAG", "CL", "BZ", "NATGAS", "XPT", "XPD", "COPPER", "PAXG", "XAUT", "SLVON"}


def log_move(a, b):
    return abs(math.log(b / a)) if a > 0 and b > 0 else 0.0


def pct(x):
    """|log| move -> the up-move percent it equals."""
    return (math.exp(x) - 1) * 100


def chart_check(pair):
    end = int(time.time()) // DAY * DAY            # today's candle left out
    rows = bitunix_data.klines(pair, "1d", end - 400 * DAY, end)
    if not rows:
        return None
    age = (end - rows[0][0]) // DAY
    last = [r for r in rows if r[0] >= end - 90 * DAY]
    closes = [r[4] for r in rows if r[0] >= end - 97 * DAY]
    off = len(closes) - len(last)
    day = max((log_move(closes[i - 1], closes[i]) for i in range(max(1, off), len(closes))), default=0)
    week = max((log_move(closes[i - 7], closes[i]) for i in range(max(7, off), len(closes))), default=0)
    vals = [r[5] * r[4] for r in last]
    med = statistics.median(vals) if vals else 0
    spike = max(vals) / med if med > 0 else 0
    v7 = sum(r[5] * r[4] for r in rows if r[0] >= end - 7 * DAY) / 7
    v30 = sum(r[5] * r[4] for r in rows if r[0] >= end - 30 * DAY) / 30
    move90 = (last[-1][4] / last[0][1] - 1) * 100 if last and last[0][1] > 0 else 0
    return {"age": age, "day": day, "week": week, "spike": spike, "move90": move90,
            "bx7": v7, "bx30": v30, "bars": len(last)}


def delta_descriptions():
    prods = get(config.DELTA_API_BASE_URL + "/v2/products",
                {"contract_types": "perpetual_futures", "page_size": 1000}).get("result") or []
    out = {}
    for p in prods:
        if p.get("contract_type") == "perpetual_futures" and p.get("state") == "live":
            base = (p.get("underlying_asset") or {}).get("symbol") or p["symbol"].removesuffix("USD")
            out[base] = (p.get("description") or "") + " " + ((p.get("underlying_asset") or {}).get("name") or "")
    return out


def is_xstock(base, desc):
    d = desc.lower()
    return "xstock" in d or " stock" in d or "etf" in d or "backed" in d


def stock_ticker(base):
    """Delta names xStocks TSLAX / SOXLB; Bitunix lists the plain ticker."""
    return base[:-1] if base[-1:] in ("X", "B") and len(base) > 2 else base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=100e6)
    ap.add_argument("--xstock-min", type=float, default=1e6)
    ap.add_argument("--max-day", type=float, default=40.0, help="one-day move, %%")
    ap.add_argument("--max-spike", type=float, default=10.0)
    ap.add_argument("--min-age", type=int, default=90)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    lim_day = math.log(1 + a.max_day / 100)

    cd, cd_note = coindcx()
    dl, dl_note = delta()
    desc = delta_descriptions()
    bx = bitunix_pairs()

    crypto_now = {norm_base(s.split("/")[0].removesuffix("USD")): s for s in config.CRYPTO_WATCHLIST}
    xs_now = {}
    for s in config.XSTOCK_WATCHLIST:
        pair = config.BITUNIX_XSTOCK_PAIRS.get(s, "")
        xs_now[pair.removesuffix("USDT") or s] = s

    venues = {}
    for b, v in cd.items():
        venues.setdefault(norm_base(b), {})["dcx"] = (v[0], v[1])
    for b, v in dl.items():
        venues.setdefault(norm_base(b), {})["delta"] = (v[0], v[1])
        venues[norm_base(b)]["desc"] = desc.get(b, "")

    rows = []
    for nb, v in sorted(venues.items()):
        if nb in COMMODITIES:
            continue
        xs = is_xstock(nb, v.get("desc", "")) or stock_ticker(nb) in xs_now
        key = stock_ticker(nb) if xs else nb
        c7, c30 = v.get("dcx", (0, 0))
        d7, d30 = v.get("delta", (0, 0))
        bar = a.xstock_min if xs else a.min
        passes = (c7 >= bar and c30 >= bar) or (d7 >= bar and d30 >= bar)
        scanned = key in (xs_now if xs else crypto_now)
        pair = next((p for p in (key + "USDT", "1000" + key + "USDT") if p in bx), None)
        if not (passes or scanned):
            continue
        rows.append({"base": key, "kind": "xstock" if xs else "crypto", "scanned": scanned,
                     "dcx7": c7 / 1e6, "dcx30": c30 / 1e6, "d7": d7 / 1e6, "d30": d30 / 1e6,
                     "vol_pass": passes, "bitunix": pair})
    seen = {(r["kind"], r["base"]) for r in rows}
    for kind, now in (("crypto", crypto_now), ("xstock", xs_now)):
        for b in now:
            if (kind, b) not in seen:
                rows.append({"base": b, "kind": kind, "scanned": True, "dcx7": 0, "dcx30": 0,
                             "d7": 0, "d30": 0, "vol_pass": False,
                             "bitunix": next((p for p in (b + "USDT", "1000" + b + "USDT") if p in bx), None)})

    for r in rows:
        ch = None
        if r["bitunix"]:
            try:
                ch = chart_check(r["bitunix"])
            except Exception as exc:       # one bad pair must not stop the table
                r["error"] = str(exc)
        r["chart"] = ch
        why = []
        if ch:
            if ch["day"] >= lim_day:
                why.append(f"day {pct(ch['day']):.0f}%")
            if ch["spike"] >= a.max_spike:
                why.append(f"vol spike {ch['spike']:.0f}x")
            if ch["age"] < a.min_age:
                why.append(f"listed {ch['age']}d")
        elif r["bitunix"]:
            why.append("no candles")
        r["pump"] = why
        r["verdict"] = ("keep" if r["vol_pass"] and not why else "remove") if r["scanned"] else (
            "add" if r["vol_pass"] and r["bitunix"] and not why else
            "skip: no Bitunix" if not r["bitunix"] else "skip: chart")
    (OUT / "coin_list_review.json").write_text(json.dumps(rows, indent=1, default=str))

    def table(kind):
        sel = sorted((r for r in rows if r["kind"] == kind),
                     key=lambda r: (["keep", "remove", "add"].index(r["verdict"]) if r["verdict"] in ("keep", "remove", "add") else 3,
                                    -max(r["dcx30"], r["d30"])))
        out = [f"## {kind}", "",
               "| Coin | Verdict | Scanned | DCX 7d | DCX 30d | Delta 7d | Delta 30d | Bitunix 30d | Day max | Week max | Vol spike | Age d | 90d move | Chart flags |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sel:
            ch = r["chart"] or {}
            out.append(
                f"| {r['base']} | {r['verdict']} | {'yes' if r['scanned'] else '-'} | {r['dcx7']:.1f} | {r['dcx30']:.1f} | "
                f"{r['d7']:.1f} | {r['d30']:.1f} | {ch.get('bx30', 0) / 1e6:.1f} | "
                f"{pct(ch['day']):.0f}% | {pct(ch['week']):.0f}% | {ch['spike']:.1f}x | {ch['age']} | {ch['move90']:+.0f}% | "
                if ch else
                f"| {r['base']} | {r['verdict']} | {'yes' if r['scanned'] else '-'} | {r['dcx7']:.1f} | {r['dcx30']:.1f} | "
                f"{r['d7']:.1f} | {r['d30']:.1f} | - | - | - | - | - | - | ")
            out[-1] += (", ".join(r["pump"]) or "-") + " |"
        return out + [""]

    text = "\n".join([
        "# Coin list review (M USD a day, avg of last 7 / 30 complete UTC days)", "",
        f"- Volume pass: one venue >= {a.min / 1e6:.0f}M (crypto) / {a.xstock_min / 1e6:.1f}M (xStocks) on BOTH 7d and 30d",
        f"- Pump/dump chart (Bitunix 1d, last 90 days): one-day move >= {a.max_day:.0f}% "
        f"(falls as |log|, so -29% = +40%), a day's traded value >= {a.max_spike:.0f}x the median day, or listed < {a.min_age} days",
        f"- {cd_note}", f"- {dl_note}", f"- Bitunix: {len(bx)} pairs", ""]
        + table("crypto") + table("xstock"))
    (OUT / "COIN_LIST_REVIEW.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
