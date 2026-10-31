# TL BROKEN alerts traded in the break direction (2026-06-01 to now)

Support closed below -> sell; resistance closed above -> buy. 'at close' = market entry at the next candle's open; 'break low/high' = stop order at the break candle's far end within 5 candles. SL break candle = its other end; SL candle before break = that candle's high (sell) / low (buy); wider = the further of the two; SL line = back inside the line. Net after fees + stop slippage; % = net R x stop %. Crypto on Delta candles; 42 crypto trades filled within 15 min of CPI/PPI/FOMC left out.

| market   | tf   | rule                                    |   signals |   trades |   win_% |   avg_stop_% |   R_per_trade |   %_per_trade |   R_total |
|:---------|:-----|:----------------------------------------|----------:|---------:|--------:|-------------:|--------------:|--------------:|----------:|
| crypto   | 4H   | at close, SL break candle, 1R           |      1243 |     1218 |      50 |         2.92 |        -0.091 |        -0.133 |    -111.3 |
| crypto   | 4H   | at close, SL break candle, 2R+BE        |      1243 |     1157 |      21 |         2.92 |        -0.027 |         0.022 |     -31.3 |
| crypto   | 4H   | at close, SL candle before break, 1R    |      1243 |     1217 |      52 |         3.85 |        -0.027 |         0.067 |     -33.1 |
| crypto   | 4H   | at close, SL candle before break, 2R+BE |      1243 |     1101 |      20 |         3.85 |         0.021 |         0.168 |      23.4 |
| crypto   | 4H   | at close, SL wider of the two, 1R       |      1243 |     1219 |      51 |         3.91 |        -0.026 |         0.051 |     -31.5 |
| crypto   | 4H   | at close, SL line, 1R                   |      1243 |     1196 |      42 |         1.42 |        -0.582 |        -0.189 |    -696.2 |
| crypto   | 4H   | break low/high, SL break candle, 1R     |      1235 |      973 |      51 |         3.63 |        -0.042 |        -0.074 |     -40.9 |
| crypto   | 4H   | live TL touch (now)                     |      2294 |     1660 |      39 |         1.26 |        -0.319 |        -0.332 |    -529.8 |
| crypto   | 1D+  | at close, SL break candle, 1R           |       211 |      202 |      60 |         8.21 |         0.18  |         1.916 |      36.4 |
| crypto   | 1D+  | at close, SL break candle, 2R+BE        |       211 |      194 |      22 |         8.21 |         0.133 |         1.415 |      25.8 |
| crypto   | 1D+  | at close, SL candle before break, 1R    |       211 |      197 |      58 |        11.18 |         0.138 |         2.212 |      27.2 |
| crypto   | 1D+  | at close, SL candle before break, 2R+BE |       211 |      179 |      19 |        11.18 |         0.074 |         1.707 |      13.3 |
| crypto   | 1D+  | at close, SL wider of the two, 1R       |       211 |      197 |      58 |        11.28 |         0.14  |         2.188 |      27.5 |
| crypto   | 1D+  | at close, SL line, 1R                   |       211 |      206 |      51 |         4.55 |        -0.065 |         1.02  |     -13.4 |
| crypto   | 1D+  | break low/high, SL break candle, 1R     |       211 |      166 |      61 |        10.2  |         0.211 |         2.399 |      35   |
| crypto   | 1D+  | live TL touch (now)                     |       333 |      301 |      31 |         2.15 |        -0.477 |        -0.381 |    -143.6 |
| crypto   | 1D   | at close, SL break candle, 1R           |       196 |      189 |      62 |         7.53 |         0.209 |         2.311 |      39.5 |
| crypto   | 1D   | at close, SL break candle, 2R+BE        |       196 |      179 |      22 |         7.53 |         0.15  |         1.697 |      26.9 |
| crypto   | 1D   | at close, SL candle before break, 1R    |       196 |      185 |      59 |        10.36 |         0.17  |         2.631 |      31.4 |
| crypto   | 1D   | at close, SL candle before break, 2R+BE |       196 |      165 |      19 |        10.36 |         0.087 |         2.134 |      14.4 |
| crypto   | 1D   | at close, SL wider of the two, 1R       |       196 |      185 |      59 |        10.44 |         0.171 |         2.61  |      31.6 |
| crypto   | 1D   | at close, SL line, 1R                   |       196 |      191 |      52 |         3.93 |        -0.042 |         1.1   |      -8   |
| crypto   | 1D   | break low/high, SL break candle, 1R     |       196 |      159 |      62 |         9.44 |         0.227 |         2.776 |      36.1 |
| crypto   | 1D   | live TL touch (now)                     |       314 |      282 |      30 |         1.84 |        -0.496 |        -0.595 |    -139.8 |
| crypto   | 1W   | at close, SL break candle, 1R           |        15 |       13 |      38 |        17.08 |        -0.242 |        -3.828 |      -3.1 |
| crypto   | 1W   | at close, SL break candle, 2R+BE        |        15 |       15 |      13 |        17.08 |        -0.074 |        -1.952 |      -1.1 |
| crypto   | 1W   | at close, SL candle before break, 1R    |        15 |       12 |      33 |        21.87 |        -0.344 |        -4.242 |      -4.1 |
| crypto   | 1W   | at close, SL candle before break, 2R+BE |        15 |       14 |      14 |        21.87 |        -0.078 |        -3.329 |      -1.1 |
| crypto   | 1W   | at close, SL wider of the two, 1R       |        15 |       12 |      33 |        22.28 |        -0.343 |        -4.303 |      -4.1 |
| crypto   | 1W   | at close, SL line, 1R                   |        15 |       15 |      33 |        12.56 |        -0.359 |         0.006 |      -5.4 |
| crypto   | 1W   | break low/high, SL break candle, 1R     |        15 |        7 |      43 |        24    |        -0.153 |        -6.158 |      -1.1 |
| crypto   | 1W   | live TL touch (now)                     |        19 |       19 |      42 |         6.68 |        -0.202 |         2.789 |      -3.8 |
| nse      | 4H   | at close, SL break candle, 1R           |      1841 |     1761 |      48 |         2.54 |        -0.198 |        -0.091 |    -348.5 |
| nse      | 4H   | at close, SL break candle, 2R+BE        |      1841 |     1728 |      19 |         2.54 |        -0.159 |        -0.081 |    -274.9 |
| nse      | 4H   | at close, SL candle before break, 1R    |      1841 |     1777 |      51 |         3.58 |        -0.054 |        -0.061 |     -96.8 |
| nse      | 4H   | at close, SL candle before break, 2R+BE |      1841 |     1665 |      18 |         3.58 |        -0.05  |        -0.196 |     -83.7 |
| nse      | 4H   | at close, SL wider of the two, 1R       |      1841 |     1778 |      51 |         3.65 |        -0.07  |        -0.067 |    -125.2 |
| nse      | 4H   | at close, SL line, 1R                   |      1841 |     1681 |      44 |         1.44 |        -0.443 |        -0.103 |    -745.3 |
| nse      | 4H   | break low/high, SL break candle, 1R     |      1841 |     1499 |      51 |         3.14 |        -0.049 |        -0.016 |     -73   |
| nse      | 4H   | live TL touch (now)                     |      3919 |     2943 |      39 |         1.26 |        -0.344 |        -0.38  |   -1012.9 |
| nse      | 1D+  | at close, SL break candle, 1R           |      1160 |     1082 |      49 |         4.23 |        -0.112 |        -0.217 |    -121.7 |
| nse      | 1D+  | at close, SL break candle, 2R+BE        |      1160 |     1070 |      17 |         4.23 |        -0.127 |        -0.47  |    -135.8 |
| nse      | 1D+  | at close, SL candle before break, 1R    |      1160 |     1046 |      50 |         6.29 |        -0.035 |        -0.137 |     -36.4 |
| nse      | 1D+  | at close, SL candle before break, 2R+BE |      1160 |      966 |      15 |         6.29 |        -0.114 |        -0.734 |    -110.6 |
| nse      | 1D+  | at close, SL wider of the two, 1R       |      1160 |     1046 |      50 |         6.37 |        -0.043 |        -0.174 |     -45   |
| nse      | 1D+  | at close, SL line, 1R                   |      1160 |     1016 |      44 |         2.24 |        -0.432 |        -0.115 |    -439   |
| nse      | 1D+  | break low/high, SL break candle, 1R     |      1160 |      845 |      52 |         5.29 |         0.003 |        -0.029 |       2.5 |
| nse      | 1D+  | live TL touch (now)                     |      2282 |     1766 |      39 |         1.51 |        -0.339 |        -0.418 |    -598.6 |
| nse      | 1D   | at close, SL break candle, 1R           |       993 |      950 |      48 |         3.6  |        -0.124 |        -0.294 |    -117.8 |
| nse      | 1D   | at close, SL break candle, 2R+BE        |       993 |      941 |      17 |         3.6  |        -0.125 |        -0.414 |    -117.9 |
| nse      | 1D   | at close, SL candle before break, 1R    |       993 |      933 |      50 |         5.41 |        -0.035 |        -0.09  |     -33   |
| nse      | 1D   | at close, SL candle before break, 2R+BE |       993 |      857 |      15 |         5.41 |        -0.098 |        -0.546 |     -83.8 |
| nse      | 1D   | at close, SL wider of the two, 1R       |       993 |      933 |      50 |         5.46 |        -0.045 |        -0.127 |     -41.8 |
| nse      | 1D   | at close, SL line, 1R                   |       993 |      872 |      43 |         1.99 |        -0.451 |        -0.207 |    -392.9 |
| nse      | 1D   | break low/high, SL break candle, 1R     |       993 |      757 |      52 |         4.53 |        -0.002 |        -0.083 |      -1.6 |
| nse      | 1D   | live TL touch (now)                     |      1900 |     1498 |      39 |         1.41 |        -0.343 |        -0.417 |    -513.3 |
| nse      | 1W   | at close, SL break candle, 1R           |       157 |      127 |      51 |         7.56 |        -0.038 |         0.183 |      -4.9 |
| nse      | 1W   | at close, SL break candle, 2R+BE        |       157 |      125 |      16 |         7.56 |        -0.126 |        -0.707 |     -15.8 |
| nse      | 1W   | at close, SL candle before break, 1R    |       157 |      110 |      50 |        10.84 |        -0.022 |        -0.335 |      -2.4 |
| nse      | 1W   | at close, SL candle before break, 2R+BE |       157 |      106 |       9 |        10.84 |        -0.242 |        -2.159 |     -25.7 |
| nse      | 1W   | at close, SL wider of the two, 1R       |       157 |      110 |      50 |        11.12 |        -0.02  |        -0.376 |      -2.2 |
| nse      | 1W   | at close, SL line, 1R                   |       157 |      136 |      48 |         3.45 |        -0.322 |         0.516 |     -43.7 |
| nse      | 1W   | break low/high, SL break candle, 1R     |       157 |       87 |      54 |         9.33 |         0.058 |         0.688 |       5.1 |
| nse      | 1W   | live TL touch (now)                     |       360 |      250 |      38 |         2.02 |        -0.328 |        -0.445 |     -82   |
| nse      | 1M   | at close, SL break candle, 1R           |        10 |        5 |      60 |        13.89 |         0.19  |         4.309 |       0.9 |
| nse      | 1M   | at close, SL break candle, 2R+BE        |        10 |        4 |       0 |        13.89 |        -0.509 |        -6.356 |      -2   |
| nse      | 1M   | at close, SL candle before break, 1R    |        10 |        3 |      33 |        21.04 |        -0.342 |        -7.491 |      -1   |
| nse      | 1M   | at close, SL candle before break, 2R+BE |        10 |        3 |       0 |        21.04 |        -0.339 |        -4.238 |      -1   |
| nse      | 1M   | at close, SL wider of the two, 1R       |        10 |        3 |      33 |        21.06 |        -0.342 |        -7.43  |      -1   |
| nse      | 1M   | at close, SL line, 1R                   |        10 |        8 |      38 |         6.02 |        -0.291 |        -0.866 |      -2.3 |
| nse      | 1M   | break low/high, SL break candle, 1R     |        10 |        1 |       0 |        16.12 |        -1.007 |       -21.498 |      -1   |
| nse      | 1M   | live TL touch (now)                     |        22 |       18 |      44 |         3.03 |        -0.187 |        -0.172 |      -3.4 |
