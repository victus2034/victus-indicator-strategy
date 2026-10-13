# Fib: when an old fib dies (2026-09-01 to now)

Live fib rules otherwise (deeper zone, S/R stop, 2R + BE, entry not reached this candle), net after fees. R and % per trade and in total (% = R x the trade's stop distance).

| market   | tf   | rule                              |   alerts |   trades |   win_% |   R_total |   R_per_trade |   %_total |   %_per_trade |
|:---------|:-----|:----------------------------------|---------:|---------:|--------:|----------:|--------------:|----------:|--------------:|
| crypto   | 4H   | old: dies only past its top/base  |       59 |       45 |      53 |       1.8 |         0.04  |      30.2 |         0.671 |
| crypto   | 4H   | live: dies past L4                |      129 |       91 |      50 |      -7.6 |        -0.084 |     -28.3 |        -0.311 |
| crypto   | 4H   | dies past the stop (L4 + 25% box) |      111 |       79 |      53 |      -2.6 |        -0.033 |     -20.5 |        -0.259 |
| crypto   | 1D+  | old: dies only past its top/base  |       13 |       10 |      88 |       8.8 |         0.882 |      70   |         6.998 |
| crypto   | 1D+  | live: dies past L4                |       28 |       22 |      69 |       7.3 |         0.333 |      39.6 |         1.801 |
| crypto   | 1D+  | dies past the stop (L4 + 25% box) |       22 |       18 |      82 |       9.7 |         0.538 |      44.2 |         2.455 |
| crypto   | all  | old: dies only past its top/base  |       72 |       55 |      61 |      10.6 |         0.193 |     100.2 |         1.822 |
| crypto   | all  | live: dies past L4                |      157 |      113 |      53 |      -0.3 |        -0.003 |      11.4 |         0.101 |
| crypto   | all  | dies past the stop (L4 + 25% box) |      133 |       97 |      58 |       7.1 |         0.073 |      23.7 |         0.245 |
| nse      | 4H   | old: dies only past its top/base  |      117 |       85 |      41 |     -13.5 |        -0.159 |     -41   |        -0.483 |
| nse      | 4H   | live: dies past L4                |      418 |      303 |      43 |     -62.5 |        -0.206 |     -98   |        -0.324 |
| nse      | 4H   | dies past the stop (L4 + 25% box) |      342 |      245 |      42 |     -46.7 |        -0.191 |     -83.4 |        -0.34  |
| nse      | 1D+  | old: dies only past its top/base  |       91 |       60 |      36 |     -14   |        -0.234 |    -114.1 |        -1.902 |
| nse      | 1D+  | live: dies past L4                |      252 |      186 |      45 |     -21.9 |        -0.118 |    -118.2 |        -0.636 |
| nse      | 1D+  | dies past the stop (L4 + 25% box) |      215 |      150 |      47 |      -9.5 |        -0.063 |    -106.1 |        -0.707 |
| nse      | all  | old: dies only past its top/base  |      208 |      145 |      39 |     -27.5 |        -0.19  |    -155.2 |        -1.07  |
| nse      | all  | live: dies past L4                |      670 |      489 |      44 |     -84.4 |        -0.173 |    -216.3 |        -0.442 |
| nse      | all  | dies past the stop (L4 + 25% box) |      557 |      395 |      44 |     -56.2 |        -0.142 |    -189.5 |        -0.48  |
