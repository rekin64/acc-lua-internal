// Simulated $500 position, marked to the price shown in the chart header.
//
// Every amount is derived from the prices exactly as displayed (4 significant
// digits), in exact integer arithmetic, so anyone can re-check the panel with
// a calculator: tokens = 500 / entry, value = tokens x price,
// PNL = value - 500, ROI = PNL / 500 x 100 (fees and slippage excluded).

import { FPS } from './engine.js';
import { priceDecimals } from './format.js';

export const POSITION_SIZE_USD = 500;
// Frame 30 (t = 0.500 s) is the first frame whose header shows $0.00001567.
export const ENTRY_FRAME = 30;

// Displayed price as an exact fraction { n, d, text }.
export function displayedPrice(p) {
  const dec = priceDecimals(p);
  const text = p.toFixed(dec);
  return { n: BigInt(text.replace('.', '')), d: 10n ** BigInt(dec), text: `$${text}` };
}

// Round n / d to the nearest integer, halves away from zero.
function roundDiv(n, d) {
  if (d < 0n) {
    n = -n;
    d = -d;
  }
  const q = (2n * n + (n >= 0n ? d : -d)) / (2n * d);
  return q;
}

export function buildPosition(market, { sizeUsd = POSITION_SIZE_USD, entryFrame = ENTRY_FRAME } = {}) {
  const entryT = entryFrame / FPS;
  const s0 = market.stateAt(entryT);
  const entry = displayedPrice(s0.price);
  const size = BigInt(sizeUsd);
  const entrySlot = s0.candles.length - 1;
  // tokens = size / entry = size * entry.d / entry.n
  const tokensHundredths = roundDiv(size * entry.d * 100n, entry.n);

  return {
    sizeCents: size * 100n,
    entryT,
    entryFrame,
    entry,
    entryValue: Number(entry.n) / Number(entry.d),
    entrySlot,
    tokensHundredths,
    at(t) {
      const price = displayedPrice(market.stateAt(t).price);
      if (t < entryT - 1e-9) return { open: false, price };
      // value = size * price / entry, as exact fractions
      const num = size * price.n * entry.d;
      const den = price.d * entry.n;
      const valueCents = roundDiv(num * 100n, den);
      const pnlCents = valueCents - size * 100n;
      // ROI % = (price / entry - 1) * 100, in basis points of a percent
      const roiBp = roundDiv((num - size * den) * 10000n, size * den);
      return { open: true, price, valueCents, pnlCents, roiBp };
    },
  };
}
