# Fib + trendline: Delta vs Bitunix candles

Live timeframes 4h, 1d, 1w, 1M; 23 crypto symbols; each timeframe cut to the window both venues cover (plus 60 bars of warm-up). 'random' is the no-edge control. Fees: Delta.

| source   | kind      | tf   |   alerts |   filled |   win_1r |   net_R_at_2R |   R_per_trade_2R |   net_R_at_1R |
|:---------|:----------|:-----|---------:|---------:|---------:|--------------:|-----------------:|--------------:|
| bitunix  | fib       | 1d   |      244 |      217 |    0.364 |       -30.500 |           -0.140 |       -61.800 |
| delta    | fib       | 1d   |      310 |      279 |    0.326 |       -77.400 |           -0.277 |       -99.000 |
| bitunix  | fib       | 1w   |       31 |       27 |    0.417 |        -2.800 |           -0.105 |        -4.900 |
| delta    | fib       | 1w   |       39 |       35 |    0.419 |        -5.200 |           -0.150 |        -6.200 |
| bitunix  | fib       | 4h   |     1148 |      906 |    0.378 |      -239.600 |           -0.264 |      -304.600 |
| delta    | fib       | 4h   |     1266 |     1007 |    0.371 |      -271.200 |           -0.269 |      -343.300 |
| bitunix  | random    | 1d   |     1314 |     1273 |    0.391 |      -194.600 |           -0.153 |      -331.000 |
| delta    | random    | 1d   |     1730 |     1659 |    0.382 |      -262.100 |           -0.158 |      -459.300 |
| bitunix  | random    | 1w   |      252 |      246 |    0.376 |       -23.300 |           -0.095 |       -67.700 |
| delta    | random    | 1w   |      534 |      521 |    0.376 |       -56.900 |           -0.109 |      -143.800 |
| bitunix  | random    | 4h   |     1703 |     1556 |    0.430 |      -201.500 |           -0.130 |      -328.700 |
| delta    | random    | 4h   |     2083 |     1886 |    0.373 |      -445.600 |           -0.236 |      -599.100 |
| bitunix  | trendline | 1d   |      936 |      831 |    0.317 |      -282.000 |           -0.339 |      -324.500 |
| delta    | trendline | 1d   |      975 |      858 |    0.321 |      -290.800 |           -0.339 |      -332.800 |
| bitunix  | trendline | 1w   |       82 |       71 |    0.377 |        -2.100 |           -0.029 |       -20.200 |
| delta    | trendline | 1w   |       48 |       45 |    0.273 |       -16.000 |           -0.357 |       -22.100 |
| bitunix  | trendline | 4h   |     5808 |     4470 |    0.382 |     -1175.500 |           -0.263 |     -1294.700 |
| delta    | trendline | 4h   |     6511 |     5064 |    0.370 |     -1408.700 |           -0.278 |     -1589.100 |
