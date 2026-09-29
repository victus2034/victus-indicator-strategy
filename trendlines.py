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


def build_trendlines(highs, lows, closes, length=10, keep=6):
    """Replay every bar as the Pine does and return the lines it would hold."""
    n = len(closes)
    lines = []
    pl_x, pl_y, ph_x, ph_y = [], [], [], []

    def add(line):
        lines.append(line)
        count = 0
        for k in range(len(lines) - 1, -1, -1):
            if lines[k].kind == line.kind:
                count += 1
                if count > keep:
                    del lines[k]

    for bar in range(n):
        nx = bar - length
        if nx >= length:
            if _is_pivot(lows, nx, length, high=False):
                best = _best_anchor(pl_x, pl_y, nx, lows[nx], lower=True)
                if best >= 0:
                    add(Trendline(SUPPORT, pl_x[best], pl_y[best], nx, lows[nx], bar))
                pl_x.append(nx)
                pl_y.append(lows[nx])
                if len(pl_x) > SWING_MEMORY:
                    pl_x.pop(0)
                    pl_y.pop(0)
            if _is_pivot(highs, nx, length, high=True):
                best = _best_anchor(ph_x, ph_y, nx, highs[nx], lower=False)
                if best >= 0:
                    add(Trendline(RESISTANCE, ph_x[best], ph_y[best], nx, highs[nx], bar))
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

    return lines
