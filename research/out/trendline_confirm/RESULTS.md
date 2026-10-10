# Trendline confirm-window fix: quick backtest, alerts since 2026-09-01

old = closes before the line is drawn not checked (v12.7.8); new = v12.7.9. Trendlines only.

| market | tf | rule | alerts | filled | win@2R | net R | R/trade |
|---|---|---|---|---|---|---|---|
| crypto | 4h | old | 700 | 521 | 26% | -128.9 | -0.249 |
| crypto | 4h | new | 668 | 494 | 26% | -124.3 | -0.254 |
| crypto | 1d | old | 79 | 69 | 23% | -23.1 | -0.334 |
| crypto | 1d | new | 79 | 69 | 23% | -23.1 | -0.334 |
| crypto | 1w | old | 2 | 2 | 100% | +2.0 | +0.976 |
| crypto | 1w | new | 2 | 2 | 100% | +2.0 | +0.976 |
| crypto | 1M | old | 0 | 0 | 0% | +0.0 | +0.000 |
| crypto | 1M | new | 0 | 0 | 0% | +0.0 | +0.000 |
| crypto | all | old | 781 | 592 | 26% | -150.0 | -0.255 |
| crypto | all | new | 749 | 565 | 25% | -145.4 | -0.259 |
| nse | 4h | old | 1214 | 957 | 21% | -355.0 | -0.375 |
| nse | 4h | new | 1179 | 931 | 20% | -360.8 | -0.392 |
| nse | 1d | old | 678 | 577 | 25% | -125.4 | -0.221 |
| nse | 1d | new | 664 | 565 | 25% | -123.8 | -0.223 |
| nse | 1w | old | 107 | 88 | 22% | -24.7 | -0.317 |
| nse | 1w | new | 103 | 85 | 22% | -24.7 | -0.325 |
| nse | 1M | old | 8 | 8 | 33% | -0.3 | -0.041 |
| nse | 1M | new | 8 | 8 | 33% | -0.3 | -0.041 |
| nse | all | old | 2007 | 1630 | 22% | -505.4 | -0.316 |
| nse | all | new | 1954 | 1589 | 22% | -509.7 | -0.327 |

## Lines drawn already broken (all history, live timeframes)

| market | lines | drawn broken | share |
|---|---|---|---|
| crypto | 6470 | 723 | 11.2% |
| nse | 58138 | 5049 | 8.7% |
