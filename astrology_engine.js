"use strict";

const https = require("https");
const swe = require("sweph");

const IST_OFFSET_HOURS = 5.5;
const IST_LABEL = "IST";
const MS_PER_DAY = 24 * 60 * 60 * 1000;
const YEAR_DAYS = 365.2425;
const JABALPUR = Object.freeze({ latitude: 23.1815, longitude: 79.9864 });

const SIGNS = Object.freeze([
  "Aries",
  "Taurus",
  "Gemini",
  "Cancer",
  "Leo",
  "Virgo",
  "Libra",
  "Scorpio",
  "Sagittarius",
  "Capricorn",
  "Aquarius",
  "Pisces",
]);

const NAKSHATRAS = Object.freeze([
  "Ashwini",
  "Bharani",
  "Krittika",
  "Rohini",
  "Mrigashira",
  "Ardra",
  "Punarvasu",
  "Pushya",
  "Ashlesha",
  "Magha",
  "Purva Phalguni",
  "Uttara Phalguni",
  "Hasta",
  "Chitra",
  "Swati",
  "Vishakha",
  "Anuradha",
  "Jyeshtha",
  "Mula",
  "Purva Ashadha",
  "Uttarashadha",
  "Shravana",
  "Dhanishta",
  "Shatabhisha",
  "Purva Bhadrapada",
  "Uttara Bhadrapada",
  "Revati",
]);

const NAKSHATRA_LORDS = Object.freeze([
  "Ketu",
  "Venus",
  "Sun",
  "Moon",
  "Mars",
  "Rahu",
  "Jupiter",
  "Saturn",
  "Mercury",
]);

const DASHA_YEARS = Object.freeze({
  Ketu: 7,
  Venus: 20,
  Sun: 6,
  Moon: 10,
  Mars: 7,
  Rahu: 18,
  Jupiter: 16,
  Saturn: 19,
  Mercury: 17,
});

const DASHA_ORDER = Object.freeze([
  "Ketu",
  "Venus",
  "Sun",
  "Moon",
  "Mars",
  "Rahu",
  "Jupiter",
  "Saturn",
  "Mercury",
]);

const WEEKDAY_RULERS = Object.freeze([
  "Sun",
  "Moon",
  "Mars",
  "Mercury",
  "Jupiter",
  "Venus",
  "Saturn",
]);
const HORA_SEQUENCE = Object.freeze([
  "Saturn",
  "Jupiter",
  "Mars",
  "Sun",
  "Venus",
  "Mercury",
  "Moon",
]);

// Sunday..Saturday. Traditional Rahu Kalam daylight section numbers.
const RAHU_KALAM_SECTION = Object.freeze([8, 2, 7, 5, 6, 4, 3]);

const NATAL_DISPLAY_REFERENCE = Object.freeze({
  birthUtc: Date.UTC(2004, 6, 3, 10, 50), // 03 Jul 2004 16:20 IST.
  ascendant: 222 + 32 / 60,
  moon: 270 + 1 + 58 / 60,
  sun: 60 + 17 + 56 / 60,
  mars: 90 + 12 + 7 / 60,
  mercury: 90 + 3 + 58 / 60,
  jupiter: 120 + 19 + 48 / 60,
  venus: 30 + 15 + 57 / 60,
  saturn: 60 + 22 + 14 / 60,
  rahu: 14 + 1 / 60,
  ketu: 180 + 14 + 1 / 60,
});

const NATAL = Object.freeze(buildNatalLongitudes());

const PLANETS = Object.freeze({
  sun: swe.constants.SE_SUN,
  moon: swe.constants.SE_MOON,
  mars: swe.constants.SE_MARS,
  mercury: swe.constants.SE_MERCURY,
  jupiter: swe.constants.SE_JUPITER,
  venus: swe.constants.SE_VENUS,
  saturn: swe.constants.SE_SATURN,
  rahu: swe.constants.SE_MEAN_NODE,
});

const SECTOR_THEME_THRESHOLD = 3;

const SECTOR_THEME_DEFINITIONS = Object.freeze({
  "Technology / Communication": Object.freeze([
    houseFactor("mercury", "houseFromLagna", [3, 10, 11], 2),
    houseFactor("mercury", "houseFromLagna", [8, 12], -2),
    dashaFactor("Rahu", 1),
  ]),
  "Banking / Financials": Object.freeze([
    houseFactor("jupiter", "houseFromMoon", [2, 9, 11], 2),
    houseFactor("jupiter", "houseFromMoon", [6, 8, 12], -1),
    dashaFactor("Jupiter", 1),
  ]),
  Energy: Object.freeze([
    houseFactor("sun", "houseFromLagna", [3, 6, 10, 11], 1),
    houseFactor("mars", "houseFromLagna", [3, 6, 10, 11], 2),
    houseFactor("mars", "houseFromLagna", [8, 12], -2),
  ]),
  "Consumer / Luxury": Object.freeze([
    houseFactor("venus", "houseFromMoon", [2, 5, 9, 11], 2),
    houseFactor("venus", "houseFromMoon", [6, 8, 12], -1),
    houseFactor("moon", "houseFromLagna", [1, 5, 9, 11], 1),
  ]),
  "Metals / Gold": Object.freeze([
    houseFactor("saturn", "houseFromMoon", [3, 6, 11], 1),
    houseFactor("saturn", "houseFromMoon", [4, 8, 12], -1),
    dashaFactor("Saturn", 1),
  ]),
  "Pharma / Healthcare": Object.freeze([
    houseFactor("sun", "houseFromLagna", [1, 6, 10, 11], 1),
    houseFactor("jupiter", "houseFromLagna", [6, 10, 11], 1),
    houseFactor("moon", "houseFromMoon", [1, 5, 9, 11], 1),
  ]),
  "Real Estate": Object.freeze([
    houseFactor("venus", "houseFromLagna", [4, 11], 1),
    houseFactor("rahu", "houseFromLagna", [4, 10], -1),
  ]),
  Automobiles: Object.freeze([
    houseFactor("mars", "houseFromLagna", [3, 6, 11], 1),
    houseFactor("venus", "houseFromMoon", [2, 5, 9, 11], 1),
    houseFactor("sun", "houseFromLagna", [3, 10, 11], 1),
  ]),
});

function houseFactor(planet, relation, houses, score) {
  return Object.freeze({ type: "house", planet, relation, houses, score });
}

function dashaFactor(lord, score) {
  return Object.freeze({ type: "dasha", lord, score });
}

function normalizeDegrees(value) {
  return ((value % 360) + 360) % 360;
}

function buildNatalLongitudes() {
  swe.set_sid_mode(swe.constants.SE_SIDM_LAHIRI, 0, 0);
  const jd = julianDayForIst({ year: 2004, month: 7, day: 3 }, 16 + 20 / 60);
  const flags =
    swe.constants.SEFLG_MOSEPH |
    swe.constants.SEFLG_SPEED |
    swe.constants.SEFLG_SIDEREAL;
  const natalPlanets = {
    sun: swe.constants.SE_SUN,
    moon: swe.constants.SE_MOON,
    mars: swe.constants.SE_MARS,
    mercury: swe.constants.SE_MERCURY,
    jupiter: swe.constants.SE_JUPITER,
    venus: swe.constants.SE_VENUS,
    saturn: swe.constants.SE_SATURN,
    rahu: swe.constants.SE_MEAN_NODE,
  };
  const values = { birthUtc: NATAL_DISPLAY_REFERENCE.birthUtc };
  for (const [name, id] of Object.entries(natalPlanets)) {
    const result = swe.calc_ut(jd, id, flags);
    if (!result?.data || result.error) {
      throw new Error(`Swiss Ephemeris failed for natal ${name}: ${result?.error}`);
    }
    values[name] = normalizeDegrees(result.data[0]);
  }
  const houses = swe.houses_ex(
    jd,
    flags,
    JABALPUR.latitude,
    JABALPUR.longitude,
    "W",
  );
  if (!houses?.data?.points || houses.error) {
    throw new Error(`Swiss Ephemeris failed for natal ascendant: ${houses?.error}`);
  }
  values.ascendant = normalizeDegrees(houses.data.points[0]);
  values.ketu = normalizeDegrees(values.rahu + 180);
  return values;
}

function signIndex(longitude) {
  return Math.floor(normalizeDegrees(longitude) / 30);
}

function signName(longitude) {
  return SIGNS[signIndex(longitude)];
}

function houseFromSign(referenceLongitude, transitLongitude) {
  return ((signIndex(transitLongitude) - signIndex(referenceLongitude) + 12) % 12) + 1;
}

function nakshatraDetails(longitude) {
  const nakLength = 360 / 27;
  const padaLength = nakLength / 4;
  const normalized = normalizeDegrees(longitude);
  const index = Math.floor(normalized / nakLength);
  const offset = normalized - index * nakLength;
  return {
    index,
    name: NAKSHATRAS[index],
    pada: Math.floor(offset / padaLength) + 1,
    lord: NAKSHATRA_LORDS[index % 9],
    offset,
    remainingFraction: 1 - offset / nakLength,
  };
}

function parseYmd(value, envName) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    throw new Error(`${envName} must use YYYY-MM-DD.`);
  }
  return {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
  };
}

function parseForecastDate() {
  const override = process.env.ASTROLOGY_DATE?.trim();
  if (override) {
    return parseYmd(override, "ASTROLOGY_DATE");
  }

  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return {
    year: Number(values.year),
    month: Number(values.month),
    day: Number(values.day),
  };
}

function dateFromUtcMs(ms) {
  const date = new Date(ms);
  return {
    year: date.getUTCFullYear(),
    month: date.getUTCMonth() + 1,
    day: date.getUTCDate(),
  };
}

function dateToUtcMs(date) {
  return Date.UTC(date.year, date.month - 1, date.day);
}

function addDays(date, days) {
  return dateFromUtcMs(dateToUtcMs(date) + days * MS_PER_DAY);
}

function weekdayIndex(date) {
  return new Date(dateToUtcMs(date)).getUTCDay();
}

function utcDateForIstHour(date, istHour) {
  const utcHour = istHour - IST_OFFSET_HOURS;
  const wholeHours = Math.floor(utcHour);
  const minutes = Math.round((utcHour - wholeHours) * 60);
  return new Date(Date.UTC(date.year, date.month - 1, date.day, wholeHours, minutes));
}

function julianDayForIst(date, istHour = 7) {
  const utc = utcDateForIstHour(date, istHour);
  const hour =
    utc.getUTCHours() + utc.getUTCMinutes() / 60 + utc.getUTCSeconds() / 3600;
  return swe.julday(
    utc.getUTCFullYear(),
    utc.getUTCMonth() + 1,
    utc.getUTCDate(),
    hour,
    swe.constants.SE_GREG_CAL,
  );
}

function getTransits(date, istHour = 7) {
  swe.set_sid_mode(swe.constants.SE_SIDM_LAHIRI, 0, 0);
  const jd = julianDayForIst(date, istHour);
  const flags =
    swe.constants.SEFLG_MOSEPH |
    swe.constants.SEFLG_SPEED |
    swe.constants.SEFLG_SIDEREAL;

  const transits = Object.fromEntries(
    Object.entries(PLANETS).map(([name, id]) => {
      const result = swe.calc_ut(jd, id, flags);
      if (!result?.data || result.error) {
        throw new Error(`Swiss Ephemeris failed for ${name}: ${result?.error}`);
      }
      return [
        name,
        {
          longitude: normalizeDegrees(result.data[0]),
          speed: result.data[3],
        },
      ];
    }),
  );
  transits.ketu = {
    longitude: normalizeDegrees(transits.rahu.longitude + 180),
    speed: transits.rahu.speed,
  };
  return transits;
}

function activeDasha(date, istHour = 7) {
  const targetMs = utcDateForIstHour(date, istHour).getTime();
  const natalMoon = nakshatraDetails(NATAL.moon);
  const birthLord = natalMoon.lord;
  const birthLordIndex = DASHA_ORDER.indexOf(birthLord);
  const firstPeriodDays = DASHA_YEARS[birthLord] * natalMoon.remainingFraction * YEAR_DAYS;
  let periodStart = NATAL.birthUtc;
  let periodEnd = periodStart + firstPeriodDays * MS_PER_DAY;
  let orderIndex = birthLordIndex;

  for (let guard = 0; guard < 30; guard += 1) {
    const lord = DASHA_ORDER[orderIndex % DASHA_ORDER.length];
    if (targetMs < periodEnd) {
      return {
        mahadasha: lord,
        antardasha: activeAntardasha(targetMs, lord, periodStart, periodEnd),
        mahadashaStart: new Date(periodStart),
        mahadashaEnd: new Date(periodEnd),
      };
    }

    periodStart = periodEnd;
    orderIndex += 1;
    const nextLord = DASHA_ORDER[orderIndex % DASHA_ORDER.length];
    periodEnd = periodStart + DASHA_YEARS[nextLord] * YEAR_DAYS * MS_PER_DAY;
  }

  throw new Error("Unable to resolve Vimshottari dasha period.");
}

function activeAntardasha(targetMs, mahaLord, mahaStartMs, mahaEndMs) {
  const mahaDuration = mahaEndMs - mahaStartMs;
  let subStart = mahaStartMs;
  let startIndex = DASHA_ORDER.indexOf(mahaLord);
  for (let i = 0; i < DASHA_ORDER.length; i += 1) {
    const lord = DASHA_ORDER[(startIndex + i) % DASHA_ORDER.length];
    const subEnd = subStart + mahaDuration * (DASHA_YEARS[lord] / 120);
    if (targetMs < subEnd) {
      return {
        lord,
        start: new Date(subStart),
        end: new Date(subEnd),
      };
    }
    subStart = subEnd;
  }
  return {
    lord: DASHA_ORDER[(startIndex + DASHA_ORDER.length - 1) % DASHA_ORDER.length],
    start: new Date(subStart),
    end: new Date(mahaEndMs),
  };
}

function dayOfYear(date) {
  const start = Date.UTC(date.year, 0, 0);
  return Math.floor((dateToUtcMs(date) - start) / MS_PER_DAY);
}

function degToRad(value) {
  return (value * Math.PI) / 180;
}

function radToDeg(value) {
  return (value * 180) / Math.PI;
}

function normalizeHours(value) {
  return ((value % 24) + 24) % 24;
}

function solarEventLocalHour(date, isSunrise) {
  const zenith = 90.833;
  const lngHour = JABALPUR.longitude / 15;
  const n = dayOfYear(date);
  const t = n + ((isSunrise ? 6 : 18) - lngHour) / 24;
  const meanAnomaly = 0.9856 * t - 3.289;
  let trueLong =
    meanAnomaly +
    1.916 * Math.sin(degToRad(meanAnomaly)) +
    0.02 * Math.sin(degToRad(2 * meanAnomaly)) +
    282.634;
  trueLong = normalizeDegrees(trueLong);

  let rightAscension = radToDeg(Math.atan(0.91764 * Math.tan(degToRad(trueLong))));
  rightAscension = normalizeDegrees(rightAscension);
  rightAscension +=
    Math.floor(trueLong / 90) * 90 - Math.floor(rightAscension / 90) * 90;
  rightAscension /= 15;

  const sinDeclination = 0.39782 * Math.sin(degToRad(trueLong));
  const cosDeclination = Math.cos(Math.asin(sinDeclination));
  const cosHour =
    (Math.cos(degToRad(zenith)) -
      sinDeclination * Math.sin(degToRad(JABALPUR.latitude))) /
    (cosDeclination * Math.cos(degToRad(JABALPUR.latitude)));

  if (cosHour < -1 || cosHour > 1) {
    throw new Error("Unable to calculate sunrise/sunset for Jabalpur.");
  }

  const localHourAngle = isSunrise
    ? 360 - radToDeg(Math.acos(cosHour))
    : radToDeg(Math.acos(cosHour));
  const localMeanTime =
    localHourAngle / 15 + rightAscension - 0.06571 * t - 6.622;
  const utcHour = normalizeHours(localMeanTime - lngHour);
  return normalizeHours(utcHour + IST_OFFSET_HOURS);
}

function sunTimes(date) {
  return {
    sunrise: solarEventLocalHour(date, true),
    sunset: solarEventLocalHour(date, false),
  };
}

function rahuKalam(date) {
  const { sunrise, sunset } = sunTimes(date);
  const sectionLength = (sunset - sunrise) / 8;
  const section = RAHU_KALAM_SECTION[weekdayIndex(date)];
  const start = sunrise + (section - 1) * sectionLength;
  return {
    start,
    end: start + sectionLength,
    source: "Rahu Kalam",
  };
}

function overlaps(left, right) {
  return left.start < right.end && right.start < left.end;
}

function planetaryHoras(date) {
  const today = sunTimes(date);
  const tomorrow = sunTimes(addDays(date, 1));
  const dayLength = today.sunset - today.sunrise;
  const nightLength = 24 - today.sunset + tomorrow.sunrise;
  const dayRuler = WEEKDAY_RULERS[weekdayIndex(date)];
  const startIndex = HORA_SEQUENCE.indexOf(dayRuler);
  const horas = [];

  for (let i = 0; i < 12; i += 1) {
    const start = today.sunrise + (i * dayLength) / 12;
    horas.push({
      start,
      end: today.sunrise + ((i + 1) * dayLength) / 12,
      ruler: HORA_SEQUENCE[(startIndex + i) % HORA_SEQUENCE.length],
      period: "day",
    });
  }

  for (let i = 0; i < 12; i += 1) {
    const start = today.sunset + (i * nightLength) / 12;
    horas.push({
      start,
      end: today.sunset + ((i + 1) * nightLength) / 12,
      ruler: HORA_SEQUENCE[(startIndex + 12 + i) % HORA_SEQUENCE.length],
      period: "night",
    });
  }

  return horas;
}

function formatHour(decimalHour) {
  const totalMinutes = Math.round(normalizeHours(decimalHour) * 60);
  const hours = Math.floor(totalMinutes / 60) % 24;
  const minutes = totalMinutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function formatWindow(window) {
  return `${formatHour(window.start)}-${formatHour(window.end)} ${IST_LABEL}`;
}

function transitDiagnostics(transits) {
  return Object.fromEntries(
    Object.entries(transits).map(([name, planet]) => [
      name,
      {
        longitude: Number(planet.longitude.toFixed(6)),
        sign: signName(planet.longitude),
        houseFromLagna: houseFromSign(NATAL.ascendant, planet.longitude),
        houseFromMoon: houseFromSign(NATAL.moon, planet.longitude),
      },
    ]),
  );
}

function taraBala(moonNakIndex) {
  const natalNak = nakshatraDetails(NATAL.moon).index;
  const count = ((moonNakIndex - natalNak + 27) % 27) + 1;
  const tara = ((count - 1) % 9) + 1;
  return {
    count,
    tara,
    favourable: new Set([2, 4, 6, 8, 9]).has(tara),
  };
}

function chandraBala(moonFromMoon) {
  return new Set([1, 3, 6, 7, 10, 11]).has(moonFromMoon);
}

function addScore(score, amount, reason) {
  score.value += amount;
  score.reasons.push(reason);
}

function evaluateDay(date) {
  const transits = getTransits(date);
  const transit = transitDiagnostics(transits);
  const moonNak = nakshatraDetails(transits.moon.longitude);
  const dasha = activeDasha(date);
  const tara = taraBala(moonNak.index);
  const moonFromMoon = transit.moon.houseFromMoon;
  const moonFromLagna = transit.moon.houseFromLagna;
  const chandra = chandraBala(moonFromMoon);

  const scores = {
    overall: { value: 0, reasons: [] },
    study: { value: 0, reasons: [] },
    money: { value: 0, reasons: [] },
    health: { value: 0, reasons: [] },
    communication: { value: 0, reasons: [] },
  };

  if (chandra) addScore(scores.overall, 2, "Moon support");
  else addScore(scores.overall, -1, "Moon caution");
  if (tara.favourable) addScore(scores.overall, 1, "Tara Bala support");
  else addScore(scores.overall, -1, "Tara Bala caution");
  if ([1, 5, 7, 9, 10, 11].includes(moonFromLagna)) addScore(scores.overall, 1, "Moon from Lagna support");
  if ([6, 8, 12].includes(moonFromLagna)) addScore(scores.overall, -1, "Moon from Lagna caution");
  if (dasha.mahadasha === "Rahu") addScore(scores.overall, -1, "Rahu Mahadasha requires discipline");

  if ([1, 2, 5, 9, 10, 11].includes(transit.mercury.houseFromLagna)) addScore(scores.study, 2, "Mercury supports learning");
  else addScore(scores.study, -1, "Mercury needs review");
  if ([2, 5, 7, 9, 11].includes(transit.jupiter.houseFromMoon)) addScore(scores.study, 2, "Jupiter supports guidance");
  if ([5, 9, 10, 11].includes(moonFromLagna)) addScore(scores.study, 1, "Moon supports focus");
  if (!tara.favourable) addScore(scores.study, -1, "Tara Bala asks repetition");

  if (chandra) addScore(scores.money, 1, "Moon is workable");
  else addScore(scores.money, -1, "Moon is reactive");
  if ([8, 12].includes(transit.mars.houseFromLagna)) addScore(scores.money, -1, "Mars increases impulse");
  if ([4, 8, 12].includes(transit.rahu.houseFromMoon)) addScore(scores.money, -1, "Rahu increases noise");
  if ([3, 6, 10, 11].includes(transit.saturn.houseFromMoon)) addScore(scores.money, 1, "Saturn supports rules");
  if (dasha.mahadasha === "Rahu" && dasha.antardasha.lord === "Rahu") addScore(scores.money, -1, "Rahu/Rahu punishes shortcuts");

  if ([1, 3, 6, 7, 10, 11].includes(moonFromMoon)) addScore(scores.health, 1, "Moon stamina support");
  if ([6, 8, 12].includes(moonFromLagna)) addScore(scores.health, -2, "Body rhythm needs care");
  if ([1, 8, 12].includes(transit.saturn.houseFromMoon)) addScore(scores.health, -1, "Saturn may slow energy");
  if ([3, 6, 11].includes(transit.mars.houseFromLagna)) addScore(scores.health, 1, "Mars supports activity");

  if ([3, 7, 10, 11].includes(transit.mercury.houseFromLagna)) addScore(scores.communication, 2, "Mercury supports follow-up");
  else addScore(scores.communication, -1, "Mercury needs slower replies");
  if ([3, 7, 11].includes(moonFromLagna)) addScore(scores.communication, 1, "Moon supports people");
  if ([2, 8, 12].includes(transit.rahu.houseFromLagna)) addScore(scores.communication, -1, "Rahu can distort tone");
  if (tara.favourable) addScore(scores.communication, 1, "Tara Bala supports timing");

  const timings = {
    sun: sunTimes(date),
    rahuKalam: rahuKalam(date),
    horas: planetaryHoras(date),
  };
  const focus = selectFocus(scores);
  const favourable = selectFavourableWindow(timings.horas, timings.rahuKalam, focus, scores);
  const sectors = sectorThemes(transit, dasha);

  return {
    date,
    transits,
    transit,
    moonNak,
    dasha,
    tara,
    chandra,
    scores,
    timings,
    favourable,
    focus,
    sectors,
  };
}

function selectFocus(scores) {
  const ranked = Object.entries(scores)
    .filter(([name]) => name !== "overall")
    .sort((a, b) => b[1].value - a[1].value);
  return ranked[0][0];
}

function selectFavourableWindow(horas, caution, focus, scores) {
  const weightsByFocus = {
    study: { Mercury: 5, Jupiter: 4, Sun: 2, Moon: 2 },
    money: { Jupiter: 4, Mercury: 4, Saturn: 3, Venus: 2, Moon: 1 },
    health: { Sun: 4, Mars: 3, Moon: 2, Jupiter: 2 },
    communication: { Mercury: 5, Venus: 3, Moon: 3, Jupiter: 2 },
    overall: { Jupiter: 4, Mercury: 3, Moon: 2, Sun: 2 },
  };
  const weights = weightsByFocus[focus] || weightsByFocus.overall;
  const candidates = horas
    .filter((hora) => hora.period === "day")
    .filter((hora) => !overlaps(hora, caution))
    .map((hora) => ({
      ...hora,
      score: weights[hora.ruler] || 0,
    }))
    .sort((a, b) => b.score - a.score || a.start - b.start);

  const selected = candidates[0] || horas.find((hora) => hora.period === "day");
  return {
    ...selected,
    reason: `${selected.ruler} Hora selected for ${labelForSection(focus)} focus`,
  };
}

function labelForSection(name) {
  return {
    study: "Study & Career",
    money: "Money & Trading Discipline",
    health: "Health & Energy",
    communication: "Communication & People",
    overall: "Overall",
  }[name] || "Overall";
}

function scoreLevel(value) {
  if (value >= 4) return "strong_positive";
  if (value >= 2) return "positive";
  if (value >= 0) return "neutral";
  if (value >= -2) return "caution";
  return "strong_caution";
}

// Interpretation layer: money, health, and trust each split into an
// opportunity/positive dimension and a separate risk dimension (built from
// the same transit/dasha placements that already feed the underlying score),
// so a day can be "financial improvement + high expenses" or "health caution"
// rather than collapsing everything into one Supportive/Balanced/Caution
// bucket. This does not touch the astronomical calculations above - it only
// reads their outputs (scores, dasha, tara, chandra, transit houses) to pick
// a richer sentence.
function generateDailyInterpretation(evaluation) {
  const { scores, dasha, chandra, tara, transit } = evaluation;
  const money = scores.money.value;
  const health = scores.health.value;
  const study = scores.study.value;
  const communication = scores.communication.value;
  const overall = scores.overall.value;

  const moneyOpportunity =
    (chandra ? 1 : 0) +
    ([3, 6, 10, 11].includes(transit.jupiter.houseFromMoon) ? 2 : 0) +
    ([2, 5, 9, 11].includes(transit.jupiter.houseFromLagna) ? 1 : 0) +
    (dasha.mahadasha === "Jupiter" ? 1 : 0) +
    (dasha.mahadasha === "Venus" ? 1 : 0);
  const moneyRisk =
    (money <= -1 ? 1 : 0) +
    ([8, 12].includes(transit.mars.houseFromLagna) ? 2 : 0) +
    ([4, 8, 12].includes(transit.rahu.houseFromMoon) ? 2 : 0) +
    (dasha.mahadasha === "Rahu" ? 1 : 0) +
    (dasha.antardasha?.lord === "Rahu" ? 1 : 0);
  // Rahu/Ketu transiting the 1st, 6th or 8th from lagna, and Mars in the 6th
  // or 8th, are the standard dusthana-based health-caution triggers (6th =
  // disease, 8th = chronic/hidden ailment or accident-prone, 12th =
  // hospitalisation); Saturn on the natal Moon's 1st/8th/12th already covered
  // low-vitality Sade-Sati-style pressure.
  const healthRisk =
    (health <= -1 ? 1 : 0) +
    ([6, 8, 12].includes(transit.moon.houseFromLagna) ? 1 : 0) +
    ([1, 8, 12].includes(transit.saturn.houseFromMoon) ? 2 : 0) +
    ([1, 6, 8].includes(transit.rahu.houseFromLagna) ? 1 : 0) +
    ([1, 6, 8].includes(transit.ketu.houseFromLagna) ? 1 : 0) +
    ([6, 8].includes(transit.mars.houseFromLagna) ? 2 : 0);
  // A same-sign Mercury-Rahu conjunction is the classic Vedic indicator for
  // distorted or manipulative communication (Rahu overtakes Mercury's
  // clarity), so it carries as much weight as an already-negative
  // communication score.
  const trustRisk =
    (communication <= -1 ? 1 : 0) +
    ([2, 8, 12].includes(transit.rahu.houseFromLagna) ? 2 : 0) +
    (!tara.favourable ? 1 : 0) +
    (transit.mercury.sign === transit.rahu.sign ? 2 : 0);
  const studyPositive =
    (study >= 2 ? 2 : 0) +
    ([2, 5, 7, 9, 11].includes(transit.jupiter.houseFromMoon) ? 2 : 0) +
    ([1, 2, 5, 9, 10, 11].includes(transit.mercury.houseFromLagna) ? 1 : 0);

  let overallText;
  if (overall <= -2) {
    overallText =
      "Aaj ka din thoda sensitive reh sakta hai. Jaldi decisions lene ke bajay dheere aur soch-samajh kar chalna better rahega.";
  } else if (overall >= 4) {
    overallText =
      "Aaj overall conditions supportive reh sakti hain. Important kaam complete karne aur practical decisions lene ke liye din useful hai.";
  } else {
    overallText =
      "Aaj ka din mixed but manageable reh sakta hai. Routine maintain karo aur important decisions mein unnecessary hurry avoid karo.";
  }

  let moneyText;
  if (moneyOpportunity >= 3 && moneyRisk >= 3) {
    moneyText =
      "Financial position improve hone ke chances hain, lekin money outflow aur impulsive decisions rukawat create kar sakte hain. Trading mein opportunity dikhe tab bhi risk rules compromise mat karo.";
  } else if (moneyOpportunity >= 3 && moneyRisk < 3) {
    moneyText =
      "Financial matters comparatively supportive reh sakte hain. Paisa-related planning aur practical decisions ke liye din theek hai, lekin unnecessary risk avoid karo.";
  } else if (moneyOpportunity >= 1 && moneyRisk >= 3) {
    moneyText =
      "Thoda financial improvement possible hai, lekin abhi outflow aur impulsiveness ka risk zyada dominant hai. Koi bhi bada paisa wala decision lene se pehle expenses aur trading activity dono control mein rakho.";
  } else if (moneyRisk >= 3) {
    moneyText =
      "Money matters mein caution rakho. Unnecessary expenses, impulsive decisions ya pressure mein liya gaya financial decision problem create kar sakta hai. Trading activity controlled rakho.";
  } else if (money <= -1) {
    moneyText =
      "Aaj financial discipline important rahega. Har paisa wala decision lene se pehle apne rules check karo aur unnecessary activity avoid karo.";
  } else {
    moneyText =
      "Financial matters relatively balanced reh sakte hain. Normal planning theek hai, lekin bina proper setup ke financial risk lena avoid karo.";
  }

  let healthText;
  if (healthRisk >= 3) {
    healthText =
      "Health ko lightly mat lena. Food, hydration, sleep aur daily routine mein care rakho. Overexertion aur unnecessary stress avoid karo.";
  } else if (healthRisk >= 2 || health <= -1) {
    healthText =
      "Health aur energy mein thodi care ki zarurat reh sakti hai. Khane-peene, hydration aur rest mein carelessness avoid karo.";
  } else if (health >= 2) {
    healthText =
      "Energy comparatively supportive reh sakti hai. Routine maintain karo aur kaam ke beech proper breaks lete raho.";
  } else {
    healthText =
      "Health ke liye normal routine follow karna sufficient rahega. Food, hydration aur rest ko ignore mat karo.";
  }

  let careerText;
  if (studyPositive >= 4) {
    careerText =
      "Padhai aur career-related work ke liye achha time hai. Pending ya difficult task ko complete karne par focus karo.";
  } else if (study >= 1) {
    careerText =
      "Padhai aur career ke liye din workable hai. Ek important task ko priority dekar complete karna better rahega.";
  } else if (study <= -2) {
    careerText =
      "Focus maintain karne mein thodi difficulty ho sakti hai. Naye complicated work ko force karne ke bajay revision aur pending tasks complete karo.";
  } else {
    careerText =
      "Career aur studies mein steady progress ke liye routine follow karo. Consistency aaj speed se zyada important rahegi.";
  }

  let socialText;
  if (trustRisk >= 3) {
    socialText =
      "Aaj doosron ki baaton par blindly trust mat karo. Important information ya suggestions ko verify karke hi decision lena.";
  } else if (trustRisk >= 1) {
    socialText =
      "Communication normal rahegi, lekin koi bhi important suggestion ya information verify karke hi follow karo.";
  } else if (communication >= 2) {
    socialText =
      "Communication aur follow-ups ke liye din supportive reh sakta hai. Practical discussions smoothly handle ho sakti hain.";
  } else {
    socialText =
      "Communication normal rahegi, lekin unnecessary arguments aur assumptions avoid karna better hai.";
  }

  let todayAction;
  if (moneyRisk >= 3) {
    todayAction =
      "Koi bhi paisa wala decision lene se pehle apna rule/checklist dekho. Ek important study ya career task complete karo.";
  } else if (studyPositive >= 4) {
    todayAction =
      "Aaj apne most important study ya career task ko priority do aur use complete karne ki koshish karo.";
  } else {
    todayAction =
      "Ek important pending task complete karo aur financial decisions mein predefined rules follow karo.";
  }

  let avoidToday;
  if (moneyRisk >= 3) {
    avoidToday =
      "Jaldi wale financial decisions, revenge trading, unnecessary spending aur pressure mein rules change karna avoid karo.";
  } else if (trustRisk >= 3) {
    avoidToday =
      "Doosron ki advice ko bina verify kiye follow karna, assumptions aur unnecessary arguments avoid karo.";
  } else if (healthRisk >= 3) {
    avoidToday =
      "Health ko ignore karna, irregular food/sleep aur unnecessary overwork avoid karo.";
  } else {
    avoidToday =
      "Overconfidence, unnecessary risk aur bina reason apna plan change karna avoid karo.";
  }

  return {
    overallText,
    moneyText,
    healthText,
    careerText,
    socialText,
    todayAction,
    avoidToday,
    diagnostics: {
      moneyOpportunity,
      moneyRisk,
      healthRisk,
      trustRisk,
      studyPositive,
      levels: {
        overall: scoreLevel(overall),
        money: scoreLevel(money),
        health: scoreLevel(health),
        study: scoreLevel(study),
        communication: scoreLevel(communication),
      },
    },
  };
}

// Number of each nakshatra lord in Vedic numerology; the lucky number is the
// number of the lord of the nakshatra the Moon is in at 07:00 IST.
const LORD_NUMBERS = Object.freeze({
  Sun: 1,
  Moon: 2,
  Jupiter: 3,
  Rahu: 4,
  Mercury: 5,
  Venus: 6,
  Ketu: 7,
  Saturn: 8,
  Mars: 9,
});

function luckyNumber(evaluation) {
  return LORD_NUMBERS[evaluation.moonNak.lord];
}

// Same date always gives the same wording; neighbouring days and different
// slots rotate through the variants so the post does not repeat itself.
function pickVariant(date, slot, options) {
  return options[(dayOfYear(date) + slot * 3) % options.length];
}

// Slow planets (Mercury, Rahu) keep the same optional lines triggered for
// weeks, so take 3 of the triggered ones starting at a date-based offset; the
// post then varies daily without ever using a line no transit triggered.
function rotateOptional(optional, date, limit = 3) {
  if (optional.length <= limit) return optional;
  const start = dayOfYear(date) % optional.length;
  return Array.from({ length: limit }, (_, i) => optional[(start + i) % optional.length]);
}

// AstroSage-style prediction: one flowing paragraph of short sentences that
// mixes good and bad across life areas (health, money, work, family, people,
// travel, speech, devices) instead of one block per topic. Romance and
// spouse lines are left out on purpose - the reports exclude them. Every
// sentence is picked from the same transit/dasha/score outputs as the rest of
// the report; nothing here changes the astronomical calculation.
function generateForecast(evaluation) {
  const { date, scores, dasha, chandra, tara, transit, transits } = evaluation;
  const interpretation = generateDailyInterpretation(evaluation);
  const { moneyOpportunity, moneyRisk, healthRisk, trustRisk, studyPositive } =
    interpretation.diagnostics;
  const overall = scores.overall.value;
  const study = scores.study.value;
  const health = scores.health.value;
  const communication = scores.communication.value;
  const moonFromLagna = transit.moon.houseFromLagna;
  const pick = (slot, options) => pickVariant(date, slot, options);

  let opener;
  if (overall >= 3) {
    opener = pick(0, [
      "Din ki shuruaat energy ke saath hogi aur ruke hue kaam aage badhenge.",
      "Aaj confidence high rahega, jo kaam talte aa rahe the unhe nipta lo.",
      "Sitare aaj saath dete dikh rahe hain, important kaam ko aage badhao.",
    ]);
  } else if (overall >= 0) {
    opener = pick(0, [
      "Aaj ka din mixed rahega, kuch kaam smoothly honge aur kuch mein thoda wait karna padega.",
      "Din normal chalega, bas apni routine pakde raho.",
      "Aaj mann kabhi halka aur kabhi thoda bhaari reh sakta hai, par sab manageable rahega.",
    ]);
  } else {
    opener = pick(0, [
      "Aaj mood mein utaar-chadhav reh sakta hai, jaldbaazi mein koi bada faisla mat lo.",
      "Din thoda sensitive hai, dheere aur soch-samajh kar chalo.",
      "Kuch cheezein aaj tense kar sakti hain, lekin ghabrane ki zarurat nahi, din nikal jayega.",
    ]);
  }

  let healthLine;
  if (healthRisk >= 3) {
    healthLine = pick(1, [
      "Khane-peene mein bilkul laparwahi mat karo, bahar ka khana aur neend ki kami tabiyat bigaad sakti hai.",
      "Sehat ko halke mein mat lo, paani, neend aur time par khana teeno zaroori hain.",
    ]);
  } else if (healthRisk >= 2 || health <= -1) {
    healthLine = pick(1, [
      "Khane-peene mein savdhaan raho, laparwahi se sehat bigad sakti hai.",
      "Energy thodi dheemi lag sakti hai, kaam ke beech break lete raho.",
    ]);
  } else if (health >= 2) {
    healthLine = pick(1, [
      "Sehat achhi rahegi aur energy high, exercise ya sports ke liye achha din hai.",
      "Body fit lagegi, aaj ka workout ya walk skip mat karo.",
    ]);
  } else {
    healthLine = pick(1, [
      "Sehat normal rahegi, bas paani aur neend ka dhyan rakho.",
      "Health theek rahegi, khane ka time na bigaado.",
    ]);
  }

  let moneyLine;
  if (moneyOpportunity >= 3 && moneyRisk >= 3) {
    moneyLine = pick(2, [
      "Paise ki position improve hogi, lekin kharche aur outflow phir bhi kaam mein rukawat daalenge.",
      "Income ke chances achhe hain, par kharche utni hi tezi se aayenge, trading mein bhi apne rules mat todo.",
    ]);
  } else if (moneyOpportunity >= 3) {
    moneyLine = pick(2, [
      "Paise ke maamle supportive hain, planning aur practical decisions ke liye din theek hai.",
      "Financial side achhi rahegi, bas unnecessary risk se bacho.",
    ]);
  } else if (moneyOpportunity >= 1 && moneyRisk >= 3) {
    moneyLine = pick(2, [
      "Thoda financial improvement dikhega, par kharche aur impulsiveness dominant rahenge.",
      "Paisa aayega bhi aur jayega bhi, bada financial faisla aaj mat lo.",
    ]);
  } else if (moneyRisk >= 3) {
    moneyLine = pick(2, [
      "Paise ke maamle mein savdhaan raho, bina soche kharch ya pressure mein liya faisla nuksaan de sakta hai.",
      "Aaj paisa haath se phisal sakta hai, kharche aur trading dono control mein rakho.",
    ]);
  } else if (scores.money.value <= -1) {
    moneyLine = pick(2, [
      "Paise ka har faisla apne rules check karke hi lo.",
      "Financial discipline aaj important rahega, unnecessary activity avoid karo.",
    ]);
  } else {
    moneyLine = pick(2, [
      "Paise ke maamle balanced rahenge, normal planning chalegi.",
      "Financial matters stable rahenge, bina setup ke risk mat lo.",
    ]);
  }

  const recognition =
    [6, 10, 11].includes(transit.sun.houseFromLagna) || moonFromLagna === 10;
  let workLine;
  if (studyPositive >= 4) {
    workLine = pick(3, [
      "Padhai aur career ke liye shandaar din hai, mehnat ka phal milne ke chance hain, mushkil task nipta lo.",
      "Concentration achha rahega, ek difficult topic ya pending kaam aaj khatam karo.",
    ]);
  } else if (recognition && study >= 0) {
    workLine = pick(3, [
      "Aapki mehnat par kisi ka dhyan jayega, kaam par recognition mil sakti hai.",
      "Kaam par aapki mehnat notice hogi, apna best do.",
    ]);
  } else if (study >= 1) {
    workLine = pick(3, [
      "Padhai aur career workable hain, ek important task ko priority do.",
      "Kaam mein progress hogi, bas ek cheez pe focus rakho.",
    ]);
  } else if (study <= -2) {
    workLine = pick(3, [
      "Focus bikhar sakta hai, naya complicated kaam force mat karo, revision aur pending kaam karo.",
      "Dhyan bhatakne ka din hai, bade topic ke bajay chhote tasks khatam karo.",
    ]);
  } else {
    workLine = pick(3, [
      "Kaam mein steady progress hogi, speed se zyada consistency chalegi.",
      "Padhai aur kaam routine mein chalenge, shortcuts mat dhundho.",
    ]);
  }

  const familyCaution =
    ([2, 4].includes(transit.mars.houseFromLagna) ? 1 : 0) +
    ([2, 4].includes(transit.rahu.houseFromLagna) ? 1 : 0) +
    ([2, 4].includes(transit.ketu.houseFromLagna) ? 1 : 0) +
    ([2, 4].includes(transit.saturn.houseFromLagna) ? 1 : 0) +
    ([8, 12].includes(moonFromLagna) ? 1 : 0);
  const familySupport =
    ([2, 4, 5, 9, 11].includes(transit.jupiter.houseFromLagna) ? 1 : 0) +
    ([2, 4].includes(moonFromLagna) ? 1 : 0) +
    (tara.favourable ? 1 : 0) +
    (chandra ? 1 : 0);
  let familyLine;
  if (familyCaution >= 2) {
    familyLine = pick(4, [
      "Ghar mein chhoti baat par bahas ho sakti hai, bade-buzurgon se tone narm rakho.",
      "Family mein kisi ki baat chubh sakti hai, jawab dene se pehle ruk jao.",
    ]);
  } else if (familySupport >= 3) {
    familyLine = pick(4, [
      "Ghar ka mahaul sukoon bhara rahega, family ke saath waqt bitaoge to achha lagega.",
      "Family ke saath entertainment ya khana mazedaar rahega.",
    ]);
  } else {
    familyLine = pick(4, [
      "Family ke liye thoda waqt nikalo, unki chhoti zarooraton par dhyan do.",
      "Ghar mein kisi chhote-bade ko aapki baat ya madad ki zarurat ho sakti hai.",
    ]);
  }

  let peopleLine;
  if (trustRisk >= 3) {
    peopleLine = pick(5, [
      "Doosron ki baaton par aankh band karke bharosa mat karo, jo suno use verify karo.",
      "Koi aapko galat salah ya adhoori jaankari de sakta hai, sochkar hi maano.",
    ]);
  } else if (trustRisk >= 1) {
    peopleLine = pick(5, [
      "Kisi ki suggestion follow karne se pehle ek baar check kar lo.",
      "Logon ki baat sunna theek hai, par faisla apna rakho.",
    ]);
  } else if (communication >= 2) {
    peopleLine = pick(5, [
      "Baat-cheet aur follow-ups ke liye din supportive hai, practical discussions smoothly honge.",
      "Aapki communication aaj impressive rahegi.",
    ]);
  } else {
    peopleLine = pick(5, [
      "Logon se baat-cheet normal rahegi, faltu bahas aur assumptions se door raho.",
      "Kisi ke baare mein jaldi raay mat banao.",
    ]);
  }

  // Optional lines, each only when a transit actually triggers it.
  const optional = [];

  const travelCaution =
    [1, 4, 8, 12].includes(transit.mars.houseFromLagna) ||
    ([8, 12].includes(moonFromLagna) && [1, 4].includes(transit.rahu.houseFromLagna));
  const travelGood =
    [3, 9].includes(moonFromLagna) ||
    [3, 9].includes(transit.jupiter.houseFromLagna);
  if (travelCaution && travelGood) {
    optional.push(
      pick(6, [
        "Safar thaka dene wala aur bhaag-daud bhara ho sakta hai, par faydemand rahega.",
        "Travel hectic rahega lekin uska result achha milega, gaadi dhyan se chalana.",
      ]),
    );
  } else if (travelCaution) {
    optional.push(
      pick(6, [
        "Gaadi dhyan se chalao, khaaskar chauraho aur mod par, overtake karne mein jaldi mat karo.",
        "Safar mein jaldbaazi mat karo, thoda extra time lekar nikalo.",
      ]),
    );
  } else if (travelGood) {
    optional.push(
      pick(6, [
        "Chhota safar ya bahar ka kaam faydemand rahega, naye log aur nayi jagah milengi.",
        "Aaj bahar nikalna achha rahega, naye contacts ban sakte hain.",
      ]),
    );
  }

  if (moneyRisk >= 2 || [4, 8, 12].includes(transit.rahu.houseFromMoon)) {
    optional.push(
      pick(7, [
        "Koi tip, scheme ya sure-shot offer attractive lage to pehle gehrai se verify karo, phir commit karo.",
        "Jo opportunity bahut easy lage uski poori jaankari nikaalo, apne experts se poochho.",
      ]),
    );
  }

  const mercuryRetro = transits.mercury.speed < 0;
  if (mercuryRetro) {
    optional.push(
      pick(8, [
        "Mercury vakri hai, phone, apps ya trading platform mein glitch ho sakta hai, message ya order bhejne se pehle double-check karo.",
        "Technology aur paperwork mein galti ho sakti hai, bheje se pehle ek baar padh lo.",
      ]),
    );
  } else if ([6, 8, 12].includes(transit.mercury.houseFromLagna)) {
    optional.push(
      pick(8, [
        "Mobile par zyada time mat bitao, kaam mein disturbance aur galti ho sakti hai.",
        "Phone aur screen aaj dhyan bhatka sakte hain, kaam ke time unse door raho.",
      ]),
    );
  }

  const speechRisk =
    [2, 8, 12].includes(transit.mercury.houseFromLagna) ||
    transit.mercury.sign === transit.rahu.sign ||
    transit.mercury.sign === transit.mars.sign;
  if (speechRisk) {
    optional.push(
      pick(9, [
        "Zubaan par control rakho, ek galat shabd se kaam ya rishta bigad sakta hai.",
        "Aaj bolne se zyada sunna fayda dega, chup rehna kabhi-kabhi behtar hai.",
      ]),
    );
  }

  const friendSupport =
    [3, 11].includes(moonFromLagna) ||
    [3, 11].includes(transit.venus.houseFromLagna) ||
    [3, 11].includes(transit.jupiter.houseFromLagna);
  if (friendSupport && trustRisk < 3) {
    optional.push(
      pick(10, [
        "Dosto ke saath achha waqt guzrega, aur kaam ke naye log milne ke mauke hain.",
        "Doston ya known logon se kisi kaam ki madad mil sakti hai.",
      ]),
    );
  }

  let closing;
  if (overall >= 2) {
    closing = pick(11, [
      "Mauke ka fayda uthao, aaj ki mehnat aage kaam aayegi.",
      "Jo plan banaya hai use aaj aage badhao.",
    ]);
  } else {
    closing = pick(11, [
      "Aaj ka din agle kadam ki planning ke liye use karo, future ke liye sochne mein kabhi der nahi hoti.",
      "Jaldbaazi chhodo aur ek-ek kaam karte jao.",
    ]);
  }

  return [
    opener,
    healthLine,
    moneyLine,
    workLine,
    familyLine,
    peopleLine,
    ...rotateOptional(optional, date),
    closing,
  ].join(" ");
}

function getAstrologicalFocus(evaluation) {
  const { scores, dasha } = evaluation;
  const focusParts = [];
  if (scores.money.value <= -1) {
    focusParts.push("financial discipline");
  }
  if (scores.health.value <= -1) {
    focusParts.push("health and routine");
  }
  if (scores.study.value >= 2) {
    focusParts.push("study and career progress");
  }
  if (scores.communication.value <= -1) {
    focusParts.push("communication and verification");
  }
  if (dasha?.mahadasha) {
    focusParts.push(`${dasha.mahadasha} Mahadasha`);
  }
  if (!focusParts.length) {
    focusParts.push("steady routine and practical decisions");
  }
  return focusParts.slice(0, 3).join(" • ");
}

function sectorThemes(transit, dasha) {
  const evaluated = Object.fromEntries(
    Object.entries(SECTOR_THEME_DEFINITIONS).map(([name, factors]) => [
      name,
      scoreSectorTheme(factors, transit, dasha),
    ]),
  );

  const supportive = Object.entries(evaluated)
    .filter(([, item]) => item.supportReachable)
    .filter(([, item]) => item.score >= item.supportThreshold && item.supporting >= 1)
    .map(([name]) => name);
  const caution = Object.entries(evaluated)
    .filter(([, item]) => item.cautionReachable)
    .filter(([, item]) => item.score <= item.cautionThreshold && item.cautioning >= 1)
    .map(([name]) => name);

  if (!supportive.length && !caution.length) {
    return null;
  }
  return {
    supportive,
    caution,
    raw: Object.fromEntries(
      Object.entries(evaluated).map(([name, item]) => [name, item.score]),
    ),
    diagnostics: evaluated,
  };
}

function scoreSectorTheme(factors, transit, dasha) {
  let score = 0;
  let supporting = 0;
  let cautioning = 0;
  let theoreticalMin = 0;
  let theoreticalMax = 0;
  for (const factor of factors) {
    if (factor.score > 0) theoreticalMax += factor.score;
    if (factor.score < 0) theoreticalMin += factor.score;
    if (!sectorFactorApplies(factor, transit, dasha)) continue;
    score += factor.score;
    if (factor.score > 0) supporting += 1;
    if (factor.score < 0) cautioning += 1;
  }
  // SECTOR_THEME_THRESHOLD (a fixed magnitude of 3) doesn't fit every
  // sector: each theme is defined with a different number/strength of
  // factors (e.g. Metals/Gold tops out at +2, Real Estate at +1, and no
  // sector has more than one negative-scored factor), so a single global
  // bar made caution unreachable for every sector and support unreachable
  // for two of them. Instead require a majority of that sector's own
  // achievable range - a threshold calibrated to what the theme can
  // actually produce, not an arbitrary constant every theme must match.
  const supportThreshold = theoreticalMax > 0 ? Math.max(1, Math.ceil(theoreticalMax * 0.6)) : Infinity;
  const cautionThreshold = theoreticalMin < 0 ? Math.min(-1, Math.floor(theoreticalMin * 0.6)) : -Infinity;
  return {
    score,
    supporting,
    cautioning,
    theoreticalMin,
    theoreticalMax,
    supportThreshold,
    cautionThreshold,
    supportReachable: theoreticalMax >= supportThreshold,
    cautionReachable: theoreticalMin <= cautionThreshold,
  };
}

function sectorFactorApplies(factor, transit, dasha) {
  if (factor.type === "dasha") {
    return dasha.mahadasha === factor.lord || dasha.antardasha?.lord === factor.lord;
  }
  if (factor.type === "house") {
    return factor.houses.includes(transit[factor.planet]?.[factor.relation]);
  }
  return false;
}

function displayDate(date) {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(Date.UTC(date.year, date.month - 1, date.day, 6)));
}

function buildDailyText(evaluation) {
  const interpretation = generateDailyInterpretation(evaluation);
  const lines = [
    `DAILY ASTROLOGY | ${displayDate(evaluation.date)}`,
    "",
    generateForecast(evaluation),
    "",
    `Today's Lucky Number: ${luckyNumber(evaluation)}`,
    "",
    `Accha Time: ${formatWindow(evaluation.favourable)}`,
    `Savdhaan Time: ${formatWindow(evaluation.timings.rahuKalam)}`,
    "",
    `Aaj Karo: ${interpretation.todayAction}`,
    `Aaj Na Karo: ${interpretation.avoidToday}`,
    "",
    `Astrological Focus: ${getAstrologicalFocus(evaluation)}`,
  ];

  return lines.join("\n");
}

function buildDailyEmbed(evaluation) {
  const interpretation = generateDailyInterpretation(evaluation);
  const fields = [
    {
      name: "Today's Lucky Number",
      value: String(luckyNumber(evaluation)),
    },
    {
      name: "Accha Time",
      value: formatWindow(evaluation.favourable),
      inline: true,
    },
    {
      name: "Savdhaan Time",
      value: formatWindow(evaluation.timings.rahuKalam),
      inline: true,
    },
    {
      name: "Aaj Karo",
      value: interpretation.todayAction,
    },
    {
      name: "Aaj Na Karo",
      value: interpretation.avoidToday,
    },
    {
      name: "Astrological Focus",
      value: getAstrologicalFocus(evaluation),
    },
  ];

  return {
    title: `Victus Daily Astrology - ${displayDate(evaluation.date)}`,
    description: generateForecast(evaluation),
    color: 0x5865f2,
    fields,
    footer: {
      text: "Sirf reflection ke liye. Apna trading setup, stop-loss aur position-size rules khud follow karna.",
    },
  };
}

function buildDailyPayload(date) {
  const evaluation = evaluateDay(date);
  const content = buildDailyText(evaluation);
  return {
    payload: {
      username: "Victus Daily Astrology",
      content: "",
      embeds: [buildDailyEmbed(evaluation)],
      allowed_mentions: { parse: [] },
    },
    text: content,
    diagnostics: diagnosticsFor(evaluation),
  };
}

function diagnosticsFor(evaluation) {
  return {
    date: evaluation.date,
    ayanamsha: "Lahiri",
    node: "Mean Node",
    natal: {
      ascendantSign: signName(NATAL.ascendant),
      moonSign: signName(NATAL.moon),
      moonNakshatra: nakshatraDetails(NATAL.moon),
    },
    transits: evaluation.transit,
    moonNakshatra: evaluation.moonNak,
    dasha: {
      mahadasha: evaluation.dasha.mahadasha,
      antardasha: evaluation.dasha.antardasha.lord,
      mahadashaStart: ymd(evaluation.dasha.mahadashaStart),
      mahadashaEnd: ymd(evaluation.dasha.mahadashaEnd),
      antardashaStart: ymd(evaluation.dasha.antardasha.start),
      antardashaEnd: ymd(evaluation.dasha.antardasha.end),
    },
    sunrise: formatHour(evaluation.timings.sun.sunrise),
    sunset: formatHour(evaluation.timings.sun.sunset),
    rahuKalam: formatWindow(evaluation.timings.rahuKalam),
    selectedHora: {
      ruler: evaluation.favourable.ruler,
      window: formatWindow(evaluation.favourable),
      reason: evaluation.favourable.reason,
    },
    chandraBala: evaluation.chandra,
    taraBala: evaluation.tara,
    scores: Object.fromEntries(
      Object.entries(evaluation.scores).map(([key, score]) => [key, score.value]),
    ),
    sectorThemes: evaluation.sectors?.raw || null,
  };
}

function ymd(date) {
  return date.toISOString().slice(0, 10);
}

function parseWeekStart() {
  const override = process.env.ASTROLOGY_WEEK_START?.trim();
  if (override) {
    return parseYmd(override, "ASTROLOGY_WEEK_START");
  }
  const base = parseForecastDate();
  const day = weekdayIndex(base);
  const daysUntilMonday = day === 0 ? 1 : 8 - day;
  return addDays(base, daysUntilMonday);
}

function weeklyRangeLabel(start) {
  const end = addDays(start, 6);
  const startLabel = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
  }).format(new Date(Date.UTC(start.year, start.month - 1, start.day, 6)));
  const endLabel = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(Date.UTC(end.year, end.month - 1, end.day, 6)));
  return `${startLabel}-${endLabel}`.toUpperCase();
}

function weekdayLabel(date) {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
    day: "numeric",
  }).format(new Date(Date.UTC(date.year, date.month - 1, date.day, 6)));
}

function weeklyHighlights(evaluations) {
  const totals = evaluations.map((item) => item.scores.overall.value);
  const stronger = evaluations
    .filter((item) => item.scores.overall.value >= 2)
    .map((item) => weekdayLabel(item.date));
  const caution = evaluations
    .filter((item) => item.scores.overall.value <= -2 || item.scores.money.value <= -2)
    .map((item) => weekdayLabel(item.date));
  const bestDay = evaluations
    .slice()
    .sort((a, b) => b.scores.overall.value - a.scores.overall.value)[0];
  const mainFocus =
    totals.reduce((sum, value) => sum + value, 0) >= 7
      ? "Strong days par mushkil kaam karo, baaki din routine consistent rakho."
      : "Hafta practical rakho: kam faisle, saaf routine aur likhi hui priorities.";
  const avoid = evaluations.some((item) => item.scores.money.value <= -2)
    ? "Emotional paisa decisions aur pressure mein rules badalna avoid karo."
    : "Schedule ko overload karna aur facts check kiye bina react karna avoid karo.";
  const lucky = evaluations
    .map((item) => `${weekdayLabel(item.date)}: ${luckyNumber(item)}`)
    .join(" | ");
  return { stronger, caution, bestDay, mainFocus, avoid, lucky };
}

// Weekly counterpart of generateForecast: one flowing Hinglish paragraph for
// the whole week, built from the seven daily evaluations. Names the best and
// weakest day per area so the week reads as a plan, not an average. Romance
// and spouse lines stay out, same as the daily post.
function generateWeeklyForecast(evaluations) {
  const days = evaluations.map((evaluation) => ({
    evaluation,
    label: weekdayLabel(evaluation.date),
    diag: generateDailyInterpretation(evaluation).diagnostics,
  }));
  const avg = (fn) => days.reduce((sum, day) => sum + fn(day), 0) / days.length;
  const best = (fn) => days.slice().sort((a, b) => fn(b) - fn(a))[0].label;
  const worst = (fn) => days.slice().sort((a, b) => fn(a) - fn(b))[0].label;
  const score = (name) => (day) => day.evaluation.scores[name].value;
  const first = evaluations[0].date;
  const pick = (slot, options) => pickVariant(first, slot, options);

  const overall = avg(score("overall"));
  let opener;
  if (overall >= 2) {
    opener = pick(0, [
      "Ye hafta supportive rahega, ruke hue kaam aage badhane ka achha mauka hai.",
      "Hafta energy ke saath shuru hoga aur mehnat ka phal milne ke chance hain.",
    ]);
  } else if (overall <= -1) {
    opener = pick(0, [
      "Ye hafta thoda sensitive rahega, jaldbaazi mein bade faisle mat lo.",
      "Hafta dheere aur soch-samajh kar chalne ka hai, ghabrane ki zarurat nahi.",
    ]);
  } else {
    opener = pick(0, [
      "Hafta mixed rahega, kuch din smooth aur kuch din thoda slow.",
      "Ye hafta normal chalega, bas apni routine pakde raho.",
    ]);
  }

  const healthRisk = avg((d) => d.diag.healthRisk);
  const healthLine =
    healthRisk >= 2 || avg(score("health")) <= -1
      ? pick(1, [
          `Khane-peene aur neend mein laparwahi mat karo, khaaskar ${worst(score("health"))} ko sehat ka dhyan rakho.`,
          `Energy thodi dheemi reh sakti hai, ${worst(score("health"))} ko extra rest lo.`,
        ])
      : avg(score("health")) >= 2
        ? pick(1, [
            `Sehat achhi rahegi, exercise ya sports ke liye ${best(score("health"))} sabse achha din hai.`,
            "Body fit rahegi, hafte bhar walk ya workout ki routine banao.",
          ])
        : pick(1, [
            "Sehat normal rahegi, bas paani, neend aur khane ka time na bigaado.",
            "Health theek rahegi, thakaan ho to rest skip mat karo.",
          ]);

  const moneyRisk = avg((d) => d.diag.moneyRisk);
  const moneyOpportunity = avg((d) => d.diag.moneyOpportunity);
  const moneyNet = (d) => d.diag.moneyOpportunity - d.diag.moneyRisk;
  let moneyLine;
  if (moneyOpportunity >= 2 && moneyRisk >= 2) {
    moneyLine = pick(2, [
      `Paise ke chances achhe hain lekin kharche bhi utne hi rahenge, ${best(moneyNet)} sabse supportive aur ${worst(moneyNet)} sabse tight rahega.`,
      "Income aur outflow dono tez rahenge, trading mein bhi apne rules mat todo.",
    ]);
  } else if (moneyRisk >= 2) {
    moneyLine = pick(2, [
      `Paise ke maamle mein savdhaan raho, ${worst(score("money"))} ko bina soche kharch ya trade mat karo.`,
      "Hafte mein paisa haath se phisal sakta hai, kharche aur trading control mein rakho.",
    ]);
  } else if (moneyOpportunity >= 2 || avg(score("money")) >= 1) {
    moneyLine = pick(2, [
      `Financial side supportive rahegi, planning ke liye ${best(score("money"))} achha rahega.`,
      "Paise ke maamle stable rahenge, bas unnecessary risk se bacho.",
    ]);
  } else {
    moneyLine = pick(2, [
      "Paise ke maamle balanced rahenge, normal planning chalegi.",
      "Financial discipline important rahegi, har faisla rules check karke lo.",
    ]);
  }

  const workLine =
    avg(score("study")) >= 1.5
      ? pick(3, [
          `Padhai aur career ke liye achha hafta hai, mushkil kaam ${best(score("study"))} ko nipta lo.`,
          `Concentration achha rahega, ${best(score("study"))} ko ek bada pending kaam khatam karo.`,
        ])
      : avg(score("study")) <= -1
        ? pick(3, [
            `Focus bikhar sakta hai, ${worst(score("study"))} ko naya complicated kaam force mat karo.`,
            "Bade topic ke bajay chhote tasks aur revision pe dhyan do.",
          ])
        : pick(3, [
            "Kaam mein steady progress hogi, speed se zyada consistency chalegi.",
            "Padhai aur kaam routine mein chalenge, shortcuts mat dhundho.",
          ]);

  const calmDays = days.filter((d) => d.evaluation.chandra).length;
  const familyLine =
    calmDays >= 5
      ? pick(4, [
          "Ghar ka mahaul sukoon bhara rahega, family ke saath waqt bitaoge to achha lagega.",
          "Family ke saath entertainment ya khana mazedaar rahega.",
        ])
      : calmDays <= 2
        ? pick(4, [
            "Ghar mein chhoti baat par bahas ho sakti hai, bade-buzurgon se tone narm rakho.",
            "Family mein kisi ki baat chubh sakti hai, jawab dene se pehle ruk jao.",
          ])
        : pick(4, [
            "Family ke liye thoda waqt nikalo, unki chhoti zarooraton par dhyan do.",
            "Ghar mein kisi ko aapki baat ya madad ki zarurat ho sakti hai.",
          ]);

  const trustRisk = avg((d) => d.diag.trustRisk);
  const peopleLine =
    trustRisk >= 2
      ? pick(5, [
          `Doosron ki baaton par aankh band karke bharosa mat karo, khaaskar ${best((d) => d.diag.trustRisk)} ko jo suno use verify karo.`,
          "Koi galat salah ya adhoori jaankari de sakta hai, sochkar hi maano.",
        ])
      : avg(score("communication")) >= 1.5
        ? pick(5, [
            `Baat-cheet aur follow-ups ke liye hafta supportive hai, ${best(score("communication"))} sabse achha rahega.`,
            "Aapki communication impressive rahegi, naye log milne ke mauke hain.",
          ])
        : pick(5, [
            "Logon se baat-cheet normal rahegi, faltu bahas aur assumptions se door raho.",
            "Kisi ke baare mein jaldi raay mat banao.",
          ]);

  const optional = [];
  const travelDays = days
    .filter((d) => [1, 4, 8, 12].includes(d.evaluation.transit.mars.houseFromLagna))
    .map((d) => d.label);
  if (travelDays.length >= 1 && travelDays.length < days.length) {
    optional.push(
      `Gaadi dhyan se chalao, khaaskar ${travelDays[0]} se, aur safar mein jaldbaazi mat karo.`,
    );
  } else if (travelDays.length === days.length) {
    optional.push("Hafte bhar gaadi dhyan se chalao aur safar mein extra time lekar nikalo.");
  }
  if (moneyRisk >= 1.5) {
    optional.push(
      "Koi tip, scheme ya sure-shot offer attractive lage to pehle gehrai se verify karo, phir commit karo.",
    );
  }
  if (evaluations.some((item) => item.transits.mercury.speed < 0)) {
    optional.push(
      "Mercury vakri hai, phone, apps ya trading platform mein glitch ho sakta hai, bhejne se pehle double-check karo.",
    );
  }
  if (
    avg((d) =>
      d.evaluation.transit.mercury.sign === d.evaluation.transit.rahu.sign ? 1 : 0,
    ) > 0.5
  ) {
    optional.push("Zubaan par control rakho, ek galat shabd se kaam bigad sakta hai.");
  }

  const bestDay = best(score("overall"));
  const closing =
    overall >= 2
      ? `${bestDay} ko sabse achha mauka hai, us din apna sabse zaroori kaam rakho.`
      : `${bestDay} sabse achha din rahega, bade kaam uske aas-paas plan karo.`;

  return [
    opener,
    healthLine,
    moneyLine,
    workLine,
    familyLine,
    peopleLine,
    ...rotateOptional(optional, first),
    closing,
  ].join(" ");
}

function buildWeeklyText(start, evaluations) {
  const { stronger, caution, bestDay, mainFocus, avoid, lucky } =
    weeklyHighlights(evaluations);
  const lines = [
    `NEXT WEEK ASTROLOGY | ${weeklyRangeLabel(start)}`,
    "",
    generateWeeklyForecast(evaluations),
    "",
    `Lucky Numbers: ${lucky}`,
    "",
    `Stronger Days: ${stronger.length ? stronger.join(", ") : "None clearly stronger"}`,
    `Caution Days: ${caution.length ? caution.join(", ") : "None clearly caution"}`,
    `Best Period of Week: ${weekdayLabel(bestDay.date)} ${formatWindow(bestDay.favourable)}`,
    "",
    `Main Focus: ${mainFocus}`,
    `Avoid: ${avoid}`,
  ];

  const weeklySectors = mergeWeeklySectors(evaluations);
  if (weeklySectors) {
    lines.push("", "Sector Themes:");
    if (weeklySectors.supportive.length) {
      lines.push(`Supportive: ${weeklySectors.supportive.join(", ")}`);
    }
    if (weeklySectors.caution.length) {
      lines.push(`Caution: ${weeklySectors.caution.join(", ")}`);
    }
  }

  return lines.join("\n");
}

function buildWeeklyEmbed(start, evaluations) {
  const { stronger, caution, bestDay, mainFocus, avoid, lucky } =
    weeklyHighlights(evaluations);
  const fields = [
    { name: "Lucky Numbers", value: lucky },
    {
      name: "Stronger Days",
      value: stronger.length ? stronger.join(", ") : "None clearly stronger",
      inline: true,
    },
    {
      name: "Caution Days",
      value: caution.length ? caution.join(", ") : "None clearly caution",
      inline: true,
    },
    {
      name: "Best Period",
      value: `${weekdayLabel(bestDay.date)} ${formatWindow(bestDay.favourable)}`,
    },
    { name: "Main Focus", value: mainFocus },
    { name: "Avoid", value: avoid },
  ];

  const weeklySectors = mergeWeeklySectors(evaluations);
  if (weeklySectors) {
    const sectorLines = [];
    if (weeklySectors.supportive.length) {
      sectorLines.push(`Supportive: ${weeklySectors.supportive.join(", ")}`);
    }
    if (weeklySectors.caution.length) {
      sectorLines.push(`Caution: ${weeklySectors.caution.join(", ")}`);
    }
    if (sectorLines.length) {
      fields.push({ name: "Sector Themes", value: sectorLines.join("\n") });
    }
  }

  return {
    title: `Victus Weekly Astrology - ${weeklyRangeLabel(start)}`,
    description: generateWeeklyForecast(evaluations),
    color: 0x5865f2,
    fields,
    footer: {
      text: "Sirf reflection ke liye. Apna trading setup, stop-loss aur position-size rules khud follow karna.",
    },
  };
}

function mergeWeeklySectors(evaluations) {
  const totals = {};
  for (const evaluation of evaluations) {
    if (!evaluation.sectors) continue;
    for (const [sector, value] of Object.entries(evaluation.sectors.raw)) {
      totals[sector] = (totals[sector] || 0) + value;
    }
  }
  const supportive = Object.entries(totals)
    .filter(([, value]) => value >= 9)
    .map(([sector]) => sector);
  const caution = Object.entries(totals)
    .filter(([, value]) => value <= -9)
    .map(([sector]) => sector);
  if (!supportive.length && !caution.length) return null;
  return { supportive, caution };
}

function buildWeeklyPayload(start) {
  const evaluations = Array.from({ length: 7 }, (_, index) => evaluateDay(addDays(start, index)));
  const content = buildWeeklyText(start, evaluations);
  return {
    payload: {
      username: "Victus Weekly Astrology",
      content: "",
      embeds: [buildWeeklyEmbed(start, evaluations)],
      allowed_mentions: { parse: [] },
    },
    text: content,
    diagnostics: evaluations.map(diagnosticsFor),
  };
}

function postJson(url, payload, attempt = 1) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const request = https.request(
      url,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body),
        },
        timeout: 15000,
      },
      (response) => {
        let responseBody = "";
        response.on("data", (chunk) => {
          responseBody += chunk;
        });
        response.on("end", async () => {
          if (response.statusCode === 429 && attempt < 6) {
            let retryAfterMs = 1000;
            try {
              const parsed = JSON.parse(responseBody);
              retryAfterMs = Math.max(
                250,
                Math.min(Number(parsed.retry_after || 1) * 1000, 30000),
              );
            } catch {
              // Use the default delay.
            }
            resolve(postJson(url, payload, attempt + 1));
            return;
          }
          if (response.statusCode < 200 || response.statusCode >= 300) {
            reject(
              new Error(
                `Discord returned ${response.statusCode}: ${responseBody.slice(0, 300)}`,
              ),
            );
            return;
          }
          resolve();
        });
      },
    );
    request.on("timeout", () => {
      request.destroy(new Error("Discord request timed out."));
    });
    request.on("error", reject);
    request.write(body);
    request.end();
  });
}

module.exports = {
  NATAL,
  NATAL_DISPLAY_REFERENCE,
  SECTOR_THEME_DEFINITIONS,
  SECTOR_THEME_THRESHOLD,
  addDays,
  activeDasha,
  buildDailyPayload,
  buildWeeklyPayload,
  evaluateDay,
  generateForecast,
  generateWeeklyForecast,
  luckyNumber,
  getTransits,
  houseFromSign,
  nakshatraDetails,
  parseForecastDate,
  parseWeekStart,
  planetaryHoras,
  postJson,
  rahuKalam,
  scoreSectorTheme,
  signName,
  sunTimes,
  transitDiagnostics,
};
