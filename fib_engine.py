"""Fib engine for fib_trendline_scanner - a copy of the indicator's fib_reference.py.

The spec lives in `../indicator improvent by claude/fib_reference.py` (see FIB_SPEC.md
there), which is not in this repo, so GitHub Actions cannot import it. Everything
below the marker is that file unchanged. tests/test_fib_trendline_scanner.py fails
when the two differ, so a fib change is: edit fib_reference.py, run
fib_examples_check.py there, then copy the file body in here again.
"""
# ---- copied from fib_reference.py below this line ----
"""Reference model of the v12.0 fib zones - the spec the Pine section 6c is
transcribed from. Change this first, run fib_examples_check.py, then carry the
change into the .pine file. Plain Python, no packages needed.

Up move (d = +1): O = base (low), E = top (running high),
  P = next base, walked through the swings (N bars each side) CONFIRMED after
      the top bar, in order:
        swing low  -> becomes P if it is lower than P
        swing high that took back >= RESTART of the pullback (E - P) -> the
                      pullback leg is over; the NEXT swing low becomes P even
                      if it is higher, because the final push starts there
                      (v12.1, XAUUSD 2026-09-29: 4405.75 -> 4318.68)
      P is dropped if price trades below it.
  high > E : green box crossed. If P exists the base moves to P ("NEW FIB BASE
             ZONE"), otherwise it stays. E = this high.
             v12.3: the pullback low L (lowest low since the top, or since the
             restart swing) is used even before it confirms, when it reached
             Zone 1 (E - L >= 0.34 of the range) and is the lowest of the N bars
             before it - HYPE 1D 2026-09-29: 75.13 broke out 3 days later, a
             10-day confirmation could never arrive in time.
  low  < O : the up fib is dead -> down move, extreme = this low, origin = the
             highest swing high CONFIRMED after the lowest low since the top
             (where the final drop started - v12.3, XAUUSD 4318.68), or E if
             there is none.
Down move (d = -1) is the exact mirror.
"""
import csv


def load(path):
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    return ([r['ist'] for r in rows], [float(r['h']) for r in rows], [float(r['l']) for r in rows])


ZONE1 = 0.66     # v12.3: a pullback that reached Zone 1 (0.34 of the range) is a new base
RESTART = 0.88   # v12.1: 0.80 - 0.95 all give the same result on every example


def run(ist, h, l, N=10, restart=RESTART):
    """Returns one snapshot per bar (state AFTER that bar) and an event log."""
    n = len(h)
    d = 1
    O, Ot, E, Et = l[0], 0, h[0], 0
    P = Pt = None
    reset = False
    rb = None                          # bar of the swing that restarted the pullback leg
    SE, SEb, SQ = None, None, None     # v12.3: counter-extreme since E, and the swing after it
    snaps = [dict(ist=ist[0], d=d, O=O, Ot=0, E=E, Et=0, P=None, Pt=None, ended=False)]
    log = []

    def pivlow(j):
        return N <= j < n - N and l[j] < min(l[j - N:j]) and l[j] <= min(l[j + 1:j + N + 1])

    def pivhigh(j):
        return N <= j < n - N and h[j] > max(h[j - N:j]) and h[j] >= max(h[j + 1:j + N + 1])

    def zone1_low(i):
        # up move: lowest low since the top (or the restart swing), unconfirmed
        a = (rb if rb is not None else Et) + 1
        if a >= i:
            return None, None
        b = min(range(a, i), key=lambda k: (l[k], -k))
        ok = (b >= N and l[b] < min(l[b - N:b]) and l[b] > O
              and E - l[b] >= (1 - ZONE1) * (E - O))
        return (l[b], b) if ok else (None, None)

    def zone1_high(i):
        a = (rb if rb is not None else Et) + 1
        if a >= i:
            return None, None
        b = max(range(a, i), key=lambda k: (h[k], k))
        ok = (b >= N and h[b] > max(h[b - N:b]) and h[b] < O
              and h[b] - E >= (1 - ZONE1) * (O - E))
        return (h[b], b) if ok else (None, None)

    for i in range(1, n):
        j = i - N                      # the pivot bar that confirms on bar i
        ended = False
        if d == 1:
            if j > Et and pivhigh(j) and P is not None and h[j] - P >= restart * (E - P):
                reset, rb = True, j
            if SEb is not None and j > SEb and pivhigh(j) and h[j] < E and (SQ is None or h[j] > SQ):
                SQ = h[j]
            if j > Et and pivlow(j) and l[j] > O and (P is None or reset or l[j] < P):
                P, Pt, reset = l[j], j, False
            if h[i] > E:
                ended = i - Et >= N
                L, Lb = zone1_low(i)
                if L is not None and (P is None or L < P):
                    P, Pt = L, Lb
                if P is not None:
                    log.append((ist[i], 'top %g crossed, base %g -> %g (%s)' % (E, O, P, ist[Pt])))
                    O, Ot = P, Pt
                E, Et, P, reset, rb = h[i], i, None, False, None
            elif l[i] < O:
                ended = True
                log.append((ist[i], 'base %g broken, up fib dead, down from %g (%s)' % (O, E, ist[Et])))
                no, not_ = (SQ, None) if SQ is not None else (E, Et)
                if SQ is not None:
                    not_ = max(k for k in range(SEb + 1, i) if h[k] == SQ)
                    log.append((ist[i], '  down fib starts at last lower high %g (%s), not %g' % (SQ, ist[not_], E)))
                d, O, Ot, E, Et, P, reset, rb = -1, no, not_, l[i], i, None, False, None
            elif P is not None and l[i] < P:
                P = None
        else:
            if j > Et and pivlow(j) and P is not None and P - l[j] >= restart * (P - E):
                reset, rb = True, j
            if SEb is not None and j > SEb and pivlow(j) and l[j] > E and (SQ is None or l[j] < SQ):
                SQ = l[j]
            if j > Et and pivhigh(j) and h[j] < O and (P is None or reset or h[j] > P):
                P, Pt, reset = h[j], j, False
            if l[i] < E:
                ended = i - Et >= N
                L, Lb = zone1_high(i)
                if L is not None and (P is None or L > P):
                    P, Pt = L, Lb
                if P is not None:
                    log.append((ist[i], 'bottom %g crossed, top %g -> %g (%s)' % (E, O, P, ist[Pt])))
                    O, Ot = P, Pt
                E, Et, P, reset, rb = l[i], i, None, False, None
            elif h[i] > O:
                ended = True
                log.append((ist[i], 'top %g broken, down fib dead, up from %g (%s)' % (O, E, ist[Et])))
                no, not_ = (SQ, None) if SQ is not None else (E, Et)
                if SQ is not None:
                    not_ = max(k for k in range(SEb + 1, i) if l[k] == SQ)
                    log.append((ist[i], '  up fib starts at last higher low %g (%s), not %g' % (SQ, ist[not_], E)))
                d, O, Ot, E, Et, P, reset, rb = 1, no, not_, h[i], i, None, False, None
            elif P is not None and h[i] > P:
                P = None
        if Et == i:                    # new top/bottom (or flip): counter-extreme starts over
            SE, SEb, SQ = None, None, None
        elif d == 1 and (SE is None or l[i] < SE):
            SE, SEb, SQ = l[i], i, None
        elif d == -1 and (SE is None or h[i] > SE):
            SE, SEb, SQ = h[i], i, None
        snaps.append(dict(ist=ist[i], d=d, O=O, Ot=Ot, E=E, Et=Et, P=P, Pt=Pt, ended=ended))
    return snaps, log


def levels(a, b):
    """[upper 0.66, upper 0.55, lower 0.55, lower 0.66] - the four labels, top to bottom."""
    lo, hi = min(a, b), max(a, b)
    r = hi - lo
    return [lo + .66 * r, lo + .55 * r, hi - .55 * r, hi - .66 * r]


def sl_lines(a, b, d):
    """EX 2: the SL fib inside each zone -> [(upper 0.66, upper 0.55), (lower 0.66, lower 0.55)]."""
    u66, u55, d55, d66 = levels(a, b)
    w = u66 - u55
    if d == 1:
        return [(u55 + .66 * w, u55 + .55 * w), (d66 + .66 * w, d66 + .55 * w)]
    return [(u66 - .66 * w, u66 - .55 * w), (d55 - .66 * w, d55 - .55 * w)]
