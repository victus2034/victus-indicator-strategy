"""Research only - nothing here is imported by the live scanners.

Replays the supply/demand zone alerts over history twice - with and without
the indicator's v10.0 "survive before create" gate (config
ZONE_SURVIVE_BEFORE_CREATE) - and grades both alert sets with the daily
backtest's own trade rules (daily_backtest_summary.run_backtest: entry and v7
stop as planned, +0.5R breakeven, 1R/2R, costs, 5m candles, same-zone
cooldown). Fib and trendline alerts are not touched by the gate and are not
replayed here.

Alert model, the same for both arms (only the zone set differs):
- zones are rebuilt candle by candle with scanner.build_zones; at each zone
  candle the hook sees what a scan during that candle would see
- a zone alerts when a 5m candle inside that zone candle trades in the band
  [entry, entry +/- MAX_DISTANCE_PCT] on the approach side, the zone is
  active, not too young (too_young_to_alert) and its stop is not too wide
- one alert per zone per ALERT_COOLDOWN_SECONDS; crypto only inside
  CRYPTO_ALERT_START..END (IST), NSE only in session (the 5m data is)
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import time as dtime
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
import daily_backtest_summary as dbs  # noqa: E402
import fib_trendline_data as ftd  # noqa: E402
import nse_scanner  # noqa: E402
import scanner  # noqa: E402

IST = dbs.IST
TF_MINUTES = {"30m": 30, "4h": 240}
TF_SECONDS = {"30m": 1800, "4h": 14400}


def frame_from_candles(candles) -> pd.DataFrame:
    frame = pd.DataFrame([c[:5] for c in candles], columns=["ts", "open", "high", "low", "close"])
    frame.index = pd.to_datetime(frame["ts"], unit="s", utc=True).dt.tz_convert(IST)
    frame = frame.drop(columns="ts").sort_index()
    return frame[~frame.index.duplicated(keep="last")]


def in_crypto_hours(ts: pd.Timestamp) -> bool:
    t = ts.tz_convert(IST).time()
    start, end = config.CRYPTO_ALERT_START, config.CRYPTO_ALERT_END
    return t >= start or t < end if start > end else start <= t < end


def replay_alerts(symbol, market, tf, zone_frame, fine, gate, start_ts):
    """Alerts this zone candle series would have sent, with the gate on or off."""
    df = zone_frame.reset_index(drop=True).assign(volume=1.0)
    opens = zone_frame.index
    fine_idx = fine.index
    band = config.MAX_DISTANCE_PCT / 100.0
    cooldown = pd.Timedelta(seconds=config.ALERT_COOLDOWN_SECONDS)
    last_alert: dict[str, pd.Timestamp] = {}
    alerts = []

    def on_candle(i, supply, demand):
        bar_open = opens[i]
        if bar_open < start_ts:
            return
        bar_end = bar_open + pd.Timedelta(seconds=TF_SECONDS[tf])
        lo = fine_idx.searchsorted(bar_open, side="left")
        hi = fine_idx.searchsorted(bar_end, side="left")
        if hi <= lo:
            return
        highs = fine["high"].to_numpy()[lo:hi]
        lows = fine["low"].to_numpy()[lo:hi]
        for zone_type, zones in (("supply", supply), ("demand", demand)):
            for zone in zones:
                if not zone["active"] or zone.get("over_touched", False):
                    continue
                if scanner.too_young_to_alert(zone, i) or scanner.stop_too_wide(zone_type, zone):
                    continue
                entry = scanner.planned_entry_price(zone_type, zone)
                if zone_type == "demand":
                    band_lo, band_hi = entry, entry * (1 + band)
                else:
                    band_lo, band_hi = entry * (1 - band), entry
                hits = np.nonzero((highs >= band_lo) & (lows <= band_hi))[0]
                key = scanner.build_state_key(symbol, zone_type, zone)
                for k in hits:
                    ts = fine_idx[lo + k]
                    if market == "crypto" and not in_crypto_hours(ts):
                        continue
                    if key in last_alert and ts - last_alert[key] < cooldown:
                        continue
                    last_alert[key] = ts
                    alerts.append({
                        "event_time_ist": ts,
                        "timeframe": tf,
                        "symbol": symbol,
                        "side": "long" if zone_type == "demand" else "short",
                        "zone_bottom": float(zone["bottom"]),
                        "zone_top": float(zone["top"]),
                        "planned_entry": entry,
                        "stop_price": scanner.planned_stop_price(zone_type, zone),
                        "zone_id": key,
                        "rebuilt": bool(zone.get("rebuilt", False)),
                        "gate": gate,
                    })
                    break
    with patch.object(scanner, "ZONE_SURVIVE_BEFORE_CREATE", gate), \
            patch.object(scanner, "ZONE_BASE_EXTRA", config.auto_base_extra(TF_MINUTES[tf])):
        scanner.build_zones(df, on_candle=on_candle)
    return alerts


def grade(alerts, fine_frames, market):
    if not alerts:
        return pd.DataFrame()
    frame = pd.DataFrame(alerts).sort_values(["event_time_ist", "symbol"]).reset_index(drop=True)
    results, _ = dbs.run_backtest(frame, fine_frames, market)
    return results


def summarize(results: pd.DataFrame) -> dict:
    if results.empty:
        return dict(alerts=0, filled=0, win_1r=np.nan, gross_r=0.0, net_r=0.0, net_per_trade=np.nan)
    filled = results[results["filled"] == True]  # noqa: E712
    filled = filled[filled["final_result"].isin(["SL", "BE", "+1R", "+2R", "Neither"])]
    net = pd.to_numeric(filled["net_realized_r"], errors="coerce")
    gross = pd.to_numeric(filled["realized_r"], errors="coerce")
    return dict(
        alerts=len(results),
        filled=len(filled),
        win_1r=round(float(filled["final_result"].isin(["+1R", "+2R"]).mean()) * 100, 1) if len(filled) else np.nan,
        gross_r=round(float(gross.sum()), 1),
        net_r=round(float(net.sum()), 1),
        net_per_trade=round(float(net.mean()), 3) if len(filled) else np.nan,
    )


def crypto_data(days, symbols):
    end = int(time.time())
    fine_start = end - days * 86400
    data = {}
    for symbol in symbols:
        contract = scanner.delta_contract(symbol)
        if contract is None:
            print(f"skip {symbol}: no Delta contract")
            continue
        try:
            fine = frame_from_candles(ftd.delta_candles(contract, "5m", fine_start, end))
            zones = {
                "30m": frame_from_candles(ftd.delta_candles(contract, "30m", fine_start - 40 * 86400, end)),
                "4h": frame_from_candles(ftd.delta_candles(contract, "4h", fine_start - 240 * 86400, end)),
            }
            data[symbol] = (fine, zones)
            print(f"{symbol}: {len(fine)} 5m, {len(zones['30m'])} 30m, {len(zones['4h'])} 4h", flush=True)
        except Exception as error:  # noqa: BLE001
            print(f"skip {symbol}: {error}")
        time.sleep(0.2)
    return data


def nse_data(symbols):
    fine = ftd.nse_download(symbols, "5m")
    z30 = ftd.nse_download(symbols, "30m")
    z4h = ftd.nse_download(symbols, "4h")
    data = {}
    for symbol in symbols:
        if symbol in fine and symbol in z30 and symbol in z4h:
            data[symbol] = (frame_from_candles(fine[symbol]), {
                "30m": frame_from_candles(z30[symbol]),
                "4h": frame_from_candles(z4h[symbol]),
            })
    print(f"NSE: {len(data)} of {len(symbols)} symbols with 5m/30m/4h", flush=True)
    return data


def run_market(market, data, out_dir):
    rows = []
    trades = []
    for tf in ("30m", "4h"):
        for gate in (False, True):
            alerts = []
            for symbol, (fine, zones) in data.items():
                if fine.empty or zones[tf].empty:
                    continue
                start_ts = fine.index[0]
                alerts += replay_alerts(symbol, market, tf, zones[tf], fine, gate, start_ts)
            fine_frames = {s: f for s, (f, _) in data.items()}
            results = grade(alerts, fine_frames, market)
            summary = summarize(results)
            summary.update(market=market, timeframe=tf, gate="on" if gate else "off")
            rows.append(summary)
            print(summary, flush=True)
            if not results.empty:
                trades.append(results.assign(market=market))
    if trades:
        keep = ["market", "timeframe", "gate", "symbol", "side", "event_time_ist", "zone_bottom", "zone_top",
                "planned_entry", "stop_price", "rebuilt", "filled", "final_result", "realized_r", "net_realized_r"]
        frame = pd.concat(trades, ignore_index=True)
        frame[[c for c in keep if c in frame.columns]].to_csv(out_dir / f"trades_{market}.csv", index=False)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=58, help="5m history to replay (Yahoo caps NSE 5m at 60)")
    parser.add_argument("--out", default="research/out_survival_gate")
    parser.add_argument("--markets", default="crypto,nse")
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    markets = args.markets.split(",")
    if "crypto" in markets:
        rows += run_market("crypto", crypto_data(args.days, list(config.CRYPTO_WATCHLIST)), out_dir)
    if "nse" in markets:
        symbols = list(nse_scanner.load_watchlist())
        rows += run_market("nse", nse_data(symbols), out_dir)

    table = pd.DataFrame(rows)[["market", "timeframe", "gate", "alerts", "filled", "win_1r",
                                "gross_r", "net_r", "net_per_trade"]]
    table.to_csv(out_dir / "summary.csv", index=False)
    with (out_dir / "RESULTS.md").open("w", encoding="utf-8") as handle:
        handle.write("# Survival gate backtest\n\n")
        handle.write(f"Replayed {args.days} days of 5m candles, generated {pd.Timestamp.now(tz=IST):%Y-%m-%d %H:%M} IST.\n\n")
        handle.write(table.to_markdown(index=False))
        handle.write("\n")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
