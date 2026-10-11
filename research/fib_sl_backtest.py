"""Research only - nothing here is imported by the live scanners.

Lakky, 2026-10-10 (LINKUSDT 1D, Bitunix): a trendline + fib trade. Entry on the
fib 0.66 line (the strong zone's FAR edge, "L2"), SL just below the closest
swing low near the trendline, target the fib high.

Live fib alerts (strong zone only, 0.75% band) replayed as
fib_trendline_backtest.replay does; only the entry, stop and exit change:
  entry   L1 = strong zone near edge (live) | L2 = far edge (0.66, Lakky's LINK entry)
  stop    sr      = FIB_SL_HEIGHT_PCT of the box past the far edge (live)
          nearest = beyond the closest swing low under entry (trendline_sl_backtest.stop rule)
  exit    2R+BE (live) | 1.5R | 1.5R+trail | fib high (everything off at the fib's top)
"confluence" = a live trendline of the same side runs through the box (+-0.75%) at alert time.

    python research/fib_sl_backtest.py --since 2026-09-01
"""
from __future__ import annotations

import argparse
import bisect
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import fib_engine  # noqa: E402
import fib_trendline_backtest as fbt  # noqa: E402
import fib_trendline_trades as trades  # noqa: E402
import scanner  # noqa: E402
from fib_trendline_data import CRYPTO, IST, NSE, TF_SECONDS, candle_is_closed  # noqa: E402
from fib_trendline_scanner import fib_zones  # noqa: E402
from trendline_sl_backtest import MIN_GAP_ATR, atr14, crypto_load, nearest_stop, simulate  # noqa: E402
from trendlines import SUPPORT, build_trendlines  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "fib_sl"
BAND = config.FIB_TL_MAX_DISTANCE_PCT / 100
PLANS = [("L1", "sr"), ("L1", "nearest"), ("L2", "sr"), ("L2", "nearest")]
EXITS = ("2R+BE", "1.5R", "1.5R+trail", "target")


def replay(market, symbol, tf, base, evalc, now, since):
    if base and not candle_is_closed(market, base[-1][0], tf, now):
        base = base[:-1]
    n = len(base)
    if n <= fbt.MIN_BARS or not evalc:
        return []
    times = [c[0] for c in base]
    highs = [c[2] for c in base]
    lows = [c[3] for c in base]
    closes = [c[4] for c in base]
    eval_ts = [c[0] for c in evalc]
    eval_seconds = TF_SECONDS[trades.EVAL_RESOLUTION[market][tf]]
    held = (lambda ts: fbt.crypto_held(ts, eval_seconds)) if market == CRYPTO else (lambda ts: False)
    atr = atr14(highs, lows, closes)
    lines = build_trendlines(highs, lows, closes, config.TRENDLINE_SWING_LENGTH, config.TRENDLINES_KEEP, history=True)

    def bar_slice(i):
        end = times[i + 1] if i + 1 < n else times[i] + TF_SECONDS[tf]
        return bisect.bisect_left(eval_ts, times[i]), bisect.bisect_left(eval_ts, end)

    first = next((i for i in range(fbt.MIN_BARS, n) if times[i] >= eval_ts[0]), n)
    snaps, _ = fib_engine.run([str(t) for t in times], highs, lows, N=config.FIB_SWING_LENGTH)
    fired, out = set(), []
    for i in range(first, n):
        s = snaps[i - 1]
        d, base_px, top = s["d"], s["O"], s["E"]
        if base_px == top:
            continue
        e0, e1 = bar_slice(i)
        for zone in fib_zones(d, base_px, top):
            if zone["zone"] not in config.FIB_ALERT_ZONES:
                continue
            key = (d, times[s["Ot"]], top, zone["zone"])
            if key in fired:
                continue
            lo_band = zone["low"] if d == 1 else zone["low"] * (1 - BAND)
            hi_band = zone["high"] * (1 + BAND) if d == 1 else zone["high"]
            for k in range(e0, e1):
                ts, _o, h, l, c = evalc[k]
                if (l <= base_px) if d == 1 else (h >= base_px):
                    break
                if held(ts) or l > hi_band or h < lo_band:
                    continue
                if trades.already_stopped(trades.fib_plan(d, zone), c):
                    continue
                fired.add(key)
                if ts < since:
                    break
                long = d == 1
                want = SUPPORT if long else 1 - SUPPORT
                conf = any(ln.kind == want and ln.live_during(i)
                           and zone["low"] * (1 - BAND) <= ln.price_at(i) <= zone["high"] * (1 + BAND) for ln in lines)
                entries = {"L1": zone["entry"], "L2": zone["low"] if long else zone["high"]}
                t = {"market": market, "symbol": symbol, "tf": tf, "alert_ts": ts, "long": long,
                     "confluence": conf, "top": top}
                for lv, st in PLANS:
                    entry = entries[lv]
                    sl = zone["sl"] if st == "sr" else nearest_stop(long, entry, i, highs, lows, MIN_GAP_ATR * (atr[i - 1] or 0))
                    if sl is None or ((sl >= entry) if long else (sl <= entry)):
                        sl = zone["sl"]
                    t[f"risk_{lv}|{st}"] = abs(entry - sl) / entry * 100
                    for e in EXITS:
                        t[f"{lv}|{st}|{e}"] = simulate(long, entry, sl, e, market, tf, evalc, k,
                                                       times, lows, highs, top if e == "target" else None)
                out.append(t)
                break
    return out


def run_symbol(market, symbol, base, evals, now, since):
    out = []
    for tf in config.FIB_TL_TIMEFRAMES:
        res = trades.EVAL_RESOLUTION[market][tf]
        out += replay(market, symbol, tf, base.get(tf, []), evals.get(res, []), now, since)
    return out


def table(got):
    rows = []
    groups = defaultdict(list)
    for t in got:
        for tf in ("all", t["tf"]):
            groups[(t["market"], tf, "all")].append(t)
            if t["confluence"]:
                groups[(t["market"], tf, "fib+TL")].append(t)
    order = ["all"] + list(config.FIB_TL_TIMEFRAMES)
    for (market, tf, sub), items in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][2], order.index(kv[0][1]))):
        for lv, st in PLANS:
            risks = sorted(t[f"risk_{lv}|{st}"] for t in items)
            for e in EXITS:
                net = [t[f"{lv}|{st}|{e}"] for t in items if t[f"{lv}|{st}|{e}"] is not None]
                if not net:
                    continue
                rows.append({"market": market, "tf": tf, "set": sub, "entry": lv, "stop": st, "exit": e,
                             "alerts": len(items), "filled": len(net),
                             "wins_%": round(100 * sum(1 for x in net if x > 0.05) / len(net)),
                             "net_R": round(sum(net), 1), "R_per_trade": round(sum(net) / len(net), 3),
                             "median_risk_%": round(risks[len(risks) // 2], 2)})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default="2026-09-01")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    since = pd.Timestamp(args.since, tz=IST).timestamp()
    now = int(time.time())
    got = []

    def one(symbol):
        try:
            return run_symbol(CRYPTO, symbol, *crypto_load(symbol, now), now, since)
        except Exception as error:  # noqa: BLE001
            print(f"crypto {symbol} failed: {error}")
            return []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for r in pool.map(one, scanner.active_watchlist()):
            got += r
    import nse_scanner
    for symbol, (base, evals) in fbt.nse_data(nse_scanner.load_watchlist()).items():
        got += run_symbol(NSE, symbol, base, evals, now, since)
    pd.DataFrame(got).to_csv(OUT / "trades.csv", index=False)
    df = table(got)
    df.to_csv(OUT / "summary.csv", index=False)
    top = df[df["tf"] == "all"].sort_values(["market", "set", "R_per_trade"], ascending=[True, True, False])
    text = [f"# Fib entry / stop / exit backtest: {args.since} to now", "",
            "Live fib alerts (strong zone) replayed; entry, stop and exit change. Net R after Delta fees, "
            "stops slipped, timeouts closed at market. Crypto on Bitunix candles. fib+TL = a same-side trendline "
            "runs through the box.", "",
            "## All timeframes, best first", "", top.to_markdown(index=False), "",
            "## By timeframe", "", df[df["tf"] != "all"].to_markdown(index=False), ""]
    (OUT / "RESULTS.md").write_text("\n".join(text))
    print("\n".join(text))


if __name__ == "__main__":
    main()
