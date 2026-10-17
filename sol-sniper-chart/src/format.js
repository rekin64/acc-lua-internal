// Number formatting shared by the chart header and the position panel.

// Decimals that show a token price with 4 significant digits.
export function priceDecimals(p) {
  return Math.max(2, 3 - Math.floor(Math.log10(p)));
}

export function formatPrice(p) {
  return '$' + p.toFixed(priceDecimals(p));
}

export function formatPct(pct) {
  const r = Math.round(pct);
  return (r >= 0 ? '+' : '-') + Math.abs(r).toLocaleString('en-US') + '%';
}

const MINUS = '−';

// Exact decimal string of `cents` (BigInt or integer) as "1,234.56".
export function centsToString(cents) {
  const c = BigInt(cents);
  const abs = c < 0n ? -c : c;
  const whole = (abs / 100n).toLocaleString('en-US');
  return `${whole}.${String(abs % 100n).padStart(2, '0')}`;
}

// "$4,116.15"; with signed: true -> "+$3,616.15" / "−$12.40" / "$0.00".
export function formatUsdCents(cents, { signed = false } = {}) {
  const c = BigInt(cents);
  const sign = !signed || c === 0n ? '' : c > 0n ? '+' : MINUS;
  return `${sign}$${centsToString(c)}`;
}

// Basis points of a percent (12345 -> "+123.45%").
export function formatPctBp(bp) {
  const b = BigInt(bp);
  const sign = b === 0n ? '' : b > 0n ? '+' : MINUS;
  return `${sign}${centsToString(b < 0n ? -b : b)}%`;
}
