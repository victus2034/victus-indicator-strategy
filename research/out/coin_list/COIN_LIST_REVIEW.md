# Coin list review (M USD a day, avg of last 7 / 30 complete UTC days)

- Volume pass: one venue >= 100M (crypto) / 1.0M (xStocks) on BOTH 7d and 30d
- Pump/dump chart (Bitunix 1d, last 90 days): one-day move >= 40% (falls as |log|, so -29% = +40%), a day's traded value >= 10x the median day, or listed < 90 days
- CoinDCX: 548 USDT futures; candle volume x close (median |log err| vs 24h ticker 0.13, 93 coins)
- Delta: 250 live perps; candle volume (contracts x value) x close (median |log err| vs 24h ticker 0.14, 29 coins)
- Bitunix: 794 pairs

## crypto

| Coin | Verdict | Scanned | DCX 7d | DCX 30d | Delta 7d | Delta 30d | Bitunix 30d | Day max | Week max | Vol spike | Age d | 90d move | Chart flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTC | keep | yes | 10882.1 | 10497.8 | 1089.7 | 952.5 | 1973.6 | 7% | 24% | 3.0x | 400 | +17% | - |
| ETH | keep | yes | 7386.0 | 7408.9 | 612.1 | 610.1 | 1135.0 | 17% | 34% | 3.1x | 400 | +17% | - |
| ZEC | keep | yes | 1994.0 | 1706.5 | 12.1 | 10.5 | 72.4 | 29% | 76% | 8.8x | 400 | +147% | - |
| SOL | keep | yes | 1400.5 | 1470.7 | 130.7 | 134.9 | 259.1 | 11% | 30% | 2.7x | 400 | +18% | - |
| HYPE | keep | yes | 676.4 | 640.3 | 1.0 | 1.1 | 36.9 | 19% | 44% | 4.3x | 400 | +44% | - |
| NEAR | keep | yes | 431.9 | 637.3 | 0.5 | 0.9 | 41.7 | 20% | 89% | 3.0x | 400 | +134% | - |
| XRP | keep | yes | 652.8 | 621.1 | 12.4 | 12.4 | 95.9 | 15% | 53% | 4.8x | 400 | +13% | - |
| BNB | keep | yes | 327.3 | 344.8 | 2.6 | 2.3 | 21.1 | 9% | 17% | 4.0x | 400 | +16% | - |
| PEPE | keep | yes | 333.4 | 335.2 | 0.4 | 0.3 | 22.2 | 28% | 59% | 5.3x | 400 | +69% | - |
| DOGE | keep | yes | 276.1 | 300.2 | 2.9 | 4.3 | 27.8 | 14% | 34% | 4.1x | 400 | +3% | - |
| ENA | keep | yes | 209.7 | 257.1 | 0.1 | 0.2 | 15.0 | 25% | 97% | 5.3x | 400 | +83% | - |
| WLD | keep | yes | 140.1 | 233.5 | 0.1 | 0.3 | 11.3 | 16% | 43% | 2.8x | 400 | +7% | - |
| UNI | keep | yes | 217.4 | 202.4 | 10.4 | 9.6 | 12.1 | 16% | 61% | 5.4x | 400 | +81% | - |
| SUI | keep | yes | 157.6 | 202.2 | 0.4 | 0.5 | 22.2 | 18% | 49% | 4.1x | 400 | +25% | - |
| ADA | keep | yes | 112.9 | 138.6 | 0.5 | 0.8 | 10.6 | 15% | 30% | 3.0x | 400 | -7% | - |
| LINK | keep | yes | 126.4 | 119.3 | 2.2 | 1.9 | 19.6 | 12% | 34% | 4.6x | 400 | +32% | - |
| STRK | remove | yes | 29.1 | 193.8 | 0.2 | 7.1 | 13.4 | 53% | 110% | 75.0x | 400 | +72% | day 53%, vol spike 75x |
| BTW | remove | yes | 51.3 | 165.3 | 1.6 | 5.7 | 6.0 | 45% | 111% | 11.8x | 153 | +463% | day 45%, vol spike 12x |
| FIL | remove | yes | 61.8 | 118.5 | 0.2 | 0.7 | 7.0 | 19% | 28% | 5.4x | 400 | +13% | - |
| AVAX | remove | yes | 93.5 | 114.1 | 2.1 | 2.5 | 8.6 | 23% | 56% | 7.8x | 400 | +28% | - |
| TAO | remove | yes | 72.1 | 99.7 | 0.1 | 0.2 | 10.9 | 22% | 45% | 2.9x | 400 | +11% | - |
| AAVE | remove | yes | 100.5 | 95.7 | 7.9 | 6.9 | 6.5 | 24% | 65% | 4.4x | 400 | +45% | - |
| QNT | remove | yes | 51.1 | 93.7 | 0.3 | 0.7 | 4.5 | 89% | 346% | 116.9x | 400 | +237% | day 89%, vol spike 117x |
| ONDO | remove | yes | 53.5 | 80.4 | 0.2 | 0.2 | 7.9 | 27% | 40% | 8.8x | 400 | +5% | - |
| RLC | remove | yes | 5.8 | 55.7 | 0.0 | 1.5 | 2.0 | 100% | 185% | 301.6x | 400 | +60% | day 100%, vol spike 302x |
| PUMP | skip: no Bitunix | - | 113.2 | 164.8 | 0.2 | 0.3 | - | - | - | - | - | - | - |
| JCT | skip: chart | - | 131.6 | 145.2 | 5.2 | 3.4 | 5.7 | 169% | 264% | 147.3x | 362 | -21% | day 169%, vol spike 147x |
| AKE | skip: chart | - | 246.9 | 114.5 | 50.4 | 27.0 | 6.7 | 118% | 855% | 19.5x | 400 | +36% | day 118%, vol spike 20x |
| AIN | skip: chart | - | 163.5 | 111.2 | 26.5 | 17.2 | 6.2 | 640% | 665% | 190.7x | 400 | +96% | day 640%, vol spike 191x |

## xstock

| Coin | Verdict | Scanned | DCX 7d | DCX 30d | Delta 7d | Delta 30d | Bitunix 30d | Day max | Week max | Vol spike | Age d | 90d move | Chart flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SNDK | keep | yes | 0.0 | 0.0 | 10.2 | 5.5 | 79.5 | 27% | 58% | 5.5x | 226 | -32% | - |
| TSLA | keep | yes | 0.0 | 0.0 | 1.3 | 1.1 | 9.8 | 13% | 18% | 5.3x | 240 | +9% | - |
| SOXL | remove | yes | 0.0 | 0.0 | 2.4 | 2.1 | 33.7 | 61% | 117% | 7.8x | 174 | -67% | day 61% |
| META | remove | yes | 0.0 | 0.0 | 0.4 | 0.5 | 2.7 | 10% | 15% | 5.4x | 226 | +3% | - |
| NVDA | remove | yes | 0.0 | 0.0 | 0.5 | 0.4 | 5.3 | 11% | 16% | 5.8x | 234 | -16% | - |
| MRVL | remove | yes | 0.0 | 0.0 | 0.4 | 0.3 | 1.0 | 19% | 58% | 5.4x | 174 | -35% | - |
| QQQ | add | - | 0.0 | 0.0 | 2.6 | 2.4 | 8.1 | 7% | 9% | 6.0x | 230 | -9% | - |
| KORU | skip: chart | - | 0.0 | 0.0 | 1.0 | 1.4 | 31.5 | 63% | 81% | 3.9x | 108 | -59% | day 63% |

