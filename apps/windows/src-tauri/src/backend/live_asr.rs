//! Mid-meeting live ASR for `onlineLive`.
//!
//! - Product: Volc SAUC WebSocket while host mic records (PCM 16 kHz).
//! - Mock: `COMPANION_TYPE_LIVE_ASR_MOCK=1` injects partials offline.
//! - Disable: `COMPANION_TYPE_LIVE_ASR_OFF=1`.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use super::volcengine::{self, VolcengineSaucAsr};

#[derive(Clone, Debug, Default)]
pub struct LiveAsrSnapshot {
    pub text: String,
    pub mode: String,
    pub error: Option<String>,
    pub partial_count: u32,
    pub active: bool,
}

pub struct LiveAsrHub {
    text: Arc<Mutex<String>>,
    partial_count: Arc<Mutex<u32>>,
    error: Arc<Mutex<Option<String>>>,
    mode: Mutex<String>,
    stop: Arc<AtomicBool>,
    pcm_tx: Mutex<Option<std::sync::mpsc::Sender<Vec<u8>>>>,
    join: Mutex<Option<JoinHandle<()>>>,
    #[cfg(windows)]
    local:Mutex<Option<super::transcription::local_meeting::LiveInput>>,
}

impl LiveAsrHub {
    pub fn new() -> Self {
        Self {
            text: Arc::new(Mutex::new(String::new())),
            partial_count: Arc::new(Mutex::new(0)),
            error: Arc::new(Mutex::new(None)),
            mode: Mutex::new("idle".to_string()),
            stop: Arc::new(AtomicBool::new(false)),
            pcm_tx: Mutex::new(None),
            join: Mutex::new(None),
            #[cfg(windows)] local:Mutex::new(None),
        }
    }

    #[cfg(test)]
    pub(super) fn set_failed_for_test(&self, partial: &str) {
        *self.text.lock().unwrap()=partial.to_string();
        *self.error.lock().unwrap()=Some("simulated connection loss".to_string());
    }

    pub fn snapshot(&self) -> LiveAsrSnapshot {
        #[cfg(windows)]
        if let Ok(slot)=self.local.lock(){if let Some(input)=slot.as_ref(){
            if let Some((text,error))=input.preview(){
                if let Ok(mut current)=self.text.lock(){if *current!=text {
                    *current=text;if let Ok(mut n)=self.partial_count.lock(){*n+=1;}
                }}
                if error.is_some(){if let Ok(mut current)=self.error.lock(){*current=error;}}
            }
        }}
        LiveAsrSnapshot {
            text: self.text.lock().ok().map(|t| t.clone()).unwrap_or_default(),
            mode: self
                .mode
                .lock()
                .ok()
                .map(|m| m.clone())
                .unwrap_or_else(|| "idle".to_string()),
            error: self.error.lock().ok().and_then(|e| e.clone()),
            partial_count: self.partial_count.lock().ok().map(|p| *p).unwrap_or(0),
            active: self.join.lock().ok().is_some_and(|j| j.as_ref().is_some_and(|handle| !handle.is_finished())),
        }
    }

    /// Start live ASR for onlineLive. Ok(false) = intentionally not started.
    pub fn try_start_for_online_live(&self,owner:&str) -> Result<bool, String> {
        let _ = self.stop_and_take_text();
        if env_truthy("COMPANION_TYPE_LIVE_ASR_OFF") {
            return Ok(false);
        }

        self.stop.store(false, Ordering::SeqCst);
        if let Ok(mut t) = self.text.lock() {
            t.clear();
        }
        if let Ok(mut p) = self.partial_count.lock() {
            *p = 0;
        }
        if let Ok(mut e) = self.error.lock() {
            *e = None;
        }

        #[cfg(windows)] {
            *self.local.lock().map_err(|_|"本机录中处理状态暂不可用。")?=None;
            if super::transcription::local_meeting::selected(){
                let input=super::transcription::local_meeting::LiveInput::create(owner)?;
                let program=input.program.clone();let args=input.args.clone();
                *self.local.lock().map_err(|_|"本机录中处理状态暂不可用。")?=Some(input);
                *self.mode.lock().map_err(|_|"本机录中处理状态暂不可用。")?="local-bilingual-incremental".into();
                let stop=Arc::clone(&self.stop);let error=Arc::clone(&self.error);
                let join=thread::spawn(move||{
                    let _power=super::processing_power::hold();
                    if let Err(e)=super::external_command::run_local_meeting_stream(&program,&args,&stop){
                        if !stop.load(Ordering::Acquire){if let Ok(mut slot)=error.lock(){
                            *slot=Some(format!("本机录中识别未完成：{e}；原音继续保存，结束后可继续转写。"));
                        }}
                    }
                });
                *self.join.lock().map_err(|_|"本机录中处理状态暂不可用。")?=Some(join);
                return Ok(true);
            }
        }
        // A selected local provider never opens the configured cloud stream.
        if super::transcription::local_provider_selected(){
            if let Ok(mut mode)=self.mode.lock(){*mode="idle-local-after-recording".into();}
            return Ok(false);
        }

        if env_truthy("COMPANION_TYPE_LIVE_ASR_MOCK") {
            if let Ok(mut m) = self.mode.lock() {
                *m = "mock-streaming".to_string();
            }
            let stop = Arc::clone(&self.stop);
            let text = Arc::clone(&self.text);
            let partials = Arc::clone(&self.partial_count);
            let join = thread::spawn(move || {
                let steps = [
                    (180u64, "会议开始。"),
                    (180u64, "会议开始。第一项：同步录音。"),
                    (180u64, "会议开始。第一项：同步录音。第二项：在线实时转写。"),
                ];
                for (ms, line) in steps {
                    if stop.load(Ordering::SeqCst) {
                        break;
                    }
                    thread::sleep(Duration::from_millis(ms));
                    if let Ok(mut t) = text.lock() {
                        *t = line.to_string();
                    }
                    if let Ok(mut p) = partials.lock() {
                        *p += 1;
                    }
                }
            });
            if let Ok(mut j) = self.join.lock() {
                *j = Some(join);
            }
            return Ok(true);
        }

        let Some(creds) = volcengine::credentials_from_env() else {
            if let Ok(mut m) = self.mode.lock() {
                *m = "idle-no-credentials".to_string();
            }
            return Ok(false);
        };

        if let Ok(mut m) = self.mode.lock() {
            *m = "ws-sauc-streaming".to_string();
        }
        let (pcm_tx, pcm_rx) = std::sync::mpsc::channel::<Vec<u8>>();
        if let Ok(mut tx) = self.pcm_tx.lock() {
            *tx = Some(pcm_tx);
        }
        let stop = Arc::clone(&self.stop);
        let text = Arc::clone(&self.text);
        let partials = Arc::clone(&self.partial_count);
        let error = Arc::clone(&self.error);
        let join = thread::spawn(move || {
            let asr = VolcengineSaucAsr::new(creds);
            let text_cb = Arc::clone(&text);
            let partials_cb = Arc::clone(&partials);
            match asr.stream_pcm_session(pcm_rx, Arc::clone(&stop), move |partial| {
                if partial.trim().is_empty() {
                    return;
                }
                if let Ok(mut t) = text_cb.lock() {
                    *t = partial.to_string();
                }
                if let Ok(mut p) = partials_cb.lock() {
                    *p += 1;
                }
            }) {
                Ok(final_text) => {
                    if !final_text.trim().is_empty() {
                        if let Ok(mut t) = text.lock() {
                            *t = final_text;
                        }
                    }
                }
                Err(e) => {
                    if let Ok(mut err) = error.lock() {
                        *err = Some(e);
                    }
                }
            }
        });
        if let Ok(mut j) = self.join.lock() {
            *j = Some(join);
        }
        Ok(true)
    }

    pub fn push_pcm_i16(&self, samples: &[i16]) {
        if samples.is_empty() {
            return;
        }
        #[cfg(windows)] if let Ok(mut slot)=self.local.lock(){if let Some(input)=slot.as_mut(){
            if !self.stop.load(Ordering::Acquire){if let Err(e)=input.push(samples){
                if let Ok(mut error)=self.error.lock(){*error=Some(e);}
            }}
            return;
        }}
        let mut bytes = Vec::with_capacity(samples.len() * 2);
        for s in samples {
            bytes.extend_from_slice(&s.to_le_bytes());
        }
        if let Ok(tx_slot) = self.pcm_tx.lock() {
            if let Some(tx) = tx_slot.as_ref() {
                let _ = tx.send(bytes);
            }
        }
    }

    pub fn stop_and_take_text(&self) -> LiveAsrSnapshot {
        // Close the producer under its lock first: all buffers accepted
        // before stop are then visible to the worker when it drains.
        if let Ok(mut tx) = self.pcm_tx.lock() {
            *tx = None;
        }
        self.stop.store(true, Ordering::SeqCst);
        #[cfg(windows)] if let Ok(slot)=self.local.lock(){if let Some(input)=slot.as_ref(){
            if let Err(e)=input.seal(){if let Ok(mut error)=self.error.lock(){*error=Some(e);}}
        }}
        if let Ok(mut join) = self.join.lock() {
            if let Some(handle) = join.take() {
                if handle.join().is_err() {
                    if let Ok(mut error) = self.error.lock() {
                        *error = Some("实时识别线程异常结束".to_string());
                    }
                }
            }
        }
        let snap = self.snapshot();
        #[cfg(windows)] if let Ok(mut local)=self.local.lock(){*local=None;}
        if let Ok(mut m) = self.mode.lock() {
            *m = "idle".to_string();
        }
        snap
    }
}

impl Default for LiveAsrHub {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for LiveAsrHub{fn drop(&mut self){let _=self.stop_and_take_text();}}

fn env_truthy(name: &str) -> bool {
    matches!(
        std::env::var(name).ok().as_deref(),
        Some("1") | Some("true") | Some("TRUE") | Some("yes") | Some("YES")
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[cfg(windows)]
    #[test]
    #[ignore = "Explicit isolated public90s PCM/model package; real local inference, never microphone/card"]
    fn actual_public_pcm_uses_native_live_hub_and_releases_cache_lease(){
        use std::path::PathBuf;
        use sha2::{Digest,Sha256};
        assert_eq!(std::env::var("COMPANION_TYPE_ASR_PROVIDER").unwrap(),"local-meeting");
        assert!(std::env::var_os("COMPANION_TYPE_STATE_PATH").is_some());
        let source=PathBuf::from("E:/CodexData/Companion/.model-cache/local-bilingual-20261114/public-probe90.wav");
        let bytes=std::fs::read(&source).unwrap();
        assert_eq!(format!("{:x}",Sha256::digest(&bytes)),"dea1f9d47d753e6b626614a87ef163e48f21657d51303f4cffc182845dbd79a8");
        let pcm=super::super::diarization::read_pcm16k_mono_wav(&source).unwrap();
        assert_eq!(pcm.len(),90*16000*2);
        let owner=std::env::var("COMPANION_LOCAL_PUBLIC_PROBE_OWNER").unwrap();
        let output=PathBuf::from(std::env::var_os("COMPANION_LOCAL_PUBLIC_PROBE_RESULT").unwrap());
        assert!(!output.exists());
        let hub=LiveAsrHub::new();assert!(hub.try_start_for_online_live(&owner).unwrap());
        let began=std::time::Instant::now();let mut first=None;
        for packet in pcm.chunks(16000*2){
            let samples=packet.chunks_exact(2).map(|b|i16::from_le_bytes([b[0],b[1]])).collect::<Vec<_>>();
            hub.push_pcm_i16(&samples);thread::sleep(Duration::from_secs(1));
            if first.is_none()&&!hub.snapshot().text.is_empty(){first=Some(began.elapsed().as_secs_f64());}
        }
        let snap=hub.stop_and_take_text();
        assert!(!snap.active);assert!(hub.local.lock().unwrap().is_none());
        assert!(first.is_some(),"Actual incremental preview was absent during90s capture; retain failed evidence");
        let root=super::super::transcription::asr_chunk_cache_root();
        let registry:serde_json::Value=serde_json::from_slice(&std::fs::read(root.join("local-meeting/.local-meeting-owners.json")).unwrap()).unwrap();
        let e=registry["entries"].as_array().unwrap().iter().find(|e|e["owner"]==owner&&e["key"].as_str().unwrap().starts_with("stream-")).unwrap();
        let stream=root.join("local-meeting").join(e["id"].as_str().unwrap());
        assert_eq!(std::fs::read(stream.join("audio.pcm")).unwrap(),pcm);
        std::fs::write(output,serde_json::to_vec_pretty(&serde_json::json!({
            "state":"PASS_ACTUAL_NATIVE_LIVE_HUB_PACED90_SOURCE_AND_DRAFT_LEASE_RELEASED",
            "frames":pcm.len()/2,"firstPreviewSeconds":first,"streamRoot":stream,
            "seconds":began.elapsed().as_secs_f64(),"sourceSha256":"dea1f9d47d753e6b626614a87ef163e48f21657d51303f4cffc182845dbd79a8",
            "partialCharacters":snap.text.chars().count(),"previewPromotedToFinal":false,
            "realMicrophoneOrBoardAccess":false,"qualityQualified":false})).unwrap()).unwrap();
    }
    #[test]
    fn finished_failed_worker_is_not_reported_as_active_and_keeps_partial() {
        let hub=LiveAsrHub::new();
        *hub.text.lock().unwrap()="已识别的前半句".into();
        let error=Arc::clone(&hub.error);
        *hub.join.lock().unwrap()=Some(thread::spawn(move || {
            *error.lock().unwrap()=Some("模拟连接中断".into());
        }));
        let deadline=std::time::Instant::now()+Duration::from_secs(2);
        while !hub.join.lock().unwrap().as_ref().unwrap().is_finished() {
            assert!(std::time::Instant::now()<deadline,"fixture worker did not finish");
            thread::yield_now();
        }
        let state=hub.snapshot();
        assert!(!state.active,"a completed worker cannot be an active live stream");
        assert_eq!(state.text,"已识别的前半句");
        assert_eq!(state.error.as_deref(),Some("模拟连接中断"));
        let stopped=hub.stop_and_take_text();
        assert_eq!(stopped.text,state.text);assert!(stopped.error.is_some());
    }
}
