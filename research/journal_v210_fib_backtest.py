"""lakky's journal v210 Signals setup for 1D crypto fibs, replayed independently (2026-11-24:
"check this and tell should we implement this and is it poss").

His Signals screen (journal v210, Period All):
  - Crypto, CRYPTO 1D, Assets Crypto, Coins CoinDCX (the 22 watchlist coins), Levels on L2 + L4
  - BTC move = BTC flat: BTC's price at the alert (close of the last closed 15m candle) within
    +-1.5% of its 00:00 UTC (05:30 IST) daily open. Live-safe: nothing after the alert is read.
  - SL "Body" at least 1% past entry: walking back over the 300 daily candles closed before the
    alert, the first body (open / close) at least 1% past the alert's entry; none = left out
  - Early entry 0.05%: the limit sits 0.05% before the entry (above for a buy); the stop and
    every level stay at the alert's prices; R is counted from the fill
  - Exit 2R; SL shift at +1R -> +0.25R; Trail TP +1R step, SL 1R behind (never below 2R once hit)
  - Hold 20 candles: closed at the close of the 20th daily candle after the fill (Time exit)
  - fill within 20 days of the alert; the fill candle can only stop out; a candle touching the
    stop and a target is the stop; a moved stop counts from the next candle; stops slip 0.05%;
    fees 0.0826% of the position (the journal's tgtScore, re-written here from its rules)

Compared, on the same alerts, with the CoinDCX demo's fib rules (the only fib trading the bot
does today: alert SL, 1.5R, trail +0.25R / 0.5R behind, SL shift +1R -> +0.75R, held till stop).

Alerts: every 1D crypto fib alert today's live rules would send (fib_trendline_backtest.replay,
Bitunix candles), the alert moment = the 15m candle that first enters the band; walks on Bitunix
15m candles after it only. Fills within 15 min of US CPI / PPI / FOMC are left out.

    PYTHONPATH=research python research/journal_v210_fib_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bitunix_data  # noqa: E402
import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, HISTORY_START, bitunix_candles  # noqa: E402
from journal_fib_setup_backtest import IST, ist, news_overlap  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "journal_v210_fib"
DAY = 86400
FEE, SLIP = 0.0826, 0.05
FILL_SECONDS = 20 * DAY
BTC_FLAT_PCT = 1.5


@dataclass(frozen=True)
class Rules:
    name: str
    levels: tuple
    sl: str            # "body" (1% past entry) or "alert"
    target: float
    shift_at: float
    shift_to: float
    step: float        # trail step (0 = no trail)
    gap: float
    hold: int | None   # seconds after the fill candle's open, None = till stop
    early: float       # % before the entry
    btc: str           # "flat" or "" (every day)


V210 = Rules("lakky v210 (L2+L4, BTC flat)", ("L2", "L4"), "body", 2.0, 1.0, 0.25, 1.0, 1.0, 20 * DAY, 0.05, "flat")
V210_ALL_DAYS = Rules("v210, every BTC day", ("L2", "L4"), "body", 2.0, 1.0, 0.25, 1.0, 1.0, 20 * DAY, 0.05, "")
V210_NO_EARLY = Rules("v210, no early entry", ("L2", "L4"), "body", 2.0, 1.0, 0.25, 1.0, 1.0, 20 * DAY, 0.0, "flat")
DEMO = Rules("bot's fib demo rules (L2-L4)", ("L2", "L3", "L4"), "alert", 1.5, 1.0, 0.75, 0.25, 0.5, None, 0.0, "")
DEMO_L24_FLAT = Rules("demo rules, L2+L4, BTC flat", ("L2", "L4"), "alert", 1.5, 1.0, 0.75, 0.25, 0.5, None, 0.0, "flat")
ALL_RULES = (V210, V210_ALL_DAYS, V210_NO_EARLY, DEMO, DEMO_L24_FLAT)


# ----------------------------------------------------------------- the rules

def body_stop(daily, t0, entry, s, gap_pct=1.0, lookback=300):
    """The first body (open / close) at least gap_pct past entry, walking back over the
    candles closed before t0. daily = [ts, o, h, l, c]."""
    closed = [c for c in daily if c[0] + DAY <= t0][-lookback:]
    edge = entry * (1 - s * gap_pct / 100)
    for c in reversed(closed):
        b = min(c[1], c[4]) if s > 0 else max(c[1], c[4])
        if (b <= edge) if s > 0 else (b >= edge):
            return b
    return None


def play(base, stop0, s, bars, t0, r: Rules):
    """bars = [ts, h, l, c, seconds] after t0, oldest first."""
    fill = base * (1 + s * r.early / 100)
    rp = abs(base - stop0) / base * 100              # risk from the alert's entry
    fp = abs(fill - stop0) / fill * 100              # risk from the fill
    adv = s * (fill - base) / base * 100
    out = {"risk_pct": fp}
    hit = lambda b, lvl: (b[2] <= lvl) if s > 0 else (b[1] >= lvl)
    mv = lambda px: s * (px - base) / base * 100 / rp
    fi = next((i for i, b in enumerate(bars) if b[0] < t0 + FILL_SECONDS and hit(b, fill)), None)
    if fi is None:
        seen = bars[-1][0] + bars[-1][4] if bars else 0
        return {**out, "outcome": "waiting" if seen < t0 + FILL_SECONDS else "no fill"}
    f = bars[fi]
    out["fill_ts"] = f[0]

    def done(rb, why, ts):
        rr = (rb * rp - adv) / (rp + adv) - FEE / fp
        return {**out, "outcome": why, "r": rr, "exit_ts": ts}

    sl_r = -1 - (stop0 / base) * SLIP / rp
    if hit(f, stop0):
        return done(sl_r, "SL", f[0])
    end = f[0] + r.hold if r.hold else float("inf")
    stop, why, tgt = None, "", r.target

    def lift(best):
        nonlocal stop, why, tgt
        if r.step:
            while best >= tgt - 1e-9:
                lvl = max(r.target, tgt - r.gap)
                if stop is None or lvl > stop + 1e-9:
                    stop, why = lvl, "Trail TP"
                tgt += r.step
        if r.shift_at < r.target - 1e-9 and best >= r.shift_at - 1e-9 and (stop is None or r.shift_to > stop + 1e-9):
            stop, why = r.shift_to, "SL shift"

    best = max(0.0, mv(f[3]))
    if not r.step and best >= r.target - 1e-9:
        return done(r.target, "Target", f[0])
    lift(best)
    last = f
    for b in bars[fi + 1:]:
        if b[0] >= end:
            break
        last = b
        lvl = stop0 if stop is None else base * (1 + s * stop * rp / 100)
        if hit(b, lvl):
            rb = sl_r if stop is None else stop - (1 + s * stop * rp / 100) * SLIP / rp
            return done(rb, "SL" if stop is None else why, b[0])
        best = max(best, mv(b[1] if s > 0 else b[2]))
        if not r.step and best >= r.target - 1e-9:
            return done(r.target, "Target", b[0])
        lift(best)
    if r.hold and last[0] + last[4] >= end:
        return done(mv(last[3]), "Time exit", last[0])
    return {**out, "outcome": "open"}


def btc_move(btc15, t0):
    """BTC's % move at t0: the last closed 15m close vs its UTC day's first 15m open."""
    px = None
    for k in range(1, 5):
        c = btc15.get(t0 - k * 900)
        if c:
            px = c[3]
            break
    day = btc15.get(t0 // DAY * DAY)
    if not px or not day:
        return None
    return (px - day[0]) / day[0] * 100


# ----------------------------------------------------------------- data + replay

def candles(symbol, now, since):
    contract = scanner.delta_contract(symbol)
    pair = bitunix_data.pair_for(symbol, contract)
    get = lambda res, start: fbt._cached(f"jf_{pair}_{res}_{int(start) // DAY}", lambda: bitunix_candles(pair, res, start, now))
    return get("1d", HISTORY_START), get("4h", HISTORY_START), get("15m", since - 3 * DAY)


def symbol_alerts(symbol, since, now):
    daily, four, m15 = candles(symbol, now, since)
    fine = [[c[0], c[2], c[3], c[4], 900] for c in m15]
    band = fbt.band_for("1d")
    out = []
    for t in fbt.replay(CRYPTO, symbol, "1d", daily, four, now):
        if t["kind"] != "fib" or t["alert_ts"] < since or t.get("level") not in ("L2", "L3", "L4"):
            continue
        p = t["plan"]
        s = -1 if p["side"] == "short" else 1
        edge = p["entry"] * (1 + s * band)
        t0 = next((b[0] + 900 for b in fine if t["alert_ts"] <= b[0] < t["alert_ts"] + 4 * 3600
                   and ((b[2] <= edge) if s > 0 else (b[1] >= edge))), t["alert_ts"] + 4 * 3600)
        bars = [b for b in fine if b[0] >= t0]
        row = {"symbol": symbol, "level": t["level"], "side": p["side"], "entry": p["entry"], "alert_sl": p["sl"],
               "alert_ts": t0, "body_sl": body_stop(daily, t0, p["entry"], s)}
        for r in ALL_RULES:
            if row["level"] not in r.levels:
                continue
            stop = row["body_sl"] if r.sl == "body" else p["sl"]
            if stop is None:
                row[r.name] = {"outcome": "no stop"}
                continue
            res = play(p["entry"], stop, s, bars, t0, r)
            res["news"] = res.get("fill_ts") is not None and news_overlap(res["fill_ts"], res["fill_ts"] + 900)
            row[r.name] = res
        out.append(row)
    return out


def _safe(symbol, since, now):
    try:
        return symbol_alerts(symbol, since, now)
    except Exception as error:  # noqa: BLE001
        print(f"{symbol} failed: {error!r}")
        return None


def stats(rows):
    done = [x for x in rows if x.get("r") is not None]
    n = len(done)
    if not n:
        return None
    rs = [x["r"] for x in done]
    eq = peak = dd = 0.0
    for v in rs:
        eq += v
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    win, loss = sum(v for v in rs if v > 0), -sum(v for v in rs if v < 0)
    return {"n": n, "wins": sum(v > 0 for v in rs), "tot": sum(rs), "avg": sum(rs) / n,
            "pct": sum(x["r"] * x["risk_pct"] for x in done) / n, "pf": win / loss if loss else float("inf"),
            "dd": dd, "risk": sum(x["risk_pct"] for x in done) / n}


HEAD = ("| Setup | Alerts | Filled | Closed | Won | Total R | R/trade | %/trade | PF | Max DD | Avg SL | Open |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|")


def line(name, rows):
    st = stats(rows)
    filled = sum(1 for x in rows if x.get("fill_ts") is not None)
    opened = sum(1 for x in rows if x.get("outcome") == "open")
    if not st:
        return f"| {name} | {len(rows)} | {filled} | 0 | | | | | | | | {opened} |"
    return (f"| {name} | {len(rows)} | {filled} | {st['n']} | {st['wins'] / st['n'] * 100:.0f}% | {st['tot']:+.2f}R | "
            f"{st['avg']:+.3f}R | {st['pct']:+.2f}% | {st['pf']:.2f} | -{st['dd']:.2f}R | {st['risk']:.2f}% | {opened} |")


def run(since_text, tag):
    since = int(datetime.fromisoformat(since_text).replace(tzinfo=IST).timestamp())
    now = int(time.time())
    fbt.FIB_LEVELS = config.FIB_ALERT_LEVELS
    symbols = list(config.CRYPTO_WATCHLIST)
    got, failed = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for symbol, res in zip(symbols, pool.map(lambda x: _safe(x, since, now), symbols)):
            if res is None:
                failed.append(symbol)
                continue
            print(f"{symbol}: {len(res)} alerts")
            got += res
    got.sort(key=lambda x: x["alert_ts"])
    btc_sym = next(x for x in symbols if x.startswith("BTC"))
    btc15 = {c[0]: c[1:] for c in candles(btc_sym, now, since)[2]}
    for x in got:
        x["btc_pct"] = btc_move(btc15, x["alert_ts"])

    def rows(r, extra=lambda x: True):
        out = []
        for x in got:
            res = x.get(r.name)
            if res is None or res.get("outcome") == "no stop" or res.get("news") or not extra(x):
                continue
            if r.btc == "flat" and (x["btc_pct"] is None or abs(x["btc_pct"]) >= BTC_FLAT_PCT):
                continue
            out.append({**x, **res})
        return out

    news = {r.name: sum(1 for x in got if (x.get(r.name) or {}).get("news")) for r in ALL_RULES}
    nostop = sum(1 for x in got if x["level"] in ("L2", "L4") and x["body_sl"] is None)
    text = [f"# Journal v210 1D fib setup, replayed - {since_text} to {ist(now)[:10]}", "",
            f"{len(symbols)} crypto coins (CoinDCX list), Bitunix 15m walks after the alert's 15m candle. "
            f"Fills within 15 min of US CPI / PPI / FOMC left out ({news[V210.name]} for v210, {news[DEMO.name]} for the demo rules). "
            f"{nostop} L2/L4 alerts had no body 1% past entry in 300 days (left out of the body-SL rows)."
            + (f" FAILED: {', '.join(failed)}." if failed else ""), "", HEAD]
    text += [line(r.name, rows(r)) for r in ALL_RULES]
    text += ["", "## v210 by level / side / BTC", "", HEAD]
    text += [line(f"v210 {lv}", rows(V210, lambda x, lv=lv: x["level"] == lv)) for lv in ("L2", "L4")]
    text += [line(f"v210 {sd}", rows(V210, lambda x, sd=sd: x["side"] == sd)) for sd in ("long", "short")]
    up = lambda x: x["btc_pct"] is not None and x["btc_pct"] >= BTC_FLAT_PCT
    dn = lambda x: x["btc_pct"] is not None and x["btc_pct"] <= -BTC_FLAT_PCT
    text.append(line("v210 rules, BTC with the trade", rows(V210_ALL_DAYS, lambda x: up(x) if x["side"] == "long" else dn(x))))
    text.append(line("v210 rules, BTC against", rows(V210_ALL_DAYS, lambda x: dn(x) if x["side"] == "long" else up(x))))
    text += ["", "## v210 by month (alert month)", "", HEAD]
    v = rows(V210)
    for m in sorted({ist(x["alert_ts"])[:7] for x in v}):
        text.append(line(m, [x for x in v if ist(x["alert_ts"])[:7] == m]))
    text += ["", "## v210 by coin", "", HEAD] + [line(sym, [x for x in v if x["symbol"] == sym]) for sym in symbols]
    text += ["", "## v210 trades", "```"]
    for x in v:
        text.append(f"{ist(x['alert_ts'])} {x['symbol']:10} {x['level']} {x['side']:5} entry {x['entry']:.6g} body sl {x['body_sl']:.6g} "
                    f"({x['risk_pct']:.2f}%) btc {x['btc_pct']:+.2f}% fill {ist(x['fill_ts']) if x.get('fill_ts') else '-'} "
                    f"{x['outcome']}" + (f" {x['r']:+.3f}R" if x.get("r") is not None else ""))
    text.append("```")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"alerts_{tag}.json").write_text(json.dumps(got, indent=0))
    (OUT / f"SUMMARY_{tag}.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text[:text.index("## v210 trades")]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-09-01")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    run(a.since, a.tag or a.since)
