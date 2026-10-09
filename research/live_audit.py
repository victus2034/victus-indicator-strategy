"""Research only: hand-trace live alerts against real candles, and re-score
the recorded trades with a scorer written apart from the bot's.

Reads a copy of the scanner-runtime-state branch (--state). Writes
research/out/live_audit/. Posts nothing.

Part A - zone alerts (crypto 30m / 4h): rebuild the zones from the venue the
  alert says it used, on the candles that existed when it went out (closed
  candles plus the forming one built from 1m), then check the zone exists, is
  the nearest, and that distance, band, approach side, stop and the daily
  trend filter all match the rules - the last four by plain arithmetic, not
  the bot's helpers.
Part B - fib / trendline alerts since the v6 seed (crypto): replay the
  analysis on Bitunix candles at the send time and check the record's level,
  plan and band; the plan arithmetic is re-derived independently.
Part C - crypto zone trades finalized since --since: re-score each on Delta
  5m candles with an independent loop and compare outcome and net R.
Part D - fib / trendline results: re-score on Delta (crypto) with an
  independent loop and compare.
"""
import argparse
import json
import math
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config                                   # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
OUT = ROOT / "research" / "out" / "live_audit"
LINES = []


def say(text=""):
    print(text)
    LINES.append(text)


def jl(path):
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def ts_of(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-12)


# --------------------------------------------------------------- candle sources

def delta_rows(contract, resolution, start, end):
    """[open_ts, o, h, l, c, v] from Delta, paged by 2000."""
    step = {"1m": 60, "5m": 300, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}[resolution]
    out = {}
    cursor = int(end)
    while cursor > start:
        lo = max(int(start), cursor - 1999 * step)
        for attempt in range(4):
            try:
                r = requests.get(f"{config.DELTA_API_BASE_URL}/v2/history/candles",
                                 params={"symbol": contract, "resolution": resolution, "start": lo, "end": cursor},
                                 timeout=20)
                rows = r.json().get("result") or []
                break
            except Exception:           # noqa: BLE001
                time.sleep(2 * (attempt + 1))
        else:
            rows = []
        for c in rows:
            out[int(c["time"])] = [int(c["time"]), float(c["open"]), float(c["high"]), float(c["low"]),
                                   float(c["close"]), float(c.get("volume") or 0)]
        cursor = lo - 1
        if not rows:
            break
    return [out[k] for k in sorted(out)]


_CACHE = {}


def cached(key, fn):
    if key not in _CACHE:
        _CACHE[key] = fn()
    return _CACHE[key]


# --------------------------------------------------------------- Part A

def part_a(state, since_ts):
    import importlib
    import os
    import bitunix_data
    say("## A. Zone alerts rebuilt from candles\n")
    totals = Counter()
    problems = []
    for tf, fname in (("30m", "crypto_alert_records_30m.jsonl"), ("4h", "crypto_alert_records.jsonl")):
        os.environ["VICTUS_TIMEFRAME"] = tf
        importlib.reload(config)
        import scanner
        importlib.reload(scanner)
        step = scanner.TIMEFRAME_SECONDS[tf]
        recs = [r for r in jl(state / fname) if r.get("delivered_at_utc") and ts_of(r["delivered_at_utc"]) >= since_ts]
        say(f"### {tf}: {len(recs)} alerts since {datetime.fromtimestamp(since_ts, timezone.utc):%Y-%m-%d}")
        by_symbol = defaultdict(list)
        for r in recs:
            by_symbol[(r["symbol"], r.get("exchange"))].append(r)
        for (symbol, venue), rows in sorted(by_symbol.items()):
            contract = scanner.delta_contract(symbol)
            first = min(ts_of(r["delivered_at_utc"]) for r in rows)
            last = max(ts_of(r["delivered_at_utc"]) for r in rows)
            start = first - (config.OHLCV_LIMIT + 5) * step
            try:
                if venue == "bitunix":
                    pair = bitunix_data.bitunix_pair(contract)
                    bars = cached(("b", pair, tf), lambda: bitunix_data.klines(pair, tf, start, last + step))
                    ones = cached(("b1", pair, first), lambda: bitunix_data.klines(pair, "1m", first - step, last + 60))
                    daily = cached(("bd", pair), lambda: bitunix_data.klines(pair, "1d", first - 260 * 86400, last + 86400))
                else:
                    bars = cached(("d", contract, tf), lambda: delta_rows(contract, tf, start, last + step))
                    ones = cached(("d1", contract, first), lambda: delta_rows(contract, "1m", first - step, last + 60))
                    daily = cached(("dd", contract), lambda: delta_rows(contract, "1d", first - 260 * 86400, last + 86400))
            except Exception as error:     # noqa: BLE001
                say(f"- {symbol} {venue}: fetch failed {error!r}")
                totals["fetch failed"] += len(rows)
                continue
            for r in rows:
                sent = ts_of(r["delivered_at_utc"])
                opened = int(sent) // step * step
                closed = [b for b in bars if b[0] < opened][-(config.OHLCV_LIMIT - 1):]
                part = [m for m in ones if opened <= m[0] and m[0] + 60 <= sent]
                if part:
                    forming = [opened, part[0][1], max(m[2] for m in part), min(m[3] for m in part), part[-1][4], sum(m[5] for m in part)]
                    candles = closed + [forming]
                else:
                    candles = closed
                df = pd.DataFrame([[c[0] * 1000, *c[1:6]] for c in candles],
                                  columns=["time", "open", "high", "low", "close", "volume"])
                supply, demand = scanner.build_zones(df)
                ztype = r["zone_type"]
                zones = demand if ztype == "demand" else supply
                price = float(r["alert_price"])
                found = [z for z in zones if z["active"] and rel(z["bottom"], r["zone_bottom"]) < 1e-6 and rel(z["top"], r["zone_top"]) < 1e-6]
                near = [z for z in zones if z["active"] and rel(z["bottom"], r["zone_bottom"]) < 3e-3 and rel(z["top"], r["zone_top"]) < 3e-3]
                nearest, ndist = scanner.nearest_active_zone(price, zones, ztype, len(df) - 1)
                nearest_ok = nearest is not None and rel(nearest["bottom"], r["zone_bottom"]) < 3e-3 and rel(nearest["top"], r["zone_top"]) < 3e-3
                # Independent arithmetic.
                bottom, top = float(r["zone_bottom"]), float(r["zone_top"])
                entry = top if ztype == "demand" else bottom
                dist = abs(entry - price) / price * 100
                pad = (top - bottom) * config.ZONE_SL_HEIGHT_PCT / 100
                stop = bottom - pad if ztype == "demand" else top + pad
                past = price < entry if ztype == "demand" else price > entry
                band = config.MIN_DISTANCE_PCT <= dist <= config.MAX_DISTANCE_PCT
                hour = datetime.fromtimestamp(sent, IST).time()
                window = hour >= config.CRYPTO_ALERT_START or hour <= config.CRYPTO_ALERT_END
                trend_ok = True
                if config.CRYPTO_TREND_FILTER and symbol in config.CRYPTO_WATCHLIST:
                    closes = [d[4] for d in daily if d[0] + 86400 <= sent][-200:]
                    if len(closes) >= config.CRYPTO_TREND_EMA + 5:
                        ema = closes[0]
                        k = 2 / (config.CRYPTO_TREND_EMA + 1)
                        for c in closes[1:]:
                            ema = c * k + ema * (1 - k)
                        up = closes[-1] > ema
                        trend_ok = up if ztype == "demand" else not up
                checks = {
                    "zone exact": bool(found), "zone within 0.3%": bool(near), "nearest": nearest_ok,
                    "distance": abs(dist - float(r["distance_pct"])) < 1e-6,
                    "band": band, "approach side": not past,
                    "stop": rel(stop, float(r["stop_price"])) < 1e-9,
                    "entry": rel(entry, float(r["planned_entry"])) < 1e-9,
                    "alert window": window, "trend filter": trend_ok,
                }
                totals["alerts"] += 1
                for name, ok in checks.items():
                    totals[f"{name} ok" if ok else f"{name} FAIL"] += 1
                bad = [n for n, ok in checks.items() if not ok]
                if bad:
                    problems.append(f"{tf} {symbol} {venue} {r['delivered_at_utc'][:16]} {ztype} {bottom}-{top} price {price}: {', '.join(bad)}")
    say("")
    for k in sorted(totals):
        say(f"- {k}: {totals[k]}")
    say("\nAlerts with a failed check:")
    for p in problems[:200]:
        say(f"- {p}")
    if len(problems) > 200:
        say(f"- ... {len(problems) - 200} more")


# --------------------------------------------------------------- Part B

def part_b(state):
    import bitunix_data
    import fib_engine
    import fib_trendline_scanner as fts
    from fib_trendline_data import monthly_from_daily, TF_SECONDS
    say("\n## B. Fib / trendline alerts replayed (crypto, since the v6 seed)\n")
    st = json.loads((state / "fib_trendline_state.json").read_text())
    seeded = st["__seeded__"].get("fib:crypto:v6-bitunix", 0)
    recs = [r for r in jl(state / "fib_trendline_alert_records.jsonl") if r["market"] == "crypto" and r["sent_ts"] > seeded + 60]
    say(f"{len(recs)} crypto fib/TL alerts after the seed at {datetime.fromtimestamp(seeded, timezone.utc):%Y-%m-%d %H:%M} UTC")
    totals = Counter()
    problems = []
    import scanner
    for r in recs:
        symbol, tf, sent = r["symbol"], r["tf"], r["sent_ts"]
        contract = scanner.delta_contract(symbol)
        source = "bitunix" if bitunix_data.uses_bitunix(symbol) else "delta"
        try:
            if source == "bitunix":
                pair = bitunix_data.bitunix_pair(contract)
                fetch_tf = "1d" if tf in ("1d", "1M") else tf
                rows = cached(("fb", pair, fetch_tf), lambda: [x[:5] for x in bitunix_data.klines(pair, fetch_tf, sent - 2000 * 86400, time.time())])
                ones = bitunix_data.klines(pair, "1m", sent - 600, sent + 1)
                price = ones[-1][4] if ones else None
            else:
                import fib_trendline_data as ftd
                fetch_tf = "1d" if tf in ("1d", "1M") else tf
                rows = cached(("fd", contract, fetch_tf), lambda: ftd.delta_candles(contract, fetch_tf, sent - 2000 * 86400, time.time()))
                ones = delta_rows(contract, "1m", sent - 600, sent)
                price = ones[-1][4] if ones else None
        except Exception as error:     # noqa: BLE001
            totals["fetch failed"] += 1
            problems.append(f"{symbol} {tf}: fetch failed {error!r}")
            continue
        candles = [c for c in rows if c[0] + (TF_SECONDS[fetch_tf] if fetch_tf != "1M" else 0) <= sent]
        if tf == "1M":
            candles = monthly_from_daily(candles)
        if source == "delta":
            # Delta also returns the forming candle; the scanner sees it.
            candles = [c for c in rows if c[0] <= sent]
            if tf == "1M":
                candles = monthly_from_daily(candles)
        analysis = fts.analyse("crypto", symbol, tf, candles, sent, r["price"])
        hits = analysis["fib"] if r["kind"] == "fib" else analysis["touch"]
        match = [h for h in hits if h["key"] == r["key"]]
        totals["alerts"] += 1
        plan = r["plan"]
        # Independent plan arithmetic.
        if r["kind"] == "trendline":
            pct = config.TRENDLINE_SL_PCT.get(tf, 1.0) / 100
            want_sl = plan["entry"] * (1 - pct) if plan["side"] == "long" else plan["entry"] * (1 + pct)
            arith = rel(want_sl, plan["sl"]) < 1e-9
            dist = (r["price"] - plan["entry"]) / plan["entry"] * 100 if plan["side"] == "long" else (plan["entry"] - r["price"]) / plan["entry"] * 100
        else:
            arith = (plan["side"] == "long" and plan["sl"] < plan["entry"]) or (plan["side"] == "short" and plan["sl"] > plan["entry"])
            dist = None
        if match:
            m = match[0]
            totals["key reproduced"] += 1
            same_plan = rel(m["plan"]["entry"], plan["entry"]) < 1e-6 and rel(m["plan"]["sl"], plan["sl"]) < 1e-6
            totals["plan same" if same_plan else "plan DIFF"] += 1
            if r["kind"] == "fib":
                d, base, top = m["d"], m["base"], m["top"]
                u66, u55, d55, d66 = fib_engine.levels(base, top)
                deeper_low, deeper_high = (d66, d55) if d == 1 else (u55, u66)
                entry = deeper_high if d == 1 else deeper_low
                pad = (deeper_high - deeper_low) * config.FIB_SL_HEIGHT_PCT / 100
                sl = deeper_low - pad if d == 1 else deeper_high + pad
                ok = rel(entry, plan["entry"]) < 1e-9 and rel(sl, plan["sl"]) < 1e-9 and m["zone"] == 2
                totals["fib deeper zone + S/R stop ok" if ok else "fib deeper zone + S/R stop FAIL"] += 1
                if not ok:
                    problems.append(f"{symbol} {tf} fib plan {plan} vs independent entry {entry} sl {sl}")
            if not same_plan:
                problems.append(f"{symbol} {tf} {r['kind']} plan {plan} replay {m['plan']}")
        else:
            totals["key NOT reproduced"] += 1
            keys = [h["key"] for h in hits]
            problems.append(f"{symbol} {tf} {r['kind']} {datetime.fromtimestamp(sent, timezone.utc):%m-%d %H:%M} key {r['key']} not in replay ({len(hits)} hits, price replay {price} vs rec {r['price']}): {keys[:3]}")
        totals["plan arithmetic ok" if arith else "plan arithmetic FAIL"] += 1
        if dist is not None:
            band = 0 <= dist <= config.FIB_TL_MAX_DISTANCE_PCT
            totals["tl band ok" if band else "tl band FAIL"] += 1
            if not band:
                problems.append(f"{symbol} {tf} trendline sent at {dist:.3f}% from the line")
    for k in sorted(totals):
        say(f"- {k}: {totals[k]}")
    say("\nNot reproduced / failed:")
    for p in problems[:150]:
        say(f"- {p}")


# --------------------------------------------------------------- Part C

def score_zone(bars, rec, tf):
    """Independent zone-trade scorer on 5m [ts,o,h,l,c] bars. Returns (outcome, net_r) or a reason."""
    import daily_backtest_summary as dbs   # constants only
    side = rec["side"]
    s = 1 if side == "long" else -1
    entry = float(rec["planned_entry"])
    stop = float(rec["stop_price"])
    risk = s * (entry - stop)
    if risk <= 0:
        return "bad risk", None
    sent = ts_of(rec["alert_time"]) if "alert_time" in rec else None
    event = max(i for i, b in enumerate(bars) if b[0] <= sent)
    wait = int({"30m": 1800, "4h": 14400}[tf] * 3 / 300)
    fill = None
    for i in range(event + 1, min(event + wait, len(bars) - 1) + 1):
        if (bars[i][3] <= entry) if s > 0 else (bars[i][2] >= entry):
            fill = i
            break
    if fill is None:
        return "zone_not_touched", None
    cost = dbs.CRYPTO_ROUND_TRIP_COST_PCT
    cost_r = entry * cost / 100 / risk
    if cost_r > dbs.MAX_COST_R:
        return "stop_too_tight", None
    expiry = bars[fill][0] + 6 * 3600
    last = max(i for i, b in enumerate(bars) if b[0] + 300 <= expiry)
    half = entry + s * 0.5 * risk
    t2 = entry + s * 2 * risk
    t1 = entry + s * risk
    be = entry + s * entry * dbs.CRYPTO_BREAK_EVEN_OFFSET_PCT / 100
    be_ok = s * (half - be) >= 0
    slip = dbs.SL_FILL_SLIPPAGE_PCT / 100
    moved = False
    reached1 = False
    for i in range(fill, last + 1):
        o, h, l = bars[i][1], bars[i][2], bars[i][3]
        if i == fill and not ((o <= entry) if s > 0 else (o >= entry)):
            h, l = (min(h, entry), l) if s > 0 else (h, max(l, entry))
        live = be if moved else stop
        hit_stop = (l <= live) if s > 0 else (h >= live)
        hit_half = (h >= half) if s > 0 else (l <= half)
        hit_t1 = (h >= t1) if s > 0 else (l <= t1)
        hit_t2 = (h >= t2) if s > 0 else (l <= t2)
        if hit_stop and ((hit_half and not moved) or hit_t1 or hit_t2):
            return "same-candle", None
        if hit_stop:
            exit_px = live - s * live * slip
            return ("BE" if moved else "SL"), s * (exit_px - entry) / risk - cost_r
        if hit_t2:
            return "+2R", 2 - cost_r
        if hit_t1:
            reached1 = True
        if hit_half and be_ok:
            moved = True
    close = bars[last][4]
    return ("+1R" if reached1 else "Neither"), s * (close - entry) / risk - cost_r


def part_c(state, since_ts):
    import scanner
    say("\n## C. Crypto zone trades re-scored independently (Delta 5m)\n")
    rows = [r for r in jl(state / "daily_backtest_finalized_records.jsonl")
            if r.get("market") in ("CRYPTO", "XSTOCK", "OTHER") and r.get("alert_time") and ts_of(r["alert_time"]) >= since_ts]
    say(f"{len(rows)} finalized crypto/xStock/other rows since the cut")
    totals = Counter()
    diffs = []
    by_symbol = defaultdict(list)
    for r in rows:
        by_symbol[r["symbol"]].append(r)
    mine_sum = theirs_sum = 0.0
    for symbol, recs in by_symbol.items():
        contract = scanner.delta_contract(symbol)
        lo = min(ts_of(r["alert_time"]) for r in recs) - 3600
        hi = max(ts_of(r["alert_time"]) for r in recs) + 20 * 3600
        bars = cached(("d5", contract), lambda: [b[:5] for b in delta_rows(contract, "5m", lo, min(hi, time.time()))])
        for r in recs:
            theirs = r.get("final_result") or r.get("outcome")
            tf = r.get("timeframe")
            try:
                mine, net = score_zone(bars, r, tf)
            except Exception as error:     # noqa: BLE001
                mine, net = f"error {error!r}", None
            totals["rows"] += 1
            if mine == "same-candle":
                totals["same-candle (resolved on finer candles by the bot, skipped)"] += 1
                continue
            tnet = r.get("net_realized_r")
            agree = mine == theirs and (net is None or tnet is None or abs(net - float(tnet)) < 0.02)
            totals["agree" if agree else "DIFFER"] += 1
            if net is not None and tnet is not None and not (isinstance(tnet, float) and math.isnan(tnet)):
                mine_sum += net
                theirs_sum += float(tnet)
            if not agree:
                diffs.append(f"{symbol} {tf} {r['alert_time'][:16]} {r['side']} entry {r.get('planned_entry')} stop {r.get('stop_price')}: bot {theirs} {tnet} / independent {mine} {net}")
    for k in sorted(totals):
        say(f"- {k}: {totals[k]}")
    say(f"- net R on rows both scored: bot {theirs_sum:+.2f} / independent {mine_sum:+.2f}")
    say("\nDisagreements:")
    for d in diffs[:150]:
        say(f"- {d}")


# --------------------------------------------------------------- Part D

def score_fib_tl(after, plan, tf):
    """Independent fib/TL scorer on evaluation candles after the alert."""
    import fib_trendline_trades as trades
    s = 1 if plan["side"] == "long" else -1
    entry, sl = plan["entry"], plan["sl"]
    risk = abs(entry - sl)
    per = trades.EVAL_PER_BAR["crypto"][tf]
    wait, hold = config.FIB_TL_ENTRY_WAIT_BARS * per, config.FIB_TL_MAX_HOLD_BARS * per
    fill = None
    for i, b in enumerate(after[:wait]):
        if (b[3] <= entry) if s > 0 else (b[2] >= entry):
            fill = i
            break
    if fill is None:
        mine = "no fill" if len(after) >= wait else "open"
    else:
        b = after[fill]
        if (b[3] <= sl) if s > 0 else (b[2] >= sl):
            mine = "SL"
        else:
            half, t1, t2 = entry + s * risk / 2, entry + s * risk, entry + s * 2 * risk
            be = entry + s * entry * trades.BREAK_EVEN_PCT["crypto"] / 100
            be_ok = s * (half - be) >= 0
            moved = r1 = False
            mine = "open"
            for j, b in enumerate(after[fill + 1:], start=1):
                if j > hold:
                    mine = "1R" if r1 else "timeout"
                    break
                live = be if (moved and be_ok) else sl
                if (b[3] <= live) if s > 0 else (b[2] >= live):
                    mine = "1R" if r1 else ("BE" if moved and be_ok else "SL")
                    break
                if (b[2] >= t2) if s > 0 else (b[3] <= t2):
                    mine = "2R"
                    break
                if (b[2] >= t1) if s > 0 else (b[3] <= t1):
                    r1 = moved = True
                if (b[2] >= half) if s > 0 else (b[3] <= half):
                    moved = True
    return mine


def part_d(state, since_ts):
    import fib_trendline_trades as trades
    import scanner
    from fib_trendline_data import delta_candles
    say("\n## D. Fib / trendline results re-scored independently (crypto, Delta)\n")
    recs = {r["id"]: r for r in jl(state / "fib_trendline_alert_records.jsonl") if r["market"] == "crypto" and r["sent_ts"] >= since_ts}
    results = json.loads((state / "fib_trendline_results.json").read_text())
    totals = Counter()
    diffs = []
    for rid, r in recs.items():
        res = results.get(rid)
        if not res or not res.get("resolved"):
            totals["not resolved yet"] += 1
            continue
        if res.get("past_sl"):
            totals["past SL (no trade)"] += 1
            continue
        resolution = trades.EVAL_RESOLUTION["crypto"][r["tf"]]
        contract = scanner.delta_contract(r["symbol"])
        bars = cached(("fd", contract, resolution), lambda: delta_candles(contract, resolution, since_ts - 86400 * 3, time.time()))
        after = [b for b in bars if b[0] > r["sent_ts"]]
        mine = score_fib_tl(after, r["plan"], r["tf"])
        totals["scored"] += 1
        if mine == res.get("outcome"):
            totals["agree"] += 1
        else:
            totals["DIFFER"] += 1
            diffs.append(f"{r['symbol']} {r['tf']} {r['kind']} {datetime.fromtimestamp(r['sent_ts'], timezone.utc):%m-%d %H:%M}: bot {res.get('outcome')} / independent {mine}")
    for k in sorted(totals):
        say(f"- {k}: {totals[k]}")
    say("\nDisagreements:")
    for d in diffs[:100]:
        say(f"- {d}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--since", default="2026-10-05")
    parser.add_argument("--parts", default="a,b,c,d")
    args = parser.parse_args()
    state = Path(args.state)
    since_ts = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc).timestamp()
    OUT.mkdir(parents=True, exist_ok=True)
    say(f"# Live audit ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, since {args.since})\n")
    for name, fn in (("a", lambda: part_a(state, since_ts)), ("b", lambda: part_b(state)),
                     ("c", lambda: part_c(state, since_ts)), ("d", lambda: part_d(state, since_ts))):
        if name in args.parts:
            try:
                fn()
            except Exception:          # noqa: BLE001
                say(f"\nPart {name} crashed:\n```\n{traceback.format_exc()}\n```")
            (OUT / "LIVE_AUDIT.md").write_text("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
