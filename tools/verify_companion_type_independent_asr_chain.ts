import assert from 'node:assert/strict';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { spawnSync } from 'node:child_process';

const OUT_JSON = 'docs/validation/companion-type-independent-asr-chain.json';
const rustManifest = 'apps/windows/src-tauri/Cargo.toml';
const transcriptionSource = 'apps/windows/src-tauri/src/backend/transcription.rs';

function run(command: string, args: string[]) {
  const startedAt = new Date().toISOString();
  const result = spawnSync(command, args, {
    cwd: process.cwd(),
    encoding: 'utf8',
    env: {
      ...process.env,
      COMPANION_TYPE_HOST_RECORDING_MODE: 'synthetic',
    },
  });
  return {
    command: [command, ...args],
    startedAt,
    finishedAt: new Date().toISOString(),
    exitCode: result.status,
    stdoutTail: result.stdout.split(/\r?\n/).slice(-40).join('\n'),
    stderrTail: result.stderr.split(/\r?\n/).slice(-40).join('\n'),
  };
}

const transcription = readFileSync(transcriptionSource, 'utf8');
assert.match(transcription, /COMPANION_TYPE_TRANSCRIPT_TEXT/);
assert.match(transcription, /COMPANION_TYPE_ASR_COMMAND/);
assert.match(transcription, /COMPANION_TYPE_ASR_ENDPOINT/);
assert.match(transcription, /companion-type-openai-compatible-asr/);
assert.match(transcription, /Companion-Type ASR command must not call listener-type/);
assert.doesNotMatch(transcription, /Command::new\([^)]*listener-type/i);

const cargoBackend = run('cargo', [
  'test',
  '--manifest-path',
  rustManifest,
  '--lib',
  'backend_transcribes_audio_with_companion_type_sidecar_provider',
  '--',
  '--nocapture',
]);
assert.equal(cargoBackend.exitCode, 0, `${cargoBackend.command.join(' ')} failed\n${cargoBackend.stdoutTail}\n${cargoBackend.stderrTail}`);

const cargoSidecar = run('cargo', [
  'test',
  '--manifest-path',
  rustManifest,
  '--lib',
  'sidecar_transcript_is_loaded_without_listener_type',
  '--',
  '--nocapture',
]);
assert.equal(cargoSidecar.exitCode, 0, `${cargoSidecar.command.join(' ')} failed\n${cargoSidecar.stdoutTail}\n${cargoSidecar.stderrTail}`);

const cargoGuard = run('cargo', [
  'test',
  '--manifest-path',
  rustManifest,
  '--lib',
  'listener_type_command_is_rejected',
  '--',
  '--nocapture',
]);
assert.equal(cargoGuard.exitCode, 0, `${cargoGuard.command.join(' ')} failed\n${cargoGuard.stdoutTail}\n${cargoGuard.stderrTail}`);

const cargoOpenAiCompatible = run('cargo', [
  'test',
  '--manifest-path',
  rustManifest,
  '--lib',
  'openai_compatible_provider_posts_audio_multipart',
  '--',
  '--nocapture',
]);
assert.equal(cargoOpenAiCompatible.exitCode, 0, `${cargoOpenAiCompatible.command.join(' ')} failed\n${cargoOpenAiCompatible.stdoutTail}\n${cargoOpenAiCompatible.stderrTail}`);

const core = run('node', ['--experimental-strip-types', 'packages/core/src/companionV1.test.ts']);
assert.equal(core.exitCode, 0, `${core.command.join(' ')} failed\n${core.stdoutTail}\n${core.stderrTail}`);

const artifact = {
  schema: 'companion_type.independent_asr_chain.v1',
  generatedAt: new Date().toISOString(),
  result: 'PASS',
  listenerTypeExecutableInvoked: false,
  independence: {
    movedBoundary: 'Companion-Type owns meetingTranscribeAudio and backend/transcription.rs',
    providers: [
      'COMPANION_TYPE_TRANSCRIPT_TEXT',
      'audio .transcript.txt sidecar',
      'COMPANION_TYPE_ASR_ENDPOINT OpenAI-compatible multipart provider',
      'COMPANION_TYPE_ASR_COMMAND generic command',
    ],
    forbiddenRuntime: 'listener-type executable is rejected by Companion-Type ASR command guard',
  },
  commands: [cargoBackend, cargoSidecar, cargoGuard, cargoOpenAiCompatible, core],
};

mkdirSync(dirname(OUT_JSON), { recursive: true });
writeFileSync(OUT_JSON, `${JSON.stringify(artifact, null, 2)}\n`);
console.log(`PASS companion-type independent ASR chain: ${OUT_JSON}`);
