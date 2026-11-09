"""Ranked summary of the full grid (aggregate.py output) -> summary.json + top/bottom CSVs."""
import json
import sys
from pathlib import Path

import pandas as pd

agg, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
cols = None
frames = []
for f in sorted(agg.glob("*.csv.gz")):
    cat = {c: "category" for c in ["kind", "channel", "coins", "btc_day", "level_or_type", "exit_at", "move_sl", "trail_tp", "hold", "fees", "sample"]}
    d = pd.read_csv(f, dtype=cat, low_memory=False)
    d = d[d["graded"] > 0]
    frames.append(d)
df = pd.concat(frames, ignore_index=True)
for c in ["kind", "channel", "coins", "btc_day", "level_or_type", "exit_at", "move_sl", "trail_tp", "hold", "fees", "sample"]:
    df[c] = df[c].astype(str)
df["profit_factor"] = pd.to_numeric(df["profit_factor"].replace("inf", float("inf")), errors="coerce")
print("rows with results", len(df))
WHICH = ["kind", "channel", "coins", "btc_day", "level_or_type"]
HOW = ["exit_at", "move_sl", "trail_tp", "hold", "fees"]
SHOW = WHICH + HOW + ["alerts", "graded", "win_pct", "total_r", "avg_r", "profit_factor", "max_dd_r", "worst_losing_run",
                      "total_pct_move", "avg_pct_move", "sample", "janmay_graded", "janmay_avg_r", "junnov_graded", "junnov_avg_r"]
df["both_halves_up"] = (df["janmay_avg_r"] > 0) & (df["junnov_avg_r"] > 0)
wf = df[df["fees"] == "with"]
base = (wf["channel"] == "All") & (wf["coins"] == "All") & (wf["btc_day"] == "All days") & (wf["level_or_type"] == "All")
S = {}


def rec(d):
    return json.loads(d[SHOW + ["both_halves_up"]].to_json(orient="records"))


# 1) The scanner's own rules vs the best / worst rule set, every alert of a kind.
for kind in ["fib", "trendline"]:
    k = wf[base & (wf["kind"] == kind)]
    S[f"{kind}_all"] = {"scanner": rec(k[k["exit_at"] == "Scanner"]), "best_total": rec(k.nlargest(10, "total_r")),
                        "worst_total": rec(k.nsmallest(5, "total_r")), "rule_sets": int(len(k)),
                        "positive_rule_sets": int((k["total_r"] > 0).sum()), "both_halves_up": int(k["both_halves_up"].sum())}

# 2) Per channel (coins / BTC day / level all): scanner, best and worst rule set.
for kind in ["fib", "trendline"]:
    for ch in ["4H", "1D", "1W", "1M"]:
        k = wf[(wf["kind"] == kind) & (wf["channel"] == ch) & (wf["coins"] == "All") & (wf["btc_day"] == "All days") & (wf["level_or_type"] == "All")]
        if not len(k):
            continue
        S[f"{kind}_{ch}"] = {"scanner": rec(k[k["exit_at"] == "Scanner"]), "best_total": rec(k.nlargest(3, "total_r")),
                             "best_avg_30": rec(k[k["graded"] >= 30].nlargest(3, "avg_r")), "worst_total": rec(k.nsmallest(3, "total_r")),
                             "rule_sets": int(len(k)), "positive_rule_sets": int((k["total_r"] > 0).sum())}

# 3) Top / bottom combos of everything (which x how), with fees, by sample size.
for kind in ["fib", "trendline"]:
    k = wf[wf["kind"] == kind]
    for lab, mn in [("n100", 100), ("n300", 300), ("n30", 30)]:
        kk = k[k["graded"] >= mn]
        S[f"{kind}_top_total_{lab}"] = rec(kk.nlargest(25, "total_r"))
        S[f"{kind}_top_avg_{lab}"] = rec(kk.nlargest(25, "avg_r"))
        S[f"{kind}_top_avg_steady_{lab}"] = rec(kk[kk["both_halves_up"] & (kk["janmay_graded"] >= mn / 3) & (kk["junnov_graded"] >= mn / 3)].nlargest(25, "avg_r"))
        S[f"{kind}_bottom_total_{lab}"] = rec(kk.nsmallest(15, "total_r"))

# 4) One filter at a time: for each value, the best rule set (others All), with fees, 30+ graded.
for kind in ["fib", "trendline"]:
    k = wf[(wf["kind"] == kind) & (wf["graded"] >= 30)]
    eff = {}
    for dim, vals in [("channel", None), ("coins", None), ("btc_day", None), ("level_or_type", None)]:
        others = [d for d in ["channel", "coins", "btc_day", "level_or_type"] if d != dim]
        kk = k
        for o in others:
            kk = kk[kk[o] == ("All" if o != "btc_day" else "All days")]
        eff[dim] = {v: {"scanner": rec(g[g["exit_at"] == "Scanner"]), "best": rec(g.nlargest(1, "total_r")), "best_avg": rec(g.nlargest(1, "avg_r"))}
                    for v, g in kk.groupby(dim, observed=True)}
    S[f"{kind}_one_filter"] = eff

# 5) Each "how" setting on its own, averaged over every rule set it is part of (All view, with fees).
for kind in ["fib", "trendline"]:
    k = wf[base & (wf["kind"] == kind) & (wf["exit_at"] != "Scanner")]
    S[f"{kind}_how_effects"] = {h: json.loads(k.groupby(h)[["total_r", "avg_r", "win_pct"]].agg(["mean", "max"]).round(3).to_json(orient="index"))
                                for h in ["exit_at", "hold", "move_sl", "trail_tp"]}

(out / "summary.json").write_text(json.dumps(S, indent=1))
wf.sort_values("total_r", ascending=False).head(2000)[SHOW + ["both_halves_up"]].to_csv(out / "top_2000_with_fees.csv", index=False)
wf[wf["graded"] >= 100].sort_values("avg_r", ascending=False).head(2000)[SHOW + ["both_halves_up"]].to_csv(out / "top_2000_avg_r_100plus.csv", index=False)
wf.sort_values("total_r").head(1000)[SHOW + ["both_halves_up"]].to_csv(out / "bottom_1000_with_fees.csv", index=False)
print("done")
