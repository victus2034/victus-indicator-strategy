# Trendline anchor backtest (trendlines only, length 10)

oldest = live Pine rule; nearest = join the last valid earlier swing; tangent = only a rising low / falling high vs the previous swing, anchored on the candle the line hugs; last_lower = the same from the most recent earlier swing below (above) the new one, not only the previous swing. Same data, trade rules and scoring as `trendline_length_backtest.py`.

| market | tf | anchor | alerts | /day | filled | win@2R | net R | R/trade |
|---|---|---|---|---|---|---|---|---|
| crypto | 4h | tangent | 4582 | 4.7 | 3562 | 23% | -1114.0 | -0.313 |
| crypto | 4h | last_lower | 8026 | 8.2 | 6240 | 23% | -1931.1 | -0.310 |
| crypto | 1d | tangent | 746 | 0.8 | 675 | 20% | -259.9 | -0.385 |
| crypto | 1d | last_lower | 1143 | 1.2 | 1036 | 20% | -394.2 | -0.381 |
| crypto | 1w | tangent | 29 | 0.1 | 27 | 24% | -8.2 | -0.305 |
| crypto | 1w | last_lower | 48 | 0.1 | 45 | 20% | -18.0 | -0.401 |
| crypto | 1M | tangent | 0 | 0.0 | 0 | 0% | +0.0 | +0.000 |
| crypto | 1M | last_lower | 0 | 0.0 | 0 | 0% | +0.0 | +0.000 |
| crypto | all | tangent | 5357 | 5.5 | 4264 | 22% | -1382.1 | -0.324 |
| crypto | all | last_lower | 9217 | 9.4 | 7321 | 23% | -2343.4 | -0.320 |
| nse | 4h | tangent | 9313 | 14.0 | 7297 | 24% | -2219.5 | -0.304 |
| nse | 4h | last_lower | 15742 | 23.6 | 12186 | 23% | -3850.9 | -0.316 |
| nse | 1d | tangent | 5649 | 8.1 | 4668 | 24% | -1107.4 | -0.238 |
| nse | 1d | last_lower | 9876 | 14.2 | 8176 | 24% | -2021.3 | -0.248 |
| nse | 1w | tangent | 6767 | 0.6 | 5953 | 22% | -1853.1 | -0.311 |
| nse | 1w | last_lower | 10264 | 1.0 | 9042 | 22% | -2787.5 | -0.309 |
| nse | 1M | tangent | 736 | 0.1 | 685 | 22% | -192.7 | -0.281 |
| nse | 1M | last_lower | 940 | 0.1 | 877 | 23% | -239.9 | -0.274 |
| nse | all | tangent | 22465 | 2.1 | 18603 | 23% | -5372.8 | -0.289 |
| nse | all | last_lower | 36822 | 3.4 | 30281 | 23% | -8899.6 | -0.294 |

## Total, live timeframes, both markets

| anchor | alerts | filled | net R | R/trade |
|---|---|---|---|---|
| tangent | 27822 | 22867 | -6754.8 | -0.296 |
| last_lower | 46039 | 37602 | -11243.0 | -0.299 |
