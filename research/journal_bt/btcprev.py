"""The app's BTC day is the alert day's own daily candle (open -> close, UTC), only known
once that day closes. Here the same cells split by the PREVIOUS UTC day's BTC candle,
which is known when the alert fires."""
import gzip, json, sys
from datetime import datetime, timedelta, timezone
import numpy as np
run, cfile = sys.argv[1], sys.argv[2]
alerts = json.load(open(f"{run}/alerts.json")); rules = json.load(open(f"{run}/rules.json"))
R = np.fromfile(f"{run}/r.f32", dtype=np.float32).reshape(len(rules), len(alerts))
day = {datetime.fromtimestamp(c[0], timezone.utc).strftime("%Y-%m-%d"): (c[4] - c[1]) / c[1] * 100 for c in json.load(gzip.open(cfile))["candles"]}
bias = lambda p: None if p is None else "bull" if p > 1.5 else "bear" if p < -1.5 else "side"
IST = timezone(timedelta(hours=5, minutes=30))
prev, same = [], []
for a in alerts:
    t = datetime.strptime(a["date"] + " " + a["time"], "%Y-%m-%d %H:%M").replace(tzinfo=IST).astimezone(timezone.utc)
    d0 = t.strftime("%Y-%m-%d"); d1 = (t - timedelta(days=1)).strftime("%Y-%m-%d")
    same.append(bias(day.get(d0))); prev.append(bias(day.get(d1)))
prev, same = np.array(prev, dtype=object), np.array(same, dtype=object)
agree = np.mean([s == a["btc"] for s, a in zip(same, alerts) if a["btc"]])
print(f"same-day labels match the app's: {agree:.4f}")
def ridx(tgt, stop="off", trail="off", hold="tp"):
    return next(i for i, r in enumerate(rules) if (r["tgt"] or "") == tgt and (not tgt or (r["stop"] == stop and r["trail"] == trail and r["hold"] == hold)))
cells = [("fib", "CRYPTO 1D", "", ""), ("fib", "", "", ""), ("fib", "CRYPTO 4H", "", ""), ("trendline", "", "rsbr", ""), ("trendline", "", "spbr", ""),
         ("trendline", "", "support", ""), ("trendline", "", "resistance", "")]
picks = [("Scanner", ridx("")), ("3R + trail 0.25R/0R", ridx("3R", trail="TP +0.25R, SL 0R behind")), ("2% + trail 0.25%/0%", ridx("2%", trail="TP +0.25%, SL 0% behind"))]
out = []
for kind, ch, tl, _ in cells:
    m0 = np.array([a["kind"] == kind and (not ch or a["chan"] == ch) and (not tl or a["tl"] == tl) for a in alerts])
    for lab, j in picks:
        row = {"kind": kind, "channel": ch.replace("CRYPTO ", "") or "All", "type": tl or "All", "rule": lab}
        for split, lab2 in [(same, "same day (app)"), (prev, "previous day")]:
            for b in ["bull", "bear", "side"]:
                r = R[j, m0 & (split == b)]; r = r[~np.isnan(r)]
                row[f"{lab2} {b}"] = f"{r.sum():+.1f}R / {len(r)} ({(r.mean() if len(r) else 0):+.2f})"
        out.append(row)
for r in out:
    print(r["kind"], r["channel"], r["type"], "|", r["rule"])
    for lab2 in ["same day (app)", "previous day"]:
        print("    ", lab2.ljust(15), " | ".join(f"{b}: {r[f'{lab2} {b}']}" for b in ["bull", "bear", "side"]))
json.dump(out, open(f"{run}/btc_prev_day.json", "w"), indent=1)
