import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const files = {
  lib: 'apps/windows/src-tauri/src/lib.rs',
  commands: 'apps/windows/src-tauri/src/commands.rs',
  coordinator: 'apps/windows/src-tauri/src/coordinator.rs',
  backend: 'apps/windows/src-tauri/src/backend/mod.rs',
  hostRecording: 'apps/windows/src-tauri/src/backend/host_recording.rs',
  transcription: 'apps/windows/src-tauri/src/backend/transcription.rs',
  bleBridge: 'apps/windows/src-tauri/src/backend/ble_bridge.rs',
  privacy: 'apps/windows/src-tauri/src/backend/privacy.rs',
  contract: 'apps/windows/src-tauri/src/companion_v1.rs',
  syncPopup: 'tools/run_companion_type_ble_sync_popup.ps1',
};

for (const [name, path] of Object.entries(files)) {
  assert.ok(existsSync(path), `${name} file is missing at ${path}`);
}

const lib = readFileSync(files.lib, 'utf8');
const commands = readFileSync(files.commands, 'utf8');
const coordinator = readFileSync(files.coordinator, 'utf8');
const backend = readFileSync(files.backend, 'utf8');
const hostRecording = readFileSync(files.hostRecording, 'utf8');
const transcription = readFileSync(files.transcription, 'utf8');
const bleBridge = readFileSync(files.bleBridge, 'utf8');
const privacy = readFileSync(files.privacy, 'utf8');
const contract = readFileSync(files.contract, 'utf8');
const syncPopup = readFileSync(files.syncPopup, 'utf8');
const cargo = readFileSync('apps/windows/src-tauri/Cargo.toml', 'utf8');

assert.match(lib, /mod backend;/);
assert.match(lib, /mod commands;/);
assert.match(lib, /mod companion_v1;/);
assert.match(lib, /mod coordinator;/);
assert.match(lib, /CompanionCoordinator::new_fixture\(\)/);
assert.match(lib, /\.manage\(coordinator\)/);
assert.doesNotMatch(lib, /#\[tauri::command\]/, 'lib.rs should not own IPC commands');

for (const commandName of [
  'get_companion_v1_snapshot',
  'apply_companion_v1_control',
  'get_companion_backend_capabilities',
  'get_companion_ble_bridge_status',
]) {
  assert.match(commands, new RegExp(`pub (?:async )?fn ${commandName}`));
  assert.match(lib, new RegExp(`commands::${commandName}`));
}
assert.match(commands, /spawn_blocking/);

assert.match(coordinator, /pub struct CompanionCoordinator/);
assert.match(coordinator, /backend: Arc<dyn CompanionBackend>/);
assert.match(coordinator, /pub fn snapshot/);
assert.match(coordinator, /pub fn apply_control/);
assert.match(coordinator, /pub fn backend_capabilities/);
assert.match(coordinator, /pub fn ble_bridge_status/);

assert.match(backend, /pub trait CompanionBackend/);
assert.match(backend, /pub struct FixtureCompanionBackend/);
assert.match(backend, /mod host_recording;/);
assert.match(backend, /mod transcription;/);
assert.match(backend, /mod ble_bridge;/);
assert.match(backend, /mod privacy;/);
assert.match(backend, /host_recording\.start/);
assert.match(backend, /host_recording\.stop/);
assert.match(backend, /transcription\.transcribe_audio/);
assert.match(backend, /privacy\.erase_selected_audio/);
for (const service of ['device_control', 'recording', 'transcription', 'minutes', 'export']) {
  assert.match(backend, new RegExp(`pub ${service}: CompanionServiceBoundary`));
}
for (const token of [
  'host-microphone-wav',
  'companion-type.hybrid-host',
  'companion-type-transcription',
  'fixture-minutes',
  'fixture-markdown-export',
]) {
  assert.match(backend, new RegExp(token));
}

assert.match(hostRecording, /cpal::/);
assert.match(hostRecording, /TARGET_SAMPLE_RATE: u32 = 16_000/);
assert.match(hostRecording, /write_synthetic_wav/);
assert.match(transcription, /COMPANION_TYPE_TRANSCRIPT_TEXT/);
assert.match(transcription, /COMPANION_TYPE_ASR_COMMAND/);
assert.match(transcription, /COMPANION_TYPE_ASR_ENDPOINT/);
assert.match(transcription, /gpt-4o-transcribe/);
assert.match(transcription, /multipart::Form/);
assert.match(transcription, /listener-type/);
assert.match(bleBridge, /CompanionBleBridgeStatus/);
assert.match(bleBridge, /CompanionBleOperation/);
assert.match(bleBridge, /companion-type-windows-ble/);
assert.match(bleBridge, /btleplug::/);
assert.match(bleBridge, /RECORDING_LIST_UUID/);
assert.match(bleBridge, /RECORDING_CHUNK_PULL_UUID/);
assert.match(bleBridge, /scan_native_device/);
assert.match(bleBridge, /connect_native_probe/);
assert.match(bleBridge, /sync_first_native_recording/);
assert.match(bleBridge, /parse_recording_list/);
assert.match(bleBridge, /parse_recording_chunk/);
assert.match(bleBridge, /recording_packet_crc32/);
assert.match(bleBridge, /Sha256/);
assert.match(bleBridge, /write_pcm16_wav/);
assert.match(bleBridge, /real_native_ble_scan_connect_smoke/);
assert.match(bleBridge, /real_native_ble_recording_sync_smoke/);
assert.match(bleBridge, /companion_ble_real_bench\.py/);
assert.match(bleBridge, /companion_flash_recording_chain\.py/);
assert.match(privacy, /PrivacyManager/);
assert.match(privacy, /erase_selected_audio/);
assert.match(privacy, /is_owned_recording_path/);

assert.match(contract, /pub struct CompanionV1Snapshot/);
assert.match(contract, /pub struct CompanionV1ControlRequest/);
assert.match(contract, /pub fn apply_fixture_control/);
assert.match(contract, /MeetingTranscribeAudio/);
assert.match(contract, /DeviceSyncRecordings/);
assert.match(contract, /PrivacyEraseAudio/);
assert.match(contract, /OobeRunChecks/);

assert.match(syncPopup, /System\.Windows\.Forms/);
assert.match(syncPopup, /SW3\/B3/);
assert.match(syncPopup, /ReadExisting/);
assert.match(syncPopup, /companion-type-native-ble-sync-popup\.json/);
assert.match(syncPopup, /real_native_ble_recording_sync_smoke/);

for (const crate of ['btleplug', 'crc32fast', 'futures', 'sha2', 'tokio', 'uuid']) {
  assert.match(cargo, new RegExp(`^${crate}\\s*=`, 'm'), `Cargo.toml missing ${crate}`);
}

console.log('PASS companion-type backend shape: ASR, native BLE/GATT, OOBE, privacy boundaries are present');
