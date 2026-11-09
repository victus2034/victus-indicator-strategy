"""Stats for every "which alerts" x "how each trade is played" combination.

Reads the harness output (alerts.json, rules.json, r.f32 = one R per alert per rule set,
NaN = no result) and writes one row per kind / channel / coins / BTC day / level-or-type /
rule set / fees, with the Signals strip's numbers: alerts, graded, wins, win %, total R,
average R, profit factor, max drawdown, worst losing run, best / worst, % price move,
and the same split Jan-May vs Jun-Nov.

python3 aggregate.py RUN_DIR OUT_DIR [--split 2026-06-01]
"""
import csv
import gzip
import json
import sys
from pathlib import Path

import numpy as np

run, out = Path(sys.argv[1]), Path(sys.argv[2])
split = sys.argv[sys.argv.index("--split") + 1] if "--split" in sys.argv else "2026-06-01"
out.mkdir(parents=True, exist_ok=True)
alerts = json.loads((run / "alerts.json").read_text())
rules = json.loads((run / "rules.json").read_text())
N = len(alerts)
R_all = np.fromfile(run / "r.f32", dtype=np.float32).reshape(len(rules), N)

TOP3, TOP5, PICKS = {"BTC", "ETH", "XRP"}, {"BTC", "ETH", "XRP", "BNB", "SOL"}, {"BTC", "ETH", "SOL"}
CHANS = ["", "CRYPTO 4H", "CRYPTO 1D", "CRYPTO 1W", "CRYPTO 1MO"]
COINS = [("All", None), ("Top 3", TOP3), ("Top 5", TOP5), ("Picks BTC/ETH/SOL", PICKS)]
BTC = ["", "bull", "bear", "side"]
SUBS = {"fib": ["", "L1", "L2", "L3", "L4"], "trendline": ["", "support", "resistance", "spbr", "rsbr"]}
SUB_LABEL = {"": "All", "support": "Support TL", "resistance": "Resistance TL", "spbr": "SP TL BR", "rsbr": "RS TL BR"}
BTC_LABEL = {"": "All days", "bull": "Bullish", "bear": "Bearish", "side": "Sideways"}


def sample_word(n):
    return "too few (<30)" if n < 30 else "early (30-99)" if n < 100 else "fair (100-299)" if n < 300 else "solid (300+)"


def stats(R, slp):
    """R: rules x k (time order), NaN = no result. Returns dict of per-rule arrays."""
    if R.shape[1] == 0:
        z = np.zeros(len(R))
        return dict(n=z.astype(int), win=z.astype(int), loss=z.astype(int), tot=z, pf=z * np.nan, mdd=z, mls=z.astype(int),
                    best=z * np.nan, worst=z * np.nan, pct=z)
    g = ~np.isnan(R)
    R0 = np.where(g, R, 0.0).astype(np.float64)
    n = g.sum(1)
    win = (R0 > 0).sum(1)
    loss = (R0 < 0).sum(1)
    tot = R0.sum(1)
    gw = np.where(R0 > 0, R0, 0).sum(1)
    gl = -np.where(R0 < 0, R0, 0).sum(1)
    eq = np.cumsum(R0, 1)
    peak = np.maximum.accumulate(np.maximum(eq, 0), 1)
    mdd = (peak - eq).max(1) if R.shape[1] else np.zeros(len(R))
    lz = (R0 < 0).astype(np.int32)
    reset = g & (R0 >= 0)
    c = np.cumsum(lz, 1)
    last = np.maximum.accumulate(np.where(reset, c, 0), 1)
    mls = (c - last).max(1) if R.shape[1] else np.zeros(len(R))
    with np.errstate(invalid="ignore", divide="ignore"):
        best = np.where(n > 0, np.nanmax(np.where(g, R0, -np.inf), 1), np.nan)
        worst = np.where(n > 0, np.nanmin(np.where(g, R0, np.inf), 1), np.nan)
        pct = (R0 * slp[None, :]).sum(1)
        pf = np.where(gl > 0, gw / np.where(gl > 0, gl, 1), np.where(gw > 0, np.inf, np.nan))
    return dict(n=n, win=win, loss=loss, tot=tot, pf=pf, mdd=mdd, mls=mls, best=best, worst=worst, pct=pct)


def fmt(v, d=4):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if v == np.inf:
        return "inf"
    return f"{v:.{d}f}"


HEAD = ["kind", "channel", "coins", "btc_day", "level_or_type", "exit_at", "move_sl", "trail_tp", "hold", "fees",
        "alerts", "graded", "wins", "losses", "win_pct", "total_r", "avg_r", "profit_factor", "max_dd_r",
        "worst_losing_run", "best_r", "worst_r", "total_pct_move", "avg_pct_move", "sample",
        "janmay_graded", "janmay_total_r", "janmay_avg_r", "junnov_graded", "junnov_total_r", "junnov_avg_r"]

files = {}
rows_written = 0
for kind in ["fib", "trendline"]:
    idx = [a["i"] for a in alerts if a["kind"] == kind]
    # sigGraded's order: by date + time, ties kept in the app's order.
    idx.sort(key=lambda i: (alerts[i]["when"], i))
    A = [alerts[i] for i in idx]
    if not A:
        continue
    R = R_all[:, idx]
    feeR = np.array([a["feeR"] or 0 for a in A], dtype=np.float64)
    slp = np.array([a["slp"] or 0 for a in A], dtype=np.float64)
    chan = np.array([a["chan"] for a in A])
    coin = np.array([a["coin"] for a in A])
    btc = np.array([a["btc"] for a in A])
    sub = np.array([a["lvl"] if kind == "fib" else a["tl"] for a in A])
    early = np.array([a["date"] < split for a in A])
    for ch in CHANS:
        mc = np.ones(len(A), bool) if not ch else chan == ch
        if not mc.any():
            continue
        for cl, cs in COINS:
            mk = mc if cs is None else mc & np.isin(coin, list(cs))
            for b in BTC:
                mb = mk if not b else mk & (btc == b)
                for s in SUBS[kind]:
                    m = mb if not s else mb & (sub == s)
                    k = int(m.sum())
                    for fees in ("with", "without"):
                        Rm = R[:, m].astype(np.float64)
                        if fees == "without":
                            Rm = Rm + feeR[m][None, :]
                        st = stats(Rm, slp[m])
                        e1 = stats(Rm[:, early[m]], slp[m][early[m]])
                        e2 = stats(Rm[:, ~early[m]], slp[m][~early[m]])
                        for j, ru in enumerate(rules):
                            tk = ru["tgt"] or "Scanner"
                            key = (kind, tk)
                            if key not in files:
                                fh = gzip.open(out / f"{kind}_exit_{tk.replace('%', 'pct').replace('.', '_')}.csv.gz", "wt", newline="")
                                w = csv.writer(fh)
                                w.writerow(HEAD)
                                files[key] = (fh, w)
                            n = int(st["n"][j])
                            if k == 0:
                                continue
                            w = files[key][1]
                            avg = st["tot"][j] / n if n else np.nan
                            w.writerow([kind, ch.replace("CRYPTO ", "").replace("1MO", "1M") or "All", cl, BTC_LABEL[b], SUB_LABEL.get(s, s),
                                        tk, ru.get("stop", "off") if ru["tgt"] else "n/a (scanner rules)",
                                        ru.get("trail", "off") if ru["tgt"] else "n/a (scanner rules)",
                                        ("Till TP / SL" if ru["hold"] == "tp" else "20 candles") if ru["tgt"] else "n/a (scanner rules)", fees,
                                        k, n, int(st["win"][j]), int(st["loss"][j]), fmt(st["win"][j] / n * 100 if n else np.nan, 1),
                                        fmt(st["tot"][j], 3), fmt(avg, 4), fmt(st["pf"][j], 3), fmt(st["mdd"][j], 3), int(st["mls"][j]),
                                        fmt(st["best"][j], 3), fmt(st["worst"][j], 3), fmt(st["pct"][j], 2), fmt(st["pct"][j] / n if n else np.nan, 3),
                                        sample_word(n),
                                        int(e1["n"][j]), fmt(e1["tot"][j], 3), fmt(e1["tot"][j] / e1["n"][j] if e1["n"][j] else np.nan, 4),
                                        int(e2["n"][j]), fmt(e2["tot"][j], 3), fmt(e2["tot"][j] / e2["n"][j] if e2["n"][j] else np.nan, 4)])
                            rows_written += 1
    print(kind, "done", rows_written, flush=True)
for fh, _ in files.values():
    fh.close()
print("rows", rows_written)
