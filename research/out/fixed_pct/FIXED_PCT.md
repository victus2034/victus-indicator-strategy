# Fixed 1.5% stop, 3% / 4% target, with the trend: 2026-09-01 to now

Entries as live. Stop 1.5% from entry, target 3% or 4%; a candle touching both is the stop. BE = at +0.5R the stop moves past entry by the live offset. Out at the close after 20 candles of the alert's timeframe ('time'). Trend = daily EMA50 on every market. Net R after fees and 0.05% stop slip, 1R = 1.5%. 'live rules' = today's stop and 2R target as scored live (zones) or replayed (fib/trendline). win_% counts target hits only.

| alert     | market   | rule                             |   trades |   TP |   SL |   BE |   time |   win_% |   net_R |   R_per_trade |
|:----------|:---------|:---------------------------------|---------:|-----:|-----:|-----:|-------:|--------:|--------:|--------------:|
| fib       | CRYPTO   | live rules, all trades           |       35 |    0 |    0 |    0 |      0 |       0 |    -9.1 |        -0.259 |
| fib       | CRYPTO   | live rules, trend only           |       28 |    0 |    0 |    0 |      0 |       0 |    -8.8 |        -0.314 |
| fib       | CRYPTO   | SL 1.5% / TP 3%, trend only      |       31 |   10 |   21 |    0 |      0 |      32 |    -3.4 |        -0.11  |
| fib       | CRYPTO   | SL 1.5% / TP 3% + BE, trend only |       31 |    6 |   19 |    6 |      0 |      19 |    -9.2 |        -0.296 |
| fib       | CRYPTO   | SL 1.5% / TP 4%, trend only      |       29 |    7 |   22 |    0 |      0 |      24 |    -5.7 |        -0.195 |
| fib       | CRYPTO   | SL 1.5% / TP 4% + BE, trend only |       29 |    4 |   19 |    6 |      0 |      14 |   -10.4 |        -0.358 |
| fib       | NSE      | live rules, all trades           |      145 |    0 |    0 |    0 |      0 |       0 |   -28.5 |        -0.197 |
| fib       | NSE      | live rules, trend only           |      102 |    0 |    0 |    0 |      0 |       0 |   -14.2 |        -0.139 |
| fib       | NSE      | SL 1.5% / TP 3%, trend only      |      102 |   19 |   74 |    0 |      9 |      19 |   -41.6 |        -0.408 |
| fib       | NSE      | SL 1.5% / TP 3% + BE, trend only |      103 |   11 |   54 |   37 |      1 |      11 |   -38.6 |        -0.374 |
| fib       | NSE      | SL 1.5% / TP 4%, trend only      |      102 |   15 |   75 |    0 |     12 |      15 |   -37.1 |        -0.364 |
| fib       | NSE      | SL 1.5% / TP 4% + BE, trend only |      103 |    8 |   54 |   39 |      2 |       8 |   -37.8 |        -0.367 |
| fib       | OTHER    | live rules, all trades           |        8 |    0 |    0 |    0 |      0 |       0 |     2.1 |         0.259 |
| fib       | OTHER    | live rules, trend only           |        6 |    0 |    0 |    0 |      0 |       0 |     0.1 |         0.023 |
| fib       | OTHER    | SL 1.5% / TP 3%, trend only      |        4 |    0 |    2 |    0 |      2 |       0 |    -2.7 |        -0.685 |
| fib       | OTHER    | SL 1.5% / TP 3% + BE, trend only |        4 |    0 |    1 |    3 |      0 |       0 |    -1.2 |        -0.292 |
| fib       | OTHER    | SL 1.5% / TP 4%, trend only      |        4 |    0 |    2 |    0 |      2 |       0 |    -2.7 |        -0.685 |
| fib       | OTHER    | SL 1.5% / TP 4% + BE, trend only |        4 |    0 |    1 |    3 |      0 |       0 |    -1.2 |        -0.292 |
| fib       | XSTOCK   | live rules, all trades           |       11 |    0 |    0 |    0 |      0 |       0 |     3.8 |         0.342 |
| fib       | XSTOCK   | live rules, trend only           |        8 |    0 |    0 |    0 |      0 |       0 |     3.8 |         0.475 |
| fib       | XSTOCK   | SL 1.5% / TP 3%, trend only      |        8 |    2 |    6 |    0 |      0 |      25 |    -2.6 |        -0.33  |
| fib       | XSTOCK   | SL 1.5% / TP 3% + BE, trend only |        8 |    1 |    3 |    4 |      0 |      12 |    -1.4 |        -0.178 |
| fib       | XSTOCK   | SL 1.5% / TP 4%, trend only      |        8 |    2 |    6 |    0 |      0 |      25 |    -1.3 |        -0.163 |
| fib       | XSTOCK   | SL 1.5% / TP 4% + BE, trend only |        8 |    1 |    3 |    4 |      0 |      12 |    -0.8 |        -0.095 |
| trendline | CRYPTO   | live rules, all trades           |      444 |    0 |    0 |    0 |      0 |       0 |  -135.3 |        -0.305 |
| trendline | CRYPTO   | live rules, trend only           |      211 |    0 |    0 |    0 |      0 |       0 |   -80.8 |        -0.383 |
| trendline | CRYPTO   | SL 1.5% / TP 3%, trend only      |      211 |   52 |  158 |    0 |      1 |      25 |   -71.6 |        -0.339 |
| trendline | CRYPTO   | SL 1.5% / TP 3% + BE, trend only |      211 |   31 |  111 |   69 |      0 |      15 |   -62.3 |        -0.295 |
| trendline | CRYPTO   | SL 1.5% / TP 4%, trend only      |      211 |   45 |  163 |    0 |      3 |      21 |   -58.4 |        -0.277 |
| trendline | CRYPTO   | SL 1.5% / TP 4% + BE, trend only |      211 |   25 |  111 |   74 |      1 |      12 |   -56.5 |        -0.268 |
| trendline | NSE      | live rules, all trades           |     1596 |    0 |    0 |    0 |      0 |       0 |  -505.4 |        -0.317 |
| trendline | NSE      | live rules, trend only           |      579 |    0 |    0 |    0 |      0 |       0 |  -177.5 |        -0.307 |
| trendline | NSE      | SL 1.5% / TP 3%, trend only      |      560 |  152 |  354 |    0 |     54 |      27 |   -76.8 |        -0.137 |
| trendline | NSE      | SL 1.5% / TP 3% + BE, trend only |      575 |   88 |  276 |  188 |     23 |      15 |  -128.8 |        -0.224 |
| trendline | NSE      | SL 1.5% / TP 4%, trend only      |      555 |  106 |  369 |    0 |     80 |      19 |   -83.1 |        -0.15  |
| trendline | NSE      | SL 1.5% / TP 4% + BE, trend only |      570 |   56 |  276 |  205 |     33 |      10 |  -140.1 |        -0.246 |
| trendline | OTHER    | live rules, all trades           |       31 |    0 |    0 |    0 |      0 |       0 |     3.5 |         0.114 |
| trendline | OTHER    | live rules, trend only           |       13 |    0 |    0 |    0 |      0 |       0 |    -0.1 |        -0.008 |
| trendline | OTHER    | SL 1.5% / TP 3%, trend only      |       13 |    3 |    5 |    0 |      5 |      23 |    -0.3 |        -0.023 |
| trendline | OTHER    | SL 1.5% / TP 3% + BE, trend only |       13 |    1 |    4 |    8 |      0 |       8 |    -2.6 |        -0.201 |
| trendline | OTHER    | SL 1.5% / TP 4%, trend only      |       13 |    0 |    5 |    0 |      8 |       0 |    -2.7 |        -0.208 |
| trendline | OTHER    | SL 1.5% / TP 4% + BE, trend only |       13 |    0 |    4 |    8 |      1 |       0 |    -3.2 |        -0.246 |
| trendline | XSTOCK   | live rules, all trades           |      113 |    0 |    0 |    0 |      0 |       0 |   -18.2 |        -0.161 |
| trendline | XSTOCK   | live rules, trend only           |       44 |    0 |    0 |    0 |      0 |       0 |   -10.4 |        -0.236 |
| trendline | XSTOCK   | SL 1.5% / TP 3%, trend only      |       44 |    9 |   34 |    0 |      1 |      20 |   -19.5 |        -0.442 |
| trendline | XSTOCK   | SL 1.5% / TP 3% + BE, trend only |       44 |    8 |   27 |    8 |      1 |      18 |   -14   |        -0.318 |
| trendline | XSTOCK   | SL 1.5% / TP 4%, trend only      |       44 |    9 |   34 |    0 |      1 |      20 |   -13.5 |        -0.306 |
| trendline | XSTOCK   | SL 1.5% / TP 4% + BE, trend only |       44 |    7 |   27 |    9 |      1 |      16 |   -11.3 |        -0.257 |
| zone      | CRYPTO   | live rules, all trades           |      539 |    0 |    0 |    0 |      0 |       0 |  -131.3 |        -0.244 |
| zone      | CRYPTO   | live rules, trend only           |      351 |    0 |    0 |    0 |      0 |       0 |   -52.1 |        -0.148 |
| zone      | CRYPTO   | SL 1.5% / TP 3%, trend only      |      192 |   39 |  108 |    0 |     45 |      20 |   -23.8 |        -0.124 |
| zone      | CRYPTO   | SL 1.5% / TP 3% + BE, trend only |      192 |   24 |   66 |   81 |     21 |      12 |   -18.5 |        -0.096 |
| zone      | CRYPTO   | SL 1.5% / TP 4%, trend only      |      192 |   27 |  109 |    0 |     56 |      14 |   -13.3 |        -0.069 |
| zone      | CRYPTO   | SL 1.5% / TP 4% + BE, trend only |      192 |   17 |   66 |   83 |     26 |       9 |   -11.1 |        -0.058 |
| zone      | NSE      | live rules, all trades           |     1134 |    0 |    0 |    0 |      0 |       0 |  -664   |        -0.586 |
| zone      | NSE      | live rules, trend only           |      373 |    0 |    0 |    0 |      0 |       0 |  -258.6 |        -0.693 |
| zone      | NSE      | SL 1.5% / TP 3%, trend only      |      371 |   35 |  131 |    0 |    205 |       9 |   -36.8 |        -0.099 |
| zone      | NSE      | SL 1.5% / TP 3% + BE, trend only |      371 |   32 |  106 |   79 |    154 |       9 |   -24.6 |        -0.066 |
| zone      | NSE      | SL 1.5% / TP 4%, trend only      |      371 |   16 |  133 |    0 |    222 |       4 |   -34.1 |        -0.092 |
| zone      | NSE      | SL 1.5% / TP 4% + BE, trend only |      371 |   15 |  106 |   81 |    169 |       4 |   -19.3 |        -0.052 |
| zone      | OTHER    | live rules, all trades           |       46 |    0 |    0 |    0 |      0 |       0 |   -15.9 |        -0.345 |
| zone      | OTHER    | live rules, trend only           |       18 |    0 |    0 |    0 |      0 |       0 |   -11.1 |        -0.615 |
| zone      | OTHER    | SL 1.5% / TP 3%, trend only      |       17 |    0 |    4 |    0 |     13 |       0 |    -4.3 |        -0.252 |
| zone      | OTHER    | SL 1.5% / TP 3% + BE, trend only |       17 |    0 |    4 |    4 |      9 |       0 |    -4.9 |        -0.29  |
| zone      | OTHER    | SL 1.5% / TP 4%, trend only      |       17 |    0 |    4 |    0 |     13 |       0 |    -4.3 |        -0.252 |
| zone      | OTHER    | SL 1.5% / TP 4% + BE, trend only |       17 |    0 |    4 |    4 |      9 |       0 |    -4.9 |        -0.29  |
| zone      | XSTOCK   | live rules, all trades           |      123 |    0 |    0 |    0 |      0 |       0 |   -42.4 |        -0.345 |
| zone      | XSTOCK   | live rules, trend only           |       63 |    0 |    0 |    0 |      0 |       0 |   -18.5 |        -0.293 |
| zone      | XSTOCK   | SL 1.5% / TP 3%, trend only      |       47 |    7 |   17 |    0 |     23 |      15 |    -1.2 |        -0.025 |
| zone      | XSTOCK   | SL 1.5% / TP 3% + BE, trend only |       48 |    6 |   14 |   13 |     15 |      12 |    -2   |        -0.041 |
| zone      | XSTOCK   | SL 1.5% / TP 4%, trend only      |       47 |    5 |   17 |    0 |     25 |      11 |     0.9 |         0.02  |
| zone      | XSTOCK   | SL 1.5% / TP 4% + BE, trend only |       48 |    4 |   14 |   14 |     16 |       8 |    -1.5 |        -0.03  |
