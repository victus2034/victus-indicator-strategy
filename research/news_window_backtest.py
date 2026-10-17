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

# Official calendars: BLS (bls.gov/schedule/2026/09_sched_list.htm, 10_sched_list.htm)
# and the Fed (federalreserve.gov, Sep 15-16 2026 meeting). UTC; US daylight time
# (EDT = UTC-4) until Nov 1 2026. CPI/PPI 8:30 ET, FOMC statement 2:00 PM ET.
EVENTS = [
    ("PPI", "2026-09-10 12:30"),
    ("CPI", "2026-09-11 12:30"),
    ("FOMC", "2026-09-16 18:00"),
    ("CPI", "2026-10-14 12:30"),
    ("PPI", "2026-10-15 12:30"),
]
EVENT_TS = [(name, int(pd.Timestamp(at, tz="UTC").timestamp())) for name, at in EVENTS]


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


def collect(since, now, limit):
    scanner.ZONE_BASE_EXTRA = 1
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    symbols = list(config.CRYPTO_WATCHLIST)[: limit or None]

    def one(symbol):
        out = []
        fine = []
        for name, ev in EVENT_TS:      # 5m around each release, wide enough for a daily fill candle
            try:
                fine += fbt._cached(f"nw_{symbol}_5m_{ev}",
                                    lambda ev=ev: bitunix_candles(symbol, "5m", ev - 86400 - 3600, ev + 86400 + 3600))
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
        print(f"{symbol}: {len(out)} alerts, {sum(1 for t in out if t['news'])} filled in a news window")
        return out

    got = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(one, symbols):
            got += res
    return got


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
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    parser.add_argument("--limit", type=int, default=0, help="first N coins (smoke test)")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    since = int(pd.Timestamp(args.since, tz=IST).timestamp())
    now = int(time.time())
    got = collect(since, now, args.limit)
    df = table(got)
    df.to_csv(OUT / "summary.csv", index=False)
    skipped = [t for t in got if t["news"]]
    detail = pd.DataFrame([{
        "event": t["news"][0], "symbol": t["symbol"], "kind": t["kind"], "tf": t["tf"], "side": t["plan"]["side"],
        "alert_utc": pd.Timestamp(t["alert_ts"], unit="s", tz="UTC").strftime("%m-%d %H:%M"),
        "fill_utc": pd.Timestamp(t["fill_5m"], unit="s", tz="UTC").strftime("%m-%d %H:%M"),
        "fill_on_5m": t["fill_exact"], "entry": t["plan"]["entry"], "outcome": t["result"]["outcome"],
        "net_r": trades.booked_r(t["plan"], t["market"], t["result"])[1],
        "risk_%": round(trades.risk_pct(t["plan"]), 3)} for t in skipped])
    detail.to_csv(OUT / "skipped.csv", index=False)
    events = pd.DataFrame([{"event": n, "utc": pd.Timestamp(e, unit="s", tz="UTC").strftime("%Y-%m-%d %H:%M"),
                            "ist": pd.Timestamp(e, unit="s", tz=IST).strftime("%Y-%m-%d %H:%M"),
                            "trades filled in window": sum(1 for t in skipped if t["news"][1] == e)}
                           for n, e in EVENT_TS])
    text = [f"# No trades +-{WINDOW_MIN} min around US CPI / PPI / FOMC, crypto ({args.since} to now)", "",
            "A trade is skipped when its entry fills within the window (fill time on Bitunix 5m). "
            "Trades open at the release are kept. Scored the live way, net after fees. "
            "Zones on Bitunix (scored like fibs), fib/TL on Delta.", "",
            events.to_markdown(index=False), "", df.to_markdown(index=False), "",
            "## Skipped trades", "", detail.to_markdown(index=False) if len(detail) else "none", ""]
    (OUT / "NEWS_WINDOW.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
