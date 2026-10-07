"""Dump one crypto symbol's candles from the alert feed and list the trendlines
trendlines.py (Pine 6b) holds on them, so a chart screenshot can be checked line
by line. The candles go to research/out/trendline_trace/<pair>_<tf>.json.

Research only. Lakky, 2026-10-07: HYPEUSDT.P 1D on Bitunix, "wrong trendline".

    python research/trendline_crypto_trace.py HYPEUSD --tf 1d
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from fib_trendline_data import crypto_charts  # noqa: E402
from trendlines import SUPPORT, build_trendlines  # noqa: E402

OUT = Path(__file__).resolve().parent / "out" / "trendline_trace"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("contract")
    p.add_argument("--tf", default="1d")
    p.add_argument("--source", default="bitunix")
    a = p.parse_args()
    rows = crypto_charts(a.contract, [a.tf], int(time.time()), source=a.source)[a.tf]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{a.contract}_{a.tf}_{a.source}.json").write_text(json.dumps(rows))
    t = [datetime.fromtimestamp(r[0], timezone.utc).strftime("%y-%m-%d %H:%M") for r in rows]
    H = [r[2] for r in rows]; Lo = [r[3] for r in rows]; C = [r[4] for r in rows]
    print(f"{a.contract} {a.tf} {a.source}: {len(rows)} bars {t[0]} -> {t[-1]}")
    for ln in build_trendlines(H, Lo, C, config.TRENDLINE_SWING_LENGTH, config.TRENDLINES_KEEP, history=True):
        kind = "SUP" if ln.kind == SUPPORT else "RES"
        state = "live" if ln.alive else f"broken {t[ln.broken_at]}"
        print(f"  {kind} {ln.y1:.4f} ({t[ln.x1]}) -> {ln.y2:.4f} ({t[ln.x2]}) {state}"
              f"{'' if ln.trimmed_at is None else ' trimmed ' + t[ln.trimmed_at]}")


if __name__ == "__main__":
    main()
