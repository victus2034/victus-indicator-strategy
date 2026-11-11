"""RESEARCH ONLY - not live (lakky, 2026-11-11: "do not ship it until i say").

The fib the way lakky draws it (his BTC / UNI / ETH / SOL / ADA / NEAR 1D charts, Nov 2026).
Same snapshots as `fib_engine.run`, different rules:

  base    the last pullback low before the top - the most recent swing low (BASE_N candles each
          side; the right side may still be short) since the previous top. "Where the trend starts",
          not the lowest low. A new top moves the base up to the newest pullback low.
  broken  a candle CLOSES past the last level (L4, 0.66 of the range from the top) and the next
          candle trades past that candle's low; or price trades under the base itself.
          (Live: one wick past the stop, 0.6875.)
  then    step back to the older base: the most recent earlier swing low that is lower, same top
          (BTC 1D: 74,916 -> 62,505 on 30 Oct; UNI 1D: 5.815 -> 3.168 on 13 Oct). Only when no
          older low of this up move is left does the fib flip to the opposite side, and that one
          starts from the last swing high before the break.
  turn    the counter move since the top (the pullback) becomes a fib of its own once its low has
          reversed: it reached this fib's first level (0.34 of the range), it is still the lowest
          low since the top and BASE_N candles have closed after it. Then the fib is the SELL fib
          from the last swing high down to that low. This is how a BUY fib appears after a rally
          inside an old, unbroken SELL fib (ETH / ADA 1D, Aug - Oct): the fib follows the most
          recent extreme that has reversed, never one that is still forming.
  closes  only closed candles are passed in, so the forming candle never sets a low or a high.

Down fibs are the mirror. `run(..., c=closes)`; without `c` the closes come from CLOSES["c"]
(set by the backtest wrapper, which calls `run(stamp, highs, lows, N=...)` like the live engine).
"""
ZONE1 = 0.66
BASE_N = 3
STEPS = 2        # how many older bases a broken fib may step back to before it flips
REBOUND = 0          # share of the pullback price must take back for a new fib from its low (0 = off)
MIN_GAP = 0      # an older base must be lower by this share of the fib's range, or it is the same low
TURN = False     # research switch: a reversed pullback becomes the opposite fib
CLOSES = {"c": []}


def run(ist, h, l, N=10, restart=None, c=None, base_n=None, steps=None, turn_on=None):
    n = len(h)
    c = CLOSES["c"] if c is None else c
    assert len(c) == n, "closes do not match the candles"
    B = base_n or BASE_N
    max_steps = STEPS if steps is None else steps
    turn_on = TURN if turn_on is None else turn_on
    used = 0                           # step-backs since the last new top / flip
    d, O, Ot, E, Et, T0 = 1, l[0], 0, h[0], 0, 0
    fresh = False
    R = Rb = None                      # counter-extreme since the fib's extreme (the pullback so far)
    snaps = [dict(ist=ist[0], d=d, O=O, Ot=0, E=E, Et=0, P=None, Pt=None, ended=False)]
    log = []

    def swing(j, i, s):
        """Bar j is a swing low (s = 1) / high (s = -1) as seen on bar i (right side up to i)."""
        if j < 1 or j >= i:
            return False
        a, b = max(0, j - B), min(j + B, i)
        if s == 1:
            return l[j] < min(l[a:j]) and l[j] <= min(l[j + 1:b + 1])
        return h[j] > max(h[a:j]) and h[j] >= max(h[j + 1:b + 1])

    def newest(a, b, i, s):
        for j in range(b - 1, a - 1, -1):
            if swing(j, i, s):
                return j
        return None

    for i in range(1, n):
        ended = False
        up = d == 1
        s = 1 if up else -1
        x, y = (h, l) if up else (l, h)        # x: the side the extreme is on, y: the base side
        past = (lambda p, q: p > q) if up else (lambda p, q: p < q)
        turn = (turn_on and R is not None and i - Rb >= B and swing(Rb, i, s)
                and abs(E - R) >= (1 - ZONE1) * abs(E - O) and not past(x[i], E) and not past(R, y[i]))
        back = (REBOUND and R is not None and not past(x[i], E) and not past(R, y[i])
                and past(x[i], R + s * REBOUND * abs(E - R)) and abs(E - R) >= (1 - ZONE1) * abs(E - O))
        if back:
            # the pullback is over: price took back REBOUND of it. New fib from the pullback low
            # (lakky: "if it go to the up trend from the 30 oct then 30 oct will be new low";
            # HYPE 1D 74.411 (24 Oct) -> 97.13 (29 Oct), under the 23 Sep top).
            log.append((ist[i], "pullback %g (%s) taken back, new %s fib from it" % (R, ist[Rb], "up" if up else "down")))
            O, Ot, E, Et, fresh, ended, used = R, Rb, x[i], i, False, True, 0
        elif turn:
            j = newest(Ot + 1, Rb, i, -s)
            no, nt = (x[j], j) if j is not None else (E, Et)
            log.append((ist[i], "%s %g (%s) has reversed: %s fib from %g (%s)"
                        % ("low" if up else "high", R, ist[Rb], "down" if up else "up", no, ist[nt])))
            d, T0, O, Ot, E, Et, fresh, ended = -d, Ot, no, nt, R, Rb, False, True
        elif past(x[i], E):
            j = newest(Et + 1, i, i, s)
            if j is not None and past(y[j], O) and j > Ot:
                log.append((ist[i], "%s %g crossed, base %g -> %g (%s)" % ("top" if up else "bottom", E, O, y[j], ist[j])))
                O, Ot, ended = y[j], j, True
            E, Et, fresh = x[i], i, False
            used = 0 if ended else used
        else:
            L4 = E - s * ZONE1 * abs(E - O)
            hit = past(O, y[i])
            two = not fresh and past(L4, c[i - 1]) and past(y[i - 1], y[i])
            if hit or two:
                ended = True
                cur, found = O - s * MIN_GAP * abs(E - O), None
                for j in (range(Ot - 1, T0 - 1, -1) if used < max_steps else ()):
                    if (j == T0 or swing(j, i, s)) and past(cur, y[j]):
                        if not past(y[j], y[i]):
                            found = j
                            break
                        cur = y[j]
                if found is not None:
                    log.append((ist[i], "%s fib %g broken (%s), back to the older base %g (%s)"
                                % ("up" if up else "down", O, "base" if hit else "2 candles past L4", y[found], ist[found])))
                    O, Ot, used = y[found], found, used + 1
                else:
                    j = newest(Et, i, i, -s)
                    no, nt = (x[j], j) if j is not None and past(x[j], y[i]) else (E, Et)
                    log.append((ist[i], "%s fib %g -> %g broken, no older base: %s fib from %g (%s)"
                                % ("up" if up else "down", O, E, "down" if up else "up", no, ist[nt])))
                    d, T0, O, Ot, E, Et, fresh, used = -d, Et, no, nt, y[i], i, True, 0
        if Et == i or turn or d != (1 if up else -1):
            R = Rb = None
        if Et != i:
            yy = l if d == 1 else h
            lo = i if (turn or d != (1 if up else -1)) else (Rb if R is not None else i)
            for k in range(max(Et + 1, lo), i + 1):
                if R is None or (yy[k] < R if d == 1 else yy[k] > R):
                    R, Rb = yy[k], k
        snaps.append(dict(ist=ist[i], d=d, O=O, Ot=Ot, E=E, Et=Et, P=None, Pt=None, ended=ended))
    return snaps, log
