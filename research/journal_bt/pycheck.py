"""Second check, written apart from the journal's code: re-score alerts from the saved
Delta candles in plain Python (fixed target, fixed stop) and compare with the harness."""
import gzip, json, math, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np

run, cdir, now = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
alerts = json.loads((run / "alerts.json").read_text())
rules = json.loads((run / "rules.json").read_text())
R = np.fromfile(run / "r.f32", dtype=np.float32).reshape(len(rules), len(alerts))
IST = timezone(timedelta(hours=5, minutes=30))
RES = [(1, "1m"), (5, "5m"), (15, "15m"), (60, "1h"), (240, "4h"), (1440, "1d")]
TFM = {"4H": 240, "1D": 1440, "1W": 10080, "1MO": 43200}
COST, SLIP = 0.0826, 0.05
cache = {}

def series(sym, res):
    k = (sym, res)
    if k not in cache:
        f = cdir / f"{sym}_{res}.json.gz"
        cache[k] = json.load(gzip.open(f))["candles"] if f.exists() else []
    return cache[k]

def score(a, tgt, hold):
    tfm = TFM[a["tf"]]
    t0 = int(datetime.strptime(a["date"] + " " + a["time"], "%Y-%m-%d %H:%M").replace(tzinfo=IST).timestamp() * 1000)
    nowms = now * 1000
    span = max(nowms - t0, 3600000) if hold == "tp" else 40 * tfm * 60000
    rm, rn = next((r for r in RES if span / (r[0] * 60000) <= 1900), RES[-1])
    frm, to = t0 - rm * 60000, min(nowms, t0 + span)
    rows = [c for c in series(a["dsym"], rn) if frm // 1000 <= c[0] <= math.ceil(to / 1000)]
    if not rows:
        return None
    resms, tfms = rm * 60000, tfm * 60000
    bars = [(c[0] * 1000, c[2], c[3], c[4]) for c in rows if c[2] > 0 and c[3] > 0 and c[4] > 0 and c[0] * 1000 + resms > t0]
    e, sl, s = a["entry"], a["stop"], (-1 if a["side"] == "short" else 1)
    fi = next((i for i, b in enumerate(bars) if b[0] < t0 + 20 * tfms and (b[2] <= e if s > 0 else b[1] >= e)), -1)
    if fi < 0:
        return None
    end = math.inf if hold == "tp" else bars[fi][0] + 20 * tfms
    risk = abs(e - sl) / e * 100
    costR = COST / risk
    tR = tgt[0] if tgt[1] == "R" else tgt[0] / risk
    d = tR * risk / 100
    mv = lambda p: s * (p - e) / e
    hit = lambda b: b[2] <= sl if s > 0 else b[1] >= sl
    slR = -1 - (sl / e) * SLIP / risk - costR
    f = bars[fi]
    if hit(f):
        return slR
    m = max(0, mv(f[3])); last = f
    for b in bars[fi + 1:]:
        if b[0] >= end:
            break
        last = b
        if hit(b):
            return tR - costR if m >= d - 1e-12 else slR
        m = max(m, mv(b[1] if s > 0 else b[2]))
    if m >= d - 1e-12:
        return tR - costR
    done = hold != "tp" and last[0] + resms >= end
    return mv(last[3]) * 100 / risk - costR if done else None

for tgt, hold in [((1, "R"), "20"), ((2, "%"), "20"), ((2, "R"), "tp"), ((1, "%"), "tp")]:
    tk = f"{tgt[0]}{tgt[1]}"
    j = next(i for i, r in enumerate(rules) if r["tgt"] == tk and r["hold"] == hold and r["stop"] == "off" and r["trail"] == "off")
    same = diff = both_none = 0; ex = []
    for i, a in enumerate(alerts):
        if a["why"]:
            continue
        p = score(a, tgt, hold); h = R[j, i]
        if p is None and np.isnan(h): both_none += 1
        elif p is not None and not np.isnan(h) and abs(p - h) < 2e-3: same += 1
        else:
            diff += 1
            if len(ex) < 5: ex.append((a["sym"], a["tf"], a["date"], a["time"], p, float(h)))
    print(f"{tk} hold {hold}: same {same}, both no result {both_none}, differ {diff}", ex)
