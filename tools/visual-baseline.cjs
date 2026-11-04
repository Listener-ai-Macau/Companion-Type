const { chromium } = require('@playwright/test');
const path = require('path');
(async () => {
  const browser = await chromium.launch({headless: true});
  for (const [name, url, viewport] of [
    ['windows', 'http://127.0.0.1:1432/', {width: 1440, height: 900}],
    ['mobile', 'http://127.0.0.1:1433/', {width: 390, height: 844}],
  ]) {
    const page = await browser.newPage({viewport, deviceScaleFactor: 1});
    await page.goto(url, {waitUntil:'networkidle'});
    await page.screenshot({path:path.join('E:/CodexData/Companion/unified-frontends-r2-20261102', name+'-'+(process.env.COMPANION_VISUAL_STAGE || 'baseline')+'.png'), fullPage:true});
    console.log(name, await page.title(), (await page.locator('body').innerText()).slice(0,450));
    await page.close();
  }
  await browser.close();
})().catch(error => {console.error(error); process.exit(1)});
