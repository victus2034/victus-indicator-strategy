# Fib + trendline: Delta vs Bitunix candles

Live timeframes 4h, 1d, 1w, 1M; 23 crypto symbols; each timeframe cut to the window both venues cover (plus 60 bars of warm-up). 'random' is the no-edge control. Fees: Delta.

| source                      | kind      | tf   |   alerts |   filled |   win_1r |   net_R_at_2R |   R_per_trade_2R |   net_R_at_1R |
|:----------------------------|:----------|:-----|---------:|---------:|---------:|--------------:|-----------------:|--------------:|
| bitunix (graded on bitunix) | fib       | 1d   |      268 |      236 |    0.369 |       -30.300 |           -0.128 |       -65.700 |
| bitunix (graded on delta)   | fib       | 1d   |      268 |      237 |    0.377 |       -35.300 |           -0.149 |       -63.800 |
| delta (graded on delta)     | fib       | 1d   |      344 |      310 |    0.323 |       -84.400 |           -0.272 |      -112.000 |
| bitunix (graded on bitunix) | fib       | 1w   |       31 |       27 |    0.417 |        -2.800 |           -0.105 |        -4.900 |
| bitunix (graded on delta)   | fib       | 1w   |       31 |       27 |    0.417 |        -2.800 |           -0.105 |        -4.900 |
| delta (graded on delta)     | fib       | 1w   |       39 |       35 |    0.419 |        -5.200 |           -0.150 |        -6.200 |
| bitunix (graded on bitunix) | fib       | 4h   |     1372 |     1102 |    0.378 |      -282.000 |           -0.256 |      -364.600 |
| bitunix (graded on delta)   | fib       | 4h   |     1372 |     1094 |    0.386 |      -259.400 |           -0.237 |      -348.100 |
| delta (graded on delta)     | fib       | 4h   |     1416 |     1133 |    0.373 |      -296.600 |           -0.262 |      -381.300 |
| bitunix (graded on bitunix) | random    | 1d   |     1270 |     1228 |    0.394 |      -160.400 |           -0.131 |      -314.400 |
| bitunix (graded on delta)   | random    | 1d   |     1270 |     1220 |    0.383 |      -164.700 |           -0.135 |      -338.200 |
| delta (graded on delta)     | random    | 1d   |     1824 |     1752 |    0.381 |      -279.100 |           -0.159 |      -485.600 |
| bitunix (graded on bitunix) | random    | 1w   |      280 |      274 |    0.371 |       -30.500 |           -0.111 |       -78.000 |
| bitunix (graded on delta)   | random    | 1w   |      280 |      274 |    0.380 |       -23.600 |           -0.086 |       -74.000 |
| delta (graded on delta)     | random    | 1w   |      534 |      521 |    0.376 |       -56.900 |           -0.109 |      -143.800 |
| bitunix (graded on bitunix) | random    | 4h   |     1652 |     1507 |    0.411 |      -255.800 |           -0.170 |      -370.500 |
| bitunix (graded on delta)   | random    | 4h   |     1652 |     1486 |    0.389 |      -320.800 |           -0.216 |      -426.100 |
| delta (graded on delta)     | random    | 4h   |     2235 |     2023 |    0.380 |      -454.200 |           -0.224 |      -617.800 |
| bitunix (graded on bitunix) | trendline | 1d   |     1166 |     1034 |    0.315 |      -364.100 |           -0.352 |      -410.300 |
| bitunix (graded on delta)   | trendline | 1d   |     1166 |     1027 |    0.309 |      -361.600 |           -0.352 |      -416.900 |
| delta (graded on delta)     | trendline | 1d   |     1057 |      933 |    0.322 |      -311.800 |           -0.334 |      -359.000 |
| bitunix (graded on bitunix) | trendline | 1w   |       86 |       75 |    0.356 |        -6.300 |           -0.084 |       -24.400 |
| bitunix (graded on delta)   | trendline | 1w   |       86 |       75 |    0.342 |       -11.300 |           -0.151 |       -26.400 |
| delta (graded on delta)     | trendline | 1w   |       48 |       45 |    0.273 |       -16.000 |           -0.357 |       -22.100 |
| bitunix (graded on bitunix) | trendline | 4h   |     7471 |     5807 |    0.385 |     -1471.200 |           -0.253 |     -1658.700 |
| bitunix (graded on delta)   | trendline | 4h   |     7471 |     5742 |    0.376 |     -1471.900 |           -0.256 |     -1734.400 |
| delta (graded on delta)     | trendline | 4h   |     7328 |     5716 |    0.374 |     -1530.300 |           -0.268 |     -1746.400 |
