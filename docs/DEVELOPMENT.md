# Engineering notes retained from the previous homepage

These notes preserve the earlier development context. WB55 bring-up and fixture reports are historical; they do not establish current WBA acceptance. Use the [current readiness page](STATUS.md) for product scope. Some commands and linked files require the local engineering workspace and are not published in this documentation-only update.

---

## Windows atomic file paths

Recording payloads, meeting indexes, ASR cache, settings/checkpoints and reconnection preferences share the atomic writer. It resolves an existing parent once, uses its canonical Windows path when calling `MoveFileExW`, preserves the leaf component, and stages under a short unique name. A valid long destination filename no longer becomes an oversized temporary filename. Existing-file sharing errors preserve the old destination; only the writer's own stage is removed, and retry remains available. No registry or machine settings are changed. References: [Microsoft MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw), [Windows path limits](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation).

`--file-storage-self-test <new-folder>` exercises ordinary local Windows paths over 300 UTF-16 units, Unicode, a 245-unit leaf name, dot-parent normalization, explicit replacement, occupied destinations, retry and production reconnection preferences. Installed cache and credential-storage probes also run under long roots. These are controlled local software fixtures. Network shares, physical power loss, third-party audio libraries and native GUI interactions need separate validation; this does not complete the artifact ownership/deletion ledger.

## Generated audio provenance and explicit cleanup

`backend/audio_artifacts.rs` records newly generated files in `.audio-artifacts.json` under the durable recording root. Each record has an exact source reference, a relative single-component filename, purpose, phase and sealed byte/hash identity. An intent is published before creation; native OS leases cover writing and ASR consumption. Explicit deletion resolves this recorded graph, preserves other meetings' references, checks identities/leases before mutation, and publishes a retryable deletion intention before removing a file. Unknown existing files cannot be adopted through a generation call. Corrupt manifests, changed payloads and unsealed crash data fail closed. Imports/exports are retained.

The integrated paths cover host WAV creation/sealing, board raw Opus/COP1, native decoded WAV/staging, live prefixes/windows and newly split ASR chunks. A completed transfer cursor is attached to its final WAV only after its full byte count and SHA match the verified payload, before the library checkpoint and device ACK; an unsuccessful ACK can no longer leave an unassociated complete `.part` behind. Finalized online recording links its generated prefix groups even when a partial ASR consumer failed. The live 30-second consumer window now uses validated native PCM and the WAV writer instead of looking up FFmpeg. ASR chunks use short unique names in the durable root and record the exact imported or product source. Completed scratch history is bounded to 256 recent records plus any retired bridge still needed by a live descendant; active/unresolved entries are never pruned.

`--audio-artifacts-self-test <fresh-folder>` exercises actual native COP1 decoding, PCM window/split coverage, the production privacy coordinator, Windows file sharing and lease exclusion, manifest corruption, changed identities, shared owners, delete-intent retry and bounded retired history in an isolated profile. Synthetic host recording is expressly a software fixture; it does not use a microphone or prove board capture. Full artifact ownership remains open: old untracked Opus/live/Temp files are not swept, growing/unverified transfer `.part` cursors and common atomic-writer staging are not integrated yet, unfinished online groups still need pending-device/session recovery, unprovable legacy cache/embedding files need a migration contract, and physical power loss, real process restart, cross-process scenarios, native GUI and the board chain remain unverified. Ownership metadata/recent history is not a complete historical privacy erase.

## ASR cache ownership and privacy deletion

The Volcengine consumer records new V2 bodies in `.cache-owners.json` beside the cache. Each entry has its exact filename, byte/hash identity, recording ancestry and explicit meeting IDs. Original references are captured before temporary ASR files are removed; finalized online prefix groups attach to the verified final recording. Session transcription binds successful cached chunks even if another chunk failed. The journal contains no transcript body or speaker embeddings. Prepared identity is published before the body; a durable deleting phase precedes removal. Native locks exclude overlapping journal writers, and audio usage leases block privacy effects during consumption. Optional cache/binding errors preserve successful paid ASR results and do not block delivery of the verified board WAV.

Production clear-transcript, delete-session, erase-audio and local erase-all now remove the applicable cache bodies before committing the index mutation. Other explicit cache owners remain; clearing one transcript releases that meeting's cache reference. Erase-audio also drops its optional ASR cache while retaining the meeting's index transcript. Occupied/changed bodies, corrupt journals or failed publication preserve the index for retry. After a partial unlink, durable identity allows retry with the audio source already absent. Normal retention bounds fully validated V2 bodies to 512 and no longer deletes arbitrary hash-shaped files. Cache files are disposable; index transcripts and user exports have separate retention contracts.

Unregistered legacy V2 bodies can be adopted for deletion only if their schema, embedded PCM/configuration identity, final result digest and exact content-addressed filename all validate. Selected deletion additionally requires an exact PCM match; shared unbound legacy PCM stays until local erase-all. V1/embedding formats without proven identity, malformed files, unknown sidecars, imports and user exports are preserved and counted in the control result. Thus local cleanup does not claim complete historical erasure. Legacy partial-chunk attribution and complete ownership/backup history remain CP13 work.

`--cache-privacy-self-test <fresh-folder>` exercises production privacy controls, shared cache ownership, scratch ancestry, final prefix association, absent audio pointers, Windows occupied-file failures, durable retry through a fresh coordinator, ASR usage exclusion, legacy V2 matching and unknown V1 preservation, journal corruption/traversal and optional-cache repair. It uses controlled PCM/provider results only; no real ASR, microphone, device, real process restart or GUI acceptance is implied. Cache overrides are internal environment variables: `COMPANION_TYPE_ASR_CACHE_DIR` first, otherwise an explicit recording-root override uses its `.asr-chunk-cache`, otherwise the usual local application profile. These probes never use the normal user cache.

## Explicit credential clearing

Secret inputs left blank retain saved values. The settings form sends a separate `clearCredentials` list for an explicit clear, supports undo before saving, and retains intent after a failed save. Conflicting replacement/clear requests, unknown keys and whitespace-only replacements are rejected. The coordinator excludes recording and other active operations while saving.

Settings format 3 keeps persistent fallback suppression per key; format 2 remains readable. Clearing removes process aliases and prevents shared legacy import from re-enabling Volc credentials. It does not change the user's environment or another product's shared credential target. The new public file is the commit point. A durable clear journal prevents pre-clear backup recovery if cleanup is interrupted; both recovery files are updated before retiring old Companion-owned vault snapshots. Cleanup failures remain visible and can be retried by saving again. A missing/damaged primary during an unresolved clear fails closed and preserves files for repair.

`--settings-storage-self-test <new-folder>` tests native Windows file sharing and only unique, isolated Credential Manager targets. Its `credentialClearChecks` cover blank/clear/replacement, failure before and after commit, retry, redaction, fallback suppression, startup application and cleared backup recovery. It does not prove native GUI interaction, physical power-loss durability, deletion of all historical plaintext/quarantine artifacts, real ASR, or board acceptance. Custom external scripts retain responsibility for credentials they obtain independently.

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
- dual meeting routes on `meetingStart.meetingMode`:
  - **`offlineStore` (default)**: store WAV/chunks first; batch ASR later (`needs_transcription` until then);
  - **`onlineLive`**: append live partials via `meetingAppendLiveTranscript` while recording; stop can land transcribed-ready (audio still stored as backup);
- record on the WBA device using codec=3 Opus/COP1 and its NOR recording partition; Type pulls by byte offset and validates packet CRC plus final SHA before acknowledging a complete recording;
- keep device recording and the optional computer microphone input as separate sources; host audio and deterministic fixtures are never evidence of board capture;
- use the configured board duration limit and report the actual captured host WAV duration after stopping;
- transcribe captured audio through Companion-Type owned providers;
- keep manual transcript import as an override path;
- generate summary, decisions, action items, questions, keywords, and Markdown;
- save existing Markdown/TXT/JSON/SRT through the desktop save dialog, without rerunning transcription or minutes generation; SRT requires real timestamps;
- erase selected audio, selected transcript/minutes, or all local meeting state.

Goal contracts:

- Dual mode: `docs/goals/companion-type-dual-meeting-mode-goal.md` → `npm run verify:dual-meeting-mode`
- Product close (excl wake/mobile): `docs/goals/companion-type-product-close-excl-wake-mobile-goal.md` → `npm run verify:product-close`

Product settings (ASR / DeepSeek / BLE compress / default mode) persist under `%APPDATA%\Companion Type\product-settings.json` and apply into process env at launch.

The browser/mobile shells use deterministic fixture state. The Windows Tauri shell uses the same `CompanionV1Snapshot` and `CompanionV1ControlRequest` contract, with native BLE, real host WAV recording, Companion-Type owned transcription providers, conservative local audio deletion, and a Companion-Type device boundary. A failed microphone never silently becomes synthetic audio; synthetic capture is an explicit test mode. Runtime capture errors preserve existing audio and pause automatic processing.

Current WBA readiness and unresolved electrical/physical acceptance items are indexed in `../ACTIVE_GOAL.md` and `../Companion-Firmware/platform/stm32wba55_companion_v11/README.md`. Historical WB55 and deterministic test reports below do not establish WBA acceptance. The first-install kit uses SWD and an external NOR loader; this PCB's USB-C connection supplies power only.

## Backend Shape

The Windows Tauri backend uses a Type-style separation pattern:

- `apps/windows/src-tauri/src/lib.rs`: app assembly, background recovery/reconnection, and diagnostic/acceptance CLI entry points.
- `apps/windows/src-tauri/src/commands.rs`: IPC command surface for React.
- `apps/windows/src-tauri/src/coordinator.rs`: single owner of Companion host workflow state.
- `apps/windows/src-tauri/src/backend/mod.rs`: replaceable backend boundary.
- `apps/windows/src-tauri/src/companion_v1.rs`: Companion V1 contract and fixture state transitions.

The active backend is still `FixtureCompanionBackend`, but it now exposes separate service boundaries for device control, host recording, Companion-Type transcription, minutes generation, and Markdown export. The device-control bridge now has a Windows-native BLE path behind the same UI contract, while the deterministic state reducer keeps browser/mobile validation repeatable.

The backend now has three real host-side boundaries:

- `backend/host_recording.rs`: starts host microphone capture on `meetingStart`, writes 16 kHz mono WAV, and writes the WAV path back to the selected session on `meetingStop`/`meetingFinalize`. Automated tests force synthetic WAV mode so validation does not require microphone permissions.
- `backend/transcription.rs`: owns the `meetingTranscribeAudio` path. It can read `COMPANION_TYPE_TRANSCRIPT_TEXT`, use a sibling `*.transcript.txt` sidecar for deterministic validation, call an OpenAI-compatible multipart ASR endpoint with `COMPANION_TYPE_ASR_ENDPOINT` plus `COMPANION_TYPE_ASR_API_KEY`/`OPENAI_API_KEY`, or run a generic `COMPANION_TYPE_ASR_COMMAND`. It rejects `listener-type` commands so Companion Type does not depend on `listener-type.exe`.
- Advanced ASR/minutes commands on Windows run in a dedicated OS job, including their descendants. ASR has a 120-second deadline, minutes 180 seconds, stdout a 4 MiB cap and stderr a 64 KiB cap; bounded cleanup follows. Timeout, output overflow and exit failure retain the original audio/transcript and minutes draft. Errors omit command paths, arguments, environment values and output. This runner adds no user-facing cancel button.
- Configure an executable or an explicit interpreter (for example `python.exe` plus the script path in the arguments). Arguments remain literal; the runner does not implicitly launch a shell or interpret batch files. Custom scripts own their internal service protocol and must report failure with a nonzero exit code. JSON output must contain a valid final result; legacy plain transcript/Markdown output is still supported.
- The optional `tools/deepseek_minutes_polish.py` helper independently bounds its HTTP request (120 seconds, 4 MiB), refuses redirects and rejects truncated completions or invalid fields. Its deadline worker is intended for the CLI process; it does not cancel a request thread when embedded in a long-lived Python host. Run `python tools/test_deepseek_minutes_request_limits.py` for controlled loopback tests without real keys or user recordings.
- `backend/ble_bridge.rs`: exposes the Companion-Type device boundary for scan/connect/sync. On Windows it uses the native BLE stack through `btleplug` to scan for Companion, connect/discover GATT, read `recording_list`, pull `recording_chunk_pull` packets by byte offset, verify CRC32 and final SHA-256, and export 16 kHz mono WAV into the Companion-Type recording cache. Companion-Firmware BLE helper tools (`companion_ble_real_bench.py`, `companion_flash_recording_chain.py`, `companion_button_recording_chain.py`) remain validation inventory, not the app runtime dependency.
- `backend/privacy.rs`: deletes only Companion-Type owned local recording files under `COMPANION_TYPE_RECORDING_DIR` and leaves arbitrary imported paths untouched.
- Production deletion validates the confirmed session ID and current selection before file/device effects; host/board recording or an active live-ASR session blocks deletion. Shared indexed audio remains for retained meetings and is reported. Failed migration-ledger publication can retry after the WAV is already absent. `--privacy-delete-self-test <fresh-folder>` exercises the coordinator and Windows occupied-file/ledger failures with isolated fixtures. Cache privacy has its separate ownership probe above. Historical unknown Opus/live/partial and unprovable cache/embedding artifacts remain outside the completed cleanup scope.

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
