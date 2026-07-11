//! Host microphone recording backend.
//!
//! The product path is host-owned long recording. Firmware remains a short
//! cache/trigger, while this backend records a 16 kHz mono WAV on the host.

use std::fs::{create_dir_all, File};
use std::io::{Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{SampleFormat, StreamConfig};

const TARGET_SAMPLE_RATE: u32 = 16_000;
const TARGET_CHANNELS: u16 = 1;
const BITS_PER_SAMPLE: u16 = 16;
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
    Real(HostRecorderHandle),
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
            match HostRecorderHandle::start(path.clone()) {
                Ok(handle) => (
                    ActiveHostRecordingMode::Real(handle),
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
        ActiveHostRecordingMode::Real(handle) => {
            let stop = handle.stop()?;
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

struct HostRecorderHandle {
    stop_flag: Arc<AtomicBool>,
    join_handle: Option<JoinHandle<Result<u64, String>>>,
    path: PathBuf,
}

struct HostRecorderStop {
    path: PathBuf,
    bytes: u64,
}

impl HostRecorderHandle {
    fn start(path: PathBuf) -> Result<Self, String> {
        let writer = Arc::new(Mutex::new(WavWriter::create(&path)?));
        let stop_flag = Arc::new(AtomicBool::new(false));
        let stop_for_thread = Arc::clone(&stop_flag);
        let writer_for_thread = Arc::clone(&writer);
        let (startup_tx, startup_rx) = mpsc::channel::<Result<(), String>>();

        let join_handle = thread::Builder::new()
            .name("companion-type-host-recorder".to_string())
            .spawn(move || run_audio_thread(stop_for_thread, writer_for_thread, startup_tx))
            .map_err(|err| format!("spawn host recorder thread: {err}"))?;

        startup_rx
            .recv_timeout(Duration::from_secs(5))
            .map_err(|err| format!("host recorder startup timeout: {err}"))??;

        Ok(Self {
            stop_flag,
            join_handle: Some(join_handle),
            path,
        })
    }

    fn stop(mut self) -> Result<HostRecorderStop, String> {
        self.stop_flag.store(true, Ordering::SeqCst);
        self.join_handle
            .take()
            .ok_or_else(|| "host recorder thread already joined".to_string())?
            .join()
            .map_err(|_| "host recorder thread panicked".to_string())??;
        let bytes = std::fs::metadata(&self.path)
            .map_err(|err| format!("read wav metadata: {err}"))?
            .len();
        Ok(HostRecorderStop {
            path: self.path,
            bytes,
        })
    }
}

fn run_audio_thread(
    stop_flag: Arc<AtomicBool>,
    writer: Arc<Mutex<WavWriter>>,
    startup_tx: mpsc::Sender<Result<(), String>>,
) -> Result<u64, String> {
    let host = cpal::default_host();
    let device = host
        .default_input_device()
        .ok_or_else(|| "no default input microphone".to_string());
    let device = match device {
        Ok(device) => device,
        Err(err) => {
            let _ = startup_tx.send(Err(err.clone()));
            return Err(err);
        }
    };
    let supported_config = match device.default_input_config() {
        Ok(config) => config,
        Err(err) => {
            let message = format!("read default input config: {err}");
            let _ = startup_tx.send(Err(message.clone()));
            return Err(message);
        }
    };

    let stream_config: StreamConfig = supported_config.clone().into();
    let sample_rate = stream_config.sample_rate.0;
    let channels = stream_config.channels as usize;
    let err_fn = |err| eprintln!("[companion-type-recorder] stream error: {err}");

    let stream_result = match supported_config.sample_format() {
        SampleFormat::F32 => build_stream::<f32>(
            &device,
            &stream_config,
            channels,
            sample_rate,
            writer,
            err_fn,
        ),
        SampleFormat::I16 => build_stream::<i16>(
            &device,
            &stream_config,
            channels,
            sample_rate,
            writer,
            err_fn,
        ),
        SampleFormat::U16 => build_stream::<u16>(
            &device,
            &stream_config,
            channels,
            sample_rate,
            writer,
            err_fn,
        ),
        other => Err(format!("unsupported input sample format: {other:?}")),
    };

    let stream = match stream_result {
        Ok(stream) => stream,
        Err(err) => {
            let _ = startup_tx.send(Err(err.clone()));
            return Err(err);
        }
    };

    if let Err(err) = stream.play() {
        let message = format!("start input stream: {err}");
        let _ = startup_tx.send(Err(message.clone()));
        return Err(message);
    }
    let _ = startup_tx.send(Ok(()));

    while !stop_flag.load(Ordering::SeqCst) {
        thread::sleep(Duration::from_millis(25));
    }
    drop(stream);

    Ok(0)
}

trait CompanionSample {
    fn to_f32_sample(self) -> f32;
}

impl CompanionSample for f32 {
    fn to_f32_sample(self) -> f32 {
        self.clamp(-1.0, 1.0)
    }
}

impl CompanionSample for i16 {
    fn to_f32_sample(self) -> f32 {
        self as f32 / i16::MAX as f32
    }
}

impl CompanionSample for u16 {
    fn to_f32_sample(self) -> f32 {
        (self as f32 - 32768.0) / 32768.0
    }
}

fn build_stream<T>(
    device: &cpal::Device,
    config: &StreamConfig,
    channels: usize,
    source_rate: u32,
    writer: Arc<Mutex<WavWriter>>,
    err_fn: impl Fn(cpal::StreamError) + Send + 'static,
) -> Result<cpal::Stream, String>
where
    T: cpal::SizedSample + CompanionSample + Send + 'static,
{
    let mut resampler = RatioResampler::new(source_rate, TARGET_SAMPLE_RATE);
    device
        .build_input_stream(
            config,
            move |data: &[T], _| {
                let mut mono = Vec::with_capacity(data.len() / channels.max(1));
                for frame in data.chunks(channels.max(1)) {
                    let sum: f32 = frame.iter().map(|sample| sample.to_f32_sample()).sum();
                    mono.push(sum / frame.len().max(1) as f32);
                }
                let samples = resampler.process(&mono);
                if samples.is_empty() {
                    return;
                }
                if let Ok(mut writer) = writer.lock() {
                    let _ = writer.write_samples(&samples);
                }
            },
            err_fn,
            None,
        )
        .map_err(|err| format!("build input stream: {err}"))
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

struct WavWriter {
    file: File,
    data_bytes: u32,
}

impl WavWriter {
    fn create(path: &Path) -> Result<Self, String> {
        if let Some(parent) = path.parent() {
            create_dir_all(parent).map_err(|err| format!("create wav parent {parent:?}: {err}"))?;
        }
        let mut file = File::create(path).map_err(|err| format!("create wav {path:?}: {err}"))?;
        write_wav_header(&mut file, 0)?;
        Ok(Self {
            file,
            data_bytes: 0,
        })
    }

    fn write_samples(&mut self, samples: &[i16]) -> Result<(), String> {
        for sample in samples {
            self.file
                .write_all(&sample.to_le_bytes())
                .map_err(|err| format!("write wav sample: {err}"))?;
            self.data_bytes = self.data_bytes.saturating_add(2);
        }
        Ok(())
    }

    fn finalize(&mut self) -> Result<u64, String> {
        write_wav_header(&mut self.file, self.data_bytes)?;
        self.file
            .seek(SeekFrom::End(0))
            .map_err(|err| format!("seek wav end: {err}"))
    }
}

impl Drop for WavWriter {
    fn drop(&mut self) {
        let _ = self.finalize();
    }
}

fn write_wav_header(file: &mut File, data_bytes: u32) -> Result<(), String> {
    let byte_rate = TARGET_SAMPLE_RATE * TARGET_CHANNELS as u32 * BITS_PER_SAMPLE as u32 / 8;
    let block_align = TARGET_CHANNELS * BITS_PER_SAMPLE / 8;
    let riff_size = 36u32.saturating_add(data_bytes);

    file.seek(SeekFrom::Start(0))
        .map_err(|err| format!("seek wav header: {err}"))?;
    file.write_all(b"RIFF")
        .map_err(|err| format!("write riff: {err}"))?;
    file.write_all(&riff_size.to_le_bytes())
        .map_err(|err| format!("write riff size: {err}"))?;
    file.write_all(b"WAVEfmt ")
        .map_err(|err| format!("write wave fmt: {err}"))?;
    file.write_all(&16u32.to_le_bytes())
        .map_err(|err| format!("write fmt size: {err}"))?;
    file.write_all(&1u16.to_le_bytes())
        .map_err(|err| format!("write pcm tag: {err}"))?;
    file.write_all(&TARGET_CHANNELS.to_le_bytes())
        .map_err(|err| format!("write channels: {err}"))?;
    file.write_all(&TARGET_SAMPLE_RATE.to_le_bytes())
        .map_err(|err| format!("write sample rate: {err}"))?;
    file.write_all(&byte_rate.to_le_bytes())
        .map_err(|err| format!("write byte rate: {err}"))?;
    file.write_all(&block_align.to_le_bytes())
        .map_err(|err| format!("write block align: {err}"))?;
    file.write_all(&BITS_PER_SAMPLE.to_le_bytes())
        .map_err(|err| format!("write bits per sample: {err}"))?;
    file.write_all(b"data")
        .map_err(|err| format!("write data tag: {err}"))?;
    file.write_all(&data_bytes.to_le_bytes())
        .map_err(|err| format!("write data size: {err}"))?;
    file.seek(SeekFrom::End(0))
        .map_err(|err| format!("seek wav data end: {err}"))?;
    Ok(())
}

fn write_synthetic_wav(path: &Path, duration_ms: u64) -> Result<(), String> {
    let mut writer = WavWriter::create(path)?;
    let samples = (TARGET_SAMPLE_RATE as u64 * duration_ms / 1000).max(1);
    let mut chunk = Vec::<i16>::with_capacity(1024);
    for index in 0..samples {
        let t = index as f32 / TARGET_SAMPLE_RATE as f32;
        chunk.push(f32_to_i16(
            (t * SYNTHETIC_HZ * std::f32::consts::TAU).sin() * 0.18,
        ));
        if chunk.len() >= 1024 {
            writer.write_samples(&chunk)?;
            chunk.clear();
        }
    }
    if !chunk.is_empty() {
        writer.write_samples(&chunk)?;
    }
    writer.finalize()?;
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
        std::thread::sleep(Duration::from_millis(1800));
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
        std::thread::sleep(Duration::from_secs(requested_seconds));
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
