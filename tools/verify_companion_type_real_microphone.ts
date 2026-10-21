import assert from 'node:assert/strict';
import { mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { spawnSync } from 'node:child_process';

const outJson = 'docs/validation/companion-type-real-microphone.json';

const result = spawnSync(
  'cargo',
  [
    'test',
    '--manifest-path',
    'apps/windows/src-tauri/Cargo.toml',
    '--lib',
    'real_microphone_recording_smoke',
    '--',
    '--nocapture',
  ],
  {
    encoding: 'utf8',
    env: {
      ...process.env,
      COMPANION_TYPE_REAL_MIC_ACCEPTANCE: '1',
      COMPANION_TYPE_HOST_RECORDING_MODE: 'real',
    },
  },
);

const combined = `${result.stdout}\n${result.stderr}`;
if (result.status !== 0) {
  process.stdout.write(result.stdout);
  process.stderr.write(result.stderr);
}
assert.equal(result.status, 0, 'real microphone acceptance test failed');

const wavMatch = combined.match(/real_microphone_wav=(.+\.wav)/);
assert.ok(wavMatch, 'real microphone test did not report a WAV path');
const wavPath = wavMatch[1].trim();
const wav = readFileSync(wavPath);
assert.equal(wav.subarray(0, 4).toString('ascii'), 'RIFF');
assert.equal(wav.subarray(8, 12).toString('ascii'), 'WAVE');
assert.equal(wav.subarray(36, 40).toString('ascii'), 'data');
const channels = wav.readUInt16LE(22);
const sampleRate = wav.readUInt32LE(24);
const dataBytes = wav.readUInt32LE(40);
assert.equal(channels, 1);
assert.equal(sampleRate, 16000);
assert.ok(dataBytes > 0, 'real microphone WAV has no sample data');

const artifact = {
  schema: 'companion_type.real_microphone_acceptance.v1',
  generatedAt: new Date().toISOString(),
  result: 'PASS',
  command: 'cargo test --manifest-path apps/windows/src-tauri/Cargo.toml --lib real_microphone_recording_smoke -- --nocapture',
  wav: {
    path: wavPath,
    bytes: statSync(wavPath).size,
    channels,
    sampleRate,
    dataBytes,
  },
};

mkdirSync(dirname(outJson), { recursive: true });
writeFileSync(outJson, `${JSON.stringify(artifact, null, 2)}\n`);
console.log(`PASS companion-type real microphone acceptance: ${outJson}`);
