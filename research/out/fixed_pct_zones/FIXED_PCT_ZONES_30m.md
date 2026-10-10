# Zones, fixed 1.5% stop / 3-4% target, trend only: 30m, 2026-06-01 to 2026-10-10

Alerts replayed with the live zone rules. Graded by the production scorer (6h after entry for crypto/xStock/other, same day to 15:10 for NSE; fees, stop slip). 'BE' = +0.5R moves the stop past entry. Net R in each rule's own R (fixed: 1R = 1.5%); net_%_per_trade = net R x stop % - compare that column across rules. 'from' = first alert (NSE 30m: Yahoo keeps 60 days).

| market   | tf   | from       | rule                             |   trades |   target_hit |   SL |   BE |   time_exit |   target_% |   net_R |   R_per_trade |   net_%_per_trade |
|:---------|:-----|:-----------|:---------------------------------|---------:|-------------:|-----:|-----:|------------:|-----------:|--------:|--------------:|------------------:|
| CRYPTO   | 30m  | 2026-05-31 | live rules (as today)            |      854 |          148 |  359 |  321 |          26 |         17 |  -194.1 |        -0.227 |            -0.114 |
| CRYPTO   | 30m  | 2026-05-31 | live rules, trend only           |      854 |          148 |  359 |  321 |          26 |         17 |  -194.1 |        -0.227 |            -0.114 |
| CRYPTO   | 30m  | 2026-05-31 | SL 1.5% / TP 3%, trend only      |      980 |          102 |  396 |    0 |         482 |         10 |  -109.9 |        -0.112 |            -0.168 |
| CRYPTO   | 30m  | 2026-05-31 | SL 1.5% / TP 3% + BE, trend only |      976 |           59 |  286 |  303 |         328 |          6 |  -118.7 |        -0.122 |            -0.182 |
| CRYPTO   | 30m  | 2026-05-31 | SL 1.5% / TP 4%, trend only      |      980 |           64 |  407 |    0 |         509 |          7 |  -114.4 |        -0.117 |            -0.175 |
| CRYPTO   | 30m  | 2026-05-31 | SL 1.5% / TP 4% + BE, trend only |      976 |           37 |  286 |  311 |         342 |          4 |  -115.3 |        -0.118 |            -0.177 |
| XSTOCK   | 30m  | 2026-05-31 | live rules (as today)            |      388 |           47 |  203 |  118 |          20 |         12 |  -186.7 |        -0.481 |            -0.228 |
| XSTOCK   | 30m  | 2026-05-31 | live rules, trend only           |      194 |           24 |  108 |   48 |          14 |         12 |   -96.7 |        -0.499 |            -0.256 |
| XSTOCK   | 30m  | 2026-05-31 | SL 1.5% / TP 3%, trend only      |      260 |           28 |   96 |    0 |         136 |         11 |   -39.3 |        -0.151 |            -0.227 |
| XSTOCK   | 30m  | 2026-05-31 | SL 1.5% / TP 3% + BE, trend only |      259 |           18 |   78 |   59 |         104 |          7 |   -45.7 |        -0.176 |            -0.265 |
| XSTOCK   | 30m  | 2026-05-31 | SL 1.5% / TP 4%, trend only      |      260 |           15 |   96 |    0 |         149 |          6 |   -37.1 |        -0.143 |            -0.214 |
| XSTOCK   | 30m  | 2026-05-31 | SL 1.5% / TP 4% + BE, trend only |      259 |           11 |   78 |   60 |         110 |          4 |   -42.8 |        -0.165 |            -0.248 |
| OTHER    | 30m  | 2026-06-01 | live rules (as today)            |      107 |           18 |   50 |   36 |           3 |         17 |   -41.5 |        -0.388 |            -0.133 |
| OTHER    | 30m  | 2026-06-01 | live rules, trend only           |       47 |            8 |   17 |   20 |           2 |         17 |   -11.7 |        -0.249 |            -0.054 |
| OTHER    | 30m  | 2026-06-01 | SL 1.5% / TP 3%, trend only      |       82 |            2 |   15 |    0 |          65 |          2 |    -8.3 |        -0.101 |            -0.151 |
| OTHER    | 30m  | 2026-06-01 | SL 1.5% / TP 3% + BE, trend only |       82 |            1 |   13 |   12 |          56 |          1 |    -7.9 |        -0.096 |            -0.144 |
| OTHER    | 30m  | 2026-06-01 | SL 1.5% / TP 4%, trend only      |       82 |            2 |   15 |    0 |          65 |          2 |    -6.9 |        -0.084 |            -0.127 |
| OTHER    | 30m  | 2026-06-01 | SL 1.5% / TP 4% + BE, trend only |       82 |            1 |   13 |   12 |          56 |          1 |    -7.2 |        -0.088 |            -0.132 |
| NSE      | 30m  | 2026-08-06 | live rules (as today)            |     1571 |          205 |  645 |  516 |         205 |         13 |  -513.8 |        -0.327 |            -0.172 |
| NSE      | 30m  | 2026-08-06 | live rules, trend only           |      704 |           89 |  304 |  225 |          86 |         13 |  -265.7 |        -0.377 |            -0.201 |
| NSE      | 30m  | 2026-08-06 | SL 1.5% / TP 3%, trend only      |      929 |           36 |  211 |    0 |         682 |          4 |   -97.5 |        -0.105 |            -0.157 |
| NSE      | 30m  | 2026-08-06 | SL 1.5% / TP 3% + BE, trend only |      930 |           30 |  184 |  156 |         560 |          3 |   -97.4 |        -0.105 |            -0.157 |
| NSE      | 30m  | 2026-08-06 | SL 1.5% / TP 4%, trend only      |      929 |           18 |  211 |    0 |         700 |          2 |   -91.3 |        -0.098 |            -0.147 |
| NSE      | 30m  | 2026-08-06 | SL 1.5% / TP 4% + BE, trend only |      930 |           15 |  184 |  156 |         575 |          2 |   -91.6 |        -0.099 |            -0.148 |
