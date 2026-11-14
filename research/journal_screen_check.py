"""lakky, 2026-11-14: "i backtest this settings in all time and it give good return so i want you
to check are these settings matches with current settings or not" - two journal Signals screens
(v.191), period All (= the journal's history, 1 Jun - 14 Nov 2026), Market Crypto, CRYPTO 1D,
Assets Crypto, Coins CoinDCX, BTC day All, Exit 1.5R, SL wick or body >= 0.75% past entry,
SL shift +1R -> +0.5R, Partial off, Trail TP +0.5R / 0.5R behind, Till TP / SL, fees on:

  Trendline, type All:  466 alerts, 449 filled, 200W / 190L, +3.42R, PF 1.02, max DD -37.78R
  Fib, levels L2-L4:    284 alerts, 269 filled, 119W / 125L, +10.65R, PF 1.08, max DD -26.51R

Both are played again by the journal's own independent retest (journal tools/signals-retest.py,
fetched from the journal repo at run time - not a copy) on Delta 15m / 1d candles:
  - his screen, to confirm the journal's numbers,
  - the live CoinDCX bot's exits (SL shift +1R -> +0.75R, Trail TP +0.25R / 0.5R behind),
  - the CoinDCX demo's fib rule (the alert's own SL, the bot's exits),
and every set split into the 16 crypto the scanner watches today and the 9 dropped on 8 Nov.

    python research/journal_screen_check.py STATE_DIR RETEST_PY JOURNAL_INDEX_HTML
"""
from __future__ import annotations

import gzip
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
from journal_fib_setup_backtest import delta  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
OUT = Path(__file__).resolve().parent / "out" / "journal_screen_check"
DAY = 86400
NOT_COIN = {"XAUT", "PAXG", "SLVON", "CL"}           # the journal's SIG_NOT_COIN
TODAY_16 = set(config.CRYPTO_WATCHLIST)

SCREEN = {"tgt": "1.5R", "sl": {"mode": "near", "gap": 0.75}, "stop": {"mode": "shift", "shAt": 1, "shTo": 0.5},
          "trail": {"on": True, "step": 0.5, "gap": 0.5}, "hold": "tp"}
BOT = dict(SCREEN, stop={"mode": "shift", "shAt": 1, "shTo": 0.75}, trail={"on": True, "step": 0.25, "gap": 0.5})
DEMO_FIB = dict(BOT, sl={})                            # the alert's own SL
JOURNAL = {"trendline": "466 alerts, 449 filled, 200W / 190L, +3.42R, PF 1.02, max DD -37.78R",
           "fib": "284 alerts, 269 filled, 119W / 125L, +10.65R, PF 1.08, max DD -26.51R"}


def base_of(symbol):
    return re.sub(r"(USDT|USDC|USD)$", "", re.sub(r"[^A-Z0-9]", "", symbol.upper().split("/")[0].split(":")[0]))


def level_of(rec):
    parts = rec.get("key", "").split("|")
    tag = parts[7] if len(parts) > 7 else ""
    return tag if tag in ("L1", "L2", "L3", "L4") else {"1": "L1", "2": "L3"}.get(parts[6] if len(parts) > 6 else "", "")


def load(path):
    for raw in open(path, encoding="utf-8"):
        try:
            yield json.loads(raw)
        except ValueError:
            continue


def records(state, dcx):
    """The alerts the journal shows: the rebuild before its cutoff, live records after."""
    meta = json.loads((state / "fibtl_rebuild_meta.json").read_text())
    cutoff = datetime.fromisoformat(meta["cutoff"]).timestamp()
    rows = [r for r in load(state / "fibtl_rebuild_records.jsonl") if r.get("sent_ts", 0) < cutoff]
    rows += [r for r in load(state / "fib_trendline_alert_records.jsonl") if r.get("sent_ts", 0) >= cutoff]

    def ok(r):
        b = base_of(r.get("symbol", ""))
        return (r.get("market") == "crypto" and r.get("tf") == "1d" and r.get("kind") in ("trendline", "fib")
                and isinstance(r.get("plan"), dict) and b in dcx and b not in NOT_COIN
                and (r["kind"] != "fib" or level_of(r) in ("L2", "L3", "L4")))
    return sorted((r for r in rows if ok(r)), key=lambda r: r["sent_ts"]), cutoff


def stats(rows):
    """rows = [(record, result)] in alert order."""
    closed = [x for _, x in rows if x.get("r") is not None]
    filled = sum(1 for _, x in rows if x.get("filled"))
    no_stop = sum(1 for _, x in rows if x.get("label") == "no stop")
    no_fill = sum(1 for _, x in rows if x.get("filled") is False)
    wins = [x["r"] for x in closed if x["r"] > 0]
    losses = [x["r"] for x in closed if x["r"] <= 0]
    total = sum(x["r"] for x in closed)
    peak = run = dd = 0.0
    for x in closed:
        run += x["r"]
        peak = max(peak, run)
        dd = min(dd, run - peak)
    pf = sum(wins) / -sum(losses) if losses and sum(losses) < 0 else float("inf")
    return {"alerts": len(rows), "filled": filled, "no_fill": no_fill, "no_stop": no_stop, "closed": len(closed),
            "w": len(wins), "l": len(losses), "total": total, "avg": total / len(closed) if closed else 0.0,
            "pf": pf, "dd": dd}


HEAD = "| Set | Alerts | Filled | W / L | Win % | Total R | R / trade | PF | Max DD |\n|---|---|---|---|---|---|---|---|---|"


def line(name, rows):
    s = stats(rows)
    win = 100 * s["w"] / s["closed"] if s["closed"] else 0
    return (f"| {name} | {s['alerts']} | {s['filled']} | {s['w']}W / {s['l']}L | {win:.0f}% | {s['total']:+.2f}R | "
            f"{s['avg']:+.3f}R | {s['pf']:.2f} | {s['dd']:.2f}R |")


def main(state, retest, index_html):
    state = Path(state)
    html = Path(index_html).read_text(encoding="utf-8")
    dcx = set(json.loads(re.search(r"const DEMO_DCX = (\{.*?\});", html).group(1)))
    recs, cutoff = records(state, dcx)
    results = json.loads((state / "fibtl_rebuild_results.json").read_text())
    now = int(time.time()) // 900 * 900
    syms = sorted({r["symbol"] for r in recs})
    first = min(r["sent_ts"] for r in recs)
    candles, missing = {}, []
    for sym in syms:
        candles[sym + "_15m"] = delta(sym, 15, "15m", first - DAY, now)
        candles[sym + "_1d"] = delta(sym, 1440, "1d", first - 330 * DAY, now)
        if not candles[sym + "_15m"]:
            missing.append(sym)
        print(sym, len(candles[sym + "_15m"]), len(candles[sym + "_1d"]), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    fx = OUT / "fixture.json.gz"
    with gzip.open(fx, "wt") as f:
        json.dump({"now": now, "records": recs, "results": {r["id"]: results[r["id"]] for r in recs if r["id"] in results},
                   "candles": candles}, f)
    span = {"chan": "CRYPTO 1D", "from": "2000-01-01", "to": "2100-01-01"}
    combos = [dict(SCREEN, name="tl_screen", kind="trendline", **span), dict(BOT, name="tl_bot", kind="trendline", **span),
              dict(SCREEN, name="fib_screen", kind="fib", **span), dict(BOT, name="fib_bot", kind="fib", **span),
              dict(DEMO_FIB, name="fib_demo", kind="fib", **span)]
    (OUT / "combos.json").write_text(json.dumps(combos, indent=1))
    got = OUT / "retest.json"
    subprocess.run([sys.executable, retest, str(fx), str(OUT / "combos.json"), str(got)], check=True)
    rep = json.loads(got.read_text())
    fx.unlink()                                        # tens of MB of candles: not committed

    def rows(combo, keep=lambda r: True):
        return [(r, rep[combo][r["id"]]) for r in recs if r["id"] in rep[combo] and keep(r)]
    on16 = lambda r: r["symbol"] in TODAY_16
    dropped = lambda r: r["symbol"] not in TODAY_16
    touch = lambda r: not r.get("broken") and not r["key"].endswith("|br")
    text = [f"# Journal screens re-played - CRYPTO 1D, CoinDCX coins, {datetime.fromtimestamp(first, IST):%d %b} to "
            f"{datetime.fromtimestamp(now, IST):%d %b %Y %H:%M} IST", "",
            "Alerts: the journal's own set (rebuild before " + f"{datetime.fromtimestamp(cutoff, IST):%d %b %H:%M}"
            + " IST, live after; news-window rows out), crypto 1D on CoinDCX coins, fib L2-L4. "
            "Played by the journal's retest (tools/signals-retest.py) on Delta 15m; SL wick or body from Delta 1d. "
            "Max DD in alert order.", "",
            "Screen = his settings: SL shift +1R -> +0.5R, Trail TP +0.5R / 0.5R behind. "
            "Bot = live CoinDCX bot / demo exits: SL shift +1R -> +0.75R, Trail TP +0.25R / 0.5R behind. "
            "Both: exit 1.5R, SL wick or body 0.75%, till TP / SL, fees 0.0826%, stops slip 0.05%.", "",
            f"Coins with no Delta 15m candles: {', '.join(missing) or 'none'}.", ""]
    for kind, tag in (("trendline", "tl"), ("fib", "fib")):
        text += [f"## {kind.capitalize()}", "", f"Journal screen: {JOURNAL[kind]}", "", HEAD]
        text.append(line("Screen, 25 coins (his screen)", rows(f"{tag}_screen")))
        text.append(line("Screen, today's 16 coins", rows(f"{tag}_screen", on16)))
        text.append(line("Screen, 9 dropped coins", rows(f"{tag}_screen", dropped)))
        text.append(line("Bot exits, 25 coins", rows(f"{tag}_bot")))
        text.append(line("Bot exits, today's 16 coins (what the bot can trade)", rows(f"{tag}_bot", on16)))
        if kind == "trendline":
            for name, f in (("touch", touch), ("break", lambda r: not touch(r))):
                text.append(line(f"Screen, 16 coins, {name}", rows("tl_screen", lambda r, f=f: on16(r) and f(r))))
                text.append(line(f"Bot exits, 16 coins, {name}", rows("tl_bot", lambda r, f=f: on16(r) and f(r))))
        else:
            text.append(line("Demo rule (alert's SL, bot exits), 16 coins", rows("fib_demo", on16)))
            for lv in ("L2", "L3", "L4"):
                text.append(line(f"Screen, 16 coins, {lv}", rows("fib_screen", lambda r, lv=lv: on16(r) and level_of(r) == lv)))
        months = defaultdict(list)
        for r, x in rows(f"{tag}_screen", on16):
            months[datetime.fromtimestamp(r["sent_ts"], IST).strftime("%Y-%m")].append((r, x))
        text += ["", "By month (screen, 16 coins)", "", HEAD] + [line(m, months[m]) for m in sorted(months)]
        by_coin = defaultdict(list)
        for r, x in rows(f"{tag}_screen"):
            by_coin[r["symbol"]].append((r, x))
        text += ["", "By coin (screen, 25 coins; * = dropped 8 Nov)", "", HEAD]
        text += [line(s + ("" if s in TODAY_16 else " *"), by_coin[s])
                 for s in sorted(by_coin, key=lambda s: -stats(by_coin[s])["total"])]
        text.append("")
    (OUT / "SUMMARY.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print("\n".join(text))


if __name__ == "__main__":
    main(*sys.argv[1:4])
