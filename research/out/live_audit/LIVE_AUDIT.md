# Live audit (2026-10-09 16:24 UTC, since 2026-10-05)

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
- 30m HYPEUSD bitunix 2026-10-06T15:56 demand 92.04-92.343 price 92.37: nearest | replay nearest 89.667-89.671 at 2.922%
- 30m LINKUSD bitunix 2026-10-06T06:08 demand 13.649-13.749 price 13.752: nearest | replay nearest 13.144-13.2492 at 3.657%
- 30m UNIUSD bitunix 2026-10-08T12:47 demand 7.51-7.57008 price 7.574: zone exact, zone within 0.3%, nearest | replay nearest 5.933-5.972 at 21.151% | closest replay zones [(0.3389199999999999, 7.683, 7.736, False), (0.46092000000000066, 7.766, 7.775, False)]
- 30m UNIUSD bitunix 2026-10-08T13:41 demand 7.51-7.57008 price 7.577: zone exact, zone within 0.3%, nearest | replay nearest 5.933-5.972 at 21.183% | closest replay zones [(0.3389199999999999, 7.683, 7.736, False), (0.46092000000000066, 7.766, 7.775, False)]

## B. Fib / trendline alerts replayed (crypto, since the v6 seed)

24 crypto fib/TL alerts after the seed at 2026-10-08 15:54 UTC
- alerts: 12
- fetch failed: 12
- fib deeper zone + S/R stop ok: 7
- key NOT reproduced: 1
- key reproduced: 11
- plan arithmetic ok: 12
- plan same: 11
- tl band ok: 4

Not reproduced / failed:
- MRVL/USDT:USDT 4h: fetch failed RuntimeError("Bitunix MRVLBUSDT 4h: {'code': 20015, 'data': None, 'msg': 'this Futures is not allowed to trade.'}")
- SNDKBUSD 4h: fetch failed RuntimeError("Bitunix SNDKBUSDT 4h: {'code': 20015, 'data': None, 'msg': 'this Futures is not allowed to trade.'}")
- SNDKBUSD 1d: fetch failed RuntimeError("Bitunix SNDKBUSDT 1d: {'code': 20015, 'data': None, 'msg': 'this Futures is not allowed to trade.'}")
- MRVL/USDT:USDT 4h: fetch failed RuntimeError("Bitunix MRVLBUSDT 4h: {'code': 20015, 'data': None, 'msg': 'this Futures is not allowed to trade.'}")
- TSLAXUSD 4h: fetch failed RuntimeError("Bitunix TSLAXUSDT 4h: {'code': 20015, 'data': None, 'msg': 'this Futures is not allowed to trade.'}")
- TSLAXUSD 4h: fetch failed RuntimeError("Bitunix TSLAXUSDT 4h: {'code': 20015, 'data': None, 'msg': 'this Futures is not allowed to trade.'}")
- TSLAXUSD 4h: fetch failed RuntimeError("Bitunix TSLAXUSDT 4h: {'code': 20015, 'data': None, 'msg': 'this Futures is not allowed to trade.'}")
- BNBUSD 1M fib 10-09 12:13 key fib|BNBUSD|1M|1|1704067200|1374.48|2 not in replay (0 hits, price replay 744.19 vs rec 744.17): []
-     replay fib d=1 base=182.97 (2022-06-01) top=1374.48; 1636 1d candles from 2022-04-17
- TSLAXUSD 4h: fetch failed RuntimeError("Bitunix TSLAXUSDT 4h: {'code': 20015, 'data': None, 'msg': 'this Futures is not allowed to trade.'}")
- SNDKBUSD 4h: fetch failed RuntimeError("Bitunix SNDKBUSDT 4h: {'code': 20015, 'data': None, 'msg': 'this Futures is not allowed to trade.'}")
- TSLAXUSD 4h: fetch failed RuntimeError("Bitunix TSLAXUSDT 4h: {'code': 20015, 'data': None, 'msg': 'this Futures is not allowed to trade.'}")
- TSLAXUSD 4h: fetch failed RuntimeError("Bitunix TSLAXUSDT 4h: {'code': 20015, 'data': None, 'msg': 'this Futures is not allowed to trade.'}")
- NVDAXUSD 4h: fetch failed RuntimeError("Bitunix NVDAXUSDT 4h: {'code': 20015, 'data': None, 'msg': 'this Futures is not allowed to trade.'}")

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
