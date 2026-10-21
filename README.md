# Companion Type

Companion Type is the standalone host app for Companion hardware.

It keeps Companion-specific controls out of Listener Type and shares one V1 protocol model across:

- `apps/windows`: Tauri Windows desktop shell.
- `apps/mobile`: reserved mobile shell. Native mobile framework is intentionally deferred until the team-provided framework lands.
- `packages/core`: Companion V1 GATT boundary, fixture state, control payloads, and tests.
- `packages/ui`: reusable Companion dashboard UI.

## Host Recording Flow

Companion Type now owns the user-facing meeting flow:

- scan/connect/sync Companion device state through the Companion-Type device boundary;
- start/stop a meeting session from the host UI;
- keep STM32 flash as a short raw-audio cache, currently modeled as a 60 second device cache;
- treat one hour meetings as host-owned recordings, not firmware-owned raw flash storage;
- model long meetings as 5 minute host WAV chunks, with a one hour raw PCM estimate of 115.2 MB;
- transcribe captured audio through Companion-Type owned providers;
- keep manual transcript import as an override path;
- generate summary, decisions, action items, questions, keywords, and Markdown;
- export the generated Markdown from the app state;
- erase selected audio, selected transcript/minutes, or all local meeting state.

The browser/mobile shells use deterministic fixture state. The Windows Tauri shell uses the same `CompanionV1Snapshot` and `CompanionV1ControlRequest` contract, with real host WAV recording, Companion-Type owned transcription providers, conservative local audio deletion, and a Companion-Type device boundary.

## Backend Shape

The Windows Tauri backend uses a Type-style separation pattern:

- `apps/windows/src-tauri/src/lib.rs`: app assembly only.
- `apps/windows/src-tauri/src/commands.rs`: IPC command surface for React.
- `apps/windows/src-tauri/src/coordinator.rs`: single owner of Companion host workflow state.
- `apps/windows/src-tauri/src/backend/mod.rs`: replaceable backend boundary.
- `apps/windows/src-tauri/src/companion_v1.rs`: Companion V1 contract and fixture state transitions.

The active backend is still `FixtureCompanionBackend`, but it now exposes separate service boundaries for device control, host recording, Companion-Type transcription, minutes generation, and Markdown export. The device-control bridge now has a Windows-native BLE path behind the same UI contract, while the deterministic state reducer keeps browser/mobile validation repeatable.

The backend now has three real host-side boundaries:

- `backend/host_recording.rs`: starts host microphone capture on `meetingStart`, writes 16 kHz mono WAV, and writes the WAV path back to the selected session on `meetingStop`/`meetingFinalize`. Automated tests force synthetic WAV mode so validation does not require microphone permissions.
- `backend/transcription.rs`: owns the `meetingTranscribeAudio` path. It can read `COMPANION_TYPE_TRANSCRIPT_TEXT`, use a sibling `*.transcript.txt` sidecar for deterministic validation, call an OpenAI-compatible multipart ASR endpoint with `COMPANION_TYPE_ASR_ENDPOINT` plus `COMPANION_TYPE_ASR_API_KEY`/`OPENAI_API_KEY`, or run a generic `COMPANION_TYPE_ASR_COMMAND`. It rejects `listener-type` commands so Companion Type does not depend on `listener-type.exe`.
- `backend/ble_bridge.rs`: exposes the Companion-Type device boundary for scan/connect/sync. On Windows it uses the native BLE stack through `btleplug` to scan for Companion, connect/discover GATT, read `recording_list`, pull `recording_chunk_pull` packets by byte offset, verify CRC32 and final SHA-256, and export 16 kHz mono WAV into the Companion-Type recording cache. Companion-Firmware BLE helper tools (`companion_ble_real_bench.py`, `companion_flash_recording_chain.py`, `companion_button_recording_chain.py`) remain validation inventory, not the app runtime dependency.
- `backend/privacy.rs`: deletes only Companion-Type owned local recording files under `COMPANION_TYPE_RECORDING_DIR` and leaves arbitrary imported paths untouched.

## ASR Provider

For real cloud ASR, set:

```powershell
$env:COMPANION_TYPE_ASR_PROVIDER = 'openai-compatible'
$env:COMPANION_TYPE_ASR_ENDPOINT = 'https://api.openai.com/v1/audio/transcriptions'
$env:COMPANION_TYPE_ASR_API_KEY = '<key>'
$env:COMPANION_TYPE_ASR_MODEL = 'gpt-4o-transcribe'
```

Validation uses a local HTTP mock for the OpenAI-compatible multipart request, so CI and offline development do not need a real key. `COMPANION_TYPE_ASR_MAX_UPLOAD_BYTES` defaults to 25 MiB; one hour raw PCM is larger than that, so long meetings should be chunked before ASR.

## Commands

```powershell
npm install
npm run test
npm run verify:user-chain
npm run verify:backend-shape
npm run verify:host-recording
npm run verify:real-microphone
npm run verify:real-microphone-soak
npm run verify:real-microphone-soak:popup
npm run verify:independent-asr
npm run verify:long-meeting
npm run verify:product-chain
npm run verify:dirty-audit
npm run verify:joint-acceptance
npm run verify:msi-install-smoke
npm run verify:installed-ui-sync
npm run verify:final-human-signoff
npm run verify:browser-ui
npm run build
npm run build:windows
npm run build:mobile
npm run tauri:windows
cargo test --manifest-path apps/windows/src-tauri/Cargo.toml --lib
cargo build --manifest-path apps/windows/src-tauri/Cargo.toml
```

For the real board recording-sync gate, run the popup-guided tool under a workflow hardware lock:

```powershell
pwsh -NoProfile -File ..\..\ai-collaboration-workflow\scripts\aiw.ps1 with-lock -Resource Companion-WB55,BLE-Companion,COM13 -Purpose "Companion-Type popup native BLE sync" -Run pwsh -NoProfile -File tools\run_companion_type_ble_sync_popup.ps1
```

The Windows Tauri shell keeps state behind a Type-style commands/coordinator/backend split, so Setup -> Scan -> Connect -> Sync -> Start -> Stop -> Transcribe -> Minutes -> Markdown -> Erase behaves like the real user chain while each backend service remains replaceable. `npm run verify:joint-acceptance` writes `docs/validation/companion-type-joint-acceptance.json`, which maps the current 1-7 acceptance status, evidence, and remaining human/external gates. The current native BLE evidence is `docs/validation/companion-type-native-ble-smoke.json`, covering real Windows scan/connect/discover through the app backend boundary; `docs/validation/companion-type-native-ble-sync-popup.json` records the popup-guided SW3 recording-sync attempt. Final human acceptance still needs a successful popup-guided recording sync or installed app sync path, and real ASR requires a configured key.

`npm run verify:long-meeting` writes `docs/validation/companion-type-long-meeting-chain.json` for the one hour meeting-recorder path: 12 five-minute chunks, transcript import, minutes, Markdown export, and local audio erase. This is a deterministic simulation, not a real one hour microphone soak.

`npm run verify:real-microphone-soak` records through the real host microphone and writes `docs/validation/companion-type-real-microphone-soak.json`. By default it requests 3600 seconds and only that produces `PASS_ONE_HOUR_REAL_MIC_SOAK`; for a shorter smoke use `$env:COMPANION_TYPE_REAL_MIC_SOAK_SECONDS = '2'` before running it, which produces `PASS_SHORT_REAL_MIC_SOAK_SMOKE`. `npm run verify:real-microphone-soak:popup` is the same validation behind a Chinese popup start/end prompt, with no Notepad handoff.

`npm run verify:dirty-audit` writes `docs/validation/companion-type-dirty-audit.json`. It is read-only: it records the current dirty worktree, categories, git status outputs, and evidence files without staging, committing, stashing, resetting, deleting, or touching Listener-Type.

`npm run verify:msi-install-smoke` installs the latest Tauri MSI, launches the installed Companion Type executable, then writes `docs/validation/companion-type-msi-install-smoke.json`. If Windows asks for UAC or installer confirmation, the script uses a Chinese popup prompt; it does not open Notepad.

`npm run verify:installed-ui-sync` launches the installed app, clicks the visible Scan -> Sync chain, and captures screenshots under `docs/validation/companion-type-installed-ui-sync-*.png`. The summary JSON is `docs/validation/companion-type-installed-ui-sync.json`; final PASS for item 2 still requires visual review of the after-Sync screenshot.

`npm run verify:final-human-signoff` opens a Chinese popup for the final local human gate. It writes `docs/validation/companion-type-final-human-signoff.json`; only an explicit "确认通过" with all checklist items checked can clear the item 1/2 human confirmation gate.
