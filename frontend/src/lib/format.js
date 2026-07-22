// Display helpers for money, gold weight, and signed Dr/Cr balances.

const npr = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Format an NPR amount, e.g. 12500 -> "NPR 12,500.00". */
export function formatNpr(value) {
  const n = Number(value ?? 0);
  return `NPR ${npr.format(n)}`;
}

/** Format grams to 3dp, e.g. "9.167 g". */
export function formatGrams(value) {
  const n = Number(value ?? 0);
  return `${n.toFixed(3)} g`;
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
