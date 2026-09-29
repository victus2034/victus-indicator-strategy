# Fib + trendline alerts - history backtest

Generated 2026-09-29 20:23 IST by `fib_trendline_backtest.py` in 1 min. Symbols: CRYPTO 31, NSE 200.

## Rules

- **Alert**: price comes within 1.5% of a fib zone or a live trendline (down to touching it), with the live scanner's levels, once-only and re-arm rules, and the crypto 01:00-08:00 IST hold.
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
| CRYPTO | 30m | 3514 | 42.4 | 1200 | 783 | 98 | 317 | 2 | 6 | 2308 | 35% | 27% | -0.82R | -0.72R | 0.21% |
| CRYPTO | 4H | 1659 | 2.5 | 1099 | 725 | 96 | 278 | 0 | 6 | 554 | 34% | 25% | -0.45R | -0.37R | 0.94% |
| CRYPTO | 1D | 526 | 0.5 | 450 | 291 | 30 | 129 | 0 | 1 | 75 | 35% | 29% | -0.36R | -0.20R | 2.14% |
| CRYPTO | 1W | 125 | 0.2 | 115 | 74 | 6 | 35 | 0 | 3 | 7 | 36% | 31% | -0.32R | -0.11R | 4.14% |
| CRYPTO | 1M | 8 | 0.1 | 8 | 7 | 0 | 1 | 0 | 0 | 0 | 12% | 12% | -0.77R | -0.64R | 5.14% |
| NSE | 30m | 12386 | 150.9 | 3951 | 2621 | 351 | 978 | 0 | 35 | 8401 | 34% | 25% | -0.92R | -0.85R | 0.21% |
| NSE | 4H | 7305 | 10.8 | 4864 | 3172 | 402 | 1289 | 0 | 23 | 2419 | 35% | 27% | -0.47R | -0.37R | 0.73% |
| NSE | 1D | 2858 | 4.1 | 2121 | 1354 | 208 | 558 | 0 | 14 | 724 | 36% | 26% | -0.38R | -0.31R | 1.10% |
| NSE | 1W | 1847 | 1.0 | 1558 | 936 | 158 | 464 | 0 | 5 | 284 | 40% | 30% | -0.25R | -0.15R | 2.61% |
| NSE | 1M | 754 | 0.4 | 678 | 374 | 95 | 209 | 0 | 4 | 72 | 45% | 31% | -0.13R | -0.10R | 5.10% |

## Trendline

| Market | TF | Alerts | Alerts/day | Filled | SL | 1R | 2R | Timeout | Open | No fill | Win @1R | Win @2R | Net R @1R | Net R @2R | Median risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CRYPTO | 30m | 10343 | 125.7 | 3619 | 2155 | 438 | 956 | 69 | 19 | 6706 | 39% | 27% | -0.41R | -0.38R | 0.50% |
| CRYPTO | 4H | 7607 | 11.4 | 4651 | 2777 | 535 | 1336 | 2 | 5 | 2952 | 40% | 29% | -0.29R | -0.24R | 1.00% |
| CRYPTO | 1D | 1255 | 1.4 | 1049 | 683 | 115 | 251 | 0 | 5 | 201 | 35% | 24% | -0.37R | -0.35R | 1.50% |
| CRYPTO | 1W | 46 | 0.1 | 43 | 31 | 4 | 7 | 0 | 1 | 3 | 26% | 17% | -0.52R | -0.54R | 2.50% |
| NSE | 30m | 19003 | 234.4 | 5970 | 3386 | 828 | 1739 | 10 | 125 | 12915 | 43% | 30% | -0.35R | -0.33R | 0.50% |
| NSE | 4H | 19005 | 28.5 | 11917 | 7154 | 1419 | 3320 | 0 | 101 | 7011 | 40% | 28% | -0.31R | -0.27R | 1.00% |
| NSE | 1D | 11091 | 16.0 | 7950 | 4658 | 1040 | 2233 | 0 | 69 | 3091 | 41% | 28% | -0.25R | -0.23R | 1.50% |
| NSE | 1W | 3315 | 1.8 | 2819 | 1705 | 340 | 765 | 0 | 24 | 481 | 39% | 27% | -0.26R | -0.23R | 2.50% |
| NSE | 1M | 316 | 0.2 | 281 | 155 | 46 | 80 | 0 | 2 | 33 | 45% | 28% | -0.14R | -0.18R | 3.00% |

## Baseline - random levels, no edge (100 per symbol and timeframe)

| Market | TF | Alerts | Alerts/day | Filled | SL | 1R | 2R | Timeout | Open | No fill | Win @1R | Win @2R | Net R @1R | Net R @2R | Median risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CRYPTO | 30m | 3100 | 37.6 | 1322 | 768 | 161 | 390 | 3 | 0 | 1778 | 42% | 30% | -0.36R | -0.30R | 0.50% |
| CRYPTO | 4H | 3100 | 4.7 | 2355 | 1437 | 249 | 669 | 0 | 0 | 745 | 39% | 28% | -0.32R | -0.25R | 1.00% |
| CRYPTO | 1D | 3100 | 3.2 | 2836 | 1778 | 251 | 807 | 0 | 0 | 264 | 37% | 28% | -0.32R | -0.21R | 1.50% |
| CRYPTO | 1W | 2400 | 2.9 | 2332 | 1625 | 139 | 568 | 0 | 0 | 68 | 30% | 24% | -0.43R | -0.31R | 2.50% |
| CRYPTO | 1M | 1200 | 5.4 | 1182 | 738 | 87 | 357 | 0 | 0 | 18 | 38% | 30% | -0.28R | -0.13R | 3.00% |
| NSE | 30m | 20000 | 252.4 | 8069 | 4513 | 1098 | 2455 | 3 | 0 | 11931 | 44% | 31% | -0.33R | -0.30R | 0.50% |
| NSE | 4H | 20000 | 29.6 | 15747 | 8996 | 1969 | 4782 | 0 | 0 | 4253 | 43% | 30% | -0.25R | -0.20R | 1.00% |
| NSE | 1D | 20000 | 30.3 | 16822 | 9237 | 2272 | 5313 | 0 | 0 | 3178 | 45% | 32% | -0.17R | -0.12R | 1.50% |
| NSE | 1W | 20000 | 12.2 | 18804 | 10526 | 2448 | 5830 | 0 | 0 | 1196 | 44% | 31% | -0.16R | -0.11R | 2.50% |
| NSE | 1M | 18100 | 17.6 | 17508 | 9498 | 2367 | 5643 | 0 | 0 | 592 | 46% | 32% | -0.12R | -0.07R | 3.00% |

## Fib - first touch vs later touches

Filled fib trades only, split by whether it was the first time price reached that fib (one base, one top) or a later touch of the same fib - the other zone, after the first had already traded. See `touch_order`.

| Market | TF | Touch | Trades | SL | 1R | 2R | Win @1R | Win @2R | Net R @1R | Net R @2R | Zone 1 share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CRYPTO | 30m | first | 890 | 576 | 72 | 240 | 35% | 27% | -0.81R | -0.70R | 90% |
| CRYPTO | 30m | later | 310 | 207 | 26 | 77 | 33% | 25% | -0.87R | -0.79R | 10% |
| CRYPTO | 4H | first | 741 | 485 | 62 | 194 | 35% | 26% | -0.45R | -0.35R | 91% |
| CRYPTO | 4H | later | 358 | 240 | 34 | 84 | 33% | 24% | -0.47R | -0.43R | 7% |
| CRYPTO | 1D | first | 285 | 188 | 17 | 80 | 34% | 28% | -0.38R | -0.22R | 96% |
| CRYPTO | 1D | later | 165 | 103 | 13 | 49 | 38% | 30% | -0.31R | -0.17R | 3% |
| CRYPTO | 1W | first | 73 | 46 | 3 | 24 | 37% | 33% | -0.29R | -0.03R | 90% |
| CRYPTO | 1W | later | 42 | 28 | 3 | 11 | 33% | 26% | -0.36R | -0.24R | 12% |
| CRYPTO | 1M | first | 5 | 5 | 0 | 0 | 0% | 0% | -1.02R | -1.02R | 40% |
| CRYPTO | 1M | later | 3 | 2 | 0 | 1 | 33% | 33% | -0.35R | -0.02R | 33% |
| NSE | 30m | first | 2921 | 1919 | 272 | 729 | 34% | 25% | -0.88R | -0.82R | 92% |
| NSE | 30m | later | 1030 | 702 | 79 | 249 | 32% | 24% | -1.02R | -0.94R | 7% |
| NSE | 4H | first | 3361 | 2179 | 273 | 908 | 35% | 27% | -0.46R | -0.35R | 94% |
| NSE | 4H | later | 1503 | 993 | 129 | 381 | 34% | 25% | -0.49R | -0.40R | 2% |
| NSE | 1D | first | 1447 | 910 | 148 | 389 | 37% | 27% | -0.36R | -0.30R | 92% |
| NSE | 1D | later | 674 | 444 | 60 | 169 | 34% | 25% | -0.43R | -0.35R | 6% |
| NSE | 1W | first | 1060 | 644 | 110 | 306 | 39% | 29% | -0.26R | -0.18R | 96% |
| NSE | 1W | later | 498 | 292 | 48 | 158 | 41% | 32% | -0.22R | -0.09R | 5% |
| NSE | 1M | first | 484 | 269 | 73 | 142 | 44% | 29% | -0.14R | -0.14R | 94% |
| NSE | 1M | later | 194 | 105 | 22 | 67 | 46% | 35% | -0.10R | +0.01R | 12% |

1013 of 102963 alert trades had a candle touching both SL and a target (scored as SL).
