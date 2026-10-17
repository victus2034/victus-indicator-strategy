# Fib stop: lakky's candle SL vs live (2026-09-01 to now)

Candle SL = most recent closed wick/body >= 0.75% past entry (closer one) + 0.2% buffer. Same alerts, entry and 2R + BE scoring as live; net after fees. % = R x the trade's stop distance. Crypto on Delta candles, NSE on Yahoo.

| market   | tf   | rule                      |   alerts |   trades |   win_% |   R_total |   R_per_trade |   %_total |   %_per_trade |   skipped |   median_stop_% |
|:---------|:-----|:--------------------------|---------:|---------:|--------:|----------:|--------------:|----------:|--------------:|----------:|----------------:|
| crypto   | 4H   | live (25% of box)         |      126 |      100 |      52 |      -6.4 |        -0.064 |       5.1 |         0.051 |         0 |            2.48 |
| crypto   | 4H   | candle SL, no cap         |      126 |      101 |      45 |     -16.3 |        -0.161 |      -8.8 |        -0.088 |         0 |            1.54 |
| crypto   | 4H   | candle SL, cap 3.5%       |      126 |      101 |      45 |     -16.3 |        -0.162 |     -23.1 |        -0.229 |         0 |            1.54 |
| crypto   | 4H   | candle SL, cap 5%         |      126 |      101 |      45 |     -16.3 |        -0.161 |     -15.9 |        -0.157 |         0 |            1.54 |
| crypto   | 4H   | candle SL, skip if > 3.5% |      126 |       87 |      41 |     -22.1 |        -0.254 |     -43.2 |        -0.497 |        17 |            1.43 |
| crypto   | 4H   | candle SL, skip if > 5%   |      126 |       94 |      44 |     -19.2 |        -0.204 |     -30.4 |        -0.324 |         9 |            1.47 |
| crypto   | 4H   | fixed 3.5% SL             |      126 |       97 |      49 |      -5.2 |        -0.054 |     -18.3 |        -0.188 |         0 |            3.5  |
| crypto   | 1D+  | live (25% of box)         |       26 |       20 |      67 |       8.7 |         0.436 |      40.5 |         2.025 |         0 |            6.75 |
| crypto   | 1D+  | candle SL, no cap         |       26 |       21 |      24 |     -12   |        -0.572 |     -28.9 |        -1.378 |         0 |            2.97 |
| crypto   | 1D+  | candle SL, cap 3.5%       |       26 |       23 |      21 |     -10.1 |        -0.441 |     -20.6 |        -0.896 |         0 |            2.97 |
| crypto   | 1D+  | candle SL, cap 5%         |       26 |       22 |      22 |      -9.1 |        -0.412 |     -14.2 |        -0.644 |         0 |            2.97 |
| crypto   | 1D+  | candle SL, skip if > 3.5% |       26 |       13 |       8 |      -9.9 |        -0.762 |     -19.8 |        -1.52  |        11 |            1.99 |
| crypto   | 1D+  | candle SL, skip if > 5%   |       26 |       17 |       7 |     -12   |        -0.705 |     -28.8 |        -1.693 |         7 |            2.26 |
| crypto   | 1D+  | fixed 3.5% SL             |       26 |       23 |      30 |      -4.7 |        -0.204 |     -16.4 |        -0.714 |         0 |            3.5  |
| nse      | 4H   | live (25% of box)         |      321 |      231 |      41 |     -46.2 |        -0.2   |     -96.6 |        -0.418 |         0 |            1.47 |
| nse      | 4H   | candle SL, no cap         |      321 |      228 |      37 |     -56.9 |        -0.25  |    -101.5 |        -0.445 |         0 |            1.41 |
| nse      | 4H   | candle SL, cap 3.5%       |      321 |      230 |      36 |     -59.1 |        -0.257 |    -100.1 |        -0.435 |         0 |            1.41 |
| nse      | 4H   | candle SL, cap 5%         |      321 |      229 |      37 |     -57   |        -0.249 |     -97.5 |        -0.426 |         0 |            1.41 |
| nse      | 4H   | candle SL, skip if > 3.5% |      321 |      209 |      37 |     -50.5 |        -0.242 |     -70.1 |        -0.335 |        28 |            1.35 |
| nse      | 4H   | candle SL, skip if > 5%   |      321 |      224 |      37 |     -54.9 |        -0.245 |     -87.1 |        -0.389 |         6 |            1.38 |
| nse      | 4H   | fixed 3.5% SL             |      321 |      206 |      41 |     -48.7 |        -0.237 |    -170.5 |        -0.828 |         0 |            3.5  |
| nse      | 1D+  | live (25% of box)         |      202 |      144 |      43 |     -19.6 |        -0.136 |    -144.8 |        -1.006 |         0 |            2.6  |
| nse      | 1D+  | candle SL, no cap         |      202 |      155 |      46 |     -14.1 |        -0.091 |     -38.7 |        -0.25  |         0 |            1.65 |
| nse      | 1D+  | candle SL, cap 3.5%       |      202 |      159 |      47 |     -11.3 |        -0.071 |     -21.3 |        -0.134 |         0 |            1.65 |
| nse      | 1D+  | candle SL, cap 5%         |      202 |      158 |      47 |     -12.1 |        -0.077 |     -25   |        -0.158 |         0 |            1.65 |
| nse      | 1D+  | candle SL, skip if > 3.5% |      202 |      134 |      48 |      -7.6 |        -0.057 |      -8.3 |        -0.062 |        30 |            1.52 |
| nse      | 1D+  | candle SL, skip if > 5%   |      202 |      148 |      47 |     -11   |        -0.074 |     -19.2 |        -0.13  |        13 |            1.59 |
| nse      | 1D+  | fixed 3.5% SL             |      202 |      150 |      41 |     -32.1 |        -0.214 |    -112.3 |        -0.749 |         0 |            3.5  |
