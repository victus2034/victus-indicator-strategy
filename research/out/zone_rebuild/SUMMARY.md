# S/R zone backtest rebuilt under today's rules (2026-09-01 to 2026-10-27 22:34 IST)

Today's zone engine, filters and watchlists on 4H, 1D, 1W, 1M (no 30m). 4H graded by the daily zone report's code (Delta / Yahoo 5m, fees, BE); 1D+ like the live 1D+ zone alerts (5 candles to fill, hold 20, 2R + BE, fees). % = R x the trade's stop distance. 5 trades filled within 15 min of US CPI/PPI/FOMC left out.

| market | tf | alerts | filled+closed | win % | total R | R/trade | %/trade |
|---|---|---|---|---|---|---|---|
| CRYPTO | 4H | 59 | 32 | 28% | -0.0 | -0.00 | -0.03% |
| CRYPTO | 1D | 8 | 8 | 0% | -9.3 | -1.16 | -1.03% |
| NSE | 4H | 472 | 334 | 29% | +14.6 | +0.04 | +0.05% |
| NSE | 1D | 232 | 199 | 18% | -79.7 | -0.40 | -0.27% |
| NSE | 1W | 101 | 68 | 22% | -35.7 | -0.53 | -0.40% |
| NSE | 1M | 3 | 3 | 0% | -3.5 | -1.16 | -1.15% |
| OTHER | 4H | 24 | 12 | 25% | -0.4 | -0.03 | -0.02% |
| XSTOCK | 4H | 54 | 40 | 32% | +1.1 | +0.03 | +0.04% |

Check: live zone alerts since 2026-10-21 that the replay also sends (same symbol, side, timeframe, within 4h): 1D+ 29/77, 4H 71/120


4H outcomes: zone_not_touched 168, BE 158, SL 93, Neither 81, +2R 64, +1R 25, stop_too_tight 9, alert_before_data 4, data_quality_ambiguous 4, zone_cooldown 2, Pending 1

