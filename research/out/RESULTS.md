# Research results: exits (1), trend filter (2), edge report (5)

Data: 2,747 filled zone trades, 2026-08-11 to 2026-10-04 (2,533 replayed;
206 had no candles, mostly delisted coins). Research only, nothing live changed.
Replay on 5m candles: stop counts on the fill candle, targets from the next
one, and a candle touching both counts as the stop. That is harsher than the
daily report, which uses 1m candles to settle those, so compare variants with
each other, not with the daily report's totals.

## 1. Exits: no variant turns it positive

Net R after fees, same 2,533 trades:

| rule | crypto | NSE | xStock | other |
|---|---:|---:|---:|---:|
| current scoring (2R, BE at 0.5R, banks +1R) | -143 | -834 | -70 | -13 |
| 2R target, honest (no +1R banking) | -205 | -1002 | -82 | -15 |
| 1R target | -225 | -1026 | -86 | -16 |
| 3R target | -223 | -993 | -83 | -18 |
| 3R, no breakeven | -270 | -965 | -94 | -16 |
| half at 1R, rest 3R | -220 | -998 | -83 | -17 |
| trail 1R behind peak after +1R | -166 | -953 | -70 | -16 |
| trail 0.5R behind peak after +1R | **-131** | -930 | **-67** | **-14** |
| 3R, 24h horizon (crypto) | -229 | -993 | -84 | -19 |
| trail 1R, 24h horizon (crypto) | -158 | -953 | -68 | -14 |

- Bigger targets make it worse: price rarely runs 3R inside the horizon.
- Best honest rule is the 0.5R trail: about +70R better than an honest 2R target on both crypto and NSE, but still negative.
- Scoring problem found: the daily report credits +1R to a trade that touched
  +1R and then came back to the breakeven stop. That adds about +62R (crypto) and +168R (NSE) over
  these 8 weeks compared with scoring the real exit.

## 2. Trend filter: helps crypto a lot, not NSE

Crypto, "with trend" = long above / short below the daily EMA50 (recorded net R):

| | trades | net R | first half | second half |
|---|---:|---:|---:|---:|
| all crypto | 564 | -79 | -61 | -27 |
| with daily trend | 258 | **-8** | -19 | +11 |
| against daily trend | 306 | -79 | -42 | -37 |

- Taking only with-trend trades cuts crypto losses by about 90% and keeps 46% of the trades. It holds in both halves.
- Crypto 30m with trend: 207 trades, +7R (break-even to slightly positive).
- Crypto 4h shorts with trend still lose (-16R on 43 trades).
- NSE: every trend definition tried (4h/daily EMA50, EMA20>50, EMA slope) leaves it at -0.25 to -0.36R a trade. No fix.
- xStock/other: the 4h/1D EMA50 halves the loss, but the samples are small (164 trades).

## 5. Edge report

See EDGE_REPORT.md. No bucket (stop size, touches, rating, hour, weekday) is
reliably positive. The rating does not separate winners.

## Trailing-stop grid (119 rules, 2026-10-04)

Start trailing at +a R, stop d R behind the best price (a 0.5-1.5, d 0.25-1.0),
breakeven on/off, 6/12/24h; plus structure trails (lowest low of last 3/6/12
5m candles). "+slip" also charges 0.05% slippage on every trailed/BE stop exit,
not just the full stop - a trailed stop is a stop order too.

Crypto with the daily trend filter (258 trades):

| rule | R | R +slip | first half | second half | win % |
|---|---:|---:|---:|---:|---:|
| current scoring | -43 | -52 | -38 | -15 | 33 |
| honest 2R target | -75 | -84 | -42 | -42 | 18 |
| trail 0.5R after +1R | -28 | -42 | -24 | -18 | 33 |
| **trail 0.25R after +0.5R** | **-5** | **-19** | -11 | -8 | 48 |
| trail 0.5R after +0.5R | -23 | -38 | -20 | -18 | 38 |
| structure trail, last 3 candles | -33 | -48 | -26 | -22 | 37 |

- Best everywhere: start early (+0.5R) and trail tight (0.25R). Breakeven on/off and
  12h vs 24h barely matter (most trades are out well before).
- With the trend filter it is close to break-even (-0.07R/trade after slippage), but
  still not positive in either half.
- All crypto (no filter): best rule -128R vs -222R honest 2R. NSE: nothing beats the current rule.
- Caveat: a 0.25R trail on 5m candles is only practical with an automated trailing stop;
  by hand it will slip more than modelled.
