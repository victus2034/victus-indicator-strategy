# Backtest audit - stored vs re-simulated (current code)

| market | tf | stored trades | stored net R | resim trades | resim net R | resim trail R |
|---|---|---|---|---|---|---|
| CRYPTO | 30m | 30 | -22.5 | 34 | -21.3 | -19.8 |
| CRYPTO | 4h | 6 | -0.5 | 6 | -0.3 | +1.4 |
| NSE | 30m | 47 | -19.3 | 46 | -23.9 | -25.5 |
| NSE | 4h | 30 | -7.0 | 30 | -7.9 | -13.2 |
| OTHER | 30m | 1 | -1.4 | 1 | -1.4 | -1.4 |
| XSTOCK | 30m | 6 | +1.5 | 6 | +0.6 | +2.2 |
| XSTOCK | 4h | 3 | +0.5 | 3 | +0.5 | +0.7 |

Rows that grade differently now: 33

## Transitions (stored -> resim), changed only

| market | tf | stored | resim | n |
|---|---|---|---|---|
| XSTOCK | 30m | alert_before_data | no_candles | 7 |
| CRYPTO | 30m | alert_before_data | zone_not_touched | 4 |
| CRYPTO | 30m | alert_before_data | data_missing | 3 |
| NSE | 30m | +1R | BE | 3 |
| NSE | 30m | BE | Neither | 3 |
| CRYPTO | 30m | zone_not_touched | +2R | 1 |
| CRYPTO | 30m | alert_before_data | +2R | 1 |
| CRYPTO | 30m | alert_before_data | BE | 1 |
| CRYPTO | 30m | alert_before_data | SL | 1 |
| CRYPTO | 30m | +1R | BE | 1 |
| XSTOCK | 30m | +1R | BE | 1 |
| CRYPTO | 4h | Neither | BE | 1 |
| XSTOCK | 4h | immature | no_candles | 1 |
| OTHER | 4h | alert_before_data | zone_not_touched | 1 |
| NSE | 30m | BE | data_quality_ambiguous | 1 |
| NSE | 30m | BE | SL | 1 |
| NSE | 4h | +1R | BE | 1 |

## Independent reference vs production: 3 disagreements

| production | reference | n |
|---|---|---|
| data_missing | alert_before_data | 3 |
