"""Fib "Scanner" exit three ways: the journal's booking, TP at 1R (as the alert prints), the scanner's own 2R + BE."""
import os
import gzip, json, collections
D = os.environ.get('JBT_DATA', 'research/out/journal_bt') + '/'
res = json.load(gzip.open(D + 'fibtl_rebuild_results.json.gz', 'rt'))
A = json.load(open('full/alerts.json'))
COST, SLIP, BE = 0.0826, 0.05, 0.0933
def book(a, x):
    e, sl = a['entry'], a['stop']; rp = abs(e - sl) / e * 100; c = COST / rp
    sgn = -1 if a['side'] == 'short' else 1
    SL = -1 - (sl / e) * SLIP / rp - c; BEr = (BE - (1 + sgn * BE / 100) * SLIP) / rp - c
    closed = SL if x.get('sl') else BEr if x.get('be') else None
    tp1 = 1 - c if x.get('r1') else closed
    s2 = 2 - c if x.get('r2') else closed
    return tp1, s2
out = collections.defaultdict(lambda: [0, 0.0, 0, 0.0, 0, 0.0, 0])
rows = []
for a in A:
    if a['kind'] != 'fib' or a['scanR'] is None:
        continue
    x = res.get(a['key'])
    if x is None:
        continue
    tp1, s2 = book(a, x)
    for cell in ['Fib all', 'Fib ' + a['chan'].replace('CRYPTO ', ''), 'Fib ' + a['lvl'], 'Fib 1D ' + a['lvl'] if a['chan'] == 'CRYPTO 1D' else None]:
        if not cell:
            continue
        o = out[cell]
        o[0] += 1; o[1] += a['scanR']
        if tp1 is not None: o[2] += 1; o[3] += tp1
        if s2 is not None: o[4] += 1; o[5] += s2
        if x['outcome'] == '1R' and x.get('be'): o[6] += 1
print(f"{'cell':<12} {'journal Scanner':>22} {'TP 1R (alert text)':>22} {'scanner 2R+BE':>22}  1R-then-BE")
tab = []
for k in sorted(out):
    o = out[k]
    print(f"{k:<12} {o[0]:>5} {o[1]:>8.1f} ({o[1]/o[0]:+.3f}) {o[2]:>5} {o[3]:>8.1f} ({o[3]/max(o[2],1):+.3f}) {o[4]:>5} {o[5]:>8.1f} ({o[5]/max(o[4],1):+.3f})  {o[6]}")
    tab.append(dict(cell=k, journal_n=o[0], journal_total_r=round(o[1], 1), tp1r_n=o[2], tp1r_total_r=round(o[3], 1), scanner_2r_be_n=o[4], scanner_2r_be_total_r=round(o[5], 1), one_r_then_be=o[6]))
json.dump(tab, open('full/scanner_booking.json', 'w'), indent=1)
