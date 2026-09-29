# Fib + trendline alerts - history backtest

Generated 2026-09-29 21:26 IST by `fib_trendline_backtest.py` in 0 min. Symbols: CRYPTO 31, NSE 200.

## Rules

- **Alert**: price comes within 0.75% of a fib zone or a live trendline (down to touching it), with the live scanner's levels, once-only and re-arm rules, and the crypto 01:00-08:00 IST hold.
- **Fib trade**: entry at the zone's near edge, SL on the inner fib's 0.55 line - Shiva's EX 2 ETH trades (entry 2723.94 / SL 2711.79, 2672.86 / 2660.74).
- **Trendline trade**: entry at the line, SL 30m 0.5%, 4H 1.0%, 1D 1.5%, 1W 2.5%, 1M 3.0% beyond it.
- Limit entry, filled only from the evaluation candle after the alert and within 5 candles of the alert's timeframe; held up to 20 candles (trading candles - an NSE trade's clock stops overnight).
- Scored on finer candles: crypto 30m on 5m, 4H on 1h, 1D on 4h, 1W on 1d, 1M on 1d; NSE 30m on 5m, 4H on 1h, 1D on 1h, 1W on 1d, 1M on 1d. A candle that touches both the SL and a target counts as the SL.
- Net R subtracts the round trip (crypto 0.1%, NSE 0.1063%) divided by the trade's own risk %, so tight stops pay more R in costs.

**Win @1R** = reached 1R before the SL, out of trades that did one or the other. **Win @2R** the same for 2R. **Net R** = average result per filled trade booking everything at that target. Timeouts and still-open trades are left out of both.

**Read every win rate against the Baseline table at the end, not against 50%.** Random levels scored by these same rules win well under 50% at 1R, because a limit order only fills while price moves against it and a candle touching both SL and target counts as the SL. An alert type has an edge only where it beats the baseline for the same market and timeframe.

## Fib

| Market | TF | Alerts | Alerts/day | Filled | SL | 1R | 2R | Timeout | Open | No fill | Win @1R | Win @2R | Net R @1R | Net R @2R | Median risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CRYPTO | 30m | 2495 | 30.1 | 1294 | 845 | 112 | 335 | 2 | 3 | 1198 | 35% | 26% | -0.81R | -0.72R | 0.21% |
| CRYPTO | 4H | 1435 | 2.2 | 1146 | 771 | 96 | 279 | 0 | 2 | 287 | 33% | 24% | -0.48R | -0.40R | 1.05% |
| CRYPTO | 1D | 488 | 0.5 | 442 | 297 | 27 | 118 | 0 | 0 | 46 | 33% | 27% | -0.41R | -0.26R | 2.18% |
| CRYPTO | 1W | 120 | 0.1 | 113 | 74 | 7 | 32 | 0 | 1 | 6 | 35% | 29% | -0.34R | -0.17R | 4.14% |
| CRYPTO | 1M | 8 | 0.1 | 8 | 7 | 0 | 1 | 0 | 0 | 0 | 12% | 12% | -0.77R | -0.64R | 5.14% |
| NSE | 30m | 7899 | 96.2 | 4094 | 2694 | 389 | 1010 | 0 | 23 | 3783 | 34% | 25% | -0.88R | -0.82R | 0.21% |
| NSE | 4H | 6227 | 9.2 | 4962 | 3316 | 418 | 1227 | 0 | 17 | 1249 | 33% | 25% | -0.49R | -0.41R | 0.77% |
| NSE | 1D | 2550 | 3.7 | 2147 | 1400 | 209 | 537 | 0 | 9 | 395 | 35% | 25% | -0.41R | -0.35R | 1.13% |
| NSE | 1W | 1755 | 1.0 | 1533 | 958 | 152 | 423 | 0 | 6 | 216 | 38% | 28% | -0.29R | -0.22R | 2.66% |
| NSE | 1M | 727 | 0.4 | 673 | 378 | 94 | 201 | 0 | 1 | 53 | 44% | 30% | -0.15R | -0.12R | 5.12% |

## Trendline

| Market | TF | Alerts | Alerts/day | Filled | SL | 1R | 2R | Timeout | Open | No fill | Win @1R | Win @2R | Net R @1R | Net R @2R | Median risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CRYPTO | 30m | 9443 | 114.8 | 4747 | 2730 | 629 | 1307 | 81 | 7 | 4689 | 41% | 29% | -0.37R | -0.34R | 0.50% |
| CRYPTO | 4H | 6543 | 9.8 | 5004 | 3047 | 611 | 1342 | 3 | 3 | 1537 | 39% | 27% | -0.32R | -0.29R | 1.00% |
| CRYPTO | 1D | 1119 | 1.2 | 988 | 657 | 103 | 228 | 0 | 3 | 128 | 34% | 23% | -0.40R | -0.37R | 1.50% |
| CRYPTO | 1W | 48 | 0.1 | 45 | 33 | 3 | 8 | 0 | 1 | 3 | 25% | 18% | -0.54R | -0.49R | 2.50% |
| NSE | 30m | 17698 | 218.3 | 8876 | 5069 | 1258 | 2528 | 9 | 97 | 8737 | 43% | 29% | -0.36R | -0.35R | 0.50% |
| NSE | 4H | 16162 | 24.3 | 12484 | 7664 | 1467 | 3331 | 0 | 59 | 3641 | 39% | 27% | -0.34R | -0.30R | 1.00% |
| NSE | 1D | 9211 | 13.3 | 7662 | 4610 | 944 | 2095 | 0 | 27 | 1535 | 40% | 27% | -0.28R | -0.25R | 1.50% |
| NSE | 1W | 3003 | 1.7 | 2671 | 1696 | 315 | 656 | 0 | 13 | 323 | 36% | 25% | -0.31R | -0.30R | 2.50% |
| NSE | 1M | 303 | 0.2 | 272 | 162 | 41 | 69 | 0 | 2 | 29 | 40% | 25% | -0.23R | -0.27R | 3.00% |

## Baseline - random levels, no edge (100 per symbol and timeframe)

| Market | TF | Alerts | Alerts/day | Filled | SL | 1R | 2R | Timeout | Open | No fill | Win @1R | Win @2R | Net R @1R | Net R @2R | Median risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CRYPTO | 30m | 3100 | 37.6 | 1925 | 1092 | 258 | 555 | 20 | 0 | 1175 | 43% | 30% | -0.35R | -0.31R | 0.50% |
| CRYPTO | 4H | 3100 | 4.7 | 2658 | 1585 | 321 | 748 | 4 | 0 | 442 | 40% | 28% | -0.29R | -0.25R | 1.00% |
| CRYPTO | 1D | 3100 | 3.2 | 2967 | 1838 | 295 | 834 | 0 | 0 | 133 | 38% | 28% | -0.31R | -0.22R | 1.50% |
| CRYPTO | 1W | 2400 | 2.9 | 2367 | 1646 | 127 | 594 | 0 | 0 | 33 | 30% | 25% | -0.43R | -0.29R | 2.50% |
| CRYPTO | 1M | 1200 | 5.4 | 1187 | 729 | 91 | 367 | 0 | 0 | 13 | 39% | 31% | -0.26R | -0.11R | 3.00% |
| NSE | 30m | 20000 | 252.4 | 12862 | 7086 | 1781 | 3989 | 6 | 0 | 7138 | 45% | 31% | -0.31R | -0.28R | 0.50% |
| NSE | 4H | 20000 | 29.6 | 17740 | 9962 | 2204 | 5571 | 3 | 0 | 2260 | 44% | 31% | -0.23R | -0.16R | 1.00% |
| NSE | 1D | 20000 | 30.3 | 18281 | 9946 | 2508 | 5827 | 0 | 0 | 1719 | 46% | 32% | -0.16R | -0.11R | 1.50% |
| NSE | 1W | 20000 | 12.2 | 19278 | 10961 | 2405 | 5912 | 0 | 0 | 722 | 43% | 31% | -0.18R | -0.12R | 2.50% |
| NSE | 1M | 18100 | 17.6 | 17726 | 9765 | 2351 | 5610 | 0 | 0 | 374 | 45% | 32% | -0.14R | -0.09R | 3.00% |

## Fib - first touch vs later touches

Filled fib trades only, split by whether it was the first time price reached that fib (one base, one top) or a later touch of the same fib - the other zone, after the first had already traded. See `touch_order`.

| Market | TF | Touch | Trades | SL | 1R | 2R | Win @1R | Win @2R | Net R @1R | Net R @2R | Zone 1 share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CRYPTO | 30m | first | 940 | 611 | 80 | 247 | 35% | 26% | -0.80R | -0.71R | 89% |
| CRYPTO | 30m | later | 354 | 234 | 32 | 88 | 34% | 25% | -0.81R | -0.74R | 9% |
| CRYPTO | 4H | first | 738 | 499 | 55 | 184 | 32% | 25% | -0.49R | -0.39R | 91% |
| CRYPTO | 4H | later | 408 | 272 | 41 | 95 | 33% | 23% | -0.47R | -0.43R | 6% |
| CRYPTO | 1D | first | 280 | 192 | 15 | 73 | 31% | 26% | -0.44R | -0.28R | 96% |
| CRYPTO | 1D | later | 162 | 105 | 12 | 45 | 35% | 28% | -0.36R | -0.23R | 3% |
| CRYPTO | 1W | first | 71 | 46 | 4 | 21 | 35% | 30% | -0.32R | -0.13R | 90% |
| CRYPTO | 1W | later | 42 | 28 | 3 | 11 | 33% | 26% | -0.36R | -0.24R | 12% |
| CRYPTO | 1M | first | 5 | 5 | 0 | 0 | 0% | 0% | -1.02R | -1.02R | 40% |
| CRYPTO | 1M | later | 3 | 2 | 0 | 1 | 33% | 33% | -0.35R | -0.02R | 33% |
| NSE | 30m | first | 2924 | 1902 | 288 | 733 | 35% | 25% | -0.86R | -0.80R | 90% |
| NSE | 30m | later | 1170 | 792 | 101 | 277 | 32% | 24% | -0.94R | -0.88R | 7% |
| NSE | 4H | first | 3239 | 2159 | 264 | 816 | 33% | 25% | -0.49R | -0.40R | 95% |
| NSE | 4H | later | 1723 | 1157 | 154 | 411 | 33% | 24% | -0.50R | -0.44R | 2% |
| NSE | 1D | first | 1415 | 914 | 143 | 358 | 35% | 25% | -0.39R | -0.34R | 93% |
| NSE | 1D | later | 732 | 486 | 66 | 179 | 34% | 24% | -0.43R | -0.37R | 6% |
| NSE | 1W | first | 1037 | 657 | 103 | 277 | 37% | 27% | -0.31R | -0.24R | 96% |
| NSE | 1W | later | 496 | 301 | 49 | 146 | 39% | 29% | -0.26R | -0.16R | 5% |
| NSE | 1M | first | 479 | 270 | 73 | 136 | 44% | 29% | -0.15R | -0.17R | 94% |
| NSE | 1M | later | 194 | 108 | 21 | 65 | 44% | 34% | -0.13R | -0.02R | 12% |

947 of 87234 alert trades had a candle touching both SL and a target (scored as SL).
