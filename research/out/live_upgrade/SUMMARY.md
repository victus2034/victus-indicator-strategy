# Live bot upgrade replay - breaks only, break stop, kill switch

Source: `research/out/journal_tl_setup/trades_2025-01-01.json` (bot's exits, 16 crypto, 1 Jan 2025 - 13 Nov 2026, fees + stop slip, fills within 15 min of CPI / PPI / FOMC left out). Account rules as `coindcx_live.py`: one trade per coin, at most 5 open. R per trade at the fixed risk.

## The changes

| Set | Taken | Skipped | Win | Total R | R/trade | PF | Max DD | Worst run | Months up | Avg SL | Kill switch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Before: touch + break, 10R loss from start | 48 | 1223 | 42% | -7.5R | -0.157R | 0.75 | -12.7R | 8 | 0/1 | 3.5% | 2025-01-27 |
| Before, no kill switch | 910 | 361 | 48% | -71.2R | -0.078R | 0.86 | -83.7R | 10 | 7/23 | 3.9% | never |
| Breaks only, wick/body SL (default) | 393 | 110 | 60% | +69.4R | +0.177R | 1.43 | -13.2R | 7 | 18/23 | 6.5% | never |
| Breaks only, alert's own SL (BREAK_SL=alert) | 277 | 225 | 60% | +58.1R | +0.210R | 1.52 | -13.9R | 11 | 18/23 | 10.7% | never |
| Default + kill switch 15R from the best point | 393 | 110 | 60% | +69.4R | +0.177R | 1.43 | -13.2R | 7 | 18/23 | 6.5% | never |
| Alert SL + kill switch 15R from the best point | 277 | 225 | 60% | +58.1R | +0.210R | 1.52 | -13.9R | 11 | 18/23 | 10.7% | never |

Why the alert's SL is not the default: it is better a trade, but its stops are wider, so trades last longer and hold the 5 slots; fewer breaks get in and the total is lower.

## Max open trades (breaks only)

| Set | Taken | Skipped | Win | Total R | R/trade | PF | Max DD | Worst run | Months up | Avg SL | Kill switch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| wick/body, at most 5 open | 393 | 110 | 60% | +69.4R | +0.177R | 1.43 | -13.2R | 7 | 18/23 | 6.5% | never |
| wick/body, at most 8 open | 419 | 84 | 59% | +65.5R | +0.156R | 1.37 | -13.2R | 7 | 15/23 | 7.0% | never |
| wick/body, at most 10 open | 421 | 82 | 59% | +65.4R | +0.155R | 1.37 | -13.2R | 7 | 15/23 | 7.2% | never |
| wick/body, no limit (one per coin) | 426 | 77 | 59% | +67.0R | +0.157R | 1.37 | -13.2R | 7 | 15/23 | 7.1% | never |
| alert SL, at most 5 open | 277 | 225 | 60% | +58.1R | +0.210R | 1.52 | -13.9R | 11 | 18/23 | 10.7% | never |
| alert SL, at most 8 open | 343 | 159 | 60% | +71.1R | +0.207R | 1.51 | -16.7R | 13 | 19/23 | 11.1% | never |
| alert SL, at most 10 open | 355 | 147 | 60% | +74.5R | +0.210R | 1.52 | -16.7R | 13 | 17/23 | 11.3% | never |
| alert SL, no limit (one per coin) | 360 | 142 | 59% | +68.7R | +0.191R | 1.46 | -16.7R | 13 | 17/23 | 11.4% | never |

## Kill switch variants (breaks only)

| Set | Taken | Skipped | Win | Total R | R/trade | PF | Max DD | Worst run | Months up | Avg SL | Kill switch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| wick/body, 10R loss from start (old rule) | 393 | 110 | 60% | +69.4R | +0.177R | 1.43 | -13.2R | 7 | 18/23 | 6.5% | never |
| wick/body, 10R from the best point | 258 | 245 | 57% | +29.7R | +0.115R | 1.26 | -11.2R | 7 | 11/16 | 6.9% | 2026-04-03 |
| wick/body, 15R from the best point | 393 | 110 | 60% | +69.4R | +0.177R | 1.43 | -13.2R | 7 | 18/23 | 6.5% | never |
| wick/body, 15R + no new trade after 2R lost in 24h | 389 | 114 | 60% | +64.9R | +0.167R | 1.40 | -12.2R | 7 | 18/23 | 6.4% | never |
| wick/body, 15R + no new trade after 3R lost in 24h | 392 | 111 | 60% | +70.4R | +0.180R | 1.43 | -12.2R | 7 | 18/23 | 6.5% | never |
| alert SL, 10R loss from start (old rule) | 277 | 225 | 60% | +58.1R | +0.210R | 1.52 | -13.9R | 11 | 18/23 | 10.7% | never |
| alert SL, 10R from the best point | 191 | 311 | 57% | +32.1R | +0.168R | 1.39 | -14.6R | 12 | 10/15 | 11.4% | 2026-03-31 |
| alert SL, 15R from the best point | 277 | 225 | 60% | +58.1R | +0.210R | 1.52 | -13.9R | 11 | 18/23 | 10.7% | never |
| alert SL, 15R + no new trade after 2R lost in 24h | 271 | 231 | 61% | +61.6R | +0.227R | 1.57 | -10.1R | 7 | 18/23 | 10.7% | never |
| alert SL, 15R + no new trade after 3R lost in 24h | 276 | 226 | 60% | +59.2R | +0.214R | 1.53 | -12.9R | 10 | 18/23 | 10.7% | never |

A 24h loss cap is not used: 2R helps the alert SL and hurts wick/body, 3R moves under 1R - noise.

## Robustness (breaks only, wick/body SL - default)

| Set | Taken | Skipped | Win | Total R | R/trade | PF | Max DD | Worst run | Months up | Avg SL | Kill switch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Jan - Nov 2025 | 191 | 69 | 58% | +24.3R | +0.127R | 1.29 | -9.7R | 7 | 8/11 | 7.1% | never |
| Dec 2025 - Nov 2026 | 202 | 41 | 62% | +45.1R | +0.223R | 1.56 | -13.2R | 6 | 10/12 | 6.0% | never |
| Buy breaks (RS TL BR) | 192 | 44 | 62% | +45.3R | +0.236R | 1.60 | -12.1R | 6 | 14/22 | 7.0% | never |
| Sell breaks (SP TL BR) | 211 | 56 | 60% | +32.7R | +0.155R | 1.37 | -12.2R | 5 | 15/22 | 6.0% | never |

## Robustness (breaks only, alert's own SL)

| Set | Taken | Skipped | Win | Total R | R/trade | PF | Max DD | Worst run | Months up | Avg SL | Kill switch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Jan - Nov 2025 | 138 | 122 | 59% | +32.8R | +0.237R | 1.58 | -6.4R | 5 | 8/11 | 11.7% | never |
| Dec 2025 - Nov 2026 | 141 | 101 | 60% | +26.5R | +0.188R | 1.46 | -13.9R | 11 | 10/12 | 9.6% | never |
| Buy breaks (RS TL BR) | 168 | 68 | 60% | +35.7R | +0.213R | 1.52 | -9.1R | 7 | 12/22 | 10.6% | never |
| Sell breaks (SP TL BR) | 168 | 98 | 62% | +42.3R | +0.252R | 1.65 | -15.2R | 7 | 17/22 | 10.4% | never |
