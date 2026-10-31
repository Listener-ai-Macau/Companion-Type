//! Experimental two-source meeting recorder. Product session persistence,
//! replay, transcription and the explicit UI choice must be connected before
//! this module can be used as an end-user feature.
use std::fs;
use std::path::Path;
use std::sync::{mpsc, Arc, Mutex};
use std::time::Duration;
use denzic_host_audio_v1_core::capture::{CaptureOptions, CaptureSession, TimedCaptureInfo};
use super::host_recording::RatioResampler;
use super::meeting_audio_timeline::Timeline;
use super::meeting_audio_tracks::{TrackPart, TrackWriter};

const SAMPLE_RATE: u32 = 16_000;
const MIC_START_TIMEOUT: Duration = Duration::from_secs(5);

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
    state: Arc<Mutex<State>>,
}

#[allow(dead_code)]
pub(super) struct CaptureResult {
    pub(super) microphone: Vec<TrackPart>,
    pub(super) system: Vec<TrackPart>,
    pub(super) discontinuity: bool,
    pub(super) error: Option<String>,
}

#[allow(dead_code)]
impl Capture {
    /// Checkpoint the session/path first; no device opens without this step.
    /// `root` is new, owned by that session, and remains on failure.
    pub(super) fn start(root: &Path, part_samples: u64,
        checkpoint: impl FnOnce(&Path) -> Result<(), String>) -> Result<Self, String> {
        checkpoint(root)?;
        fs::create_dir(root).map_err(|e| e.to_string())?;
        let mic = Track { timeline: Timeline::new(), writer: TrackWriter::create(&root.join("microphone"), part_samples).map_err(|e| e.to_string())?, resampler: None };
        let system = Track { timeline: Timeline::new(), writer: TrackWriter::create(&root.join("system"), part_samples).map_err(|e| e.to_string())?, resampler: None };
        let (send, recv) = mpsc::sync_channel(1);
        let state = Arc::new(Mutex::new(State { origin: None, mic, system, error: None, discontinuity: false, ready: Some(send) }));
        let mic_state = Arc::clone(&state);
        let mic_errors = Arc::clone(&state);
        let mic = CaptureSession::start_timed_microphone(CaptureOptions { device_name: None, on_stream_error: Some(Arc::new(move |e| {
            if let Ok(mut state) = mic_errors.lock() { state.fail(format!("麦克风中断：{e}")); }
        })) }, move |pcm, rate, info| { if let Ok(mut state) = mic_state.lock() { state.packet(false, pcm, rate, info); } })
            .map_err(|e| e.to_string())?;
        match recv.recv_timeout(MIC_START_TIMEOUT) {
            Ok(Ok(())) => (),
            result => { let _ = mic.stop(); return Err(format!("麦克风未能开始录音：{result:?}；已保留文件。")); }
        }
        let output_state = Arc::clone(&state);
        let output_errors = Arc::clone(&state);
        let output = CaptureSession::start_timed_system_output(CaptureOptions { device_name: None, on_stream_error: Some(Arc::new(move |e| {
            if let Ok(mut state) = output_errors.lock() { state.fail(format!("电脑声音中断：{e}")); }
        })) }, move |pcm, rate, info| { if let Ok(mut state) = output_state.lock() { state.packet(true, pcm, rate, info); } });
        match output {
            Ok(system) => Ok(Self { mic, system, state }),
            Err(error) => { let _ = mic.stop(); Err(format!("电脑声音未能开始：{error}；已保留文件。")) }
        }
    }

    pub(super) fn stop(self) -> Result<CaptureResult, String> {
        if let Err(e) = self.system.stop() { if let Ok(mut state) = self.state.lock() { state.fail(format!("停止电脑声音失败：{e}")); } }
        if let Err(e) = self.mic.stop() { if let Ok(mut state) = self.state.lock() { state.fail(format!("停止麦克风失败：{e}")); } }
        let mutex = Arc::try_unwrap(self.state).map_err(|_| "录音线程尚未结束，原文件保留".to_string())?;
        let mut state = mutex.into_inner().map_err(|_| "录音状态不可用，原文件保留".to_string())?;
        let end = state.mic.timeline.samples().max(state.system.timeline.samples());
        if state.error.is_none() {
            if let Err(e) = state.mic.pad(end).and_then(|_| state.system.pad(end)) { state.fail(format!("保存录音失败：{e}")); }
        }
        let error = state.error;
        let microphone = state.mic.writer.finish().map_err(|e| format!("保存麦克风失败：{e}；原文件保留"))?;
        let system = state.system.writer.finish().map_err(|e| format!("保存电脑声音失败：{e}；原文件保留"))?;
        Ok(CaptureResult { microphone, system, discontinuity: state.discontinuity, error })
    }
}
