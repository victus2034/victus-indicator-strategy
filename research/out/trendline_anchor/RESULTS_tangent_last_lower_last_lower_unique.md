# Trendline anchor backtest (trendlines only, length 10)

oldest = live Pine rule; nearest = join the last valid earlier swing; tangent = only a rising low / falling high vs the previous swing, anchored on the candle the line hugs; last_lower = the same from the most recent earlier swing below (above) the new one, not only the previous swing; _unique = and a new line replaces an older one from the same candle. Same data, trade rules and scoring as `trendline_length_backtest.py`.

| market | tf | anchor | alerts | /day | filled | win@2R | net R | R/trade |
|---|---|---|---|---|---|---|---|---|
| crypto | 4h | tangent | 4582 | 4.7 | 3562 | 23% | -1112.0 | -0.312 |
| crypto | 4h | last_lower | 8026 | 8.2 | 6240 | 23% | -1927.3 | -0.309 |
| crypto | 4h | last_lower_unique | 8118 | 8.3 | 6319 | 23% | -1930.0 | -0.306 |
| crypto | 1d | tangent | 746 | 0.8 | 675 | 20% | -259.9 | -0.385 |
| crypto | 1d | last_lower | 1143 | 1.2 | 1036 | 20% | -394.2 | -0.381 |
| crypto | 1d | last_lower_unique | 1143 | 1.2 | 1037 | 20% | -390.2 | -0.377 |
| crypto | 1w | tangent | 29 | 0.1 | 27 | 24% | -8.2 | -0.305 |
| crypto | 1w | last_lower | 48 | 0.1 | 45 | 20% | -18.0 | -0.401 |
| crypto | 1w | last_lower_unique | 44 | 0.1 | 41 | 19% | -17.9 | -0.436 |
| crypto | 1M | tangent | 0 | 0.0 | 0 | 0% | +0.0 | +0.000 |
| crypto | 1M | last_lower | 0 | 0.0 | 0 | 0% | +0.0 | +0.000 |
| crypto | 1M | last_lower_unique | 0 | 0.0 | 0 | 0% | +0.0 | +0.000 |
| crypto | all | tangent | 5357 | 5.5 | 4264 | 22% | -1380.1 | -0.324 |
| crypto | all | last_lower | 9217 | 9.4 | 7321 | 23% | -2339.6 | -0.320 |
| crypto | all | last_lower_unique | 9305 | 9.5 | 7397 | 23% | -2338.1 | -0.316 |
| nse | 4h | tangent | 9464 | 14.2 | 7395 | 24% | -2286.9 | -0.309 |
| nse | 4h | last_lower | 15967 | 23.9 | 12342 | 23% | -3969.5 | -0.322 |
| nse | 4h | last_lower_unique | 16027 | 24.0 | 12392 | 23% | -3981.6 | -0.321 |
| nse | 1d | tangent | 5742 | 8.3 | 4750 | 25% | -1115.7 | -0.235 |
| nse | 1d | last_lower | 10042 | 14.4 | 8329 | 24% | -2046.7 | -0.246 |
| nse | 1d | last_lower_unique | 10224 | 14.7 | 8488 | 24% | -2085.5 | -0.246 |
| nse | 1w | tangent | 6824 | 0.6 | 6004 | 22% | -1871.5 | -0.312 |
| nse | 1w | last_lower | 10363 | 1.0 | 9133 | 22% | -2823.7 | -0.309 |
| nse | 1w | last_lower_unique | 10417 | 1.0 | 9189 | 22% | -2840.7 | -0.309 |
| nse | 1M | tangent | 736 | 0.1 | 685 | 22% | -192.7 | -0.281 |
| nse | 1M | last_lower | 940 | 0.1 | 877 | 23% | -239.9 | -0.274 |
| nse | 1M | last_lower_unique | 936 | 0.1 | 874 | 23% | -241.9 | -0.277 |
| nse | all | tangent | 22766 | 2.1 | 18834 | 23% | -5466.8 | -0.290 |
| nse | all | last_lower | 37312 | 3.5 | 30681 | 23% | -9079.8 | -0.296 |
| nse | all | last_lower_unique | 37604 | 3.5 | 30943 | 23% | -9149.7 | -0.296 |

## Total, live timeframes, both markets

| anchor | alerts | filled | net R | R/trade |
|---|---|---|---|---|
| tangent | 28123 | 23098 | -6846.9 | -0.297 |
| last_lower | 46529 | 38002 | -11419.3 | -0.301 |
| last_lower_unique | 46909 | 38340 | -11487.8 | -0.300 |
