"""Discord alert audit (lakky, 2026-10-27): was every fib / trendline / 1D+ zone alert
sent since --since one today's rules allow, and did any alert the rules call for go missing?

Read-only: posts nothing, touches no state. Needs a copy of the scanner-runtime-state branch
(--state) and its git history (pass times come from fib_trendline_state.json's __last_scan__).

Part A - every alert, on the candles that existed when it went out:
  1. rebuilt: fib_trendline_scanner.analyse at the send time (closed candles, the forming
     range and the swept range from fine candles) gives the same key and plan;
  2. band, independent: the deepest price traded since the previous pass (Bitunix 1m / Yahoo 5m)
     came within the band of the entry (0.75%, 3% on 1W/1M; zones MAX_DISTANCE_PCT / 3%);
  3. not touched, independent: no fine candle of the alert's own forming candle, before the send,
     traded through the entry (fib) or the line (TL);
  4. TL line, independent: the line through the record's two points, extended to the forming
     bar, gives the entry; the stop is re-derived from the candles (lakky's candle stop).
Part B - missing / extra: fib_trendline_backtest.replay with today's live rules on the same
  candles over the window, matched against the live records (fib by fib + level, TL by side,
  entry and time). Zones are not replayed here.
"""
import argparse
import json
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import bitunix_data                              # noqa: E402
import config                                    # noqa: E402
import fib_engine                                # noqa: E402
import fib_trendline_backtest as bt              # noqa: E402
import fib_trendline_data as ftd                 # noqa: E402
import fib_trendline_scanner as fts              # noqa: E402
import fib_trendline_trades as trades            # noqa: E402
import scanner                                   # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
OUT = ROOT / "research" / "out" / "discord_audit"
LINES = []
TFS = ("4h", "1d", "1w", "1M")


def say(text=""):
    print(text)
    LINES.append(text)


def jl(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def when(ts):
    return datetime.fromtimestamp(ts, IST).strftime("%m-%d %H:%M")


def band_pct(kind, tf):
    base = scanner.MAX_DISTANCE_PCT if kind == "zone" else config.FIB_TL_MAX_DISTANCE_PCT
    return config.alert_band_pct(tf, base)


def pass_times(git_dir, since):
    """Every pass's time per market, from the state file's history."""
    out = {"crypto": set(), "nse": set()}
    try:
        hashes = subprocess.run(["git", "-C", str(git_dir), "log", "--format=%H", f"--since={since - 86400}",
                                 "FETCH_HEAD", "--", "fib_trendline_state.json"],
                                capture_output=True, text=True, check=True).stdout.split()
    except Exception as error:     # noqa: BLE001
        print(f"pass history unavailable: {error}")
        return {m: [] for m in out}
    for h in hashes:
        try:
            st = json.loads(subprocess.run(["git", "-C", str(git_dir), "show", f"{h}:fib_trendline_state.json"],
                                           capture_output=True, text=True, check=True).stdout)
        except Exception:          # noqa: BLE001
            continue
        for m, t in (st.get("__last_scan__") or {}).items():
            out.setdefault(m, set()).add(t)
        if st.get("__nse_last_scan__"):
            out["nse"].add(st["__nse_last_scan__"])
    return {m: sorted(v) for m, v in out.items()}


def previous(passes, ts):
    before = [p for p in passes if p < ts - 5]
    return before[-1] if before else None


# ----------------------------------------------------------------- candles

class Crypto:
    def __init__(self):
        self.cache = {}

    def source(self, symbol):
        contract = scanner.delta_contract(symbol) or symbol
        if bitunix_data.uses_bitunix(symbol):
            return "bitunix", bitunix_data.pair_for(symbol, contract)
        return "delta", contract

    def rows(self, symbol, res, start, end):
        src, name = self.source(symbol)
        if src == "bitunix":
            return [r[:5] for r in bitunix_data.klines(name, res, int(start), int(end) + 1)]
        return ftd.delta_candles(name, "5m" if res == "1m" else res, start, end)

    def chart(self, symbol, tf, now):
        key = (symbol, tf)
        if key not in self.cache:
            fetch_tf = "1d" if tf in ("1d", "1M") else tf
            self.cache[key] = self.rows(symbol, fetch_tf, ftd.HISTORY_START, time.time())
        rows = self.cache[key]
        return rows if tf != "1M" else ftd.monthly_from_daily(rows)

    def fine(self, symbol, start, end):
        """1m candles opening in [start, end), via 1h for the bulk of a long span."""
        key = (symbol, "fine", int(start), int(end))
        if key in self.cache:
            return self.cache[key]
        cut = max(int(start), (int(end) // 3600) * 3600 - 3600)
        out = []
        if cut > start:
            out += [r for r in self.rows(symbol, "1h", start, cut - 1) if r[0] + 3600 <= cut]
        out += [r for r in self.rows(symbol, "1m", cut, end) if r[0] < end]
        self.cache[key] = out
        return out


class Nse:
    def __init__(self, symbols):
        self.charts = ftd.nse_charts(symbols, list(TFS))
        self.five = ftd.nse_download(symbols, "5m", period="60d")
        self.hourly = ftd.nse_download(symbols, "1h")

    def chart(self, symbol, tf, now):
        return self.charts.get(symbol, {}).get(tf, [])

    def fine(self, symbol, start, end):
        return [r for r in self.five.get(symbol, []) if r[0] >= start - 300 and r[0] < end]


def candle_open(market, tf, ts):
    """Open time of the tf candle containing ts (the live charts' own boundaries)."""
    t = datetime.fromtimestamp(ts, timezone.utc if market == "crypto" else IST)
    if tf == "1M":
        return t.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
    if tf == "1w":
        d = (t - timedelta(days=t.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return d.timestamp()
    if tf == "1d":
        return t.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    if market == "crypto":
        return ts // 14400 * 14400
    start = t.replace(hour=9, minute=15, second=0, microsecond=0)
    if t >= start + timedelta(hours=4):
        start += timedelta(hours=4)
    return start.timestamp()


def closed_at(market, tf, rows, ts):
    return [c for c in rows if ftd.candle_close_ts(market, c[0], tf) <= ts]


# ----------------------------------------------------------------- Part A

def check_alert(r, feed, passes):
    market, symbol, tf, ts, kind = r["market"], r["symbol"], r["tf"], r["sent_ts"], r["kind"]
    plan = r["plan"]
    long = plan["side"] == "long"
    entry = plan["entry"]
    level = entry
    out = {"id": r["id"], "market": market, "kind": kind, "tf": tf, "symbol": symbol, "when": when(ts)}
    prev = previous(passes, ts)
    since = fts.sweep_start(prev, ts)
    fine = feed.fine(symbol, candle_open(market, tf, ts) - 1800, ts)
    width = 60 if market == "crypto" else 300
    swept_rows = [c for c in fine if c[0] + width > since and c[0] < ts]
    deepest = min([r["price"]] + [c[3] for c in swept_rows]) if long else max([r["price"]] + [c[2] for c in swept_rows])
    reach = ((deepest - entry) if long else (entry - deepest)) / entry * 100
    out["reach_pct"] = round(reach, 3)
    out["now_pct"] = round(((r["price"] - entry) if long else (entry - r["price"])) / entry * 100, 3)
    out["band_ok"] = reach <= band_pct(kind, tf) + 1e-6 or not swept_rows and out["now_pct"] <= band_pct(kind, tf)
    if kind == "zone":
        out["band_ok"] = reach <= band_pct(kind, tf) + 1e-6
    out["fine_rows"] = len(swept_rows)
    # the alert's own candle, before the send: closed fine candles only
    opened = candle_open(market, tf, ts)
    own = [c for c in fine if c[0] >= opened and c[0] + width <= ts]
    if kind == "fib":
        hit = [c for c in own if (c[3] < entry if long else c[2] > entry)]
    elif kind == "trendline":
        hit = [c for c in own if (c[3] <= entry if long else c[2] >= entry)]
    else:
        far = r["zone_bottom"] if long else r["zone_top"]
        hit = [c for c in own if (c[3] <= far if long else c[2] >= far)]
    out["touched_before"] = bool(hit)
    if hit:
        out["touched_at"] = when(hit[0][0])
    # rebuild with the bot's analysis
    try:
        rows = feed.chart(symbol, tf, ts)
        candles = [c for c in rows if c[0] <= ts]
        if market == "crypto":
            candles = closed_at(market, tf, candles, ts)
        forming = (min(c[3] for c in own), max(c[2] for c in own)) if own else None
        swept = (min(c[3] for c in swept_rows), max(c[2] for c in swept_rows)) if swept_rows else None
        trend = None
        if kind == "zone" and market == "crypto" and scanner.trend_filter_applies(symbol):
            daily = closed_at(market, "1d", feed.chart(symbol, "1d", ts), ts)
            trend = scanner._trend_from_daily([(c[0], c[4]) for c in daily], ts)
        a = fts.analyse(market, symbol, tf, candles, ts, r["price"], forming, trend, swept)
        hits = {"fib": a["fib"], "trendline": a["touch"], "zone": a["zone"]}[kind]
        same = [h for h in hits if h["key"] == r["key"]]
        out["rebuilt"] = bool(same)
        if same:
            p = same[0]["plan"]
            out["plan_same"] = abs(p["entry"] - entry) <= 1e-6 * entry and abs(p["sl"] - plan["sl"]) <= 1e-6 * entry
        else:
            out["rebuilt_keys"] = [h["key"] for h in hits][:4]
            if kind == "fib":
                closed = candles if fts.candle_is_closed(market, candles[-1][0], tf, ts) else candles[:-1]
                stamp = [str(c[0]) for c in closed]
                snaps, _ = fib_engine.run(stamp, [c[2] for c in closed], [c[3] for c in closed], N=config.FIB_SWING_LENGTH)
                s = snaps[-1]
                out["live_fib"] = f"d={s['d']} base={s['O']} top={s['E']} origin={closed[s['Ot']][0]}"
        if kind == "trendline":
            closed = candles if fts.candle_is_closed(market, candles[-1][0], tf, ts) else candles[:-1]
            stamps = [datetime.fromtimestamp(c[0], IST).strftime("%Y-%m-%d %H:%M") for c in closed]
            (y1, s1), (y2, s2) = r["from"], r["to"]
            if s1 in stamps and s2 in stamps:
                x1, x2, now_bar = stamps.index(s1), stamps.index(s2), len(closed)
                line = y1 + (y2 - y1) * (now_bar - x1) / (x2 - x1)
                out["line_ok"] = abs(line - entry) <= 1e-6 * entry
                # lakky's candle stop, re-derived: most recent wick and body >= 0.75% past entry, the closer one
                gap = entry * config.TRENDLINE_STOP_MIN_PCT / 100
                wick = body = None
                for c in reversed(closed):
                    w = c[3] if long else c[2]
                    b = min(c[1], c[4]) if long else max(c[1], c[4])
                    if wick is None and (w <= entry - gap if long else w >= entry + gap):
                        wick = w
                    if body is None and (b <= entry - gap if long else b >= entry + gap):
                        body = b
                    if wick is not None and body is not None:
                        break
                got = [x for x in (wick, body) if x is not None]
                want = (max(got) if long else min(got)) if got else None
                if want is None:
                    pct = config.TRENDLINE_SL_PCT.get(tf, 1.0) / 100
                    want = entry * (1 - pct) if long else entry * (1 + pct)
                out["stop_ok"] = abs(want - plan["sl"]) <= 1e-6 * entry
            else:
                out["line_ok"] = None
    except Exception as error:     # noqa: BLE001
        out["error"] = repr(error)[:200]
    return out


# ----------------------------------------------------------------- Part B

def replay_window(market, symbol, feed, since, now, eval_rows):
    bt.FIB_LEVELS = dict(config.FIB_ALERT_LEVELS)
    bt.EARLY_BAND = True
    got = []
    for tf in TFS:
        base = feed.chart(symbol, tf, now)
        res = trades.EVAL_RESOLUTION[market][tf]
        evalc = [c for c in eval_rows(res) if c[0] >= since]
        if not base or not evalc:
            continue
        try:
            got += bt.replay(market, symbol, tf, base, evalc, now)
        except Exception as error:     # noqa: BLE001
            print(f"replay {symbol} {tf}: {error}")
    return got


def match_part_b(market, replayed, records, all_keys, seeded_keys, since):
    """(missing, extra): replay alerts with no live record, live records with no replay alert."""
    live = [r for r in records if r["market"] == market and r["kind"] in ("fib", "trendline")]
    used = set()
    missing = []
    for a in replayed:
        if a["kind"] == "fib":
            sym, tf, d, origin, top = a["fib_id"].split("|")
            k = f"fib|{sym}|{tf}|{d}|{origin}|{top}|{a['zone']}"
            key = k if a["level"] == "L3" else f"{k}|{a['level']}"
            if key in all_keys or key in seeded_keys:
                used.add(key)
                continue
            missing.append(a)
        else:
            span = ftd.TF_SECONDS[a["tf"]]
            near = [r for r in live if r["kind"] == "trendline" and r["symbol"] == a["symbol"] and r["tf"] == a["tf"]
                    and r["plan"]["side"] == a["plan"]["side"]
                    and abs(r["plan"]["entry"] - a["plan"]["entry"]) <= 0.01 * a["plan"]["entry"]
                    and abs(r["sent_ts"] - a["alert_ts"]) <= span + 3600]
            if near:
                used.update(r["id"] for r in near)
            else:
                missing.append(a)
    live = [r for r in live if r["sent_ts"] >= since]
    extra = [r for r in live if (r["key"] not in used if r["kind"] == "fib" else r["id"] not in used)]
    return missing, extra


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--since", default="2026-10-21T15:15")
    ap.add_argument("--no-replay", action="store_true")
    ap.add_argument("--git-dir", default=".", help="repo whose FETCH_HEAD is the state branch")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    state = Path(args.state)
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc).timestamp()
    now = time.time()
    records = jl(state / "fib_trendline_alert_records.jsonl")
    window = [r for r in records if r["sent_ts"] >= since]
    st = json.loads((state / "fib_trendline_state.json").read_text())
    passes = pass_times(args.git_dir, since)
    say(f"# Discord alert audit - alerts sent {when(since)} IST to {when(now)} IST\n")
    say(f"{len(window)} fib / trendline / 1D+ zone records; passes: crypto {len(passes.get('crypto', []))}, "
        f"NSE {len(passes.get('nse', []))}\n")

    crypto = Crypto()
    nse_syms = sorted({r["symbol"] for r in window if r["market"] == "nse"})
    import nse_scanner
    nse_all = nse_scanner.load_watchlist()
    nse = Nse(sorted(set(nse_syms) | set(nse_all)))

    results = []
    for r in window:
        feed = crypto if r["market"] == "crypto" else nse
        try:
            results.append(check_alert(r, feed, passes.get(r["market"], [])))
        except Exception:      # noqa: BLE001
            results.append({"id": r["id"], "market": r["market"], "kind": r["kind"], "tf": r["tf"],
                            "error": traceback.format_exc()[-300:]})
    (OUT / "part_a.json").write_text(json.dumps(results, indent=1))
    say("## A. Every alert vs today's rules\n")
    say("| market | kind | tf | alerts | rebuilt | band ok | touched before | line ok | stop ok | errors |")
    say("|---|---|---|---|---|---|---|---|---|---|")
    groups = defaultdict(list)
    for x in results:
        groups[(x["market"], x["kind"], x["tf"])].append(x)
    for g in sorted(groups):
        xs = groups[g]
        c = lambda f: sum(1 for x in xs if x.get(f) is True)   # noqa: E731
        say(f"| {g[0]} | {g[1]} | {g[2]} | {len(xs)} | {c('rebuilt')} | {c('band_ok')} | {c('touched_before')} | "
            f"{c('line_ok')} | {c('stop_ok')} | {sum(1 for x in xs if 'error' in x)} |")
    say("\n### Not rebuilt / band missed / touched before (first 80)\n")
    bad = [x for x in results if not x.get("rebuilt") or not x.get("band_ok") or x.get("touched_before")
           or x.get("line_ok") is False or x.get("stop_ok") is False or "error" in x]
    for x in bad[:80]:
        say("- " + json.dumps({k: v for k, v in x.items() if k not in ("market",)}))

    if args.no_replay:
        (OUT / "REPORT.md").write_text("\n".join(LINES) + "\n")
        return
    say("\n## B. Missing / extra vs a replay with today's rules\n")
    seeded = {k for k, v in st.items() if isinstance(v, dict) and "sent" in v}
    all_keys = {r["key"] for r in records}
    rows_b = []
    for market in ("crypto", "nse"):
        symbols = list(scanner.active_watchlist()) if market == "crypto" else nse_all
        replayed = []
        for symbol in symbols:
            if market == "crypto":
                feed = crypto
                eval_rows = lambda res, s=symbol: crypto.rows(s, res, since - 86400 * 2, now)   # noqa: E731
            else:
                feed = nse
                cache = {}

                def eval_rows(res, s=symbol, cache=cache):
                    if res not in cache:
                        cache[res] = (nse.charts.get(s, {}).get("1d", []) if res == "1d"
                                      else nse.hourly.get(s, []) if res == "1h"
                                      else ftd.nse_download([s], res).get(s, []))
                    return cache[res]
            try:
                replayed += replay_window(market, symbol, feed, since, now, eval_rows)
            except Exception as error:     # noqa: BLE001
                print(f"replay {symbol}: {error}")
        missing, extra = match_part_b(market, replayed, records, all_keys, seeded, since)
        live_n = sum(1 for r in window if r["market"] == market and r["kind"] in ("fib", "trendline"))
        say(f"- {market}: replay {len(replayed)} alerts, live {live_n}; replay-only {len(missing)}, live-only {len(extra)}")
        for a in missing[:40]:
            rows_b.append({"market": market, "type": "replay-only", "symbol": a["symbol"], "tf": a["tf"],
                           "kind": a["kind"], "level": a.get("level"), "when": when(a["alert_ts"]),
                           "entry": a["plan"]["entry"], "side": a["plan"]["side"]})
        for r in extra[:40]:
            rows_b.append({"market": market, "type": "live-only", "symbol": r["symbol"], "tf": r["tf"],
                           "kind": r["kind"], "level": r.get("level"), "when": when(r["sent_ts"]),
                           "entry": r["plan"]["entry"], "side": r["plan"]["side"]})
        tally = Counter((a["tf"], a["kind"]) for a in missing)
        say(f"  replay-only by tf/kind: {dict(tally)}")
        tally = Counter((r["tf"], r["kind"]) for r in extra)
        say(f"  live-only by tf/kind: {dict(tally)}")
    (OUT / "part_b.json").write_text(json.dumps(rows_b, indent=1))
    for x in rows_b[:120]:
        say("- " + json.dumps(x))
    (OUT / "REPORT.md").write_text("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
