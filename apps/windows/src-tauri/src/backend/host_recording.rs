//! Host microphone recording backend.
//!
//! The optional host-input path records a 16 kHz mono WAV on the computer;
//! board recording has its own codec/storage/transfer path.
//! Capture, sample conversion, and the WAV container come from the platform
//! `denzic-host-audio-v1-core` crate; this module keeps session management,
//! file placement, the ratio resampler, and explicit synthetic test mode.

use std::fs::create_dir_all;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

/// Optional PCM fan-out (16 kHz mono i16) for onlineLive streaming ASR.
pub type HostPcmSink = Arc<dyn Fn(&[i16]) + Send + Sync>;

use denzic_host_audio_v1_core::capture::{CaptureOptions, CaptureSession};
use denzic_host_audio_v1_core::wav::WavWriter;
use denzic_host_audio_v1_core::PCM_SAMPLE_RATE_HZ as TARGET_SAMPLE_RATE;

const SYNTHETIC_HZ: f32 = 440.0;

#[derive(Clone, Debug)]
pub struct HostRecordingStart {
    pub session_id: String,
    pub path: PathBuf,
    pub mode: String,
}

#[derive(Clone, Debug)]
pub struct HostRecordingStop {
    pub session_id: String,
    pub path: PathBuf,
    pub duration_ms: u64,
    pub bytes: u64,
    pub mode: String,
    pub capture_error: Option<String>,
}

struct ActiveHostRecording {
    session_id: String,
    path: PathBuf,
    started_at: Instant,
    mode: ActiveHostRecordingMode,
    artifact: Option<super::audio_artifacts::WriteLease>,
}

enum ActiveHostRecordingMode {
    Real(RealRecording),
    Synthetic,
}

pub struct HostRecordingManager {
    active: Mutex<Option<ActiveHostRecording>>,
    pcm_sink: Mutex<Option<HostPcmSink>>,
}

impl HostRecordingManager {
    pub fn new() -> Self {
        Self {
            active: Mutex::new(None),
            pcm_sink: Mutex::new(None),
        }
    }

    pub fn set_pcm_sink(&self, sink: Option<HostPcmSink>) {
        if let Ok(mut slot) = self.pcm_sink.lock() {
            *slot = sink;
        }
    }

    pub fn start(&self, session_id: &str, title: &str) -> Result<HostRecordingStart, String> {
        let requested_mode = std::env::var("COMPANION_TYPE_HOST_RECORDING_MODE")
            .unwrap_or_else(|_| if cfg!(test) { "synthetic" } else { "real" }.to_string());
        let _diagnostic_scope=super::diagnostics::RecordingScope::enter(session_id);
        super::diagnostics::Span::start(super::diagnostics::Operation::HostRecordingStart).result(self.start_with_mode(session_id, title, &requested_mode, RealRecording::start))
    }

    fn start_with_mode(
        &self,
        session_id: &str,
        title: &str,
        requested_mode: &str,
        start_real: impl FnOnce(PathBuf, Option<HostPcmSink>) -> Result<RealRecording, String>,
    ) -> Result<HostRecordingStart, String> {
        let mut active = self
            .active
            .lock()
            .map_err(|_| "host recording state lock failed".to_string())?;
        if active.is_some() {
            return Err("已有本机录音正在进行，请先结束当前录音".to_string());
        }

        let path = recording_path(session_id, title)?;
        let artifact = super::audio_artifacts::WriteLease::begin(&path, &path, super::audio_artifacts::Purpose::Recording)?;
        let pcm_sink = self.pcm_sink.lock().ok().and_then(|slot| slot.clone());

        let (mode, mode_label) = if requested_mode.eq_ignore_ascii_case("synthetic") {
            (ActiveHostRecordingMode::Synthetic, "synthetic".to_string())
        } else {
            // Even the legacy fallback setting must surface capture failure.
            // Generated audio is available only through explicit synthetic mode.
            let recording = start_real(path.clone(), pcm_sink)
                .map_err(|error| format!("无法启动本机麦克风录音：{error}"))?;
            (ActiveHostRecordingMode::Real(recording), "host-microphone".to_string())
        };

        *active = Some(ActiveHostRecording {
            session_id: session_id.to_string(),
            path: path.clone(),
            started_at: Instant::now(),
            mode,
            artifact,
        });

        Ok(HostRecordingStart {
            session_id: session_id.to_string(),
            path,
            mode: mode_label,
        })
    }

    pub fn stop(
        &self,
        requested_session_id: Option<&str>,
    ) -> Result<Option<HostRecordingStop>, String> {
        let _diagnostic_scope=super::diagnostics::RecordingScope::enter_optional(requested_session_id);
        let mut span = super::diagnostics::Span::start(super::diagnostics::Operation::HostRecordingStop);
        let result = self.stop_inner(requested_session_id);
        if let Ok(Some(report))=&result{span.bind_recording(&report.session_id);}
        let error = match &result { Err(error) => Some(error.as_str()), Ok(Some(report)) => report.capture_error.as_deref(), _ => None };
        span.finish(error);
        result
    }

    fn stop_inner(&self, requested_session_id: Option<&str>) -> Result<Option<HostRecordingStop>, String> {
        let mut active = self
            .active
            .lock()
            .map_err(|_| "host recording state lock failed".to_string())?;
        let Some(recording) = active.as_ref() else {
            return Ok(None);
        };
        if let Some(session_id) = requested_session_id {
            if recording.session_id != session_id {
                return Err("停止请求与正在录音的会议不一致，当前录音继续保留".to_string());
            }
        }
        stop_active_recording(active.take().expect("active recording checked above")).map(Some)
    }

    pub fn discard(&self) {
        if let Ok(mut active) = self.active.lock() {
            if let Some(recording) = active.take() {
                let _ = stop_active_recording(recording);
            }
        }
    }
}

impl Default for HostRecordingManager {
    fn default() -> Self {
        Self::new()
    }
}

fn stop_active_recording(recording: ActiveHostRecording) -> Result<HostRecordingStop, String> {
    let elapsed_ms = recording.started_at.elapsed().as_millis().max(1) as u64;
    let (path, bytes, mode, capture_error) = match recording.mode {
        ActiveHostRecordingMode::Real(real) => {
            let stop = real.stop()?;
            (stop.path, stop.bytes, "host-microphone".to_string(), stop.capture_error)
        }
        ActiveHostRecordingMode::Synthetic => {
            write_synthetic_wav(&recording.path, elapsed_ms.max(1_000))?;
            let bytes = std::fs::metadata(&recording.path)
                .map_err(|err| format!("read synthetic wav metadata: {err}"))?
                .len();
            (recording.path, bytes, "synthetic".to_string(), None)
        }
    };

    if let Some(artifact) = recording.artifact { artifact.finish()?; }
    Ok(HostRecordingStop {
        session_id: recording.session_id,
        path,
        duration_ms: bytes.saturating_sub(44).saturating_mul(1_000)
            / (u64::from(TARGET_SAMPLE_RATE) * 2),
        bytes,
        mode,
        capture_error,
    })
}

fn recording_path(session_id: &str, title: &str) -> Result<PathBuf, String> {
    let root = super::audio_storage::recording_root()?;
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|err| format!("clock before epoch: {err}"))?
        .as_secs();
    let safe_title = sanitize_file_stem(title);
    // The session ID belongs in the index, not in a path component. A unique
    // bounded filename also prevents two starts from replacing an older file.
    let _ = session_id;
    Ok(root.join(format!("{stamp}-{}-{safe_title}.wav", uuid::Uuid::new_v4().simple())))
}

fn sanitize_file_stem(value: &str) -> String {
    let mut safe = value
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_') {
                ch
            } else {
                '-'
            }
        })
        .collect::<String>();
    while safe.contains("--") {
        safe = safe.replace("--", "-");
    }
    let safe = safe.trim_matches('-');
    if safe.is_empty() {
        "meeting".to_string()
    } else {
        safe.chars().take(48).collect()
    }
}

struct RealRecording {
    session: CaptureSession,
    path: PathBuf,
    writer: Arc<Mutex<WavWriter>>,
    capture_error: Arc<Mutex<Option<String>>>,
}

struct RealRecordingStop {
    path: PathBuf,
    bytes: u64,
    capture_error: Option<String>,
}

fn remember_capture_error(slot: &Mutex<Option<String>>, message: String) {
    if let Ok(mut error) = slot.lock() {
        if error.is_none() {
            *error = Some(message.chars().take(512).collect());
        }
    }
}

fn finish_capture_file(
    writer: &Mutex<WavWriter>,
    capture_error: &Mutex<Option<String>>,
) -> (u64, Option<String>) {
    let mut bytes = 0;
    match writer.lock() {
        Ok(mut writer) => match writer.finalize() {
            Ok(length) => bytes = length,
            Err(error) => remember_capture_error(capture_error, format!("录音文件保存失败：{error}")),
        },
        Err(_) => remember_capture_error(capture_error, "录音文件状态不可用".to_string()),
    }
    if bytes <= 44 {
        remember_capture_error(capture_error, "麦克风没有录到有效音频帧".to_string());
    }
    let error = capture_error.lock().ok().and_then(|error| error.clone());
    (bytes, error)
}

impl RealRecording {
    fn start(path: PathBuf, pcm_sink: Option<HostPcmSink>) -> Result<Self, String> {
        if let Some(parent) = path.parent() {
            create_dir_all(parent).map_err(|err| format!("create wav parent {parent:?}: {err}"))?;
        }
        let writer = Arc::new(Mutex::new(
            WavWriter::create(&path).map_err(|err| format!("create wav {path:?}: {err}"))?,
        ));
        let sink_writer = Arc::clone(&writer);
        let capture_error = Arc::new(Mutex::new(None::<String>));
        let stream_error = Arc::clone(&capture_error);
        let write_error = Arc::clone(&capture_error);
        let resampler_slot = Arc::new(Mutex::new(None::<RatioResampler>));
        let sink_resampler = Arc::clone(&resampler_slot);

        let session = CaptureSession::start(
            CaptureOptions {
                device_name: None,
                on_stream_error: Some(Arc::new(move |err| {
                    eprintln!("[companion-type-recorder] stream error: {err}");
                    remember_capture_error(&stream_error, format!("麦克风录音中断：{err}"));
                })),
            },
            move |samples: &[f32], source_rate: u32| {
                let mut slot = match sink_resampler.lock() {
                    Ok(slot) => slot,
                    Err(_) => return,
                };
                let resampler = slot
                    .get_or_insert_with(|| RatioResampler::new(source_rate, TARGET_SAMPLE_RATE));
                let resampled = resampler.process(samples);
                if resampled.is_empty() {
                    return;
                }
                if let Ok(mut writer) = sink_writer.lock() {
                    if let Err(error) = writer.append_samples(&resampled) {
                        remember_capture_error(&write_error, format!("录音写入失败：{error}"));
                    }
                } else {
                    remember_capture_error(&write_error, "录音文件状态不可用".to_string());
                }
                if let Some(sink) = pcm_sink.as_ref() {
                    sink(&resampled);
                }
            },
        )
        .map_err(|err| err.to_string())?;

        Ok(Self { session, path, writer, capture_error })
    }

    fn stop(self) -> Result<RealRecordingStop, String> {
        if let Err(error) = self.session.stop() {
            remember_capture_error(&self.capture_error, format!("停止麦克风失败：{error}"));
        }
        let (bytes, capture_error) = finish_capture_file(&self.writer, &self.capture_error);
        Ok(RealRecordingStop {
            path: self.path,
            bytes,
            capture_error,
        })
    }
}

struct RatioResampler {
    source_rate: u64,
    target_rate: u64,
    accumulator: u64,
}

impl RatioResampler {
    fn new(source_rate: u32, target_rate: u32) -> Self {
        Self {
            source_rate: source_rate.max(1) as u64,
            target_rate: target_rate.max(1) as u64,
            accumulator: 0,
        }
    }

    fn process(&mut self, input: &[f32]) -> Vec<i16> {
        let mut output = Vec::new();
        for sample in input {
            self.accumulator += self.target_rate;
            while self.accumulator >= self.source_rate {
                self.accumulator -= self.source_rate;
                output.push(f32_to_i16(*sample));
            }
        }
        output
    }
}

fn f32_to_i16(sample: f32) -> i16 {
    (sample.clamp(-1.0, 1.0) * i16::MAX as f32) as i16
}

fn write_synthetic_wav(path: &PathBuf, duration_ms: u64) -> Result<(), String> {
    let mut writer =
        WavWriter::create(path).map_err(|err| format!("create wav {path:?}: {err}"))?;
    let samples = (TARGET_SAMPLE_RATE as u64 * duration_ms / 1000).max(1);
    let mut chunk = Vec::<i16>::with_capacity(1024);
    for index in 0..samples {
        let t = index as f32 / TARGET_SAMPLE_RATE as f32;
        chunk.push(f32_to_i16(
            (t * SYNTHETIC_HZ * std::f32::consts::TAU).sin() * 0.18,
        ));
        if chunk.len() >= 1024 {
            writer
                .append_samples(&chunk)
                .map_err(|err| format!("write wav sample: {err}"))?;
            chunk.clear();
        }
    }
    if !chunk.is_empty() {
        writer
            .append_samples(&chunk)
            .map_err(|err| format!("write wav sample: {err}"))?;
    }
    writer
        .finalize()
        .map_err(|err| format!("finalize wav {path:?}: {err}"))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::super::CompanionBackend;

    #[test]
    #[ignore]
    fn isolated_abrupt_host_recording_child() {
        let Some(path) = std::env::var_os("COMPANION_CRASH_MODEL_FILE") else { return; };
        let path = std::path::PathBuf::from(path);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        let _artifact = super::super::audio_artifacts::WriteLease::begin(
            &path, &path, super::super::audio_artifacts::Purpose::Recording).unwrap();
        let mut writer = WavWriter::create(&path).unwrap();
        writer.append_bytes(&vec![42u8; 32000]).unwrap();
        // Deliberately exit this isolated child without Drop/finalize.
        std::process::exit(0);
    }

    #[test]
    #[ignore]
    fn isolated_crash_during_recovery_child() {
        let Some(path) = std::env::var_os("COMPANION_CRASH_MODEL_FILE") else { return; };
        let result = super::super::host_interrupted_recovery::recover_copy(std::path::Path::new(&path));
        if std::env::var_os("COMPANION_TEST_RECOVERY_COLLISION").is_some() { assert!(result.is_err()); }
    }

    #[test]
    fn interrupted_recovery_can_retry_and_privacy_cleanup_without_touching_unknown_files() {
        for stage in ["empty-created", "header-written", "identity-committed", "delete-cleared"] {
            let root=std::env::temp_dir().join(format!("host-recovery-crash-{}-{}",stage,uuid::Uuid::new_v4()));
            std::fs::create_dir_all(&root).unwrap();
            let path=root.join("unfinished.wav");
            let exe=std::env::current_exe().unwrap();
            let child=std::process::Command::new(&exe)
                .args(["--exact","backend::host_recording::tests::isolated_abrupt_host_recording_child","--ignored"])
                .env("COMPANION_CRASH_MODEL_FILE",&path).env("COMPANION_TYPE_RECORDING_DIR",&root).output().unwrap();
            assert!(child.status.success());
            let raw=std::fs::read(&path).unwrap();
            let mut recovery=std::process::Command::new(&exe);
            recovery.args(["--exact","backend::host_recording::tests::isolated_crash_during_recovery_child","--ignored"])
                .env("COMPANION_CRASH_MODEL_FILE",&path).env("COMPANION_TYPE_RECORDING_DIR",&root);
            if stage == "header-written" { recovery.env("COMPANION_TEST_RECOVERY_CRASH_AFTER_HEADER","1"); }
            else { recovery.env("COMPANION_TEST_RECOVERY_FAILPOINT",stage); }
            let result=recovery.output().unwrap();
            assert!(result.status.success());
            assert!(!String::from_utf8_lossy(&result.stdout).contains("test result:"),"failpoint did not exit at {stage}");
            assert_eq!(std::fs::read(&path).unwrap(),raw);
            let orphans:Vec<_>=std::fs::read_dir(&root).unwrap().map(|entry|entry.unwrap().path())
                .filter(|p|p.file_name().unwrap().to_string_lossy().starts_with("recovered-")).collect();
            match stage {
                "empty-created" => { assert_eq!(orphans.len(),1); assert_eq!(std::fs::metadata(&orphans[0]).unwrap().len(),0); }
                "header-written" | "identity-committed" => assert!(orphans.is_empty(),"pending output should disappear at {stage}"),
                "delete-cleared" => { assert_eq!(orphans.len(),1); assert_eq!(std::fs::read(&orphans[0]).unwrap().len(),raw.len()); },
                _ => unreachable!(),
            }
            std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&root);
            let recovered=super::super::host_interrupted_recovery::recover_copy(&path).unwrap();
            let target=recovered.path.clone();drop(recovered);
            let unknown=root.join("unrelated.wav");std::fs::write(&unknown,b"private unrelated file").unwrap();
            let erased=super::super::audio_artifacts::erase(&root,&[target.to_string_lossy().to_string()],&[]);
            assert!(erased.is_ok(),"privacy cleanup after {stage}: {:?}",erased.as_ref().err());
            let report=erased.unwrap();
            assert!(!path.exists()&&!target.exists());
            if stage == "empty-created" {
                assert!(orphans[0].exists(),"unowned empty file retained");
                assert_eq!(std::fs::metadata(&orphans[0]).unwrap().len(),0);
                let orphan_key=super::super::audio_artifacts::reference_key(&orphans[0]).unwrap();
                assert!(report.retained_paths.iter().any(|p| super::super::audio_artifacts::reference_key(p).ok().as_ref()==Some(&orphan_key)));
                assert_eq!(report.unverified_empty, 1);
            } else if stage == "delete-cleared" { assert!(!orphans[0].exists()); }
            assert_eq!(std::fs::read(&unknown).unwrap(),b"private unrelated file");
            std::env::remove_var("COMPANION_TYPE_RECORDING_DIR");
        }
    }

    #[test]
    fn recovery_filename_collision_never_adopts_or_deletes_unknown_file() {
        let root=std::env::temp_dir().join(format!("host-recovery-collision-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        let path=root.join("unfinished.wav");
        let exe=std::env::current_exe().unwrap();
        let child=std::process::Command::new(&exe)
            .args(["--exact","backend::host_recording::tests::isolated_abrupt_host_recording_child","--ignored"])
            .env("COMPANION_CRASH_MODEL_FILE",&path).env("COMPANION_TYPE_RECORDING_DIR",&root).output().unwrap();
        assert!(child.status.success());
        let raw=std::fs::read(&path).unwrap();
        let collision=std::process::Command::new(&exe)
            .args(["--exact","backend::host_recording::tests::isolated_crash_during_recovery_child","--ignored"])
            .env("COMPANION_CRASH_MODEL_FILE",&path).env("COMPANION_TYPE_RECORDING_DIR",&root)
            .env("COMPANION_TEST_RECOVERY_COLLISION","1").output().unwrap();
        assert!(collision.status.success(),"{}",String::from_utf8_lossy(&collision.stderr));
        let manifest:serde_json::Value=serde_json::from_slice(&std::fs::read(root.join(".audio-artifacts.json")).unwrap()).unwrap();
        let item=manifest["files"].as_array().unwrap().iter().find(|item|item["purpose"]=="decodeTemporary").unwrap();
        assert_eq!(item["phase"],"prepared");assert!(item["identity"].is_null(),"unknown file must not be adopted");
        let unknown=root.join(item["file"].as_str().unwrap());
        assert_eq!(std::fs::read(&unknown).unwrap(),b"unrelated collision");
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&root);
        assert!(super::super::audio_artifacts::erase(&root,&[path.to_string_lossy().to_string()],&[]).is_err());
        assert_eq!(std::fs::read(&unknown).unwrap(),b"unrelated collision");
        assert_eq!(std::fs::read(&path).unwrap(),raw);
        std::env::remove_var("COMPANION_TYPE_RECORDING_DIR");
    }

    #[test]
    fn isolated_process_exit_keeps_raw_pcm_but_not_a_valid_wav() {
        let root = std::env::temp_dir().join(format!("host-crash-model-{}", std::process::id()));
        std::fs::create_dir_all(&root).unwrap();
        let path = root.join("unfinished.wav");
        assert!(!path.exists());
        let result = std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "backend::host_recording::tests::isolated_abrupt_host_recording_child", "--ignored"])
            .env("COMPANION_CRASH_MODEL_FILE", &path)
            .env("COMPANION_TYPE_RECORDING_DIR", &root)
            .output().unwrap();
        assert!(result.status.success());
        let bytes=std::fs::read(&path).unwrap();
        assert_eq!(bytes.len(), 32044);
        assert_eq!(&bytes[44..], &vec![42u8; 32000]);
        assert_eq!(u32::from_le_bytes(bytes[40..44].try_into().unwrap()), 0);
        assert!(super::super::meeting_workspace::validate_wav(&path).is_err());
        assert!(root.join(".audio-artifacts.json").exists(), "capture ownership must survive");
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &root);
        let recovered = super::super::host_interrupted_recovery::recover_copy(&path).unwrap();
        assert_eq!(recovered.bytes, 32044);
        assert_eq!(recovered.duration_ms, 1000);
        assert_ne!(recovered.path, path);
        let restored = std::fs::read(&recovered.path).unwrap();
        assert_eq!(&restored[44..], &bytes[44..]);
        assert_eq!(std::fs::read(&path).unwrap(), bytes, "raw original stays byte-for-byte intact");
        assert!(super::super::meeting_workspace::validate_wav(&recovered.path).is_ok());
        drop(recovered);
        let state_path = root.join("sessions.json");
        let mut fixture = crate::companion_v1::apply_fixture_control(
            crate::companion_v1::fixture_snapshot(),
            crate::control_request(crate::companion_v1::CompanionV1ControlAction::MeetingStart, Some("crashed-host".into()))).unwrap();
        let mut session = fixture.host.sessions.remove(0);
        session.id = "crashed-host".into(); session.source = "hostMicrophone".into();
        session.status = "recording".into(); session.stopped_at = None;
        session.audio_path = Some(path.to_string_lossy().to_string());
        session.audio_stored = false; session.audio_bytes = 0; session.chunks.clear();
        session.transcript_text = "保留之前的部分文字".into(); session.transcript_final = false;
        let expected = super::super::session_store::privacy_authorization(&session).unwrap();
        super::super::persistence::save_sessions_to(&state_path, &[session]).unwrap();
        super::super::host_interrupted_recovery::recover_session_at(&state_path, "crashed-host", &expected).unwrap();
        let saved = super::super::persistence::load_sessions_from(&state_path).unwrap();
        let row = &saved[0];
        assert!(row.audio_stored && row.retention.audio_cached && row.capture_incomplete);
        assert_eq!(row.duration_ms, 1000);
        assert!(row.stopped_at.is_none(), "the original stop time is unknown");
        assert_eq!(row.transcript_text, "保留之前的部分文字");
        assert!(!row.transcript_final);
        assert_eq!(row.pending_reason.as_deref(), Some("capture_interrupted"));
        let saved_copy = std::fs::read(row.audio_path.as_deref().unwrap()).unwrap();
        assert_eq!(&saved_copy[44..], &bytes[44..]);
        assert_eq!(std::fs::read(&path).unwrap(), bytes);
        let before_retry = std::fs::read(&state_path).unwrap();
        assert!(super::super::host_interrupted_recovery::recover_session_at(&state_path, "crashed-host", &expected).is_err());
        assert_eq!(std::fs::read(&state_path).unwrap(), before_retry, "repeat cannot replace the saved copy");
        let second = root.join("second-unfinished.wav");
        let second_child = std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "backend::host_recording::tests::isolated_abrupt_host_recording_child", "--ignored"])
            .env("COMPANION_CRASH_MODEL_FILE", &second)
            .env("COMPANION_TYPE_RECORDING_DIR", &root).output().unwrap();
        assert!(second_child.status.success());
        let second_raw = std::fs::read(&second).unwrap();
        let state2 = root.join("session-two.json");
        let mut second_session = row.clone();
        second_session.id = "second-host".into(); second_session.status = "recording".into();
        second_session.audio_path = Some(second.to_string_lossy().to_string());
        second_session.audio_bytes = 0; second_session.audio_stored = false;
        second_session.capture_incomplete = false; second_session.chunks.clear();
        second_session.recovery = Default::default(); second_session.pending_reason = None;
        super::super::persistence::save_sessions_to(&state2, &[second_session]).unwrap();
        std::env::set_var("COMPANION_TYPE_STATE_PATH", &state2);
        let backend = super::super::FixtureCompanionBackend::new();
        let req: crate::companion_v1::CompanionV1ControlRequest = serde_json::from_value(serde_json::json!({"action":"meetingRestoreAudio", "sessionId":"second-host"})).unwrap();
        let before_locked = std::fs::read(&state2).unwrap();
        let privacy_lock = super::super::library_lifecycle::action_lock(&state2).unwrap();
        assert!(backend.apply_control(req.clone()).is_err(), "privacy action prevents simultaneous recovery");
        assert_eq!(std::fs::read(&state2).unwrap(), before_locked);
        assert_eq!(std::fs::read(&second).unwrap(), second_raw);
        drop(privacy_lock);
        let restored = backend.apply_control(req).unwrap();
        let restored_row = restored.host.sessions.iter().find(|s| s.id == "second-host").unwrap();
        assert!(restored_row.audio_stored && restored_row.capture_incomplete);
        assert_eq!(restored_row.pending_reason.as_deref(), Some("capture_interrupted"));
        assert_eq!(&std::fs::read(restored_row.audio_path.as_deref().unwrap()).unwrap()[44..], &second_raw[44..]);
        assert_eq!(std::fs::read(&second).unwrap(), second_raw);
        std::env::remove_var("COMPANION_TYPE_STATE_PATH");
        let third = root.join("third-unfinished.wav");
        let third_child = std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "backend::host_recording::tests::isolated_abrupt_host_recording_child", "--ignored"])
            .env("COMPANION_CRASH_MODEL_FILE", &third)
            .env("COMPANION_TYPE_RECORDING_DIR", &root).output().unwrap();
        assert!(third_child.status.success());
        let third_raw = std::fs::read(&third).unwrap();
        let state3 = root.join("session-three.json");
        let mut third_session = row.clone();
        third_session.id = "third-host".into(); third_session.status = "recording".into();
        third_session.audio_path = Some(third.to_string_lossy().to_string());
        third_session.audio_bytes = 0; third_session.audio_stored = false;
        third_session.capture_incomplete = false; third_session.chunks.clear();
        third_session.recovery = Default::default(); third_session.pending_reason = None;
        let third_auth = super::super::session_store::privacy_authorization(&third_session).unwrap();
        super::super::persistence::save_sessions_to(&state3, &[third_session]).unwrap();
        let raced = super::super::host_interrupted_recovery::recover_session_with(&state3, "third-host", &third_auth, || {
            super::super::session_store::update_checked(&state3, |rows| {rows.clear(); Ok(())})
        });
        assert!(raced.is_err(), "a removed session must not be recreated after copying");
        let remaining = super::super::persistence::load_sessions_from(&state3).unwrap();
        assert!(remaining.is_empty());
        assert_eq!(std::fs::read(&third).unwrap(), third_raw, "racing removal never mutates the original");


        let unknown = root.join("unknown.wav");
        std::fs::write(&unknown, &bytes).unwrap();
        assert!(super::super::host_interrupted_recovery::recover_copy(&unknown).is_err());
        assert_eq!(std::fs::read(&unknown).unwrap(), bytes);
        let busy = root.join("still-recording.wav");
        let busy_lease = super::super::audio_artifacts::WriteLease::begin(
            &busy, &busy, super::super::audio_artifacts::Purpose::Recording).unwrap();
        let mut busy_writer = WavWriter::create(&busy).unwrap();
        busy_writer.append_bytes(&[4u8; 200]).unwrap();
        let before_busy = std::fs::read(&busy).unwrap();
        assert!(super::super::host_interrupted_recovery::recover_copy(&busy).is_err(), "active writer must block recovery");
        assert_eq!(std::fs::read(&busy).unwrap(), before_busy);
        drop(busy_writer); drop(busy_lease);
        let bad = root.join("malformed.wav");
        let bad_lease = super::super::audio_artifacts::WriteLease::begin(
            &bad, &bad, super::super::audio_artifacts::Purpose::Recording).unwrap();
        let mut corrupt = bytes.clone(); corrupt[24] ^= 1;
        std::fs::write(&bad, &corrupt).unwrap();
        drop(bad_lease);
        assert!(super::super::host_interrupted_recovery::recover_copy(&bad).is_err(), "unknown format must not be guessed");
        assert_eq!(std::fs::read(&bad).unwrap(), corrupt);
        let finalized = root.join("finalized-before-index.wav");
        let finalized_lease = super::super::audio_artifacts::WriteLease::begin(
            &finalized, &finalized, super::super::audio_artifacts::Purpose::Recording).unwrap();
        let mut finalized_writer = WavWriter::create(&finalized).unwrap();
        finalized_writer.append_bytes(&[8u8; 200]).unwrap();
        finalized_writer.finalize().unwrap(); drop(finalized_writer); drop(finalized_lease);
        let finalized_bytes = std::fs::read(&finalized).unwrap();
        let finalized_copy = super::super::host_interrupted_recovery::recover_copy(&finalized).unwrap();
        assert_eq!(std::fs::read(&finalized_copy.path).unwrap(), finalized_bytes);
        assert_eq!(std::fs::read(&finalized).unwrap(), finalized_bytes);
        drop(finalized_copy);
        // Explicit privacy erasure of the restored recording must also reach
        // the exact raw original, without touching an unrelated unknown file.
        let retained_copy = std::path::PathBuf::from(row.audio_path.as_deref().unwrap());
        assert!(root.canonicalize().unwrap().starts_with(std::env::temp_dir().canonicalize().unwrap()));
        assert!(path.canonicalize().unwrap().starts_with(root.canonicalize().unwrap()));
        assert!(retained_copy.canonicalize().unwrap().starts_with(root.canonicalize().unwrap()));
        let erased = super::super::audio_artifacts::erase(&root, &[retained_copy.to_string_lossy().to_string()], &[]).unwrap();
        assert!(erased.deleted >= 2);
        assert!(!path.exists() && !retained_copy.exists());
        assert_eq!(std::fs::read(&unknown).unwrap(), bytes);
        std::env::remove_var("COMPANION_TYPE_RECORDING_DIR");
    }

    #[test]
    fn synthetic_recording_writes_valid_wav() {
        let root = std::env::temp_dir().join("companion-type-host-recording-test");
        let path = root.join("synthetic.wav");
        let _ = std::fs::remove_file(&path);
        write_synthetic_wav(&path, 250).unwrap();
        let bytes = std::fs::read(&path).unwrap();
        assert!(bytes.len() > 44);
        assert_eq!(&bytes[0..4], b"RIFF");
        assert_eq!(&bytes[8..12], b"WAVE");
        assert_eq!(&bytes[12..16], b"fmt ");
        assert_eq!(&bytes[36..40], b"data");
        assert_eq!(u16::from_le_bytes([bytes[22], bytes[23]]), 1);
        assert_eq!(
            u32::from_le_bytes([bytes[24], bytes[25], bytes[26], bytes[27]]),
            TARGET_SAMPLE_RATE
        );
    }

    #[test]
    fn manager_synthetic_mode_creates_session_file_on_stop() {
        let root = std::env::temp_dir().join("companion-type-host-recording-manager-test");
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &root);
        let manager = HostRecordingManager::new();
        let start = manager.start("session-1", "Meeting Title").unwrap();
        assert_eq!(start.mode, "synthetic");
        let stop = manager.stop(Some("session-1")).unwrap().unwrap();
        assert_eq!(stop.session_id, "session-1");
        assert!(stop.path.exists());
        assert!(stop.bytes > 44);
        std::env::remove_var("COMPANION_TYPE_RECORDING_DIR");
    }

    #[test]
    fn microphone_failure_never_creates_a_synthetic_success() {
        for mode in ["real", "real-with-synthetic-fallback"] {
            let manager = HostRecordingManager::new();
            let error = manager.start_with_mode("failed-mic", "Failure", mode,
                |_, _| Err("capture device unavailable".to_string())).unwrap_err();
            assert!(error.contains("capture device unavailable"));
            assert!(manager.stop(Some("failed-mic")).unwrap().is_none());
            assert!(manager.active.lock().unwrap().is_none());
        }
    }

    #[test]
    fn interrupted_capture_keeps_decodable_audio_and_reports_the_original_failure() {
        let path = std::env::temp_dir().join("companion-type-interrupted-capture.wav");
        let writer = Mutex::new(WavWriter::create(&path).unwrap());
        writer.lock().unwrap().append_samples(&[100, -100, 50]).unwrap();
        let errors = Mutex::new(None);
        remember_capture_error(&errors, "麦克风已拔出".to_string());
        remember_capture_error(&errors, "后续错误".to_string());
        let (length, error) = finish_capture_file(&writer, &errors);
        assert_eq!(length, 50);
        assert_eq!(error.as_deref(), Some("麦克风已拔出"));
        let wav = std::fs::read(&path).unwrap();
        assert_eq!(u32::from_le_bytes(wav[40..44].try_into().unwrap()), 6);
        assert_eq!(&wav[44..], &[100, 0, 156, 255, 50, 0]);
    }

    #[test]
    fn capture_without_frames_is_not_reported_as_success() {
        let path = std::env::temp_dir().join("companion-type-no-capture-frames.wav");
        let writer = Mutex::new(WavWriter::create(&path).unwrap());
        let (length, error) = finish_capture_file(&writer, &Mutex::new(None));
        assert_eq!(length, 44);
        assert!(error.unwrap().contains("没有录到有效音频帧"));
    }

    #[test]
    fn duplicate_start_and_wrong_stop_preserve_the_original_recording() {
        let manager = HostRecordingManager::new();
        let original = manager.start_with_mode("original", "Original", "synthetic", |_, _| unreachable!()).unwrap();
        assert!(manager.start_with_mode("replacement", "Replacement", "synthetic", |_, _| unreachable!()).is_err());
        assert!(manager.stop(Some("other-session")).is_err());
        let stop = manager.stop(Some("original")).unwrap().unwrap();
        assert_eq!(stop.session_id, "original");
        assert_eq!(stop.path, original.path);
        assert!(stop.bytes > 44);
    }

    #[test]
    fn real_microphone_recording_smoke() {
        if std::env::var("COMPANION_TYPE_REAL_MIC_ACCEPTANCE")
            .ok()
            .as_deref()
            != Some("1")
        {
            return;
        }

        let root = std::env::temp_dir().join("companion-type-real-microphone-acceptance");
        std::env::set_var("COMPANION_TYPE_HOST_RECORDING_MODE", "real");
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &root);

        let manager = HostRecordingManager::new();
        let start = manager
            .start("real-mic-session", "Real Microphone Acceptance")
            .expect("real microphone recording should start");
        assert_eq!(start.mode, "host-microphone");
        std::thread::sleep(std::time::Duration::from_millis(1800));
        let stop = manager
            .stop(Some("real-mic-session"))
            .expect("real microphone recording should stop")
            .expect("real microphone recording should be active");

        let bytes = std::fs::read(&stop.path).expect("real microphone wav should be readable");
        assert!(bytes.len() > 44, "real microphone WAV should contain data");
        assert_eq!(&bytes[0..4], b"RIFF");
        assert_eq!(&bytes[8..12], b"WAVE");
        assert_eq!(&bytes[36..40], b"data");
        assert_eq!(u16::from_le_bytes([bytes[22], bytes[23]]), 1);
        assert_eq!(
            u32::from_le_bytes([bytes[24], bytes[25], bytes[26], bytes[27]]),
            TARGET_SAMPLE_RATE
        );
        let data_bytes = u32::from_le_bytes([bytes[40], bytes[41], bytes[42], bytes[43]]);
        assert!(
            data_bytes > 0,
            "real microphone WAV data chunk should be non-empty"
        );
        println!("real_microphone_wav={}", stop.path.to_string_lossy());

        std::env::remove_var("COMPANION_TYPE_HOST_RECORDING_MODE");
        std::env::remove_var("COMPANION_TYPE_RECORDING_DIR");
    }

    #[test]
    fn real_microphone_recording_soak() {
        if std::env::var("COMPANION_TYPE_REAL_MIC_SOAK_ACCEPTANCE")
            .ok()
            .as_deref()
            != Some("1")
        {
            return;
        }

        let requested_seconds = std::env::var("COMPANION_TYPE_REAL_MIC_SOAK_SECONDS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(3600)
            .max(1);
        let root = std::env::temp_dir().join("companion-type-real-microphone-soak");
        std::env::set_var("COMPANION_TYPE_HOST_RECORDING_MODE", "real");
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &root);

        let manager = HostRecordingManager::new();
        let start = manager
            .start("real-mic-soak", "Real Microphone Soak")
            .expect("real microphone soak should start");
        assert_eq!(start.mode, "host-microphone");
        std::thread::sleep(std::time::Duration::from_secs(requested_seconds));
        let stop = manager
            .stop(Some("real-mic-soak"))
            .expect("real microphone soak should stop")
            .expect("real microphone soak should be active");
        assert_eq!(stop.mode, "host-microphone");

        let bytes = std::fs::read(&stop.path).expect("real microphone soak WAV should be readable");
        assert!(
            bytes.len() > 44,
            "real microphone soak WAV should contain data"
        );
        assert_eq!(&bytes[0..4], b"RIFF");
        assert_eq!(&bytes[8..12], b"WAVE");
        assert_eq!(&bytes[36..40], b"data");
        assert_eq!(u16::from_le_bytes([bytes[22], bytes[23]]), 1);
        assert_eq!(
            u32::from_le_bytes([bytes[24], bytes[25], bytes[26], bytes[27]]),
            TARGET_SAMPLE_RATE
        );
        let data_bytes = u32::from_le_bytes([bytes[40], bytes[41], bytes[42], bytes[43]]);
        assert!(
            data_bytes > 0,
            "real microphone soak WAV data chunk should be non-empty"
        );

        println!("real_microphone_soak_wav={}", stop.path.to_string_lossy());
        println!("real_microphone_soak_mode={}", stop.mode);
        println!("real_microphone_soak_duration_ms={}", stop.duration_ms);
        println!("real_microphone_soak_bytes={}", stop.bytes);
        println!("real_microphone_soak_requested_seconds={requested_seconds}");

        std::env::remove_var("COMPANION_TYPE_HOST_RECORDING_MODE");
        std::env::remove_var("COMPANION_TYPE_RECORDING_DIR");
    }
}
