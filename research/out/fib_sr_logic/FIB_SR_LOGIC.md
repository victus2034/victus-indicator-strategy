# Fib zones with the S/R trade logic: 2026-09-01 to now

S/R stop = 25% of zone height beyond the far edge; cap = stop within 1.5% of entry; trend = daily EMA50. Entry = near edge everywhere. Live trade rules (2R target, BE at +0.5R), net R after fees. Crypto replayed on Delta candles.

| market   | tf   | group                                      |   alerts |   filled |   SL |   BE |   1R |   2R |   win_1r_% |   net_R |   R_per_trade |
|:---------|:-----|:-------------------------------------------|---------:|---------:|-----:|-----:|-----:|-----:|-----------:|--------:|--------------:|
| crypto   | all  | live today: both zones, fib SL             |      169 |      132 |   68 |   22 |   12 |   28 |         37 |   -31.9 |        -0.245 |
| crypto   | all  | PR #22: deeper zone, fib SL                |       61 |       48 |   20 |    8 |    9 |   11 |         50 |    -5.7 |        -0.118 |
| crypto   | all  | PR #22 + daily trend                       |       45 |       36 |   17 |    5 |    8 |    6 |         45 |   -11.6 |        -0.323 |
| crypto   | all  | S/R stop, both zones                       |      173 |      138 |   54 |   35 |   18 |   20 |         41 |   -20.1 |        -0.162 |
| crypto   | all  | S/R stop, deeper zone                      |       62 |       50 |   17 |   15 |    9 |    8 |         50 |    -3.1 |        -0.065 |
| crypto   | all  | S/R stop + 1.5% cap, both zones            |       41 |       26 |   12 |    7 |    3 |    4 |         37 |    -7.3 |        -0.28  |
| crypto   | all  | S/R stop + 1.5% cap, deeper zone           |       17 |       11 |    3 |    3 |    3 |    2 |         62 |    -0.2 |        -0.018 |
| crypto   | all  | S/R full (stop + cap + trend), both zones  |       30 |       21 |    9 |    6 |    2 |    4 |         40 |    -3.9 |        -0.184 |
| crypto   | all  | S/R full (stop + cap + trend), deeper zone |       13 |        9 |    2 |    3 |    2 |    2 |         67 |     0.9 |         0.105 |
| crypto   | 4h   | PR #22: deeper zone, fib SL                |       50 |       39 |   17 |    5 |    8 |    9 |         50 |    -6.3 |        -0.162 |
| crypto   | 4h   | S/R full (stop + cap + trend), deeper zone |       13 |        9 |    2 |    3 |    2 |    2 |         67 |     0.9 |         0.105 |
| crypto   | 1d   | PR #22: deeper zone, fib SL                |        9 |        7 |    2 |    2 |    1 |    2 |         60 |     1.7 |         0.241 |
| crypto   | 1w   | PR #22: deeper zone, fib SL                |        1 |        1 |    0 |    1 |    0 |    0 |        nan |    -0   |        -0.019 |
| crypto   | 1M   | PR #22: deeper zone, fib SL                |        1 |        1 |    1 |    0 |    0 |    0 |          0 |    -1   |        -1.023 |
| nse      | all  | live today: both zones, fib SL             |      507 |      402 |  228 |   56 |   45 |   66 |         33 |  -156.3 |        -0.397 |
| nse      | all  | PR #22: deeper zone, fib SL                |      199 |      155 |   91 |   19 |   20 |   20 |         31 |   -72.8 |        -0.489 |
| nse      | all  | PR #22 + daily trend                       |      129 |       98 |   57 |   11 |   15 |   15 |         34 |   -43.6 |        -0.449 |
| nse      | all  | S/R stop, both zones                       |      505 |      406 |  174 |   97 |   54 |   57 |         39 |   -78.3 |        -0.212 |
| nse      | all  | S/R stop, deeper zone                      |      198 |      160 |   66 |   42 |   17 |   21 |         37 |   -30.5 |        -0.213 |
| nse      | all  | S/R stop + 1.5% cap, both zones            |      107 |       82 |   38 |   22 |    6 |   16 |         37 |   -13.6 |        -0.166 |
| nse      | all  | S/R stop + 1.5% cap, deeper zone           |       39 |       32 |   14 |   10 |    3 |    5 |         36 |    -6.8 |        -0.212 |
| nse      | all  | S/R full (stop + cap + trend), both zones  |       98 |       75 |   36 |   20 |    5 |   14 |         35 |   -15.1 |        -0.202 |
| nse      | all  | S/R full (stop + cap + trend), deeper zone |       33 |       27 |   13 |    8 |    2 |    4 |         32 |    -7.5 |        -0.278 |
| nse      | 4h   | PR #22: deeper zone, fib SL                |      112 |       83 |   50 |    8 |   12 |   12 |         32 |   -40.8 |        -0.504 |
| nse      | 4h   | S/R full (stop + cap + trend), deeper zone |       28 |       22 |   11 |    7 |    1 |    3 |         27 |    -7.1 |        -0.324 |
| nse      | 1d   | PR #22: deeper zone, fib SL                |       67 |       55 |   30 |    9 |    7 |    8 |         33 |   -20.3 |        -0.377 |
| nse      | 1d   | S/R full (stop + cap + trend), deeper zone |        5 |        5 |    2 |    1 |    1 |    1 |         50 |    -0.4 |        -0.078 |
| nse      | 1w   | PR #22: deeper zone, fib SL                |       14 |       11 |    7 |    2 |    1 |    0 |         12 |    -7.4 |        -0.742 |
| nse      | 1M   | PR #22: deeper zone, fib SL                |        6 |        6 |    4 |    0 |    0 |    0 |          0 |    -4.2 |        -1.047 |
