# Live audit (2026-10-09 16:15 UTC, since 2026-10-05)

## A. Zone alerts rebuilt from candles

### 30m: 260 alerts since 2026-10-05
### 4h: 22 alerts since 2026-10-05

- alert window ok: 282
- alerts: 282
- approach side ok: 282
- band ok: 282
- distance ok: 282
- entry ok: 282
- matched only as 199 closed, no forming: 9
- nearest FAIL: 4
- nearest ok: 278
- stop ok: 282
- trend filter ok: 282
- zone exact FAIL: 2
- zone exact ok: 280
- zone within 0.3% FAIL: 2
- zone within 0.3% ok: 280

Alerts with a failed check:
- 30m HYPEUSD bitunix 2026-10-06T15:56 demand 92.04-92.343 price 92.37: nearest
- 30m LINKUSD bitunix 2026-10-06T06:08 demand 13.649-13.749 price 13.752: nearest
- 30m UNIUSD bitunix 2026-10-08T12:47 demand 7.51-7.57008 price 7.574: zone exact, zone within 0.3%, nearest
- 30m UNIUSD bitunix 2026-10-08T13:41 demand 7.51-7.57008 price 7.577: zone exact, zone within 0.3%, nearest

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
-     replay fib d=1 base=182.97 (2022-06-01) top=1374.48; 1636 1d candles from 2022-04-17

## C. Crypto zone trades re-scored independently (Delta 5m)

105 finalized crypto/xStock/other rows since the cut
- agree: 103
- rows: 105
- same-candle (resolved on finer candles by the bot, skipped): 1
- zone_cooldown (same-day dedup, not re-derived): 1
- net R on rows both scored: bot -24.20 / independent -24.20

Disagreements:

## D. Fib / trendline results re-scored independently (crypto, Delta)

- agree: 147
- not resolved yet: 35
- scored: 147

Disagreements:
