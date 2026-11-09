"""Old app (full/) vs fixed app (fixed/) vs 15m + scanner booking (real/): key cells, with fees."""
import json
import numpy as np
A = json.load(open('full/alerts.json')); RU = json.load(open('full/rules.json'))
A2 = json.load(open('fixed/alerts.json')); RU2 = json.load(open('fixed/rules.json'))
assert [a['key'] for a in A] == [a['key'] for a in A2]
assert RU == RU2
N = len(A)
L = lambda d: np.fromfile(d + '/r.f32', dtype=np.float32).reshape(len(RU), N)
F, X, R = L('full'), L('fixed'), L('real')
def rid(tgt, hold='tp', stop='off', trail='off'):
    for j, r in enumerate(RU):
        if r['tgt'] == tgt and r['hold'] == hold and r['stop'] == stop and r['trail'] == trail:
            return j
    raise KeyError((tgt, hold, stop, trail))
T25 = 'TP +0.25R, SL 0R behind'
rules = {'Scanner': rid(''), '1R': rid('1R'), '2R': rid('2R'), '3R': rid('3R'), '1R trail': rid('1R', trail=T25), '3R trail': rid('3R', trail=T25),
         '1.5R 20c': rid('1.5R', hold='20')}
kind = np.array([a['kind'] for a in A]); ch = np.array([a['chan'] for a in A]); lvl = np.array([a['lvl'] for a in A]); tl = np.array([a['tl'] for a in A])
cells = {'Fib all': kind == 'fib', 'Fib 4H': (kind == 'fib') & (ch == 'CRYPTO 4H'), 'Fib 1D': (kind == 'fib') & (ch == 'CRYPTO 1D'),
         'Fib 1D L4': (kind == 'fib') & (ch == 'CRYPTO 1D') & (lvl == 'L4'), 'TL all': kind == 'trendline', 'Support TL': tl == 'support',
         'Resistance TL': tl == 'resistance', 'SP TL BR': tl == 'spbr', 'RS TL BR': tl == 'rsbr', 'RS TL BR 1D': (tl == 'rsbr') & (ch == 'CRYPTO 1D')}
out = []
def s(a):
    g = ~np.isnan(a)
    return int(g.sum()), round(float(np.nansum(a)), 1)
for cn, m in cells.items():
    for rn, j in rules.items():
        (fn, ft), (xn, xt), (rn_, rt) = s(F[j, m]), s(X[j, m]), s(R[j, m])
        out.append(dict(cell=cn, rule=rn, old_n=fn, old=ft, fixed_n=xn, fixed=xt, real_n=rn_, real=rt))
        print(f"{cn:<13} {rn:<9} old {fn:>5} {ft:>8}   fixed {xn:>5} {xt:>8}   15m {rn_:>5} {rt:>8}")
d = lambda P, Q: float((np.abs(np.nan_to_num(P, nan=-99) - np.nan_to_num(Q, nan=-99)) > 1e-3).mean() * 100)
print('alert x rule results differing  old vs 15m: %.2f%%   fixed vs 15m: %.2f%%' % (d(F, R), d(X, R)))
# walk rules only (not Scanner)
wr = [j for j, r in enumerate(RU) if r['tgt'] != '']
print('walk rules only              old vs 15m: %.2f%%   fixed vs 15m: %.2f%%' % (d(F[wr], R[wr]), d(X[wr], R[wr])))
json.dump(out, open('fixed/compare.json', 'w'), indent=1)
