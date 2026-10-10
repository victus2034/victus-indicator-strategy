# GLENMARK 1d: Yahoo daily vs close rebuilt from 1h

date | open | high | low | close | 1h close
---|---|---|---|---|---
2026-09-29 00:00 +0530 | 2330.40 | 2441.50 | 2292.00 | 2441.50 | 2441.50
2026-09-30 00:00 +0530 | 2391.00 | 2410.00 | 2334.70 | 2334.70 | 2334.70
2026-10-01 00:00 +0530 | 2339.00 | 2360.00 | 2279.30 | 2331.00 | 2331.00
2026-10-05 00:00 +0530 | 2325.00 | 2340.50 | 2273.50 | 2295.00 | 2295.00
2026-10-06 00:00 +0530 | 2312.20 | 2320.00 | 2277.30 | 2311.00 | 2311.00
2026-10-07 00:00 +0530 | 2314.90 | 2326.80 | 2274.40 | 2282.30 | 2282.30
2026-10-08 00:00 +0530 | 2280.00 | 2284.00 | 2181.20 | 2192.20 | 2192.20
2026-10-09 00:00 +0530 | 2207.00 | 2293.00 | 2203.00 | 2293.00 | 2293.00

GLENMARK 1d alert 2026-10-01 09:24 entry 2314.96 tl|GLENMARK.NS|1d|0|1769970600|1781634600: no line
GLENMARK 1d alert 2026-10-01 13:49 entry 2271.33 tl|GLENMARK.NS|1d|0|1744828200|1769970600: no line
GLENMARK 1d alert 2026-10-01 13:49 entry 2272.08 tl|GLENMARK.NS|1d|0|1769970600|1785695400: no line
GLENMARK 1d alert 2026-10-05 09:24 entry 2317.77 tl|GLENMARK.NS|1d|0|1769970600|1781634600: no line
GLENMARK 1d alert 2026-10-05 11:24 entry 2273.89 tl|GLENMARK.NS|1d|0|1744828200|1769970600: no line
GLENMARK 1d alert 2026-10-05 11:24 entry 2274.64 tl|GLENMARK.NS|1d|0|1769970600|1785695400: no line
GLENMARK 1d alert 2026-10-06 14:19 entry 2279.00 tl|GLENMARK.NS|1d|0|1744828200|1769970600: no line
GLENMARK 1d alert 2026-10-07 09:29 entry 2279.76 tl|GLENMARK.NS|1d|0|1769970600|1785695400: no line
GLENMARK 1d alert 2026-10-08 10:53 entry 2248.88 tl|GLENMARK.NS|1d|0|1781634600|1785695400: ok
GLENMARK 1d alert 2026-10-09 11:53 entry 2249.69 tl|GLENMARK.NS|1d|0|1781634600|1785695400: broken 2026-10-08 close 2192.20 line 2249.69

# All trendline alerts since 2026-10-01, replayed on today's candles

market | tf | status | alerts
---|---|---|---
crypto | 1d | no | 7
crypto | 1d | no data | 14
crypto | 1d | ok | 8
crypto | 1w | ok | 1
crypto | 4h | no | 76
crypto | 4h | no data | 67
crypto | 4h | ok | 52
nse | 1M | no | 1
nse | 1M | ok | 5
nse | 1d | broken | 6
nse | 1d | no | 67
nse | 1d | ok | 64
nse | 1d | window-broken | 3
nse | 1w | no | 12
nse | 1w | ok | 14
nse | 1w | window-broken | 2
nse | 4h | broken | 3
nse | 4h | no | 71
nse | 4h | ok | 112
nse | 4h | window-broken | 1

## Alerts on an already broken line

nse GABRIEL.NS 1d sent 2026-10-01 09:24 entry 1312.90: window-broken 2026-09-29 close 1303.90 line 1305.82
nse BERGEPAINT.NS 4h sent 2026-10-01 09:54 entry 448.82: broken 2026-09-29 close 448.20 line 448.27
nse BERGEPAINT.NS 4h sent 2026-10-01 13:59 entry 449.04: broken 2026-09-29 close 448.20 line 448.27
nse NAM-INDIA.NS 1w sent 2026-10-01 15:09 entry 1043.92: window-broken 2026-03-09 close 823.65 line 838.34
nse GABRIEL.NS 1d sent 2026-10-05 10:04 entry 1316.97: window-broken 2026-09-29 close 1303.90 line 1305.82
nse NMDC.NS 1w sent 2026-10-08 11:23 entry 71.05: window-broken 2023-06-19 close 34.90 line 35.61
nse ALKEM.NS 1d sent 2026-10-08 11:34 entry 5327.83: broken 2026-10-07 close 5350.50 line 5323.87
nse IDBI.NS 4h sent 2026-10-08 14:03 entry 83.22: window-broken 2026-10-01 close 82.13 line 82.28
nse DABUR.NS 1d sent 2026-10-09 09:23 entry 383.34: window-broken 2026-10-06 close 388.90 line 386.64
nse ASAHIINDIA.NS 4h sent 2026-10-09 09:43 entry 935.99: broken 2026-10-08 close 939.00 line 944.83
nse GLENMARK.NS 1d sent 2026-10-09 11:53 entry 2249.69: broken 2026-10-08 close 2192.20 line 2249.69
nse DALBHARAT.NS 1d sent 2026-10-09 12:33 entry 1606.07: broken 2026-10-08 close 1592.90 line 1606.07
nse ITI.NS 1d sent 2026-10-09 13:03 entry 237.29: broken 2026-10-08 close 237.18 line 237.29
nse JINDALSAW.NS 1d sent 2026-10-09 13:23 entry 270.21: broken 2026-10-08 close 270.20 line 270.21
nse JSL.NS 1d sent 2026-10-09 13:33 entry 708.59: broken 2026-10-08 close 705.60 line 708.59
