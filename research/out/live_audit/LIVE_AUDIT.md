# Live audit (2026-10-09 16:08 UTC, since 2026-10-05)

## A. Zone alerts rebuilt from candles

### 30m: 259 alerts since 2026-10-05
### 4h: 22 alerts since 2026-10-05

- alert window ok: 281
- alerts: 281
- approach side ok: 281
- band ok: 281
- distance ok: 281
- entry ok: 281
- nearest FAIL: 13
- nearest ok: 268
- stop ok: 281
- trend filter ok: 281
- zone exact FAIL: 11
- zone exact ok: 270
- zone within 0.3% FAIL: 11
- zone within 0.3% ok: 270

Alerts with a failed check:
- 30m AKE/USDT bitunix 2026-10-05T11:53 demand 0.031184-0.031351 price 0.031354: zone exact, zone within 0.3%, nearest
- 30m AVAXUSD bitunix 2026-10-05T16:11 demand 10.817-10.868 price 10.871: zone exact, zone within 0.3%, nearest
- 30m HYPEUSD bitunix 2026-10-06T15:56 demand 92.04-92.343 price 92.37: nearest
- 30m LINKUSD bitunix 2026-10-06T06:08 demand 13.649-13.749 price 13.752: nearest
- 30m LINKUSD bitunix 2026-10-07T12:33 demand 13.211-13.316688000000001 price 13.338: zone exact, zone within 0.3%, nearest
- 30m LINKUSD bitunix 2026-10-07T13:13 demand 13.211-13.316688000000001 price 13.329: zone exact, zone within 0.3%, nearest
- 30m LINKUSD bitunix 2026-10-07T13:46 demand 13.211-13.316688000000001 price 13.334: zone exact, zone within 0.3%, nearest
- 30m LINKUSD bitunix 2026-10-07T14:48 demand 13.211-13.316688000000001 price 13.341: zone exact, zone within 0.3%, nearest
- 30m LINKUSD bitunix 2026-10-07T15:21 demand 13.211-13.316688000000001 price 13.336: zone exact, zone within 0.3%, nearest
- 30m SOLUSD bitunix 2026-10-06T09:28 demand 118.84-119.01 price 119.11: zone exact, zone within 0.3%, nearest
- 30m UNIUSD bitunix 2026-10-08T12:47 demand 7.51-7.57008 price 7.574: zone exact, zone within 0.3%, nearest
- 30m UNIUSD bitunix 2026-10-08T13:41 demand 7.51-7.57008 price 7.577: zone exact, zone within 0.3%, nearest
- 30m XRPUSD bitunix 2026-10-06T19:21 demand 1.4898-1.4934 price 1.4959: zone exact, zone within 0.3%, nearest

## B. Fib / trendline alerts replayed (crypto, since the v6 seed)

24 crypto fib/TL alerts after the seed at 2026-10-08 15:54 UTC
- alerts: 24
- fib deeper zone + S/R stop ok: 8
- key NOT reproduced: 1
- key reproduced: 23
- plan arithmetic ok: 24
- plan same: 23
- tl band ok: 15

Not reproduced / failed:
- BNBUSD 1M fib 10-09 12:13 key fib|BNBUSD|1M|1|1704067200|1374.48|2 not in replay (0 hits, price replay 744.19 vs rec 744.17): []

## C. Crypto zone trades re-scored independently (Delta 5m)

105 finalized crypto/xStock/other rows since the cut
- DIFFER: 44
- agree: 60
- rows: 105
- same-candle (resolved on finer candles by the bot, skipped): 1
- net R on rows both scored: bot -24.20 / independent -24.20

Disagreements:
- XAUTUSD 30m 2026-10-05T08:36 long entry 4140.96 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- XAUTUSD 30m 2026-10-05T20:01 long entry 4137.5 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- XAUTUSD 4h 2026-10-05T19:16 long entry 4136.23 stop None: bot zone_cooldown None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- XAUTUSD 30m 2026-10-06T08:03 long entry 4139.03 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- XAUTUSD 30m 2026-10-06T16:11 short entry 4171.89 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- XAUTUSD 30m 2026-10-07T11:31 long entry 4131.34 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- BEAT/USDT 30m 2026-10-05T09:03 short entry 0.0888 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- ETHUSD 30m 2026-10-05T10:03 long entry 2694.1 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- ETHUSD 30m 2026-10-05T20:06 long entry 2694.12 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- ETHUSD 30m 2026-10-07T00:56 long entry 2677.52 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- ETHUSD 30m 2026-10-08T09:52 long entry 2550.15 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- BNBUSD 30m 2026-10-05T10:03 long entry 786.71 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- BNBUSD 30m 2026-10-06T23:01 long entry 778.72 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- BNBUSD 30m 2026-10-08T10:12 long entry 764.69904 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- UNIUSD 30m 2026-10-05T10:08 long entry 8.969 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- AAVEUSD 30m 2026-10-05T14:21 long entry 177.37 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- SOLUSD 30m 2026-10-06T11:43 long entry 119.01 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- ZORAUSD 30m 2026-10-05T20:06 long entry 0.00763 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- TRUMP/USDT 30m 2026-10-06T22:32 long entry 2.001 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- TSLAXUSD 30m 2026-10-05T08:01 short entry 373.8 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- TSLAXUSD 30m 2026-10-05T08:36 long entry 371.9544915348329 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- TSLAXUSD 30m 2026-10-06T10:32 short entry 381.65 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- TSLAXUSD 4h 2026-10-06T16:31 short entry 384.2757936507937 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- TSLAXUSD 30m 2026-10-08T14:17 long entry 375.45 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- METAXUSD 30m 2026-10-05T08:01 long entry 728.85 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- METAXUSD 30m 2026-10-05T20:01 short entry 746.25 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- METAXUSD 30m 2026-10-06T11:48 short entry 746.85 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- METAXUSD 30m 2026-10-07T19:11 long entry 726.55 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- METAXUSD 30m 2026-10-08T09:12 long entry 722.05 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- METAXUSD 30m 2026-10-08T17:47 long entry 712.45 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- SNDKBUSD 30m 2026-10-05T11:01 long entry 1721.14 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- SNDKBUSD 30m 2026-10-06T14:46 long entry 1688.21 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- SNDKBUSD 30m 2026-10-07T16:38 long entry 1618.24 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- MRVL/USDT:USDT 30m 2026-10-05T18:01 long entry 272.0133972088851 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- NVDAXUSD 30m 2026-10-05T19:13 short entry 237.52 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- NVDAXUSD 30m 2026-10-06T22:51 long entry 239.35 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- SLVONUSD 30m 2026-10-06T17:33 short entry 56.0 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- BCHUSD 30m 2026-10-06T09:06 long entry 313.76 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- BTCUSD 30m 2026-10-07T23:11 long entry 82990.6 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- DOGEUSD 30m 2026-10-06T11:46 long entry 0.09396 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- RIVERUSD 30m 2026-10-06T16:21 short entry 1.234 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- HYPEUSD 30m 2026-10-06T19:56 long entry 92.343 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- HYPEUSD 30m 2026-10-08T16:36 long entry 86.122 stop None: bot stop_too_tight None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None
- XRPUSD 30m 2026-10-07T00:51 long entry 1.4934 stop None: bot zone_not_touched None / independent error TypeError("float() argument must be a string or a real number, not 'NoneType'") None

## D. Fib / trendline results re-scored independently (crypto, Delta)

- agree: 147
- not resolved yet: 35
- scored: 147

Disagreements:
