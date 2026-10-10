# Zones, fixed 1.5% stop / 3-4% target, trend only: 4h, 2026-06-01 to 2026-10-10

Alerts replayed with the live zone rules. Graded by the production scorer (6h after entry for crypto/xStock/other, same day to 15:10 for NSE; fees, stop slip). 'BE' = +0.5R moves the stop past entry. Net R in each rule's own R (fixed: 1R = 1.5%); net_%_per_trade = net R x stop % - compare that column across rules. 'from' = first alert (NSE 30m: Yahoo keeps 60 days).

| market   | tf   | from       | rule                             |   trades |   target_hit |   SL |   BE |   time_exit |   target_% |   net_R |   R_per_trade |   net_%_per_trade |
|:---------|:-----|:-----------|:---------------------------------|---------:|-------------:|-----:|-----:|------------:|-----------:|--------:|--------------:|------------------:|
| CRYPTO   | 4h   | 2026-06-01 | live rules (as today)            |      105 |           14 |   49 |   32 |          10 |         13 |   -29.2 |        -0.278 |            -0.237 |
| CRYPTO   | 4h   | 2026-06-01 | live rules, trend only           |      105 |           14 |   49 |   32 |          10 |         13 |   -29.2 |        -0.278 |            -0.237 |
| CRYPTO   | 4h   | 2026-06-01 | SL 1.5% / TP 3%, trend only      |      107 |            8 |   54 |    0 |          45 |          7 |   -33.6 |        -0.314 |            -0.471 |
| CRYPTO   | 4h   | 2026-06-01 | SL 1.5% / TP 3% + BE, trend only |      106 |            6 |   40 |   28 |          32 |          6 |   -25.2 |        -0.237 |            -0.356 |
| CRYPTO   | 4h   | 2026-06-01 | SL 1.5% / TP 4%, trend only      |      107 |            6 |   56 |    0 |          45 |          6 |   -35.7 |        -0.333 |            -0.5   |
| CRYPTO   | 4h   | 2026-06-01 | SL 1.5% / TP 4% + BE, trend only |      106 |            5 |   40 |   29 |          32 |          5 |   -23.8 |        -0.225 |            -0.337 |
| XSTOCK   | 4h   | 2026-06-01 | live rules (as today)            |      101 |           11 |   48 |   30 |          12 |         11 |   -35.2 |        -0.348 |            -0.245 |
| XSTOCK   | 4h   | 2026-06-01 | live rules, trend only           |       35 |            5 |   17 |    9 |           4 |         14 |    -9.4 |        -0.269 |            -0.204 |
| XSTOCK   | 4h   | 2026-06-01 | SL 1.5% / TP 3%, trend only      |       37 |            3 |   19 |    0 |          15 |          8 |   -16.4 |        -0.443 |            -0.665 |
| XSTOCK   | 4h   | 2026-06-01 | SL 1.5% / TP 3% + BE, trend only |       37 |            2 |   15 |   10 |          10 |          5 |   -14   |        -0.379 |            -0.568 |
| XSTOCK   | 4h   | 2026-06-01 | SL 1.5% / TP 4%, trend only      |       37 |            2 |   19 |    0 |          16 |          5 |   -14.9 |        -0.402 |            -0.603 |
| XSTOCK   | 4h   | 2026-06-01 | SL 1.5% / TP 4% + BE, trend only |       37 |            1 |   15 |   10 |          11 |          3 |   -13.2 |        -0.355 |            -0.533 |
| OTHER    | 4h   | 2026-06-05 | live rules (as today)            |       40 |            6 |   15 |   12 |           7 |         15 |    -6.8 |        -0.169 |            -0.091 |
| OTHER    | 4h   | 2026-06-05 | live rules, trend only           |       13 |            1 |    5 |    4 |           3 |          8 |    -4.1 |        -0.317 |            -0.108 |
| OTHER    | 4h   | 2026-06-05 | SL 1.5% / TP 3%, trend only      |       13 |            0 |    3 |    0 |          10 |          0 |    -0.8 |        -0.06  |            -0.09  |
| OTHER    | 4h   | 2026-06-05 | SL 1.5% / TP 3% + BE, trend only |       13 |            0 |    3 |    1 |           9 |          0 |    -0.9 |        -0.068 |            -0.102 |
| OTHER    | 4h   | 2026-06-05 | SL 1.5% / TP 4%, trend only      |       13 |            0 |    3 |    0 |          10 |          0 |    -0.8 |        -0.06  |            -0.09  |
| OTHER    | 4h   | 2026-06-05 | SL 1.5% / TP 4% + BE, trend only |       13 |            0 |    3 |    1 |           9 |          0 |    -0.9 |        -0.068 |            -0.102 |
| NSE      | 4h   | 2026-06-01 | live rules (as today)            |      428 |           37 |  165 |   44 |         182 |          9 |  -111   |        -0.259 |            -0.199 |
| NSE      | 4h   | 2026-06-01 | live rules, trend only           |       51 |            8 |   19 |    5 |          19 |         16 |    -4.2 |        -0.082 |            -0.073 |
| NSE      | 4h   | 2026-06-01 | SL 1.5% / TP 3%, trend only      |       56 |            3 |   10 |    0 |          43 |          5 |    -2.2 |        -0.04  |            -0.06  |
| NSE      | 4h   | 2026-06-01 | SL 1.5% / TP 3% + BE, trend only |       56 |            3 |   10 |    4 |          39 |          5 |    -1.6 |        -0.029 |            -0.044 |
| NSE      | 4h   | 2026-06-01 | SL 1.5% / TP 4%, trend only      |       56 |            2 |   10 |    0 |          44 |          4 |    -0.9 |        -0.015 |            -0.023 |
| NSE      | 4h   | 2026-06-01 | SL 1.5% / TP 4% + BE, trend only |       56 |            2 |   10 |    4 |          40 |          4 |    -0.3 |        -0.005 |            -0.007 |
