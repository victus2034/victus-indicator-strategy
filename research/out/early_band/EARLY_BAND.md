# 1W / 1M alerts from 3% away (2026-09-01 to now)

Same entry, stop and target; only the alert band changes on 1W and 1M. Fibs at the live levels (once each, 2R + BE), TL lakky stop + 1R, zones 2R + BE; net after fees. R and % per trade. Crypto fib/TL on Delta candles, zones on Bitunix; NSE on Yahoo. Entries filled within 15 min of US CPI/PPI/FOMC left out. days_alert_to_fill = median days from the alert to the entry filling (daily candles).

| market   | kind      | tf   | rule                       |   alerts |   trades |   win_% |   R_total |   R_per_trade |   %_total |   %_per_trade |   days_alert_to_fill |
|:---------|:----------|:-----|:---------------------------|---------:|---------:|--------:|----------:|--------------:|----------:|--------------:|---------------------:|
| crypto   | fib       | 1w   | live (0.75% / zones 0.20%) |       21 |        8 |      33 |      -4.1 |        -0.514 |    -127   |       -15.876 |                  1   |
| crypto   | fib       | 1w   | 3% on 1W/1M                |       30 |       10 |      25 |      -6.6 |        -0.657 |    -128.5 |       -12.849 |                  1.5 |
| crypto   | fib       | 1M   | live (0.75% / zones 0.20%) |       10 |        3 |       0 |      -2   |        -0.669 |    -119.1 |       -39.69  |                  1   |
| crypto   | fib       | 1M   | 3% on 1W/1M                |       12 |        4 |       0 |      -3   |        -0.761 |    -122.8 |       -30.689 |                  2   |
| crypto   | trendline | 1w   | live (0.75% / zones 0.20%) |        5 |        5 |      60 |       0.8 |         0.161 |      16.2 |         3.241 |                  1   |
| crypto   | trendline | 1w   | 3% on 1W/1M                |        4 |        4 |      75 |       1.9 |         0.471 |      18   |         4.497 |                  2.5 |
| nse      | fib       | 1w   | live (0.75% / zones 0.20%) |      130 |       63 |      36 |     -26.9 |        -0.427 |    -166.7 |        -2.645 |                  1   |
| nse      | fib       | 1w   | 3% on 1W/1M                |      170 |       57 |      34 |     -28.6 |        -0.501 |    -109.8 |        -1.926 |                  5   |
| nse      | fib       | 1M   | live (0.75% / zones 0.20%) |       36 |       16 |      25 |     -10.6 |        -0.664 |     -85.6 |        -5.348 |                  1   |
| nse      | fib       | 1M   | 3% on 1W/1M                |       42 |       16 |      25 |     -10.7 |        -0.67  |     -75.8 |        -4.737 |                  6.5 |
| nse      | trendline | 1w   | live (0.75% / zones 0.20%) |      100 |       85 |      29 |     -43.3 |        -0.51  |     -48.2 |        -0.567 |                  1   |
| nse      | trendline | 1w   | 3% on 1W/1M                |      121 |       86 |      35 |     -34.4 |        -0.4   |     -43.2 |        -0.502 |                  4   |
| nse      | trendline | 1M   | live (0.75% / zones 0.20%) |        7 |        6 |      50 |      -0.5 |        -0.087 |       3.5 |         0.581 |                  2   |
| nse      | trendline | 1M   | 3% on 1W/1M                |        6 |        3 |     100 |       2.8 |         0.922 |       5.7 |         1.884 |                 13   |
| nse      | zone      | 1w   | live (0.75% / zones 0.20%) |       28 |       25 |      26 |     -10.2 |        -0.408 |      -6.4 |        -0.256 |                  1   |
| nse      | zone      | 1w   | 3% on 1W/1M                |      259 |      186 |      14 |    -146.4 |        -0.787 |    -105.9 |        -0.569 |                  6   |
| nse      | zone      | 1M   | 3% on 1W/1M                |        3 |        1 |       0 |      -1.2 |        -1.157 |      -1.1 |        -1.148 |                  1   |
