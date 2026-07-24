//! Host microphone recording backend.
//!
//! The product path is host-owned long recording. Firmware remains a short
//! cache/trigger, while this backend records a 16 kHz mono WAV on the host.
//! Capture, sample conversion, and the WAV container come from the platform
//! `denzic-host-audio-v1-core` crate; this module keeps session management,
//! file placement, the ratio resampler, and the synthetic fallback mode.

use std::fs::create_dir_all;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

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
}

struct ActiveHostRecording {
    session_id: String,
    path: PathBuf,
    started_at: Instant,
    mode: ActiveHostRecordingMode,
}

enum ActiveHostRecordingMode {
    Real(RealRecording),
    Synthetic,
}

pub struct HostRecordingManager {
    active: Mutex<Option<ActiveHostRecording>>,
}

impl HostRecordingManager {
    pub fn new() -> Self {
        Self {
            active: Mutex::new(None),
        }
    }

    pub fn start(&self, session_id: &str, title: &str) -> Result<HostRecordingStart, String> {
        let mut active = self
            .active
            .lock()
            .map_err(|_| "host recording state lock failed".to_string())?;
        if let Some(recording) = active.take() {
            let _ = stop_active_recording(recording);
        }

        let path = recording_path(session_id, title)?;
        let requested_mode =
            std::env::var("COMPANION_TYPE_HOST_RECORDING_MODE").unwrap_or_else(|_| {
                if cfg!(test) {
                    "synthetic".to_string()
                } else {
                    "real-with-synthetic-fallback".to_string()
                }
            });

        let (mode, mode_label) = if requested_mode.eq_ignore_ascii_case("synthetic") {
            (ActiveHostRecordingMode::Synthetic, "synthetic".to_string())
        } else {
            match RealRecording::start(path.clone()) {
                Ok(recording) => (
                    ActiveHostRecordingMode::Real(recording),
                    "host-microphone".to_string(),
                ),
                Err(err) if requested_mode.eq_ignore_ascii_case("real") => return Err(err),
                Err(_) => (
                    ActiveHostRecordingMode::Synthetic,
                    "synthetic-fallback".to_string(),
                ),
            }
        };

        *active = Some(ActiveHostRecording {
            session_id: session_id.to_string(),
            path: path.clone(),
            started_at: Instant::now(),
            mode,
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
        let mut active = self
            .active
            .lock()
            .map_err(|_| "host recording state lock failed".to_string())?;
        let Some(recording) = active.take() else {
            return Ok(None);
        };
        if let Some(session_id) = requested_session_id {
            if recording.session_id != session_id {
                let result = stop_active_recording(recording);
                return result.map(Some);
            }
        }
        stop_active_recording(recording).map(Some)
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
    let (path, bytes, mode) = match recording.mode {
        ActiveHostRecordingMode::Real(real) => {
            let stop = real.stop()?;
            (stop.path, stop.bytes, "host-microphone".to_string())
        }
        ActiveHostRecordingMode::Synthetic => {
            write_synthetic_wav(&recording.path, elapsed_ms.max(1_000))?;
            let bytes = std::fs::metadata(&recording.path)
                .map_err(|err| format!("read synthetic wav metadata: {err}"))?
                .len();
            (recording.path, bytes, "synthetic".to_string())
        }
    };

    Ok(HostRecordingStop {
        session_id: recording.session_id,
        path,
        duration_ms: elapsed_ms,
        bytes,
        mode,
    })
}

fn recording_path(session_id: &str, title: &str) -> Result<PathBuf, String> {
    let root = std::env::var("COMPANION_TYPE_RECORDING_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            std::env::temp_dir()
                .join("companion-type")
                .join("recordings")
        });
    create_dir_all(&root).map_err(|err| format!("create recording dir {root:?}: {err}"))?;
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|err| format!("clock before epoch: {err}"))?
        .as_secs();
    let safe_title = sanitize_file_stem(title);
    Ok(root.join(format!("{stamp}-{session_id}-{safe_title}.wav")))
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
}

struct RealRecordingStop {
    path: PathBuf,
    bytes: u64,
}

impl RealRecording {
    fn start(path: PathBuf) -> Result<Self, String> {
        if let Some(parent) = path.parent() {
            create_dir_all(parent).map_err(|err| format!("create wav parent {parent:?}: {err}"))?;
        }
        let writer = Arc::new(Mutex::new(
            WavWriter::create(&path).map_err(|err| format!("create wav {path:?}: {err}"))?,
        ));
        let sink_writer = Arc::clone(&writer);
        let resampler_slot = Arc::new(Mutex::new(None::<RatioResampler>));
        let sink_resampler = Arc::clone(&resampler_slot);

        let session = CaptureSession::start(
            CaptureOptions {
                device_name: None,
                on_stream_error: Some(Arc::new(|err| {
                    eprintln!("[companion-type-recorder] stream error: {err}");
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
                    let _ = writer.append_samples(&resampled);
                }
            },
        )
        .map_err(|err| err.to_string())?;

        Ok(Self { session, path })
    }

    fn stop(self) -> Result<RealRecordingStop, String> {
        self.session.stop().map_err(|err| err.to_string())?;
        let bytes = std::fs::metadata(&self.path)
            .map_err(|err| format!("read wav metadata: {err}"))?
            .len();
        Ok(RealRecordingStop {
            path: self.path,
            bytes,
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
