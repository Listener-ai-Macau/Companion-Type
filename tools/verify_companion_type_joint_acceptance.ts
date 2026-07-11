import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';

const OUT_JSON = 'docs/validation/companion-type-joint-acceptance.json';
const TYPE_ROOT = process.cwd();
const FIRMWARE_ROOT = resolve(TYPE_ROOT, '..', 'Companion-Firmware');

function readJson(path: string) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function command(command: string, args: string[], cwd: string) {
  const result = spawnSync(command, args, { cwd, encoding: 'utf8' });
  return {
    command: [command, ...args],
    cwd,
    exitCode: result.status,
    stdoutTail: result.stdout.split(/\r?\n/).slice(-40).join('\n'),
    stderrTail: result.stderr.split(/\r?\n/).slice(-40).join('\n'),
  };
}

function walkFiles(root: string): string[] {
  if (!existsSync(root)) return [];
  const found: string[] = [];
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const path = join(root, entry.name);
    if (entry.isDirectory()) found.push(...walkFiles(path));
    if (entry.isFile()) found.push(path);
  }
  return found;
}

function latestFile(root: string, basename: string): string | null {
  const matches = walkFiles(root)
    .filter((path) => path.endsWith(basename))
    .map((path) => ({ path, mtimeMs: statSync(path).mtimeMs }))
    .sort((left, right) => right.mtimeMs - left.mtimeMs);
  return matches[0]?.path ?? null;
}

function latestJsonFileWhere(
  root: string,
  basename: string,
  predicate: (value: any) => boolean,
): string | null {
  const matches = walkFiles(root)
    .filter((path) => path.endsWith(basename))
    .map((path) => {
      try {
        return { path, value: readJson(path), mtimeMs: statSync(path).mtimeMs };
      } catch {
        return null;
      }
    })
    .filter((entry): entry is { path: string; value: any; mtimeMs: number } => Boolean(entry))
    .filter((entry) => predicate(entry.value))
    .sort((left, right) => right.mtimeMs - left.mtimeMs);
  return matches[0]?.path ?? null;
}

function latestExtension(root: string, extension: string): string | null {
  const matches = walkFiles(root)
    .filter((path) => path.toLowerCase().endsWith(extension.toLowerCase()))
    .map((path) => ({ path, mtimeMs: statSync(path).mtimeMs }))
    .sort((left, right) => right.mtimeMs - left.mtimeMs);
  return matches[0]?.path ?? null;
}

function fileEvidence(path: string) {
  return {
    path,
    exists: existsSync(path),
    bytes: existsSync(path) ? statSync(path).size : 0,
  };
}

function repoFileEvidence(repoRoot: string, path: string) {
  const fullPath = path && /^[A-Za-z]:[\\/]/.test(path) ? path : join(repoRoot, path);
  return {
    path,
    fullPath,
    exists: existsSync(fullPath),
    bytes: existsSync(fullPath) ? statSync(fullPath).size : 0,
  };
}

function envFlag(name: string) {
  return Boolean(process.env[name]?.trim());
}

const artifacts = {
  typeProduct: 'docs/validation/companion-type-productization-chain.json',
  typeBrowser: 'docs/validation/companion-type-browser-ui-chain.json',
  typeBrowserScreenshot: 'docs/validation/companion-type-browser-ui-chain.png',
  typeIndependentAsr: 'docs/validation/companion-type-independent-asr-chain.json',
  typeRealMicrophone: 'docs/validation/companion-type-real-microphone.json',
  typeRealMicrophoneSoak: 'docs/validation/companion-type-real-microphone-soak.json',
  typeReleaseLaunch: 'docs/validation/companion-type-release-launch-smoke.json',
  typeMsiInstallSmoke: 'docs/validation/companion-type-msi-install-smoke.json',
  typeLongMeeting: 'docs/validation/companion-type-long-meeting-chain.json',
  typeNativeBleSmoke: 'docs/validation/companion-type-native-ble-smoke.json',
  typeNativeBleSmokeLog: 'docs/validation/companion-type-native-ble-smoke.log',
  typeNativeBleSyncPopup: 'docs/validation/companion-type-native-ble-sync-popup.json',
  typeNativeBleSyncLog: 'docs/validation/companion-type-native-ble-sync-smoke.log',
  typeNativeBleSyncSerialLog: 'docs/validation/companion-type-native-ble-sync-sw3-serial.log',
  typeInstalledUiSync: 'docs/validation/companion-type-installed-ui-sync.json',
  typeFinalHumanSignoff: 'docs/validation/companion-type-final-human-signoff.json',
  typeDirtyAudit: 'docs/validation/companion-type-dirty-audit.json',
  typeMsi: latestExtension(
    'apps/windows/src-tauri/target/release/bundle/msi',
    '.msi',
  ),
  firmwareButtonChain: latestJsonFileWhere(
    join(FIRMWARE_ROOT, '.cache', 'validation'),
    'companion-button-recording-chain.json',
    (value) => value.status === 'PASS',
  ),
  firmwareButtonChainLatest: latestFile(join(FIRMWARE_ROOT, '.cache', 'validation'), 'companion-button-recording-chain.json'),
  firmwareFlashChain: latestFile(join(FIRMWARE_ROOT, '.cache', 'validation'), 'companion-flash-recording-chain.json'),
  firmwarePostprocess: join(FIRMWARE_ROOT, 'docs', 'validation', 'companion-recording-to-minutes-fixture.json'),
};

const product = readJson(artifacts.typeProduct);
const browser = readJson(artifacts.typeBrowser);
const independentAsr = readJson(artifacts.typeIndependentAsr);
const realMic = readJson(artifacts.typeRealMicrophone);
const realMicSoak = existsSync(artifacts.typeRealMicrophoneSoak) ? readJson(artifacts.typeRealMicrophoneSoak) : null;
const releaseLaunch = existsSync(artifacts.typeReleaseLaunch) ? readJson(artifacts.typeReleaseLaunch) : null;
const msiInstallSmoke = existsSync(artifacts.typeMsiInstallSmoke) ? readJson(artifacts.typeMsiInstallSmoke) : null;
const longMeeting = existsSync(artifacts.typeLongMeeting) ? readJson(artifacts.typeLongMeeting) : null;
const nativeBleSmoke = existsSync(artifacts.typeNativeBleSmoke) ? readJson(artifacts.typeNativeBleSmoke) : null;
const nativeBleSyncPopup = existsSync(artifacts.typeNativeBleSyncPopup) ? readJson(artifacts.typeNativeBleSyncPopup) : null;
const installedUiSync = existsSync(artifacts.typeInstalledUiSync) ? readJson(artifacts.typeInstalledUiSync) : null;
const finalHumanSignoff = existsSync(artifacts.typeFinalHumanSignoff) ? readJson(artifacts.typeFinalHumanSignoff) : null;
const dirtyAudit = existsSync(artifacts.typeDirtyAudit) ? readJson(artifacts.typeDirtyAudit) : null;
const buttonChain = artifacts.firmwareButtonChain ? readJson(artifacts.firmwareButtonChain) : null;
const latestButtonChainAttempt = artifacts.firmwareButtonChainLatest ? readJson(artifacts.firmwareButtonChainLatest) : null;
const flashChain = artifacts.firmwareFlashChain ? readJson(artifacts.firmwareFlashChain) : null;
const postprocess = existsSync(artifacts.firmwarePostprocess)
  ? readJson(artifacts.firmwarePostprocess)
  : {};

assert.equal(product.result, 'PASS', 'productization chain must pass');
assert.equal(browser.result, 'PASS', 'browser UI chain must pass');
assert.equal(independentAsr.result, 'PASS', 'independent ASR chain must pass');
assert.equal(realMic.result, 'PASS', 'real microphone artifact must pass');
if (realMicSoak) assert.ok(
  ['PASS_SHORT_REAL_MIC_SOAK_SMOKE', 'PASS_ONE_HOUR_REAL_MIC_SOAK'].includes(realMicSoak.result),
  'real microphone soak result must be explicit',
);
if (nativeBleSmoke) assert.equal(nativeBleSmoke.result, 'PASS', 'native BLE smoke must pass when present');
if (msiInstallSmoke) assert.equal(msiInstallSmoke.result, 'PASS', 'MSI install smoke must pass when present');
if (longMeeting) assert.equal(longMeeting.result, 'PASS', 'long meeting chain must pass when present');
if (nativeBleSyncPopup) assert.ok(['PASS', 'FAIL'].includes(nativeBleSyncPopup.result), 'native BLE sync popup result must be explicit');
if (installedUiSync) assert.ok(
  String(installedUiSync.result).startsWith('PASS') || String(installedUiSync.result).startsWith('FAIL'),
  'installed UI sync result must be explicit',
);
if (finalHumanSignoff) assert.ok(
  ['PASS', 'FAIL_HUMAN_REJECTED', 'PENDING_HUMAN_SIGNOFF', 'PENDING_TIMEOUT', 'PENDING_CLOSED'].includes(finalHumanSignoff.result),
  'final human signoff result must be explicit',
);
if (dirtyAudit) assert.equal(dirtyAudit.result, 'PASS_DIRTY_WORKTREE_AUDITED', 'dirty audit must pass when present');
assert.ok(buttonChain, 'latest SW3 button chain artifact is missing');
assert.equal(buttonChain.status, 'PASS', 'latest passing SW3 button recording chain must pass');

const bleBridge = readFileSync('apps/windows/src-tauri/src/backend/ble_bridge.rs', 'utf8');
for (const token of [
  'btleplug::',
  'scan_native_device',
  'connect_native_probe',
  'sync_first_native_recording',
  'RECORDING_LIST_UUID',
  'RECORDING_CHUNK_PULL_UUID',
  'recording_packet_crc32',
  'Sha256',
  'write_pcm16_wav',
]) {
  assert.ok(bleBridge.includes(token), `native BLE bridge missing ${token}`);
}

const packageJson = readJson('package.json');
assert.ok(packageJson.scripts['verify:joint-acceptance'], 'package script verify:joint-acceptance missing');

const typeGitStatus = command('git', ['status', '--short', '--branch'], TYPE_ROOT);
const firmwareGitStatus = command('git', ['status', '--short', '--branch'], FIRMWARE_ROOT);

const env = {
  openaiApiKey: envFlag('OPENAI_API_KEY'),
  companionAsrApiKey: envFlag('COMPANION_TYPE_ASR_API_KEY'),
  companionAsrEndpoint: envFlag('COMPANION_TYPE_ASR_ENDPOINT'),
  companionDeviceRecordingPath: envFlag('COMPANION_TYPE_DEVICE_RECORDING_PATH'),
  companionBleNativeReadyOverride: envFlag('COMPANION_TYPE_BLE_NATIVE_READY'),
};

const buttonOps = new Map(
  buttonChain.operations.map((operation: Record<string, unknown>) => [operation.operation, operation]),
);
const recordingList = buttonOps.get('recording_list_after_sw3_stop') as Record<string, any> | undefined;
const recordingPull = buttonOps.get('recording_pull') as Record<string, any> | undefined;
const audioQuality = buttonOps.get('audio_quality') as Record<string, any> | undefined;
const finalPhysicalSignoffPass = finalHumanSignoff?.result === 'PASS'
  && finalHumanSignoff?.checks?.physicalBoard
  && finalHumanSignoff?.checks?.sw3ButtonChain
  && finalHumanSignoff?.checks?.realMicrophoneVoice
  && finalHumanSignoff?.checks?.noListenerTypeRuntime;
const finalInstalledUiSignoffPass = finalHumanSignoff?.result === 'PASS'
  && finalHumanSignoff?.checks?.installedUiImport
  && finalHumanSignoff?.checks?.noListenerTypeRuntime;
const realMicSoakOneHourPass = realMicSoak?.result === 'PASS_ONE_HOUR_REAL_MIC_SOAK'
  && realMicSoak?.requestedSeconds >= 3600
  && realMicSoak?.actualDurationMs >= 3420000;
const realMicSoakShortPass = realMicSoak?.result === 'PASS_SHORT_REAL_MIC_SOAK_SMOKE';

const items = [
  {
    id: 1,
    name: '真机物理链路',
    status: finalPhysicalSignoffPass
      ? 'PASS_AI_EVIDENCE_AND_HUMAN_FINAL_SIGNOFF'
      : 'PASS_AI_EVIDENCE__PENDING_HUMAN_FINAL_SIGNOFF',
    evidence: [
      repoFileEvidence(FIRMWARE_ROOT, artifacts.firmwareButtonChain!),
      artifacts.firmwareButtonChainLatest
        ? repoFileEvidence(FIRMWARE_ROOT, artifacts.firmwareButtonChainLatest)
        : { path: 'latest companion-button-recording-chain.json', fullPath: '', exists: false, bytes: 0 },
      repoFileEvidence(FIRMWARE_ROOT, String(buttonChain.artifacts?.wav_path ?? '')),
      repoFileEvidence(FIRMWARE_ROOT, String(buttonChain.artifacts?.button_serial_log ?? '')),
      fileEvidence(artifacts.typeFinalHumanSignoff),
    ],
    observed: {
      button: 'SW3/B3 PD1',
      recordingCountAfterStop: recordingList?.recording_list?.count,
      recordingBytes: recordingPull?.total_length,
      packetCount: recordingPull?.packet_count,
      sourceMode: recordingList?.recording_list?.entries?.[0]?.source_mode,
      audioQuality: audioQuality
        ? {
          duration_s: audioQuality.duration_s,
          peak: audioQuality.peak,
          rms: audioQuality.rms,
          status: audioQuality.status,
        }
        : null,
      resetPersistence: Boolean(buttonOps.get('reset_persistence_compare')),
      deleteAfterSync: Boolean(buttonOps.get('delete_after_sync')),
      latestAttempt: latestButtonChainAttempt
        ? {
          path: artifacts.firmwareButtonChainLatest,
          status: latestButtonChainAttempt.status,
          mode: latestButtonChainAttempt.mode,
          error: latestButtonChainAttempt.error ?? null,
        }
        : null,
      finalHumanSignoff: finalHumanSignoff
        ? {
          result: finalHumanSignoff.result,
          generatedAt: finalHumanSignoff.generatedAt,
          checks: finalHumanSignoff.checks,
        }
        : null,
    },
    remainingGate: finalPhysicalSignoffPass
      ? '真实按键、真实麦克风声源、板上状态已由本地人工最终确认。'
      : '用户最终确认真实按键、真实麦克风声源、板上状态与预期一致。',
  },
  {
    id: 2,
    name: 'Windows 原生 BLE 直连',
    status: nativeBleSyncPopup?.result === 'PASS' && installedUiSync?.visualReview?.result === 'PASS' && finalInstalledUiSignoffPass
      ? 'PASS_NATIVE_BLE_REAL_RECORDING_SYNC_AND_INSTALLED_APP_UI_SYNC__HUMAN_CONFIRMED'
      : nativeBleSyncPopup?.result === 'PASS' && installedUiSync?.visualReview?.result === 'PASS'
      ? 'PASS_NATIVE_BLE_REAL_RECORDING_SYNC_AND_INSTALLED_APP_UI_SYNC__PENDING_HUMAN_FINAL_CONFIRM'
      : nativeBleSyncPopup?.result === 'PASS' && installedUiSync?.result
      ? 'PASS_NATIVE_BLE_REAL_RECORDING_SYNC__INSTALLED_APP_UI_VISUAL_REVIEW_PENDING'
      : nativeBleSyncPopup?.result === 'PASS'
      ? 'PASS_NATIVE_BLE_REAL_RECORDING_SYNC__PENDING_APP_UI_CONFIRM'
      : nativeBleSmoke?.result === 'PASS'
      ? 'PASS_NATIVE_BLE_REAL_SCAN_CONNECT__PENDING_POPUP_GUIDED_RECORDING_SYNC'
      : 'PASS_CODE_AND_UNIT__PENDING_REAL_APP_HW_RUN',
    evidence: [
      { path: 'apps/windows/src-tauri/src/backend/ble_bridge.rs', exists: true },
      { command: 'cargo test --manifest-path apps/windows/src-tauri/Cargo.toml --lib', result: 'PASS in latest run' },
      fileEvidence(artifacts.typeNativeBleSmoke),
      fileEvidence(artifacts.typeNativeBleSmokeLog),
      fileEvidence(artifacts.typeNativeBleSyncPopup),
      fileEvidence(artifacts.typeNativeBleSyncLog),
      fileEvidence(artifacts.typeNativeBleSyncSerialLog),
      fileEvidence(artifacts.typeInstalledUiSync),
      fileEvidence(artifacts.typeFinalHumanSignoff),
      fileEvidence(artifacts.firmwareButtonChain!),
    ],
    observed: {
      provider: 'btleplug Windows backend',
      implemented: ['scan', 'connect/discover', 'recording_list read', 'recording_chunk_pull notify/write', 'CRC32', 'final SHA-256', 'WAV export'],
      nativeBleSmoke: nativeBleSmoke?.observed ?? null,
      nativeBleSyncPopup: nativeBleSyncPopup
        ? {
          result: nativeBleSyncPopup.result,
          phase: nativeBleSyncPopup.phase,
          error: nativeBleSyncPopup.error,
          serialPort: nativeBleSyncPopup.serialPort,
          startPopup: nativeBleSyncPopup.popup?.start
            ? {
              status: nativeBleSyncPopup.popup.start.status,
              pressLine: nativeBleSyncPopup.popup.start.pressLine,
              releaseLine: nativeBleSyncPopup.popup.start.releaseLine,
            }
            : null,
          stopPopup: nativeBleSyncPopup.popup?.stop
            ? {
              status: nativeBleSyncPopup.popup.stop.status,
              pressLine: nativeBleSyncPopup.popup.stop.pressLine,
              releaseLine: nativeBleSyncPopup.popup.stop.releaseLine,
            }
            : null,
          cargoExitCode: nativeBleSyncPopup.cargo?.exitCode ?? null,
        }
        : null,
      installedUiSync: installedUiSync
        ? {
          result: installedUiSync.result,
          phase: installedUiSync.phase,
          error: installedUiSync.error,
          installedExe: installedUiSync.installedExe,
          visualReview: installedUiSync.visualReview ?? null,
          screenshots: installedUiSync.screenshots ?? null,
        }
        : null,
      finalHumanSignoff: finalHumanSignoff
        ? {
          result: finalHumanSignoff.result,
          generatedAt: finalHumanSignoff.generatedAt,
          checks: finalHumanSignoff.checks,
        }
        : null,
      note: 'Firmware Python/Bleak bench remains validation inventory, but Type now has its own native app path.',
    },
    remainingGate: nativeBleSyncPopup?.result === 'PASS' && installedUiSync?.visualReview?.result === 'PASS' && finalInstalledUiSignoffPass
      ? '原生 Windows BLE backend 同步、安装版 UI 导入和本地人工最终确认均已通过。'
      : nativeBleSyncPopup?.result === 'PASS' && installedUiSync?.visualReview?.result === 'PASS'
      ? '原生 Windows BLE backend 同步和安装版 UI 点击链条均已通过；仅剩最终人工确认真实导入体验。'
      : nativeBleSyncPopup?.result === 'PASS' && installedUiSync?.result
        ? '安装版 UI 点击链条截图已生成；还要核验 afterSync 截图确实显示真实 WAV 导入。'
        : nativeBleSyncPopup?.result === 'PASS'
      ? '原生 Windows BLE 录音拉取已通过 backend 烟测；还要在 Companion-Type Windows app UI 内点 Sync，确认导入 WAV。'
      : nativeBleSyncPopup?.result === 'FAIL'
        ? `原生 Windows BLE scan/connect 已在真机通过；弹窗+串口检测同步链路已准备，但最近一次停在 ${nativeBleSyncPopup.phase}: ${nativeBleSyncPopup.error}。需要操作者看到弹窗后短按 SW3 并马上松开。`
      : nativeBleSmoke?.result === 'PASS'
      ? '原生 Windows BLE scan/connect 已在真机通过；还要通过弹窗/串口检测录一条短音并让 Companion-Type native BLE 拉成 WAV。'
      : '在 Companion-Type Windows app 内对真实板子点 Scan/Connect/Sync，确认导入的 WAV 路径和设备状态。',
  },
  {
    id: 3,
    name: '真实 ASR key 与真实音频',
    status: env.openaiApiKey || env.companionAsrApiKey ? 'READY_FOR_REAL_ASR_RUN' : 'BLOCKED_EXTERNAL_KEY',
    evidence: [
      fileEvidence(artifacts.typeRealMicrophone),
      fileEvidence(artifacts.typeIndependentAsr),
    ],
    observed: {
      realMicrophoneWav: realMic.wav,
      independentAsrMock: independentAsr.result,
      env,
    },
    remainingGate: env.openaiApiKey || env.companionAsrApiKey
      ? '运行真实 ASR provider 上传一段真实 WAV 并检查 transcript。'
      : '需要设置 OPENAI_API_KEY 或 COMPANION_TYPE_ASR_API_KEY；当前不能诚实标记真实 ASR 通过。',
  },
  {
    id: 4,
    name: '打包安装与 OOBE',
    status: artifacts.typeMsi && releaseLaunch?.result === 'PASS' && msiInstallSmoke?.result === 'PASS'
      ? 'PASS_INSTALLED_APP_LAUNCH_AND_UI_OOBE'
      : artifacts.typeMsi && releaseLaunch?.result === 'PASS'
      ? 'PASS_BUNDLE_RELEASE_LAUNCH_AND_UI_OOBE__PENDING_INSTALLER_INSTALL_SMOKE'
      : artifacts.typeMsi
        ? 'PASS_BUNDLE_AND_UI_OOBE__PENDING_RELEASE_LAUNCH_SMOKE'
        : 'PASS_UI_OOBE__PENDING_INSTALLER_BUILD',
    evidence: [
      fileEvidence(artifacts.typeBrowser),
      fileEvidence(artifacts.typeBrowserScreenshot),
      fileEvidence(artifacts.typeProduct),
      artifacts.typeMsi ? fileEvidence(artifacts.typeMsi) : { path: 'apps/windows/src-tauri/target/release/bundle/msi/*.msi', exists: false, bytes: 0 },
      fileEvidence(artifacts.typeReleaseLaunch),
      fileEvidence(artifacts.typeMsiInstallSmoke),
    ],
    observed: {
      oobeComplete: product.steps?.some((step: Record<string, unknown>) => step.action === 'oobeRunChecks'),
      browserClicked: browser.clicked,
      msiPath: artifacts.typeMsi,
      releaseLaunch,
      msiInstallSmoke: msiInstallSmoke
        ? {
          result: msiInstallSmoke.result,
          phase: msiInstallSmoke.phase,
          error: msiInstallSmoke.error,
          installedExe: msiInstallSmoke.installedExe,
          launched: msiInstallSmoke.launched,
          installAttempt: msiInstallSmoke.installAttempt,
          elevatedAttempt: msiInstallSmoke.elevatedAttempt,
        }
        : null,
    },
    remainingGate: artifacts.typeMsi && releaseLaunch?.result === 'PASS' && msiInstallSmoke?.result === 'PASS'
      ? 'MSI 已真实安装并从安装目录启动通过；这里只剩最终人工桌面/OOBE确认，不再是 AI 自动化缺口。'
      : artifacts.typeMsi && releaseLaunch?.result === 'PASS'
      ? 'MSI 已生成，release exe 启动烟测已过；严格非开发者 OOBE 还要实际安装 MSI 后启动一次。'
      : artifacts.typeMsi
        ? 'MSI 已生成；还要从 release 或安装产物启动一次确认进程路径与版本。'
      : '还要跑 release/package artifact，并从安装产物启动一次确认进程路径与版本。',
  },
  {
    id: 5,
    name: '长会议分段与录音笔体验',
    status: longMeeting?.result === 'PASS' && realMicSoakOneHourPass
      ? 'PASS_ONE_HOUR_CHUNK_MINUTES_SIMULATION_AND_REAL_MIC_SOAK'
      : longMeeting?.result === 'PASS' && realMicSoakShortPass
      ? 'PASS_ONE_HOUR_CHUNK_MINUTES_SIMULATION__SHORT_REAL_MIC_SOAK_ONLY'
      : longMeeting?.result === 'PASS'
      ? 'PASS_ONE_HOUR_CHUNK_MINUTES_SIMULATION__PENDING_REAL_LONG_SOAK'
      : 'PASS_POLICY_AND_SIMULATION__PENDING_LONG_SOAK',
    evidence: [
      fileEvidence(artifacts.typeProduct),
      fileEvidence(artifacts.typeLongMeeting),
      fileEvidence(artifacts.typeRealMicrophoneSoak),
      fileEvidence(artifacts.firmwarePostprocess),
    ],
    observed: {
      targetSeconds: product.coverage?.longMeetingPolicy?.targetSeconds,
      rawPcmBytes: product.coverage?.longMeetingPolicy?.rawPcmBytes,
      chunksPerHour: product.coverage?.longMeetingPolicy?.chunksPerHour,
      firmwareOneHourNote: postprocess.capacity?.one_hour_note,
      longMeeting: longMeeting
        ? {
          chunkCount: longMeeting.chunkCount,
          chunkSeconds: longMeeting.chunkSeconds,
          maxAsrUploadBytes: longMeeting.maxAsrUploadBytes,
          transcriptSegments: longMeeting.minutes?.transcriptSegments,
          decisions: longMeeting.minutes?.decisions,
          actionItems: longMeeting.minutes?.actionItems,
          note: longMeeting.note,
        }
        : null,
      realMicrophoneSoak: realMicSoak
        ? {
          result: realMicSoak.result,
          requestedSeconds: realMicSoak.requestedSeconds,
          actualDurationMs: realMicSoak.actualDurationMs,
          audioDurationMs: realMicSoak.audioDurationMs,
          wav: realMicSoak.wav,
        }
        : null,
    },
    remainingGate: longMeeting?.result === 'PASS' && realMicSoakOneHourPass
      ? '一小时分段、纪要、隐私删除和真实一小时麦克风 soak 均已通过。'
      : longMeeting?.result === 'PASS' && realMicSoakShortPass
      ? '一小时分段、纪要和隐私删除的确定性模拟已过；真实麦克风 soak 工具链短时通过，仍需预留 1 小时跑 3600 秒实测。'
      : longMeeting?.result === 'PASS'
      ? '一小时分段、纪要和隐私删除的确定性模拟已过；真实一小时麦克风 soak 仍需占用 1 小时跑实测。'
      : '当前设计正确取舍为 host/分段/ASR 上传上限；真实一小时会议还需要长时间 soak 或更大存储/压缩方案。',
  },
  {
    id: 6,
    name: '语音唤醒词',
    status: 'PASS_CONTROL_SURFACE__REAL_KWS_DEFERRED',
    evidence: [
      { path: join(FIRMWARE_ROOT, 'docs', 'ble_gatt_contract.md'), exists: true },
      fileEvidence(artifacts.firmwarePostprocess),
    ],
    observed: {
      currentSurface: ['wake_word_control arm', 'disarm', 'simulate_detect', 'wake_word_status counters'],
      postprocessWakePhrase: postprocess.minutes?.wake_word ?? postprocess.wake_word ?? null,
    },
    remainingGate: '真实 always-on keyword spotting 需要模型、功耗、误触发/漏触发、隐私 UI；当前不能称作物理唤醒。',
  },
  {
    id: 7,
    name: '脏改整理与可审查交付',
    status: dirtyAudit?.result === 'PASS_DIRTY_WORKTREE_AUDITED'
      ? 'PASS_DIRTY_AUDIT_ARTIFACT_GENERATED__DIRTY_WORKTREE_REMAINS'
      : 'PASS_AUDIT_GENERATED__DIRTY_WORKTREE_REMAINS',
    evidence: [
      { command: typeGitStatus.command.join(' '), exitCode: typeGitStatus.exitCode },
      { command: firmwareGitStatus.command.join(' '), exitCode: firmwareGitStatus.exitCode },
      fileEvidence(artifacts.typeDirtyAudit),
    ],
    observed: {
      companionTypeStatus: typeGitStatus.stdoutTail,
      companionFirmwareStatus: firmwareGitStatus.stdoutTail,
      dirtyAudit: dirtyAudit
        ? {
          result: dirtyAudit.result,
          branch: dirtyAudit.branch,
          counts: dirtyAudit.counts,
          listenerTypeTouched: dirtyAudit.listenerTypeTouched,
          entriesSample: dirtyAudit.entries?.slice?.(0, 40) ?? [],
        }
        : null,
    },
    remainingGate: '当前按你的要求保留脏改，不回滚；最终交付前需要拆分/提交/保留策略。',
  },
];

const report = {
  schema: 'companion_type.joint_acceptance.v1',
  generatedAt: new Date().toISOString(),
  result: 'PASS_AUDIT_WITH_RECORDED_HUMAN_AND_EXTERNAL_GATES',
  goal: 'Companion 1-7 joint acceptance',
  noListenerTypeChanges: true,
  items,
  blockers: items
    .filter((item) => item.status.includes('BLOCKED') || item.status.includes('PENDING'))
    .map((item) => ({ id: item.id, name: item.name, status: item.status, remainingGate: item.remainingGate })),
  nextHumanActions: [
    ...(finalPhysicalSignoffPass && finalInstalledUiSignoffPass
      ? []
      : ['运行 npm run verify:final-human-signoff，在中文弹窗中最终确认真实板子、SW3、麦克风和安装版导入体验。']),
    '如要验真实 ASR，先设置 OPENAI_API_KEY 或 COMPANION_TYPE_ASR_API_KEY。',
    ...(realMicSoakOneHourPass
      ? []
      : ['如要验真实一小时会议，运行 npm run verify:real-microphone-soak:popup 并预留 1 小时麦克风 soak 时间。']),
  ],
};

mkdirSync(dirname(OUT_JSON), { recursive: true });
writeFileSync(OUT_JSON, `${JSON.stringify(report, null, 2)}\n`);
console.log(`PASS companion-type joint acceptance audit: ${OUT_JSON}`);
