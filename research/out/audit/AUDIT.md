# Backtest audit - stored vs re-simulated (current code)

| market | tf | stored trades | stored net R | resim trades | resim net R | resim trail R |
|---|---|---|---|---|---|---|
| CRYPTO | 30m | 707 | -232.1 | 576 | -211.4 | -173.1 |
| CRYPTO | 4h | 205 | -85.1 | 166 | -77.8 | -64.0 |
| NSE | 30m | 1307 | -867.7 | 1269 | -868.6 | -816.0 |
| NSE | 4h | 434 | -144.7 | 433 | -144.7 | -146.2 |
| OTHER | 30m | 26 | -13.3 | 27 | -14.2 | -17.1 |
| OTHER | 4h | 9 | -2.2 | 9 | -2.0 | -2.1 |
| XSTOCK | 30m | 131 | -61.5 | 128 | -59.2 | -45.5 |
| XSTOCK | 4h | 66 | -13.7 | 48 | -10.2 | -2.5 |

Rows that grade differently now: 1584

## Transitions (stored -> resim), changed only

| market | tf | stored | resim | n |
|---|---|---|---|---|
| CRYPTO | 30m | alert_before_data | data_missing | 160 |
| XSTOCK | 30m | alert_before_data | no_candles | 133 |
| CRYPTO | 30m | SL | data_missing | 56 |
| CRYPTO | 30m | zone_not_touched | data_missing | 34 |
| CRYPTO | 30m | BE | data_missing | 32 |
| CRYPTO | 30m | +1R | data_missing | 26 |
| CRYPTO | 30m | +2R | data_missing | 21 |
| XSTOCK | 30m | zone_not_touched | no_candles | 16 |
| CRYPTO | 4h | SL | data_missing | 16 |
| NSE | 30m | BE | data_quality_ambiguous | 16 |
| NSE | 30m | +1R | data_quality_ambiguous | 13 |
| XSTOCK | 30m | stop_too_tight | no_candles | 10 |
| CRYPTO | 30m | stop_too_tight | SL | 9 |
| CRYPTO | 4h | Neither | data_missing | 9 |
| XSTOCK | 4h | SL | no_candles | 9 |
| CRYPTO | 4h | +2R | data_missing | 8 |
| XSTOCK | 30m | stop_too_tight | SL | 7 |
| CRYPTO | 30m | stop_too_tight | data_missing | 6 |
| XSTOCK | 30m | BE | no_candles | 6 |
| NSE | 30m | SL | data_quality_ambiguous | 6 |
| CRYPTO | 30m | SL | BE | 4 |
| CRYPTO | 30m | zone_not_touched | alert_before_data | 4 |
| CRYPTO | 30m | zone_cooldown | data_missing | 4 |
| CRYPTO | 30m | stop_too_tight | +2R | 4 |
| XSTOCK | 4h | +2R | no_candles | 4 |
| CRYPTO | 30m | +2R | alert_before_data | 3 |
| CRYPTO | 30m | BE | alert_before_data | 3 |
| XSTOCK | 30m | stop_too_tight | +2R | 3 |
| XSTOCK | 30m | SL | no_candles | 3 |
| CRYPTO | 4h | +1R | data_missing | 3 |
| XSTOCK | 4h | +1R | no_candles | 3 |
| XSTOCK | 4h | alert_before_data | no_candles | 3 |
| CRYPTO | 30m | stop_too_tight | BE | 2 |
| CRYPTO | 30m | BE | +2R | 2 |
| CRYPTO | 30m | +2R | data_quality_ambiguous | 2 |
| XSTOCK | 30m | SL | BE | 2 |
| XSTOCK | 30m | +2R | no_candles | 2 |
| CRYPTO | 4h | BE | data_missing | 2 |
| XSTOCK | 4h | Neither | no_candles | 2 |
| CRYPTO | 30m | zone_not_touched | data_quality_ambiguous | 1 |
| CRYPTO | 30m | +1R | alert_before_data | 1 |
| CRYPTO | 30m | Neither | data_missing | 1 |
| CRYPTO | 30m | SL | alert_before_data | 1 |
| CRYPTO | 30m | stop_too_tight | alert_before_data | 1 |
| CRYPTO | 30m | stop_too_tight | data_quality_ambiguous | 1 |
| XSTOCK | 30m | BE | +2R | 1 |
| XSTOCK | 30m | +1R | no_candles | 1 |
| XSTOCK | 30m | SL | data_quality_ambiguous | 1 |
| OTHER | 30m | stop_too_tight | SL | 1 |
| CRYPTO | 4h | SL | data_quality_ambiguous | 1 |
| CRYPTO | 4h | SL | BE | 1 |
| XSTOCK | 4h | stop_too_tight | no_candles | 1 |
| NSE | 30m | alert_before_data | data_quality_ambiguous | 1 |
| NSE | 30m | +2R | data_quality_ambiguous | 1 |
| NSE | 30m | +2R | no_candles | 1 |
| NSE | 30m | SL | no_candles | 1 |
| NSE | 4h | BE | data_quality_ambiguous | 1 |

## Independent reference vs production: 378 disagreements

| production | reference | n |
|---|---|---|
| data_missing | alert_before_data | 378 |
