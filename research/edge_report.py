"""Research only: net-R breakdown of recorded zone trades (idea 5).

Reads daily_backtest_finalized_records.jsonl (and research/out/trades.csv when
present, for trend and exit columns) and writes a markdown report. Posts
nothing. Buckets with fewer than MIN_N trades are marked thin.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

MIN_N = 30


def table(frame: pd.DataFrame, by, r_col="net_realized_r") -> str:
    g = frame.groupby(by, observed=True)[r_col]
    out = pd.DataFrame({
        "trades": g.size(),
        "net R": g.sum().round(1),
        "avg R": g.mean().round(3),
        "win %": g.apply(lambda s: round((s > 0.1).mean() * 100)),
    })
    out["note"] = ["thin" if n < MIN_N else "" for n in out["trades"]]
    return out.to_markdown()


def build(records: Path) -> str:
    d = pd.read_json(records, lines=True)
    f = d[d["filled"] == True].copy()  # noqa: E712
    f["stop %"] = pd.cut((f["entry_price"] - f["stop_price"]).abs() / f["entry_price"] * 100,
                         [0, 0.3, 0.5, 0.8, 1.5, 100],
                         labels=["<0.3%", "0.3-0.5%", "0.5-0.8%", "0.8-1.5%", ">1.5%"])
    f["touches"] = pd.cut(f["touch_count"].fillna(-1), [-2, -0.5, 0.5, 1.5, 3.5, 1e9],
                          labels=["unknown", "0", "1", "2-3", "4+"])
    f["hour IST"] = pd.to_datetime(f["alert_time"], utc=True, format="ISO8601").dt.tz_convert("Asia/Kolkata").dt.hour
    f["weekday"] = pd.to_datetime(f["date"]).dt.day_name().str[:3]
    f["rating"] = pd.cut(f["rating"], [-1, 4, 6, 8, 10], labels=["0-4", "5-6", "7-8", "9-10"])
    f["week"] = pd.to_datetime(f["date"]).dt.to_period("W").astype(str)
    parts = [
        f"# Edge report (research)\n\n{len(f)} filled trades, {f['date'].min():%Y-%m-%d} to {f['date'].max():%Y-%m-%d}. "
        "R is net of fees, as the daily report scores it. 'thin' = under 30 trades.\n",
        "## Market x timeframe x side\n" + table(f, ["market", "timeframe", "side"]),
        "## Stop size\n" + table(f, ["market", "stop %"]),
        "## Touch count\n" + table(f, ["market", "touches"]),
        "## Rating\n" + table(f, ["market", "rating"]),
        "## Alert hour (IST)\n" + table(f, ["market", "hour IST"]),
        "## Weekday\n" + table(f, ["market", "weekday"]),
        "## Week\n" + table(f, ["week", "market"]),
    ]
    return "\n\n".join(parts) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", default="daily_backtest_finalized_records.jsonl")
    parser.add_argument("--out", default="research/out/EDGE_REPORT.md")
    args = parser.parse_args(argv)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(build(Path(args.records)))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
