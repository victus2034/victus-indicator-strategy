# 1W / 1M live alerts audit

Records: 86. Rules today vs as sent: not sent today 25, same 56, same fib, sent on a wick 5
Result checks agree: 85 / 86 (diffs in traces.txt)

### Today's rules, independent scorer (crypto 5m, NSE 1h); alerts today's rules would not send left out

| Group | Alerts | Not filled | Open | News | Closed | R/trade | %/trade |
|---|---|---|---|---|---|---|---|
| crypto fib 1M | 1 | 0 | 1 | 0 | 0 | - | - |
| crypto fib 1w | 2 | 0 | 1 | 0 | 1 | -0.01R | -0.04% |
| crypto trendline 1w | 1 | 0 | 0 | 0 | 1 | +0.97R | +2.59% |
| nse fib 1M | 6 | 0 | 5 | 0 | 1 | -1.02R | -6.97% |
| nse fib 1w | 18 | 0 | 15 | 0 | 3 | -0.02R | +0.04% |
| nse trendline 1M | 7 | 0 | 2 | 0 | 5 | +0.11R | +1.14% |
| nse trendline 1w | 25 | 0 | 7 | 0 | 18 | -0.32R | -0.26% |
| nse zone 1w | 1 | 0 | 0 | 0 | 1 | -1.16R | -1.15% |

### As stored before the fix (1d candles)

| Group | Alerts | Not filled | Open | News | Closed | R/trade | %/trade |
|---|---|---|---|---|---|---|---|
| crypto fib 1M | 4 | 0 | 3 | 0 | 1 | -1.01R | -23.37% |
| crypto fib 1w | 5 | 0 | 2 | 0 | 3 | -0.34R | -5.93% |
| crypto trendline 1w | 1 | 0 | 0 | 0 | 1 | -1.05R | -2.81% |
| nse fib 1M | 14 | 1 | 11 | 0 | 2 | -0.51R | -3.50% |
| nse fib 1w | 29 | 5 | 22 | 0 | 2 | -0.51R | -3.50% |
| nse trendline 1M | 7 | 0 | 3 | 0 | 4 | -0.10R | +0.73% |
| nse trendline 1w | 25 | 2 | 8 | 0 | 15 | -0.43R | -0.33% |
| nse zone 1w | 1 | 1 | 0 | 0 | 0 | - | - |

### After the fix: live scorer on 1h, every alert sent (what cards / journal will read)

| Group | Alerts | Not filled | Open | News | Closed | R/trade | %/trade |
|---|---|---|---|---|---|---|---|
| crypto fib 1M | 4 | 0 | 3 | 0 | 1 | -1.01R | -23.37% |
| crypto fib 1w | 5 | 0 | 2 | 0 | 3 | -0.34R | -5.93% |
| crypto trendline 1w | 1 | 0 | 0 | 0 | 1 | +0.97R | +2.59% |
| nse fib 1M | 14 | 0 | 11 | 0 | 3 | -0.34R | -2.35% |
| nse fib 1w | 29 | 0 | 23 | 0 | 6 | -0.02R | -0.33% |
| nse trendline 1M | 7 | 0 | 2 | 0 | 5 | +0.11R | +1.14% |
| nse trendline 1w | 25 | 0 | 7 | 0 | 18 | -0.32R | -0.26% |
| nse zone 1w | 1 | 0 | 0 | 0 | 1 | -1.16R | -1.15% |

### Fibs with the trail exit (draft, not live yet), today's rules

| Group | Alerts | Not filled | Open | News | Closed | R/trade | %/trade |
|---|---|---|---|---|---|---|---|
| crypto fib 1M | 1 | 0 | 1 | 0 | 0 | - | - |
| crypto fib 1w | 2 | 0 | 1 | 0 | 1 | +0.39R | +1.38% |
| nse fib 1M | 6 | 0 | 5 | 0 | 1 | -1.02R | -6.97% |
| nse fib 1w | 18 | 0 | 13 | 0 | 5 | +0.25R | +1.86% |

