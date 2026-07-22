import NepaliDate from "nepali-date-converter";

// ---------------------------------------------------------------------------
// Single source of truth for date formatting on the frontend.
//
// The API always exchanges AD (Gregorian) ISO-8601 dates. BS is derived here,
// purely for display, based on the active calendar preference. BS is never
// sent to the backend as a source of truth.
// ---------------------------------------------------------------------------

const BS_MONTHS = [
  "Baisakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
  "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra",
];
const AD_MONTHS_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

// Available display formats. Keep the keys in sync with the backend DateFormat.
export const DATE_FORMATS = [
  { value: "DMY_TEXT", label: "Day Month Year (27 Magh 2080)" },
  { value: "YMD", label: "Year-Month-Day (2080-10-27)" },
  { value: "DMY", label: "Day/Month/Year (27/10/2080)" },
  { value: "MDY", label: "Month/Day/Year (10/27/2080)" },
];

function pad(n) {
  return String(n).padStart(2, "0");
}

function render(year, month, day, monthName, fmt) {
  switch (fmt) {
    case "YMD":
      return `${year}-${pad(month)}-${pad(day)}`;
    case "DMY":
      return `${pad(day)}/${pad(month)}/${year}`;
    case "MDY":
      return `${pad(month)}/${pad(day)}/${year}`;
    default: // DMY_TEXT
      return `${day} ${monthName} ${year}`;
  }
}

/**
 * Format an AD date (ISO string or Date) in the active calendar + format.
 * @param {string|Date|null|undefined} value  AD date from the API.
 * @param {"BS"|"AD"} calendar                Active display calendar.
 * @param {{withTime?: boolean, format?: string}} [opts]
 * @returns {string}
 */
export function formatDate(value, calendar = "AD", opts = {}) {
  if (!value) return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const fmt = opts.format || "DMY_TEXT";

  let out;
  if (calendar === "BS") {
    const bs = new NepaliDate(date).getBS(); // { year, month (0-based), date }
    out = render(bs.year, bs.month + 1, bs.date, BS_MONTHS[bs.month], fmt);
  } else {
    out = render(date.getFullYear(), date.getMonth() + 1, date.getDate(), AD_MONTHS_SHORT[date.getMonth()], fmt);
  }

  if (opts.withTime) {
    out += ` ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }
  return out;
}

/** Convert an AD Date to a `YYYY-MM-DD` string for API submission. */
export function toApiDate(date) {
  const d = date instanceof Date ? date : new Date(date);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Current year in the active calendar (BS year or AD year). */
export function currentYear(calendar = "AD") {
  const now = new Date();
  return calendar === "BS" ? new NepaliDate(now).getBS().year : now.getFullYear();
}

/**
 * AD start/end (`{from, to}` ISO strings) for a whole month in the active
 * calendar. `monthIdx` is 0-based (0 = Baisakh in BS, January in AD).
 */
export function monthRangeToApi(calendar, year, monthIdx) {
  let start;
  let end;
  if (calendar === "BS") {
    start = new NepaliDate(year, monthIdx, 1).toJsDate();
    const ny = monthIdx === 11 ? year + 1 : year;
    const nm = monthIdx === 11 ? 0 : monthIdx + 1;
    const nextStart = new NepaliDate(ny, nm, 1).toJsDate();
    end = new Date(nextStart.getTime() - 86400000); // day before next month
  } else {
    start = new Date(year, monthIdx, 1);
    end = new Date(year, monthIdx + 1, 0); // last day of month
  }
  return { from: toApiDate(start), to: toApiDate(end) };
}

/** Number of days in a BS month (year, 0-based month). */
export function daysInBsMonth(year, monthIdx) {
  const start = new NepaliDate(year, monthIdx, 1).toJsDate();
  const ny = monthIdx === 11 ? year + 1 : year;
  const nm = monthIdx === 11 ? 0 : monthIdx + 1;
  const next = new NepaliDate(ny, nm, 1).toJsDate();
  return Math.round((next - start) / 86400000);
}

/** BS (year, 0-based month, day) -> AD `YYYY-MM-DD`. */
export function bsToApi(year, monthIdx, day) {
  return toApiDate(new NepaliDate(year, monthIdx, day).toJsDate());
}

/** AD ISO/date -> BS parts `{ year, month (0-based), day }`, or null. */
export function adToBsParts(value) {
  if (!value) return null;
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  const bs = new NepaliDate(d).getBS();
  return { year: bs.year, month: bs.month, day: bs.date };
}

export { BS_MONTHS };
