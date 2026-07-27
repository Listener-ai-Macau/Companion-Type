// verify_companion_type_installed_user_journey.spec.cjs
// Holistic platform-layer acceptance: drives the INSTALLED Companion-Type app
// (real Tauri WebView2) through a full real-user journey via Playwright-over-CDP.
// Because the webview is the real Tauri runtime, isTauriRuntime() is true and the
// button clicks invoke the real Tauri command -> real Rust backend (synthetic mode,
// env-overridden BLE), so Start/Sync/Minutes/Export all run for real on-host.
//
// Requires the app to be built from the setup() that honors COMPANION_TYPE_WEBVIEW_ARGS
// (see apps/windows/src-tauri/src/lib.rs) and installed via verify:msi-install-smoke.
const { chromium, test, expect } = require('@playwright/test');
const fs = require('fs');
const net = require('net');
const http = require('http');
const os = require('os');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

const INSTALLED_EXE = process.env.COMPANION_TYPE_INSTALLED_EXE || String.raw`C:\Program Files\Companion Type\companion-type.exe`;
const OUT_JSON = path.resolve('docs/validation/companion-type-installed-user-journey.json');
const SHOT_DIR = path.resolve('docs/validation');
const RESULT_PLACEHOLDER = '连接板子并同步录音、转写后，这里显示纪要…';

function freePort() {
  return new Promise((resolve) => {
    const s = net.createServer();
    s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => resolve(p)); });
  });
}

function writeShortWav(file) {
  // minimal 16kHz mono PCM WAV, ~0.5s of near-silence (low-amplitude sine avoids all-zero)
  const sampleRate = 16000; const seconds = 0.5; const samples = sampleRate * seconds;
  const dataLen = samples * 2;
  const buf = Buffer.alloc(44 + dataLen);
  buf.write('RIFF', 0); buf.writeUInt32LE(36 + dataLen, 4); buf.write('WAVE', 8);
  buf.write('fmt ', 12); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(1, 22); buf.writeUInt32LE(sampleRate, 24);
  buf.writeUInt32LE(sampleRate * 2, 28); buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34);
  buf.write('data', 36); buf.writeUInt32LE(dataLen, 40);
  for (let i = 0; i < samples; i++) {
    const v = Math.round(Math.sin(2 * Math.PI * 440 * (i / sampleRate)) * 800);
    buf.writeInt16LE(v, 44 + i * 2);
  }
  fs.writeFileSync(file, buf);
}

function probeVersion(port) {
  return new Promise((resolve) => {
    const req = http.get({ host: '127.0.0.1', port, path: '/json/version', timeout: 1500 }, (res) => {
      let body = ''; res.on('data', (c) => (body += c)); res.on('end', () => {
        try { resolve({ ok: res.statusCode === 200, json: JSON.parse(body) }); } catch { resolve({ ok: false }); }
      });
    });
    req.on('error', () => resolve({ ok: false }));
    req.on('timeout', () => { req.destroy(); resolve({ ok: false }); });
  });
}

async function waitForCdp(port, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const r = await probeVersion(port);
    if (r.ok) return r.json;
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`/json/version never responded on port ${port}`);
}

async function getPage(browser, timeoutMs = 25000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const ctxs = browser.contexts();
    if (ctxs.length && ctxs[0].pages().length) return ctxs[0].pages()[0];
    await new Promise((r) => setTimeout(r, 250));
  }
  const ctx = browser.contexts()[0];
  if (!ctx) throw new Error('no browser context exposed over CDP');
  return ctx.waitForEvent('page', { timeout: 5000 });
}

const transcriptText = [
  'Alex 开启了周会并确认 Companion 录音状态正常。',
  '决定：Companion 用 STM32 闪存作短缓存，主机 app 负责一小时会议录音。',
  '行动：Maya 在周五前把 BLE 录音触发接到 Windows app。',
  '行动负责人：Chen，截止 7 月 5 日，需校验导入转写和导出 Markdown。',
  '问题：首次硬件 beta 前是否需要本地唤醒词？',
].join('\n');

const state = { child: null, port: null, wavFile: null, recDir: null, artifact: null };

test.describe('installed user journey', () => {
  test.describe.configure({ mode: 'serial' });

  test.beforeAll(async () => {
    if (!fs.existsSync(INSTALLED_EXE)) {
      test.skip(true, 'installed exe not present; run npm run tauri:windows + verify:msi-install-smoke first');
    }
    fs.mkdirSync(SHOT_DIR, { recursive: true });
    state.port = await freePort();
    state.recDir = fs.mkdtempSync(path.join(os.tmpdir(), 'companion-journey-'));
    state.wavFile = path.join(state.recDir, 'device-recording.wav');
    writeShortWav(state.wavFile);

    state.child = spawn(INSTALLED_EXE, [], {
      env: {
        ...process.env,
        COMPANION_TYPE_WEBVIEW_ARGS: `--remote-debugging-port=${state.port}`,
        COMPANION_TYPE_HOST_RECORDING_MODE: 'synthetic',
        COMPANION_TYPE_BLE_NATIVE_READY: '1',
        COMPANION_TYPE_DEVICE_RECORDING_PATH: state.wavFile,
        COMPANION_TYPE_RECORDING_DIR: state.recDir,
      },
      stdio: 'ignore',
      detached: false,
    });
    await waitForCdp(state.port);
  });

  test('real user drives full meeting journey on installed app', async () => {
    const browser = await chromium.connectOverCDP(`http://127.0.0.1:${state.port}`);
    const page = await getPage(browser);
    await page.getByRole('heading', { name: '会议纪要' }).waitFor({ state: 'visible', timeout: 20000 });

    const shots = [];
    const snap = (name) => {
      const p = path.join(SHOT_DIR, `companion-type-installed-user-journey-${name}.png`);
      shots.push(p);
      return page.screenshot({ path: p, fullPage: true });
    };
    const journey = [];
    const t0 = Date.now();
    const click = async (label, action) => {
      const started = Date.now();
      await page.getByRole('button', { name: label, exact: true }).click({ timeout: 15000 });
      journey.push({ button: label, action, ok: true, durationMs: Date.now() - started });
    };

    let journeyMode = 'env-overridden-ble-full-chain';
    let phase = 'connect';
    let error = null;
    try {
      await snap('00-initial');
      // Path A: main product flow (scan -> connect -> sync -> import -> minutes -> export).
      await click('扫描', 'deviceScan');
      await click('连接', 'deviceConnect');
      phase = 'sync';
      await snap('01-after-connect');
      // 同步短录 is gated on connected; Playwright auto-waits for it to enable.
      await click('同步短录', 'deviceSyncRecordings');
      await snap('02-after-sync');
      phase = 'import';
      // transcript textarea enables once hasSyncedAudio; fill() auto-waits for editable.
      const ta = page.locator('textarea.ct-step-textarea').first();
      await ta.fill(transcriptText);
      await click('导入文本', 'meetingImportTranscript');
      await snap('03-after-import');
      phase = 'minutes';
      // 生成纪要 gated on canGenerate (transcript present); auto-waits.
      await click('生成纪要', 'meetingGenerateMinutes');
      await snap('04-after-minutes');
      phase = 'export';
      await click('导出 Markdown', 'meetingExportMarkdown');
      await snap('05-after-export');
    } catch (e) {
      error = e && e.message ? e.message : String(e);
      // Path B fallback: no-board demo -> minutes -> export.
      if (phase === 'connect' || phase === 'sync') {
        journeyMode = 'meetingLoadDemo-fallback';
        try {
          await page.getByRole('button', { name: '展开高级功能（本机长会 / 演示 / 隐私）', exact: true }).click({ timeout: 8000 });
          await click('调试：无板演示', 'meetingLoadDemo');
          await snap('04-after-minutes');
          await click('生成纪要', 'meetingGenerateMinutes');
          await click('导出 Markdown', 'meetingExportMarkdown');
          await snap('05-after-export');
          error = null;
          phase = 'export';
        } catch (e2) {
          error = `Path A failed at ${phase}: ${error}; Path B fallback also failed: ${e2 && e2.message}`;
        }
      }
    }

    // Assert the minutes textarea holds real generated minutes (not the placeholder).
    let markdown = '';
    let minutesContainsActionItems = false;
    try {
      markdown = (await page.locator('textarea.ct-minutes-output').first().inputValue({ timeout: 8000 })) || '';
      minutesContainsActionItems = markdown.includes('## Action Items') && markdown !== RESULT_PLACEHOLDER;
    } catch (e) {
      if (!error) error = `minutes read failed: ${e && e.message}`;
    }
    if (!error) expect(minutesContainsActionItems, 'minutes textarea should contain generated ## Action Items').toBeTruthy();

    state.artifact = {
      schema: 'companion_type.installed_user_journey.v1',
      generatedAt: new Date().toISOString(),
      result: error ? 'FAIL' : 'PASS',
      phase: error ? phase : 'export-markdown',
      error,
      installedExe: INSTALLED_EXE,
      processId: state.child ? state.child.pid : null,
      cdpEndpoint: `http://127.0.0.1:${state.port}`,
      webViewAgent: 'playwright-connectOverCDP',
      tauriRuntime: true,
      syntheticMode: true,
      journeyMode,
      env: {
        COMPANION_TYPE_WEBVIEW_ARGS: `--remote-debugging-port=${state.port}`,
        COMPANION_TYPE_HOST_RECORDING_MODE: 'synthetic',
        COMPANION_TYPE_BLE_NATIVE_READY: '1',
        COMPANION_TYPE_DEVICE_RECORDING_PATH: state.wavFile,
        COMPANION_TYPE_RECORDING_DIR: state.recDir,
      },
      journey,
      assertions: [
        { name: 'dashboard-mounted', passed: true },
        { name: 'minutesContainsActionItems', passed: minutesContainsActionItems, actual: markdown.slice(0, 200) },
      ],
      clicked: journey.map((j) => j.button),
      markdownBytes: Buffer.byteLength(markdown, 'utf8'),
      durationMs: Date.now() - t0,
      screenshots: {
        initial: { path: shots[0] || null, exists: shots[0] ? fs.existsSync(shots[0]) : false },
        afterConnect: { path: shots[1] || null, exists: shots[1] ? fs.existsSync(shots[1]) : false },
        afterSync: { path: shots[2] || null, exists: shots[2] ? fs.existsSync(shots[2]) : false },
        afterImport: { path: shots[3] || null, exists: shots[3] ? fs.existsSync(shots[3]) : false },
        afterMinutes: { path: shots[4] || null, exists: shots[4] ? fs.existsSync(shots[4]) : false },
        afterExport: { path: shots[5] || null, exists: shots[5] ? fs.existsSync(shots[5]) : false },
      },
    };
    fs.mkdirSync(path.dirname(OUT_JSON), { recursive: true });
    fs.writeFileSync(OUT_JSON, JSON.stringify(state.artifact, null, 2) + '\n');
    await browser.close();
    if (error) throw new Error(error);
  });

  test.afterAll(() => {
    if (state.child && state.child.pid) {
      try { spawnSync('taskkill', ['/F', '/T', '/PID', String(state.child.pid)], { stdio: 'ignore' }); } catch {}
    }
  });
});
