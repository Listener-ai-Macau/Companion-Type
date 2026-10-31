//! Experimental two-source meeting recorder. Product session persistence,
//! replay, transcription and the explicit UI choice must be connected before
//! this module can be used as an end-user feature.
#[cfg(test)]
use std::fs;
use std::path::Path;
use std::io::Read;
use std::sync::{mpsc, Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Duration;
use denzic_host_audio_v1_core::capture::{CaptureOptions, CaptureSession, TimedCaptureInfo};
use super::host_recording::RatioResampler;
use super::meeting_audio_timeline::Timeline;
use super::meeting_audio_tracks::{TrackPart, TrackWriter};

const SAMPLE_RATE: u32 = 16_000;
const MIC_START_TIMEOUT: Duration = Duration::from_secs(5);
// The audio callbacks must not wait for file creation, writes, or fsync.
// Keep only a short backlog; if storage cannot catch up, preserve the audio
// already accepted and report the interruption instead of silently dropping it.
const QUEUED_PACKETS: usize = 512;

struct Packet {
    system: bool,
    pcm: Vec<f32>,
    rate: u32,
    info: TimedCaptureInfo,
}

enum WorkerMessage { Packet(Packet), Finish }

type SharedFailure = Arc<Mutex<Option<String>>>;

fn record_failure(failure: &SharedFailure, error: String) {
    if let Ok(mut slot) = failure.lock() {
        if slot.is_none() { *slot = Some(error); }
    }
}

#[derive(Clone)]
struct PacketSink {
    sender: mpsc::SyncSender<WorkerMessage>,
    failure: SharedFailure,
}

impl PacketSink {
    fn submit(&self, system: bool, pcm: &[f32], rate: u32, info: TimedCaptureInfo) {
        if self.failure.lock().map(|error| error.is_some()).unwrap_or(true) { return; }
        let packet = Packet { system, pcm: pcm.to_vec(), rate, info };
        match self.sender.try_send(WorkerMessage::Packet(packet)) {
            Ok(()) => (),
            Err(mpsc::TrySendError::Full(_)) => record_failure(&self.failure,
                "录音保存跟不上采集，已录内容保留。".into()),
            Err(mpsc::TrySendError::Disconnected(_)) => record_failure(&self.failure,
                "录音处理已停止，已录内容保留。".into()),
        }
    }
}

fn finish_worker(sink: PacketSink, worker: JoinHandle<State>) -> Result<State, String> {
    let failure = Arc::clone(&sink.failure);
    // An explicit finish also handles a timed-out device startup whose
    // underlying capture thread might still hold a sender clone.
    let _ = sink.sender.send(WorkerMessage::Finish);
    drop(sink);
    let mut state = worker.join().map_err(|_| "录音处理线程意外停止，原文件保留".to_string())?;
    let error = failure.lock().map(|error| error.clone())
        .unwrap_or_else(|_| Some("会议录音状态不可用，已录内容保留。".into()));
    if let Some(error) = error { state.fail(error); }
    Ok(state)
}

struct Track {
    timeline: Timeline,
    writer: TrackWriter,
    resampler: Option<RatioResampler>,
}
impl Track {
    fn push(&mut self, offset: i64, input: &[f32], rate: u32) -> Result<(), String> {
        let pcm = self.resampler.get_or_insert_with(|| RatioResampler::new(rate, SAMPLE_RATE)).process(input);
        self.timeline.append(offset, &pcm, |samples| self.writer.append(samples)).map_err(|e| e.to_string())
    }
    fn pad(&mut self, end: u64) -> Result<(), String> {
        self.timeline.finish(end, |samples| self.writer.append(samples)).map_err(|e| e.to_string())
    }
}

struct State {
    origin: Option<TimedCaptureInfo>,
    mic: Track,
    system: Track,
    error: Option<String>,
    discontinuity: bool,
    ready: Option<mpsc::SyncSender<Result<(), String>>>,
}
impl State {
    fn fail(&mut self, error: String) {
        if self.error.is_none() { self.error = Some(error.clone()); }
        if let Some(ready) = self.ready.take() { let _ = ready.try_send(Err(error)); }
    }
    fn packet(&mut self, system: bool, pcm: &[f32], rate: u32, info: TimedCaptureInfo) {
        if self.error.is_some() { return; }
        if info.captured_at.is_none() { self.fail("录音时间无法确认，已保留现有文件".into()); return; }
        if !system && self.origin.is_none() { self.origin = Some(info); }
        let Some(origin) = self.origin else { self.fail("录音时间基准尚未准备好".into()); return; };
        let Some(offset) = info.sample_offset_since(&origin, SAMPLE_RATE) else {
            self.fail("录音时间无法对齐，已保留现有文件".into()); return;
        };
        self.discontinuity |= info.discontinuity;
        let track = if system { &mut self.system } else { &mut self.mic };
        if let Err(error) = track.push(offset, pcm, rate) { self.fail(format!("录音写入失败：{error}")); return; }
        if !system { if let Some(ready) = self.ready.take() { let _ = ready.try_send(Ok(())); } }
    }
}

#[allow(dead_code)]
pub(super) struct Capture {
    mic: CaptureSession,
    system: CaptureSession,
    sink: PacketSink,
    worker: JoinHandle<State>,
}

#[allow(dead_code)]
pub(super) struct CaptureResult {
    pub(super) microphone: Vec<TrackPart>,
    pub(super) system: Vec<TrackPart>,
    pub(super) discontinuity: bool,
    pub(super) error: Option<String>,
}

impl CaptureResult {
    /// Prepare the exact files for an atomic session-index update. This does
    /// not itself commit the session or authorize removal of any file.
    #[allow(dead_code)]
    pub(super) fn into_session_tracks(self, root: &Path) -> Result<crate::companion_v1::CompanionV1MeetingTracks, String> {
        use crate::companion_v1::{CompanionV1MeetingTrackPart, CompanionV1MeetingTracks};
        if !root.is_absolute() { return Err("会议保存位置无效".into()); }
        let parent = root.parent().ok_or("会议保存位置无效")?.canonicalize().map_err(|_| "会议保存目录不可用")?;
        let prefix = root.file_name().and_then(|s| s.to_str()).ok_or("会议保存名称无效")?;
        let convert = |parts: Vec<TrackPart>, source: &str| -> Result<(Vec<CompanionV1MeetingTrackPart>, u64), String> {
            let mut expected = 0u64;
            let mut result = Vec::new();
            for (index, part) in parts.into_iter().enumerate() {
                let name = format!("{prefix}-{source}-{index:08}.wav");
                if part.path.file_name().and_then(|s| s.to_str()) != Some(name.as_str())
                    || part.path.parent().and_then(|p| p.canonicalize().ok()).as_ref() != Some(&parent)
                    || part.first_sample != expected || part.samples == 0 {
                    return Err("会议音轨分段不连续，原文件保留".into());
                }
                let metadata = std::fs::symlink_metadata(&part.path).map_err(|_| "会议音轨文件缺失")?;
                let bytes = part.samples.checked_mul(2).and_then(|n| u32::try_from(n).ok()).ok_or("会议音轨分段过大")?;
                if !metadata.is_file() || metadata.file_type().is_symlink() || metadata.len() != u64::from(bytes) + 44 {
                    return Err("会议音轨文件不完整，原文件保留".into());
                }
                let mut header = [0u8; 44];
                std::fs::File::open(&part.path).and_then(|mut f| f.read_exact(&mut header)).map_err(|_| "无法读取会议音轨")?;
                if header != denzic_host_audio_v1_core::wav::wav_header(bytes) { return Err("会议音轨格式不正确，原文件保留".into()); }
                expected = expected.checked_add(part.samples).ok_or("会议音轨长度无效")?;
                result.push(CompanionV1MeetingTrackPart { path: part.path.to_string_lossy().into_owned(), first_sample: part.first_sample, samples: part.samples });
            }
            Ok((result, expected))
        };
        let (microphone, mic_samples) = convert(self.microphone, "mic")?;
        let (system, system_samples) = convert(self.system, "system")?;
        let complete = self.error.is_none() && !self.discontinuity && mic_samples > 0 && mic_samples == system_samples;
        Ok(CompanionV1MeetingTracks { root: root.to_string_lossy().into_owned(),
            state: if complete { "captured" } else { "needsReview" }.into(), microphone, system,
            discontinuity: self.discontinuity, issue: self.error.or_else(|| (!complete).then(|| "会议音轨未完整对齐，请核对原音".into())) })
    }
}

#[allow(dead_code)]
impl Capture {
    /// Checkpoint the session/path first; no device opens without this step.
    /// `root` is a unique unused session prefix directly in the managed
    /// recordings directory. Individual WAV files remain on failure.
    pub(super) fn start(root: &Path, part_samples: u64,
        checkpoint: impl FnOnce(&Path) -> Result<(), String>) -> Result<Self, String> {
        checkpoint(root)?;
        let parent = root.parent().ok_or("录音保存位置无效")?;
        let name = root.file_name().and_then(|s| s.to_str()).ok_or("录音名称无效")?;
        let mic = Track { timeline: Timeline::new(), writer: TrackWriter::create_flat(parent, &format!("{name}-mic"), part_samples).map_err(|e| e.to_string())?, resampler: None };
        let system = Track { timeline: Timeline::new(), writer: TrackWriter::create_flat(parent, &format!("{name}-system"), part_samples).map_err(|e| e.to_string())?, resampler: None };
        let (send, recv) = mpsc::sync_channel(1);
        let state = State { origin: None, mic, system, error: None, discontinuity: false, ready: Some(send) };
        let (sender, packets) = mpsc::sync_channel::<WorkerMessage>(QUEUED_PACKETS);
        let failure: SharedFailure = Arc::new(Mutex::new(None));
        let sink = PacketSink { sender, failure };
        let worker_failure = Arc::clone(&sink.failure);
        let worker = thread::spawn(move || {
            let mut state = state;
            while let Ok(WorkerMessage::Packet(packet)) = packets.recv() {
                state.packet(packet.system, &packet.pcm, packet.rate, packet.info);
                if let Some(error) = state.error.as_ref() {
                    record_failure(&worker_failure, error.clone());
                }
            }
            state
        });
        let mic_sink = sink.clone();
        let mic_errors = Arc::clone(&sink.failure);
        let mic = CaptureSession::start_timed_microphone(CaptureOptions { device_name: None, on_stream_error: Some(Arc::new(move |e| {
            record_failure(&mic_errors, format!("麦克风中断：{e}"));
        })) }, move |pcm, rate, info| mic_sink.submit(false, pcm, rate, info));
        let mic = match mic {
            Ok(mic) => mic,
            Err(error) => {
                record_failure(&sink.failure, format!("麦克风未能开始录音：{error}"));
                let _ = finish_worker(sink, worker);
                return Err(error.to_string());
            }
        };
        match recv.recv_timeout(MIC_START_TIMEOUT) {
            Ok(Ok(())) => (),
            result => {
                let _ = mic.stop();
                record_failure(&sink.failure, "麦克风未能开始录音".into());
                let _ = finish_worker(sink, worker);
                return Err(format!("麦克风未能开始录音：{result:?}；已保留文件。"));
            }
        }
        let output_sink = sink.clone();
        let output_errors = Arc::clone(&sink.failure);
        let output = CaptureSession::start_timed_system_output(CaptureOptions { device_name: None, on_stream_error: Some(Arc::new(move |e| {
            record_failure(&output_errors, format!("电脑声音中断：{e}"));
        })) }, move |pcm, rate, info| output_sink.submit(true, pcm, rate, info));
        match output {
            Ok(system) => Ok(Self { mic, system, sink, worker }),
            Err(error) => {
                let _ = mic.stop();
                record_failure(&sink.failure, format!("电脑声音未能开始：{error}"));
                let _ = finish_worker(sink, worker);
                Err(format!("电脑声音未能开始：{error}；已保留文件。"))
            }
        }
    }

    /// An acquisition or write failure stops accepting further packets. Surface
    /// it while the session is still open so the user can finish and recover.
    pub(super) fn error(&self) -> Option<String> {
        self.sink.failure.lock().map(|error| error.clone())
            .unwrap_or_else(|_| Some("会议录音状态不可用，已录内容保留。".into()))
    }

    pub(super) fn stop(self) -> Result<CaptureResult, String> {
        let Self { mic, system, sink, worker } = self;
        if let Err(e) = system.stop() { record_failure(&sink.failure, format!("停止电脑声音失败：{e}")); }
        if let Err(e) = mic.stop() { record_failure(&sink.failure, format!("停止麦克风失败：{e}")); }
        // Drain every accepted packet before sealing the WAV files.
        let mut state = finish_worker(sink, worker)?;
        let end = state.mic.timeline.samples().max(state.system.timeline.samples());
        if state.error.is_none() {
            if let Err(e) = state.mic.pad(end).and_then(|_| state.system.pad(end)) { state.fail(format!("保存录音失败：{e}")); }
        }
        let mut error = state.error;
        let (microphone, mic_error) = state.mic.writer.finish_recoverable();
        let (system, system_error) = state.system.writer.finish_recoverable();
        for (label, failure) in [("麦克风", mic_error), ("电脑声音", system_error)] {
            if let Some(failure) = failure {
                let detail = format!("{label}：{failure}");
                match &mut error { Some(existing) => existing.push_str(&format!("；{detail}")), None => error = Some(detail) }
            }
        }
        Ok(CaptureResult { microphone, system, discontinuity: state.discontinuity, error })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};
    static NEXT: AtomicU64 = AtomicU64::new(0);

    #[test]
    fn full_queue_reports_interruption_without_discarding_accepted_packet() {
        let (sender, packets) = mpsc::sync_channel(1);
        let sink = PacketSink { sender, failure: Arc::new(Mutex::new(None)) };
        let info = TimedCaptureInfo { captured_at: None, discontinuity: false };
        sink.submit(false, &[0.25], 16_000, info);
        // No receiver is consuming: this must return rather than blocking the
        // capture callback, and the first packet must remain recoverable.
        sink.submit(true, &[0.75], 16_000, info);
        assert!(sink.failure.lock().unwrap().as_ref().unwrap().contains("跟不上"));
        match packets.try_recv().unwrap() {
            WorkerMessage::Packet(packet) => assert_eq!(packet.pcm, [0.25]),
            WorkerMessage::Finish => panic!("unexpected finish"),
        }
        assert!(matches!(packets.try_recv(), Err(mpsc::TryRecvError::Empty)));
    }

    #[test]
    fn worker_finishes_even_if_a_timed_out_capture_keeps_a_sender() {
        let root = std::env::temp_dir().join(format!("meeting-worker-finish-{}-{}", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
        fs::create_dir(&root).unwrap();
        let track = |name: &str| Track { timeline: Timeline::new(), writer: TrackWriter::create(&root.join(name), 3).unwrap(), resampler: None };
        let state = State { origin: None, mic: track("mic"), system: track("system"), error: None, discontinuity: false, ready: None };
        let (sender, packets) = mpsc::sync_channel(1);
        let sink = PacketSink { sender, failure: Arc::new(Mutex::new(None)) };
        let retained = sink.clone();
        let worker = thread::spawn(move || {
            assert!(matches!(packets.recv(), Ok(WorkerMessage::Finish)));
            state
        });
        drop(finish_worker(sink, worker).unwrap());
        assert!(matches!(retained.sender.try_send(WorkerMessage::Finish), Err(mpsc::TrySendError::Disconnected(_))));
        drop(retained);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn resampled_capture_packets_keep_offsets_in_saved_parts() {
        let root = std::env::temp_dir().join(format!("meeting-packets-{}-{}", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
        fs::create_dir(&root).unwrap();
        let mut track = Track { timeline: Timeline::new(), writer: TrackWriter::create(&root.join("output"), 3).unwrap(), resampler: None };
        // Four 32 kHz samples become two 16 kHz samples.
        track.push(0, &[0.5, 0.5, -0.5, -0.5], 32_000).unwrap();
        track.push(4, &[1.0, 1.0], 32_000).unwrap();
        track.pad(7).unwrap();
        let parts = track.writer.finish().unwrap();
        let mut samples = Vec::new();
        for part in parts {
            let bytes = fs::read(part.path).unwrap();
            samples.extend(bytes[44..].chunks_exact(2).map(|s| i16::from_le_bytes([s[0], s[1]])));
        }
        assert_eq!(samples, [16383, -16383, 0, 0, 32767, 0, 0]);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn invalid_clock_reports_failure_without_inventing_alignment() {
        let root = std::env::temp_dir().join(format!("meeting-invalid-clock-{}-{}", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
        fs::create_dir(&root).unwrap();
        let track = |name: &str| Track { timeline: Timeline::new(), writer: TrackWriter::create(&root.join(name), 3).unwrap(), resampler: None };
        let (send, recv) = mpsc::sync_channel(1);
        let mut state = State { origin: None, mic: track("mic"), system: track("system"), error: None, discontinuity: false, ready: Some(send) };
        state.packet(false, &[0.5], 16_000, TimedCaptureInfo { captured_at: None, discontinuity: false });
        assert!(state.error.is_some());
        assert!(recv.try_recv().unwrap().is_err());
        assert_eq!(state.mic.timeline.samples(), 0);
        drop(state);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn session_tracks_verify_part_identity_and_lengths() {
        let dir = std::env::temp_dir().join(format!("meeting-index-{}-{}", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
        fs::create_dir(&dir).unwrap(); let anchor = dir.join("unique");
        let mut mic = TrackWriter::create_flat(&dir, "unique-mic", 2).unwrap();
        let mut output = TrackWriter::create_flat(&dir, "unique-system", 2).unwrap();
        mic.append(&[1,2,3]).unwrap(); output.append(&[4,5,6]).unwrap();
        let captured = CaptureResult { microphone: mic.finish().unwrap(), system: output.finish().unwrap(), discontinuity: false, error: None };
        let altered = CaptureResult { microphone: captured.microphone.clone(), system: captured.system.clone(), discontinuity: false, error: None };
        let indexed = captured.into_session_tracks(&anchor).unwrap();
        assert_eq!(indexed.state, "captured"); assert_eq!(indexed.microphone.len(), 2); assert_eq!(indexed.system.len(), 2);
        fs::write(&altered.system[0].path, b"replaced").unwrap();
        assert!(altered.into_session_tracks(&anchor).is_err());
        fs::remove_dir_all(dir).unwrap();
    }
}
