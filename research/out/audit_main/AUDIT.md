# Backtest audit - stored vs re-simulated (current code)

| market | tf | stored trades | stored net R | resim trades | resim net R | resim trail R |
|---|---|---|---|---|---|---|
| CRYPTO | 30m | 564 | -51.9 | 561 | -210.1 | -185.8 |
| CRYPTO | 4h | 191 | -45.4 | 166 | -78.9 | -68.3 |
| NSE | 30m | 1303 | -438.4 | 1269 | -815.3 | -816.0 |
| NSE | 4h | 434 | -108.0 | 433 | -134.3 | -146.2 |
| OTHER | 30m | 22 | -10.3 | 26 | -12.3 | -16.5 |
| OTHER | 4h | 8 | +0.3 | 9 | -1.9 | -2.4 |
| XSTOCK | 30m | 115 | -41.6 | 118 | -58.4 | -46.0 |
| XSTOCK | 4h | 55 | -11.1 | 48 | -9.3 | -4.1 |

Rows that grade differently now: 1647

## Transitions (stored -> resim), changed only

| market | tf | stored | resim | n |
|---|---|---|---|---|
| CRYPTO | 30m | alert_before_data | data_missing | 160 |
| XSTOCK | 30m | alert_before_data | no_candles | 133 |
| NSE | 30m | +1R | BE | 102 |
| CRYPTO | 30m | alert_before_data | zone_not_touched | 90 |
| NSE | 30m | +1R | SL | 77 |
| NSE | 30m | BE | SL | 73 |
| CRYPTO | 30m | alert_before_data | SL | 63 |
| CRYPTO | 30m | SL | data_missing | 56 |
| CRYPTO | 30m | +1R | BE | 42 |
| CRYPTO | 30m | zone_not_touched | data_missing | 34 |
| CRYPTO | 30m | BE | data_missing | 32 |
| CRYPTO | 30m | +1R | data_missing | 26 |
| NSE | 4h | +1R | BE | 26 |
| CRYPTO | 30m | zone_not_touched | +2R | 22 |
| CRYPTO | 30m | +2R | data_missing | 21 |
| CRYPTO | 4h | immature | zone_not_touched | 20 |
| CRYPTO | 30m | alert_before_data | +2R | 18 |
| CRYPTO | 30m | +1R | SL | 18 |
| CRYPTO | 30m | BE | SL | 18 |
| CRYPTO | 30m | alert_before_data | BE | 17 |
| XSTOCK | 30m | zone_not_touched | no_candles | 16 |
| CRYPTO | 4h | SL | data_missing | 16 |
| NSE | 30m | BE | data_quality_ambiguous | 16 |
| CRYPTO | 30m | +2R | BE | 14 |
| CRYPTO | 4h | SL | BE | 14 |
| CRYPTO | 30m | +2R | SL | 13 |
| NSE | 30m | +1R | data_quality_ambiguous | 13 |
| NSE | 30m | BE | Neither | 12 |
| CRYPTO | 30m | SL | BE | 10 |
| CRYPTO | 30m | zone_not_touched | BE | 10 |
| XSTOCK | 30m | stop_too_tight | no_candles | 10 |
| XSTOCK | 4h | immature | no_candles | 10 |
| CRYPTO | 4h | immature | data_missing | 9 |
| CRYPTO | 4h | Neither | data_missing | 9 |
| CRYPTO | 4h | +2R | SL | 9 |
| CRYPTO | 4h | +2R | BE | 9 |
| XSTOCK | 4h | SL | no_candles | 9 |
| XSTOCK | 30m | zone_not_touched | +2R | 8 |
| CRYPTO | 4h | +2R | data_missing | 8 |
| NSE | 30m | BE | +2R | 8 |
| NSE | 4h | BE | SL | 8 |
| CRYPTO | 30m | zone_cooldown | SL | 7 |
| XSTOCK | 30m | BE | SL | 7 |
| XSTOCK | 30m | zone_not_touched | BE | 7 |
| NSE | 30m | +1R | +2R | 7 |
| NSE | 30m | +2R | SL | 7 |
| CRYPTO | 30m | stop_too_tight | data_missing | 6 |
| XSTOCK | 30m | +1R | SL | 6 |
| XSTOCK | 30m | BE | no_candles | 6 |
| CRYPTO | 4h | Neither | BE | 6 |
| CRYPTO | 4h | +1R | BE | 6 |
| XSTOCK | 4h | immature | zone_not_touched | 6 |
| NSE | 30m | SL | data_quality_ambiguous | 6 |
| NSE | 4h | BE | +2R | 6 |
| CRYPTO | 30m | zone_not_touched | stop_too_tight | 5 |
| CRYPTO | 4h | +1R | SL | 5 |
| CRYPTO | 30m | alert_before_data | Neither | 4 |
| CRYPTO | 30m | BE | +2R | 4 |
| CRYPTO | 30m | zone_not_touched | SL | 4 |
| CRYPTO | 30m | zone_not_touched | alert_before_data | 4 |
| CRYPTO | 30m | zone_cooldown | data_missing | 4 |
| XSTOCK | 30m | +1R | BE | 4 |
| CRYPTO | 4h | +1R | +2R | 4 |
| CRYPTO | 4h | BE | SL | 4 |
| CRYPTO | 4h | immature | +2R | 4 |
| CRYPTO | 4h | immature | SL | 4 |
| XSTOCK | 4h | +2R | no_candles | 4 |
| XSTOCK | 4h | SL | BE | 4 |
| XSTOCK | 4h | immature | BE | 4 |
| XSTOCK | 4h | Neither | BE | 4 |
| NSE | 30m | +1R | Neither | 4 |
| NSE | 4h | BE | Neither | 4 |
| CRYPTO | 30m | +1R | zone_not_touched | 3 |
| CRYPTO | 30m | +1R | +2R | 3 |
| CRYPTO | 30m | stop_too_tight | zone_not_touched | 3 |
| CRYPTO | 30m | BE | zone_not_touched | 3 |
| CRYPTO | 30m | +2R | alert_before_data | 3 |
| CRYPTO | 30m | BE | alert_before_data | 3 |
| XSTOCK | 30m | stop_too_tight | zone_not_touched | 3 |
| XSTOCK | 30m | SL | no_candles | 3 |
| XSTOCK | 30m | zone_not_touched | stop_too_tight | 3 |
| CRYPTO | 4h | immature | +1R | 3 |
| CRYPTO | 4h | immature | Neither | 3 |
| CRYPTO | 4h | +1R | data_missing | 3 |
| CRYPTO | 4h | immature | BE | 3 |
| XSTOCK | 4h | +1R | no_candles | 3 |
| XSTOCK | 4h | alert_before_data | no_candles | 3 |
| XSTOCK | 4h | immature | SL | 3 |
| NSE | 30m | alert_before_data | SL | 3 |
| NSE | 30m | +2R | BE | 3 |
| CRYPTO | 30m | alert_before_data | +1R | 2 |
| CRYPTO | 30m | zone_not_touched | +1R | 2 |
| CRYPTO | 30m | alert_before_data | stop_too_tight | 2 |
| CRYPTO | 30m | +2R | data_quality_ambiguous | 2 |
| XSTOCK | 30m | +2R | SL | 2 |
| XSTOCK | 30m | +2R | no_candles | 2 |
| XSTOCK | 30m | SL | BE | 2 |
| OTHER | 30m | zone_not_touched | +2R | 2 |
| CRYPTO | 4h | SL | zone_cooldown | 2 |
| CRYPTO | 4h | Neither | SL | 2 |
| CRYPTO | 4h | BE | data_missing | 2 |
| XSTOCK | 4h | Neither | no_candles | 2 |
| XSTOCK | 4h | immature | +1R | 2 |
| XSTOCK | 4h | +1R | BE | 2 |
| XSTOCK | 4h | +1R | SL | 2 |
| XSTOCK | 4h | immature | +2R | 2 |
| OTHER | 4h | immature | zone_not_touched | 2 |
| OTHER | 4h | +1R | SL | 2 |
| NSE | 4h | +1R | SL | 2 |
| CRYPTO | 30m | zone_not_touched | data_quality_ambiguous | 1 |
| CRYPTO | 30m | +2R | zone_not_touched | 1 |
| CRYPTO | 30m | +1R | zone_cooldown | 1 |
| CRYPTO | 30m | +2R | +1R | 1 |
| CRYPTO | 30m | +1R | alert_before_data | 1 |
| CRYPTO | 30m | Neither | data_missing | 1 |
| CRYPTO | 30m | SL | alert_before_data | 1 |
| CRYPTO | 30m | stop_too_tight | alert_before_data | 1 |
| CRYPTO | 30m | zone_cooldown | BE | 1 |
| CRYPTO | 30m | zone_cooldown | +2R | 1 |
| CRYPTO | 30m | zone_cooldown | zone_not_touched | 1 |
| CRYPTO | 30m | SL | +2R | 1 |
| CRYPTO | 30m | zone_not_touched | zone_cooldown | 1 |
| XSTOCK | 30m | +1R | no_candles | 1 |
| XSTOCK | 30m | zone_not_touched | SL | 1 |
| XSTOCK | 30m | BE | zone_not_touched | 1 |
| XSTOCK | 30m | zone_cooldown | BE | 1 |
| XSTOCK | 30m | BE | +2R | 1 |
| XSTOCK | 30m | SL | data_quality_ambiguous | 1 |
| XSTOCK | 30m | +2R | BE | 1 |
| OTHER | 30m | +1R | BE | 1 |
| OTHER | 30m | BE | SL | 1 |
| OTHER | 30m | zone_not_touched | BE | 1 |
| OTHER | 30m | +2R | BE | 1 |
| OTHER | 30m | zone_cooldown | SL | 1 |
| CRYPTO | 4h | Neither | zone_not_touched | 1 |
| CRYPTO | 4h | SL | data_quality_ambiguous | 1 |
| CRYPTO | 4h | BE | +2R | 1 |
| CRYPTO | 4h | immature | zone_cooldown | 1 |
| XSTOCK | 4h | Neither | SL | 1 |
| XSTOCK | 4h | +2R | BE | 1 |
| XSTOCK | 4h | +1R | +2R | 1 |
| XSTOCK | 4h | stop_too_tight | no_candles | 1 |
| OTHER | 4h | +2R | BE | 1 |
| OTHER | 4h | +1R | +2R | 1 |
| OTHER | 4h | SL | BE | 1 |
| OTHER | 4h | immature | +1R | 1 |
| OTHER | 4h | alert_before_data | zone_not_touched | 1 |
| NSE | 30m | alert_before_data | data_quality_ambiguous | 1 |
| NSE | 30m | alert_before_data | BE | 1 |
| NSE | 30m | +2R | data_quality_ambiguous | 1 |
| NSE | 30m | +2R | no_candles | 1 |
| NSE | 30m | SL | no_candles | 1 |
| NSE | 4h | BE | +1R | 1 |
| NSE | 4h | BE | data_quality_ambiguous | 1 |

## Independent reference vs production: 387 disagreements

| production | reference | n |
|---|---|---|
| data_missing | alert_before_data | 387 |
