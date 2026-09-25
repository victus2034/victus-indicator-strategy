# discord alert — Victus Indicator Strategy

Python crypto alert bot. Watches a fixed watchlist on the `4h` timeframe, rebuilds the
active supply and demand zones from the TradingView Pine logic, and alerts when price
gets close to one of those levels. A separate, isolated 30-minute workflow uses the same
logic and watchlist but keeps its own cooldown state and its own Discord webhook.

The most active project here — 4,781 commits, and the only one with an offsite copy.

## Running it

There is a venv here (`.venv`, 48 packages, created 2026-09-01):

```powershell
.venv\Scripts\python.exe scanner.py            # continuous
.venv\Scripts\python.exe scanner.py --once     # single scan
```

Verified working 2026-09-01: a `--once` run scanned **64/64 symbols, 0 failures**
against live Binance data in ~2 minutes.

`pandas` resolved to **3.0.5**, a major version above the `>=2.0` in `requirements.txt`.
Nothing broke, but suspect it first for any dataframe-shaped bug.

## Configuration

All in `config.py`, which **is tracked in git**:

- `WATCHLIST` — the symbols scanned (the README still says "10 coins"; it is 36 as of
  2026-09-15: 64 as of 2026-09-01 cut from 119 on seven-day Delta volume, then
  `CRYPTO_WATCHLIST` cut again to drop every CoinSwitch-only crypto symbol once
  Shiva stopped trading there - see `config.py`'s note on that list)
- `DELTA_LISTED_SYMBOLS` — the 31 symbols Delta India lists. `entry_confirm.py` tags
  each alert with the venue this way; since 2026-09-16 `WATCHLIST` (crypto, other,
  and xStock combined) equals `DELTA_LISTED_SYMBOLS` exactly, so that tag only ever
  reads "Delta" now - no symbol on the watchlist is CoinSwitch-only any more.
  Static on purpose; re-audit against Delta's `/v2/products` when the watchlist changes
- `EXCHANGE_IDS` — exchange fallback order
- `MAX_DISTANCE_PCT` — how close price must get before alerting
- `DISCORD_WEBHOOK_URL`, `DISCORD_STATUS_WEBHOOK_URL`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — only if Telegram becomes available again

All four credential fields are currently empty strings, and that is deliberate. Fill them
locally and **never commit real values** — this repo is on GitHub. Verified clean as of
2026-09-01: the only webhook URLs anywhere in the tree are `webhooks/123/token` test
placeholders in `tests/test_daily_backtest_summary.py`.

## Git

- remote: `github.com/victus2034/victus-indicator-strategy`
- branch: `main`; also `backup-before-revert`, `agent/astrology-corrections-v2`,
  `agent/daily-astrology`
- last commit Aug 31 12:36, clean tree

## Staying in step with the indicator

The zone logic here is a port of `Shiva_Indicator_v7.pine` (in
`../indicator improvent by claude/`), and the point of running it live is that an
alert is one the chart would have fired. **`tests/test_indicator_scanner_parity.py`
holds that.** It replays `build_zones` against `tests/pine_v7_reference.py` — a
transcription of the Pine source, written from the Pine and not from this
scanner — and asserts the surviving zone sets are identical. Change either side
of the geometry and run it.

Two rules in there are unreachable from a synthetic random walk (over 24,000
generated bars neither fired once), so the test also carries 800 real 30m candles
in `tests/fixtures/`. Do not replace that fixture with generated data.

The one place the two legitimately differ: a wick with no height. The chart floors
the box at `syminfo.mintick`; the scanner has no tick size for a symbol and floors
at 1% of ATR. It moves only the near edge, and only on a wick that had no height
to begin with.

**`tests/test_six_worked_examples.py` is the other half — run it alongside the
parity test, not instead of it.** Six zones Shiva drew by hand on real TradingView
charts, then measured pixel-by-pixel off each chart's own price axis: both the
input candles and the expected box edges came from the screenshot, not from code.
The source images are in `TRADINGVIEW SCRIPT INDICATOR IMG EXAMPLE/EX 1`
through `EX 6` (untracked — local only, back them up separately), and every
example in the test names the exact screenshot it was measured from
(`"EX3/40"` → `EX 3/Screenshot (40).png`). EX6 is the case that caught the
4h `base_extra` bug the synthetic parity test could not — it never exercises 4h.

**Run this test after every change to `scanner.py`'s zone-building path
(`qualify_wick_zone`, `tighten_wide_zone`, ATR, `ZONE_BASE_EXTRA`, pivot/swing
logic) — not just when the geometry itself changes.** The 4h `base_extra` bug
was a change elsewhere that silently stopped re-deriving a value this test
depends on; nothing about the zone-building code itself looked different.

**When Shiva adds a new worked example (EX7 and beyond), it must be added
here too, the same way:** a new `EX N` folder of screenshots, and a new entry
in `EXAMPLES` in `tests/test_six_worked_examples.py` with the OHLC values and
drawn box measured off that image, named `"EX<N>/<screenshot number>"`. The
test file name will then undercount, but the loop iterates `EXAMPLES` itself,
so nothing else needs to change. Do not consider a scanner change verified
against these examples until every entry in `EXAMPLES` has been checked, not
just the ones that existed when the file was named.

## Gotchas

- **There is a cap on zone width and deliberately no floor.** `ZONE_MAX_WIDTH_PCT`
  is the EX 6 rule and handles a zone that comes out too wide. Nothing handles one
  that comes out too thin: measured over 42 symbols, 91 of 886 live zones (10.3%)
  plan a stop under 0.10% — the round-trip cost
  (`daily_backtest_summary.CRYPTO_ROUND_TRIP_COST_PCT`) — the smallest at 0.003%,
  where fees are 2.7x the risk.

  **Asked and answered, 2026-09-07: leave it.** The zones are to be the ones the
  indicator draws, and nothing else. A minimum width would mute levels the chart
  shows, and matching the chart is the requirement that outranks it. Do not add
  one, on the alert side either — the stop distance is already printed on every
  alert, and skipping a thin one is a reading decision, not a code one.
- Alert state is gitignored and machine-local: `alert_state*.json`,
  `nse_alert_state*.json`, `crypto_alert_records*.jsonl`. Deleting these resets cooldowns
  and can cause a burst of duplicate alerts on the next run.
- The 30-minute workflow is deliberately isolated. Changing shared zone logic affects both
  it and the 4h flow — check both before assuming a fix is local. **Since 2026-09-25 it
  also affects NSE** (next bullet).
- **NSE runs crypto's zone engine — there is no second copy, and there must not be one.**
  `nse_scanner.py` used to keep a private copy of `atr / find_pivots / build_zones /
  qualify_wick_zone / record_zone_touch / too_young_to_alert / nearest_active_zone` and its
  own numbers in `nse_config.py`. When crypto moved to the v7 wick rules the copy stayed on
  the old ATR band, a plain drop-the-oldest buffer and a close-through break, so the two
  markets silently ran different strategies for weeks. Now `nse_scanner` aliases the
  `scanner` functions (`nse_scanner.build_zones is scanner.build_zones`) and `nse_config`
  imports its zone numbers from `config.py`, so a change to either is a change to both.
  `tests/test_nse_shares_crypto_engine.py` fails if a copy comes back.

  The engine reads one timeframe-dependent number, `ZONE_BASE_EXTRA` (30m → 5, 4h → 1).
  `nse_scanner.bind_zone_engine()` sets it from NSE's own timeframe when NSE actually scans
  (in `scan_symbol`), not at import, so a crypto-only process that merely imports
  `nse_scanner` is never reconfigured.

  NSE builds zones on the candle still forming, like crypto and the chart (since
  2026-09-25) - a wick through a zone's far edge kills it at once. A half-finished candle
  cannot kill a zone the finished one would not, since its range sits inside the full
  candle's: replayed over 700 mid-bar snapshots of 20 real stocks there were no false
  kills. The one thing that stays on confirmed candles is the range-filter *signal*,
  which unlike a zone can appear on the forming bar and be gone by the close.
  `tests/test_nse_forming_candle.py` pins both.

  Still NSE-only on purpose: session hours and holidays, the yfinance data, the
  500-candle lookback, the watchlist, webhooks and rating display. Not shared: watch
  rows / entry-confirm, the 90-second scan loop and the live ticker are crypto-only, and
  NSE paper trading is paused.
- There is an astrology component (`astrology_engine.js`, `ASTROLOGY_SETUP.md`) with its
  own agent branches.
