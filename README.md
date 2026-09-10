# Victus Indicator Strategy

This bot watches your fixed crypto watchlist on the `4h` timeframe, rebuilds the active supply and demand zones from your TradingView Pine logic, and alerts when price gets close to one of those levels.

It also includes an isolated 30-minute workflow. It uses the same logic and watchlist, but keeps its own cooldown state and sends alerts to a separate Discord webhook.

## Setup

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Edit `config.py`:
   - set your 10 coins in `WATCHLIST`
   - set exchange fallback order in `EXCHANGE_IDS`
   - change `MAX_DISTANCE_PCT` if you want a tighter or wider alert
   - fill `DISCORD_WEBHOOK_URL` if you want Discord alerts
   - fill `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` only if Telegram is available for you again later

3. Run:

```powershell
python scanner.py
```

For a single scan:

```powershell
python scanner.py --once
```

## How alerts work

- 4-hour zone alerts use a `0.25%-1.25%` distance window
- The separate 30-minute cloud workflows use a `0.25%-0.75%` distance window
- Distances below `0.25%` are intentionally ignored because they are too close to manage
- supply alerts use the zone `top`
- demand alerts use the zone `bottom`
- `ALERT_COOLDOWN_SECONDS` stops repeated alerts while price stays near the same level
- `REARM_FACTOR` makes the bot wait until price moves away before it can alert that zone again

## Discord setup

1. In your Discord server, create a channel for alerts.
2. Open the channel settings and create a webhook.
3. Paste the webhook URL into `DISCORD_WEBHOOK_URL` in `config.py`.

## Free cloud option

This project now includes a GitHub Actions workflow at `.github/workflows/scan.yml`.

- It runs `python scanner.py --once`
- it is scheduled every 20 minutes at minutes `1`, `20`, and `40`
- it can also be run manually from the Actions tab
- it commits `alert_state.json` after scans so cooldowns still work in the cloud

Recommended setup:

1. Push this project to GitHub.
2. Add repository secrets named `DISCORD_WEBHOOK_URL` and `DISCORD_STATUS_WEBHOOK_URL`.
3. Keep your scanner config in the repo.
4. Let GitHub Actions run it on schedule.

## 30-minute Discord alerts

The 30-minute scanner runs from `.github/workflows/scan_30m.yml` just after each 30-minute candle closes. It does not change the 4-hour scanner.

1. Create a Discord webhook inside `#30m-alerts`.
2. Add its URL as the repository secret `DISCORD_30M_WEBHOOK_URL`.
3. Keep `DISCORD_STATUS_WEBHOOK_URL` pointed at `#scanner-status`.
4. Run `Victus Crypto Scanner 30m` manually once from GitHub Actions to verify it.

If you keep the repo private, GitHub Free includes limited Actions minutes, so reduce the schedule if needed. If the repo is public, standard GitHub-hosted Actions minutes remain free.

## 30-minute crypto zone ratings

Eligible 30-minute crypto zone alerts include one compact research rating,
shown as a 1-10 score (percentile against `score_reference`) or a grade:

- `A (best tested)`: top 30% of model scores
- `B (mixed)`: middle 30-70th percentile
- `C (weak)`: bottom 30% of model scores

Retrained 2026-09-10 on 340 real decided crypto 30m trades (2026-08-13 to
2026-09-10), reconstructed from live OHLCV and the production zone builder -
not a synthetic backtest. The original model (46 Binance pairs, 365 days,
GradientBoostingClassifier on 32 features) had decayed to *worse* than no
rating at all on live outcomes (grade A: 51.4% win vs 59.0% baseline) and,
separately, a missing `score_reference` in the bundle meant it could only
ever emit three raw scores (3, 6, or 9), not the 1-10 range the code was
built for. The retrain cuts to 4 features
(`current_gap_atr`, `alert_close_location_aligned`, `return_vol20_pct`,
`di_alignment`) to avoid overfitting a dataset this size - a 32-feature
retrain on the same data still overfit (train/test AUC gap of 0.15 vs the
4-feature model's 0.02). Validated by 5-fold expanding-window walk-forward,
not a single split: AUC 0.76-0.92 across folds, mean 0.871.

An `A` rating means better historical relative odds, not a guaranteed
profitable trade. 340 examples across ~4 weeks is still a thin base by ML
standards - re-check with `rating_validation_report.py` as more decided
trades accumulate, and retrain again once volume allows a larger held-out
set. Ratings are intentionally disabled for 4-hour alerts, NSE stocks,
xStocks, and crypto symbols outside the validated universe in
`crypto_zone_rating.py` (now the live crypto watchlist, not a fixed
46-pair list).

## Files

- `scanner.py`: main watchlist scanner and alert loop
- `config.py`: watchlist and alert settings
- `crypto_zone_rating.py`: isolated 30-minute crypto rating feature builder
- `alert_state.json`: created automatically to remember which levels already alerted
