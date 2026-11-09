"""Check 2: the app's own Signals strip (ui_check.json) vs the runner's grid rows."""
import gzip, csv, json, re, sys
from pathlib import Path
agg = Path(sys.argv[1]); ui = json.load(open(sys.argv[2]))
def num(s):
    m = re.search(r"([+-]?\d+(?:\.\d+)?)", s.replace(",", "")); return float(m.group(1)) if m else None
bad = 0
for x in ui:
    c, cards = x["c"], x["res"]["cards"]
    row = dict(c["row"])
    if c["label"].startswith("fib 1D 1% shift1->0.5"): row["move_sl"] = "off"  # at = target never fires: same as off
    tk = row["exit_at"]
    f = agg / f"{row['kind']}_exit_{tk.replace('%','pct').replace('.','_')}.csv.gz"
    hit = None
    for r in csv.DictReader(gzip.open(f, "rt")):
        if all(r[k] == v for k, v in row.items()):
            hit = r; break
    get = lambda lab: next(cd for cd in cards if cd.startswith(lab))
    app = {"alerts": num(get("Alerts")), "graded": sum(map(float, re.search(r"(\d+)W / (\d+)L", get("Win rate")).groups())),
           "total_r": num(get("Total R").split("Total R")[1]), "avg_r": num(get("Average R").split("Average R")[1]),
           "pf": num(get("Profit factor").split("Profit factor")[1]), "mdd": num(get("Max drawdown").split("Max drawdown")[1].replace("-", "")),
           "mls": num(get("Max drawdown").split("worst run:")[1])}
    mine = {"alerts": float(hit["alerts"]), "graded": float(hit["graded"]), "total_r": round(float(hit["total_r"]), 2), "avg_r": round(float(hit["avg_r"]), 2),
            "pf": round(float(hit["profit_factor"]), 2), "mdd": round(float(hit["max_dd_r"]), 2), "mls": float(hit["worst_losing_run"])} if hit else None
    ok = mine is not None and all(abs(app[k] - mine[k]) < 0.011 for k in app)
    bad += not ok
    print("OK  " if ok else "DIFF", c["label"], "\n   app ", app, "\n   grid", mine)
print("mismatches", bad)
