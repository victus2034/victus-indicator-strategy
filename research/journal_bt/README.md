# Journal Signals backtest, every filter crossed (lakky, 2026-11-09)

Runs the journal's own Signals code (`index.html` of victus2034/journal) on every crypto fib and
trendline alert from 1 Jan 2026, for every "How each trade is played" rule set (5,697), and
splits the results by every filter (channel, coins, BTC day, level / type, fees).

Inputs: `research/out/journal_bt/` (part `journal-bt` of `bitunix_research.yml`): the 1 Jan
rebuild (`fibtl_rebuild_*`, crypto only) and Delta candles (`candles/`, end = the replay's "now").

| Step | Command | Output |
|---|---|---|
| 1. Score in the app | `node harness.mjs --app ../journal --data research/out/journal_bt --candles research/out/journal_bt/candles --now 1794204240 --out RUN [--walk fine]` | `RUN/alerts.json`, `rules.json`, `r.f32` (R per rule x alert, fees in, NaN = no result) |
| 2. Fib scanner rule (optional) | `python rebook.py` (reads `fine/`, writes `real/`) | the fib "Scanner" exit booked as the scanner books it: 2R + BE |
| 3. Grid | `python aggregate.py RUN RUN/agg` | one CSV.gz per kind and Exit at: every channel x coins x BTC day x level/type x rule set x fees |
| 4. Ranking | `python report.py RUN/agg RUN/rep` | `summary.json`, top / bottom CSVs |
| Report tables | `keycells.py RUN`, `matrix.py RUN`, `filters.py`, `scanbook.py`, `finecmp.py` | JSON beside the run |

`--walk app` reads candles the way the app does (one page of at most 1,900 per alert, so old
alerts get 1h-1d candles); `--walk fine` walks every alert on 15m candles.

Checks: `pycheck.py` (plain-Python re-score of 600 alerts x 4 rule sets, 0 differences) and
`ui_check.mjs` + `combos.json` + `ui_compare.py` (the Signals tab on screen vs the grid, 7
combos, 0 mismatches). `btcprev.py`: the BTC-day split by the previous day's candle.
`fixcmp.py`: the journal after its fix (journal#93, v.179; run step 1 again into `fixed/` on that
build) against the app's old grid and the 15m grid with the scanner's fib booking.

Findings (journal side, fixed in journal#93, v.179): the Signals "Scanner" exit books a fib trade that
reached +1R and came back to breakeven as +1R (fib all +17.7R vs -281.2R on the scanner's own
2R + BE), and tight Trail TP rules on old alerts read better on coarse candles than on 15m
(RS TL BR 3R + trail +273R vs +165R).

After the fix (`fixcmp.py`): fib Scanner -281.2R, the scanner's own booking; alert x rule results that
differ from the 15m grid 6.59% -> 0.12% (trades still open after ~18 days walk their tail on coarser
candles); RS TL BR 3R + trail 273.1R -> 167.9R (164.9R on 15m).
