# Victus Astrology Reports

This isolated workflow posts Victus's personalized Vedic astrology briefing to a
private Discord channel.

Reports:

- Daily astrology: every day at 07:00 IST
- Weekly astrology: every Sunday at 19:00 IST for the next week

The daily post is an AstroSage-style prediction: one flowing Hinglish paragraph of
short sentences that mixes good and bad across health and food, money, work and
study, family, people and trust, plus lines that appear only when a transit
triggers them (travel and driving, tips and schemes, Mercury retrograde or
phone trouble, speech, friends). It is followed by:

- Today's Lucky Number (number of the Moon's nakshatra lord at 07:00 IST)
- Accha Time and Savdhaan Time
- Aaj Karo / Aaj Na Karo
- Astrological Focus

Wording is chosen from the same transits, dasha, Tara Bala and Chandra Bala the
scores already used, and rotates by date so consecutive days do not repeat.

The weekly post uses the same style: one Hinglish paragraph for the whole week
that names the best and weakest day for each area (health, money, work, family,
people), plus travel, scheme, Mercury and speech lines when triggered. It is
followed by day-wise Lucky Numbers, stronger days, caution days, best period of
week, main focus, avoid, and sector themes.

The system intentionally excludes romance content and does not produce trade
entries, exits, stop-losses, take-profits, leverage, position sizing, or
buy/sell signals.

## One-time Discord setup

1. Create a private Discord channel such as `#victus-daily-astrology`.
2. Open Edit Channel -> Integrations -> Webhooks -> New Webhook.
3. Copy the webhook URL.
4. In GitHub, open Settings -> Secrets and variables -> Actions.
5. Create a repository secret named `DISCORD_ASTROLOGY_WEBHOOK_URL` and paste
   the webhook URL as its value.
6. Open Actions -> Victus Daily Astrology -> Run workflow to send a test post.

The same webhook secret is used by both daily and weekly astrology workflows.

## Schedule and testing

GitHub Actions schedules in UTC:

- Daily: `30 1 * * *` = 07:00 IST
- Weekly: `30 13 * * 0` = 19:00 IST every Sunday

GitHub may start scheduled jobs a few minutes late during busy periods.

Run the regression tests:

```bash
npm run test:astrology
```

Preview daily without posting to Discord:

```bash
ASTROLOGY_DRY_RUN=true npm run astrology
```

Preview a particular daily date:

```bash
ASTROLOGY_DRY_RUN=true ASTROLOGY_DATE=2026-08-08 npm run astrology
```

Preview weekly without posting to Discord:

```bash
ASTROLOGY_DRY_RUN=true ASTROLOGY_WEEK_START=2026-08-10 npm run astrology:weekly
```
