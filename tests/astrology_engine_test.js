"use strict";

const assert = require("assert");
const {
  NATAL,
  NATAL_DISPLAY_REFERENCE,
  SECTOR_THEME_DEFINITIONS,
  SECTOR_THEME_THRESHOLD,
  activeDasha,
  addDays,
  buildDailyPayload,
  buildWeeklyPayload,
  evaluateDay,
  generateForecast,
  generateWeeklyForecast,
  houseFromSign,
  luckyNumber,
  nakshatraDetails,
  planetaryHoras,
  rahuKalam,
  scoreSectorTheme,
  signName,
  sunTimes,
} = require("../astrology_engine");

function assertRange(value, min, max, label) {
  assert(
    value >= min && value <= max,
    `${label} expected ${min}-${max}, got ${value}`,
  );
}

const natalMoon = nakshatraDetails(NATAL.moon);
assert.strictEqual(signName(NATAL.ascendant), "Scorpio");
assert.strictEqual(signName(NATAL.moon), "Capricorn");
assert.strictEqual(natalMoon.name, "Uttarashadha");
assert.strictEqual(natalMoon.pada, 2);
assert(Math.abs(NATAL.moon - NATAL_DISPLAY_REFERENCE.moon) > 0.000001);
assert(Math.abs(NATAL.ascendant - NATAL_DISPLAY_REFERENCE.ascendant) > 0.000001);

for (const [sector, factors] of Object.entries(SECTOR_THEME_DEFINITIONS)) {
  const emptyTransit = {};
  for (const factor of factors) {
    if (factor.type === "house") {
      emptyTransit[factor.planet] = emptyTransit[factor.planet] || {};
      emptyTransit[factor.planet][factor.relation] = -1;
    }
  }
  const diagnostics = scoreSectorTheme(
    factors,
    emptyTransit,
    { mahadasha: "None", antardasha: { lord: "None" } },
  );
  if (diagnostics.supportReachable) {
    assert(
      diagnostics.theoreticalMax >= diagnostics.supportThreshold,
      `${sector} support threshold is unreachable`,
    );
  }
  if (diagnostics.cautionReachable) {
    assert(
      diagnostics.theoreticalMin <= diagnostics.cautionThreshold,
      `${sector} caution threshold is unreachable`,
    );
  }
  // Every sector must be reachable in at least one direction - a theme
  // that can never fire either way (support or caution) regardless of
  // real transits would be silently dead weight in the report.
  assert(
    diagnostics.supportReachable || diagnostics.cautionReachable,
    `${sector} is unreachable in both directions`,
  );
}

const regressionDate = { year: 2026, month: 8, day: 8 };
const dasha = activeDasha(regressionDate);
assert.strictEqual(dasha.mahadasha, "Rahu");
assert.strictEqual(dasha.antardasha.lord, "Rahu");

const evaluation = evaluateDay(regressionDate);
assert.strictEqual(evaluation.transit.sun.sign, "Cancer");
assert.strictEqual(evaluation.transit.moon.sign, "Taurus");
assert.strictEqual(evaluation.transit.mars.sign, "Gemini");
assert.strictEqual(evaluation.transit.mercury.sign, "Cancer");
assert.strictEqual(evaluation.transit.jupiter.sign, "Cancer");
assert.strictEqual(evaluation.transit.venus.sign, "Virgo");
assert.strictEqual(evaluation.transit.saturn.sign, "Pisces");
assert.strictEqual(evaluation.transit.rahu.sign, "Aquarius");
assert.strictEqual(evaluation.transit.ketu.sign, "Leo");

assert.strictEqual(houseFromSign(NATAL.ascendant, evaluation.transits.sun.longitude), 9);
assert.strictEqual(houseFromSign(NATAL.ascendant, evaluation.transits.moon.longitude), 7);
assert.strictEqual(houseFromSign(NATAL.ascendant, evaluation.transits.mars.longitude), 8);
assert.strictEqual(houseFromSign(NATAL.ascendant, evaluation.transits.mercury.longitude), 9);
assert.strictEqual(houseFromSign(NATAL.ascendant, evaluation.transits.jupiter.longitude), 9);
assert.strictEqual(houseFromSign(NATAL.ascendant, evaluation.transits.venus.longitude), 11);
assert.strictEqual(houseFromSign(NATAL.ascendant, evaluation.transits.saturn.longitude), 5);
assert.strictEqual(houseFromSign(NATAL.ascendant, evaluation.transits.rahu.longitude), 4);
assert.strictEqual(houseFromSign(NATAL.ascendant, evaluation.transits.ketu.longitude), 10);

const augustSun = sunTimes(regressionDate);
const decemberSun = sunTimes({ year: 2026, month: 12, day: 8 });
assert.notStrictEqual(augustSun.sunrise.toFixed(2), decemberSun.sunrise.toFixed(2));
assertRange(augustSun.sunrise, 5, 7, "Jabalpur sunrise");
assertRange(augustSun.sunset, 17, 19.5, "Jabalpur sunset");

const rahu = rahuKalam(regressionDate);
assert(rahu.start > augustSun.sunrise && rahu.end < augustSun.sunset);
assert.notStrictEqual(rahu.start.toFixed(2), "6.00");

const horas = planetaryHoras(regressionDate);
assert.strictEqual(horas.length, 24);
assert.notStrictEqual((horas[0].end - horas[0].start).toFixed(3), "1.000");

const dailyPayload = buildDailyPayload(regressionDate);
const daily = dailyPayload.text;
const dailyEmbedText = JSON.stringify(dailyPayload.payload.embeds);
assert(daily.includes("Today's Lucky Number:"));
assert(dailyEmbedText.includes("Today's Lucky Number"));
assert(dailyPayload.payload.embeds[0].description.length > 300);
assert.strictEqual(dailyPayload.payload.content, "");
assert.strictEqual(dailyPayload.payload.embeds.length, 1);
assert(!/romance|dating|marriage|love-life/i.test(daily));
assert(!/stop-loss|take-profit|leverage|position size|buy\/sell signal/i.test(daily));
assert(!/disclaimer|not a trade signal/i.test(daily));

// Forecast style: one flowing paragraph, a lucky number, wording that is
// stable for a date, varies across dates, and never touches excluded topics.
assert.strictEqual(generateForecast(evaluation), generateForecast(evaluation));
assert.strictEqual(luckyNumber(evaluation), 2); // Moon in Rohini, ruled by the Moon (2)
const forecasts = new Set();
for (let offset = 0; offset < 60; offset += 1) {
  const day = addDays(regressionDate, offset);
  const dayEval = evaluateDay(day);
  const forecast = generateForecast(dayEval);
  forecasts.add(forecast);
  assert(!forecast.includes("\n"), "forecast must be a single paragraph");
  assertRange(forecast.split(". ").length, 6, 11, "forecast sentence count");
  assertRange(luckyNumber(dayEval), 1, 9, "lucky number");
  assert(!/romance|dating|marriage|love|spouse|pati|patni/i.test(forecast));
  assert(!/stop-loss|take-profit|leverage|position size|buy\/sell/i.test(forecast));
}
assert(forecasts.size >= 55, `forecasts repeat too much: ${forecasts.size}/60 distinct`);

const weeklyPayload = buildWeeklyPayload({ year: 2026, month: 8, day: 10 });
const weekly = weeklyPayload.text;
const weeklyEmbedText = JSON.stringify(weeklyPayload.payload.embeds);
assert(weekly.includes("NEXT WEEK ASTROLOGY"));
assert(weekly.includes("Lucky Numbers:"));
assert(weeklyEmbedText.includes("Lucky Numbers"));
assert(weeklyPayload.payload.embeds[0].description.length > 300);
assert.strictEqual(weeklyPayload.payload.content, "");
assert.strictEqual(weeklyPayload.payload.embeds.length, 1);
assert(!/romance|dating|marriage|love-life/i.test(weekly));
assert(!/disclaimer|not a trade signal/i.test(weekly));

const weeklyForecasts = new Set();
for (let week = 0; week < 12; week += 1) {
  const startDay = addDays({ year: 2026, month: 8, day: 10 }, week * 7);
  const evals = Array.from({ length: 7 }, (_, i) => evaluateDay(addDays(startDay, i)));
  const forecast = generateWeeklyForecast(evals);
  weeklyForecasts.add(forecast);
  assert(!forecast.includes("\n"), "weekly forecast must be a single paragraph");
  assertRange(forecast.split(". ").length, 7, 11, "weekly sentence count");
  assert(!/romance|dating|marriage|love|spouse|\bpati\b|patni/i.test(forecast));
  assert(!/stop-loss|take-profit|leverage|position size|buy\/sell/i.test(forecast));
}
assert(weeklyForecasts.size >= 10, `weekly forecasts repeat: ${weeklyForecasts.size}/12`);

console.log("Astrology engine regression tests passed.");
