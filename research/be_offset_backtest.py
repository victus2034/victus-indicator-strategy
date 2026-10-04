"""Research only - nothing here is imported by the live scanners.

Breakeven offset backtest (2026-10-04). Since the audit, a BE exit pays the
same 0.05% stop slippage as an SL, so the current offset (1.129 x fees)
clears fees but not fees plus slip and a BE exit nets about zero. This
re-runs every recorded zone alert under several offsets with the production
simulator (same candles, same rules, only the offset changes) to show what a
wider offset would have done.

    python research/be_offset_backtest.py     # writes research/out/be_offset/
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[1]))

import backtest_audit as audit  # noqa: E402
import daily_backtest_summary as dbs  # noqa: E402

NSE_COST = dbs.ROUND_TRIP_COST_PCT
CRYPTO_COST = dbs.CRYPTO_ROUND_TRIP_COST_PCT
SLIP = dbs.SL_FILL_SLIPPAGE_PCT
# name -> (nse offset %, crypto offset %, breakeven on)
VARIANTS = {
    "no BE": (0.0, 0.0, False),
    "entry (0%)": (0.0, 0.0, True),
    "current (1.129 x fees)": (dbs.BREAK_EVEN_OFFSET_PCT, dbs.CRYPTO_BREAK_EVEN_OFFSET_PCT, True),
    "fees + slip": (round(NSE_COST + SLIP, 4), round(CRYPTO_COST + SLIP, 4), True),
    "1.129 x (fees + slip)": (round((NSE_COST + SLIP) * 1.129, 4), round((CRYPTO_COST + SLIP) * 1.129, 4), True),
    "2 x (fees + slip)": (round((NSE_COST + SLIP) * 2, 4), round((CRYPTO_COST + SLIP) * 2, 4), True),
}
FILLED = audit.FILLED


def run_variant(sub, frames, market, nse_off, crypto_off, enabled):
    dbs.BREAK_EVEN_OFFSET_PCT = nse_off
    dbs.CRYPTO_BREAK_EVEN_OFFSET_PCT = crypto_off
    dbs.BREAK_EVEN_ENABLED = enabled
    rows = dbs.simulate_alerts(sub, frames, market)
    amb = pd.DataFrame([r for r in rows if r.get("final_result") == dbs.DATA_QUALITY_AMBIGUOUS])
    if not amb.empty:
        fine, _ = dbs.fetch_resolution_frames(
            sorted(amb["symbol"].unique()), market, windows=dbs.resolution_windows(amb))
        rows = dbs.rerun_ambiguous(sub, rows, frames, market, fine)
    results, _ = dbs.apply_same_day_zone_cooldown(pd.DataFrame(rows), market)
    return results


def main() -> None:
    out = Path("research/out/be_offset")
    out.mkdir(parents=True, exist_ok=True)
    stored = {r["trade_id"]: r for r in dbs.read_jsonl(Path("daily_backtest_finalized_records.jsonl"))}
    by_key = {(r.get("zone_id"), str(r.get("alert_time"))[:26]): r["trade_id"] for r in stored.values()}
    stats = defaultdict(lambda: defaultdict(float))  # (variant, group) -> counters
    groups = set()

    for (file_market, tf), name in audit.ALERT_FILES.items():
        alerts = dbs.load_records(Path(name), tf)
        if alerts.empty:
            continue
        alerts["trade_id"] = [
            by_key.get((z, t.isoformat()[:26]), tid)
            for z, t, tid in zip(alerts["zone_id"], alerts["event_time_ist"], alerts["trade_id"])
        ]
        alerts = alerts[alerts["trade_id"].astype(str).isin(stored)].copy()
        for market in audit.MARKETS_IN_FILE[file_market]:
            sub = alerts[alerts["market_class"] == market.upper()].copy().reset_index(drop=True)
            if sub.empty:
                continue
            start = int(sub["event_time"].min().timestamp()) - 3 * 3600
            end = int(sub["event_time"].max().timestamp()) + 40 * 3600
            if market != "nse":
                dbs.configure_crypto_data(tf)
            frames = audit.fetch_frames(market if market == "nse" else "crypto",
                                        sorted(sub["symbol"].unique()), start, end)
            sub = sub[sub["symbol"].isin(frames)].reset_index(drop=True)
            group = f"{market.upper()} {tf}"
            groups.add(group)
            print(f"{group}: {len(sub)} alerts")
            for variant, (nse_off, crypto_off, enabled) in VARIANTS.items():
                res = run_variant(sub, frames, market, nse_off, crypto_off, enabled)
                for row in res.to_dict("records"):
                    result = row.get("final_result")
                    net = row.get("net_realized_r")
                    if not row.get("filled") or result not in FILLED or net is None or pd.isna(net):
                        continue
                    for key in ((variant, group), (variant, "ALL"),
                                (variant, "CRYPTO+X+OTHER" if market != "nse" else "NSE")):
                        s = stats[key]
                        s["n"] += 1
                        s["net"] += net
                        s[result] += 1
                        if result == "BE":
                            s["be_net"] += net
                        if net > 0:
                            s["wins"] += 1

    order = sorted(groups) + ["NSE", "CRYPTO+X+OTHER", "ALL"]
    lines = ["# Breakeven offset backtest", "",
             f"Same recorded alerts, same candles, production simulator; only the BE offset changes. "
             f"Fees: NSE {NSE_COST}%, crypto {CRYPTO_COST}%. Stop slip {SLIP}% on SL and BE exits.", "",
             "| variant | NSE offset % | crypto offset % |", "|---|---|---|"]
    lines += [f"| {v} | {a if e else '-'} | {b if e else '-'} |" for v, (a, b, e) in VARIANTS.items()]
    for group in order:
        lines += ["", f"## {group}", "",
                  "| variant | trades | net R | avg R | win % | SL | BE | BE avg R | +1R | +2R | Neither |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for variant in VARIANTS:
            s = stats[(variant, group)]
            n = int(s["n"])
            if not n:
                continue
            be = int(s["BE"])
            lines.append(
                f"| {variant} | {n} | {s['net']:+.1f} | {s['net'] / n:+.3f} | {100 * s['wins'] / n:.1f} | "
                f"{int(s['SL'])} | {be} | {(s['be_net'] / be if be else 0):+.3f} | {int(s['+1R'])} | "
                f"{int(s['+2R'])} | {int(s['Neither'])} |")
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
