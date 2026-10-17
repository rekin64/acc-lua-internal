// Writes out/pnl-frames.csv: for each of the 600 frames, the price shown in
// the header and the position panel values, to audit the PNL by hand.
// Usage: node scripts/export-pnl-table.js

import { writeFile } from 'node:fs/promises';
import { buildMarket, DURATION, FPS } from '../src/engine.js';
import { centsToString, formatPct, formatPctBp, formatPrice, formatUsdCents } from '../src/format.js';
import { buildPosition } from '../src/position.js';

const market = buildMarket();
const position = buildPosition(market);
const rows = [['frame', 'time_s', 'header_price', 'token_change', 'position', 'entry_price', 'tokens', 'current_value', 'unrealized_pnl', 'roi']];
for (let f = 0; f < FPS * DURATION; f++) {
  const t = f / FPS;
  const s = market.stateAt(t);
  const p = position.at(t);
  rows.push([
    f,
    t.toFixed(3),
    formatPrice(s.price),
    formatPct(s.pct),
    p.open ? 'OPEN' : 'NO POSITION',
    p.open ? position.entry.text : '',
    p.open ? centsToString(position.tokensHundredths) : '',
    p.open ? formatUsdCents(p.valueCents) : '',
    p.open ? formatUsdCents(p.pnlCents, { signed: true }).replace('−', '-') : '',
    p.open ? formatPctBp(p.roiBp).replace('−', '-') : '',
  ]);
}
const csv = rows.map((r) => r.map((v) => (/[",]/.test(String(v)) ? `"${v}"` : v)).join(',')).join('\n') + '\n';
const out = new URL('../out/pnl-frames.csv', import.meta.url);
await writeFile(out, csv);
console.log('wrote', out.pathname, `(${rows.length - 1} frames)`);
