//! Resume checked work for the same adopted transcript after a pause or stop.
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Instant;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::companion_v1::CompanionV1HostSession;

use super::source_checkpoint::CheckedSourcePrefix;
use super::super::long_meeting;
use crate::backend::external_command::LOCAL_SERVICE_LOW_MEMORY;

#[derive(PartialEq, Eq)]
struct SourceKey {
    recording: String,
    input_hash: [u8; 32],
}

impl SourceKey {
    fn for_session(session: &CompanionV1HostSession) -> Self {
        Self {
            recording: session.id.clone(),
            input_hash: Sha256::digest(serde_json::to_vec(&(
                &session.transcript_text, &session.utterances, session.duration_ms,
                &session.meeting_mode, session.transcript_review.as_ref().map(|review| review.revision),
            )).expect("meeting input serialization")).into(),
        }
    }
}

struct Saved {
    source: SourceKey,
    prefix: Arc<CheckedSourcePrefix>,
}

pub(super) struct RetrySlot(Mutex<Option<Saved>>);

impl RetrySlot {
    pub(super) const fn new() -> Self {
        Self(Mutex::new(None))
    }

    fn get(&self, source: &SourceKey) -> Option<Arc<CheckedSourcePrefix>> {
        let mut slot = self.0.lock().ok()?;
        let previous = slot.as_ref()?;
        if &previous.source == source {
            return Some(Arc::clone(&previous.prefix));
        }
        if previous.source.recording == source.recording {
            *slot = None; // The recording was corrected or replaced.
        }
        None
    }

    fn clear(&self, source: &SourceKey) {
        if let Ok(mut slot) = self.0.lock() {
            if slot.as_ref().is_some_and(|saved| &saved.source == source) {
                *slot = None;
            }
        }
    }
}

const MAX_RETRY_BYTES: u64 = 8 * 1024 * 1024;

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ResumeFile {
    version: u32,
    input_hash: [u8; 32],
    receipt: Value,
}

struct DiskRetry {
    path: PathBuf,
    _lock: File,
}

impl DiskRetry {
    fn open(root: &Path, source: &SourceKey) -> Option<Self> {
        let lock = long_meeting::root_lock(root).ok()?;
        Some(Self { path: root.join(long_meeting::local_resume_filename(&source.recording)), _lock: lock })
    }

    fn load(&self, source: &SourceKey, transcript: &str) -> Option<Arc<CheckedSourcePrefix>> {
        if !long_meeting::regular(&self.path) { return None; }
        let mut bytes = Vec::new();
        File::open(&self.path).ok()?.take(MAX_RETRY_BYTES + 1).read_to_end(&mut bytes).ok()?;
        if bytes.len() as u64 > MAX_RETRY_BYTES { return None; }
        let saved: ResumeFile = serde_json::from_slice(&bytes).ok()?;
        if saved.version != 1 || saved.input_hash != source.input_hash { return None; }
        CheckedSourcePrefix::for_desktop_retry(transcript, &saved.receipt).map(Arc::new)
    }

    fn save(&self, source: &SourceKey, prefix: &CheckedSourcePrefix) -> Option<()> {
        if fs::symlink_metadata(&self.path).is_ok() && !long_meeting::regular(&self.path) { return None; }
        let bytes = serde_json::to_vec(&ResumeFile {
            version: 1, input_hash: source.input_hash, receipt: prefix.desktop_receipt(),
        }).ok()?;
        if bytes.len() as u64 > MAX_RETRY_BYTES { return None; }
        // A stopped save leaves only this recording's identifiable staging file,
        // so deleting the recording also removes any uncommitted progress.
        let pending = self.path.with_extension("part");
        if fs::symlink_metadata(&pending).is_ok() {
            if !long_meeting::regular(&pending) { return None; }
            fs::remove_file(&pending).ok()?;
        }
        let mut file = OpenOptions::new().write(true).create_new(true).open(&pending).ok()?;
        let written = file.write_all(&bytes).and_then(|()| file.sync_all()).is_ok();
        drop(file);
        if !written || crate::backend::export::replace_file(&pending, &self.path).is_err() {
            let _ = fs::remove_file(pending);
            return None;
        }
        Some(())
    }

    fn clear(&self) {
        for path in [&self.path, &self.path.with_extension("part")] {
            if long_meeting::regular(path) { let _ = fs::remove_file(path); }
        }
    }
}

fn progress(prefix: &CheckedSourcePrefix) -> (usize, bool) {
    (prefix.len(), prefix.completed_source_review().is_some())
}

fn pressure<T>(result: &Result<T, String>, trace: &Value) -> bool {
    result.as_ref().err().is_some_and(|error| error == LOCAL_SERVICE_LOW_MEMORY)
        && trace["backend"] == "cpu"
}

fn keep_validated_source(saved: &mut Option<Arc<CheckedSourcePrefix>>, source: &str, trace: &Value) {
    let Some(prefix) = CheckedSourcePrefix::for_desktop_retry(source, trace) else { return; };
    if saved.as_ref().is_none_or(|prior| progress(&prefix) >= progress(prior)) {
        *saved = Some(Arc::new(prefix));
    }
}

pub(super) fn generate<T>(
    slot: &RetrySlot,
    session: &CompanionV1HostSession,
    cache_root: Option<&Path>,
    mut run: impl FnMut(&CheckedSourcePrefix, bool) -> (Result<T, String>, Value),
    mut memory_recovered: impl FnMut() -> bool,
    cancelled: impl Fn() -> bool,
) -> (Result<T, String>, Value, Option<Arc<CheckedSourcePrefix>>) {
    let start = Instant::now();
    let source = SourceKey::for_session(session);
    let empty = CheckedSourcePrefix::default();
    let mut saved = slot.get(&source);
    let disk = cache_root.and_then(|path| DiskRetry::open(path, &source));
    let loaded = disk.as_ref().and_then(|disk| disk.load(&source, &session.transcript_text));
    let loaded_from_disk = loaded.as_ref().is_some_and(|prefix| {
        saved.as_ref().is_none_or(|old| progress(prefix) >= progress(old))
    });
    if loaded_from_disk { saved = loaded; }
    let (mut result, mut trace) = run(saved.as_deref().unwrap_or(&empty), saved.is_some());

    if pressure(&result, &trace) {
        keep_validated_source(&mut saved, &session.transcript_text, &trace);
        if memory_recovered() {
            if let Some((disk, prefix)) = disk.as_ref().zip(saved.as_ref()) {
                let _ = disk.save(&source, prefix);
            }
            let first_seconds = trace["seconds"].clone();
            let first_requests = trace["inferenceRequestAttempts"].clone();
            // Release the original trace before starting a new service.
            drop(trace);
            (result, trace) = run(saved.as_deref().unwrap_or(&empty), true);
            trace["memoryRecovery"] = json!({
                "initialSeconds": first_seconds, "initialRequests": first_requests,
                "resumedSourceWindows": trace["reusedSourceWindows"],
            });
            trace["seconds"] = json!(start.elapsed().as_secs_f64());
        }
    }

    trace["restoredLocalCheckpoint"] = json!(loaded_from_disk && trace["reusedSourceWindows"].as_u64().unwrap_or(0) > 0);
    let low_memory = pressure(&result, &trace);
    if low_memory || cancelled() {
        keep_validated_source(&mut saved, &session.transcript_text, &trace);
        if let Some(prefix) = saved {
            let durable = disk.as_ref().is_some_and(|disk| disk.save(&source, &prefix).is_some());
            let windows = prefix.len();
            if let Ok(mut cache) = slot.0.lock() {
                *cache = Some(Saved { source, prefix: Arc::clone(&prefix) });
            }
            trace["retainedSourceWindows"] = json!(windows);
            trace["savedLocalCheckpoint"] = json!(durable);
            if low_memory {
                let lead = super::super::LOCAL_MEMORY_RETRY_PREFIX;
                let message = if durable {
                    format!("{lead}，已保存 {windows} 段本地整理进度。释放内存后可以继续。")
                } else {
                    format!("{lead}，已保留 {windows} 段整理进度。内存恢复后，点击重试可接着生成。")
                };
                trace["error"] = json!(message);
                return (Err(message), trace, Some(prefix));
            }
            return (result, trace, None);
        }
        return (result, trace, None);
    }

    if result.is_ok() {
        slot.clear(&source);
        if let Some(disk) = disk { disk.clear(); }
    }
    (result, trace, None)
}


#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::minutes::local::assets;
    use crate::backend::minutes::tests::session_with_text;

    fn interrupted_trace() -> Value {
        json!({
            "provider":"local","modelSha256":assets::MODEL_SHA,"runtimeSha256":assets::SERVER_SHA,
            "backend":"cpu","newCloudCalls":0,"trainingUpdates":0,"contextTokens":8192,
            "reviewedSourceWindows":[{"window":1,"sourceEncoding":"direct-single-role"}],
            "calls":[], "seconds":60, "inferenceRequestAttempts":0
        })
    }

    #[test]
    fn stable_memory_recovery_uses_validated_work_and_retries_once() {
        let slot = RetrySlot::new();
        let session = session_with_text("测试环境今天仍然可用。");
        let mut attempts = Vec::new();
        let (result, trace, retained) = generate(
            &slot, &session, None,
            |prefix, lean| {
                attempts.push((prefix.len(), lean));
                if attempts.len() == 1 {
                    (Err(LOCAL_SERVICE_LOW_MEMORY.into()), interrupted_trace())
                } else {
                    (Ok(()), json!({"backend":"cpu","reusedSourceWindows":prefix.len()}))
                }
            },
            || true,
            || false,
        );
        assert!(result.is_ok());
        assert!(retained.is_none());
        assert_eq!(attempts, [(0, false), (1, true)]);
        assert_eq!(trace["memoryRecovery"]["resumedSourceWindows"], 1);
        assert!(slot.get(&SourceKey::for_session(&session)).is_none());
    }

    #[test]
    fn persistent_pressure_preserves_only_the_matching_recording_for_manual_retry() {
        let slot = RetrySlot::new();
        let session = session_with_text("测试环境今天仍然可用。");
        let mut attempts = 0;
        let (result, trace, retained) = generate(
            &slot, &session, None,
            |prefix, _| {
                attempts += 1;
                let trace = if attempts == 1 {
                    interrupted_trace()
                } else {
                    assert_eq!(prefix.len(), 1);
                    json!({"backend":"cpu","reusedSourceWindows":1})
                };
                (Err::<(), _>(LOCAL_SERVICE_LOW_MEMORY.into()), trace)
            },
            || true,
            || false,
        );
        assert_eq!(retained.unwrap().len(), 1);
        assert_eq!(attempts, 2);
        assert_eq!(trace["retainedSourceWindows"], 1);
        assert!(result.unwrap_err().contains("保留 1 段"));
        let mut another = session.clone();
        another.id.push_str("-other");
        assert!(slot.get(&SourceKey::for_session(&another)).is_none());
        assert!(slot.get(&SourceKey::for_session(&session)).is_some());

        let mut edited = session.clone();
        edited.transcript_text.push_str("现在已经确认原记录有误。");
        assert!(slot.get(&SourceKey::for_session(&edited)).is_none());
        assert!(slot.get(&SourceKey::for_session(&session)).is_none());
    }

    #[test]
    fn pressure_that_has_not_cleared_keeps_progress_for_a_later_click() {
        let slot = RetrySlot::new();
        let session = session_with_text("测试环境今天仍然可用。");
        let mut attempts = 0;
        let _ = generate(
            &slot, &session, None,
            |_, _| {
                attempts += 1;
                (Err::<(), _>(LOCAL_SERVICE_LOW_MEMORY.into()), interrupted_trace())
            },
            || false,
            || false,
        );
        assert_eq!(attempts, 1);
        let (result, _, _) = generate(&slot, &session, None, |prefix, lean| {
            assert_eq!(prefix.len(), 1);
            assert!(lean);
            (Ok(()), json!({"backend":"cpu","reusedSourceWindows":prefix.len()}))
        }, || panic!("memory recovered before this retry"), || false);
        assert!(result.is_ok());
    }

    #[test]
    fn stopped_generation_resumes_in_a_new_process_slot_and_clears_on_success() {
        let root = std::env::temp_dir().join(format!("companion-local-resume-{}", uuid::Uuid::new_v4()));
        let session = session_with_text("测试环境今天仍然可用。");
        let stop = || true;
        let (_, trace, _) = generate(&RetrySlot::new(), &session, Some(&root),
            |_, _| (Err::<(), _>("本地纪要已取消，已有内容保留。".into()), interrupted_trace()),
            || false, stop);
        assert_eq!(trace["savedLocalCheckpoint"], true);

        let mut edited = session.clone();
        edited.transcript_text.push_str("修改后的转写。");
        let _ = generate(&RetrySlot::new(), &edited, Some(&root),
            |prefix, _| {
                assert_eq!(prefix.len(), 0);
                (Err::<(), _>("未开始".into()), json!({}))
            }, || false, || false);

        let (result, trace, _) = generate(&RetrySlot::new(), &session, Some(&root),
            |prefix, lean| {
                assert_eq!(prefix.len(), 1);
                assert!(lean);
                (Ok(()), json!({"reusedSourceWindows":prefix.len()}))
            }, || false, || false);
        assert!(result.is_ok());
        assert_eq!(trace["restoredLocalCheckpoint"], true);
        assert!(!root.join(long_meeting::local_resume_filename(&session.id)).exists());
        fs::remove_file(root.join("work.lock")).unwrap();
        fs::remove_dir(root).unwrap();
    }

    #[test]
    fn privacy_erase_removes_owned_local_progress_even_if_it_is_interrupted() {
        let root = std::env::temp_dir().join(format!("companion-local-erase-{}", uuid::Uuid::new_v4()));
        fs::create_dir(&root).unwrap();
        let owned = root.join(long_meeting::local_resume_filename("selected"));
        let pending = owned.with_extension("part");
        let other = root.join(long_meeting::local_resume_filename("retained"));
        for file in [&owned, &pending, &other] {
            fs::write(file, b"partial or unreadable local progress").unwrap();
        }
        assert_eq!(long_meeting::erase(&root, &["selected".into()], false).unwrap(), (2, 0));
        assert!(!owned.exists() && !pending.exists() && other.is_file());
        assert_eq!(long_meeting::erase(&root, &[], true).unwrap(), (1, 0));
        fs::remove_file(root.join("work.lock")).unwrap();
        fs::remove_dir(root).unwrap();
    }
}
