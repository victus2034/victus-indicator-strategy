# xStocks on Delta: fib L2-L4 + trendlines (2026-09-01 to now)

Delta candles, Delta fees (0.0826% round trip) + stop slip. Live rules: fib L2-L4 own stops 2R + BE; TL touch wick/body stop 1R; TL break entry at alert, stop past the candle before the break, 1R. Entries filled within 15 min of US CPI/PPI/FOMC left out.

## xStocks Delta lists (tested = >= 0.1M USD a day on both 7d and 30d)

| symbol    | base   |   7d $M/day |   30d $M/day | live   | tested   |
|:----------|:-------|------------:|-------------:|:-------|:---------|
| SNDKBUSD  | SNDKB  |        6.74 |         7.88 | True   | True     |
| SOXLBUSD  | SOXLB  |        1.68 |         2.37 | False  | True     |
| QQQXUSD   | QQQX   |        0.36 |         1.6  | True   | True     |
| NVDAXUSD  | NVDAX  |        0.71 |         1.36 | False  | True     |
| SNXXBUSD  | SNXXB  |        0.84 |         1.14 | False  | True     |
| TSLAXUSD  | TSLAX  |        0.13 |         0.87 | True   | True     |
| KORUBUSD  | KORUB  |        0.5  |         0.83 | False  | True     |
| SPCXXUSD  | SPCXX  |        0.1  |         0.58 | False  | False    |
| MVLLBUSD  | MVLLB  |        0.17 |         0.58 | False  | True     |
| TQQQBUSD  | TQQQB  |        0.56 |         0.55 | False  | True     |
| GOOGLXUSD | GOOGLX |        0.12 |         0.54 | False  | True     |
| SPYXUSD   | SPYX   |        0.16 |         0.44 | False  | True     |
| METAXUSD  | METAX  |        0.09 |         0.35 | False  | False    |
| AAPLXUSD  | AAPLX  |        0.04 |         0.29 | False  | False    |
| MUUBUSD   | MUUB   |        0.2  |         0.26 | False  | True     |
| AMZNXUSD  | AMZNX  |        0.03 |         0.23 | False  | False    |
| COINXUSD  | COINX  |        0.07 |         0.13 | False  | False    |
| CRCLXUSD  | CRCLX  |        0.03 |         0.13 | False  | False    |
| DRAMBUSD  | DRAMB  |        0.14 |         0.08 | False  | False    |
| SPYBUSD   | SPYB   |        0.3  |         0.07 | False  | False    |
| EWYBUSD   | EWYB   |        0.03 |         0.05 | False  | False    |

## All tested xStocks

| setup     | tf   |   alerts |   trades |   win_% |   R/trade |   %/trade |   R total |
|:----------|:-----|---------:|---------:|--------:|----------:|----------:|----------:|
| Fib L2-L4 | 4H   |      317 |      153 |      41 |    -0.275 |    -0.123 |     -42   |
| TL touch  | 4H   |      447 |      261 |      40 |    -0.308 |    -0.175 |     -80.4 |
| TL break  | 4H   |      179 |      177 |      52 |    -0.066 |    -0.297 |     -11.8 |
| All       | 4H   |      943 |      591 |      44 |    -0.227 |    -0.198 |    -134.2 |
| Fib L2-L4 | 1D+  |       69 |       57 |      41 |    -0.318 |    -0.646 |     -18.2 |
| TL touch  | 1D+  |       55 |       48 |      40 |    -0.318 |    -0.148 |     -15.2 |
| TL break  | 1D+  |       29 |       28 |      36 |    -0.324 |    -1.533 |      -9.1 |
| All       | 1D+  |      153 |      133 |      39 |    -0.319 |    -0.653 |     -42.5 |

## Live 3 (TSLA, SNDK, QQQ)

| setup     | tf   |   alerts |   trades |   win_% |   R/trade |   %/trade |   R total |
|:----------|:-----|---------:|---------:|--------:|----------:|----------:|----------:|
| Fib L2-L4 | 4H   |      105 |       52 |      41 |    -0.364 |    -0.4   |     -18.9 |
| TL touch  | 4H   |      165 |      103 |      40 |    -0.315 |    -0.438 |     -32.4 |
| TL break  | 4H   |       71 |       71 |      54 |    -0.068 |    -0.293 |      -4.8 |
| All       | 4H   |      341 |      226 |      45 |    -0.249 |    -0.383 |     -56.2 |
| Fib L2-L4 | 1D+  |       22 |       15 |      58 |     0.026 |     0.223 |       0.4 |
| TL touch  | 1D+  |       19 |       19 |      21 |    -0.696 |    -0.56  |     -13.2 |
| TL break  | 1D+  |       12 |       12 |      17 |    -0.696 |    -4.183 |      -8.3 |
| All       | 1D+  |       53 |       46 |      30 |    -0.46  |    -1.25  |     -21.2 |

## Not on the watchlist yet

| setup     | tf   |   alerts |   trades |   win_% |   R/trade |   %/trade |   R total |
|:----------|:-----|---------:|---------:|--------:|----------:|----------:|----------:|
| Fib L2-L4 | 4H   |      212 |      101 |      41 |    -0.229 |     0.019 |     -23.1 |
| TL touch  | 4H   |      282 |      158 |      40 |    -0.304 |    -0.004 |     -48   |
| TL break  | 4H   |      108 |      106 |      51 |    -0.065 |    -0.3   |      -6.9 |
| All       | 4H   |      602 |      365 |      44 |    -0.214 |    -0.084 |     -78   |
| Fib L2-L4 | 1D+  |       47 |       42 |      34 |    -0.442 |    -0.957 |     -18.5 |
| TL touch  | 1D+  |       36 |       29 |      52 |    -0.07  |     0.122 |      -2   |
| TL break  | 1D+  |       17 |       16 |      50 |    -0.045 |     0.455 |      -0.7 |
| All       | 1D+  |      100 |       87 |      44 |    -0.245 |    -0.338 |     -21.3 |

## Per symbol (all setups)

| symbol    | tf   |   trades |   win_% |   R/trade |   %/trade |   R total |
|:----------|:-----|---------:|--------:|----------:|----------:|----------:|
| SNDKBUSD  | 4H   |       53 |      39 |    -0.314 |    -0.503 |     -16.6 |
| SNDKBUSD  | 1D+  |        8 |      50 |    -0.284 |    -0.478 |      -2.3 |
| SOXLBUSD  | 4H   |       65 |      39 |    -0.289 |    -0.168 |     -18.8 |
| SOXLBUSD  | 1D+  |       12 |      40 |    -0.194 |    -1.206 |      -2.3 |
| QQQXUSD   | 4H   |       88 |      48 |    -0.246 |    -0.095 |     -21.7 |
| QQQXUSD   | 1D+  |       14 |      33 |    -0.287 |    -0.495 |      -4   |
| NVDAXUSD  | 4H   |       65 |      36 |    -0.374 |    -0.386 |     -24.3 |
| NVDAXUSD  | 1D+  |       21 |      37 |    -0.484 |    -0.608 |     -10.2 |
| SNXXBUSD  | 4H   |        2 |      50 |    -0.023 |    -1.222 |      -0   |
| TSLAXUSD  | 4H   |       85 |      45 |    -0.211 |    -0.608 |     -17.9 |
| TSLAXUSD  | 1D+  |       24 |      22 |    -0.62  |    -1.948 |     -14.9 |
| KORUBUSD  | 4H   |       34 |      27 |    -0.423 |    -1.989 |     -14.4 |
| MVLLBUSD  | 4H   |        6 |      33 |    -0.199 |     4.348 |      -1.2 |
| TQQQBUSD  | 4H   |       19 |      44 |    -0.308 |    -0.293 |      -5.9 |
| GOOGLXUSD | 4H   |       93 |      55 |    -0.002 |     0.586 |      -0.2 |
| GOOGLXUSD | 1D+  |        9 |      56 |     0.012 |     0.213 |       0.1 |
| SPYXUSD   | 4H   |       69 |      43 |    -0.287 |    -0.161 |     -19.8 |
| SPYXUSD   | 1D+  |       45 |      46 |    -0.198 |    -0.09  |      -8.9 |
| MUUBUSD   | 4H   |       12 |      64 |     0.541 |     0.973 |       6.5 |
