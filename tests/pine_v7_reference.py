"""A bar-by-bar transcription of Shiva_Indicator_v7.pine, layer 0.

Written from the Pine source and NOT from scanner.py, so the two can be diffed
against each other. Only the zone machinery is here - the signal block, zigzag
and price-action labels do not affect which zones exist.

Pine semantics this preserves, each of which the scanner had drifted from at
some point:

  * ta.pivothigh(high, L, L) confirms L bars after the pivot bar
  * farS  = ta.highest(high, win)[off],  win = 2 * base_extra + 1,
            off = swing_length - base_extra
  * nearS = f_tighten(farS, ta.highest(max(open, close), win)[off], ...)
  * a     = ta.atr(atr_len) read on the CONFIRMATION bar, and that is the
            number f_addZone measures the overlap filter against
  * f_tryCreate clears the armed rebuild when it creates a zone
  * f_tryRebuild refuses a replacement whose wick has no height, and leaves
    the rebuild armed when it does
  * order within a bar: tryCreate, then tryRebuild, then the break/touch loop
"""
import math

import numpy as np
import pandas as pd


def true_atr(df, period):
    high, low, close = df["high"], df["low"], df["close"]
    true_range = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    # ta.atr is Wilder's RMA
    return true_range.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def _pivots(values, left, right, is_high):
    out = [math.nan] * len(values)
    for i in range(left, len(values) - right):
        v = values[i]
        neighbours = list(range(i - left, i)) + list(range(i + 1, i + right + 1))
        if all((v > values[j]) if is_high else (v < values[j]) for j in neighbours):
            out[i] = v
    return out


def f_tighten(far, near0, first, win, is_sup, highs, lows, bar, max_width_pct):
    """Pine f_tighten. `first` and `win` are offsets BACK from `bar`."""
    if max_width_pct <= 0 or near0 <= 0 or far <= 0:
        return near0
    width = (far - near0) / near0 * 100 if is_sup else (near0 - far) / far * 100
    if width <= max_width_pct:
        return near0
    widest = None
    for offset in range(first, first + win):
        index = bar - offset
        if index < 0:
            continue
        c = highs[index] if is_sup else lows[index]
        inside = (near0 < c < far) if is_sup else (far < c < near0)
        if not inside:
            continue
        candidate_width = (far - c) / c * 100 if is_sup else (c - far) / far * 100
        if candidate_width <= max_width_pct:
            widest = c if widest is None else (min(widest, c) if is_sup else max(widest, c))
    if widest is not None:
        return widest
    return far / (1 + max_width_pct / 100) if is_sup else far * (1 + max_width_pct / 100)


def live_zones(
    df,
    swing_length=10,
    base_extra=5,
    atr_len=50,
    overlap_mult=1.0,
    max_width_pct=0.80,
    history_keep=50,
    keep_strongest=True,
    break_on_wick=True,
    do_rebuild=True,
    min_untouched=15,
):
    """The zones still on the chart at the end of `df`."""
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    body_hi = np.maximum(opens, closes)
    body_lo = np.minimum(opens, closes)
    atr = true_atr(df, atr_len).to_numpy(dtype=float)

    length, base = swing_length, base_extra
    win = 2 * base + 1
    off = length - base if length > base else 0

    pivot_high = _pivots(highs, length, length, True)
    pivot_low = _pivots(lows, length, length, False)
    short_high = _pivots(highs, base, base, True) if base > 0 else [math.nan] * len(df)
    short_low = _pivots(lows, base, base, False) if base > 0 else [math.nan] * len(df)

    zones = []
    pending = {1: False, -1: False}
    last_pivot = {1: -1, -1: -1}
    last_rebuild = {1: -1, -1: -1}

    def window(values, end_off, bar, reducer):
        low_index = bar - end_off - win + 1
        if low_index < 0:
            return math.nan
        return float(reducer(values[low_index:bar - end_off + 1]))

    def trim(kind, protected, bar):
        same = [z for z in zones if z["type"] == kind]
        while len(same) > history_keep:
            pool = [z for z in same if z is not protected]
            if not pool:
                break
            victim = min(pool, key=lambda z: bar - z["clock"]) if keep_strongest else pool[0]
            zones.remove(victim)
            same.remove(victim)

    def add(kind, top, bottom, atr_value, bar):
        if any(math.isnan(v) for v in (top, bottom, atr_value)):
            return False
        midpoint = (top + bottom) / 2
        threshold = atr_value * overlap_mult
        if overlap_mult > 0:
            for z in zones:
                if z["type"] == kind and abs(midpoint - (z["top"] + z["bottom"]) / 2) <= threshold:
                    return False
        zone = {"type": kind, "top": top, "bottom": bottom, "clock": bar,
                "created_idx": bar, "rebuilt": False}
        zones.append(zone)
        trim(kind, zone, bar)
        return True

    for bar in range(len(df)):
        atr_value = atr[bar]
        valid_atr = not math.isnan(atr_value) and atr_value > 0

        if valid_atr and bar - length >= 0:
            pivot = bar - length
            far_s = window(highs, off, bar, np.max)
            far_d = window(lows, off, bar, np.min)
            near_s = f_tighten(far_s, window(body_hi, off, bar, np.max), off, win,
                               True, highs, lows, bar, max_width_pct)
            near_d = f_tighten(far_d, window(body_lo, off, bar, np.min), off, win,
                               False, highs, lows, bar, max_width_pct)
            if not math.isnan(pivot_high[pivot]) and pivot > last_pivot[1]:
                last_pivot[1] = pivot
                if add(1, far_s, near_s, atr_value, bar):
                    pending[1] = False
            elif not math.isnan(pivot_low[pivot]) and pivot > last_pivot[-1]:
                last_pivot[-1] = pivot
                if add(-1, near_d, far_d, atr_value, bar):
                    pending[-1] = False

        if do_rebuild and base > 0 and valid_atr and bar - base >= 0:
            rebuild_at = bar - base
            far_s = window(highs, 0, bar, np.max)
            far_d = window(lows, 0, bar, np.min)
            near_s = f_tighten(far_s, window(body_hi, 0, bar, np.max), 0, win,
                               True, highs, lows, bar, max_width_pct)
            near_d = f_tighten(far_d, window(body_lo, 0, bar, np.min), 0, win,
                               False, highs, lows, bar, max_width_pct)
            if pending[1] and not math.isnan(short_high[rebuild_at]) and rebuild_at > last_rebuild[1]:
                if not math.isnan(far_s) and far_s > near_s:
                    last_rebuild[1] = rebuild_at
                    if add(1, far_s, near_s, atr_value, bar):
                        zones[-1]["rebuilt"] = True
                    pending[1] = False
            if pending[-1] and not math.isnan(short_low[rebuild_at]) and rebuild_at > last_rebuild[-1]:
                if not math.isnan(far_d) and near_d > far_d:
                    last_rebuild[-1] = rebuild_at
                    if add(-1, near_d, far_d, atr_value, bar):
                        zones[-1]["rebuilt"] = True
                    pending[-1] = False

        high, low, close = highs[bar], lows[bar], closes[bar]
        for zone in list(reversed(zones)):
            kind = zone["type"]
            far = zone["top"] if kind == 1 else zone["bottom"]
            if kind == 1:
                broke = high >= far if break_on_wick else close >= far
            else:
                broke = low <= far if break_on_wick else close <= far
            if broke:
                pending[kind] = True
                zones.remove(zone)
            elif high >= zone["bottom"] and low <= zone["top"]:
                if bar - zone["clock"] >= min_untouched:
                    zone["entries"] = zone.get("entries", 0) + 1
                zone["clock"] = bar

    return zones
