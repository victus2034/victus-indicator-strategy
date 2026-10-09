# Victus Indicator Strategy

Discord alert bot for the Shiva / Victus TradingView indicator. It rebuilds the
indicator's levels in Python and posts when price comes near one, so an alert in
Discord is one the chart would have fired.

Three kinds of alert, each with its own channels and state:

| Alert | Timeframes | Markets | Code |
|---|---|---|---|
| Supply / demand zones | 4H, 30m | crypto, xStocks, gold/silver, NSE | `scanner.py`, `nse_scanner.py` |
| Fib zones and trendlines | 4H, 1D, 1W, 1M (30m built, off) | crypto, xStocks, gold/silver, NSE | `fib_trendline_scanner.py` |
| Entry confirm | 1D, 1W, 1M fib + trendline alerts | crypto, NSE | `entry_confirm.py` |

Everything runs on GitHub Actions. There is no server.

## Watchlist

`config.py` holds it. 31 symbols, exactly the ones Delta India lists (`DELTA_LISTED_SYMBOLS`):

- `CRYPTO_WATCHLIST`: 23 coins (BTC, ETH, SOL, ...)
- `XSTOCK_WATCHLIST`: 6 tokenised stocks (TSLA, META, SOXL, SNDK, MRVL, NVDA)
- `OTHER_WATCHLIST`: XAUT (gold) and SLVON (silver)

NSE scans 200 stocks, market-cap ranks 100-300 (`NSE_RANK_START`/`END` in `nse_config.py`, `nse_scanner.load_watchlist`).

## Where the candles come from

| What | Source |
|---|---|
| Crypto alert levels (zones, fibs, trendlines, entry confirm, daily trend filter) | Bitunix, Delta if Bitunix fails (zones only) |
| xStock alert levels | Bitunix pairs in `BITUNIX_XSTOCK_PAIRS` (since 2026-10-09), same fallback |
| XAUT, SLVON | Delta |
| Trades, fees, daily backtest, paper trading | Delta (the venue trades are taken on) |
| NSE | Yahoo Finance |

Bitunix never returns the candle still forming; `bitunix_data.forming_candle` builds it from 1m.
The fib/trendline scan has no Delta fallback: Delta's shorter history draws different fibs.

## Alert rules (short)

- Zones: alert from 0.00% to 0.20% from the entry edge (`MAX_DISTANCE_PCT`), approach side only,
  stop 25% of the zone height past the far edge, stops wider than 1.5% skipped, 4h cooldown,
  crypto alert window 08:00-01:00 IST. Crypto only: daily EMA50 trend filter.
- Fibs: deeper (strong) zone only, entry at its near edge, stop = the zone rule. Band 0-0.75%.
- Trendlines: v12.6 anchors, band 0-0.75%, stop `TRENDLINE_SL_PCT` beyond the line, BROKEN posts
  only on the first scan after the break candle closes.

`CLAUDE.md` has the reasoning and the backtest behind each rule. Change a rule only after a backtest.

## Workflows

Most are dispatched by cron-job.org (GitHub's own cron was too unreliable).

| Workflow | What it does |
|---|---|
| `scan.yml`, `scan_30m.yml` | crypto zone scans, 4H and 30m (loops every ~90s inside a run) |
| `nse_scan.yml`, `nse_scan_30m.yml` | NSE zone scans, market hours only |
| `fib_trendline_scan.yml` | fib + trendline alerts, runs after each 30m crypto scan |
| `entry_confirm.yml` | entry-confirmed digest |
| `daily_backtest_summary.yml`, `weekly_backtest_summary.yml`, `daily_catchup.yml` | scores alerts on real candles, posts the reports; paper trading |
| `daily_astrology.yml`, `weekly_astrology.yml` | astrology posts (`astrology_engine.js`) |
| `tests.yml` | the test suite on every push |
| `bitunix_research.yml`, `research_backtest.yml`, `backtest_audit.yml` | research only, run by hand |

Runtime state (cooldowns, alert records, results) lives on the `scanner-runtime-state` branch,
restored and pushed by `.github/scripts/restore_runtime_state.sh` / `persist_runtime_state.sh`.
Locally it is gitignored. Deleting it resets cooldowns.

## Secrets

Set as GitHub Actions secrets, never in `config.py` (this repo is public; the fields there stay empty).

- `DISCORD_WEBHOOK_URL`, `DISCORD_30M_WEBHOOK_URL`, `DISCORD_NSE_WEBHOOK_URL`, `DISCORD_NSE_30M_WEBHOOK_URL`, `DISCORD_STATUS_WEBHOOK_URL`
- `DISCORD_FIB_WEBHOOK_URL`, `DISCORD_TRENDLINE_WEBHOOK_URL`, and per market
  `DISCORD_{FIB,TRENDLINE}_{CRYPTO,NSE}_WEBHOOK_URL`
- `DISCORD_ENTRY_CONFIRM_WEBHOOK_URL`, `DISCORD_DAILY_BACKTEST_WEBHOOK_URL`,
  `DISCORD_PAPER_TRADING_WEBHOOK_URL`, `DISCORD_ASTROLOGY_WEBHOOK_URL`

## Files

| File | Role |
|---|---|
| `scanner.py` | crypto zone engine and scan (the one zone engine; NSE imports it) |
| `nse_scanner.py`, `nse_scanner_30m.py`, `nse_config.py` | NSE scan, session hours, Yahoo data |
| `bitunix_data.py` | Bitunix candles, forming candle, live price, xStock pairs |
| `fib_engine.py`, `trendlines.py` | fib and trendline ports of the Pine |
| `fib_trendline_scanner.py`, `fib_trendline_data.py`, `fib_trendline_trades.py` | fib/trendline alerts, candles, trade rules |
| `fib_trendline_backtest.py`, `fib_trendline_daily_report.py` | history backtest, daily fib/trendline report |
| `entry_confirm.py` | entry-confirmed digest |
| `daily_backtest_summary.py`, `weekly_backtest_summary.py` | zone trade scoring and reports |
| `paper_trading.py` | paper trades on Delta candles |
| `zone_scoring.py`, `crypto_zone_rating.py`, `xstock_hybrid_rating.py`, `rating_validation_report.py` | the 1-10 zone score on each alert |
| `research/` | backtests and probes; results in `research/out/` |
| `reports/FIB_TRENDLINE_BACKTEST.md` | fib/trendline history backtest |
| `tests/` | `python -m pytest -q` |

## Running locally

```powershell
pip install -r requirements.txt
python scanner.py --once                    # one crypto zone scan
python fib_trendline_scanner.py --dry-run   # what fib/trendline would alert, sends nothing
python -m pytest -q
```

Without webhooks set, nothing is posted. Run `tests/test_indicator_scanner_parity.py` and
`tests/test_six_worked_examples.py` after any change to the zone code.
