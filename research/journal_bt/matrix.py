import json, sys, numpy as np
run = sys.argv[1]
A = json.load(open(run + '/alerts.json')); RU = json.load(open(run + '/rules.json')); N = len(A)
R = np.fromfile(run + '/r.f32', dtype=np.float32).reshape(len(RU), N).astype(np.float64)
def rid(tgt, hold='tp', stop='off', trail='off'):
    return next(j for j, r in enumerate(RU) if r['tgt'] == tgt and r['hold'] == hold and r['stop'] == stop and r['trail'] == trail)
rules = {'Scanner': rid(''), '1R': rid('1R'), '2R': rid('2R'), '3R': rid('3R'),
         '3R trail .25/.25': rid('3R', trail='TP +0.25R, SL 0.25R behind'),
         '3R trail .5/.25 shift': rid('3R', stop='SL to +0.25R at +1.5R', trail='TP +0.5R, SL 0.25R behind'),
         'CoinDCX rule': rid('1.5R', stop='SL to +0.75R at +1R', trail='TP +0.25R, SL 0.5R behind'),
         'Screenshot rule': rid('1%', trail='TP +0.25%, SL 0.25% behind')}
kind = np.array([a['kind'] for a in A]); ch = np.array([a['chan'].replace('CRYPTO ', '').replace('1MO', '1M') for a in A])
lvl = np.array([a['lvl'] for a in A]); tl = np.array([a['tl'] for a in A])
cells = {'Fib 4H': (kind == 'fib') & (ch == '4H'), 'Fib 1D': (kind == 'fib') & (ch == '1D'), 'Fib 1W': (kind == 'fib') & (ch == '1W'),
         'Fib 1D L1': (kind == 'fib') & (ch == '1D') & (lvl == 'L1'), 'Fib 1D L2': (kind == 'fib') & (ch == '1D') & (lvl == 'L2'),
         'Fib 1D L3': (kind == 'fib') & (ch == '1D') & (lvl == 'L3'), 'Fib 1D L4': (kind == 'fib') & (ch == '1D') & (lvl == 'L4'),
         'Support TL': tl == 'support', 'Resistance TL': tl == 'resistance',
         'SP TL BR 4H': (tl == 'spbr') & (ch == '4H'), 'SP TL BR 1D': (tl == 'spbr') & (ch == '1D'),
         'RS TL BR 4H': (tl == 'rsbr') & (ch == '4H'), 'RS TL BR 1D': (tl == 'rsbr') & (ch == '1D')}
out = []
for cn, m in cells.items():
    row = {'cell': cn}
    for rn, j in rules.items():
        x = R[j, m]; n = int((~np.isnan(x)).sum())
        row[rn] = [n, round(float(np.nansum(x)), 1), round(float(np.nanmean(x)), 3) if n else None]
    out.append(row)
json.dump(out, open(run + '/matrix.json', 'w'), indent=1)
print('cell'.ljust(14), ' | '.join(k[:14].ljust(14) for k in rules))
for r in out:
    print(r['cell'].ljust(14), ' | '.join(f"{r[k][1]:>6} {r[k][2]:+.2f}".ljust(14) for k in rules), ' n', r['Scanner'][0], r['1R'][0])
