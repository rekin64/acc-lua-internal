// Shared Playwright launcher: uses the system Chromium when PLAYWRIGHT_BROWSERS_PATH provides one.
import { chromium } from 'playwright';

export async function launch() {
  return chromium.launch({
    headless: true,
    args: ['--force-color-profile=srgb', '--disable-lcd-text', '--font-render-hinting=none', '--hide-scrollbars'],
  });
}

/** Open a page that follows the render contract: window.__ready (Promise) + window.__render(t). */
export async function openPage(browser, url, { width = 1080, height = 1920 } = {}) {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__ready !== undefined, null, { timeout: 20000 }).catch(() => {});
  await page.evaluate(() => window.__ready);
  await page.evaluate(() => document.fonts.ready);
  page.__errors = errors;
  return page;
}
