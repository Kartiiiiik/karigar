import { BS_MONTHS, adToBsParts, bsToApi, currentYear, daysInBsMonth } from "../lib/date";

/**
 * Calendar-aware date input. The value in/out is ALWAYS an AD `YYYY-MM-DD`
 * string (the API contract). When the shop calendar is BS, the user picks a
 * BS year / month / day and we convert to AD under the hood.
 */
export default function DateInput({ value, onChange, calendar = "AD", id }) {
  if (calendar !== "BS") {
    return (
      <input
        id={id}
        className="input"
        type="date"
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  // BS mode: three selects. Default to today (BS) when no value yet.
  const parts = adToBsParts(value) || adToBsParts(new Date());
  const baseYear = currentYear("BS");
  const years = Array.from({ length: 20 }, (_, i) => baseYear - 16 + i);
  const days = daysInBsMonth(parts.year, parts.month);

  const emit = (next) => {
    const y = next.year ?? parts.year;
    const m = next.month ?? parts.month;
    let d = next.day ?? parts.day;
    const max = daysInBsMonth(y, m);
    if (d > max) d = max; // clamp when switching to a shorter month
    onChange(bsToApi(y, m, d));
  };

  return (
    <div className="flex gap-2">
      <select className="input" value={parts.day}
        onChange={(e) => emit({ day: Number(e.target.value) })} aria-label="Day">
        {Array.from({ length: days }, (_, i) => i + 1).map((d) => (
          <option key={d} value={d}>{d}</option>
        ))}
      </select>
      <select className="input" value={parts.month}
        onChange={(e) => emit({ month: Number(e.target.value) })} aria-label="Month">
        {BS_MONTHS.map((m, i) => <option key={m} value={i}>{m}</option>)}
      </select>
      <select className="input" value={parts.year}
        onChange={(e) => emit({ year: Number(e.target.value) })} aria-label="Year">
        {years.map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
    </div>
  );
}
