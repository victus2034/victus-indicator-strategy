"""Research only - nothing here is imported by the live scanners.

Lakky (2026-10-10): the daily EMA50 trend filter is live for crypto zone alerts
only (CRYPTO_TREND_FILTER). What if it applied to everything - NSE, xStock and
gold/silver zones, and every fib and trendline alert?

Rule tested, the live one (scanner._trend_from_daily): a buy only while the last
closed daily candle is above its EMA50, a sell only below; no trend known = no block.

  zones        - the live, scored trades (daily_backtest_finalized_records.jsonl),
                 tagged with the trend at their alert time. Crypto only up to
                 2026-10-04 07:07 UTC, when the filter went live and stopped
                 recording counter-trend crypto trades.
  fib / trend  - history replay with today's live rules (fib_trendline_backtest),
                 crypto on Delta candles, NSE on Yahoo.

    python research/trend_filter_all_backtest.py --state FINALIZED.jsonl --since 2026-09-01
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import scanner  # noqa: E402
from daily_backtest_summary import market_class  # noqa: E402
from fib_sr_logic_backtest import trend_at  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE, delta_candles, nse_download  # noqa: E402
from fib_zone_preference import row  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "trend_filter_all"
CRYPTO_FILTER_LIVE = pd.Timestamp("2026-10-04 07:07", tz="UTC").timestamp()


def against(trend, side):
    return trend is not None and (trend < 0 if side == "long" else trend > 0)


def summary(label, net):
    wins = sum(1 for n in net if n > 0.05)
    return {"group": label, "trades": len(net), "wins_%": round(100 * wins / len(net)) if net else None,
            "net_R": round(sum(net), 1), "R_per_trade": round(sum(net) / len(net), 3) if net else None}


def zone_rows(path, since, now):
    trades = []
    for line in open(path):
        if not line.strip():
            continue
        r = json.loads(line)
        if not r.get("filled") or r.get("net_realized_r") is None:
            continue
        ts = pd.Timestamp(r["alert_time"]).timestamp()
        if ts < since:
            continue
        cls = market_class(r["symbol"])
        if cls == "CRYPTO" and ts >= CRYPTO_FILTER_LIVE:
            continue
        trades.append({**r, "cls": cls, "ts": ts})
    daily = {}
    nse = sorted({t["symbol"] for t in trades if t["cls"] == "NSE"})
    if nse:
        daily.update(nse_download(nse, "1d"))
    for symbol in sorted({t["symbol"] for t in trades if t["cls"] != "NSE"}):
        contract = scanner.delta_contract(symbol)
        if contract:
            try:
                daily[symbol] = delta_candles(contract, "1d", now - 400 * 86400, now)
            except Exception as error:  # noqa: BLE001
                print(f"{symbol} daily failed: {error}")
    rows = []
    for cls in ("CRYPTO", "NSE", "XSTOCK", "OTHER"):
        for tf in ("all", "30m", "4h"):
            items = [t for t in trades if t["cls"] == cls and (tf == "all" or t["timeframe"] == tf)]
            if not items:
                continue
            for t in items:
                t["against"] = against(trend_at(daily.get(t["symbol"]), t["ts"]), t["side"])
            for label, keep in (("no filter", lambda t: True), ("with filter", lambda t: not t["against"]),
                                ("blocked by filter", lambda t: t["against"])):
                net = [float(t["net_realized_r"]) for t in items if keep(t)]
                if net:
                    rows.append({"alert": "zone", "market": cls, "tf": tf, **summary(label, net)})
    return rows


def fib_tl_rows(since, now):
    fbt.TIMEFRAMES = list(config.FIB_TL_TIMEFRAMES)
    got = []

    def one(symbol):
        try:
            data = fbt.crypto_data(symbol, now)
            if not data:
                return []
            out = fbt.replay_symbol(CRYPTO, symbol, *data, now)
            for t in out:
                t["cls"] = market_class(symbol)
                t["against"] = against(trend_at(data[0].get("1d"), t["alert_ts"]), t["plan"]["side"])
            return out
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            return []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(one, scanner.active_watchlist()):
            got += result
    import nse_scanner
    for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
        for t in fbt.replay_symbol(NSE, symbol, base, evals, now):
            t["cls"] = "NSE"
            t["against"] = against(trend_at(base.get("1d"), t["alert_ts"]), t["plan"]["side"])
            got.append(t)
    got = [t for t in got if t["kind"] in ("fib", "trendline") and t["alert_ts"] >= since]
    rows = []
    groups = defaultdict(list)
    for t in got:
        for tf in ("all", t["tf"]):
            groups[(t["kind"], t["cls"], tf)].append(t)
    for (kind, cls, tf), items in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1],
                                         -1 if kv[0][2] == "all" else fbt.TIMEFRAMES.index(kv[0][2]))):
        for label, keep in (("no filter", lambda t: True), ("with filter", lambda t: not t["against"]),
                            ("blocked by filter", lambda t: t["against"])):
            sub = [t for t in items if keep(t)]
            if sub:
                r = row(label, sub)
                rows.append({"alert": kind, "market": cls, "tf": tf, "group": label, "trades": r["filled"],
                             "wins_%": r["win_1r_%"], "net_R": r["net_R"], "R_per_trade": r["R_per_trade"]})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, help="daily_backtest_finalized_records.jsonl")
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = time.time()
    rows = zone_rows(args.state, since, now) + fib_tl_rows(since, now)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "summary.csv", index=False)
    text = [f"# Daily EMA{config.CRYPTO_TREND_EMA} trend filter on every alert: {args.since} to now", "",
            "Filter: buy only while the last closed daily candle is above its EMA, sell only below. "
            "Net R after fees. Zones = live scored trades (crypto only before the filter went live, "
            "2026-10-04); fib/trendline = history replay with today's live rules (crypto on Delta candles).", "",
            df.to_markdown(index=False), ""]
    (OUT / "TREND_FILTER_ALL.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
