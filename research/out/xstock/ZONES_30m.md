# Zones 30m: Delta vs Bitunix candles

Window: last 60 days to 2026-10-09 21:45 IST; 6 crypto symbols both venues serve. Fees: Delta in every row.

## Candles (evaluation window, closed bars)

| symbol         | tf   |   common_bars |   delta_missing |   bitunix_missing |   close_diff_med_pct |   range_ratio_med |   vol_ratio_bitunix_to_delta |   delta_thin_pct |   bitunix_thin_pct |   delta_zero_vol |   bitunix_zero_vol |   delta_wick_outliers |   bitunix_wick_outliers |   okx_bars |   delta_only_wicks |   bitunix_only_wicks |
|:---------------|:-----|--------------:|----------------:|------------------:|---------------------:|------------------:|-----------------------------:|-----------------:|-------------------:|-----------------:|-------------------:|----------------------:|------------------------:|-----------:|-------------------:|---------------------:|
| TSLAXUSD       | 30m  |          2866 |               0 |                13 |                0.108 |             0.714 |                       13.092 |           20.237 |              0.977 |              157 |                  0 |                  1792 |                    2415 |   2866.000 |           1708.000 |               78.000 |
| METAXUSD       | 30m  |          2866 |               0 |                13 |                0.062 |             0.607 |                        5.435 |           24.320 |              0.035 |              273 |                  0 |                   980 |                    2107 |    nan     |            nan     |              nan     |
| SOXLBUSD       | 30m  |          2866 |               0 |                13 |                0.116 |             0.806 |                       15.569 |           15.911 |             10.502 |               86 |                  0 |                   308 |                    1248 |    nan     |            nan     |              nan     |
| SNDKBUSD       | 30m  |          2866 |               0 |                13 |                0.102 |             0.899 |                       18.332 |           11.619 |              6.141 |               12 |                  0 |                   842 |                    1380 |    nan     |            nan     |              nan     |
| MRVL/USDT:USDT | 30m  |          2866 |               0 |                13 |                0.066 |             0.244 |                        5.817 |           28.856 |              0.000 |              615 |                  0 |                   141 |                    1936 |   2866.000 |            128.000 |              127.000 |
| NVDAXUSD       | 30m  |          2866 |               0 |                13 |                0.089 |             0.763 |                       10.385 |           20.586 |              2.338 |              190 |                  0 |                  1703 |                    2378 |   2866.000 |           1512.000 |              346.000 |

## Alert replay

| alerts_from   | graded_on   |   alerts |   filled |   SL |   BE |   +1R |   +2R |   Neither |   ambiguous |   win_pct |   net_R |   R_per_trade |
|:--------------|:------------|---------:|---------:|-----:|-----:|------:|------:|----------:|------------:|----------:|--------:|--------------:|
| delta         | delta       |      410 |      167 |   83 |   50 |     5 |    23 |         6 |           4 |      25.2 |   -68.7 |        -0.412 |
| delta         | bitunix     |      409 |      164 |   81 |   47 |     3 |    25 |         8 |           9 |      25.7 |   -62.9 |        -0.384 |
| bitunix       | delta       |      455 |      210 |  108 |   57 |     6 |    33 |         6 |           7 |      26.5 |   -83.1 |        -0.396 |
| bitunix       | bitunix     |      457 |      216 |   99 |   72 |     3 |    36 |         6 |           6 |      28.3 |   -67.1 |        -0.311 |
| delta only    | delta       |      105 |       36 |   19 |    8 |     2 |     5 |         2 |           0 |      26.9 |   -16.4 |        -0.456 |
| bitunix only  | delta       |      153 |       51 |   33 |   10 |     1 |     5 |         2 |           0 |      15.4 |   -34.7 |        -0.681 |
