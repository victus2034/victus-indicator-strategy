# Fib alerts: skip zones already touched since the fib's top (2026-09-01 to now)

Live fib rules (deeper zone, S/R stop, 2R + BE), net after fees. R and % are per trade and in total (% = R x the trade's stop distance). Crypto replayed on Delta candles.

| market   | tf   | rule                                   |   alerts |   trades |   win_% |   R_total |   R_per_trade |   %_total |   %_per_trade |
|:---------|:-----|:---------------------------------------|---------:|---------:|--------:|----------:|--------------:|----------:|--------------:|
| crypto   | 4H   | live (all alerts)                      |       59 |       46 |      45 |      -5.2 |        -0.113 |     -77.2 |        -1.678 |
| crypto   | 4H   | skip zones touched before (new rule)   |       55 |       42 |      50 |      -2.1 |        -0.05  |     -42.2 |        -1.004 |
| crypto   | 4H   | only the touched-before ones (removed) |        4 |        4 |       0 |      -3.1 |        -0.774 |     -35   |        -8.753 |
| crypto   | 1D+  | live (all alerts)                      |       13 |       11 |      67 |       4.8 |         0.437 |     -29.7 |        -2.7   |
| crypto   | 1D+  | skip zones touched before (new rule)   |       12 |       10 |      75 |       5.8 |         0.582 |      -5.9 |        -0.593 |
| crypto   | 1D+  | only the touched-before ones (removed) |        1 |        1 |       0 |      -1   |        -1.005 |     -23.8 |       -23.765 |
| crypto   | all  | live (all alerts)                      |       72 |       57 |      50 |      -0.4 |        -0.006 |    -106.9 |        -1.875 |
| crypto   | all  | skip zones touched before (new rule)   |       67 |       52 |      56 |       3.7 |         0.072 |     -48.1 |        -0.925 |
| crypto   | all  | only the touched-before ones (removed) |        5 |        5 |       0 |      -4.1 |        -0.821 |     -58.8 |       -11.755 |
| nse      | 4H   | live (all alerts)                      |      115 |       85 |      40 |     -14.4 |        -0.17  |     -44.2 |        -0.52  |
| nse      | 4H   | skip zones touched before (new rule)   |      114 |       84 |      41 |     -13.4 |        -0.159 |     -42.3 |        -0.504 |
| nse      | 4H   | only the touched-before ones (removed) |        1 |        1 |       0 |      -1.1 |        -1.091 |      -1.9 |        -1.886 |
| nse      | 1D+  | live (all alerts)                      |       90 |       62 |      33 |     -15.1 |        -0.244 |    -115.4 |        -1.861 |
| nse      | 1D+  | skip zones touched before (new rule)   |       90 |       62 |      33 |     -15.1 |        -0.244 |    -115.4 |        -1.861 |
| nse      | all  | live (all alerts)                      |      205 |      147 |      37 |     -29.6 |        -0.201 |    -159.6 |        -1.086 |
| nse      | all  | skip zones touched before (new rule)   |      204 |      146 |      37 |     -28.5 |        -0.195 |    -157.7 |        -1.08  |
| nse      | all  | only the touched-before ones (removed) |        1 |        1 |       0 |      -1.1 |        -1.091 |      -1.9 |        -1.886 |
