"""Print what the alert bot holds on one crypto chart right now - zones, fib,
trendlines - in chart terms, so it can be read against a TradingView screenshot
of the indicator on the same feed and timeframe.

Research only. Lakky, 2026-10-07: "make sure new script matches the VIS"
(Pine v12.5 vs the bot), checked on his LTCUSDT.P 4h Bitunix chart.

    VICTUS_TIMEFRAME=4h python research/chart_vs_bot.py LTCUSD
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

import config  # noqa: E402
import fib_engine  # noqa: E402
import scanner  # noqa: E402
import bitunix_data  # noqa: E402
from fib_trendline_data import CRYPTO, candle_is_closed, crypto_charts  # noqa: E402
from fib_trendline_scanner import FIB_SWING_LENGTH, fib_zones  # noqa: E402
from trendlines import SUPPORT, build_trendlines  # noqa: E402


def ts(t):
    t = t / 1000 if t > 1e11 else t
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def main():
    symbol = sys.argv[1]
    tf = config.TIMEFRAME
    now = int(time.time())
    print(f"== {symbol} {tf} ==")

    # zones: exactly the scan path
    ohlcv, venue = scanner.fetch_symbol_ohlcv(symbol)
    df = pd.DataFrame(ohlcv, columns=["time", "open", "high", "low", "close", "volume"])
    supply, demand = scanner.build_zones(df)
    last = len(df) - 1
    print(f"zones from {venue}: {len(df)} candles {ts(df['time'].iloc[0])} -> {ts(df['time'].iloc[-1])}, "
          f"last close {df['close'].iloc[-1]}")
    for row in df.tail(3).itertuples():
        print(f"  candle {ts(row.time)} o {row.open} h {row.high} l {row.low} c {row.close} v {row.volume}")
    for name, zones in (("SUPPLY", supply), ("DEMAND", demand)):
        live = [z for z in zones if z["active"]]
        for z in sorted(live, key=lambda z: -z["top"]):
            young = " (too young to alert)" if scanner.too_young_to_alert(z, last) else ""
            print(f"  {name} {z['bottom']:.4f} - {z['top']:.4f}  from {ts(df['time'].iloc[z['created_idx']])}{young}")

    # fib + trendlines: exactly the fib/trendline scan path
    contract = scanner.delta_contract(symbol)
    source = "bitunix" if bitunix_data.uses_bitunix(symbol) else "delta"
    candles = crypto_charts(contract, [tf], now, source=source)[tf]
    closed = candles if candle_is_closed(CRYPTO, candles[-1][0], tf, now) else candles[:-1]
    highs = [c[2] for c in closed]; lows = [c[3] for c in closed]; closes = [c[4] for c in closed]
    stamp = [ts(c[0]) for c in closed]
    print(f"fib/trendlines from {source}: {len(closed)} closed candles {stamp[0]} -> {stamp[-1]}")
    live = fib_engine.run(stamp, highs, lows, N=FIB_SWING_LENGTH)[0][-1]
    d, base, top = live["d"], live["O"], live["E"]
    print(f"  FIB {'UP' if d == 1 else 'DOWN'} base {base} ({stamp[live['Ot']]}) top {top} ({stamp[live['Et']]})")
    for z in fib_zones(d, base, top):
        print(f"    {z}")
    for ln in build_trendlines(highs, lows, closes, config.TRENDLINE_SWING_LENGTH, config.TRENDLINES_KEEP):
        state = "live" if ln.alive else f"broken {stamp[ln.broken_at]}"
        print(f"  {'SUP' if ln.kind == SUPPORT else 'RES'} {ln.y1} ({stamp[ln.x1]}) -> {ln.y2} ({stamp[ln.x2]}) "
              f"{state}, now at {ln.price_at(len(closed)):.4f}")


if __name__ == "__main__":
    main()
