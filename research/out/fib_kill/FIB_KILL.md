# Fib: when an old fib dies (2026-09-01 to now)

Live fib rules otherwise (deeper zone, S/R stop, 2R + BE, entry not reached this candle), net after fees. R and % per trade and in total (% = R x the trade's stop distance).

| market   | tf   | rule                                  |   alerts |   trades |   win_% |   R_total |   R_per_trade |   %_total |   %_per_trade |
|:---------|:-----|:--------------------------------------|---------:|---------:|--------:|----------:|--------------:|----------:|--------------:|
| crypto   | 4H   | live: dies only past its top/base     |       59 |       45 |      53 |       1.8 |         0.04  |      30.2 |         0.671 |
| crypto   | 4H   | past L4, new fib from the low/high    |      126 |       90 |      49 |      -9.5 |        -0.105 |     -29.5 |        -0.328 |
| crypto   | 4H   | past L4, new fib from last higher low |      130 |       94 |      47 |     -10.7 |        -0.114 |     -21.9 |        -0.233 |
| crypto   | 1D+  | live: dies only past its top/base     |       13 |       10 |      88 |       8.8 |         0.882 |      70   |         6.998 |
| crypto   | 1D+  | past L4, new fib from the low/high    |       28 |       22 |      69 |       7.3 |         0.333 |      39.6 |         1.801 |
| crypto   | 1D+  | past L4, new fib from last higher low |       31 |       25 |      60 |       5.2 |         0.209 |      29.5 |         1.179 |
| crypto   | all  | live: dies only past its top/base     |       72 |       55 |      61 |      10.6 |         0.193 |     100.2 |         1.822 |
| crypto   | all  | past L4, new fib from the low/high    |      154 |      112 |      52 |      -2.2 |        -0.019 |      10.1 |         0.09  |
| crypto   | all  | past L4, new fib from last higher low |      161 |      119 |      49 |      -5.5 |        -0.046 |       7.6 |         0.063 |
| nse      | 4H   | live: dies only past its top/base     |      118 |       85 |      42 |     -12.3 |        -0.145 |     -39.9 |        -0.469 |
| nse      | 4H   | past L4, new fib from the low/high    |      404 |      296 |      43 |     -59.4 |        -0.201 |     -97.9 |        -0.331 |
| nse      | 4H   | past L4, new fib from last higher low |      409 |      299 |      43 |     -59.6 |        -0.199 |     -99.4 |        -0.333 |
| nse      | 1D+  | live: dies only past its top/base     |       89 |       60 |      33 |     -14   |        -0.234 |    -114.1 |        -1.902 |
| nse      | 1D+  | past L4, new fib from the low/high    |      244 |      181 |      45 |     -21.4 |        -0.118 |    -114.3 |        -0.632 |
| nse      | 1D+  | past L4, new fib from last higher low |      254 |      189 |      47 |     -17   |        -0.09  |    -112.8 |        -0.597 |
| nse      | all  | live: dies only past its top/base     |      207 |      145 |      38 |     -26.3 |        -0.182 |    -154   |        -1.062 |
| nse      | all  | past L4, new fib from the low/high    |      648 |      477 |      44 |     -80.8 |        -0.169 |    -212.2 |        -0.445 |
| nse      | all  | past L4, new fib from last higher low |      663 |      488 |      44 |     -76.6 |        -0.157 |    -212.2 |        -0.435 |
