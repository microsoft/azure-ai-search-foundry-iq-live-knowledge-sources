// Capture deterministic frames from scene.html using a system Chrome.
// Usage: npm install && node capture.js   (then ./build.sh)
const path = require('path');
const fs = require('fs');
const puppeteer = require('puppeteer-core');

const DUR_MS = 11000;
const FPS = 15;
const OUT = path.join(__dirname, 'frames');

function findChrome() {
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const candidates = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
  ];
  for (const c of candidates) if (fs.existsSync(c)) return c;
  throw new Error('Chrome not found. Set CHROME_PATH=/path/to/chrome');
}

(async () => {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: findChrome(),
    headless: 'new',
    args: ['--no-sandbox', '--force-color-profile=srgb', '--hide-scrollbars'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1000, height: 640, deviceScaleFactor: 2 });
  await page.goto('file://' + path.join(__dirname, 'scene.html'), { waitUntil: 'networkidle0' });
  const total = Math.round((DUR_MS / 1000) * FPS);
  for (let i = 0; i < total; i++) {
    const ms = Math.round((i / FPS) * 1000);
    await page.evaluate((t) => window.__seek(t), ms);
    await new Promise((r) => setTimeout(r, 30));
    await page.screenshot({ path: path.join(OUT, String(i).padStart(4, '0') + '.png') });
  }
  console.log('captured', total, 'frames ->', OUT);
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
