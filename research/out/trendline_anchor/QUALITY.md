# Trendline lines: old (v12.4) vs new (v12.5)

Same candles as the backtests (Delta for crypto, Yahoo for NSE), length 10, live timeframes. Cut-through = a candle between the two anchors is through the line. Twins = another line starts from the same candle. Far = anchors more than 100 bars apart. Held = first touch after the line appears, no close through it on that candle or the next 3.

| market | tf | rule | lines | cut-through | twins | far | median span | touched | held at 1st touch |
|---|---|---|---|---|---|---|---|---|---|
| crypto | 4h | old (v12.4) | 5582 | 18% | 87% | 47% | 89.0 | 4691 | 23% |
| crypto | 4h | new (v12.5) | 3259 | 0% | 0% | 0% | 26 | 2687 | 22% |
| crypto | 1d | old (v12.4) | 806 | 19% | 83% | 35% | 65.0 | 642 | 23% |
| crypto | 1d | new (v12.5) | 517 | 0% | 0% | 0% | 27 | 417 | 25% |
| crypto | 1w | old (v12.4) | 36 | 17% | 56% | 0% | 35.0 | 21 | 43% |
| crypto | 1w | new (v12.5) | 26 | 0% | 0% | 0% | 35.0 | 14 | 36% |
| crypto | 1M | old (v12.4) | 0 | - | - | - | - | 0 | - |
| crypto | 1M | new (v12.5) | 0 | - | - | - | - | 0 | - |
| crypto | all | old (v12.4) | 6424 | 18% | 86% | 45% | 84.0 | 5354 | 23% |
| crypto | all | new (v12.5) | 3802 | 0% | 0% | 0% | 27.0 | 3118 | 22% |
| nse | 4h | old (v12.4) | 9010 | 21% | 83% | 41% | 75.0 | 7601 | 24% |
| nse | 4h | new (v12.5) | 5378 | 0% | 0% | 0% | 27.0 | 4449 | 23% |
| nse | 1d | old (v12.4) | 41136 | 22% | 84% | 45% | 86.0 | 36309 | 29% |
| nse | 1d | new (v12.5) | 24154 | 0% | 0% | 0% | 26.0 | 20739 | 29% |
| nse | 1w | old (v12.4) | 7078 | 26% | 82% | 38% | 71.0 | 5687 | 26% |
| nse | 1w | new (v12.5) | 4484 | 0% | 0% | 1% | 27.0 | 3607 | 26% |
| nse | 1M | old (v12.4) | 927 | 32% | 59% | 12% | 43 | 561 | 22% |
| nse | 1M | new (v12.5) | 720 | 0% | 0% | 0% | 27.0 | 456 | 22% |
| nse | all | old (v12.4) | 58151 | 22% | 84% | 43% | 80 | 50158 | 28% |
| nse | all | new (v12.5) | 34736 | 0% | 0% | 0% | 26.0 | 29251 | 28% |
