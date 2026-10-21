import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';

const OUT_JSON = 'docs/validation/companion-type-real-microphone-soak.json';
const TARGET_SAMPLE_RATE = 16000;
const TARGET_CHANNELS = 1;
const TARGET_BITS_PER_SAMPLE = 16;
const ONE_HOUR_SECONDS = 3600;

function requestedSeconds() {
  const secondsFlag = process.argv.findIndex((arg) => arg === '--seconds');
  const raw = secondsFlag >= 0
    ? process.argv[secondsFlag + 1]
    : process.env.COMPANION_TYPE_REAL_MIC_SOAK_SECONDS ?? String(ONE_HOUR_SECONDS);
  const seconds = Number.parseInt(raw ?? '', 10);
  assert.ok(Number.isSafeInteger(seconds) && seconds > 0, 'soak seconds must be a positive integer');
  return seconds;
}

function stdoutTail(value: string) {
  return value.split(/\r?\n/).slice(-80).join('\n');
}

function parseRequired(pattern: RegExp, value: string, label: string) {
  const match = value.match(pattern);
  assert.ok(match?.[1], `real microphone soak did not report ${label}`);
  return match[1].trim();
}

const seconds = requestedSeconds();
const command = [
  'cargo',
  'test',
  '--manifest-path',
  'apps/windows/src-tauri/Cargo.toml',
  '--lib',
  'real_microphone_recording_soak',
  '--',
  '--nocapture',
];

const result = spawnSync(command[0], command.slice(1), {
  encoding: 'utf8',
  env: {
    ...process.env,
    COMPANION_TYPE_REAL_MIC_SOAK_ACCEPTANCE: '1',
    COMPANION_TYPE_REAL_MIC_SOAK_SECONDS: String(seconds),
    COMPANION_TYPE_HOST_RECORDING_MODE: 'real',
  },
});

const combined = `${result.stdout}\n${result.stderr}`;
if (result.status !== 0) {
  process.stdout.write(result.stdout);
  process.stderr.write(result.stderr);
}
assert.equal(result.status, 0, 'real microphone soak test failed');

const wavPath = parseRequired(/real_microphone_soak_wav=(.+\.wav)/, combined, 'WAV path');
const mode = parseRequired(/real_microphone_soak_mode=(.+)/, combined, 'recording mode');
const actualDurationMs = Number.parseInt(
  parseRequired(/real_microphone_soak_duration_ms=(\d+)/, combined, 'duration'),
  10,
);
const rustReportedBytes = Number.parseInt(
  parseRequired(/real_microphone_soak_bytes=(\d+)/, combined, 'byte count'),
  10,
);

assert.equal(mode, 'host-microphone', 'soak must use the real host microphone backend');
const wav = readFileSync(wavPath);
assert.equal(wav.subarray(0, 4).toString('ascii'), 'RIFF');
assert.equal(wav.subarray(8, 12).toString('ascii'), 'WAVE');
assert.equal(wav.subarray(36, 40).toString('ascii'), 'data');
const channels = wav.readUInt16LE(22);
const sampleRate = wav.readUInt32LE(24);
const bitsPerSample = wav.readUInt16LE(34);
const dataBytes = wav.readUInt32LE(40);
assert.equal(channels, TARGET_CHANNELS);
assert.equal(sampleRate, TARGET_SAMPLE_RATE);
assert.equal(bitsPerSample, TARGET_BITS_PER_SAMPLE);
assert.ok(dataBytes > 0, 'real microphone soak WAV has no sample data');

const byteRate = sampleRate * channels * bitsPerSample / 8;
const audioDurationMs = Math.floor((dataBytes / byteRate) * 1000);
const minimumActualDurationMs = Math.floor(seconds * 1000 * 0.95);
const minimumAudioDurationMs = Math.floor(seconds * 1000 * (seconds >= ONE_HOUR_SECONDS ? 0.85 : 0.35));
assert.ok(
  actualDurationMs >= minimumActualDurationMs,
  `soak elapsed time ${actualDurationMs}ms is shorter than expected ${minimumActualDurationMs}ms`,
);
assert.ok(
  audioDurationMs >= minimumAudioDurationMs,
  `captured audio duration ${audioDurationMs}ms is shorter than expected ${minimumAudioDurationMs}ms`,
);

const artifact = {
  schema: 'companion_type.real_microphone_soak.v1',
  generatedAt: new Date().toISOString(),
  result: seconds >= ONE_HOUR_SECONDS
    ? 'PASS_ONE_HOUR_REAL_MIC_SOAK'
    : 'PASS_SHORT_REAL_MIC_SOAK_SMOKE',
  command: command.join(' '),
  requestedSeconds: seconds,
  oneHourThresholdSeconds: ONE_HOUR_SECONDS,
  mode,
  actualDurationMs,
  audioDurationMs,
  minimumActualDurationMs,
  minimumAudioDurationMs,
  wav: {
    path: wavPath,
    bytes: statSync(wavPath).size,
    rustReportedBytes,
    channels,
    sampleRate,
    bitsPerSample,
    dataBytes,
  },
  stdoutTail: stdoutTail(result.stdout),
  stderrTail: stdoutTail(result.stderr),
};

mkdirSync(dirname(OUT_JSON), { recursive: true });
writeFileSync(OUT_JSON, `${JSON.stringify(artifact, null, 2)}\n`);
console.log(`PASS companion-type real microphone soak: ${OUT_JSON}`);
