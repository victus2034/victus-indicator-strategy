"""Coins and BTC day (same day = the app's, previous day = known when the alert fires), realistic grid."""
import gzip, json, os, sys
from datetime import datetime, timedelta, timezone
import numpy as np
run = 'real'
A = json.load(open(f'{run}/alerts.json')); RU = json.load(open(f'{run}/rules.json')); N = len(A)
R = np.fromfile(f'{run}/r.f32', dtype=np.float32).reshape(len(RU), N).astype(np.float64)
cf = os.environ.get('JBT_DATA', 'research/out/journal_bt') + '/candles/BTCUSD_1d.json.gz'
day = {datetime.fromtimestamp(c[0], timezone.utc).strftime('%Y-%m-%d'): (c[4] - c[1]) / c[1] * 100 for c in json.load(gzip.open(cf))['candles']}
bias = lambda p: None if p is None else 'bull' if p > 1.5 else 'bear' if p < -1.5 else 'side'
IST = timezone(timedelta(hours=5, minutes=30))
prev = []
for a in A:
    t = datetime.strptime(a['date'] + ' ' + a['time'], '%Y-%m-%d %H:%M').replace(tzinfo=IST).astimezone(timezone.utc)
    prev.append(bias(day.get((t - timedelta(days=1)).strftime('%Y-%m-%d'))))
prev = np.array(prev, dtype=object); same = np.array([a['btc'] for a in A], dtype=object)
coin = np.array([a['coin'] for a in A]); kind = np.array([a['kind'] for a in A]); ch = np.array([a['chan'].replace('CRYPTO ', '') for a in A]); tl = np.array([a['tl'] for a in A])
def rid(tgt, hold='tp', stop='off', trail='off'):
    return next(j for j, r in enumerate(RU) if r['tgt'] == tgt and r['hold'] == hold and r['stop'] == stop and r['trail'] == trail)
RULE = {'Scanner': rid(''), '3R + trail': rid('3R', trail='TP +0.25R, SL 0.25R behind')}
cells = {'Fib 4H': (kind == 'fib') & (ch == '4H'), 'Fib 1D': (kind == 'fib') & (ch == '1D'), 'Support TL': tl == 'support', 'Resistance TL': tl == 'resistance',
         'SP TL BR': tl == 'spbr', 'RS TL BR': tl == 'rsbr'}
COINS = {'All': None, 'Top 3': {'BTC', 'ETH', 'XRP'}, 'Top 5': {'BTC', 'ETH', 'XRP', 'BNB', 'SOL'}, 'Coins only': 'coins', 'xStocks + XAUT/SLVON': 'other'}
def st(m, j):
    x = R[j, m]; x = x[~np.isnan(x)]
    return (len(x), round(float(x.sum()), 1), round(float(x.mean()), 3) if len(x) else None)
out = {'coins': [], 'btc': []}
for cn, m in cells.items():
    for rn, j in RULE.items():
        row = {'cell': cn, 'rule': rn}
        for k, s in COINS.items():
            mm = m if s is None else m & (coin != '') if s == 'coins' else m & (coin == '') if s == 'other' else m & np.isin(coin, list(s))
            row[k] = st(mm, j)
        out['coins'].append(row)
        row = {'cell': cn, 'rule': rn}
        for b in ['bull', 'bear', 'side']:
            row['same ' + b] = st(m & (same == b), j); row['prev ' + b] = st(m & (prev == b), j)
        out['btc'].append(row)
json.dump(out, open(f'{run}/filters.json', 'w'), indent=1)
f = lambda v: f"{v[2]:+.2f} ({v[0]})" if v[2] is not None else '-'
print('COINS'); [print(r['cell'].ljust(14), r['rule'].ljust(10), ' | '.join(f'{k}: {f(r[k])}' for k in COINS)) for r in out['coins']]
print('BTC'); [print(r['cell'].ljust(14), r['rule'].ljust(10), ' | '.join(f"{k}: {f(r[k])}" for k in ['same bull', 'prev bull', 'same bear', 'prev bear', 'same side', 'prev side'])) for r in out['btc']]
