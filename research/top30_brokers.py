"""Research only: the top 30 cryptos by trading volume, and whether each is on
both of lakky's brokers (lakky, 2026-11-14: "make sure top30 cryptos are
available in coindcx and delta").

Ranks every CoinDCX USDT future by its average daily traded value over the last
30 complete UTC days (the journal's Top 10 / 20 / 30 rule, SIG_VOL30), and marks
for each coin: a live Delta India perp, a Bitunix perp (the scanner's candles),
already scanned (config.CRYPTO_WATCHLIST), and the 2026-11-08 pump/dump chart
check (coin_list_review.chart_check: a 40%+ day, a 10x volume day, or listed
under 90 days). Gold, silver, oil and xStocks are left out.

Writes research/out/top30/TOP30.md and top30.json. Posts nothing, touches no state.
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config                                               # noqa: E402
from coin_list_review import (COMMODITIES, chart_check, delta_descriptions,   # noqa: E402
                              is_xstock, pct)
from coindcx_volume_probe import bitunix_pairs              # noqa: E402
from volume_7d_30d_probe import coindcx, delta, norm_base   # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "top30"
STABLES = {"USDC", "FDUSD", "TUSD", "DAI", "USDE", "USD1", "PYUSD", "BUSD", "USDP", "EUR", "EURC"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--show", type=int, default=50, help="rows in the CoinDCX table")
    ap.add_argument("--max-day", type=float, default=40.0)
    ap.add_argument("--max-spike", type=float, default=10.0)
    ap.add_argument("--min-age", type=int, default=90)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    lim_day = math.log(1 + a.max_day / 100)

    cd, cd_note = coindcx()
    dl, dl_note = delta()
    desc = delta_descriptions()
    bx = bitunix_pairs()
    scanned = {norm_base(s.split("/")[0].removesuffix("USD")) for s in config.CRYPTO_WATCHLIST}

    dmap = {}
    for b, v in dl.items():
        if is_xstock(b, desc.get(b, "")):
            continue
        dmap[norm_base(b)] = {"d7": v[0] / 1e6, "d30": v[1] / 1e6, "sym": v[4]}

    rows = []
    for b, v in cd.items():
        nb = norm_base(b)
        if nb in COMMODITIES or nb in STABLES:
            continue
        d = dmap.get(nb)
        pair = next((p for p in (nb + "USDT", "1000" + nb + "USDT") if p in bx), None)
        rows.append({"base": nb, "dcx_symbol": b, "dcx7": v[0] / 1e6, "dcx30": v[1] / 1e6,
                     "delta": d["sym"] if d else None, "d7": d["d7"] if d else 0.0, "d30": d["d30"] if d else 0.0,
                     "bitunix": pair, "scanned": nb in scanned})
    # Delta-only coins (not on CoinDCX) for completeness
    have = {r["base"] for r in rows}
    for nb, d in dmap.items():
        if nb in have or nb in COMMODITIES or nb in STABLES:
            continue
        rows.append({"base": nb, "dcx_symbol": None, "dcx7": 0.0, "dcx30": 0.0, "delta": d["sym"],
                     "d7": d["d7"], "d30": d["d30"],
                     "bitunix": next((p for p in (nb + "USDT", "1000" + nb + "USDT") if p in bx), None),
                     "scanned": nb in scanned})
    rows.sort(key=lambda r: -r["dcx30"])
    for i, r in enumerate(rows):
        r["dcx_rank"] = i + 1 if r["dcx_symbol"] else None
        r["both"] = bool(r["dcx_symbol"] and r["delta"])

    # chart check on everything that can make either table
    both = [r for r in rows if r["both"]]
    look = {r["base"] for r in rows[: a.show]} | {r["base"] for r in both[: a.top + 10]} | scanned
    for r in rows:
        r["chart"], r["flags"] = None, []
        if r["base"] not in look or not r["bitunix"]:
            continue
        try:
            ch = chart_check(r["bitunix"])
        except Exception as exc:                # one bad pair must not stop the table
            r["flags"] = ["error: " + str(exc)[:60]]
            continue
        r["chart"] = ch
        if not ch:
            r["flags"] = ["no candles"]
            continue
        if ch["day"] >= lim_day:
            r["flags"].append(f"day {pct(ch['day']):.0f}%")
        if ch["spike"] >= a.max_spike:
            r["flags"].append(f"vol spike {ch['spike']:.0f}x")
        if ch["age"] < a.min_age:
            r["flags"].append(f"listed {ch['age']}d")
    (OUT / "top30.json").write_text(json.dumps(rows, indent=1, default=str))

    yn = lambda x: "yes" if x else "**no**"

    def line(i, r):
        return (f"| {i} | {r['base']} | {r['dcx30']:.1f} | {r['dcx7']:.1f} | {yn(r['delta'])} | {r['d30']:.1f} | "
                f"{yn(r['bitunix'])} | {'yes' if r['scanned'] else '-'} | {', '.join(r['flags']) or '-'} |")

    head = ["| # | Coin | DCX 30d | DCX 7d | On Delta | Delta 30d | On Bitunix | Scanned | Chart flags |",
            "|---|---|---|---|---|---|---|---|---|"]
    top_dcx = [r for r in rows if r["dcx_symbol"]][: a.show]
    top_both = both[: a.top]
    clean = [r for r in top_both if r["bitunix"] and not r["flags"]]
    not_delta = [r["base"] for r in [r for r in rows if r["dcx_symbol"]][: a.top] if not r["delta"]]
    top_names = {r["base"] for r in top_both}
    out_of_top = sorted(b for b in scanned if b not in top_names)
    missing = [r["base"] for r in top_both if not r["scanned"]]

    text = "\n".join([
        f"# Top {a.top} cryptos by volume, on CoinDCX and Delta (M USDT a day)", "",
        f"- Rank: average daily traded value on CoinDCX USDT futures over the last 30 complete UTC days (the journal's Top 10/20/30 rule)",
        f"- {cd_note}", f"- {dl_note}", f"- Bitunix: {len(bx)} pairs (the scanner's candles)",
        f"- Chart flags (Bitunix 1d, 90 days, the 8 Nov rule): a {a.max_day:.0f}%+ day, a {a.max_spike:.0f}x volume day, or listed < {a.min_age} days", "",
        "## Summary", "",
        f"- CoinDCX top {a.top} not on Delta: {', '.join(not_delta) or 'none'}",
        f"- Top {a.top} on BOTH brokers: {', '.join(r['base'] for r in top_both)}",
        f"- ... of those with a Bitunix perp and no pump/dump flag: {len(clean)} ({', '.join(r['base'] for r in clean)})",
        f"- Scanner watches {len(scanned)} crypto; outside the top {a.top} on both: {', '.join(out_of_top) or 'none'}",
        f"- Top {a.top} on both that the scanner does not watch: {', '.join(missing) or 'none'}", "",
        f"## Top {a.top} on both CoinDCX and Delta", ""] + head
        + [line(i + 1, r) for i, r in enumerate(top_both)]
        + ["", f"## CoinDCX top {a.show} (any Delta listing)", ""] + head
        + [line(r["dcx_rank"], r) for r in top_dcx] + [""])
    (OUT / "TOP30.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
