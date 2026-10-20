# Fib alerts at every level (2026-09-01 to now)

L1-L4 on 1D/1W/1M, L2-L4 on 4H. Each level trades its own entry with the alert's stop, 2R + BE, net after fees. R and % per trade and in total. Crypto on Delta candles. Entries filled within 15 min of US CPI/PPI/FOMC left out.

| market   | tf   | level   | rule                        |   alerts |   trades |   win_% |   R_total |   R_per_trade |   %_total |   %_per_trade |
|:---------|:-----|:--------|:----------------------------|---------:|---------:|--------:|----------:|--------------:|----------:|--------------:|
| crypto   | 4H   | all     | live: L3 once               |      175 |      127 |      54 |      -4.3 |        -0.034 |       4.7 |         0.037 |
| crypto   | 4H   | all     | requested levels, once each |      526 |      366 |      45 |     -52.1 |        -0.142 |       9.1 |         0.025 |
| crypto   | 4H   | all     | requested + repeat rule     |     1021 |      642 |      46 |    -101.6 |        -0.158 |     -45.1 |        -0.07  |
| crypto   | 4H   | L2      | requested, once             |      224 |      151 |      52 |       3.4 |         0.023 |      11.4 |         0.076 |
| crypto   | 4H   | L3      | requested, once             |      175 |      127 |      54 |      -4.3 |        -0.034 |       4.7 |         0.037 |
| crypto   | 4H   | L4      | requested, once             |      127 |       88 |      28 |     -51.1 |        -0.581 |      -7   |        -0.08  |
| crypto   | 1D   | all     | live: L3 once               |       35 |       30 |      68 |      12.5 |         0.416 |      35.3 |         1.178 |
| crypto   | 1D   | all     | requested levels, once each |      161 |      126 |      53 |       9.3 |         0.074 |     105.4 |         0.836 |
| crypto   | 1D   | all     | requested + repeat rule     |      371 |      261 |      50 |       3.9 |         0.015 |     -17.9 |        -0.068 |
| crypto   | 1D   | L1      | requested, once             |       60 |       40 |      59 |       6.7 |         0.167 |      70.3 |         1.758 |
| crypto   | 1D   | L2      | requested, once             |       42 |       36 |      53 |       0.7 |         0.019 |      13   |         0.361 |
| crypto   | 1D   | L3      | requested, once             |       35 |       30 |      68 |      12.5 |         0.416 |      35.3 |         1.178 |
| crypto   | 1D   | L4      | requested, once             |       24 |       20 |      22 |     -10.5 |        -0.526 |     -13.2 |        -0.661 |
| crypto   | 1W   | all     | live: L3 once               |        5 |        3 |     100 |      -0   |        -0.008 |      -0.1 |        -0.039 |
| crypto   | 1W   | all     | requested levels, once each |       21 |        7 |      33 |      -4.1 |        -0.586 |    -127   |       -18.139 |
| crypto   | 1W   | all     | requested + repeat rule     |       38 |       15 |      55 |      -1.2 |        -0.078 |     -37.4 |        -2.491 |
| crypto   | 1W   | L1      | requested, once             |       10 |        1 |       0 |      -1   |        -1.002 |     -76.7 |       -76.75  |
| crypto   | 1W   | L2      | requested, once             |        5 |        2 |       0 |      -2   |        -1.018 |     -46.4 |       -23.207 |
| crypto   | 1W   | L3      | requested, once             |        5 |        3 |     100 |      -0   |        -0.008 |      -0.1 |        -0.039 |
| crypto   | 1W   | L4      | requested, once             |        1 |        1 |       0 |      -1   |        -1.038 |      -3.7 |        -3.688 |
| crypto   | 1M   | all     | live: L3 once               |        1 |        1 |     nan |      -0   |        -0.002 |      -0   |        -0.039 |
| crypto   | 1M   | all     | requested levels, once each |       10 |        3 |       0 |      -2   |        -0.669 |    -119.1 |       -39.69  |
| crypto   | 1M   | all     | requested + repeat rule     |       10 |        3 |       0 |      -2   |        -0.669 |    -119.1 |       -39.69  |
| crypto   | 1M   | L1      | requested, once             |        7 |        1 |       0 |      -1   |        -1.002 |     -76.7 |       -76.75  |
| crypto   | 1M   | L2      | requested, once             |        2 |        1 |       0 |      -1   |        -1.004 |     -42.3 |       -42.28  |
| crypto   | 1M   | L3      | requested, once             |        1 |        1 |     nan |      -0   |        -0.002 |      -0   |        -0.039 |
| nse      | 4H   | all     | live: L3 once               |      334 |      240 |      41 |     -46.1 |        -0.192 |     -95.6 |        -0.398 |
| nse      | 4H   | all     | requested levels, once each |     1014 |      723 |      38 |    -254.1 |        -0.352 |    -296.4 |        -0.41  |
| nse      | 4H   | all     | requested + repeat rule     |     1887 |     1315 |      41 |    -368.8 |        -0.28  |    -572.8 |        -0.436 |
| nse      | 4H   | L2      | requested, once             |      414 |      291 |      46 |     -50.9 |        -0.175 |    -151.7 |        -0.521 |
| nse      | 4H   | L3      | requested, once             |      334 |      240 |      41 |     -46.1 |        -0.192 |     -95.6 |        -0.398 |
| nse      | 4H   | L4      | requested, once             |      266 |      192 |      26 |    -157.1 |        -0.818 |     -49.1 |        -0.256 |
| nse      | 1D   | all     | live: L3 once               |      164 |      128 |      46 |      -8.5 |        -0.066 |     -47.4 |        -0.37  |
| nse      | 1D   | all     | requested levels, once each |      779 |      535 |      42 |    -107.3 |        -0.201 |    -270.2 |        -0.505 |
| nse      | 1D   | all     | requested + repeat rule     |     1631 |     1015 |      43 |    -198.9 |        -0.196 |    -851.2 |        -0.839 |
| nse      | 1D   | L1      | requested, once             |      267 |      156 |      48 |     -12.2 |        -0.078 |    -110.7 |        -0.71  |
| nse      | 1D   | L2      | requested, once             |      203 |      141 |      48 |     -18.4 |        -0.13  |     -85.7 |        -0.608 |
| nse      | 1D   | L3      | requested, once             |      164 |      128 |      46 |      -8.5 |        -0.066 |     -47.4 |        -0.37  |
| nse      | 1D   | L4      | requested, once             |      145 |      110 |      29 |     -68.2 |        -0.62  |     -26.4 |        -0.24  |
| nse      | 1W   | all     | live: L3 once               |       30 |       15 |      33 |      -8.3 |        -0.554 |     -56.3 |        -3.753 |
| nse      | 1W   | all     | requested levels, once each |      130 |       52 |      41 |     -21.6 |        -0.415 |    -112.2 |        -2.158 |
| nse      | 1W   | all     | requested + repeat rule     |      287 |       89 |      42 |     -30.8 |        -0.346 |    -227.6 |        -2.558 |
| nse      | 1W   | L1      | requested, once             |       45 |        9 |      40 |      -1.1 |        -0.12  |     -14   |        -1.555 |
| nse      | 1W   | L2      | requested, once             |       36 |       12 |      67 |      -4.1 |        -0.344 |     -30.4 |        -2.536 |
| nse      | 1W   | L3      | requested, once             |       30 |       15 |      33 |      -8.3 |        -0.554 |     -56.3 |        -3.753 |
| nse      | 1W   | L4      | requested, once             |       19 |       16 |      29 |      -8.1 |        -0.505 |     -11.5 |        -0.718 |
| nse      | 1M   | all     | live: L3 once               |       10 |        5 |       0 |      -4.1 |        -0.816 |     -42.3 |        -8.466 |
| nse      | 1M   | all     | requested levels, once each |       36 |       16 |      20 |     -10.6 |        -0.664 |     -85.6 |        -5.348 |
| nse      | 1M   | all     | requested + repeat rule     |       71 |       21 |      21 |     -13.7 |        -0.651 |    -174.8 |        -8.323 |
| nse      | 1M   | L1      | requested, once             |       11 |        1 |       0 |      -1   |        -1.011 |     -13.6 |       -13.643 |
| nse      | 1M   | L2      | requested, once             |        7 |        2 |       0 |      -2   |        -1.015 |     -21.1 |       -10.574 |
| nse      | 1M   | L3      | requested, once             |       10 |        5 |       0 |      -4.1 |        -0.816 |     -42.3 |        -8.466 |
| nse      | 1M   | L4      | requested, once             |        8 |        8 |      38 |      -3.5 |        -0.438 |      -8.4 |        -1.055 |
