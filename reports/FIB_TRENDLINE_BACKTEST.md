# Fib + trendline alerts - history backtest

Generated 2026-09-29 20:01 IST by `fib_trendline_backtest.py` in 2 min. Symbols: CRYPTO 31, NSE 200.

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
| CRYPTO | 30m | 3511 | 42.4 | 1200 | 783 | 98 | 317 | 2 | 3 | 2308 | 35% | 27% | -0.82R | -0.72R | 0.21% |
| CRYPTO | 4H | 1678 | 2.5 | 1112 | 737 | 94 | 281 | 0 | 6 | 560 | 34% | 25% | -0.46R | -0.37R | 0.95% |
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
| CRYPTO | 30m | 9540 | 116.0 | 2899 | 1766 | 334 | 765 | 33 | 18 | 6624 | 38% | 27% | -0.43R | -0.39R | 0.50% |
| CRYPTO | 4H | 7249 | 11.0 | 4352 | 2599 | 510 | 1240 | 2 | 5 | 2893 | 40% | 29% | -0.30R | -0.24R | 1.00% |
| CRYPTO | 1D | 1216 | 1.3 | 1016 | 669 | 107 | 240 | 0 | 4 | 196 | 34% | 24% | -0.38R | -0.36R | 1.50% |
| CRYPTO | 1W | 45 | 0.1 | 42 | 30 | 3 | 8 | 0 | 1 | 3 | 27% | 20% | -0.50R | -0.45R | 2.50% |
| NSE | 30m | 17871 | 220.5 | 4941 | 2841 | 673 | 1414 | 7 | 119 | 12817 | 42% | 29% | -0.37R | -0.35R | 0.50% |
| NSE | 4H | 18601 | 27.9 | 11545 | 7006 | 1348 | 3167 | 0 | 101 | 6979 | 39% | 28% | -0.32R | -0.28R | 1.00% |
| NSE | 1D | 10599 | 15.3 | 7489 | 4505 | 935 | 2031 | 0 | 68 | 3060 | 40% | 27% | -0.28R | -0.25R | 1.50% |
| NSE | 1W | 3265 | 1.8 | 2777 | 1688 | 330 | 750 | 0 | 23 | 474 | 39% | 27% | -0.26R | -0.23R | 2.50% |
| NSE | 1M | 314 | 0.2 | 280 | 156 | 45 | 79 | 0 | 2 | 32 | 44% | 28% | -0.15R | -0.19R | 3.00% |

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

972 of 99698 alert trades had a candle touching both SL and a target (scored as SL).
