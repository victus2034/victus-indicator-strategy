"""real/ = the 15m grid with the fib "Scanner" exit booked by the scanner's own rule (2R + BE, fees in)."""
import os
import gzip, json, numpy as np
D = os.environ.get('JBT_DATA', 'research/out/journal_bt') + '/'
res = json.load(gzip.open(D + 'fibtl_rebuild_results.json.gz', 'rt'))
A = json.load(open('fine/alerts.json')); RU = json.load(open('fine/rules.json')); N = len(A)
R = np.fromfile('fine/r.f32', dtype=np.float32).reshape(len(RU), N).copy()
assert RU[0]['tgt'] == ''
COST, SLIP, BE = 0.0826, 0.05, 0.0933
changed = 0
for a in A:
    if a['kind'] != 'fib':
        continue
    i = a['i']; x = res.get(a['key'])
    if a['scanR'] is None or x is None:
        R[0, i] = np.nan; continue
    e, sl = a['entry'], a['stop']; rp = abs(e - sl) / e * 100; c = COST / rp
    sgn = -1 if a['side'] == 'short' else 1
    v = 2 - c if x.get('r2') else (-1 - (sl / e) * SLIP / rp - c) if x.get('sl') else ((BE - (1 + sgn * BE / 100) * SLIP) / rp - c) if x.get('be') else np.nan
    if not (np.isnan(v) and np.isnan(R[0, i])) and abs((0 if np.isnan(v) else v) - (0 if np.isnan(R[0, i]) else R[0, i])) > 1e-4:
        changed += 1
    R[0, i] = v
R.tofile('real/r.f32')
f = R[0][[a['i'] for a in A if a['kind'] == 'fib']]
print('fib scanner alerts re-booked:', changed, '| graded', int((~np.isnan(f)).sum()), 'total', round(float(np.nansum(f)), 1))
