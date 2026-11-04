"""Research only: print each NIFTY day's high/low (5m, IST) and what the daily-fib breakout rule does, Oct 27 on."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fib_trendline_data as fdata  # noqa: E402
from daily_fib_backtest import by_day  # noqa: E402
from daily_fib_breakout_backtest import fib_boxes, run_side  # noqa: E402
from fib_trendline_data import IST  # noqa: E402

candles = fdata.nse_download(["^NSEI"], "5m").get("^NSEI", [])
days = list(by_day(candles, IST).items())
for (pd_, pb), (d, b) in zip(days, days[1:]):
    if str(d) < "2026-10-27":
        continue
    ph, pl = max(x[2] for x in pb), min(x[3] for x in pb)
    hi, lo = max(x[2] for x in b), min(x[3] for x in b)
    hit = lambda f: datetime.fromtimestamp(f, IST).strftime("%H:%M")  # noqa: E731
    print(f"{d}: open {b[0][1]:.2f} high {hi:.2f} ({hit(max(b, key=lambda x: x[2])[0])}) low {lo:.2f} "
          f"({hit(min(b, key=lambda x: x[3])[0])}) close {b[-1][4]:.2f} | prev {pd_} high {ph:.2f} low {pl:.2f} | "
          f"broke up: {hi > ph}, broke down: {lo < pl}")
    for side in ("buy", "sell"):
        ext = hi if side == "buy" else lo
        if (side == "buy" and hi > ph) or (side == "sell" and lo < pl):
            print("   ", side, "boxes at day extreme:", [(n, round(e, 2), round(s, 2)) for n, e, s in
                                                       fib_boxes(side, pl if side == "buy" else ph, ext, "near")])
            for t in run_side(side, ph, pl, b, "near", "high", 0):
                print("    trade", t["box"], round(t["entry"], 2), "sl", round(t["stop"], 2), "tp", round(t["target"], 2),
                      hit(t["fill_ts"]), t["outcome"], round(t["exit"], 2))
