# Fib/TL alerts on a wick into the band vs a 5-minute check (2026-09-01 to now)

Live rules otherwise (fib 2R + BE, TL lakky stop + 1R), net after fees. Band judged on 5m candles. R and % per trade and in total. Crypto replayed on Delta candles.

| market   | kind      | tf   | rule                                          |   alerts |   trades |   win_% |   R_total |   R_per_trade |   %_total |   %_per_trade |
|:---------|:----------|:-----|:----------------------------------------------|---------:|---------:|--------:|----------:|--------------:|----------:|--------------:|
| crypto   | fib       | 4H   | live: 5m close in band (a check every ~5 min) |      159 |      119 |      51 |     -18.2 |        -0.153 |     -47.9 |        -0.403 |
| crypto   | fib       | 4H   | new: any wick into band                       |      166 |      120 |      54 |      -9.1 |        -0.076 |     -30.4 |        -0.254 |
| crypto   | fib       | 1D+  | live: 5m close in band (a check every ~5 min) |       37 |       32 |      74 |      13.5 |         0.421 |      54.7 |         1.708 |
| crypto   | fib       | 1D+  | new: any wick into band                       |       38 |       32 |      74 |      13.5 |         0.421 |      54.7 |         1.708 |
| crypto   | trendline | 4H   | live: 5m close in band (a check every ~5 min) |      625 |      477 |      36 |    -184.2 |        -0.386 |    -220.3 |        -0.462 |
| crypto   | trendline | 4H   | new: any wick into band                       |      690 |      512 |      36 |    -198.4 |        -0.388 |    -238.7 |        -0.466 |
| crypto   | trendline | 1D+  | live: 5m close in band (a check every ~5 min) |       99 |       91 |      27 |     -49.3 |        -0.541 |     -45.5 |        -0.5   |
| crypto   | trendline | 1D+  | new: any wick into band                       |      109 |      100 |      27 |     -55   |        -0.55  |     -59.3 |        -0.593 |
| nse      | fib       | 4H   | live: 5m close in band (a check every ~5 min) |      302 |      237 |      41 |     -51.4 |        -0.217 |    -105.8 |        -0.447 |
| nse      | fib       | 4H   | new: any wick into band                       |      325 |      235 |      41 |     -46.5 |        -0.198 |     -97.1 |        -0.413 |
| nse      | fib       | 1D+  | live: 5m close in band (a check every ~5 min) |      189 |      143 |      42 |     -23.7 |        -0.166 |    -156   |        -1.091 |
| nse      | fib       | 1D+  | new: any wick into band                       |      197 |      143 |      44 |     -18.6 |        -0.13  |    -142.4 |        -0.996 |
| nse      | trendline | 4H   | live: 5m close in band (a check every ~5 min) |     1143 |      897 |      39 |    -307.3 |        -0.343 |    -338.2 |        -0.377 |
| nse      | trendline | 4H   | new: any wick into band                       |     1283 |      962 |      38 |    -353   |        -0.367 |    -390   |        -0.405 |
| nse      | trendline | 1D+  | live: 5m close in band (a check every ~5 min) |      647 |      543 |      40 |    -174.2 |        -0.321 |    -206.4 |        -0.38  |
| nse      | trendline | 1D+  | new: any wick into band                       |      704 |      565 |      40 |    -177   |        -0.313 |    -209.2 |        -0.37  |

- Alerts only the wick rule sends: 489
- Same alert, sent earlier by the wick rule: 1041 of 3015, median 15 min earlier
