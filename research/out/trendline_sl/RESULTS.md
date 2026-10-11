# Trendline stop + exit backtest: 2026-09-01 to now

Live trendline alerts replayed; only the stop and the exit change. Net R after Delta fees, stops slipped, timeouts closed at market. Crypto on Bitunix candles.

## All timeframes, best first

| market   | tf   | stop            | exit         |   alerts |   filled |   wins_% |   net_R |   R_per_trade |   median_risk_% |
|:---------|:-----|:----------------|:-------------|---------:|---------:|---------:|--------:|--------------:|----------------:|
| crypto   | all  | touch           | 1R no cap    |      740 |      563 |       56 |    50.3 |         0.089 |            2.03 |
| crypto   | all  | nearest         | 1R no cap    |      740 |      563 |       55 |    36.1 |         0.064 |            1.67 |
| crypto   | all  | hybrid          | 1R no cap    |      740 |      563 |       55 |    35.8 |         0.064 |            1.66 |
| crypto   | all  | nearest 0.25ATR | 1R no cap    |      740 |      563 |       53 |     5   |         0.009 |            1.5  |
| crypto   | all  | hybrid          | 2R no cap    |      740 |      563 |       30 |   -90.2 |        -0.16  |            1.66 |
| crypto   | all  | hybrid          | 2R+BE no cap |      740 |      563 |       18 |   -92.6 |        -0.164 |            1.66 |
| crypto   | all  | hybrid          | 2R no BE     |      740 |      563 |       31 |   -95.1 |        -0.169 |            1.66 |
| crypto   | all  | nearest         | 2R no cap    |      740 |      563 |       30 |   -96   |        -0.17  |            1.67 |
| crypto   | all  | touch           | 2R no BE     |      740 |      563 |       31 |   -96.7 |        -0.172 |            2.03 |
| crypto   | all  | touch           | 2R no cap    |      740 |      563 |       30 |   -99.1 |        -0.176 |            2.03 |
| crypto   | all  | hybrid          | 2R+BE        |      740 |      563 |       18 |   -99   |        -0.176 |            1.66 |
| crypto   | all  | nearest         | 2R+BE no cap |      740 |      563 |       17 |  -100.2 |        -0.178 |            1.67 |
| crypto   | all  | nearest         | 2R no BE     |      740 |      563 |       31 |  -102.6 |        -0.182 |            1.67 |
| crypto   | all  | touch           | 2R+BE no cap |      740 |      563 |       18 |  -103.5 |        -0.184 |            2.03 |
| crypto   | all  | touch           | 2R+BE        |      740 |      563 |       18 |  -104.9 |        -0.186 |            2.03 |
| crypto   | all  | nearest 0.25ATR | 2R no cap    |      740 |      563 |       30 |  -104.5 |        -0.186 |            1.5  |
| crypto   | all  | nearest         | 2R+BE        |      740 |      563 |       18 |  -106.5 |        -0.189 |            1.67 |
| crypto   | all  | lakky           | 1R no cap    |      740 |      563 |       45 |  -107   |        -0.19  |            1.03 |
| crypto   | all  | touch           | 1.5R         |      740 |      563 |       35 |  -111.3 |        -0.198 |            2.03 |
| crypto   | all  | nearest 0.25ATR | 2R no BE     |      740 |      563 |       31 |  -112.3 |        -0.199 |            1.5  |
| crypto   | all  | hybrid          | 1.5R         |      740 |      563 |       34 |  -113.3 |        -0.201 |            1.66 |
| crypto   | all  | touch           | 1.5R+trail   |      740 |      563 |       35 |  -116   |        -0.206 |            2.03 |
| crypto   | all  | touch           | 1.5R+high    |      740 |      563 |       35 |  -117.2 |        -0.208 |            2.03 |
| crypto   | all  | nearest 0.25ATR | 2R+BE no cap |      740 |      563 |       17 |  -119.3 |        -0.212 |            1.5  |
| crypto   | all  | nearest         | 1.5R         |      740 |      563 |       34 |  -121.9 |        -0.216 |            1.67 |
| crypto   | all  | nearest 0.25ATR | 2R+BE        |      740 |      563 |       17 |  -121.9 |        -0.216 |            1.5  |
| crypto   | all  | hybrid          | 1.5R+trail   |      740 |      563 |       34 |  -124   |        -0.22  |            1.66 |
| crypto   | all  | hybrid          | 1.5R+high    |      740 |      563 |       34 |  -125   |        -0.222 |            1.66 |
| crypto   | all  | nearest 0.25ATR | 1.5R         |      740 |      563 |       34 |  -126.2 |        -0.224 |            1.5  |
| crypto   | all  | nearest         | 1.5R+trail   |      740 |      563 |       34 |  -126.9 |        -0.225 |            1.67 |
| crypto   | all  | nearest 0.25ATR | 1.5R+high    |      740 |      563 |       34 |  -127.5 |        -0.226 |            1.5  |
| crypto   | all  | live            | 1R no cap    |      740 |      563 |       44 |  -127.6 |        -0.227 |            1    |
| crypto   | all  | nearest         | 1.5R+high    |      740 |      563 |       34 |  -128.4 |        -0.228 |            1.67 |
| crypto   | all  | nearest 0.25ATR | 1.5R+trail   |      740 |      563 |       34 |  -128.8 |        -0.229 |            1.5  |
| crypto   | all  | touch           | candle close |      740 |      563 |       47 |  -129.3 |        -0.23  |            2.03 |
| crypto   | all  | hybrid          | candle close |      740 |      563 |       46 |  -130   |        -0.231 |            1.66 |
| crypto   | all  | nearest         | candle close |      740 |      563 |       46 |  -132.1 |        -0.235 |            1.67 |
| crypto   | all  | nearest 0.25ATR | candle close |      740 |      563 |       44 |  -150.1 |        -0.267 |            1.5  |
| crypto   | all  | lakky           | 2R no cap    |      740 |      563 |       26 |  -169   |        -0.3   |            1.03 |
| crypto   | all  | lakky           | 2R no BE     |      740 |      563 |       26 |  -171.5 |        -0.305 |            1.03 |
| crypto   | all  | live            | 1.5R         |      740 |      563 |       32 |  -176.5 |        -0.314 |            1    |
| crypto   | all  | lakky           | 2R+BE no cap |      740 |      563 |       16 |  -176.7 |        -0.314 |            1.03 |
| crypto   | all  | live            | 2R no cap    |      740 |      563 |       26 |  -178.7 |        -0.317 |            1    |
| crypto   | all  | lakky           | 1.5R         |      740 |      563 |       31 |  -178.7 |        -0.317 |            1.03 |
| crypto   | all  | lakky           | 2R+BE        |      740 |      563 |       16 |  -179.1 |        -0.318 |            1.03 |
| crypto   | all  | live            | 2R no BE     |      740 |      563 |       26 |  -180   |        -0.32  |            1    |
| crypto   | all  | live            | 1.5R+trail   |      740 |      563 |       32 |  -185   |        -0.329 |            1    |
| crypto   | all  | live            | 1.5R+high    |      740 |      563 |       32 |  -191   |        -0.339 |            1    |
| crypto   | all  | lakky           | 1.5R+trail   |      740 |      563 |       31 |  -191.1 |        -0.339 |            1.03 |
| crypto   | all  | live            | 2R+BE        |      740 |      563 |       16 |  -191.2 |        -0.34  |            1    |
| crypto   | all  | live            | 2R+BE no cap |      740 |      563 |       16 |  -191.2 |        -0.34  |            1    |
| crypto   | all  | lakky           | 1.5R+high    |      740 |      563 |       31 |  -192.9 |        -0.343 |            1.03 |
| crypto   | all  | lakky           | candle close |      740 |      563 |       37 |  -201   |        -0.357 |            1.03 |
| crypto   | all  | live            | candle close |      740 |      563 |       36 |  -203.2 |        -0.361 |            1    |
| nse      | all  | touch           | 1R no cap    |     1967 |     1603 |       46 |  -138.8 |        -0.087 |            2.09 |
| nse      | all  | nearest         | 1R no cap    |     1967 |     1603 |       45 |  -180.1 |        -0.112 |            1.9  |
| nse      | all  | hybrid          | 1R no cap    |     1967 |     1603 |       45 |  -183   |        -0.114 |            1.87 |
| nse      | all  | nearest 0.25ATR | 1R no cap    |     1967 |     1603 |       46 |  -204.7 |        -0.128 |            1.55 |
| nse      | all  | touch           | candle close |     1967 |     1603 |       43 |  -361.8 |        -0.226 |            2.09 |
| nse      | all  | touch           | 2R+BE no cap |     1967 |     1603 |       17 |  -363.2 |        -0.227 |            2.09 |
| nse      | all  | nearest 0.25ATR | 2R+BE no cap |     1967 |     1603 |       18 |  -365   |        -0.228 |            1.55 |
| nse      | all  | touch           | 2R+BE        |     1967 |     1603 |       17 |  -375.8 |        -0.234 |            2.09 |
| nse      | all  | touch           | 1.5R+trail   |     1967 |     1603 |       33 |  -376.6 |        -0.235 |            2.09 |
| nse      | all  | nearest 0.25ATR | 2R+BE        |     1967 |     1603 |       17 |  -376.1 |        -0.235 |            1.55 |
| nse      | all  | touch           | 1.5R+high    |     1967 |     1603 |       33 |  -380.3 |        -0.237 |            2.09 |
| nse      | all  | hybrid          | candle close |     1967 |     1603 |       43 |  -388.5 |        -0.242 |            1.87 |
| nse      | all  | nearest         | candle close |     1967 |     1603 |       43 |  -389.7 |        -0.243 |            1.9  |
| nse      | all  | nearest 0.25ATR | 1.5R+trail   |     1967 |     1603 |       33 |  -396.8 |        -0.248 |            1.55 |
| nse      | all  | hybrid          | 2R+BE no cap |     1967 |     1603 |       16 |  -398.2 |        -0.248 |            1.87 |
| nse      | all  | nearest         | 2R+BE no cap |     1967 |     1603 |       16 |  -399.6 |        -0.249 |            1.9  |
| nse      | all  | nearest 0.25ATR | 1.5R+high    |     1967 |     1603 |       33 |  -402.8 |        -0.251 |            1.55 |
| nse      | all  | nearest 0.25ATR | candle close |     1967 |     1603 |       42 |  -405.7 |        -0.253 |            1.55 |
| nse      | all  | hybrid          | 1.5R+trail   |     1967 |     1603 |       32 |  -405.7 |        -0.253 |            1.87 |
| nse      | all  | hybrid          | 2R+BE        |     1967 |     1603 |       16 |  -407   |        -0.254 |            1.87 |
| nse      | all  | nearest         | 2R+BE        |     1967 |     1603 |       16 |  -408.3 |        -0.255 |            1.9  |
| nse      | all  | nearest         | 1.5R+trail   |     1967 |     1603 |       32 |  -408.5 |        -0.255 |            1.9  |
| nse      | all  | touch           | 1.5R         |     1967 |     1603 |       32 |  -414.2 |        -0.258 |            2.09 |
| nse      | all  | nearest         | 1.5R+high    |     1967 |     1603 |       32 |  -415.5 |        -0.259 |            1.9  |
| nse      | all  | hybrid          | 1.5R+high    |     1967 |     1603 |       32 |  -415.4 |        -0.259 |            1.87 |
| nse      | all  | nearest 0.25ATR | 2R no cap    |     1967 |     1603 |       29 |  -427.7 |        -0.267 |            1.55 |
| nse      | all  | touch           | 2R no cap    |     1967 |     1603 |       28 |  -429.5 |        -0.268 |            2.09 |
| nse      | all  | nearest 0.25ATR | 1.5R         |     1967 |     1603 |       32 |  -429   |        -0.268 |            1.55 |
| nse      | all  | live            | 1R no cap    |     1967 |     1603 |       42 |  -439.8 |        -0.274 |            1    |
| nse      | all  | nearest         | 1.5R         |     1967 |     1603 |       32 |  -439.1 |        -0.274 |            1.9  |
| nse      | all  | nearest 0.25ATR | 2R no BE     |     1967 |     1603 |       28 |  -439.6 |        -0.274 |            1.55 |
| nse      | all  | hybrid          | 1.5R         |     1967 |     1603 |       31 |  -440.4 |        -0.275 |            1.87 |
| nse      | all  | touch           | 2R no BE     |     1967 |     1603 |       28 |  -447.6 |        -0.279 |            2.09 |
| nse      | all  | hybrid          | 2R no cap    |     1967 |     1603 |       28 |  -458.5 |        -0.286 |            1.87 |
| nse      | all  | nearest         | 2R no cap    |     1967 |     1603 |       28 |  -463.7 |        -0.289 |            1.9  |
| nse      | all  | lakky           | 1R no cap    |     1967 |     1603 |       41 |  -466   |        -0.291 |            1.09 |
| nse      | all  | hybrid          | 2R no BE     |     1967 |     1603 |       27 |  -469.1 |        -0.293 |            1.87 |
| nse      | all  | nearest         | 2R no BE     |     1967 |     1603 |       27 |  -474.3 |        -0.296 |            1.9  |
| nse      | all  | lakky           | 1.5R+trail   |     1967 |     1603 |       31 |  -475.9 |        -0.297 |            1.09 |
| nse      | all  | live            | 1.5R+trail   |     1967 |     1603 |       31 |  -479.5 |        -0.299 |            1    |
| nse      | all  | live            | 1.5R+high    |     1967 |     1603 |       31 |  -493.5 |        -0.308 |            1    |
| nse      | all  | lakky           | 1.5R+high    |     1967 |     1603 |       31 |  -495.8 |        -0.309 |            1.09 |
| nse      | all  | live            | 2R+BE        |     1967 |     1603 |       15 |  -497.9 |        -0.311 |            1    |
| nse      | all  | live            | 2R+BE no cap |     1967 |     1603 |       15 |  -497.9 |        -0.311 |            1    |
| nse      | all  | live            | 2R no BE     |     1967 |     1603 |       27 |  -525.5 |        -0.328 |            1    |
| nse      | all  | live            | 2R no cap    |     1967 |     1603 |       27 |  -525.5 |        -0.328 |            1    |
| nse      | all  | lakky           | 2R+BE        |     1967 |     1603 |       15 |  -527.2 |        -0.329 |            1.09 |
| nse      | all  | lakky           | 2R+BE no cap |     1967 |     1603 |       15 |  -526.9 |        -0.329 |            1.09 |
| nse      | all  | live            | 1.5R         |     1967 |     1603 |       31 |  -535.8 |        -0.334 |            1    |
| nse      | all  | lakky           | 2R no BE     |     1967 |     1603 |       27 |  -537   |        -0.335 |            1.09 |
| nse      | all  | lakky           | 1.5R         |     1967 |     1603 |       31 |  -543.9 |        -0.339 |            1.09 |
| nse      | all  | lakky           | 2R no cap    |     1967 |     1603 |       27 |  -544.9 |        -0.34  |            1.09 |
| nse      | all  | live            | candle close |     1967 |     1603 |       37 |  -556.2 |        -0.347 |            1    |
| nse      | all  | lakky           | candle close |     1967 |     1603 |       37 |  -582.9 |        -0.364 |            1.09 |

## By timeframe

| market   | tf   | stop            | exit         |   alerts |   filled |   wins_% |   net_R |   R_per_trade |   median_risk_% |
|:---------|:-----|:----------------|:-------------|---------:|---------:|---------:|--------:|--------------:|----------------:|
| crypto   | 4h   | live            | 2R+BE        |      658 |      490 |       15 |  -162.8 |        -0.332 |            1    |
| crypto   | 4h   | live            | 2R no BE     |      658 |      490 |       27 |  -143.7 |        -0.293 |            1    |
| crypto   | 4h   | live            | 1.5R         |      658 |      490 |       33 |  -140.9 |        -0.288 |            1    |
| crypto   | 4h   | live            | 1.5R+trail   |      658 |      490 |       33 |  -146   |        -0.298 |            1    |
| crypto   | 4h   | live            | 1.5R+high    |      658 |      490 |       33 |  -151.8 |        -0.31  |            1    |
| crypto   | 4h   | live            | candle close |      658 |      490 |       37 |  -166.6 |        -0.34  |            1    |
| crypto   | 4h   | live            | 1R no cap    |      658 |      490 |       46 |   -91.6 |        -0.187 |            1    |
| crypto   | 4h   | live            | 2R no cap    |      658 |      490 |       28 |  -142.5 |        -0.291 |            1    |
| crypto   | 4h   | live            | 2R+BE no cap |      658 |      490 |       15 |  -162.8 |        -0.332 |            1    |
| crypto   | 4h   | touch           | 2R+BE        |      658 |      490 |       18 |   -94   |        -0.192 |            1.92 |
| crypto   | 4h   | touch           | 2R no BE     |      658 |      490 |       32 |   -81.1 |        -0.165 |            1.92 |
| crypto   | 4h   | touch           | 1.5R         |      658 |      490 |       36 |   -92.4 |        -0.188 |            1.92 |
| crypto   | 4h   | touch           | 1.5R+trail   |      658 |      490 |       36 |   -94   |        -0.192 |            1.92 |
| crypto   | 4h   | touch           | 1.5R+high    |      658 |      490 |       36 |   -95.1 |        -0.194 |            1.92 |
| crypto   | 4h   | touch           | candle close |      658 |      490 |       48 |  -104.1 |        -0.212 |            1.92 |
| crypto   | 4h   | touch           | 1R no cap    |      658 |      490 |       57 |    45.7 |         0.093 |            1.92 |
| crypto   | 4h   | touch           | 2R no cap    |      658 |      490 |       31 |   -83.2 |        -0.17  |            1.92 |
| crypto   | 4h   | touch           | 2R+BE no cap |      658 |      490 |       17 |   -92.2 |        -0.188 |            1.92 |
| crypto   | 4h   | nearest         | 2R+BE        |      658 |      490 |       17 |   -92.3 |        -0.188 |            1.61 |
| crypto   | 4h   | nearest         | 2R no BE     |      658 |      490 |       32 |   -82.7 |        -0.169 |            1.61 |
| crypto   | 4h   | nearest         | 1.5R         |      658 |      490 |       35 |  -101.7 |        -0.207 |            1.61 |
| crypto   | 4h   | nearest         | 1.5R+trail   |      658 |      490 |       35 |  -104   |        -0.212 |            1.61 |
| crypto   | 4h   | nearest         | 1.5R+high    |      658 |      490 |       35 |  -105.3 |        -0.215 |            1.61 |
| crypto   | 4h   | nearest         | candle close |      658 |      490 |       48 |  -105.5 |        -0.215 |            1.61 |
| crypto   | 4h   | nearest         | 1R no cap    |      658 |      490 |       56 |    32.4 |         0.066 |            1.61 |
| crypto   | 4h   | nearest         | 2R no cap    |      658 |      490 |       31 |   -76.1 |        -0.155 |            1.61 |
| crypto   | 4h   | nearest         | 2R+BE no cap |      658 |      490 |       17 |   -86   |        -0.176 |            1.61 |
| crypto   | 4h   | nearest 0.25ATR | 2R+BE        |      658 |      490 |       17 |  -108.6 |        -0.222 |            1.31 |
| crypto   | 4h   | nearest 0.25ATR | 2R no BE     |      658 |      490 |       31 |   -99.3 |        -0.203 |            1.31 |
| crypto   | 4h   | nearest 0.25ATR | 1.5R         |      658 |      490 |       34 |  -111.4 |        -0.227 |            1.31 |
| crypto   | 4h   | nearest 0.25ATR | 1.5R+trail   |      658 |      490 |       35 |  -110.8 |        -0.226 |            1.31 |
| crypto   | 4h   | nearest 0.25ATR | 1.5R+high    |      658 |      490 |       35 |  -109.4 |        -0.223 |            1.31 |
| crypto   | 4h   | nearest 0.25ATR | candle close |      658 |      490 |       45 |  -124.3 |        -0.254 |            1.31 |
| crypto   | 4h   | nearest 0.25ATR | 1R no cap    |      658 |      490 |       54 |     4.4 |         0.009 |            1.31 |
| crypto   | 4h   | nearest 0.25ATR | 2R no cap    |      658 |      490 |       31 |   -91.5 |        -0.187 |            1.31 |
| crypto   | 4h   | nearest 0.25ATR | 2R+BE no cap |      658 |      490 |       16 |  -106   |        -0.216 |            1.31 |
| crypto   | 4h   | hybrid          | 2R+BE        |      658 |      490 |       18 |   -86.8 |        -0.177 |            1.59 |
| crypto   | 4h   | hybrid          | 2R no BE     |      658 |      490 |       32 |   -78.2 |        -0.16  |            1.59 |
| crypto   | 4h   | hybrid          | 1.5R         |      658 |      490 |       35 |   -93.1 |        -0.19  |            1.59 |
| crypto   | 4h   | hybrid          | 1.5R+trail   |      658 |      490 |       36 |  -101   |        -0.206 |            1.59 |
| crypto   | 4h   | hybrid          | 1.5R+high    |      658 |      490 |       36 |  -101.9 |        -0.208 |            1.59 |
| crypto   | 4h   | hybrid          | candle close |      658 |      490 |       48 |  -103.4 |        -0.211 |            1.59 |
| crypto   | 4h   | hybrid          | 1R no cap    |      658 |      490 |       56 |    34.1 |         0.07  |            1.59 |
| crypto   | 4h   | hybrid          | 2R no cap    |      658 |      490 |       31 |   -73.3 |        -0.15  |            1.59 |
| crypto   | 4h   | hybrid          | 2R+BE no cap |      658 |      490 |       17 |   -80.3 |        -0.164 |            1.59 |
| crypto   | 4h   | lakky           | 2R+BE        |      658 |      490 |       15 |  -158   |        -0.322 |            1.02 |
| crypto   | 4h   | lakky           | 2R no BE     |      658 |      490 |       26 |  -151.8 |        -0.31  |            1.02 |
| crypto   | 4h   | lakky           | 1.5R         |      658 |      490 |       31 |  -153.5 |        -0.313 |            1.02 |
| crypto   | 4h   | lakky           | 1.5R+trail   |      658 |      490 |       31 |  -165.8 |        -0.338 |            1.02 |
| crypto   | 4h   | lakky           | 1.5R+high    |      658 |      490 |       31 |  -167.8 |        -0.342 |            1.02 |
| crypto   | 4h   | lakky           | candle close |      658 |      490 |       38 |  -163.7 |        -0.334 |            1.02 |
| crypto   | 4h   | lakky           | 1R no cap    |      658 |      490 |       46 |   -83.5 |        -0.17  |            1.02 |
| crypto   | 4h   | lakky           | 2R no cap    |      658 |      490 |       27 |  -149.3 |        -0.305 |            1.02 |
| crypto   | 4h   | lakky           | 2R+BE no cap |      658 |      490 |       15 |  -155.6 |        -0.318 |            1.02 |
| crypto   | 1d   | live            | 2R+BE        |       80 |       71 |       17 |   -32.4 |        -0.456 |            1.5  |
| crypto   | 1d   | live            | 2R no BE     |       80 |       71 |       17 |   -40.1 |        -0.565 |            1.5  |
| crypto   | 1d   | live            | 1.5R         |       80 |       71 |       21 |   -38.5 |        -0.543 |            1.5  |
| crypto   | 1d   | live            | 1.5R+trail   |       80 |       71 |       21 |   -42.3 |        -0.596 |            1.5  |
| crypto   | 1d   | live            | 1.5R+high    |       80 |       71 |       21 |   -42.5 |        -0.599 |            1.5  |
| crypto   | 1d   | live            | candle close |       80 |       71 |       21 |   -40.1 |        -0.565 |            1.5  |
| crypto   | 1d   | live            | 1R no cap    |       80 |       71 |       27 |   -37.9 |        -0.534 |            1.5  |
| crypto   | 1d   | live            | 2R no cap    |       80 |       71 |       17 |   -40.1 |        -0.565 |            1.5  |
| crypto   | 1d   | live            | 2R+BE no cap |       80 |       71 |       17 |   -32.4 |        -0.456 |            1.5  |
| crypto   | 1d   | touch           | 2R+BE        |       80 |       71 |       21 |   -11   |        -0.155 |            3.58 |
| crypto   | 1d   | touch           | 2R no BE     |       80 |       71 |       24 |   -15.7 |        -0.221 |            3.58 |
| crypto   | 1d   | touch           | 1.5R         |       80 |       71 |       27 |   -19   |        -0.268 |            3.58 |
| crypto   | 1d   | touch           | 1.5R+trail   |       80 |       71 |       27 |   -22   |        -0.31  |            3.58 |
| crypto   | 1d   | touch           | 1.5R+high    |       80 |       71 |       27 |   -22.2 |        -0.312 |            3.58 |
| crypto   | 1d   | touch           | candle close |       80 |       71 |       35 |   -25.3 |        -0.356 |            3.58 |
| crypto   | 1d   | touch           | 1R no cap    |       80 |       71 |       49 |     2.7 |         0.038 |            3.58 |
| crypto   | 1d   | touch           | 2R no cap    |       80 |       71 |       24 |   -16   |        -0.226 |            3.58 |
| crypto   | 1d   | touch           | 2R+BE no cap |       80 |       71 |       21 |   -11.4 |        -0.16  |            3.58 |
| crypto   | 1d   | nearest         | 2R+BE        |       80 |       71 |       20 |   -14.3 |        -0.202 |            4.15 |
| crypto   | 1d   | nearest         | 2R no BE     |       80 |       71 |       23 |   -20   |        -0.281 |            4.15 |
| crypto   | 1d   | nearest         | 1.5R         |       80 |       71 |       27 |   -20.3 |        -0.286 |            4.15 |
| crypto   | 1d   | nearest         | 1.5R+trail   |       80 |       71 |       27 |   -23   |        -0.324 |            4.15 |
| crypto   | 1d   | nearest         | 1.5R+high    |       80 |       71 |       27 |   -23.2 |        -0.327 |            4.15 |
| crypto   | 1d   | nearest         | candle close |       80 |       71 |       35 |   -26.6 |        -0.375 |            4.15 |
| crypto   | 1d   | nearest         | 1R no cap    |       80 |       71 |       49 |     1.7 |         0.024 |            4.15 |
| crypto   | 1d   | nearest         | 2R no cap    |       80 |       71 |       23 |   -20   |        -0.281 |            4.15 |
| crypto   | 1d   | nearest         | 2R+BE no cap |       80 |       71 |       20 |   -14.3 |        -0.202 |            4.15 |
| crypto   | 1d   | nearest 0.25ATR | 2R+BE        |       80 |       71 |       20 |   -13.3 |        -0.188 |            3.4  |
| crypto   | 1d   | nearest 0.25ATR | 2R no BE     |       80 |       71 |       27 |   -13.1 |        -0.184 |            3.4  |
| crypto   | 1d   | nearest 0.25ATR | 1.5R         |       80 |       71 |       31 |   -14.9 |        -0.21  |            3.4  |
| crypto   | 1d   | nearest 0.25ATR | 1.5R+trail   |       80 |       71 |       31 |   -18.1 |        -0.255 |            3.4  |
| crypto   | 1d   | nearest 0.25ATR | 1.5R+high    |       80 |       71 |       31 |   -18.1 |        -0.255 |            3.4  |
| crypto   | 1d   | nearest 0.25ATR | candle close |       80 |       71 |       37 |   -25.8 |        -0.363 |            3.4  |
| crypto   | 1d   | nearest 0.25ATR | 1R no cap    |       80 |       71 |       48 |    -1.4 |        -0.02  |            3.4  |
| crypto   | 1d   | nearest 0.25ATR | 2R no cap    |       80 |       71 |       27 |   -13.1 |        -0.184 |            3.4  |
| crypto   | 1d   | nearest 0.25ATR | 2R+BE no cap |       80 |       71 |       20 |   -13.3 |        -0.188 |            3.4  |
| crypto   | 1d   | hybrid          | 2R+BE        |       80 |       71 |       21 |   -12.4 |        -0.174 |            3.52 |
| crypto   | 1d   | hybrid          | 2R no BE     |       80 |       71 |       24 |   -17   |        -0.24  |            3.52 |
| crypto   | 1d   | hybrid          | 1.5R         |       80 |       71 |       27 |   -20.3 |        -0.287 |            3.52 |
| crypto   | 1d   | hybrid          | 1.5R+trail   |       80 |       71 |       27 |   -23   |        -0.325 |            3.52 |
| crypto   | 1d   | hybrid          | 1.5R+high    |       80 |       71 |       27 |   -23.2 |        -0.327 |            3.52 |
| crypto   | 1d   | hybrid          | candle close |       80 |       71 |       35 |   -26.6 |        -0.375 |            3.52 |
| crypto   | 1d   | hybrid          | 1R no cap    |       80 |       71 |       48 |    -0.3 |        -0.004 |            3.52 |
| crypto   | 1d   | hybrid          | 2R no cap    |       80 |       71 |       24 |   -17   |        -0.24  |            3.52 |
| crypto   | 1d   | hybrid          | 2R+BE no cap |       80 |       71 |       21 |   -12.4 |        -0.174 |            3.52 |
| crypto   | 1d   | lakky           | 2R+BE        |       80 |       71 |       18 |   -25.1 |        -0.353 |            1.44 |
| crypto   | 1d   | lakky           | 2R no BE     |       80 |       71 |       24 |   -23.6 |        -0.333 |            1.44 |
| crypto   | 1d   | lakky           | 1.5R         |       80 |       71 |       27 |   -28.1 |        -0.396 |            1.44 |
| crypto   | 1d   | lakky           | 1.5R+trail   |       80 |       71 |       27 |   -27.6 |        -0.389 |            1.44 |
| crypto   | 1d   | lakky           | 1.5R+high    |       80 |       71 |       27 |   -27.3 |        -0.385 |            1.44 |
| crypto   | 1d   | lakky           | candle close |       80 |       71 |       27 |   -39.7 |        -0.56  |            1.44 |
| crypto   | 1d   | lakky           | 1R no cap    |       80 |       71 |       35 |   -25.4 |        -0.358 |            1.44 |
| crypto   | 1d   | lakky           | 2R no cap    |       80 |       71 |       24 |   -23.6 |        -0.333 |            1.44 |
| crypto   | 1d   | lakky           | 2R+BE no cap |       80 |       71 |       18 |   -25.1 |        -0.353 |            1.44 |
| crypto   | 1w   | live            | 2R+BE        |        2 |        2 |      100 |     3.9 |         1.967 |            2.5  |
| crypto   | 1w   | live            | 2R no BE     |        2 |        2 |      100 |     3.9 |         1.967 |            2.5  |
| crypto   | 1w   | live            | 1.5R         |        2 |        2 |      100 |     2.9 |         1.467 |            2.5  |
| crypto   | 1w   | live            | 1.5R+trail   |        2 |        2 |      100 |     3.3 |         1.648 |            2.5  |
| crypto   | 1w   | live            | 1.5R+high    |        2 |        2 |      100 |     3.3 |         1.648 |            2.5  |
| crypto   | 1w   | live            | candle close |        2 |        2 |      100 |     3.5 |         1.738 |            2.5  |
| crypto   | 1w   | live            | 1R no cap    |        2 |        2 |      100 |     1.9 |         0.967 |            2.5  |
| crypto   | 1w   | live            | 2R no cap    |        2 |        2 |      100 |     3.9 |         1.967 |            2.5  |
| crypto   | 1w   | live            | 2R+BE no cap |        2 |        2 |      100 |     3.9 |         1.967 |            2.5  |
| crypto   | 1w   | touch           | 2R+BE        |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | touch           | 2R no BE     |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | touch           | 1.5R         |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | touch           | 1.5R+trail   |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | touch           | 1.5R+high    |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | touch           | candle close |        2 |        2 |        0 |     0   |         0.021 |          220.83 |
| crypto   | 1w   | touch           | 1R no cap    |        2 |        2 |      100 |     2   |         1     |          220.83 |
| crypto   | 1w   | touch           | 2R no cap    |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | touch           | 2R+BE no cap |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest         | 2R+BE        |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest         | 2R no BE     |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest         | 1.5R         |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest         | 1.5R+trail   |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest         | 1.5R+high    |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest         | candle close |        2 |        2 |        0 |     0   |         0.021 |          220.83 |
| crypto   | 1w   | nearest         | 1R no cap    |        2 |        2 |      100 |     2   |         1     |          220.83 |
| crypto   | 1w   | nearest         | 2R no cap    |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest         | 2R+BE no cap |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest 0.25ATR | 2R+BE        |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest 0.25ATR | 2R no BE     |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest 0.25ATR | 1.5R         |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest 0.25ATR | 1.5R+trail   |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest 0.25ATR | 1.5R+high    |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest 0.25ATR | candle close |        2 |        2 |        0 |     0   |         0.021 |          220.83 |
| crypto   | 1w   | nearest 0.25ATR | 1R no cap    |        2 |        2 |      100 |     2   |         1     |          220.83 |
| crypto   | 1w   | nearest 0.25ATR | 2R no cap    |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | nearest 0.25ATR | 2R+BE no cap |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | hybrid          | 2R+BE        |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | hybrid          | 2R no BE     |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | hybrid          | 1.5R         |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | hybrid          | 1.5R+trail   |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | hybrid          | 1.5R+high    |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | hybrid          | candle close |        2 |        2 |        0 |     0   |         0.021 |          220.83 |
| crypto   | 1w   | hybrid          | 1R no cap    |        2 |        2 |      100 |     2   |         1     |          220.83 |
| crypto   | 1w   | hybrid          | 2R no cap    |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | hybrid          | 2R+BE no cap |        2 |        2 |       50 |     0.1 |         0.047 |          220.83 |
| crypto   | 1w   | lakky           | 2R+BE        |        2 |        2 |      100 |     3.9 |         1.969 |            4.54 |
| crypto   | 1w   | lakky           | 2R no BE     |        2 |        2 |      100 |     3.9 |         1.969 |            4.54 |
| crypto   | 1w   | lakky           | 1.5R         |        2 |        2 |      100 |     2.9 |         1.469 |            4.54 |
| crypto   | 1w   | lakky           | 1.5R+trail   |        2 |        2 |      100 |     2.2 |         1.115 |            4.54 |
| crypto   | 1w   | lakky           | 1.5R+high    |        2 |        2 |      100 |     2.2 |         1.115 |            4.54 |
| crypto   | 1w   | lakky           | candle close |        2 |        2 |      100 |     2.4 |         1.195 |            4.54 |
| crypto   | 1w   | lakky           | 1R no cap    |        2 |        2 |      100 |     1.9 |         0.969 |            4.54 |
| crypto   | 1w   | lakky           | 2R no cap    |        2 |        2 |      100 |     3.9 |         1.969 |            4.54 |
| crypto   | 1w   | lakky           | 2R+BE no cap |        2 |        2 |      100 |     3.9 |         1.969 |            4.54 |
| nse      | 4h   | live            | 2R+BE        |     1192 |      945 |       14 |  -350.1 |        -0.37  |            1    |
| nse      | 4h   | live            | 2R no BE     |     1192 |      945 |       26 |  -352.1 |        -0.373 |            1    |
| nse      | 4h   | live            | 1.5R         |     1192 |      945 |       30 |  -372.5 |        -0.394 |            1    |
| nse      | 4h   | live            | 1.5R+trail   |     1192 |      945 |       30 |  -316   |        -0.334 |            1    |
| nse      | 4h   | live            | 1.5R+high    |     1192 |      945 |       30 |  -327   |        -0.346 |            1    |
| nse      | 4h   | live            | candle close |     1192 |      945 |       36 |  -374.5 |        -0.396 |            1    |
| nse      | 4h   | live            | 1R no cap    |     1192 |      945 |       39 |  -325.9 |        -0.345 |            1    |
| nse      | 4h   | live            | 2R no cap    |     1192 |      945 |       26 |  -352.1 |        -0.373 |            1    |
| nse      | 4h   | live            | 2R+BE no cap |     1192 |      945 |       14 |  -350.1 |        -0.37  |            1    |
| nse      | 4h   | touch           | 2R+BE        |     1192 |      945 |       16 |  -255.4 |        -0.27  |            1.54 |
| nse      | 4h   | touch           | 2R no BE     |     1192 |      945 |       28 |  -279.5 |        -0.296 |            1.54 |
| nse      | 4h   | touch           | 1.5R         |     1192 |      945 |       32 |  -266.6 |        -0.282 |            1.54 |
| nse      | 4h   | touch           | 1.5R+trail   |     1192 |      945 |       33 |  -227.5 |        -0.241 |            1.54 |
| nse      | 4h   | touch           | 1.5R+high    |     1192 |      945 |       33 |  -233.4 |        -0.247 |            1.54 |
| nse      | 4h   | touch           | candle close |     1192 |      945 |       43 |  -241.5 |        -0.256 |            1.54 |
| nse      | 4h   | touch           | 1R no cap    |     1192 |      945 |       48 |   -87.7 |        -0.093 |            1.54 |
| nse      | 4h   | touch           | 2R no cap    |     1192 |      945 |       29 |  -263.2 |        -0.279 |            1.54 |
| nse      | 4h   | touch           | 2R+BE no cap |     1192 |      945 |       17 |  -244.5 |        -0.259 |            1.54 |
| nse      | 4h   | nearest         | 2R+BE        |     1192 |      945 |       16 |  -280.4 |        -0.297 |            1.45 |
| nse      | 4h   | nearest         | 2R no BE     |     1192 |      945 |       27 |  -305   |        -0.323 |            1.45 |
| nse      | 4h   | nearest         | 1.5R         |     1192 |      945 |       31 |  -291.6 |        -0.309 |            1.45 |
| nse      | 4h   | nearest         | 1.5R+trail   |     1192 |      945 |       32 |  -261.7 |        -0.277 |            1.45 |
| nse      | 4h   | nearest         | 1.5R+high    |     1192 |      945 |       32 |  -265.6 |        -0.281 |            1.45 |
| nse      | 4h   | nearest         | candle close |     1192 |      945 |       43 |  -262.5 |        -0.278 |            1.45 |
| nse      | 4h   | nearest         | 1R no cap    |     1192 |      945 |       46 |  -130   |        -0.138 |            1.45 |
| nse      | 4h   | nearest         | 2R no cap    |     1192 |      945 |       28 |  -295.6 |        -0.313 |            1.45 |
| nse      | 4h   | nearest         | 2R+BE no cap |     1192 |      945 |       16 |  -272.9 |        -0.289 |            1.45 |
| nse      | 4h   | nearest 0.25ATR | 2R+BE        |     1192 |      945 |       17 |  -273.7 |        -0.29  |            1.21 |
| nse      | 4h   | nearest 0.25ATR | 2R no BE     |     1192 |      945 |       28 |  -306.8 |        -0.325 |            1.21 |
| nse      | 4h   | nearest 0.25ATR | 1.5R         |     1192 |      945 |       32 |  -301.4 |        -0.319 |            1.21 |
| nse      | 4h   | nearest 0.25ATR | 1.5R+trail   |     1192 |      945 |       32 |  -270.5 |        -0.286 |            1.21 |
| nse      | 4h   | nearest 0.25ATR | 1.5R+high    |     1192 |      945 |       32 |  -272.9 |        -0.289 |            1.21 |
| nse      | 4h   | nearest 0.25ATR | candle close |     1192 |      945 |       42 |  -277.2 |        -0.293 |            1.21 |
| nse      | 4h   | nearest 0.25ATR | 1R no cap    |     1192 |      945 |       45 |  -162.3 |        -0.172 |            1.21 |
| nse      | 4h   | nearest 0.25ATR | 2R no cap    |     1192 |      945 |       28 |  -296.4 |        -0.314 |            1.21 |
| nse      | 4h   | nearest 0.25ATR | 2R+BE no cap |     1192 |      945 |       17 |  -264.1 |        -0.279 |            1.21 |
| nse      | 4h   | hybrid          | 2R+BE        |     1192 |      945 |       16 |  -278.9 |        -0.295 |            1.43 |
| nse      | 4h   | hybrid          | 2R no BE     |     1192 |      945 |       27 |  -303.7 |        -0.321 |            1.43 |
| nse      | 4h   | hybrid          | 1.5R         |     1192 |      945 |       31 |  -290.7 |        -0.308 |            1.43 |
| nse      | 4h   | hybrid          | 1.5R+trail   |     1192 |      945 |       32 |  -258.1 |        -0.273 |            1.43 |
| nse      | 4h   | hybrid          | 1.5R+high    |     1192 |      945 |       32 |  -264.7 |        -0.28  |            1.43 |
| nse      | 4h   | hybrid          | candle close |     1192 |      945 |       42 |  -261   |        -0.276 |            1.43 |
| nse      | 4h   | hybrid          | 1R no cap    |     1192 |      945 |       46 |  -132.5 |        -0.14  |            1.43 |
| nse      | 4h   | hybrid          | 2R no cap    |     1192 |      945 |       28 |  -294.3 |        -0.311 |            1.43 |
| nse      | 4h   | hybrid          | 2R+BE no cap |     1192 |      945 |       16 |  -271.3 |        -0.287 |            1.43 |
| nse      | 4h   | lakky           | 2R+BE        |     1192 |      945 |       15 |  -313.3 |        -0.332 |            1.04 |
| nse      | 4h   | lakky           | 2R no BE     |     1192 |      945 |       27 |  -302.1 |        -0.32  |            1.04 |
| nse      | 4h   | lakky           | 1.5R         |     1192 |      945 |       31 |  -328.8 |        -0.348 |            1.04 |
| nse      | 4h   | lakky           | 1.5R+trail   |     1192 |      945 |       31 |  -271.9 |        -0.288 |            1.04 |
| nse      | 4h   | lakky           | 1.5R+high    |     1192 |      945 |       31 |  -286.5 |        -0.303 |            1.04 |
| nse      | 4h   | lakky           | candle close |     1192 |      945 |       38 |  -344.9 |        -0.365 |            1.04 |
| nse      | 4h   | lakky           | 1R no cap    |     1192 |      945 |       41 |  -282.2 |        -0.299 |            1.04 |
| nse      | 4h   | lakky           | 2R no cap    |     1192 |      945 |       27 |  -310.1 |        -0.328 |            1.04 |
| nse      | 4h   | lakky           | 2R+BE no cap |     1192 |      945 |       15 |  -313.1 |        -0.331 |            1.04 |
| nse      | 1d   | live            | 2R+BE        |      664 |      565 |       16 |  -124.1 |        -0.22  |            1.5  |
| nse      | 1d   | live            | 2R no BE     |      664 |      565 |       28 |  -149.6 |        -0.265 |            1.5  |
| nse      | 1d   | live            | 1.5R         |      664 |      565 |       34 |  -139.3 |        -0.247 |            1.5  |
| nse      | 1d   | live            | 1.5R+trail   |      664 |      565 |       34 |  -133.4 |        -0.236 |            1.5  |
| nse      | 1d   | live            | 1.5R+high    |      664 |      565 |       34 |  -136.1 |        -0.241 |            1.5  |
| nse      | 1d   | live            | candle close |      664 |      565 |       41 |  -155   |        -0.274 |            1.5  |
| nse      | 1d   | live            | 1R no cap    |      664 |      565 |       47 |   -84.5 |        -0.149 |            1.5  |
| nse      | 1d   | live            | 2R no cap    |      664 |      565 |       28 |  -149.6 |        -0.265 |            1.5  |
| nse      | 1d   | live            | 2R+BE no cap |      664 |      565 |       16 |  -124.1 |        -0.22  |            1.5  |
| nse      | 1d   | touch           | 2R+BE        |      664 |      565 |       17 |  -106.9 |        -0.189 |            2.49 |
| nse      | 1d   | touch           | 2R no BE     |      664 |      565 |       27 |  -159.3 |        -0.282 |            2.49 |
| nse      | 1d   | touch           | 1.5R         |      664 |      565 |       31 |  -139.4 |        -0.247 |            2.49 |
| nse      | 1d   | touch           | 1.5R+trail   |      664 |      565 |       31 |  -136.5 |        -0.242 |            2.49 |
| nse      | 1d   | touch           | 1.5R+high    |      664 |      565 |       31 |  -134.5 |        -0.238 |            2.49 |
| nse      | 1d   | touch           | candle close |      664 |      565 |       45 |  -112.1 |        -0.198 |            2.49 |
| nse      | 1d   | touch           | 1R no cap    |      664 |      565 |       45 |   -45.5 |        -0.081 |            2.49 |
| nse      | 1d   | touch           | 2R no cap    |      664 |      565 |       27 |  -157.5 |        -0.279 |            2.49 |
| nse      | 1d   | touch           | 2R+BE no cap |      664 |      565 |       17 |  -105.2 |        -0.186 |            2.49 |
| nse      | 1d   | nearest         | 2R+BE        |      664 |      565 |       16 |  -112.5 |        -0.199 |            2.44 |
| nse      | 1d   | nearest         | 2R no BE     |      664 |      565 |       26 |  -159.1 |        -0.282 |            2.44 |
| nse      | 1d   | nearest         | 1.5R         |      664 |      565 |       31 |  -138.2 |        -0.245 |            2.44 |
| nse      | 1d   | nearest         | 1.5R+trail   |      664 |      565 |       31 |  -133.4 |        -0.236 |            2.44 |
| nse      | 1d   | nearest         | 1.5R+high    |      664 |      565 |       31 |  -136.8 |        -0.242 |            2.44 |
| nse      | 1d   | nearest         | candle close |      664 |      565 |       45 |  -118.3 |        -0.209 |            2.44 |
| nse      | 1d   | nearest         | 1R no cap    |      664 |      565 |       45 |   -43.9 |        -0.078 |            2.44 |
| nse      | 1d   | nearest         | 2R no cap    |      664 |      565 |       26 |  -157.9 |        -0.28  |            2.44 |
| nse      | 1d   | nearest         | 2R+BE no cap |      664 |      565 |       16 |  -111.4 |        -0.197 |            2.44 |
| nse      | 1d   | nearest 0.25ATR | 2R+BE        |      664 |      565 |       18 |   -85   |        -0.15  |            1.96 |
| nse      | 1d   | nearest 0.25ATR | 2R no BE     |      664 |      565 |       29 |  -123.5 |        -0.219 |            1.96 |
| nse      | 1d   | nearest 0.25ATR | 1.5R         |      664 |      565 |       33 |  -115.8 |        -0.205 |            1.96 |
| nse      | 1d   | nearest 0.25ATR | 1.5R+trail   |      664 |      565 |       33 |  -113.1 |        -0.2   |            1.96 |
| nse      | 1d   | nearest 0.25ATR | 1.5R+high    |      664 |      565 |       33 |  -116.2 |        -0.206 |            1.96 |
| nse      | 1d   | nearest 0.25ATR | candle close |      664 |      565 |       45 |  -115.4 |        -0.204 |            1.96 |
| nse      | 1d   | nearest 0.25ATR | 1R no cap    |      664 |      565 |       47 |   -32.6 |        -0.058 |            1.96 |
| nse      | 1d   | nearest 0.25ATR | 2R no cap    |      664 |      565 |       29 |  -122   |        -0.216 |            1.96 |
| nse      | 1d   | nearest 0.25ATR | 2R+BE no cap |      664 |      565 |       18 |   -83.5 |        -0.148 |            1.96 |
| nse      | 1d   | hybrid          | 2R+BE        |      664 |      565 |       16 |  -114.2 |        -0.202 |            2.3  |
| nse      | 1d   | hybrid          | 2R no BE     |      664 |      565 |       27 |  -156.7 |        -0.277 |            2.3  |
| nse      | 1d   | hybrid          | 1.5R         |      664 |      565 |       31 |  -141.3 |        -0.25  |            2.3  |
| nse      | 1d   | hybrid          | 1.5R+trail   |      664 |      565 |       31 |  -135.3 |        -0.239 |            2.3  |
| nse      | 1d   | hybrid          | 1.5R+high    |      664 |      565 |       31 |  -138.6 |        -0.245 |            2.3  |
| nse      | 1d   | hybrid          | candle close |      664 |      565 |       45 |  -119.1 |        -0.211 |            2.3  |
| nse      | 1d   | hybrid          | 1R no cap    |      664 |      565 |       45 |   -44.3 |        -0.078 |            2.3  |
| nse      | 1d   | hybrid          | 2R no cap    |      664 |      565 |       27 |  -155.5 |        -0.275 |            2.3  |
| nse      | 1d   | hybrid          | 2R+BE no cap |      664 |      565 |       16 |  -113   |        -0.2   |            2.3  |
| nse      | 1d   | lakky           | 2R+BE        |      664 |      565 |       15 |  -171.1 |        -0.303 |            1.11 |
| nse      | 1d   | lakky           | 2R no BE     |      664 |      565 |       27 |  -189   |        -0.335 |            1.11 |
| nse      | 1d   | lakky           | 1.5R         |      664 |      565 |       32 |  -173.1 |        -0.306 |            1.11 |
| nse      | 1d   | lakky           | 1.5R+trail   |      664 |      565 |       32 |  -154.4 |        -0.273 |            1.11 |
| nse      | 1d   | lakky           | 1.5R+high    |      664 |      565 |       32 |  -159.7 |        -0.283 |            1.11 |
| nse      | 1d   | lakky           | candle close |      664 |      565 |       36 |  -195.1 |        -0.345 |            1.11 |
| nse      | 1d   | lakky           | 1R no cap    |      664 |      565 |       43 |  -137   |        -0.242 |            1.11 |
| nse      | 1d   | lakky           | 2R no cap    |      664 |      565 |       27 |  -189   |        -0.335 |            1.11 |
| nse      | 1d   | lakky           | 2R+BE no cap |      664 |      565 |       15 |  -171.1 |        -0.303 |            1.11 |
| nse      | 1w   | live            | 2R+BE        |      103 |       85 |       21 |   -23.4 |        -0.275 |            2.5  |
| nse      | 1w   | live            | 2R no BE     |      103 |       85 |       29 |   -22.4 |        -0.264 |            2.5  |
| nse      | 1w   | live            | 1.5R         |      103 |       85 |       34 |   -21.7 |        -0.255 |            2.5  |
| nse      | 1w   | live            | 1.5R+trail   |      103 |       85 |       34 |   -28.2 |        -0.331 |            2.5  |
| nse      | 1w   | live            | 1.5R+high    |      103 |       85 |       34 |   -28.5 |        -0.335 |            2.5  |
| nse      | 1w   | live            | candle close |      103 |       85 |       34 |   -25.1 |        -0.295 |            2.5  |
| nse      | 1w   | live            | 1R no cap    |      103 |       85 |       35 |   -28.1 |        -0.331 |            2.5  |
| nse      | 1w   | live            | 2R no cap    |      103 |       85 |       29 |   -22.4 |        -0.264 |            2.5  |
| nse      | 1w   | live            | 2R+BE no cap |      103 |       85 |       21 |   -23.4 |        -0.275 |            2.5  |
| nse      | 1w   | touch           | 2R+BE        |      103 |       85 |       20 |   -13.4 |        -0.157 |            5.64 |
| nse      | 1w   | touch           | 2R no BE     |      103 |       85 |       32 |    -8.7 |        -0.102 |            5.64 |
| nse      | 1w   | touch           | 1.5R         |      103 |       85 |       34 |    -8.1 |        -0.095 |            5.64 |
| nse      | 1w   | touch           | 1.5R+trail   |      103 |       85 |       34 |   -12.5 |        -0.148 |            5.64 |
| nse      | 1w   | touch           | 1.5R+high    |      103 |       85 |       34 |   -12.3 |        -0.145 |            5.64 |
| nse      | 1w   | touch           | candle close |      103 |       85 |       36 |    -7.8 |        -0.092 |            5.64 |
| nse      | 1w   | touch           | 1R no cap    |      103 |       85 |       35 |    -6.2 |        -0.073 |            5.64 |
| nse      | 1w   | touch           | 2R no cap    |      103 |       85 |       32 |    -8.7 |        -0.102 |            5.64 |
| nse      | 1w   | touch           | 2R+BE no cap |      103 |       85 |       20 |   -13.4 |        -0.157 |            5.64 |
| nse      | 1w   | nearest         | 2R+BE        |      103 |       85 |       20 |   -14.9 |        -0.176 |            5.93 |
| nse      | 1w   | nearest         | 2R no BE     |      103 |       85 |       32 |   -10.2 |        -0.12  |            5.93 |
| nse      | 1w   | nearest         | 1.5R         |      103 |       85 |       34 |    -9.4 |        -0.11  |            5.93 |
| nse      | 1w   | nearest         | 1.5R+trail   |      103 |       85 |       34 |   -13.5 |        -0.159 |            5.93 |
| nse      | 1w   | nearest         | 1.5R+high    |      103 |       85 |       34 |   -13.2 |        -0.156 |            5.93 |
| nse      | 1w   | nearest         | candle close |      103 |       85 |       36 |    -8.6 |        -0.101 |            5.93 |
| nse      | 1w   | nearest         | 1R no cap    |      103 |       85 |       35 |    -6.8 |        -0.08  |            5.93 |
| nse      | 1w   | nearest         | 2R no cap    |      103 |       85 |       32 |   -10.2 |        -0.12  |            5.93 |
| nse      | 1w   | nearest         | 2R+BE no cap |      103 |       85 |       20 |   -14.9 |        -0.176 |            5.93 |
| nse      | 1w   | nearest 0.25ATR | 2R+BE        |      103 |       85 |       18 |   -19.1 |        -0.225 |            3.8  |
| nse      | 1w   | nearest 0.25ATR | 2R no BE     |      103 |       85 |       31 |   -10.5 |        -0.124 |            3.8  |
| nse      | 1w   | nearest 0.25ATR | 1.5R         |      103 |       85 |       33 |   -12.5 |        -0.147 |            3.8  |
| nse      | 1w   | nearest 0.25ATR | 1.5R+trail   |      103 |       85 |       33 |   -13.8 |        -0.162 |            3.8  |
| nse      | 1w   | nearest 0.25ATR | 1.5R+high    |      103 |       85 |       33 |   -14.2 |        -0.167 |            3.8  |
| nse      | 1w   | nearest 0.25ATR | candle close |      103 |       85 |       34 |   -13.1 |        -0.154 |            3.8  |
| nse      | 1w   | nearest 0.25ATR | 1R no cap    |      103 |       85 |       35 |   -10.4 |        -0.123 |            3.8  |
| nse      | 1w   | nearest 0.25ATR | 2R no cap    |      103 |       85 |       31 |   -10.5 |        -0.124 |            3.8  |
| nse      | 1w   | nearest 0.25ATR | 2R+BE no cap |      103 |       85 |       18 |   -19.1 |        -0.225 |            3.8  |
| nse      | 1w   | hybrid          | 2R+BE        |      103 |       85 |       20 |   -13.5 |        -0.158 |            5.47 |
| nse      | 1w   | hybrid          | 2R no BE     |      103 |       85 |       32 |    -8.8 |        -0.103 |            5.47 |
| nse      | 1w   | hybrid          | 1.5R         |      103 |       85 |       34 |    -8.4 |        -0.099 |            5.47 |
| nse      | 1w   | hybrid          | 1.5R+trail   |      103 |       85 |       34 |   -12.4 |        -0.145 |            5.47 |
| nse      | 1w   | hybrid          | 1.5R+high    |      103 |       85 |       34 |   -12.1 |        -0.143 |            5.47 |
| nse      | 1w   | hybrid          | candle close |      103 |       85 |       36 |    -8.1 |        -0.095 |            5.47 |
| nse      | 1w   | hybrid          | 1R no cap    |      103 |       85 |       35 |    -6.8 |        -0.08  |            5.47 |
| nse      | 1w   | hybrid          | 2R no cap    |      103 |       85 |       32 |    -8.8 |        -0.103 |            5.47 |
| nse      | 1w   | hybrid          | 2R+BE no cap |      103 |       85 |       20 |   -13.5 |        -0.158 |            5.47 |
| nse      | 1w   | lakky           | 2R+BE        |      103 |       85 |       16 |   -41.7 |        -0.491 |            1.45 |
| nse      | 1w   | lakky           | 2R no BE     |      103 |       85 |       22 |   -44.8 |        -0.527 |            1.45 |
| nse      | 1w   | lakky           | 1.5R         |      103 |       85 |       27 |   -40.8 |        -0.48  |            1.45 |
| nse      | 1w   | lakky           | 1.5R+trail   |      103 |       85 |       27 |   -48.7 |        -0.573 |            1.45 |
| nse      | 1w   | lakky           | 1.5R+high    |      103 |       85 |       27 |   -48.7 |        -0.573 |            1.45 |
| nse      | 1w   | lakky           | candle close |      103 |       85 |       27 |   -40.9 |        -0.481 |            1.45 |
| nse      | 1w   | lakky           | 1R no cap    |      103 |       85 |       28 |   -45.1 |        -0.53  |            1.45 |
| nse      | 1w   | lakky           | 2R no cap    |      103 |       85 |       22 |   -44.8 |        -0.527 |            1.45 |
| nse      | 1w   | lakky           | 2R+BE no cap |      103 |       85 |       16 |   -41.7 |        -0.491 |            1.45 |
| nse      | 1M   | live            | 2R+BE        |        8 |        8 |       25 |    -0.3 |        -0.034 |            3    |
| nse      | 1M   | live            | 2R no BE     |        8 |        8 |       25 |    -1.3 |        -0.164 |            3    |
| nse      | 1M   | live            | 1.5R         |        8 |        8 |       25 |    -2.3 |        -0.289 |            3    |
| nse      | 1M   | live            | 1.5R+trail   |        8 |        8 |       25 |    -1.9 |        -0.239 |            3    |
| nse      | 1M   | live            | 1.5R+high    |        8 |        8 |       25 |    -1.9 |        -0.239 |            3    |
| nse      | 1M   | live            | candle close |        8 |        8 |       25 |    -1.6 |        -0.197 |            3    |
| nse      | 1M   | live            | 1R no cap    |        8 |        8 |       38 |    -1.3 |        -0.162 |            3    |
| nse      | 1M   | live            | 2R no cap    |        8 |        8 |       25 |    -1.3 |        -0.164 |            3    |
| nse      | 1M   | live            | 2R+BE no cap |        8 |        8 |       25 |    -0.3 |        -0.034 |            3    |
| nse      | 1M   | touch           | 2R+BE        |        8 |        8 |       50 |    -0.1 |        -0.014 |           38.74 |
| nse      | 1M   | touch           | 2R no BE     |        8 |        8 |       50 |    -0.1 |        -0.014 |           38.74 |
| nse      | 1M   | touch           | 1.5R         |        8 |        8 |       50 |    -0.1 |        -0.014 |           38.74 |
| nse      | 1M   | touch           | 1.5R+trail   |        8 |        8 |       50 |    -0.1 |        -0.014 |           38.74 |
| nse      | 1M   | touch           | 1.5R+high    |        8 |        8 |       50 |    -0.1 |        -0.014 |           38.74 |
| nse      | 1M   | touch           | candle close |        8 |        8 |       38 |    -0.4 |        -0.046 |           38.74 |
| nse      | 1M   | touch           | 1R no cap    |        8 |        8 |       50 |     0.6 |         0.073 |           38.74 |
| nse      | 1M   | touch           | 2R no cap    |        8 |        8 |       50 |    -0.1 |        -0.014 |           38.74 |
| nse      | 1M   | touch           | 2R+BE no cap |        8 |        8 |       50 |    -0.1 |        -0.014 |           38.74 |
| nse      | 1M   | nearest         | 2R+BE        |        8 |        8 |       38 |    -0.4 |        -0.052 |           38.74 |
| nse      | 1M   | nearest         | 2R no BE     |        8 |        8 |       50 |     0.1 |         0.008 |           38.74 |
| nse      | 1M   | nearest         | 1.5R         |        8 |        8 |       50 |     0.1 |         0.008 |           38.74 |
| nse      | 1M   | nearest         | 1.5R+trail   |        8 |        8 |       50 |     0.1 |         0.008 |           38.74 |
| nse      | 1M   | nearest         | 1.5R+high    |        8 |        8 |       50 |     0.1 |         0.008 |           38.74 |
| nse      | 1M   | nearest         | candle close |        8 |        8 |       38 |    -0.3 |        -0.042 |           38.74 |
| nse      | 1M   | nearest         | 1R no cap    |        8 |        8 |       50 |     0.6 |         0.073 |           38.74 |
| nse      | 1M   | nearest         | 2R no cap    |        8 |        8 |       50 |     0.1 |         0.008 |           38.74 |
| nse      | 1M   | nearest         | 2R+BE no cap |        8 |        8 |       38 |    -0.4 |        -0.052 |           38.74 |
| nse      | 1M   | nearest 0.25ATR | 2R+BE        |        8 |        8 |       38 |     1.7 |         0.215 |           25.29 |
| nse      | 1M   | nearest 0.25ATR | 2R no BE     |        8 |        8 |       50 |     1.2 |         0.148 |           25.29 |
| nse      | 1M   | nearest 0.25ATR | 1.5R         |        8 |        8 |       50 |     0.7 |         0.085 |           25.29 |
| nse      | 1M   | nearest 0.25ATR | 1.5R+trail   |        8 |        8 |       50 |     0.5 |         0.068 |           25.29 |
| nse      | 1M   | nearest 0.25ATR | 1.5R+high    |        8 |        8 |       50 |     0.5 |         0.068 |           25.29 |
| nse      | 1M   | nearest 0.25ATR | candle close |        8 |        8 |       38 |    -0   |        -0     |           25.29 |
| nse      | 1M   | nearest 0.25ATR | 1R no cap    |        8 |        8 |       50 |     0.7 |         0.087 |           25.29 |
| nse      | 1M   | nearest 0.25ATR | 2R no cap    |        8 |        8 |       50 |     1.2 |         0.148 |           25.29 |
| nse      | 1M   | nearest 0.25ATR | 2R+BE no cap |        8 |        8 |       38 |     1.7 |         0.215 |           25.29 |
| nse      | 1M   | hybrid          | 2R+BE        |        8 |        8 |       38 |    -0.4 |        -0.052 |           38.74 |
| nse      | 1M   | hybrid          | 2R no BE     |        8 |        8 |       50 |     0.1 |         0.008 |           38.74 |
| nse      | 1M   | hybrid          | 1.5R         |        8 |        8 |       50 |     0.1 |         0.008 |           38.74 |
| nse      | 1M   | hybrid          | 1.5R+trail   |        8 |        8 |       50 |     0.1 |         0.008 |           38.74 |
| nse      | 1M   | hybrid          | 1.5R+high    |        8 |        8 |       50 |     0.1 |         0.008 |           38.74 |
| nse      | 1M   | hybrid          | candle close |        8 |        8 |       38 |    -0.3 |        -0.042 |           38.74 |
| nse      | 1M   | hybrid          | 1R no cap    |        8 |        8 |       50 |     0.6 |         0.073 |           38.74 |
| nse      | 1M   | hybrid          | 2R no cap    |        8 |        8 |       50 |     0.1 |         0.008 |           38.74 |
| nse      | 1M   | hybrid          | 2R+BE no cap |        8 |        8 |       38 |    -0.4 |        -0.052 |           38.74 |
| nse      | 1M   | lakky           | 2R+BE        |        8 |        8 |       38 |    -1.1 |        -0.134 |            2.89 |
| nse      | 1M   | lakky           | 2R no BE     |        8 |        8 |       38 |    -1.1 |        -0.134 |            2.89 |
| nse      | 1M   | lakky           | 1.5R         |        8 |        8 |       38 |    -1.2 |        -0.146 |            2.89 |
| nse      | 1M   | lakky           | 1.5R+trail   |        8 |        8 |       38 |    -0.9 |        -0.114 |            2.89 |
| nse      | 1M   | lakky           | 1.5R+high    |        8 |        8 |       38 |    -0.9 |        -0.114 |            2.89 |
| nse      | 1M   | lakky           | candle close |        8 |        8 |       38 |    -2   |        -0.256 |            2.89 |
| nse      | 1M   | lakky           | 1R no cap    |        8 |        8 |       38 |    -1.7 |        -0.207 |            2.89 |
| nse      | 1M   | lakky           | 2R no cap    |        8 |        8 |       38 |    -1.1 |        -0.134 |            2.89 |
| nse      | 1M   | lakky           | 2R+BE no cap |        8 |        8 |       38 |    -1.1 |        -0.134 |            2.89 |
