// Display helpers for money, gold weight, and signed Dr/Cr balances.

const nprWhole = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const nprPaisa = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

// Whole rupee amounts read cleaner without a trailing ".00", but once paisa
// are involved we always show both digits — "17,500" / "17,500.50", never
// "17,500.5". Round first so 17500.001 counts as whole.
function money(value) {
  const n = Math.round(Number(value ?? 0) * 100) / 100;
  return Number.isInteger(n) ? nprWhole.format(n) : nprPaisa.format(n);
}

/** Format an NPR amount, e.g. 12500 -> "NPR 12,500", 12500.5 -> "NPR 12,500.50". */
export function formatNpr(value) {
  return `NPR ${money(value)}`;
}

/** Amount only (no NPR prefix), e.g. 12500 -> "12,500", 12500.5 -> "12,500.50".
 * For table cells where the unit lives in the column header. */
export function formatAmount(value) {
  return money(value);
}

/** Format grams to 3dp, e.g. "9.167 g". */
export function formatGrams(value) {
  const n = Number(value ?? 0);
  return `${n.toFixed(3)} g`;
}

/** Grams value only (no unit), e.g. 9.1667 -> "9.167". */
export function formatGramsValue(value) {
  return Number(value ?? 0).toFixed(3);
}

/**
 * Interpret a signed balance. Positive = Dr (karigar holds shop's asset),
 * negative = Cr (shop owes karigar), zero = settled.
 * @returns {{amount:number, direction:"Dr"|"Cr"|"—", isDr:boolean, isCr:boolean, isZero:boolean}}
 */
export function balanceParts(value) {
  const n = Number(value ?? 0);
  if (n > 0) return { amount: n, direction: "Dr", isDr: true, isCr: false, isZero: false };
  if (n < 0) return { amount: -n, direction: "Cr", isDr: false, isCr: true, isZero: false };
  return { amount: 0, direction: "—", isDr: false, isCr: false, isZero: true };
}

/** Signed gold balance -> "7.000 g Dr" / "2.000 g Cr" / "Settled". */
export function formatGoldBalance(value) {
  const b = balanceParts(value);
  if (b.isZero) return "Settled";
  return `${b.amount.toFixed(3)} g ${b.direction}`;
}

/** Signed cash balance -> "NPR 3,000.00 Dr" / "Settled". */
export function formatCashBalance(value) {
  const b = balanceParts(value);
  if (b.isZero) return "Settled";
  return `${formatNpr(b.amount)} ${b.direction}`;
}
