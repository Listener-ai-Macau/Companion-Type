//! Companion backend service boundary.
//!
//! Commands call a coordinator, the coordinator owns state, and replaceable
//! backend services implement device/audio/transcription/minutes work behind
//! the same IPC contract.

mod ble_bridge;
mod firmware_ota;
mod host_recording;
mod privacy;
mod transcription;

use std::sync::Mutex;

use serde::Serialize;

use crate::companion_v1::{
    apply_fixture_control, fixture_snapshot, seal_companion_v1_session_chunks,
    CompanionV1AudioChunk, CompanionV1ControlAction, CompanionV1ControlRequest,
    CompanionV1HostSession, CompanionV1Snapshot,
};
use ble_bridge::CompanionBleBridge;
pub use ble_bridge::CompanionBleBridgeStatus;
pub use firmware_ota::{CompanionFirmwareOtaReport, CompanionFirmwareOtaRequest};
use host_recording::HostRecordingManager;
use privacy::{PrivacyEraseReport, PrivacyManager};
pub(crate) use transcription::CompanionTranscriptionManager;

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionBackendCapabilities {
    pub backend_id: String,
    pub backend_kind: String,
    pub services: CompanionBackendServices,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionBackendServices {
    pub device_control: CompanionServiceBoundary,
    pub recording: CompanionServiceBoundary,
    pub transcription: CompanionServiceBoundary,
    pub minutes: CompanionServiceBoundary,
    pub export: CompanionServiceBoundary,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionServiceBoundary {
    pub provider_id: String,
    pub mode: String,
    pub supported: bool,
    pub notes: String,
}

pub trait CompanionBackend: Send + Sync {
    fn capabilities(&self) -> CompanionBackendCapabilities;
    fn ble_bridge_status(&self) -> CompanionBleBridgeStatus;
    fn snapshot(&self) -> Result<CompanionV1Snapshot, String>;
    fn apply_control(
        &self,
        request: CompanionV1ControlRequest,
    ) -> Result<CompanionV1Snapshot, String>;
    fn transfer_firmware_ota(
        &self,
        request: CompanionFirmwareOtaRequest,
    ) -> Result<CompanionFirmwareOtaReport, String>;
}

pub struct FixtureCompanionBackend {
    snapshot: Mutex<CompanionV1Snapshot>,
    host_recording: HostRecordingManager,
    transcription: CompanionTranscriptionManager,
    ble_bridge: CompanionBleBridge,
    privacy: PrivacyManager,
}

impl FixtureCompanionBackend {
    pub fn new() -> Self {
        Self {
            snapshot: Mutex::new(fixture_snapshot()),
            host_recording: HostRecordingManager::new(),
            transcription: CompanionTranscriptionManager::new(),
            ble_bridge: CompanionBleBridge::detect_default(),
            privacy: PrivacyManager::new(),
        }
    }
}

impl Default for FixtureCompanionBackend {
    fn default() -> Self {
        Self::new()
    }
}

impl CompanionBackend for FixtureCompanionBackend {
    fn capabilities(&self) -> CompanionBackendCapabilities {
        let ble_status = self.ble_bridge.status();
        CompanionBackendCapabilities {
            backend_id: "companion-type.hybrid-host".to_string(),
            backend_kind: "host-recording+standalone-transcription+fixture-control".to_string(),
            services: CompanionBackendServices {
                device_control: CompanionServiceBoundary {
                    provider_id: ble_status.provider_id.clone(),
                    mode: ble_status.mode.clone(),
                    supported: ble_status.ready,
                    notes: ble_status.message,
                },
                recording: CompanionServiceBoundary {
                    provider_id: "host-microphone-wav".to_string(),
                    mode: "real-host-wav-with-synthetic-test-fallback".to_string(),
                    supported: true,
                    notes: "Records host microphone sessions as 16 kHz mono WAV files; tests can force synthetic mode."
                        .to_string(),
                },
                transcription: CompanionServiceBoundary {
                    provider_id: "companion-type-transcription".to_string(),
                    mode: "env-sidecar-openai-compatible-or-command".to_string(),
                    supported: true,
                    notes: "Transcribes selected session audio through Companion-Type owned providers, including OpenAI-compatible multipart ASR; listener-type.exe is not used."
                        .to_string(),
                },
                minutes: CompanionServiceBoundary {
                    provider_id: "fixture-minutes".to_string(),
                    mode: "deterministic-local".to_string(),
                    supported: true,
                    notes: "Generates deterministic summary, decisions, actions, questions, and keywords."
                        .to_string(),
                },
                export: CompanionServiceBoundary {
                    provider_id: "fixture-markdown-export".to_string(),
                    mode: "markdown".to_string(),
                    supported: true,
                    notes: "Exports generated meeting minutes to Markdown in app state.".to_string(),
                },
            },
        }
    }

    fn ble_bridge_status(&self) -> CompanionBleBridgeStatus {
        self.ble_bridge.status()
    }

    fn snapshot(&self) -> Result<CompanionV1Snapshot, String> {
        self.snapshot
            .lock()
            .map_err(|_| "Companion backend state lock failed".to_string())
            .map(|snapshot| snapshot.clone())
    }

    fn apply_control(
        &self,
        mut request: CompanionV1ControlRequest,
    ) -> Result<CompanionV1Snapshot, String> {
        if matches!(
            request.action,
            CompanionV1ControlAction::MeetingResetSession
                | CompanionV1ControlAction::PrivacyEraseAll
        ) {
            self.host_recording.discard();
        }

        let mut snapshot = self
            .snapshot
            .lock()
            .map_err(|_| "Companion backend state lock failed".to_string())?;
        let action = request.action;
        let requested_session_id = request.session_id.clone();
        let mut transcription_note: Option<String> = None;
        let mut device_note: Option<String> = None;
        let mut privacy_report: Option<PrivacyEraseReport> = None;

        match action {
            CompanionV1ControlAction::DeviceScan => {
                let operation = self.ble_bridge.scan();
                if !operation.ready {
                    return Err(operation.message);
                }
                request.device_id = operation.device_id.clone();
                device_note = Some(format!(
                    "{} ({} / {})",
                    operation.message, operation.provider_id, operation.mode
                ));
            }
            CompanionV1ControlAction::DeviceConnect => {
                let operation = self.ble_bridge.connect(request.device_id.as_deref());
                if !operation.ready {
                    return Err(operation.message);
                }
                request.device_id = operation.device_id.clone();
                device_note = Some(format!(
                    "{} ({} / {})",
                    operation.message, operation.provider_id, operation.mode
                ));
            }
            CompanionV1ControlAction::DeviceSyncRecordings => {
                let operation = self.ble_bridge.sync_recordings();
                if !operation.ready {
                    return Err(operation.message);
                }
                request.device_id = operation.device_id.clone();
                if request.audio_path.is_none() {
                    request.audio_path = operation.recording_path.clone();
                }
                device_note = Some(format!(
                    "{} ({} / {})",
                    operation.message, operation.provider_id, operation.mode
                ));
            }
            CompanionV1ControlAction::PrivacyEraseAudio => {
                privacy_report = Some(self.privacy.erase_selected_audio(&snapshot));
            }
            CompanionV1ControlAction::PrivacyEraseAll => {
                privacy_report = Some(self.privacy.erase_all_audio(&snapshot));
            }
            _ => {}
        }

        let request = if action == CompanionV1ControlAction::MeetingTranscribeAudio {
            let audio_path = request
                .audio_path
                .clone()
                .or_else(|| {
                    selected_session(&snapshot).and_then(|session| session.audio_path.clone())
                })
                .ok_or_else(|| {
                    "Transcribe audio requires a selected session with audioPath.".to_string()
                })?;
            let transcript = self.transcription.transcribe_audio(&audio_path)?;
            transcription_note = Some(format!(
                "{} ({}){}",
                transcript.provider_id,
                transcript.mode,
                transcript
                    .evidence_path
                    .as_ref()
                    .map(|path| format!(" -> {}", path.to_string_lossy()))
                    .unwrap_or_default()
            ));
            let mut request = request;
            request.transcript_text = Some(transcript.text);
            request.audio_path = Some(audio_path);
            request
        } else {
            request
        };
        let mut next = apply_fixture_control(snapshot.clone(), request)?;

        match action {
            CompanionV1ControlAction::DeviceScan
            | CompanionV1ControlAction::DeviceConnect
            | CompanionV1ControlAction::DeviceDisconnect
            | CompanionV1ControlAction::DeviceSyncRecordings => {
                if let Some(echo) = next.last_control.as_mut() {
                    echo.message = device_note
                        .unwrap_or_else(|| "Companion device boundary completed".to_string());
                }
            }
            CompanionV1ControlAction::PrivacyEraseAudio
            | CompanionV1ControlAction::PrivacyEraseAll => {
                if let Some(echo) = next.last_control.as_mut() {
                    let report = privacy_report.unwrap_or_default();
                    echo.message = format!(
                        "privacy erase completed: {} deleted, {} skipped",
                        report.deleted_files, report.skipped_files
                    );
                }
            }
            CompanionV1ControlAction::PrivacyEraseTranscript => {
                if let Some(echo) = next.last_control.as_mut() {
                    echo.message =
                        "privacy erase completed: transcript and minutes cleared".to_string();
                }
            }
            CompanionV1ControlAction::MeetingStart => {
                if let Some(session) = selected_session_mut(&mut next) {
                    if session.audio_path.is_none() {
                        let start = self.host_recording.start(&session.id, &session.title)?;
                        session.audio_path = Some(start.path.to_string_lossy().to_string());
                        session.retention.audio_cached = true;
                        session.chunks = vec![audio_chunk(
                            format!("{}-host-open", session.id),
                            Some(start.path.to_string_lossy().to_string()),
                            session.started_at.clone(),
                            None,
                            0,
                            0,
                            "open",
                        )];
                        session.source = "hostMicrophone".to_string();
                        if let Some(echo) = next.last_control.as_mut() {
                            echo.message = format!(
                                "host recording started {} ({}) -> {}",
                                start.session_id,
                                start.mode,
                                start.path.to_string_lossy()
                            );
                        }
                    } else if let Some(echo) = next.last_control.as_mut() {
                        echo.message =
                            "session uses supplied audioPath; host microphone was not started"
                                .to_string();
                    }
                }
            }
            CompanionV1ControlAction::MeetingTranscribeAudio => {
                if let Some(echo) = next.last_control.as_mut() {
                    echo.message = format!(
                        "transcribed by Companion-Type provider {}",
                        transcription_note.unwrap_or_else(|| "unknown".to_string())
                    );
                }
            }
            CompanionV1ControlAction::MeetingStop | CompanionV1ControlAction::MeetingFinalize => {
                if let Some(stop) = self.host_recording.stop(requested_session_id.as_deref())? {
                    if let Some(session) = selected_session_mut(&mut next) {
                        if session.id == stop.session_id {
                            session.audio_path = Some(stop.path.to_string_lossy().to_string());
                            session.duration_ms = stop.duration_ms.max(session.duration_ms);
                            session.audio_bytes = stop.bytes;
                            session.retention.audio_cached = true;
                            let stopped_at = session
                                .stopped_at
                                .clone()
                                .unwrap_or_else(|| "host-recording-stop".to_string());
                            session.chunks = seal_companion_v1_session_chunks(
                                session,
                                &stopped_at,
                                session.duration_ms,
                                Some(stop.bytes),
                            );
                            session.source = "hostMicrophone".to_string();
                            if let Some(echo) = next.last_control.as_mut() {
                                echo.message = format!(
                                    "host recording stopped ({}) {} bytes -> {}",
                                    stop.mode,
                                    stop.bytes,
                                    stop.path.to_string_lossy()
                                );
                            }
                        }
                    }
                    next.meeting.duration_ms = stop.duration_ms.max(next.meeting.duration_ms);
                }
            }
            _ => {}
        }

        refresh_privacy_counts(&mut next);
        *snapshot = next.clone();
        Ok(next)
    }

    fn transfer_firmware_ota(
        &self,
        request: CompanionFirmwareOtaRequest,
    ) -> Result<CompanionFirmwareOtaReport, String> {
        firmware_ota::transfer(&self.ble_bridge, request)
    }
}

fn selected_session_mut(snapshot: &mut CompanionV1Snapshot) -> Option<&mut CompanionV1HostSession> {
    let selected_id = snapshot
        .host
        .selected_session_id
        .clone()
        .or_else(|| snapshot.host.active_session_id.clone())
        .or_else(|| {
            snapshot
                .host
                .sessions
                .first()
                .map(|session| session.id.clone())
        })?;
    snapshot
        .host
        .sessions
        .iter_mut()
        .find(|session| session.id == selected_id)
}

fn selected_session(snapshot: &CompanionV1Snapshot) -> Option<&CompanionV1HostSession> {
    let selected_id = snapshot
        .host
        .selected_session_id
        .as_ref()
        .or(snapshot.host.active_session_id.as_ref());
    if let Some(selected_id) = selected_id {
        return snapshot
            .host
            .sessions
            .iter()
            .find(|session| &session.id == selected_id);
    }
    snapshot.host.sessions.first()
}

fn audio_chunk(
    id: String,
    path: Option<String>,
    started_at: Option<String>,
    stopped_at: Option<String>,
    duration_ms: u64,
    bytes: u64,
    status: &str,
) -> CompanionV1AudioChunk {
    CompanionV1AudioChunk {
        id,
        path,
        started_at,
        stopped_at,
        duration_ms,
        bytes,
        status: status.to_string(),
    }
}

fn refresh_privacy_counts(snapshot: &mut CompanionV1Snapshot) {
    snapshot.privacy.audio_cache_bytes = snapshot
        .host
        .sessions
        .iter()
        .map(|session| session.audio_bytes)
        .sum();
    snapshot.privacy.transcript_bytes = snapshot
        .host
        .sessions
        .iter()
        .map(|session| session.transcript_text.as_bytes().len() as u64)
        .sum();
    snapshot.privacy.minutes_bytes = snapshot
        .host
        .sessions
        .iter()
        .map(|session| session.export_markdown.as_bytes().len() as u64)
        .sum();
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::CompanionV1ControlAction;

    #[test]
    fn fixture_backend_exposes_type_style_service_boundaries() {
        let backend = FixtureCompanionBackend::new();
        let capabilities = backend.capabilities();
        assert_eq!(capabilities.backend_id, "companion-type.hybrid-host");
        assert_eq!(
            capabilities.services.recording.provider_id,
            "host-microphone-wav"
        );
        assert_eq!(
            capabilities.services.transcription.provider_id,
            "companion-type-transcription"
        );
        assert!(capabilities.services.minutes.supported);
    }

    #[test]
    fn fixture_backend_keeps_state_between_controls() {
        let backend = FixtureCompanionBackend::new();
        let started = backend
            .apply_control(CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingStart,
                ble_name: None,
                session_id: None,
                prompt_id: None,
                title: Some("Backend state chain".to_string()),
                transcript_text: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        assert_eq!(started.host.sessions.len(), 1);
        assert!(started.host.sessions[0].audio_path.is_some());

        let stopped = backend
            .apply_control(CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingStop,
                ble_name: None,
                session_id: None,
                prompt_id: None,
                title: None,
                transcript_text: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: Some(3_600_000),
            })
            .unwrap();
        assert_eq!(stopped.host.sessions.len(), 1);
        assert!(stopped.host.sessions[0].duration_ms > 0);
        assert!(stopped.host.sessions[0].audio_path.is_some());
    }

    #[test]
    fn backend_transcribes_audio_with_companion_type_sidecar_provider() {
        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");
        std::env::remove_var("COMPANION_TYPE_ASR_COMMAND");
        let root =
            std::env::temp_dir().join("companion-type-independent-transcription-backend-test");
        let _ = std::fs::create_dir_all(&root);
        let audio = root.join("meeting.wav");
        let sidecar = root.join("meeting.transcript.txt");
        std::fs::write(&audio, b"RIFF----WAVEfmt ").unwrap();
        std::fs::write(
            &sidecar,
            "Decision: Companion-Type owns the ASR boundary.\nAction: Maya validates independent minutes.",
        )
        .unwrap();

        let backend = FixtureCompanionBackend::new();
        let started = backend
            .apply_control(CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingStart,
                ble_name: None,
                session_id: Some("sidecar-session".to_string()),
                prompt_id: None,
                title: Some("Independent ASR".to_string()),
                transcript_text: None,
                audio_path: Some(audio.to_string_lossy().to_string()),
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        assert_eq!(started.host.sessions[0].source, "deviceFlash");
        assert_eq!(
            started.host.sessions[0].audio_path.as_deref(),
            Some(audio.to_string_lossy().as_ref())
        );

        let stopped = backend
            .apply_control(CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingStop,
                ble_name: None,
                session_id: Some("sidecar-session".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: Some(90_000),
            })
            .unwrap();
        assert_eq!(stopped.host.sessions[0].status, "captured");

        let transcribed = backend
            .apply_control(CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingTranscribeAudio,
                ble_name: None,
                session_id: Some("sidecar-session".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        assert_eq!(transcribed.meeting.status, "transcribed");
        assert!(transcribed.host.sessions[0]
            .transcript_text
            .contains("Companion-Type owns the ASR boundary"));
        assert!(transcribed
            .last_control
            .as_ref()
            .unwrap()
            .message
            .contains("companion-type-sidecar-transcript"));

        let minutes = backend
            .apply_control(CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingGenerateMinutes,
                ble_name: None,
                session_id: Some("sidecar-session".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        assert_eq!(minutes.meeting.status, "minutesReady");
        assert_eq!(
            minutes.host.sessions[0]
                .minutes
                .as_ref()
                .unwrap()
                .decisions
                .len(),
            1
        );
        assert_eq!(
            minutes.host.sessions[0]
                .minutes
                .as_ref()
                .unwrap()
                .action_items
                .len(),
            1
        );
    }
}
