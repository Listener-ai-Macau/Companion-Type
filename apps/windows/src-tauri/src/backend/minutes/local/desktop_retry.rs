//! Hold a single, bounded in-process retry for the same adopted transcript.
use std::sync::{Arc, Mutex};
use std::time::Instant;

use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::companion_v1::CompanionV1HostSession;

use super::source_checkpoint::CheckedSourcePrefix;
use crate::backend::external_command::LOCAL_SERVICE_LOW_MEMORY;

#[derive(PartialEq, Eq)]
struct SourceKey {
    recording: String,
    transcript: [u8; 32],
    duration_ms: u64,
}

impl SourceKey {
    fn for_session(session: &CompanionV1HostSession) -> Self {
        Self {
            recording: session.id.clone(),
            transcript: Sha256::digest(session.transcript_text.as_bytes()).into(),
            duration_ms: session.duration_ms,
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

fn pressure<T>(result: &Result<T, String>, trace: &Value) -> bool {
    result.as_ref().err().is_some_and(|error| error == LOCAL_SERVICE_LOW_MEMORY)
        && trace["backend"] == "cpu"
}

fn keep_validated_source(saved: &mut Option<Arc<CheckedSourcePrefix>>, source: &str, trace: &Value) {
    let Some(prefix) = CheckedSourcePrefix::for_desktop_retry(source, trace) else { return; };
    let progress = |checked: &CheckedSourcePrefix| (checked.len(), checked.completed_source_review().is_some());
    if saved.as_ref().is_none_or(|prior| progress(&prefix) >= progress(prior)) {
        *saved = Some(Arc::new(prefix));
    }
}

pub(super) fn generate<T>(
    slot: &RetrySlot,
    session: &CompanionV1HostSession,
    mut run: impl FnMut(&CheckedSourcePrefix, bool) -> (Result<T, String>, Value),
    mut memory_recovered: impl FnMut() -> bool,
) -> (Result<T, String>, Value, Option<Arc<CheckedSourcePrefix>>) {
    let start = Instant::now();
    let source = SourceKey::for_session(session);
    let empty = CheckedSourcePrefix::default();
    let mut saved = slot.get(&source);
    let (mut result, mut trace) = run(saved.as_deref().unwrap_or(&empty), saved.is_some());

    if pressure(&result, &trace) {
        keep_validated_source(&mut saved, &session.transcript_text, &trace);
        if memory_recovered() {
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
            if pressure(&result, &trace) {
                keep_validated_source(&mut saved, &session.transcript_text, &trace);
            }
        }

        if pressure(&result, &trace) {
            if let Some(prefix) = saved {
                let windows = prefix.len();
                if let Ok(mut cache) = slot.0.lock() {
                    *cache = Some(Saved { source, prefix: Arc::clone(&prefix) });
                    trace["retainedSourceWindows"] = json!(windows);
                    let lead = super::super::LOCAL_MEMORY_RETRY_PREFIX;
                    let message = format!("{lead}，已保留 {windows} 段整理进度。内存恢复后，点击重试可接着生成。");
                    trace["error"] = json!(message);
                    return (Err(message), trace, Some(prefix));
                }
            }
        }
    }

    if result.is_ok() {
        slot.clear(&source);
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
            &slot, &session,
            |prefix, lean| {
                attempts.push((prefix.len(), lean));
                if attempts.len() == 1 {
                    (Err(LOCAL_SERVICE_LOW_MEMORY.into()), interrupted_trace())
                } else {
                    (Ok(()), json!({"backend":"cpu","reusedSourceWindows":prefix.len()}))
                }
            },
            || true,
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
            &slot, &session,
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
            &slot, &session,
            |_, _| {
                attempts += 1;
                (Err::<(), _>(LOCAL_SERVICE_LOW_MEMORY.into()), interrupted_trace())
            },
            || false,
        );
        assert_eq!(attempts, 1);
        let (result, _, _) = generate(&slot, &session, |prefix, lean| {
            assert_eq!(prefix.len(), 1);
            assert!(lean);
            (Ok(()), json!({"backend":"cpu","reusedSourceWindows":prefix.len()}))
        }, || panic!("memory recovered before this retry"));
        assert!(result.is_ok());
    }
}
