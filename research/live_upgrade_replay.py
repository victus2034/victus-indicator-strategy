"""Live bot upgrade replay (lakky, 2026-11-22, decision card "Breaks only + own SL + kill fix").

Reads the bot's own-rules replay of every 1D crypto trendline alert, Jan 2025 - 13 Nov 2026
(research/out/journal_tl_setup/trades_2025-01-01.json, made by journal_tl_setup_backtest.py on
Bitunix 15m candles: exit 1.5R, SL shift +1R -> +0.75R, trail +0.25R / 0.5R behind, fees and stop
slip in), and runs it through coindcx_live.py's account rules: one trade per coin, at most
COINDCX_LIVE_MAX_OPEN open, and a kill switch.

    python research/live_upgrade_replay.py          # -> research/out/live_upgrade/SUMMARY.md

Offline: no candles fetched. R is per trade at the bot's fixed risk (1R = COINDCX_LIVE_RISK).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

SOURCE = ROOT / "research/out/journal_tl_setup/trades_2025-01-01.json"
OUT = ROOT / "research/out/live_upgrade"
DAY = 86400
# the 16 crypto coins of the replay (13 Nov watchlist); xStocks / XAUT / SLVON left out like the bot
CRYPTO = set("1000PEPEUSD ADAUSD BNBUSD BTCUSD DOGEUSD ENAUSD ETHUSD HYPEUSD LINKUSD NEARUSD "
             "SOLUSD SUIUSD UNIUSD WLDUSD XRPUSD ZECUSD".split())


def load(path=SOURCE):
    rows = [t for t in json.loads(path.read_text()) if t["symbol"] in CRYPTO]
    wick = [t for t in rows if t.get("r") is not None and not t.get("news")]
    alert = []
    for t in rows:
        own = t.get("own") or {}
        if t["level"] == "BR" and own.get("r") is not None and not own.get("news"):
            alert.append({**t, **{k: own[k] for k in ("r", "risk_pct", "outcome", "fill_ts", "exit_ts", "best_r")}})
    return wick, alert


def account(trades, max_open=5, max_dd_r=None, max_loss_r=None, day_loss_r=None):
    """The bot's rules over trades in fill order: (taken, skipped, date the kill switch tripped)."""
    taken, skipped, killed, active = [], 0, None, []
    for t in sorted(trades, key=lambda t: t["fill_ts"]):
        now = t["fill_ts"]
        active = [o for o in active if o["exit_ts"] > now]
        closed = sorted((o for o in taken if o["exit_ts"] <= now), key=lambda o: o["exit_ts"])
        equity = peak = 0.0
        for o in closed:
            equity += o["r"]
            peak = max(peak, equity)
        stop = ((max_dd_r and peak - equity >= max_dd_r) or (max_loss_r and equity <= -max_loss_r))
        if stop and killed is None:
            killed = now
        if killed is not None:
            skipped += 1
            continue
        if day_loss_r and -sum(o["r"] for o in closed if o["exit_ts"] > now - DAY) >= day_loss_r:
            skipped += 1
            continue
        if len(active) >= max_open or any(o["symbol"] == t["symbol"] for o in active):
            skipped += 1
            continue
        active.append(t)
        taken.append(t)
    return taken, skipped, killed


def stats(taken):
    n = len(taken)
    total = sum(t["r"] for t in taken)
    wins = sum(t["r"] > 0 for t in taken)
    gain = sum(t["r"] for t in taken if t["r"] > 0)
    loss = -sum(t["r"] for t in taken if t["r"] < 0)
    equity = peak = dd = 0.0
    run = worst = 0
    for t in sorted(taken, key=lambda t: t["exit_ts"]):
        equity += t["r"]
        peak = max(peak, equity)
        dd = min(dd, equity - peak)
        run = run + 1 if t["r"] < 0 else 0
        worst = max(worst, run)
    months = {}
    for t in taken:
        key = datetime.fromtimestamp(t["fill_ts"], timezone.utc).strftime("%Y-%m")
        months[key] = months.get(key, 0.0) + t["r"]
    return {"n": n, "total": total, "avg": total / n if n else 0.0, "win": wins / n * 100 if n else 0.0,
            "pf": gain / loss if loss else float("inf"), "dd": dd, "worst_run": worst,
            "months_up": sum(v > 0 for v in months.values()), "months": len(months),
            "avg_sl": sum(t["risk_pct"] for t in taken) / n if n else 0.0}


HEAD = ("| Set | Taken | Skipped | Win | Total R | R/trade | PF | Max DD | Worst run | Months up | Avg SL | Kill switch |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|")


def row(name, trades, **rules):
    taken, skipped, killed = account(trades, **rules)
    s = stats(taken)
    kill = datetime.fromtimestamp(killed, timezone.utc).strftime("%Y-%m-%d") if killed else "never"
    return (f"| {name} | {s['n']} | {skipped} | {s['win']:.0f}% | {s['total']:+.1f}R | {s['avg']:+.3f}R | {s['pf']:.2f} | "
            f"{s['dd']:+.1f}R | {s['worst_run']} | {s['months_up']}/{s['months']} | {s['avg_sl']:.1f}% | {kill} |"), s


def main():
    wick, alert = load()
    breaks = [t for t in wick if t["level"] == "BR"]
    cap = config.COINDCX_LIVE_MAX_OPEN
    lines = ["# Live bot upgrade replay - breaks only, break stop, kill switch", "",
             f"Source: `{SOURCE.relative_to(ROOT)}` (bot's exits, 16 crypto, 1 Jan 2025 - 13 Nov 2026, fees + stop slip, "
             "fills within 15 min of CPI / PPI / FOMC left out). Account rules as `coindcx_live.py`: one trade per coin, "
             f"at most {cap} open. R per trade at the fixed risk.", "", "## The changes", "", HEAD]
    dd = config.COINDCX_LIVE_MAX_DRAWDOWN_R
    rows = [
        ("Before: touch + break, 10R loss from start", wick, {"max_loss_r": 10}),
        ("Before, no kill switch", wick, {}),
        ("Breaks only, wick/body SL (default)", breaks, {}),
        ("Breaks only, alert's own SL (BREAK_SL=alert)", alert, {}),
        (f"Default + kill switch {dd:g}R from the best point", breaks, {"max_dd_r": dd}),
        (f"Alert SL + kill switch {dd:g}R from the best point", alert, {"max_dd_r": dd}),
    ]
    for name, trades, rules in rows:
        lines.append(row(name, trades, max_open=cap, **rules)[0])
    lines += ["", "Why the alert's SL is not the default: it is better a trade, but its stops are wider, so trades "
              f"last longer and hold the {cap} slots; fewer breaks get in and the total is lower.", "",
              "## Max open trades (breaks only)", "", HEAD]
    for name, trades in (("wick/body", breaks), ("alert SL", alert)):
        for n in (5, 8, 10, 99):
            lines.append(row(f"{name}, at most {n} open" if n < 99 else f"{name}, no limit (one per coin)", trades,
                             max_open=n)[0])
    lines += ["", "## Kill switch variants (breaks only)", "", HEAD]
    for label, trades in (("wick/body", breaks), ("alert SL", alert)):
        for name, rules in [("10R loss from start (old rule)", {"max_loss_r": 10}),
                            ("10R from the best point", {"max_dd_r": 10}),
                            ("15R from the best point", {"max_dd_r": 15}),
                            ("15R + no new trade after 2R lost in 24h", {"max_dd_r": 15, "day_loss_r": 2}),
                            ("15R + no new trade after 3R lost in 24h", {"max_dd_r": 15, "day_loss_r": 3})]:
            lines.append(row(f"{label}, {name}", trades, max_open=cap, **rules)[0])
    lines += ["", "A 24h loss cap is not used: 2R helps the alert SL and hurts wick/body, 3R moves under 1R - noise."]
    cut = datetime(2025, 12, 1, tzinfo=timezone.utc).timestamp()
    for title, src in (("Robustness (breaks only, wick/body SL - default)", breaks),
                       ("Robustness (breaks only, alert's own SL)", alert)):
        lines += ["", f"## {title}", "", HEAD]
        for name, trades in [("Jan - Nov 2025", [t for t in src if t["fill_ts"] < cut]),
                             ("Dec 2025 - Nov 2026", [t for t in src if t["fill_ts"] >= cut]),
                             ("Buy breaks (RS TL BR)", [t for t in src if t["side"] == "long"]),
                             ("Sell breaks (SP TL BR)", [t for t in src if t["side"] == "short"])]:
            lines.append(row(name, trades, max_open=cap)[0])
    OUT.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    (OUT / "SUMMARY.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
