// Render individual frames of any page that follows the render contract.
//   node scripts/snap.mjs [page] --times 0,1.5,3 [--out out/snaps] [--w 1080 --h 1920] [--prefix name] [--query a=1]
// page defaults to src/index.html. Prints the written PNG paths.
import fs from 'node:fs';
import path from 'node:path';
import { startServer, ROOT } from './server.mjs';
import { launch, openPage } from './browser.mjs';

const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf('--' + name); return i >= 0 ? args[i + 1] : def; };
const page = args[0] && !args[0].startsWith('--') ? args[0] : 'src/index.html';
const times = opt('times', '0').split(',').map(Number);
const out = path.resolve(ROOT, opt('out', 'out/snaps'));
const w = Number(opt('w', 1080)), h = Number(opt('h', 1920));
const prefix = opt('prefix', path.basename(page, '.html'));
const query = opt('query', '');

fs.mkdirSync(out, { recursive: true });
const { server, port } = await startServer();
const browser = await launch();
try {
  const p = await openPage(browser, `http://127.0.0.1:${port}/${page}${query ? '?' + query : ''}`, { width: w, height: h });
  for (const t of times) {
    await p.evaluate((t) => window.__render(t), t);
    const file = path.join(out, `${prefix}_${t.toFixed(3)}.png`);
    await p.screenshot({ path: file, type: 'png' });
    console.log(file);
  }
  if (p.__errors.length) console.error('PAGE ERRORS:\n' + p.__errors.join('\n'));
} finally {
  await browser.close();
  server.close();
}
