"""Research only - nothing here is imported by the live scanners.

Replays every filled zone trade from daily_backtest_finalized_records.jsonl on
5m candles under alternative exit rules, and tags each one with whether it
was taken with or against the higher-timeframe trend. Writes one row per
trade (research/out/trades.csv) so the results can be sliced afterwards.

Rules shared by every variant, matching the daily backtest:
- entry and stop exactly as recorded (planned entry, v7 stop)
- the stop counts on the fill candle, targets only from the next candle
- a 5m candle that touches both stop and target counts as the stop
- SL exits pay SL_FILL_SLIPPAGE_PCT; every trade pays round_trip_cost_r
- horizon: crypto/xStock/other 6h after entry (24h variants marked _24h),
  NSE same day up to 15:10
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import time as dtime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import daily_backtest_summary as dbs  # noqa: E402
import fib_trendline_data as ftd  # noqa: E402
import scanner as crypto_scanner  # noqa: E402

IST = dbs.IST
NSE_CUTOFF = dtime(15, 10)

# name: (target_R, break_even_at_R, trail=(activate_R, distance_R), partial=(fraction, at_R), bank_best, horizon_h)
VARIANTS = {
    # The daily report's own scoring: stop to breakeven at +0.5R, exit at +2R,
    # and a trade that touched +1R is credited +1R even if it then came back.
    "current": dict(target=2.0, be=0.5, bank_best=True),
    "t1": dict(target=1.0, be=0.5),
    "t1.5": dict(target=1.5, be=0.5),
    "t2": dict(target=2.0, be=0.5),
    "t3": dict(target=3.0, be=0.5),
    "t3_nobe": dict(target=3.0, be=None),
    "half1_t3": dict(target=3.0, be=0.5, partial=(0.5, 1.0)),
    "trail1": dict(target=None, be=0.5, trail=(1.0, 1.0)),
    "trail_half": dict(target=None, be=0.5, trail=(1.0, 0.5)),
    "t3_24h": dict(target=3.0, be=0.5, horizon_h=24),
    "trail1_24h": dict(target=None, be=0.5, trail=(1.0, 1.0), horizon_h=24),
}


def market_key(market: str) -> str:
    return {"NSE": "nse", "CRYPTO": "crypto", "XSTOCK": "xstock", "OTHER": "other"}[market]


def contract_for(symbol: str) -> str | None:
    contract = crypto_scanner.delta_contract(symbol)
    if contract:
        return contract
    if symbol.endswith("/USDT"):
        return symbol.split("/")[0] + "USD"
    return None


def frame_from_candles(candles) -> pd.DataFrame:
    frame = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close"])
    frame.index = pd.to_datetime(frame["ts"], unit="s", utc=True).dt.tz_convert(IST)
    return frame.drop(columns="ts").sort_index()


def load_trades(path: Path) -> pd.DataFrame:
    records = pd.read_json(path, lines=True)
    trades = records[(records["filled"] == True)].copy()  # noqa: E712
    trades = trades[trades["final_result"].isin(["SL", "BE", "+1R", "+2R", "Neither"])]
    trades = trades.dropna(subset=["entry_price", "stop_price", "entry_time"])
    trades["entry_ts"] = pd.to_datetime(trades["entry_time"], utc=True, format="ISO8601").dt.tz_convert(IST)
    trades["alert_ts"] = pd.to_datetime(trades["alert_time"], utc=True, format="ISO8601").dt.tz_convert(IST)
    return trades.reset_index(drop=True)


def fetch_crypto(trades: pd.DataFrame) -> tuple[dict, dict, dict]:
    fine, h4, d1 = {}, {}, {}
    start = int(trades["entry_ts"].min().timestamp()) - 3600
    end = int(trades["entry_ts"].max().timestamp()) + 26 * 3600
    htf_start = start - 200 * 86400
    for symbol in sorted(trades["symbol"].unique()):
        contract = contract_for(symbol)
        if contract is None:
            print(f"skip {symbol}: no Delta contract")
            continue
        try:
            fine[symbol] = frame_from_candles(ftd.delta_candles(contract, "5m", start, end))
            h4[symbol] = frame_from_candles(ftd.delta_candles(contract, "4h", htf_start, end))
            d1[symbol] = frame_from_candles(ftd.delta_candles(contract, "1d", htf_start, end))
            print(f"{symbol}: {len(fine[symbol])} 5m, {len(h4[symbol])} 4h, {len(d1[symbol])} 1d")
        except Exception as error:  # noqa: BLE001
            print(f"skip {symbol}: {error}")
        time.sleep(0.2)
    return fine, h4, d1


def fetch_nse(trades: pd.DataFrame) -> tuple[dict, dict, dict]:
    symbols = sorted(trades["symbol"].unique())
    raw5 = ftd.nse_download(symbols, "5m")
    raw4 = ftd.nse_download(symbols, "4h")
    raw1d = ftd.nse_download(symbols, "1d", period="2y")
    fine = {s: frame_from_candles(c) for s, c in raw5.items()}
    h4 = {s: frame_from_candles(c) for s, c in raw4.items()}
    d1 = {s: frame_from_candles(c) for s, c in raw1d.items()}
    print(f"NSE: {len(fine)} 5m, {len(h4)} 4h, {len(d1)} 1d of {len(symbols)}")
    return fine, h4, d1


def bar_close_times(frame: pd.DataFrame, seconds: int, nse: bool) -> pd.Series:
    closes = pd.Series(frame.index + pd.Timedelta(seconds=seconds), index=frame.index)
    if nse:
        session_end = frame.index.normalize() + pd.Timedelta(hours=15, minutes=30)
        closes = pd.Series(np.minimum(closes.values, session_end.values), index=frame.index)
    return closes


def trend_tags(htf: pd.DataFrame | None, seconds: int, nse: bool, at: pd.Timestamp, prefix: str) -> dict:
    out = {f"{prefix}_ema50": np.nan, f"{prefix}_ema20_50": np.nan, f"{prefix}_slope50": np.nan}
    if htf is None or len(htf) < 60:
        return out
    closes_at = bar_close_times(htf, seconds, nse)
    done = htf[pd.DatetimeIndex(closes_at).as_unit("ns").asi8 <= at.as_unit("ns").value]
    if len(done) < 55:
        return out
    ema20 = done["close"].ewm(span=20, adjust=False).mean()
    ema50 = done["close"].ewm(span=50, adjust=False).mean()
    out[f"{prefix}_ema50"] = 1.0 if done["close"].iloc[-1] > ema50.iloc[-1] else -1.0
    out[f"{prefix}_ema20_50"] = 1.0 if ema20.iloc[-1] > ema50.iloc[-1] else -1.0
    out[f"{prefix}_slope50"] = 1.0 if ema50.iloc[-1] > ema50.iloc[-6] else -1.0
    return out


def simulate(highs, lows, closes, ends, i0, side, entry, stop, horizon_end, cost_r, be_offset_pct,
             target=None, be=None, trail=None, partial=None, bank_best=False, **_):
    direction = 1.0 if side == "long" else -1.0
    risk = direction * (entry - stop)
    if risk <= 0:
        return np.nan, "bad_stop"
    be_stop = entry + direction * entry * be_offset_pct / 100.0
    be_reachable = be is not None and direction * (entry + direction * risk * be - be_stop) >= 0
    active = stop
    peak = 0.0
    booked = 0.0
    remaining = 1.0
    banked_1r = False
    last = i0
    for j in range(i0, len(highs)):
        if ends[j] > horizon_end:
            break
        last = j
        hi, lo = highs[j], lows[j]
        hit = lo <= active if direction > 0 else hi >= active
        if hit:
            if active == stop:
                exit_price = stop - direction * stop * dbs.SL_FILL_SLIPPAGE_PCT / 100.0
            else:
                exit_price = active
            r = direction * (exit_price - entry) / risk
            if bank_best and banked_1r:
                r = 1.0
            return booked + remaining * r - cost_r, "stop" if active == stop else "protected"
        if j == i0:
            continue
        fav = (hi - entry) / risk if direction > 0 else (entry - lo) / risk
        peak = max(peak, fav)
        if partial and remaining == 1.0 and peak >= partial[1]:
            booked += partial[0] * partial[1]
            remaining -= partial[0]
            if direction * (be_stop - active) > 0:
                active = be_stop
        if bank_best and peak >= 1.0:
            banked_1r = True
        if target is not None and peak >= target:
            return booked + remaining * target - cost_r, "target"
        if be is not None and be_reachable and peak >= be and direction * (be_stop - active) > 0:
            active = be_stop
        if trail and peak >= trail[0]:
            level = entry + direction * (peak - trail[1]) * risk
            if direction * (level - active) > 0:
                active = level
    r = direction * (closes[last] - entry) / risk
    if bank_best and banked_1r:
        r = 1.0
    return booked + remaining * r - cost_r, "time"


def run(records: Path, out_dir: Path) -> pd.DataFrame:
    trades = load_trades(records)
    print(f"{len(trades)} filled trades")
    is_nse = trades["market"] == "NSE"
    c_fine, c_h4, c_d1 = fetch_crypto(trades[~is_nse])
    n_fine, n_h4, n_d1 = fetch_nse(trades[is_nse])

    rows = []
    for trade in trades.to_dict("records"):
        nse = trade["market"] == "NSE"
        fine = (n_fine if nse else c_fine).get(trade["symbol"])
        h4 = (n_h4 if nse else c_h4).get(trade["symbol"])
        d1 = (n_d1 if nse else c_d1).get(trade["symbol"])
        row = {k: trade.get(k) for k in (
            "trade_id", "date", "market", "timeframe", "symbol", "side", "rating", "touch_count",
            "zone_age_candles", "final_result", "realized_r", "net_realized_r", "entry_price", "stop_price",
        )}
        row["alert_hour_ist"] = trade["alert_ts"].hour
        row["stop_pct"] = abs(trade["entry_price"] - trade["stop_price"]) / trade["entry_price"] * 100
        htf, htf_seconds = (h4, 14400) if trade["timeframe"] == "30m" else (d1, 86400)
        row.update(trend_tags(htf, htf_seconds, nse, trade["alert_ts"], "htf"))
        row.update(trend_tags(d1, 86400, nse, trade["alert_ts"], "d1"))
        if fine is None or fine.empty:
            row["sim_status"] = "no_data"
            rows.append(row)
            continue
        i0 = int(fine.index.searchsorted(trade["entry_ts"].floor("5min")))
        if i0 >= len(fine) or abs((fine.index[i0] - trade["entry_ts"]).total_seconds()) > 600:
            row["sim_status"] = "entry_bar_missing"
            rows.append(row)
            continue
        row["sim_status"] = "ok"
        highs = fine["high"].to_numpy()
        lows = fine["low"].to_numpy()
        closes = fine["close"].to_numpy()
        ends = (fine.index + pd.Timedelta(minutes=5)).as_unit("ns").asi8
        entry, stop = float(trade["entry_price"]), float(trade["stop_price"])
        risk = abs(entry - stop)
        mkey = market_key(trade["market"])
        cost_r = dbs.round_trip_cost_r(entry, risk, mkey)
        be_offset = dbs.BREAK_EVEN_OFFSET_PCT if mkey == "nse" else dbs.CRYPTO_BREAK_EVEN_OFFSET_PCT
        row["cost_r"] = cost_r
        entry_bar = fine.index[i0]
        for name, params in VARIANTS.items():
            if nse:
                horizon = pd.Timestamp.combine(entry_bar.date(), NSE_CUTOFF).tz_localize(IST)
            else:
                horizon = entry_bar + pd.Timedelta(hours=params.get("horizon_h", 6))
            r, how = simulate(highs, lows, closes, ends, i0, trade["side"], entry, stop,
                              pd.Timestamp(horizon).as_unit("ns").value, cost_r, be_offset, **params)
            row[f"r_{name}"] = r
            row[f"exit_{name}"] = how
        rows.append(row)

    table = pd.DataFrame(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "trades.csv", index=False)
    return table


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", default="daily_backtest_finalized_records.jsonl")
    parser.add_argument("--out", default="research/out")
    args = parser.parse_args(argv)
    table = run(Path(args.records), Path(args.out))
    ok = table[table["sim_status"] == "ok"]
    print(table["sim_status"].value_counts().to_string())
    cols = [c for c in table.columns if c.startswith("r_")]
    print(ok.groupby("market")[["net_realized_r"] + cols].sum().round(1).T.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
