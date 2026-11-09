"""Key cells straight from r.f32 (with fees): scanner, best / worst rule sets, positive count, both halves."""
import json, sys, numpy as np
run = sys.argv[1]
A = json.load(open(run + '/alerts.json')); RU = json.load(open(run + '/rules.json')); N = len(A)
R = np.fromfile(run + '/r.f32', dtype=np.float32).reshape(len(RU), N).astype(np.float64)
kind = np.array([a['kind'] for a in A]); ch = np.array([a['chan'].replace('CRYPTO ', '').replace('1MO', '1M') for a in A])
lvl = np.array([a['lvl'] for a in A]); tl = np.array([a['tl'] for a in A]); early = np.array([a['date'] < '2026-06-01' for a in A])
def name(j):
    r = RU[j]
    if not r['tgt']: return 'Scanner'
    p = [r['tgt']]
    if r['stop'] != 'off': p.append(r['stop'])
    if r['trail'] != 'off': p.append('trail ' + r['trail'].replace('TP ', '').replace(', SL ', ' / ').replace(' behind', ' behind'))
    p.append('till TP/SL' if r['hold'] == 'tp' else '20 candles')
    return ' · '.join(p)
cells = {}
for c in ['All', '4H', '1D', '1W', '1M']:
    cells[f'Fib {c}'] = (kind == 'fib') & ((ch == c) if c != 'All' else True)
for l in ['L1', 'L2', 'L3', 'L4']:
    cells[f'Fib {l}'] = (kind == 'fib') & (lvl == l)
    cells[f'Fib 1D {l}'] = (kind == 'fib') & (lvl == l) & (ch == '1D')
TLN = {'support': 'Support TL', 'resistance': 'Resistance TL', 'spbr': 'SP TL BR', 'rsbr': 'RS TL BR'}
cells['TL All'] = kind == 'trendline'
for t, tn in TLN.items():
    for c in ['All', '4H', '1D', '1W']:
        cells[f'{tn} {c}'] = (tl == t) & ((ch == c) if c != 'All' else True)
out = {}
for cn, m in cells.items():
    X = R[:, m]; g = ~np.isnan(X); n = g.sum(1); tot = np.nansum(X, 1)
    avg = np.where(n > 0, tot / np.maximum(n, 1), np.nan)
    win = np.where(n > 0, (np.nan_to_num(X) > 0).sum(1) / np.maximum(n, 1) * 100, np.nan)
    gw = np.where(np.nan_to_num(X) > 0, np.nan_to_num(X), 0).sum(1); gl = -np.where(np.nan_to_num(X) < 0, np.nan_to_num(X), 0).sum(1)
    pf = np.where(gl > 0, gw / np.maximum(gl, 1e-9), np.inf)
    e = early[m]; X1, X2 = X[:, e], X[:, ~e]
    a1 = np.nansum(X1, 1) / np.maximum((~np.isnan(X1)).sum(1), 1); a2 = np.nansum(X2, 1) / np.maximum((~np.isnan(X2)).sum(1), 1)
    eq = np.cumsum(np.nan_to_num(X), 1); dd = (np.maximum.accumulate(np.maximum(eq, 0), 1) - eq).max(1) if X.shape[1] else np.zeros(len(RU))
    row = lambda j: dict(rule=name(j), graded=int(n[j]), win_pct=round(float(win[j]), 1), total_r=round(float(tot[j]), 1), avg_r=round(float(avg[j]), 3),
                         pf=round(float(pf[j]), 2), max_dd_r=round(float(dd[j]), 1), janmay_avg=round(float(a1[j]), 3), junnov_avg=round(float(a2[j]), 3))
    ok = n >= 30
    order = np.argsort(-np.where(ok, tot, -1e9))
    worst = np.argsort(np.where(ok, tot, 1e9))
    out[cn] = dict(alerts=int(m.sum()), scanner=row(0), best=[row(j) for j in order[:3]], worst=row(worst[0]),
                   positive=int(((tot > 0) & ok).sum()), steady=int(((a1 > 0) & (a2 > 0) & ok).sum()), rule_sets=int(ok.sum()))
json.dump(out, open(run + '/keycells.json', 'w'), indent=1)
for cn, o in out.items():
    b = o['best'][0]; s = o['scanner']
    print(f"{cn:<20} n{o['alerts']:>5} | scanner {s['graded']:>4} {s['total_r']:>7} ({s['avg_r']:+.3f}) | best {b['total_r']:>7} ({b['avg_r']:+.3f}, n{b['graded']}, PF {b['pf']}, DD {b['max_dd_r']}, halves {b['janmay_avg']:+.2f}/{b['junnov_avg']:+.2f}) {b['rule']} | pos {o['positive']}/{o['rule_sets']}")
