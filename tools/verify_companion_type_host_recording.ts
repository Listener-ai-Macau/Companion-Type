import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const cargoToml = 'apps/windows/src-tauri/Cargo.toml';
const hostRecording = 'apps/windows/src-tauri/src/backend/host_recording.rs';
const backend = 'apps/windows/src-tauri/src/backend/mod.rs';

for (const path of [cargoToml, hostRecording, backend]) {
  assert.ok(existsSync(path), `${path} is missing`);
}

assert.match(readFileSync(cargoToml, 'utf8'), /^cpal = /m);
const hostRecordingSource = readFileSync(hostRecording, 'utf8');
assert.match(hostRecordingSource, /struct HostRecordingManager/);
assert.match(hostRecordingSource, /fn write_synthetic_wav/);
assert.match(hostRecordingSource, /TARGET_SAMPLE_RATE: u32 = 16_000/);
assert.match(hostRecordingSource, /build_input_stream/);

const backendSource = readFileSync(backend, 'utf8');
assert.match(backendSource, /host_recording\.start/);
assert.match(backendSource, /host_recording\.stop/);
assert.match(backendSource, /audio_path = Some/);

const result = spawnSync(
  'cargo',
  [
    'test',
    '--manifest-path',
    'apps/windows/src-tauri/Cargo.toml',
    '--lib',
    'host_recording',
    '--',
    '--nocapture',
  ],
  {
    encoding: 'utf8',
    env: {
      ...process.env,
      COMPANION_TYPE_HOST_RECORDING_MODE: 'synthetic',
    },
  },
);

if (result.status !== 0) {
  process.stdout.write(result.stdout);
  process.stderr.write(result.stderr);
}
assert.equal(result.status, 0);
assert.match(result.stdout + result.stderr, /synthetic_recording_writes_valid_wav|manager_synthetic_mode_creates_session_file_on_stop/);

console.log('PASS companion-type host recording backend: cpal path is wired and synthetic WAV tests passed');
