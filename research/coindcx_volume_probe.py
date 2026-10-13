"""Research only: which CoinDCX USDT futures trade 100M+ USDT a day, and can
the scanner alert on them?

For every CoinDCX futures instrument with 24h volume >= --min (USDT) this
prints its volume, whether Bitunix lists <base>USDT, whether Delta India lists
a perpetual for the same base, and whether it is already in WATCHLIST.
Posts nothing, touches no state.
"""
import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config        # noqa: E402

COINDCX_RT = "https://public.coindcx.com/market_data/v3/current_prices/futures/rt"
OUT = Path(__file__).resolve().parent / "out" / "coindcx"


def coindcx_volumes():
    j = requests.get(COINDCX_RT, timeout=30).json()
    prices = j.get("prices", j)
    rows = {}
    for key, rec in prices.items():
        if not isinstance(rec, dict) or not key.endswith("_USDT"):
            continue
        base = key.removeprefix("B-").removesuffix("_USDT")
        try:
            rows[base] = float(rec.get("v") or 0)
        except (TypeError, ValueError):
            rows[base] = 0.0
    return rows


def bitunix_pairs():
    r = requests.get(config.BITUNIX_API_BASE_URL + "/api/v1/futures/market/trading_pairs", timeout=30)
    return {p.get("symbol"): p for p in (r.json().get("data") or [])}


def delta_perps():
    r = requests.get(config.DELTA_API_BASE_URL + "/v2/products", timeout=30,
                     params={"contract_types": "perpetual_futures", "page_size": 1000})
    out = {}
    for p in r.json().get("result") or []:
        if p.get("contract_type") == "perpetual_futures":
            out[p.get("symbol")] = p.get("state")
    return out


def watched_bases():
    bases = {}
    for s in config.WATCHLIST:
        b = s.split("/")[0].split(":")[0]
        for suf in ("USDT", "USD"):
            if b.endswith(suf):
                b = b[: -len(suf)]
                break
        bases[b] = s
    for s, pair in config.BITUNIX_XSTOCK_PAIRS.items():
        bases[pair.removesuffix("USDT")] = s
    return bases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=100e6)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    vols = coindcx_volumes()
    bx = bitunix_pairs()
    dl = delta_perps()
    watched = watched_bases()
    rows = []
    for base, v in sorted(vols.items(), key=lambda kv: -kv[1]):
        if v < args.min:
            continue
        # CoinDCX prefixes some with 1000 (1000PEPE); Bitunix may too.
        cands = [base + "USDT"]
        if base.startswith("1000"):
            cands.append(base[4:] + "USDT")
        else:
            cands.append("1000" + base + "USDT")
        bpair = next((c for c in cands if c in bx), None)
        bstat = (bx[bpair].get("symbolStatus") if bpair else None)
        dsym = next((d for d in (base + "USD", base + "USDT") if d in dl), None)
        rows.append({
            "base": base, "vol_musdt": round(v / 1e6, 1),
            "bitunix": bpair, "bitunix_status": bstat,
            "delta": dsym, "watched": watched.get(base),
        })
    (OUT / "coindcx_100m.json").write_text(json.dumps(rows, indent=1))
    lines = ["| CoinDCX | 24h vol (M USDT) | Bitunix | Delta | In watchlist |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['base']} | {r['vol_musdt']} | {r['bitunix'] or '-'} {r['bitunix_status'] or ''} | "
                     f"{r['delta'] or '-'} | {r['watched'] or '-'} |")
    lines.append("")
    lines.append(f"{len(vols)} CoinDCX USDT futures, {len(rows)} at >= {args.min/1e6:.0f}M; "
                 f"{len(bx)} Bitunix pairs; {len(dl)} Delta perps.")
    # Every scanned symbol: is it on CoinDCX too (any volume)? Gold/silver
    # tokens are also checked against CoinDCX's spot-metal futures.
    lines += ["", "## Current watchlist on CoinDCX", "",
              "| Symbol | CoinDCX | 24h vol (M USDT) |", "|---|---|---|"]
    near = {"XAUT": ["XAUT", "XAU", "PAXG"], "SLVON": ["SLVON", "SLV", "XAG"]}
    for base, sym in sorted(watched.items(), key=lambda kv: kv[1] not in config.CRYPTO_WATCHLIST):
        hits = [c for c in near.get(base, [base, "1000" + base]) if c in vols]
        cell = ", ".join(hits) or "-"
        vcell = ", ".join(f"{vols[c] / 1e6:.1f}" for c in hits) or "-"
        lines.append(f"| {sym} | {cell} | {vcell} |")
    text = "\n".join(lines)
    (OUT / "COINDCX_100M.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
