const { test, expect, chromium } = require('@playwright/test');
const { mkdirSync, writeFileSync } = require('node:fs');
const { dirname } = require('node:path');

test('Companion Type browser user chain', async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' });

  const clicked = [];
  async function click(name) {
    await page.getByRole('button', { name, exact: true }).click({ timeout: 10000 });
    clicked.push(name);
  }

  await click('Check');
  await click('Scan');
  await click('Connect');
  await click('Sync');
  await click('Import');
  await click('Minutes');
  await click('Markdown');

  const markdown = await page.locator('textarea.ct-minutes-output').inputValue();
  expect(markdown).toContain('## Action Items');

  await click('Audio');
  await click('Text');

  const footer = await page.locator('footer').innerText();
  const screenshotPath = 'docs/validation/companion-type-browser-ui-chain.png';
  await page.screenshot({ path: screenshotPath, fullPage: true });
  const artifact = {
    schema: 'companion_type.browser_ui_chain.v1',
    generatedAt: new Date().toISOString(),
    result: 'PASS',
    url: 'http://127.0.0.1:5173/',
    clicked,
    markdownBytes: new TextEncoder().encode(markdown).length,
    footer,
    screenshotPath,
  };
  const out = 'docs/validation/companion-type-browser-ui-chain.json';
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, `${JSON.stringify(artifact, null, 2)}\n`);
  await browser.close();
});
