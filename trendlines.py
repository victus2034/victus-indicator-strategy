"""Auto trendlines - a port of Shiva_Indicator v11.0+ section 6b.

Every new swing low is joined to the earliest earlier LOWER swing low that no
swing in between undercuts (support); every new swing high to the earliest
earlier HIGHER swing high that no swing in between overshoots (resistance).
Lines extend right and stop at the bar that closes through them. Only the
newest `keep` lines per side are kept, and only the last 30 swings per side
are remembered - both as in the Pine.

A line is drawn on the bar its second swing CONFIRMS (swing bar + length), and
from then on the Pine checks each bar's close against it. Closes between the
swing bar and that confirm bar are never checked, here or on the chart.

Swings use ta.pivothigh/ta.pivotlow's rule as tests/pine_v7_reference.py
transcribes it: strictly beyond every one of `length` bars on each side.
"""
from dataclasses import dataclass

SUPPORT = 0
RESISTANCE = 1
SWING_MEMORY = 30


@dataclass
class Trendline:
    kind: int          # SUPPORT or RESISTANCE
    x1: int
    y1: float
    x2: int
    y2: float
    created: int       # bar the line appeared on (x2 + length)
    broken_at: int = None
    trimmed_at: int = None   # bar a newer line pushed it out of the newest `keep`

    def live_during(self, bar):
        """True if the chart shows this line, unbroken, while `bar` is forming."""
        return (self.created < bar
                and (self.broken_at is None or self.broken_at >= bar)
                and (self.trimmed_at is None or self.trimmed_at >= bar))

    @property
    def alive(self):
        return self.broken_at is None

    def price_at(self, bar):
        return self.y1 + (self.y2 - self.y1) * (bar - self.x1) / (self.x2 - self.x1)


def _is_pivot(values, i, length, high):
    v = values[i]
    for j in range(i - length, i + length + 1):
        if j == i:
            continue
        if (values[j] >= v) if high else (values[j] <= v):
            return False
    return True


def _best_anchor(xs, ys, nx, ny, lower):
    """Earliest earlier swing beyond which no swing in between cuts the line."""
    n = len(xs)
    best = -1
    for i in range(n - 1, -1, -1):
        if (ys[i] < ny) if lower else (ys[i] > ny):
            ok = True
            for j in range(i + 1, n):
                yl = ys[i] + (ny - ys[i]) * (xs[j] - xs[i]) / (nx - xs[i])
                if (ys[j] < yl) if lower else (ys[j] > yl):
                    ok = False
            if ok:
                best = i
    return best


def _nearest_anchor(xs, ys, nx, ny, lower):
    """Latest earlier swing beyond which no swing in between cuts the line."""
    for i in range(len(xs) - 1, -1, -1):
        if (ys[i] < ny) if lower else (ys[i] > ny):
            ok = True
            for j in range(i + 1, len(xs)):
                yl = ys[i] + (ny - ys[i]) * (xs[j] - xs[i]) / (nx - xs[i])
                if (ys[j] < yl) if lower else (ys[j] > yl):
                    ok = False
                    break
            if ok:
                return i
    return -1


def _tangent_anchor(values, xs, ys, nx, ny, lower):
    """Research (Lakky, 2026-10-07): the candle the line hugs, not a swing.

    Only when the new swing low is above the previous one (a swing high below
    the previous one) - "the last two rising swing lows". From that swing up
    to the new one, the bar whose low (high) gives the line no candle in
    between crosses. Returns (x, y) or None.
    """
    if not xs or ((ys[-1] >= ny) if lower else (ys[-1] <= ny)):
        return None
    i = len(xs) - 1
    best = None
    for k in range(xs[i], nx):
        slope = (ny - values[k]) / (nx - k)
        if best is None or ((slope > best[0]) if lower else (slope < best[0])):
            best = (slope, k)
    return best[1], values[best[1]]


def build_trendlines(highs, lows, closes, length=10, keep=6, history=False, anchor="oldest"):
    """Replay every bar as the Pine does and return the lines it would hold.

    history=True returns every line ever drawn instead, trimmed ones included,
    so a backtest can ask which were live on any past bar (Trendline.live_during).
    anchor: "oldest" is the live Pine rule; "nearest" and "tangent" are research.
    """
    def pick(values, xs, ys, nx, lower):
        if anchor == "tangent":
            return _tangent_anchor(values, xs, ys, nx, values[nx], lower)
        i = (_nearest_anchor if anchor == "nearest" else _best_anchor)(xs, ys, nx, values[nx], lower)
        return (xs[i], ys[i]) if i >= 0 else None

    n = len(closes)
    lines = []
    everything = []
    pl_x, pl_y, ph_x, ph_y = [], [], [], []

    def add(line):
        lines.append(line)
        everything.append(line)
        count = 0
        for k in range(len(lines) - 1, -1, -1):
            if lines[k].kind == line.kind:
                count += 1
                if count > keep:
                    lines[k].trimmed_at = line.created
                    del lines[k]

    for bar in range(n):
        nx = bar - length
        if nx >= length:
            if _is_pivot(lows, nx, length, high=False):
                best = pick(lows, pl_x, pl_y, nx, lower=True)
                if best:
                    add(Trendline(SUPPORT, best[0], best[1], nx, lows[nx], bar))
                pl_x.append(nx)
                pl_y.append(lows[nx])
                if len(pl_x) > SWING_MEMORY:
                    pl_x.pop(0)
                    pl_y.pop(0)
            if _is_pivot(highs, nx, length, high=True):
                best = pick(highs, ph_x, ph_y, nx, lower=False)
                if best:
                    add(Trendline(RESISTANCE, best[0], best[1], nx, highs[nx], bar))
                ph_x.append(nx)
                ph_y.append(highs[nx])
                if len(ph_x) > SWING_MEMORY:
                    ph_x.pop(0)
                    ph_y.pop(0)

        for line in lines:
            if line.alive and bar > line.x2:
                y = line.price_at(bar)
                if (closes[bar] < y) if line.kind == SUPPORT else (closes[bar] > y):
                    line.broken_at = bar

    return everything if history else lines
