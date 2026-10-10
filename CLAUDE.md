# discord alert — Victus Indicator Strategy

Python crypto alert bot. Watches a fixed watchlist on the `4h` timeframe, rebuilds the
active supply and demand zones from the TradingView Pine logic, and alerts when price
gets close to one of those levels. A separate, isolated 30-minute workflow uses the same
logic and watchlist but keeps its own cooldown state and its own Discord webhook.

The most active project here — 4,781 commits, and the only one with an offsite copy.

## Running it

Live, everything runs on GitHub Actions (README.md has the workflow table). Locally,
with the Windows venv (`.venv`):

```powershell
.venv\Scripts\python.exe scanner.py --once             # single zone scan
.venv\Scripts\python.exe fib_trendline_scanner.py --dry-run
.venv\Scripts\python.exe -m pytest -q
```

Bitunix, Delta and Yahoo may be unreachable from a sandbox; `research/` jobs that need
candles run on Actions through `bitunix_research.yml` (input `parts`, matched whole-word).

`pandas` resolved to **3.0.5**, a major version above the `>=2.0` in `requirements.txt`.
Nothing broke, but suspect it first for any dataframe-shaped bug.

## Configuration

All in `config.py`, which **is tracked in git**:

- `WATCHLIST` — the 31 symbols scanned: 23 crypto, 6 xStocks, XAUT + SLVON (64 on
  2026-09-01, cut on Delta volume and again when CoinSwitch was dropped)
- `DELTA_LISTED_SYMBOLS` — the 31 symbols Delta India lists. Since 2026-09-16 `WATCHLIST`
  (crypto, other, and xStock combined) equals it exactly. `entry_confirm.py` used to tag
  each ping with the venue ("Delta"); dropped 2026-10-08 (lakky) - its crypto prices come
  from Bitunix, so the tag read as the wrong source. Entry confirm watches only fib and
  trendline alerts on 1D/1W/1M, crypto and NSE, since the same day.
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
- branch: `main`; runtime state on `scanner-runtime-state` (never merge it); `claude/*`
  branches are PR branches

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

## Fib + trendline alerts (added 2026-09-29)

`fib_trendline_scanner.py` — Shiva asked for fib and trendline alerts in Discord channels of
their own, on 4H / 1D / 1W / 1M, for crypto and NSE (30m is built but off - see below). Separate from the zone alerts in
every way: own state (`fib_trendline_state.json`, alert records and results, all on the
runtime-state branch), own workflow (`fib_trendline_scan.yml`, runs after each 30m crypto scan
finishes via `workflow_run`), and two webhooks — `DISCORD_FIB_WEBHOOK_URL` → `#fib-alerts`,
`DISCORD_TRENDLINE_WEBHOOK_URL` → `#trendline-alerts` (under CRYPTO in the VICTUS Alert System
server). Since 2026-10-02 each market can have its own pair: `DISCORD_{FIB,TRENDLINE}_{CRYPTO,NSE}_WEBHOOK_URL`,
each falling back to the shared one above when unset (so nothing changes until they are added). Every alert's first line
ends `· **4H NSE**` / `· **4H Crypto**` (bold). Since 2026-10-08 (lakky) alerts are 3-4 short lines, prices at five
significant figures (`price_text`); nothing parses the text - records carry the plan.

| File | Role |
|---|---|
| `fib_engine.py` | verbatim copy of `../indicator improvent by claude/fib_reference.py` (v12.3 fib spec). Re-copy below the marker when the reference changes; the test fails locally if they differ |
| `trendlines.py` | port of the indicator's Pine §6b (v11.0); `history=True` keeps trimmed lines for replay |
| `fib_trendline_data.py` | candles: Delta (paged, 4000/request) for crypto, Yahoo for NSE (4H built from 1h at 09:15) |
| `fib_trendline_trades.py` | the trade rules - one `simulate` for both the history backtest and the daily report |
| `fib_trendline_backtest.py` | history replay → `reports/FIB_TRENDLINE_BACKTEST.md` |
| `fib_trendline_daily_report.py` | scores live alerts once a day after 08:00 IST → daily-backtest channel |

- **Band (Shiva, 2026-09-29): alert from 0.75% away down to 0.00%** (`FIB_TL_MAX_DISTANCE_PCT`;
  it was 1.5% first - the backtest at both is in `config.py`),
  same for every timeframe. Fib distance is to the zone's near edge; trendline distance to the
  line, and price through the line before a close shows as 0.00%. Changing what counts as an
  alert means bumping `SEED_VERSION`, or the first pass posts everything the new rule catches.
- **30m is off (Shiva, 2026-09-29).** At the 1.5% band the history backtest counted ~530 30m
  alerts a day (crypto + NSE), 90% of the total; 4H-1M is ~75/day. `FIB_TL_TIMEFRAMES` turns it back on.
- **Backtest verdict (2026-09-29): no edge.** Read win rates against the report's random-level
  baseline (37-46% at 1R under these rules), not 50%. Fibs and trendlines land at or below it on
  nearly every timeframe; crypto 1W fib is the only one above, on 115 trades.
- **Trade rules (Shiva's choice):** fib entry at the zone's near edge - his EX 2 ETH trades
  (2723.94); SL on the inner fib's 0.55 line until 2026-10-08 (now the S/R rule, below). The first version used the inner 0.66 as entry,
  which misread EX 2 and made stops ~4x too tight; trendline entry
  at the line, SL `TRENDLINE_SL_PCT` beyond it; 1R and 2R targets; wait 5 / hold 20 candles of
  the alert's timeframe. A candle touching SL and target counts as SL.
  **Breakeven (2026-10-03, Lakky):** the zone trades' rule - at +0.5R the stop moves past entry by
  `BREAK_EVEN_OFFSET_PCT` (NSE) / `CRYPTO_BREAK_EVEN_OFFSET_PCT` (crypto) from the next candle, imported
  from `daily_backtest_summary` so the two cannot drift. Exits there are `BE`: in net R, not in win rate.
- Crypto and xStocks: Bitunix (`CRYPTO_CANDLE_SOURCE`), XAUT/SLVON: Delta. `1M` is built from
  daily candles by calendar month. **No Delta fallback here (2026-10-09):** Delta's history starts
  Dec 2023 and Bitunix's years earlier, so the same chart on Delta is a different fib under a new key -
  BNB 1M re-alerted on 2026-10-09 with a 2024 base and the entry above price. A pass with Bitunix
  down skips the symbol. `SEED_VERSION` v7 (xStocks moved to Bitunix) re-seeds silently.
- NSE: the zone scanner's 200 stocks (`nse_scanner.load_watchlist`), scanned only in the session
  and at most every 8 minutes - that pass takes ~3 minutes (Yahoo, 5 intervals).
- **Audit, 2026-09-29** (fixed, each with a test): the fib engine is a state machine whose end
  state depends on where history starts - a 1500-candle 4H window disagreed with full history on
  5.7% of bars - so 4H and NSE daily+ load everything; trendlines converge and don't care. Touch
  alerts are approach-side only (price through a support before the close used to post BUY). One
  current price per symbol across timeframes. State is saved before anything that can raise, and
  persisted `if: always()`, so posted alerts can't be re-sent. Replay == live verified on 225 bars.
- **Trendline swing length stays 10 (Lakky, 2026-10-05).** A line appears only once its second
  swing has 10 candles after it, here and in Pine (`tl_len`). Backtested 3/5/7/10/15/20 on
  trendlines only (`research/trendline_length_backtest.py`, `research/out/trendline_length/`): every
  length scores ~-0.28R a trade at ~24% wins - the length only changes how many alerts there are.
  "Alert but no line on my chart" has so far always been the chart, not the bot: wrong timeframe
  (a 4H alert on a 30m chart) or feed (INDEX vs Bitunix/Delta); `research/trendline_trace.py` checks.
- **Trendline anchors, v12.5 (Lakky, 2026-10-07, HYPE 1D).** A support line is drawn only when a
  swing low is above the previous swing low, from the candle low between them that the line rests on
  (no low in between under it); resistance mirrors it. Up to v12.4 a swing joined the *earliest*
  earlier swing no swing in between cut, so lines started far back, came in twins, and candles sat
  through them (Aug 2 -> Sep 15 instead of Aug 19 -> Sep 15). Backtest
  (`research/trendline_anchor_backtest.py`): 27,862 alerts / -6,762R vs 46,452 / -10,670R, same
  ~-0.29R a trade. `SEED_VERSION` v4 re-seeds silently.
- **Trendlines, v12.6 (Lakky, 2026-10-07, HYPE 4h) - the live rule.** v12.5 drew nothing for a swing
  low below the one just before it, so HYPE 4h Aug 19 58.10 -> Sep 15 75.13 was missing (Sep 11 and
  Sep 13 are lower lows). Now a new swing low joins the most recent earlier swing low *below* it,
  still resting on the candle low between them, and a new line replaces an older one from the same
  candle (no twins). `anchor="last_lower_unique"`; `tangent` (v12.5) and the rest stay for research.
  Backtest: 46,909 alerts / -11,488R vs v12.5's 28,123 / -6,847R, same ~-0.30R a trade; no candle
  through a line, 0% twins on the chart (`research/out/trendline_anchor/`). `tests/test_trendline_anchor.py`
  holds the HYPE 1D and 4h lines (Bitunix fixtures) and a transcription of the Pine v12.6 6b loop -
  change both sides together. `SEED_VERSION` v5 re-seeds silently.
- **Deeper fib zone only (Lakky, 2026-10-08, Notion 20).** Each fib has two boxes; only Zone 2, the
  deeper one, alerts - the lower box for a buy, the upper for a sell (`FIB_ALERT_ZONES`, crypto and NSE;
  the history backtest replays the same rule). Sep 1 - Oct 8 (`research/fib_zone_preference.py`): crypto
  -33.8R / 131 trades with both zones vs -4.6R / 47 deeper only; NSE -151.7R vs -71.7R, though NSE's
  deeper zone is worse per trade (-0.49R vs -0.33R) - kept on Lakky's call. Pine fib alerts are not changed.
- **Fib stop = the S/R zone rule (Lakky, 2026-10-08).** `FIB_SL_HEIGHT_PCT` (= `ZONE_SL_HEIGHT_PCT`, 25%)
  of the box's height beyond its far edge, as `scanner.planned_stop_price`; it was the inner 0.55 line
  inside the box. Deeper zone, Sep 1 - Oct 8 (`research/fib_sr_logic_backtest.py`): crypto -5.7R -> -3.1R,
  NSE -72.8R -> -30.5R, same alert count. The S/R 1.5% stop cap (-75% alerts) and daily trend filter
  (worse for crypto fibs) were tested and not applied. The Pine chart's fib SL lines still show 0.55/0.66.
  `SEED_VERSION` v6 re-seeds silently.
- **No late BROKEN alerts (Lakky, 2026-10-05).** A break posts only if its candle closed after
  the market's previous awake pass (`__last_scan__` in the state, `BREAK_GRACE_SECONDS` = 1h of
  catch-up). PFIZER's 1M break on September's close posted on Oct 5 while the other 1M breaks went
  out on Oct 1; a break first seen sessions later is now dropped.
- Each channel seeds silently per market on its first pass with a webhook, so adding a webhook
  never dumps a backlog. Deleting the state file re-seeds rather than bursting.
- `python fib_trendline_scanner.py --dry-run [--force-nse]` prints what would alert, sends nothing.

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
  Since 2026-10-02 that includes the planned entry and stop (`planned_stop_price`, v7's
  `zone_pct` rule): NSE had kept a fixed 0.10%-beyond-the-far-edge stop until then.

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
- **Delivery rules (2026-10-02).** A send that fails retries after `FAILED_ALERT_RETRY_SECONDS`
  (10 min), not the full 4h cooldown (`scanner.alert_due`, shared by NSE). Crypto and NSE save
  state right after each delivered alert; entry_confirm saves after each digest part and rolls
  back only the records whose lines did not land. The crypto range-filter *signal* runs on
  closed candles (`scanner.confirmed_candles`), like NSE; zones still use the forming candle.
- **Zone alert text (2026-10-08, lakky).** `**BTC | BUY | 4H | 5/10**`, then `Price` / `Zone` / `SL`
  lines; prices at most 3 decimals from 1 up, 2 from 1000 up (`scanner.price_text` / `short_places`,
  widened only if two levels would print the same; under 1 keeps `price_decimals`). The journal's
  "Import Alert Signals" parses pasted alerts (`parseSignals`): keep "SYMBOL | SIDE" first, the score
  last and each level line starting with its name - `JournalImportCompat` in `tests/test_alert_format.py`.
- **Approach side only (2026-10-02, Lakky).** Distance to the entry is measured both ways, so price
  already through the entry used to alert as "0.15% away" (19-37% of alerts). `scanner.price_past_entry`
  now blocks those for crypto and NSE; the band is still consumed, so a bounce back out does not fire.
- **Daily trend filter, crypto only (2026-10-04, Lakky).** A crypto demand zone alerts only
  while the last closed daily candle is above its EMA50, a supply zone only below
  (`CRYPTO_TREND_FILTER`, `scanner.daily_trend`). Counter-trend zones get no alert; an unknown trend (fetch failed, short history) never blocks. Backtested on
  564 recorded trades: -79R -> -8R. NSE, xStocks and "other" are not filtered - it did
  not help them. Research and numbers: `research/out/RESULTS.md`.
- **Daily report scoring (2026-10-04).** Only +2R is an exit. A trade that touches +1R and
  comes back is closed by the live stop (BE), and "+1R" now means "reached +1R, closed by
  the time limit", priced at that close. It used to be credited a flat 1R either way.
- **Trail test shadow score (2026-10-04, Lakky).** Every filled zone trade is also scored as
  if the stop trailed 0.25R behind the best price once +0.5R traded (`TRAIL_START_R`,
  `TRAIL_DISTANCE_R`, `trail_shadow_r`) - the best of 119 exit rules in
  `research/out/RESULTS.md`. Stored as `trail_net_r` and shown as "Trail test" beside
  TOTAL in the daily report. It changes no trade and no alert; it is there to be watched.
- **Crypto alert candles come from Bitunix (2026-10-05, Lakky).** `CRYPTO_CANDLE_SOURCE`
  (`VICTUS_CRYPTO_CANDLE_SOURCE`, default `bitunix`; `delta` switches back). Zones, entry_confirm,
  the daily trend filter and fib/trendline levels are drawn from Bitunix (`bitunix_data.py`); a
  Bitunix failure falls back to Delta, except in the fib/trendline scan (below). Trades are still taken on Delta, so the daily backtest grades
  on Delta candles with Delta fees - do not move those, and paper trading fills on Delta too
  (`backtest.crypto_fetch_ohlcv`; it read Bitunix-first bars until 2026-10-09). XAUT and SLVON stay
  on Delta. **xStocks alert off Bitunix since 2026-10-09 (lakky)**: Bitunix lists all six under
  their own names (`BITUNIX_XSTOCK_PAIRS`, e.g. `TSLAXUSD` -> `TSLAUSDT`), and `bitunix_data.pair_for`
  maps them. Probe and replay: `research/xstock_bitunix_probe.py`, `research/out/xstock/`.
  Why: Delta prints thin/zero-volume candles on small coins. Research: `research/bitunix_compare.py`.
  **Bitunix's kline endpoint never returns the forming candle, and a page asked to end in the future
  comes back short** (`research/bitunix_window_probe.py`). Until 2026-10-07 that left the zone scan
  with 199 candles instead of `OHLCV_LIMIT` and no forming candle, and fib/trendline alerts measured
  against the last *closed* 4H close. Now `bitunix_data.klines` never asks past now, the zone scan
  builds the forming candle from 1m (`bitunix_data.forming_candle`), and fib/trendline crypto alerts
  use `bitunix_data.last_price`. `tests/test_bitunix_source.py`'s fake serves the API's real shape.
  **A page's endTime must sit on a candle open (2026-10-09).** There it is exclusive and correct; off
  an open Bitunix drops a candle and gives the next one its open (`research/bitunix_page_probe.py`).
  Paging by "oldest - 1ms" lost one candle per 200 (UNI 30m: 7 in 1500, a demand zone that did not
  rebuild). `klines` now pages on candle opens; the test fake refuses any other endTime.
- **Watch rows are gone (2026-10-09).** `crypto_watch_records*.jsonl` fed entry confirm's zone
  watch; once entry confirm moved to fib/trendline only nothing read them. Old `_watch` /
  `_silent_ready|` state keys are dropped on load. The old files may remain on the state branch.
- **XAUT is "other", not crypto, in the reports (2026-10-09).** `market_class` still named PAXG.
- **CoinSwitch is gone (2026-10-09, lakky: no longer trades there).** Its fetch, signing, 1m top-up,
  fine price and deep-history splice are removed, with the `COINSWITCH_*` secrets in the workflows
  (they can be deleted from GitHub too). The candle chain is Bitunix, Delta, then the ccxt fallbacks.
- **Status posts once per dispatch (2026-10-09, lakky).** The scan loop runs every ~90s; started /
  finished went out on every pass. Now only the first pass posts (`scanner.first_pass_this_loop`,
  shared by NSE); a later pass posts only when most symbols failed or, on NSE, an alert failed to send.
- **Range filter alerts are off (2026-10-10, lakky).** Alerts are S/R zones, fibs and trendlines
  (incl. TL BROKEN) only. `ALERT_RANGE_FILTER_SIGNALS` is False in `config.py` and `nse_config.py`; the
  range filter is still computed but never posts. Pine v12.7.8 drops its RF marker too.
- There is an astrology component (`astrology_engine.js`, `ASTROLOGY_SETUP.md`) with its
  own agent branches.
