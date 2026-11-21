# xStocks on Delta: fib L2-L4 + trendlines (2026-09-01 to now)

Delta candles, Delta fees (0.0826% round trip) + stop slip. Live rules: fib L2-L4 own stops 2R + BE; TL touch wick/body stop 1R; TL break entry at alert, stop past the candle before the break, 1R. Entries filled within 15 min of US CPI/PPI/FOMC left out.

## xStocks Delta lists (tested = >= 1M USD a day on both 7d and 30d)

| symbol    | base   |   7d $M/day |   30d $M/day | live   | tested   |
|:----------|:-------|------------:|-------------:|:-------|:---------|
| SNDKBUSD  | SNDKB  |        6.74 |         7.88 | True   | True     |
| SOXLBUSD  | SOXLB  |        1.68 |         2.37 | False  | True     |
| QQQXUSD   | QQQX   |        0.36 |         1.6  | True   | False    |
| NVDAXUSD  | NVDAX  |        0.71 |         1.36 | False  | False    |
| SNXXBUSD  | SNXXB  |        0.84 |         1.14 | False  | False    |
| TSLAXUSD  | TSLAX  |        0.13 |         0.87 | True   | False    |
| KORUBUSD  | KORUB  |        0.5  |         0.83 | False  | False    |
| SPCXXUSD  | SPCXX  |        0.1  |         0.58 | False  | False    |
| MVLLBUSD  | MVLLB  |        0.17 |         0.58 | False  | False    |
| TQQQBUSD  | TQQQB  |        0.56 |         0.55 | False  | False    |
| GOOGLXUSD | GOOGLX |        0.12 |         0.54 | False  | False    |
| SPYXUSD   | SPYX   |        0.16 |         0.44 | False  | False    |
| METAXUSD  | METAX  |        0.09 |         0.35 | False  | False    |
| AAPLXUSD  | AAPLX  |        0.04 |         0.29 | False  | False    |
| MUUBUSD   | MUUB   |        0.2  |         0.26 | False  | False    |
| AMZNXUSD  | AMZNX  |        0.03 |         0.23 | False  | False    |
| COINXUSD  | COINX  |        0.07 |         0.13 | False  | False    |
| CRCLXUSD  | CRCLX  |        0.03 |         0.13 | False  | False    |
| DRAMBUSD  | DRAMB  |        0.14 |         0.08 | False  | False    |
| SPYBUSD   | SPYB   |        0.3  |         0.07 | False  | False    |
| EWYBUSD   | EWYB   |        0.03 |         0.05 | False  | False    |

## All tested xStocks

| setup     | tf   |   alerts |   trades |   win_% |   R/trade |   %/trade |   R total |
|:----------|:-----|---------:|---------:|--------:|----------:|----------:|----------:|
| Fib L2-L4 | 4H   |       26 |       20 |      27 |    -0.484 |    -1.391 |      -9.7 |
| TL touch  | 4H   |       65 |       57 |      26 |    -0.57  |    -0.557 |     -32.5 |
| TL break  | 4H   |       41 |       41 |      61 |     0.166 |     0.537 |       6.8 |
| All       | 4H   |      132 |      118 |      39 |    -0.3   |    -0.318 |     -35.4 |
| Fib L2-L4 | 1D+  |        7 |        7 |      40 |    -0.441 |    -3.278 |      -3.1 |
| TL touch  | 1D+  |        7 |        7 |      43 |    -0.209 |     0.68  |      -1.5 |
| TL break  | 1D+  |        6 |        6 |      50 |    -0.009 |    -0.017 |      -0.1 |
| All       | 1D+  |       20 |       20 |      44 |    -0.23  |    -0.915 |      -4.6 |

## Live 3 (TSLA, SNDK, QQQ)

| setup     | tf   |   alerts |   trades |   win_% |   R/trade |   %/trade |   R total |
|:----------|:-----|---------:|---------:|--------:|----------:|----------:|----------:|
| Fib L2-L4 | 4H   |       10 |        8 |      17 |    -0.666 |    -1.527 |      -5.3 |
| TL touch  | 4H   |       30 |       25 |      28 |    -0.539 |    -0.822 |     -13.5 |
| TL break  | 4H   |       20 |       20 |      60 |     0.11  |     0.305 |       2.2 |
| All       | 4H   |       60 |       53 |      39 |    -0.314 |    -0.503 |     -16.6 |
| Fib L2-L4 | 1D+  |        3 |        3 |      67 |    -0.35  |    -1.479 |      -1.1 |
| TL touch  | 1D+  |        3 |        3 |      33 |    -0.398 |     0.239 |      -1.2 |
| TL break  | 1D+  |        2 |        2 |      50 |    -0.013 |    -0.051 |      -0   |
| All       | 1D+  |        8 |        8 |      50 |    -0.284 |    -0.478 |      -2.3 |

## Not on the watchlist yet

| setup     | tf   |   alerts |   trades |   win_% |   R/trade |   %/trade |   R total |
|:----------|:-----|---------:|---------:|--------:|----------:|----------:|----------:|
| Fib L2-L4 | 4H   |       16 |       12 |      33 |    -0.362 |    -1.301 |      -4.3 |
| TL touch  | 4H   |       35 |       32 |      25 |    -0.594 |    -0.351 |     -19   |
| TL break  | 4H   |       21 |       21 |      62 |     0.219 |     0.759 |       4.6 |
| All       | 4H   |       72 |       65 |      39 |    -0.289 |    -0.168 |     -18.8 |
| Fib L2-L4 | 1D+  |        4 |        4 |       0 |    -0.509 |    -4.628 |      -2   |
| TL touch  | 1D+  |        4 |        4 |      50 |    -0.066 |     1.01  |      -0.3 |
| TL break  | 1D+  |        4 |        4 |      50 |    -0.008 |     0     |      -0   |
| All       | 1D+  |       12 |       12 |      40 |    -0.194 |    -1.206 |      -2.3 |

## Per symbol (all setups)

| symbol   | tf   |   trades |   win_% |   R/trade |   %/trade |   R total |
|:---------|:-----|---------:|--------:|----------:|----------:|----------:|
| SNDKBUSD | 4H   |       53 |      39 |    -0.314 |    -0.503 |     -16.6 |
| SNDKBUSD | 1D+  |        8 |      50 |    -0.284 |    -0.478 |      -2.3 |
| SOXLBUSD | 4H   |       65 |      39 |    -0.289 |    -0.168 |     -18.8 |
| SOXLBUSD | 1D+  |       12 |      40 |    -0.194 |    -1.206 |      -2.3 |
