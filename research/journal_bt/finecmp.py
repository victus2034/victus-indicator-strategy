"""App-candle grid (full/) vs every walk on 15m candles (fine/): key cells, with fees."""
import json
import numpy as np
A = json.load(open('full/alerts.json')); RU = json.load(open('full/rules.json'))
N = len(A)
F = np.fromfile('full/r.f32', dtype=np.float32).reshape(len(RU), N)
G = np.fromfile('fine/r.f32', dtype=np.float32).reshape(len(RU), N)
def rid(tgt, hold='tp', stop='off', trail='off'):
    for j, r in enumerate(RU):
        if r['tgt'] == tgt and r['hold'] == hold and r['stop'] == stop and r['trail'] == trail:
            return j
    raise KeyError((tgt, hold, stop, trail))
T25 = 'TP +0.25R, SL 0R behind'
rules = {'Scanner': rid(''), '1R': rid('1R'), '1R trail': rid('1R', trail=T25), '3R trail': rid('3R', trail=T25),
         '2% trail': rid('2%', trail=[r['trail'] for r in RU if r['tgt'] == '2%' and r['trail'] != 'off'][0]),
         '1.5R 20c': rid('1.5R', hold='20')}
kind = np.array([a['kind'] for a in A]); ch = np.array([a['chan'] for a in A]); lvl = np.array([a['lvl'] for a in A]); tl = np.array([a['tl'] for a in A])
cells = {'Fib all': kind == 'fib', 'Fib 4H': (kind == 'fib') & (ch == 'CRYPTO 4H'), 'Fib 1D': (kind == 'fib') & (ch == 'CRYPTO 1D'),
         'Fib L1': (kind == 'fib') & (lvl == 'L1'), 'TL all': kind == 'trendline', 'Support TL': tl == 'support', 'Resistance TL': tl == 'resistance',
         'SP TL BR': tl == 'spbr', 'RS TL BR': tl == 'rsbr'}
out = []
for cn, m in cells.items():
    for rn, j in rules.items():
        a, b = F[j, m], G[j, m]
        ga, gb = ~np.isnan(a), ~np.isnan(b)
        both = ga & gb
        diff = int((np.abs(np.nan_to_num(a) - np.nan_to_num(b)) > 1e-4).sum())
        out.append(dict(cell=cn, rule=rn, app_n=int(ga.sum()), app_total=round(float(np.nansum(a)), 1), app_avg=round(float(np.nanmean(a)), 3) if ga.any() else None,
                        fine_n=int(gb.sum()), fine_total=round(float(np.nansum(b)), 1), fine_avg=round(float(np.nanmean(b)), 3) if gb.any() else None,
                        alerts_changed=diff))
w = max(len(o['cell']) for o in out)
for o in out:
    print(f"{o['cell']:<14} {o['rule']:<10} app {o['app_n']:>5} {o['app_total']:>8} ({o['app_avg']})  15m {o['fine_n']:>5} {o['fine_total']:>8} ({o['fine_avg']})  changed {o['alerts_changed']}")
tot = (np.abs(np.nan_to_num(F) - np.nan_to_num(G)) > 1e-4)
print('share of alert x rule results that differ:', round(float(tot.mean()) * 100, 2), '%')
json.dump(out, open('fine/compare.json', 'w'), indent=1)
