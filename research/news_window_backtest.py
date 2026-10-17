"""Research only: no trades around US CPI, PPI and FOMC (lakky, 2026-10-17).

lakky: "remove a trading period of news where cpi, ppi and fomc news 15m before and
after of news do not trade". Every crypto alert the live rules would have sent
(S/R zones, fibs, trendlines; risk_warning_backtest's replay), Sep 1 to now, is
scored the live way. A trade is "in the news window" when its entry filled from
WINDOW_MIN minutes before a release to WINDOW_MIN minutes after it. Skipping those
trades is the rule tested; trades already open at the release are left alone.

Fill time: trades are scored on 1h (4H alerts) / 4h (1D) / 1d (1W, 1M) candles, too
coarse for a 30-minute window, so the fill candle is re-read on Bitunix 5m candles
and the first 5m candle that traded to the entry is the fill time. If no 5m candle
touched it (venue difference), the trade counts as in the window when its fill
candle overlaps the window at all.

NSE is not tested: the releases are 18:00 IST (CPI/PPI) and 23:30 IST (FOMC) in
US daylight time, after NSE closes at 15:30, so no NSE trade can fill inside one.

    PYTHONPATH=research python research/news_window_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
import zone_htf_backtest as zh  # noqa: E402
from fib_touched_before_backtest import row  # noqa: E402
from fib_trendline_data import CRYPTO, IST, TF_SECONDS, bitunix_candles  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "news_window"
WINDOW_MIN = 15
GROUPS = (("4H", ("4h",)), ("1D+", ("1d", "1w", "1M")))

# Official calendars, New York time: BLS schedules (bls.gov/schedule/2025/home.htm,
# 2026/home.htm; Oct 2025 CPI was never published, Sep 2025 PPI moved to Nov 25 by the
# shutdown) and the Fed's FOMC meeting dates. CPI/PPI 8:30 AM ET, FOMC statement 2:00 PM ET.
CPI_DATES = ["2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13", "2025-06-11",
             "2025-07-15", "2025-08-12", "2025-09-11", "2025-10-24", "2025-12-18",
             "2026-01-13", "2026-02-13", "2026-03-11", "2026-04-10", "2026-05-12", "2026-06-10",
             "2026-07-14", "2026-08-12", "2026-09-11", "2026-10-14", "2026-11-10", "2026-12-10"]
PPI_DATES = ["2025-01-14", "2025-02-13", "2025-03-13", "2025-04-11", "2025-05-15", "2025-06-12",
             "2025-07-16", "2025-08-14", "2025-09-10", "2025-11-25",
             "2026-01-14", "2026-01-30", "2026-02-27", "2026-03-18", "2026-04-14", "2026-05-13",
             "2026-06-11", "2026-07-15", "2026-08-13", "2026-09-10", "2026-10-15",
             "2026-11-13", "2026-12-15"]
FOMC_DATES = ["2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17",
              "2025-10-29", "2025-12-10",
              "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]
EVENTS = sorted([("CPI", f"{d} 08:30") for d in CPI_DATES] + [("PPI", f"{d} 08:30") for d in PPI_DATES]
                + [("FOMC", f"{d} 14:00") for d in FOMC_DATES], key=lambda e: e[1])
EVENT_TS = [(name, int(pd.Timestamp(at, tz="America/New_York").timestamp())) for name, at in EVENTS]


def window_of(ts):
    for name, ev in EVENT_TS:
        if ev - WINDOW_MIN * 60 <= ts <= ev + WINDOW_MIN * 60:
            return name, ev
    return None


def eval_seconds(tf):
    return TF_SECONDS[trades.EVAL_RESOLUTION[CRYPTO][tf]]


def fine_fill(t, fine):
    """(fill time on 5m, exact?) for a filled trade."""
    start = t["result"]["fill_ts"]
    end = start + eval_seconds(t["tf"])
    long = t["plan"]["side"] == "long"
    entry = t["plan"]["entry"]
    for ts, _o, h, l, _c in fine:
        if start <= ts < end and ts > t["alert_ts"] - 300 and ((l <= entry) if long else (h >= entry)):
            return ts, True
    return start, False


def in_window(t, fine):
    if not t["result"]["filled"]:
        return None
    ts, exact = fine_fill(t, fine)
    t["fill_5m"], t["fill_exact"] = ts, exact
    if exact:
        return window_of(ts) or window_of(ts + 299)
    start, end = t["result"]["fill_ts"], t["result"]["fill_ts"] + eval_seconds(t["tf"])
    for name, ev in EVENT_TS:
        if start <= ev + WINDOW_MIN * 60 and end > ev - WINDOW_MIN * 60:
            return name, ev
    return None


def exit_levels(plan, result, market):
    """Prices that would have closed the trade: its stop (the breakeven stop too once
    +0.5R traded) and its final target (1R plan: 1R, else 2R)."""
    entry, sl = plan["entry"], plan["sl"]
    risk = abs(entry - sl)
    sign = 1 if plan["side"] == "long" else -1
    stops = [sl] + ([trades.break_even_stop(plan, market)] if result.get("half") else [])
    target = entry + sign * risk * (1 if plan.get("target_r") == 1 else 2)
    return stops, target


def close_before_news(t, fine):
    """lakky (2026-10-17): close any open trade 15 min before a release. Returns
    (event, net R at the 5m open WINDOW_MIN before it) for the first release the trade
    was still open at, or None. Net R pays the same round-trip cost as any trade."""
    r = t["result"]
    if not r["filled"]:
        return None
    filled_at = t.get("fill_5m", r["fill_ts"])
    plan, long = t["plan"], t["plan"]["side"] == "long"
    by_ts = {c[0]: c for c in fine}
    for name, ev in EVENT_TS:
        at = ev - WINDOW_MIN * 60
        if filled_at >= at:
            continue
        end = r["end_ts"]
        if end is not None and end + eval_seconds(t["tf"]) <= at:
            continue                      # closed in an earlier candle
        if end is not None and end <= at:
            # the closing candle holds the cut-off: did an exit trade before it, on 5m?
            stops, target = exit_levels(plan, r, t["market"])
            hit = any(((l <= max(stops)) or (h >= target)) if long else ((h >= min(stops)) or (l <= target))
                      for ts, _o, h, l, _c in fine if end <= ts < at)
            if hit:
                continue
        bar = by_ts.get(at)
        if bar is None:
            continue
        risk = abs(plan["entry"] - plan["sl"])
        gross = (bar[1] - plan["entry"]) / risk * (1 if long else -1)
        return name, ev, gross - trades.COST_PCT[t["market"]] / trades.risk_pct(plan)
    return None


def collect(since, now, limit):
    scanner.ZONE_BASE_EXTRA = 1
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    symbols = list(config.CRYPTO_WATCHLIST)[: limit or None]

    def one(symbol):
        out = []
        fine = []
        for name, ev in EVENT_TS:      # 5m for the release's UTC day: every fill candle (1h/4h/1d) holding it
            if ev < since - 86400 or ev > now:
                continue
            day = ev - ev % 86400
            try:
                fine += fbt._cached(f"nw_{symbol}_5m_{day}",
                                    lambda day=day: bitunix_candles(symbol, "5m", day, min(day + 86400 - 1, now)))
            except Exception as error:  # noqa: BLE001
                print(f"{symbol} 5m {name} failed: {error}")
        fine.sort()
        try:
            data = zh.crypto_load(symbol, now, since)
            if data:
                base, evals, daily = data
                for tf in zh.TIMEFRAMES:
                    out += zh.replay(CRYPTO, symbol, tf, base[tf], evals[trades.EVAL_RESOLUTION[CRYPTO][tf]],
                                     daily, since, now)
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} zones failed: {error}")
        try:
            data = fbt.crypto_data(symbol, now)
            if data:
                out += [t for t in fbt.replay_symbol(CRYPTO, symbol, *data, now)
                        if t["kind"] in ("fib", "trendline")]
        except Exception as error:  # noqa: BLE001
            print(f"{symbol} fib/TL failed: {error}")
        out = [t for t in out if t["alert_ts"] >= since]
        for t in out:
            t["news"] = in_window(t, fine)
            t["closed"] = None if t["news"] else close_before_news(t, fine)
        print(f"{symbol}: {len(out)} alerts, {sum(1 for t in out if t['news'])} filled in a news window")
        return out

    got = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(one, symbols):
            got += res
    return got


def booked(t, close=False):
    """(net R, net %) or None, with the close-before-news rule when close=True."""
    if close and t.get("closed"):
        net = t["closed"][2]
    else:
        if not t["result"]["filled"]:
            return None
        net = trades.booked_r(t["plan"], t["market"], t["result"])[1]
        if net is None:
            return None
    return net, net * trades.risk_pct(t["plan"])


def row2(label, items, close=False):
    got = [b for b in (booked(t, close) for t in items) if b is not None]
    n = len(got)
    return {"rule": label, "trades": n,
            "R_total": round(sum(r for r, _ in got), 1),
            "R_per_trade": round(sum(r for r, _ in got) / n, 3) if n else None,
            "%_total": round(sum(p for _, p in got), 1),
            "%_per_trade": round(sum(p for _, p in got) / n, 3) if n else None}


RULES = (("now", lambda t: True, False),
         ("skip new trades in window", lambda t: not t["news"], False),
         ("close open trades 15m before", lambda t: True, True),
         ("both", lambda t: not t["news"], True))


def table2(got):
    rows = []
    for kind, name in (("zone", "S/R zone"), ("fib", "fib"), ("trendline", "TL")):
        for group, tfs in GROUPS:
            items = [t for t in got if t["kind"] == kind and t["tf"] in tfs]
            for label, keep, close in RULES:
                rows.append({"alert": name, "tf": group, **row2(label, [t for t in items if keep(t)], close)})
    for label, keep, close in RULES:
        rows.append({"alert": "ALL", "tf": "all", **row2(label, [t for t in got if keep(t)], close)})
    closed = [t for t in got if t.get("closed")]
    rows.append({"alert": "ALL", "tf": "all", **row2("closed trades, as they ended", closed)})
    rows.append({"alert": "ALL", "tf": "all", **row2("closed trades, closed 15m before", closed, True)})
    return pd.DataFrame([r for r in rows if r["trades"]])


def table(got):
    rows = []
    for kind, name in (("zone", "S/R zone"), ("fib", "fib"), ("trendline", "TL")):
        for group, tfs in GROUPS:
            items = [t for t in got if t["kind"] == kind and t["tf"] in tfs]
            for label, keep in (("all trades (today)", lambda t: True),
                                ("skip news window", lambda t: not t["news"]),
                                ("only the skipped", lambda t: bool(t["news"]))):
                pick = [t for t in items if keep(t)]
                if pick:
                    rows.append({"alert": name, "tf": group, **row(label, pick)})
    items = list(got)
    for label, keep in (("all trades (today)", lambda t: True),
                        ("skip news window", lambda t: not t["news"]),
                        ("only the skipped", lambda t: bool(t["news"]))):
        rows.append({"alert": "ALL", "tf": "all", **row(label, [t for t in items if keep(t)])})
    for kind in ("CPI", "PPI", "FOMC"):
        pick = [t for t in items if t["news"] and t["news"][0] == kind]
        if pick:
            rows.append({"alert": "ALL", "tf": "all", **row(f"skipped at {kind}", pick)})
    for year in (2025, 2026):
        pick = [t for t in items if t["news"] and pd.Timestamp(t["news"][1], unit="s").year == year]
        if pick:
            rows.append({"alert": "ALL", "tf": "all", **row(f"skipped in {year}", pick)})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--limit", type=int, default=0, help="first N coins (smoke test)")
    parser.add_argument("--out", default="news_window")
    args = parser.parse_args()
    global OUT
    OUT = OUT.parent / args.out
    OUT.mkdir(parents=True, exist_ok=True)
    since = int(pd.Timestamp(args.since, tz=IST).timestamp())
    now = int(time.time())
    got = collect(since, now, args.limit)
    df = table(got)
    df.to_csv(OUT / "summary.csv", index=False)
    rules = table2(got)
    rules.to_csv(OUT / "rules.csv", index=False)
    skipped = [t for t in got if t["news"]]
    detail = pd.DataFrame([{
        "event": t["news"][0], "symbol": t["symbol"], "kind": t["kind"], "tf": t["tf"], "side": t["plan"]["side"],
        "alert_utc": pd.Timestamp(t["alert_ts"], unit="s", tz="UTC").strftime("%Y-%m-%d %H:%M"),
        "fill_utc": pd.Timestamp(t["fill_5m"], unit="s", tz="UTC").strftime("%Y-%m-%d %H:%M"),
        "fill_on_5m": t["fill_exact"], "entry": t["plan"]["entry"], "outcome": t["result"]["outcome"],
        "net_r": trades.booked_r(t["plan"], t["market"], t["result"])[1],
        "risk_%": round(trades.risk_pct(t["plan"]), 3)} for t in skipped])
    detail.to_csv(OUT / "skipped.csv", index=False)
    events = pd.DataFrame([{"event": n, "utc": pd.Timestamp(e, unit="s", tz="UTC").strftime("%Y-%m-%d %H:%M"),
                            "ist": pd.Timestamp(e, unit="s", tz=IST).strftime("%Y-%m-%d %H:%M"),
                            "trades filled in window": sum(1 for t in skipped if t["news"][1] == e)}
                           for n, e in EVENT_TS if since <= e <= now])
    text = [f"# No trades +-{WINDOW_MIN} min around US CPI / PPI / FOMC, crypto ({args.since} to now, {sum(1 for _, e in EVENT_TS if since <= e <= now)} releases)", "",
            "A trade is skipped when its entry fills within the window (fill time on Bitunix 5m). "
            "Trades open at the release are kept. Scored the live way, net after fees. "
            "Zones on Bitunix (scored like fibs), fib/TL on Delta.", "",
            events.to_markdown(index=False), "", "## Rules side by side", "",
            "close = any trade open at the release's -15m mark is closed at that 5m open (round-trip fee charged).", "",
            rules.to_markdown(index=False), "", "## Skip rule detail", "", df.to_markdown(index=False), "",
            "## Skipped trades", "", detail.to_markdown(index=False) if len(detail) else "none", ""]
    (OUT / "NEWS_WINDOW.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
