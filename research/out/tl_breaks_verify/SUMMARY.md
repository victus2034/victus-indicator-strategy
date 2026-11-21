# 1D TL breaks only, verified data - 2025-01-01 to 2026-11-21 19:52

22 crypto coins (live list), Bitunix candles cleaned with scanner.clean_candles, live bot rules, fees 0.0826%, slip 0.05%, fills within 15 min of US CPI / PPI / FOMC left out, open trades left out. Every coin loaded.

## 1. Candle data, every coin

Missing = candles absent inside the coin's own history (gaps); Bad = zero / NaN price; H/L = high or low not covering open / close; Spike = a one-candle wick far past both neighbours (1d 25%, 4h 12%, 15m 5%). Venue = days Bitunix vs Delta close differs >1% / wick >3%.

| Coin | Bitunix 1d from | 1d miss | 4h miss | 15m rows | 15m miss | Dup | Bad | H/L | Spikes 1d/4h/15m | Delta 15m miss | Venue days (close/wick) of n | Worst |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSD | 2022-04-17 | 0 | 0 | 66511 | 0 | 0 | 0 | 1041 | 0/0/0 | 0 | 0/0 of 689 | 2.6% 2025-10-10 |
| ETHUSD | 2022-04-17 | 0 | 0 | 66511 | 0 | 0 | 0 | 1211 | 0/2/1 | 0 | 0/0 of 689 | 2.0% 2026-04-11 |
| ZECUSD | 2023-08-09 | 2 | 17 | 66511 | 0 | 0 | 0 | 1896 | 0/5/9 | 0 | 0/1 of 411 | 5.9% 2025-10-06 |
| SOLUSD | 2022-04-17 | 0 | 0 | 66511 | 0 | 0 | 0 | 1344 | 0/3/2 | 0 | 0/1 of 689 | 3.9% 2025-10-10 |
| XRPUSD | 2022-04-17 | 0 | 0 | 66511 | 0 | 0 | 0 | 1365 | 1/6/2 | 0 | 0/1 of 689 | 15.9% 2025-10-10 |
| NEARUSD | 2023-08-09 | 2 | 0 | 66511 | 0 | 0 | 0 | 1630 | 0/2/5 | 1 | 14/1 of 689 | 9.2% 2025-10-10 |
| HYPEUSD | 2025-03-27 | 0 | 0 | 58009 | 0 | 0 | 0 | 2322 | 0/1/2 | 0 | 4/1 of 535 | 42.4% 2025-10-10 |
| DOGEUSD | 2022-04-17 | 0 | 0 | 66511 | 0 | 0 | 0 | 2049 | 1/3/3 | 0 | 0/1 of 689 | 10.6% 2025-10-10 |
| SUIUSD | 2023-07-31 | 0 | 0 | 66511 | 0 | 0 | 0 | 2182 | 1/4/1 | 1 | 2/1 of 689 | 41.0% 2025-10-10 |
| UNIUSD | 2022-04-17 | 0 | 0 | 66511 | 0 | 0 | 0 | 2699 | 2/4/7 | 0 | 2/0 of 689 | 2.1% 2025-10-10 |
| BNBUSD | 2022-04-17 | 0 | 0 | 66511 | 0 | 0 | 0 | 2485 | 0/2/1 | 1 | 0/2 of 689 | 8.6% 2025-08-06 |
| ENAUSD | 2024-04-09 | 0 | 0 | 66511 | 0 | 0 | 0 | 2644 | 1/1/6 | 0 | 43/1 of 689 | 26.3% 2025-10-10 |
| 1000PEPEUSD | 2024-01-01 | 0 | 0 | 66512 | 0 | 0 | 0 | 2665 | 1/4/5 | 0 | 9/1 of 327 | 4.0% 2025-12-29 |
| WLDUSD | 2023-09-30 | 0 | 0 | 66512 | 0 | 0 | 0 | 1823 | 1/5/7 | 2 | 36/3 of 689 | 10.7% 2025-10-10 |
| ADAUSD | 2022-04-17 | 0 | 14 | 66512 | 0 | 0 | 0 | 1570 | 2/2/4 | 0 | 1/0 of 689 | 1.5% 2026-08-30 |
| LINKUSD | 2022-04-17 | 0 | 20 | 66512 | 0 | 0 | 0 | 2754 | 1/1/3 | 0 | 0/2 of 689 | 8.8% 2025-10-10 |
| AVAXUSD | 2022-04-17 | 0 | 0 | 66512 | 0 | 0 | 0 | 2751 | 1/4/5 | 0 | 0/1 of 689 | 13.1% 2025-10-10 |
| INJUSD | 2023-11-09 | 0 | 0 | 66512 | 0 | 0 | 0 | 3074 | 1/4/3 | 0 | 38/2 of 689 | 6.9% 2025-10-10 |
| FILUSD | 2022-04-17 | 0 | 0 | 66512 | 0 | 0 | 0 | 1610 | 1/7/10 | 5 | 43/3 of 689 | 60.8% 2025-10-10 |
| AAVEUSD | 2023-07-25 | 0 | 0 | 66512 | 0 | 0 | 0 | 2860 | 1/4/5 | 0 | 2/1 of 689 | 3.5% 2025-10-10 |
| TAOUSD | 2024-04-19 | 0 | 0 | 66512 | 0 | 0 | 0 | 3262 | 2/3/7 | 0 | 25/3 of 689 | 15.6% 2025-10-10 |
| ARBUSD | 2023-03-23 | 0 | 0 | 66512 | 0 | 0 | 0 | 2121 | 1/4/3 | 0 | 43/2 of 689 | 3.7% 2025-10-10 |

```
ETHUSD Bitunix 4h spikes: 2023-06-16 17:30 16.1%, 2025-02-03 05:30 14.0%
ETHUSD Bitunix 15m spikes: 2025-02-03 07:30 12.4%
ZECUSD Bitunix 1d gaps (largest): 2023-09-13 05:30 x2
ZECUSD Bitunix 4h gaps (largest): 2023-09-13 01:30 x17
ZECUSD Bitunix 4h spikes: 2024-01-03 17:30 13.1%, 2025-02-03 05:30 12.7%, 2025-10-10 09:30 17.3%, 2025-10-11 01:30 26.8%, 2026-06-05 09:30 13.9%
ZECUSD Bitunix 15m spikes: 2025-02-03 07:30 5.6%, 2025-06-01 20:15 7.6%, 2025-07-09 07:30 7.3%, 2025-10-11 02:45 8.9%, 2025-11-07 20:30 8.2%, 2026-01-19 05:30 7.3%
ZECUSD Delta 15m spikes: 2026-08-22 10:30 8.2%
SOLUSD Bitunix 4h spikes: 2022-11-08 21:30 15.0%, 2023-07-14 05:30 14.1%, 2025-10-11 01:30 18.4%
SOLUSD Bitunix 15m spikes: 2025-10-11 02:45 13.5%, 2025-10-11 03:15 5.1%
XRPUSD Bitunix 1d spikes: 2025-10-10 05:30 39.0%
XRPUSD Bitunix 4h spikes: 2022-11-08 21:30 12.9%, 2023-07-13 21:30 15.6%, 2023-08-18 01:30 13.8%, 2024-01-03 17:30 14.6%, 2025-02-03 05:30 15.3%, 2025-10-11 01:30 39.0%
XRPUSD Bitunix 15m spikes: 2025-02-03 07:30 10.0%, 2025-10-11 02:45 27.1%
NEARUSD Bitunix 1d gaps (largest): 2023-10-01 05:30 x2
NEARUSD Bitunix 4h spikes: 2024-01-03 17:30 19.1%, 2025-10-11 01:30 28.0%
NEARUSD Bitunix 15m spikes: 2025-02-03 07:30 7.0%, 2025-10-11 02:45 23.3%, 2025-11-21 13:00 5.4%, 2026-01-19 05:30 5.8%, 2026-08-22 10:30 9.7%
NEARUSD Delta 15m gaps (largest): 2026-08-16 04:15 x1
NEARUSD Delta 15m spikes: 2026-08-22 10:30 11.4%
HYPEUSD Bitunix 4h spikes: 2025-10-11 01:30 15.9%
HYPEUSD Bitunix 15m spikes: 2025-10-11 02:45 9.8%, 2026-08-22 10:30 5.9%
DOGEUSD Bitunix 1d spikes: 2025-10-10 05:30 41.9%
DOGEUSD Bitunix 4h spikes: 2022-05-11 17:30 13.3%, 2022-11-08 21:30 12.3%, 2025-10-11 01:30 46.1%
DOGEUSD Bitunix 15m spikes: 2025-02-03 07:30 7.3%, 2025-10-11 02:45 37.8%, 2025-10-11 03:30 5.4%
SUIUSD Bitunix 1d spikes: 2025-10-10 05:30 63.6%
SUIUSD Bitunix 4h spikes: 2024-01-03 17:30 15.4%, 2024-04-12 21:30 12.8%, 2025-02-03 05:30 13.0%, 2025-10-11 01:30 65.4%
SUIUSD Bitunix 15m spikes: 2025-10-11 02:45 55.4%
SUIUSD Delta 15m gaps (largest): 2026-08-16 04:15 x1
UNIUSD Bitunix 1d spikes: 2025-10-10 05:30 55.3%, 2026-02-11 05:30 31.7%
UNIUSD Bitunix 4h spikes: 2022-05-12 09:30 12.2%, 2024-04-12 21:30 14.2%, 2025-10-11 01:30 55.3%, 2026-02-11 17:30 17.3%
UNIUSD Bitunix 15m spikes: 2025-03-19 23:45 6.0%, 2025-09-22 11:30 6.9%, 2025-10-11 02:45 43.1%, 2025-11-11 06:45 5.3%, 2026-01-19 05:30 5.0%, 2026-02-11 19:30 5.3%
UNIUSD Delta 15m spikes: 2026-08-22 10:30 7.1%
BNBUSD Bitunix 4h spikes: 2022-11-08 21:30 20.6%, 2025-10-11 01:30 17.0%
BNBUSD Bitunix 15m spikes: 2025-10-11 02:45 10.2%
BNBUSD Delta 15m gaps (largest): 2026-08-16 04:15 x1
ENAUSD Bitunix 1d spikes: 2025-10-10 05:30 43.4%
ENAUSD Bitunix 4h spikes: 2025-10-11 01:30 59.3%
ENAUSD Bitunix 15m spikes: 2025-02-03 15:00 8.2%, 2025-09-22 11:30 5.4%, 2025-10-11 02:45 50.7%, 2025-11-21 13:00 6.1%, 2026-01-19 05:30 6.4%, 2026-10-14 18:00 6.8%
ENAUSD Delta 15m spikes: 2026-10-14 18:00 6.1%
1000PEPEUSD Bitunix 1d spikes: 2025-10-10 05:30 53.5%
1000PEPEUSD Bitunix 4h spikes: 2024-01-03 17:30 16.6%, 2024-04-12 21:30 20.9%, 2024-04-14 01:30 13.1%, 2025-10-11 01:30 54.5%
1000PEPEUSD Bitunix 15m spikes: 2025-02-03 07:30 5.0%, 2025-10-11 02:45 38.6%, 2025-11-21 13:00 5.5%, 2026-01-19 05:30 5.2%, 2026-08-22 10:30 5.1%
WLDUSD Bitunix 1d spikes: 2025-10-10 05:30 64.1%
WLDUSD Bitunix 4h spikes: 2023-12-16 21:30 14.0%, 2024-01-03 17:30 18.8%, 2024-04-14 01:30 12.4%, 2025-10-11 01:30 64.1%, 2026-08-22 09:30 15.9%
WLDUSD Bitunix 15m spikes: 2025-02-03 07:30 8.2%, 2025-09-09 05:45 8.2%, 2025-10-11 02:45 41.0%, 2025-11-21 13:00 7.6%, 2026-01-19 05:30 5.7%, 2026-01-29 02:30 5.8%
WLDUSD Delta 15m gaps (largest): 2026-08-16 04:15 x2
ADAUSD Bitunix 1d spikes: 2025-02-03 05:30 25.2%, 2025-10-10 05:30 52.5%
ADAUSD Bitunix 4h gaps (largest): 2023-09-18 09:30 x7, 2023-09-27 05:30 x4, 2023-09-13 09:30 x3
ADAUSD Bitunix 4h spikes: 2025-02-03 05:30 17.6%, 2025-10-11 01:30 54.1%
ADAUSD Bitunix 15m spikes: 2025-02-03 07:30 14.2%, 2025-03-04 20:00 5.4%, 2025-10-11 02:45 35.9%, 2026-08-22 10:30 6.6%
ADAUSD Delta 15m spikes: 2026-08-22 10:30 6.7%
LINKUSD Bitunix 1d spikes: 2025-10-10 05:30 44.6%
LINKUSD Bitunix 4h gaps (largest): 2023-10-01 05:30 x20
LINKUSD Bitunix 4h spikes: 2025-10-11 01:30 46.0%
LINKUSD Bitunix 15m spikes: 2025-02-03 07:30 6.7%, 2025-10-11 02:45 28.8%, 2026-08-22 10:30 5.7%
LINKUSD Delta 15m spikes: 2026-08-22 10:30 5.3%
AVAXUSD Bitunix 1d spikes: 2025-10-10 05:30 52.2%
AVAXUSD Bitunix 4h spikes: 2022-05-12 09:30 13.5%, 2023-06-10 09:30 12.1%, 2024-04-12 21:30 13.2%, 2025-10-11 01:30 52.2%
AVAXUSD Bitunix 15m spikes: 2025-02-03 07:30 5.5%, 2025-09-22 11:30 8.0%, 2025-10-11 02:45 44.1%, 2025-11-21 13:00 6.2%, 2026-08-22 10:30 6.4%
AVAXUSD Delta 15m spikes: 2026-08-22 10:30 6.4%
INJUSD Bitunix 1d spikes: 2025-10-10 05:30 61.3%
INJUSD Bitunix 4h spikes: 2024-01-03 17:30 17.7%, 2024-04-12 21:30 14.5%, 2024-04-14 01:30 13.1%, 2025-10-11 01:30 62.6%
INJUSD Bitunix 15m spikes: 2025-02-03 07:30 7.0%, 2025-10-11 02:45 51.4%, 2025-11-21 13:00 5.3%
FILUSD Bitunix 1d spikes: 2025-10-10 05:30 32.1%
FILUSD Bitunix 4h spikes: 2022-05-01 01:30 15.5%, 2022-12-17 01:30 17.4%, 2023-06-10 09:30 18.1%, 2023-08-18 01:30 12.1%, 2024-04-12 21:30 18.2%, 2025-04-04 09:30 19.1%
FILUSD Bitunix 15m spikes: 2025-02-03 07:30 8.4%, 2025-04-04 12:30 13.9%, 2025-10-11 03:00 15.8%, 2025-10-11 03:15 9.7%, 2025-11-07 02:15 5.3%, 2025-11-21 13:00 5.6%
FILUSD Delta 15m gaps (largest): 2026-07-07 14:15 x4, 2026-08-16 04:15 x1
AAVEUSD Bitunix 1d spikes: 2025-10-10 05:30 58.8%
AAVEUSD Bitunix 4h spikes: 2024-04-12 21:30 12.3%, 2024-04-14 01:30 14.2%, 2025-02-03 05:30 12.5%, 2025-10-11 01:30 58.8%
AAVEUSD Bitunix 15m spikes: 2025-02-03 07:30 6.0%, 2025-09-22 11:30 6.6%, 2025-10-11 02:45 50.6%, 2025-11-21 13:00 5.2%, 2026-06-25 22:45 6.1%
AAVEUSD Delta 15m spikes: 2026-06-25 22:45 6.1%
TAOUSD Bitunix 1d spikes: 2025-02-03 05:30 25.3%, 2025-10-10 05:30 42.0%
TAOUSD Bitunix 4h spikes: 2024-06-07 21:30 15.6%, 2025-02-03 05:30 15.9%, 2025-10-11 01:30 42.0%
TAOUSD Bitunix 15m spikes: 2025-02-03 07:30 6.3%, 2025-02-04 04:00 5.8%, 2025-08-26 11:45 8.3%, 2025-10-11 02:45 38.9%, 2026-01-19 05:30 12.5%, 2026-02-16 10:30 5.6%
ARBUSD Bitunix 1d spikes: 2025-10-10 05:30 61.2%
ARBUSD Bitunix 4h spikes: 2023-11-09 21:30 13.6%, 2024-01-03 17:30 21.4%, 2024-04-12 21:30 17.2%, 2025-10-11 01:30 61.2%
ARBUSD Bitunix 15m spikes: 2025-02-03 07:30 7.6%, 2025-10-11 02:45 46.1%, 2025-11-21 13:00 7.6%
```

## 2. Replay, 1D TL, closed trades only

### Sep 1 - now

Alerts 230: no fill 48, no 0.75% wick/body stop 5, CPI/PPI/FOMC fills left out 0, still open (no exit yet, left out) 5 (breaks 5), closed 177, of which 0 cross a missing 15m candle.

| Set | Closed | Win | R/trade | %/trade | Total R | Max DD |
|---|---|---|---|---|---|---|
| Live now: touch + break, 1 per coin, max 5 | 113 | 55% | +0.037R | +1.46% | +4.2R | -11.3R |
| **Breaks only, 1 per coin, max 5** | 54 | 76% | +0.485R | +3.82% | +26.2R | -3.1R |
| Touch + break, no slot limit | 177 | 55% | +0.042R | +0.74% | +7.4R | -22.7R |
| Breaks only, no slot limit | 82 | 67% | +0.312R | +2.20% | +25.6R | -12.2R |
| Touches only, no slot limit | 95 | 44% | -0.192R | -0.53% | -18.2R | -24.7R |
| Breaks only, no slot limit, no data gap | 82 | 67% | +0.312R | +2.20% | +25.6R | -12.2R |

Break exits: SL 27, SL shift 37, Trail TP 18

### 2025-01-01 - now

Alerts 1959: no fill 399, no 0.75% wick/body stop 14, CPI/PPI/FOMC fills left out 0, still open (no exit yet, left out) 5 (breaks 5), closed 1555, of which 0 cross a missing 15m candle.

| Set | Closed | Win | R/trade | %/trade | Total R | Max DD |
|---|---|---|---|---|---|---|
| Live now: touch + break, 1 per coin, max 5 | 1006 | 53% | +0.064R | +0.33% | +64.4R | -20.3R |
| **Breaks only, 1 per coin, max 5** | 491 | 59% | +0.179R | +1.07% | +87.7R | -12.2R |
| Touch + break, no slot limit | 1555 | 53% | +0.072R | +0.36% | +111.9R | -32.2R |
| Breaks only, no slot limit | 706 | 58% | +0.152R | +0.86% | +107.4R | -19.5R |
| Touches only, no slot limit | 849 | 49% | +0.005R | -0.05% | +4.5R | -53.8R |
| Breaks only, no slot limit, no data gap | 706 | 58% | +0.152R | +0.86% | +107.4R | -19.5R |

Break exits: SL 295, SL shift 268, Trail TP 143

### Breaks per coin (no slot limit, whole period)

| Set | Closed | Win | R/trade | %/trade | Total R | Max DD |
|---|---|---|---|---|---|---|
| BTCUSD | 30 | 70% | +0.421R | +1.79% | +12.6R | -1.4R |
| ETHUSD | 32 | 66% | +0.291R | +1.50% | +9.3R | -5.0R |
| ZECUSD | 28 | 64% | +0.338R | +4.80% | +9.5R | -3.2R |
| SOLUSD | 34 | 50% | -0.005R | +1.08% | -0.2R | -8.3R |
| XRPUSD | 33 | 61% | +0.111R | +1.09% | +3.7R | -5.8R |
| NEARUSD | 34 | 56% | +0.015R | +1.43% | +0.5R | -8.5R |
| HYPEUSD | 21 | 62% | +0.092R | +1.34% | +1.9R | -2.3R |
| DOGEUSD | 38 | 61% | +0.203R | +1.32% | +7.7R | -4.1R |
| SUIUSD | 30 | 57% | +0.157R | +3.90% | +4.7R | -5.1R |
| UNIUSD | 37 | 46% | -0.094R | -4.19% | -3.5R | -8.9R |
| BNBUSD | 32 | 69% | +0.436R | +0.96% | +14.0R | -2.3R |
| ENAUSD | 30 | 87% | +0.772R | +6.80% | +23.2R | -1.0R |
| 1000PEPEUSD | 35 | 57% | +0.085R | +2.35% | +3.0R | -4.1R |
| WLDUSD | 29 | 48% | -0.025R | +0.77% | -0.7R | -3.6R |
| ADAUSD | 37 | 62% | +0.166R | +0.03% | +6.2R | -4.5R |
| LINKUSD | 33 | 61% | +0.165R | -0.32% | +5.4R | -4.3R |
| AVAXUSD | 29 | 66% | +0.521R | +5.23% | +15.1R | -2.0R |
| INJUSD | 31 | 48% | -0.036R | +0.57% | -1.1R | -4.4R |
| FILUSD | 33 | 45% | -0.035R | -7.14% | -1.1R | -6.4R |
| AAVEUSD | 37 | 51% | +0.011R | +0.52% | +0.4R | -5.2R |
| TAOUSD | 31 | 45% | -0.205R | -2.60% | -6.4R | -9.1R |
| ARBUSD | 32 | 56% | +0.099R | +0.21% | +3.2R | -3.6R |

## 3. What the journal's Signals tab should show - 1D crypto TL BROKEN (SP + RS TL BR)

Journal's own alerts (rebuild before its cutoff, live after), Delta 15m, SL wick or body 0.75%, Exit 1.5R, SL shift +1R -> +0.75R, Trail TP 0.25R / 0.5R, Till TP / SL, fees on. Open trades left out.

| Set | Closed | Win | R/trade | %/trade | Total R | Max DD |
|---|---|---|---|---|---|---|
| 1 Jun - now (all) | 202 | 64% | +0.286R | +1.36% | +57.9R | -13.3R |
| 1 Jun - now (no news fills) | 202 | 64% | +0.286R | +1.36% | +57.9R | -13.3R |
| Sep 1 - now (all) | 95 | 64% | +0.281R | -0.01% | +26.7R | -13.3R |
| Sep 1 - now (no news fills) | 95 | 64% | +0.281R | -0.01% | +26.7R | -13.3R |

Outcomes: SL shift 79, SL 72, Trail TP 51, no fill 1, no stop 2, open 5
Missing-data alerts: none
Trades crossing a missing Delta 15m candle: 1

## 4. Hand trace (6 random closed breaks, Bitunix)

```
NEARUSD short break, daily close 2025-05-31 05:30: break candle [1748563200, 2.752, 2.767, 2.407, 2.441]
  entry 2.441 (15m open 2025-05-31 05:30), stop 2.752 (12.74%) on daily 2025-05-30 [1748563200, 2.752, 2.767, 2.407, 2.441]
  fill 2025-05-31 05:30 [1748649600, 2.449, 2.404, 2.411] -> SL shift 2025-06-19 06:00 bar [1750293000, 2.212, 2.199, 2.207] level 2.20775 best 1.193R = +0.740R
WLDUSD short break, daily close 2025-10-23 05:30: break candle [1761091200, 0.8875, 0.8962, 0.8102, 0.843]
  entry 0.843 (15m open 2025-10-23 05:30), stop 0.8875 (5.28%) on daily 2025-10-22 [1761091200, 0.8875, 0.8962, 0.8102, 0.843]
  fill 2025-10-23 05:30 [1761177600, 0.845, 0.8401, 0.844] -> SL 2025-10-24 14:15 bar [1761295500, 0.888, 0.8812, 0.8836] level 0.8875 best 0.099R = -1.026R
TAOUSD short break, daily close 2026-02-06 05:30: break candle [1770249600, 187.68, 191.19, 157.12, 160.53]
  entry 160.53 (15m open 2026-02-06 05:30), stop 187.68 (16.91%) on daily 2026-02-05 [1770249600, 187.68, 191.19, 157.12, 160.53]
  fill 2026-02-06 05:30 [1770336000, 161.66, 145.52, 147.83] -> SL 2026-02-14 09:00 bar [1771039800, 187.83, 185.75, 187.06] level 187.68 best 0.666R = -1.008R
UNIUSD short break, daily close 2025-10-11 05:30: break candle [1760054400, 7.851, 8.603, 2.351, 5.773]
  entry 5.773 (15m open 2025-10-11 05:30), stop 7.851 (36.00%) on daily 2025-10-10 [1760054400, 7.851, 8.603, 2.351, 5.773]
  fill 2025-10-11 05:30 [1760140800, 5.922, 5.735, 5.906] -> SL 2025-11-11 03:00 bar [1762810200, 8.428, 7.764, 8.423] level 7.851 best 0.5R = -1.004R
LINKUSD long break, daily close 2025-07-09 05:30: break candle [1751932800, 13.425, 13.992, 13.192, 13.963]
  entry 13.963 (15m open 2025-07-09 05:30), stop 13.425 (3.85%) on daily 2025-07-08 [1751932800, 13.425, 13.992, 13.192, 13.963]
  fill 2025-07-09 05:30 [1752019200, 13.978, 13.924, 13.934] -> Trail TP 2025-07-11 02:30 bar [1752181200, 14.859, 14.758, 14.843] level 14.769999999999996 best 1.533R = +1.465R
DOGEUSD long break, daily close 2025-05-09 05:30: break candle [1746662400, 0.17193, 0.19837, 0.17162, 0.19809]
  entry 0.19809 (15m open 2025-05-09 05:30), stop 0.17193 (13.21%) on daily 2025-05-08 [1746662400, 0.17193, 0.19837, 0.17162, 0.19809]
  fill 2025-05-09 05:30 [1746748800, 0.19864, 0.19578, 0.19586] -> Trail TP 2025-05-10 23:00 bar [1746898200, 0.23932, 0.23618, 0.23675] level 0.23732999999999999 best 1.507R = +1.489R
```
