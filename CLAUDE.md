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

## Test twice before "done" (lakky, 2026-10-10)

Never call a change done after one check. Every change gets two:

1. **Run the tests twice**: `python -m pytest -q`, two full runs. Both must pass; a pass
   then a fail is a flaky test to fix, not to ignore. CI runs it twice too (`tests.yml`).
2. **Check it a second, different way**: a `--dry-run` of the scanner you changed, a
   replay on real candles, a number recomputed by hand, or the code broken on purpose to
   confirm a test fails.

Say in the summary what both checks were. Summaries are short bullets: what changed,
what was checked, what's next.

## Configuration

All in `config.py`, which **is tracked in git**:

- `WATCHLIST` — the 33 symbols scanned: 25 crypto, 6 xStocks, XAUT + SLVON (64 on
  2026-09-01, cut on Delta volume and again when CoinSwitch was dropped; 27 crypto added
  2026-10-13 (lakky): every CoinDCX USDT future with 24h volume >= 100M USDT that Bitunix
  lists, commodities left out - `research/coindcx_volume_probe.py`, part `coindcx`; same day
  TAC, ZORA, BLESS, H, VELVET, RIVER and BEAT dropped: 2-20M a day on CoinDCX. **2026-10-16
  (lakky): crypto = average >= 100M USDT a day over BOTH the last 7 and 30 days on CoinDCX or
  Delta, with a Bitunix perp** - `research/volume_7d_30d_probe.py`, part `volume`; 19 removed
  (BCH, AKE, ARB, LTC, TRUMP, INJ, APT, MAGIC, GTC, ZRO, TIA, OGN, W, S, BAT, CAP, RSR, CT, DOS),
  RLC added. A one-day 24h snapshot misleads: MAGIC/W/BAT spiked to 100M+ for a week on a ~40M month)
- `DELTA_LISTED_SYMBOLS` — the 33 watchlist symbols Delta India lists. `WATCHLIST` equals it
  plus `NOT_DELTA_LISTED_CRYPTO` (empty since 2026-10-16; such coins grade their daily backtest
  on the ccxt fallback venues). `entry_confirm.py` used to tag
  each ping with the venue ("Delta"); dropped 2026-10-08 (lakky) - its crypto prices come
  from Bitunix, so the tag read as the wrong source. Entry confirm watches only fib and
  trendline alerts on 1D/1W/1M, crypto and NSE, since the same day.
  Since 2026-10-10 (lakky) it posts one digest per market: NSE to `DISCORD_ENTRY_CONFIRM_NSE_WEBHOOK_URL`,
  crypto (incl. xStocks, XAUT, SLVON) to `DISCORD_ENTRY_CONFIRM_CRYPTO_WEBHOOK_URL`; either unset falls back
  to `DISCORD_ENTRY_CONFIRM_WEBHOOK_URL`.
  **Fills between checks (2026-10-21, lakky: 1D+ entry confirms missing).** 26 of 235 in-hours fills (9-21 Oct)
  got no ENTRY NOW: NSE read only the last 15m close, crypto swept a fixed hour that reached back before the
  alert, and a fill already LATE / stopped by the next check was silent. Now the sweep reads fine candles
  (Bitunix 1m, Yahoo 5m) since the later of the alert and the market's previous check (`sweep_since`,
  `_last_check|<market>` in the state, at most `SWEEP_MAX_SECONDS`), and such a fill sends one ENTRY NOW line
  "filled since the last check" / "filled and stopped since the last check" with the risk used.
  `research/entry_confirm_audit.py` / `entry_confirm_replay.py`, parts `ec-audit` / `ec-replay`.
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
- **Trendline trades, Lakky's way (2026-10-11, live).** SL = the most recent closed candle whose wick, or body,
  is at least `TRENDLINE_STOP_MIN_PCT` (0.75%) past the entry - the closer of the two (`trades.candle_stop`,
  matches 9 of 11 of his hand-marked 1D charts); `TRENDLINE_SL_PCT` only when none. One target at 1R, no
  breakeven, no hold limit (plan `"target_r": 1`, `trades.simulate_1r`); the alert prints `TP x (1R)`.
  Backtested Jun 1 - Oct 11 at ~-0.33R a trade, like the fixed stop - his call to run it and refine it.
  Old records (no `target_r`) keep the BE/2R rules above. Fibs are unchanged.
- Crypto and xStocks: Bitunix (`CRYPTO_CANDLE_SOURCE`), XAUT/SLVON: Delta. `1M` is built from
  daily candles by calendar month. **No Delta fallback here (2026-10-09):** Delta's history starts
  Dec 2023 and Bitunix's years earlier, so the same chart on Delta is a different fib under a new key -
  BNB 1M re-alerted on 2026-10-09 with a 2024 base and the entry above price. A pass with Bitunix
  down skips the symbol. `SEED_VERSION` v7 (xStocks moved to Bitunix) re-seeds silently.
  **A short Bitunix page is asked again (2026-10-12, lakky, BNB 1M).** `klines` took any short page
  as the listing reached; one that came back short by mistake cut the history mid-2024, and BNB 1M's
  fib took an Aug 2024 base (entry 838.05, sent with price already inside the zone) instead of the
  chart's Jun 2022 one (719.15, touched Oct 8). Now a short page that did not reach `start` is re-asked
  (`SHORT_PAGE_RECHECKS`). Bitunix history starts 2022-04-17; full history gives 719.15 on every one of
  12 fetches (`research/bnb_fib_start_trace.py`, part `bnb-fib`). Charts also start on a fixed
  `HISTORY_START` (2017-01-01), not "2000 days ago", which would slide once history passes 2000 days.
  Entry confirm skips any alert sent with price already past its entry
  (`entry_confirm.past_entry_when_sent`) - the fib alert is that level's only message.
  **No fib alert once this candle reached the entry (2026-10-12, lakky).** A fib zone alerts only
  while the candle forming on its own timeframe has not yet traded to the entry and price is not past
  it (`fib_trendline_scanner.entry_already_touched`; the range comes from finer charts,
  `current_candle_range`, since Bitunix has no forming candle). Inside the zone no longer alerts at
  0.00%. The replay does the same (`fib_trendline_backtest.SKIP_TOUCHED_ENTRY`;
  `research/fib_entry_touched_backtest.py`, part `fib-entry`). Entry confirm: a record first seen at
  LATE sends nothing, and the "moved fast" GET READY backfill only goes out within
  `APPROACH_THRESHOLD_PCT` of entry (it printed "10.21% away" for BNB).
  **The forming 4H candle counts (2026-10-16, lakky, QNT 1D).** Bitunix serves closed candles only, so that
  range missed the 4H candle forming now - a 4H chart had no range at all, a 1D one up to 4 hours. `scan_crypto`
  now adds `bitunix_data.forming_candle(pair, "4h")` (`current_candle_range(..., live)`). The replay already used full candles.
  **A wick into the band alerts (2026-10-17, lakky, QNT 1D), fibs and trendlines, crypto and NSE.** The band is
  judged on the deepest price traded since the previous pass (`band_price`; Bitunix 1m / Yahoo 5m since
  `__last_scan__`, at most `SWEEP_MAX_SECONDS` back), not only the price at that moment; the message still shows
  the price now. QNT's 20:50 IST wick to 201.38 alerted only at 21:20. Sep 1 - Oct 16 (`research/band_wick_backtest.py`,
  part `band-wick`): ~8% more alerts, 1 in 3 earlier (median 15 min); crypto fib 4H -0.15 -> -0.08 R/trade, TL flat to slightly worse.
  **Same rule on trendlines (2026-10-12, lakky: "apply for both")**, crypto and NSE: a touch whose forming
  candle already reached the line does not alert and does not re-arm the band (`line_already_touched`,
  replay `TL_SKIP_TOUCHED_ENTRY`). Sep 1 - Oct 12 (`research/tl_entry_touched_backtest.py`, part `tl-entry`):
  crypto 4H -0.315 -> -0.335 R/trade, 1D+ -0.512 -> -0.541; NSE 4H -0.415 -> -0.406, 1D+ -0.348 -> -0.339; ~10% fewer alerts.
  Entry confirm lines (lakky, 2026-10-12): `` `BNB` BUY · **1M FIB L3** · 724.10 → 719.15 · ... ``,
  trendlines `**1D TL**`. Fib levels L1-L4 (lakky, BNB 1D chart): the four box edges in the order
  price reaches them - L1/L2 the weaker box, L3/L4 the stronger; L4 is the one he likes most. The bot's
  fib entry (strong box near edge) is L3. This replaces the Oct 8 L1/L2 names.
  Fib channel alerts (lakky, 2026-10-12) are three lines - `**BNB · FIB L3 · BUY** · **1M Crypto**`,
  `Price .. · x% away`, `Entry .. · SL .. (x%) · TP .. (1R)` (display only; fib trades still score 2R + BE); the zone edges are left off (he checks the chart)
  and kept in the record: `base`, `top`, `levels` {L1..L4} (`fib_trendline_scanner.fib_levels`).
  Trendline alerts (lakky, 2026-10-12): touch = `**RIVER · S TL · BUY** · **1D Crypto**`, `Price .. · x% away`,
  `Entry .. · SL .. (x%) · TP .. (1R)`; broken = `**TSLA · R TL BROKEN** · **4H Crypto**`, `Close .. above line ..`.
  The line's two points are off Discord and kept in the touch record (`from`, `to`).
- **Risk warning (lakky, 2026-10-17), crypto fib + trendline touch alerts only.** The title carries the coin's
  24h move (`**SOL -5.2% · FIB L3 · BUY**`, `name_with_move`; Bitunix 1h close 24h ago vs price now, `move_24h`),
  and a 4th line `⚠️ **Big 24h move · Market down: BTC ↓ ETH ↓ SOL ↑**` appears when the move is >=
  `RISK_WARN_MOVE_PCT` (2%, lakky's pick for testing; the backtest liked 4%) either way and/or `RISK_WARN_MARKET_MIN_AGAINST` (2) of `RISK_WARN_MARKET_SYMBOLS`
  (BTC, ETH, SOL) are against the trade on their daily EMA50 (`scanner.daily_trend`, once a pass). The alert still
  sends; the line is kept in the record as `warning`. Zones, TL BROKEN, xStocks/XAUT/SLVON and NSE get neither.
  Sep 1 - Oct 17 (`research/risk_warning_backtest.py`, part `risk-warn`), no warning vs warned per trade: fib 4H
  +0.05R / +0.38% vs -0.19R / -0.65%, fib 1D+ +1.21R vs -0.20R, TL 4H -0.33R vs -0.48R, TL 1D+ both ~-0.6R.
  2 of 3 split fib 4H far better than BTC alone (-0.69% vs -0.05% against/with; BTC -0.35% vs -0.26%).
  Zones went the other way (warned +0.56R on 12 trades), so they get none.
- NSE: the zone scanner's 200 stocks (`nse_scanner.load_watchlist`), scanned only in the session
  and at most every 8 minutes - that pass takes ~3 minutes (Yahoo, 5 intervals).
  **From the 09:15 open, not 09:00 (2026-10-27, Discord audit).** `nse_session_open` used the zone
  scanner's 09:00 start, so the first pass ran at 09:12-09:13 on Yahoo's pre-open bar (195 alerts
  21-27 Oct, 81 outside the band at any traded price). Candles Yahoo stamps after "now" are dropped too
  (a 13:15 bar at 13:14 hid the morning's touch). `research/discord_alert_audit.py`, part `discord-audit`.
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
- **A fib dies past its stop (lakky, 2026-10-13, DOGE 1D) - v12.7.10 / v12.7.11.** Besides price taking out its base/top,
  a fib is dead once price trades past its strong box's far edge (L4, 0.66 of the range from the extreme);
  the new fib starts at the old extreme itself (not the last higher low / lower high). DOGE 1D ran
  0.06762 -> 0.1059 through both sell boxes of the May fib (top 0.11857) and the bot kept that SELL fib;
  now it is the BUY fib 0.06762 -> 0.1059 lakky drew (`tests/fixtures/doge_usdt_1d_bitunix_300.csv`).
  **v12.7.11 (same day): the kill line is the strong box's stop** (`fib_engine.KILL`, L4 + 25% of the box =
  0.6875 of the range), not L4: the Oct 13 wick to 0.07994 went under L4 (0.08064), not the stop (0.07959),
  and the BUY fib must hold. Sep 1 - Oct 13 R / % per trade: crypto old +0.19R / +1.82%, L4 -0.00R / +0.10%,
  stop +0.07R / +0.25%; NSE -0.19R / -1.07%, -0.17R / -0.44%, -0.14R / -0.48%.
  **v12.7.12 (lakky, MAGIC 4H, same day): no flip back on a wick.** A fib born from a stop kill is not
  stop-killed itself until it makes a new low/high (`fresh` in `fib_engine.run`); only its origin kills it.
  MAGIC's SELL fib 0.16358 -> 0.09225 (Oct 11) flipped back on the Oct 12 wick to 0.14649, 6 candles later
  (`tests/fixtures/magic_usdt_4h_bitunix_400.csv`). Sep 1 - Oct 13 R / % per trade: crypto -0.04R / -0.04% ->
  -0.01R / +0.07%, NSE -0.15R / -0.49% -> -0.14R / -0.59%; a 20-candle no-flip-back gate was the other option.
  Backtest: `research/fib_kill_backtest.py`, part `fib-kill`. `SEED_VERSION` v10 re-seeds silently.
  `fib_engine.py` is changed here first: copy it back into `fib_reference.py`.
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
- **Trendline breaks, v12.7.9 (Lakky, 2026-10-10).** A line is drawn `tl_len` candles after its second
  swing; the closes in those candles are now checked when it is drawn (DABUR 1D: Oct 6 closed through a line
  drawn Oct 8). Such a line ends there and never alerts, BROKEN included. ~9-11% of lines; Sep 1 - Oct 10
  backtest ~3% fewer TL alerts, same R/trade (`research/out/trendline_confirm/`). Pine v12.7.9 does the same.
- **NSE 1D gap fill (2026-10-10, GLENMARK).** During a session Yahoo's batch 1d download can leave out the
  previous session's row, so the close that broke a line was never seen and the line alerted again the next
  day. `fib_trendline_data.fill_daily_gaps` adds missing days from the 1h candles (`research/tl_after_break_audit.py`).
- **One message per price (lakky, 2026-10-27).** Alerts one pass plans on the same channel, symbol and side with
  entries within `SAME_PRICE_PCT` (0.1%) go out as one message (`merge_same_price`): `**4H + 1D NSE**` in the
  title, one `4H · Entry .. · SL ..` line each (one line when the plans are identical; `FIB L1/L2` when levels
  differ). Keys and records stay one per timeframe. 92 of 1,017 alerts 21-27 Oct were such pairs.
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
- **Zone alert text (2026-10-12, lakky).** `**BTC | BUY | 4H**`, `Price .. · x% away`, `Entry .. · SL .. (x%)`
  (crypto and NSE, 30m and 4H; NSE may add its stop warning / sector lines). No rating and no zone edges on
  Discord - the record keeps both. Prices at most 3 decimals from 1 up, 2 from 1000 up (`scanner.price_text` /
  `short_places`, widened only if two levels would print the same; under 1 keeps `price_decimals`). The journal's
  pasted "Import Alert Signals" (`parseSignals`) still reads "SYMBOL | SIDE" and Price, but not the joint
  Entry/SL line (journal change, not done here); its record import is unaffected - `JournalImportCompat`.
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
- **30m zone alerts are off (2026-10-16, lakky: "remove 30m for now"), crypto and NSE; 4H stays on (2026-10-18,
  lakky: "keep 4h on for fib, trendline and support and resistance").** `ZONE_ALERT_TIMEFRAMES`
  (`VICTUS_ZONE_ALERT_TIMEFRAMES`, default `4h`): a zone scanner on an unlisted timeframe exits before loading
  state and ends the scan loop. An off timeframe's daily and weekly zone cards stay quiet once nothing is left to
  grade; the paper table stays quiet only when every zone timeframe is off. Keep `scan_30m.yml` dispatched - `fib_trendline_scan.yml` runs off its
  `workflow_run`. Live Sep 1 - Oct 16: crypto 30m -0.28R / -0.13% a trade (326), NSE 30m -0.50R / -0.21% (512).
- **S/R zones on 1D / 1W / 1M (2026-10-16, lakky), in the old 30m channels.** `fib_trendline_scanner.zone_candidates`
  runs the zone engine on the fib/TL charts (`ZONE_HTF_TIMEFRAMES`, Bitunix / Yahoo, `ZONE_BASE_EXTRA` 1): nearest
  zone per side, too young, over-touched, stop too wide, approach side, 0.20% band, re-arm past band x
  `REARM_FACTOR` and the 4h cooldown, crypto daily trend; a forming-candle wick through the far edge kills it.
  Posts to `DISCORD_30M_WEBHOOK_URL` / `DISCORD_NSE_30M_WEBHOOK_URL` as `**HYPE | BUY | 1D**`, recorded as
  kind `zone` and scored in the daily report like fibs (2R + BE, wait 5 / hold 20). Seeds silently on first pass.
  Backtest: `research/zone_htf_backtest.py`, part `zone-htf`. Entry confirm does not watch them.
- **Stored daily grades are kept (2026-10-18, lakky).** The morning run re-grades the latest reported
  day when no new one exists (with 30m off, that is the same day every morning). A grade already in
  `daily_backtest_finalized_records.jsonl` is no longer overwritten, and a failed fetch (`data_missing`,
  `alert_before_data`) never replaces a row: Delta stopped serving W and OGN, the re-fetch fell back to
  OKX's 300 candles and W's +2R of 16 Oct became `alert_before_data`. `--regrade` overwrites on purpose
  (after a scoring-rule change). Paper vs backtest: they can pick different deliveries of one zone
  (backtest keeps the first, drops repeats for 6h; paper fills a later re-alert) - see
  `research/daily_scores_audit.py`, part `scores-audit`.
- **Money line on the daily cards (2026-10-18, lakky: "a budget of 10000 ... 5x leverage").** Under TOTAL, zone
  cards and the fib/TL/1D+ zone cards print `10,000 at 5x: +1,234 (+12.3%)` (`ACCOUNT_BUDGET`, `ACCOUNT_LEVERAGE`
  in `config.py`; `daily_backtest_summary.money_line`). Every trade is sized at the full budget x leverage, so its
  money = 50,000 x net R x stop %. Display only. A stop over 20% at 5x would lose more than the budget.
- **Late results on the fib/TL/1D+ zone cards (2026-10-19, lakky: "no trade result of 1w and 1m").** A card shows
  only its own day's alerts, and a 1W/1M (often a 1D) trade closes days later, so its result never reached Discord.
  Now each card adds `CLOSED SINCE LAST CARD (earlier alerts)`: earlier filled alerts closed since the last card,
  by timeframe, each shown once (`reported` in the results file; `fib_trendline_daily_report.CLOSED_SINCE`, nothing
  that closed before 19 Oct 09:00 IST is dumped). The history replay already scored 1W/1M; tables fold them into 1D+.
- **Every fib level alerts (2026-10-20, lakky, BTW 4H, "for testing").** `FIB_ALERT_LEVELS`: 4H L2-L4, 1D/1W/1M L1-L4,
  crypto and NSE; each level once, on its own entry, with the fib's one stop (`fib_trendline_scanner.fib_legs`). L3 keeps
  its old key; others end `|L1` / `|L2` / `|L4`. Title and entry confirm name the level; L1/L2/L4 alerts get no what-ifs.
  No repeats - the "again after 4h if touched" rule was backtested and made it worse (`research/fib_l3_l4_backtest.py`,
  `fib_levels_all_backtest.py`, parts `fib-l3l4`, `fib-levels-all`). Sep 1 - Oct 20, per trade: crypto 4H -0.03R -> -0.14R,
  1D +0.42R -> +0.07R, NSE worse at every level. BTW's 20 Oct drop to L4 had no alert because L3 had alerted on 16 Oct (one per zone).
- **1W / 1M alert from 3% away (2026-10-21, lakky: "help me to get ready for big timeframe trades"), crypto and NSE.**
  Fibs, trendlines and 1W/1M S/R zones use `config.alert_band_pct(tf, ...)`: `EARLY_ALERT_BAND_PCT` (3%) on
  `EARLY_ALERT_TIMEFRAMES` (1w, 1M), else 0.75% (fib/TL) / `MAX_DISTANCE_PCT` (zones; re-arm at 3% x `REARM_FACTOR`).
  Entry, stop and target unchanged. The history replay does the same (`fib_trendline_backtest.band_for`,
  `EARLY_BAND`). `SEED_VERSION` not bumped on purpose: the first pass sends the 1W/1M levels already within 3% once.
  The L1/L2/L4 what-ifs keep 0.75%. Backtest: `research/early_band_backtest.py`, part `early-band`.
- **Fib what-ifs at L1 / L2 / L4 (2026-10-19, lakky).** The bot enters fibs at L3 only; once a day the fib report
  also scores each fib alert as if it had been sent at L1, L2 and L4 (`fib_level_whatif.py`): same stop as the
  alert, the level's own 0.75% band moment after the fib's top, then `trades.simulate`. Results go to
  `fib_level_results.json` (runtime-state branch) for the journal's Fib levels tab only - no Discord, no alert changes.
  **Backfill (2026-10-19, lakky: "make previous alerts correct, start from Oct").** Fib records saved before
  Oct 12 had only the plan; `research/fib_level_backfill.py` (part `fib-levels` dry run / `fib-levels-apply` of
  `bitunix_research.yml`, in the fib scan's concurrency group) adds `base`, `top`, `levels` and `level` to every
  fib alert since Oct 1 and scores the what-ifs at once; backup `fib_trendline_alert_records.pre_levels_2026-10-19.jsonl`.
  New fib records carry `level` too (L3; L1 for an old zone-1 alert).
- **Range filter alerts are off (2026-10-10, lakky).** Alerts are S/R zones, fibs and trendlines
  (incl. TL BROKEN) only. `ALERT_RANGE_FILTER_SIGNALS` is False in `config.py` and `nse_config.py`; the
  range filter is still computed but never posts. Pine v12.7.8 drops its RF marker too.
- There is an astrology component (`astrology_engine.js`, `ASTROLOGY_SETUP.md`) with its
  own agent branches.
