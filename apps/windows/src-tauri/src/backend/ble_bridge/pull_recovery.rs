//! Re-arm only a failed receive queue, against the same sealed original.
//! Each attempt closes its old receiver and durable file lease before retrying.
use futures::future::BoxFuture;

const MAX_RECEIVER_RESTARTS: usize = 3;

pub(super) trait Attempt {
    fn receive(&mut self) -> BoxFuture<'_, Result<Vec<u8>, String>>;
}

pub(super) fn receiver_overrun(error: &str) -> bool {
    if error.contains(super::pull_session::RETIRED_CLEANUP) {return false;}
    error.starts_with("recording receive queue overflow;")
        || error.starts_with("recording native receive:")
            && error.contains("Windows BLE notification queue overflow:")
}

pub(super) fn transport_lost(error: &str) -> bool {
    let lower = error.to_ascii_lowercase();
    // WinRT text may be localized; RO_E_CLOSED is stable on either locale.
    lower.contains("0x80000013")
        || lower.contains("对象已关闭")
        || lower.contains("object") && lower.contains("closed")
        || lower.contains("gattcommunicationstatus(1)")
        || lower.contains("not connected")
        || lower.contains("disconnect")
        || lower.contains("notification stream ended")
        || lower.contains("recording chunk notify timeout")
        || lower.contains("resume write timed out")
        || lower.contains("write recording_chunk_pull start timed out")
        || lower.starts_with("recording transfer stalled after 3 resume requests")
}

pub(super) fn retire_connection(error: &str) -> bool {
    receiver_overrun(error) || transport_lost(error)
        || error.contains(super::pull_session::RETIRED_CLEANUP)
        || error.starts_with("sealed stream release failed before reclaim:")
}

pub(super) async fn receive<P: Attempt>(port: &mut P, sealed_original: bool, recording_id: u32)
    -> Result<Vec<u8>, String>
{
    let started = std::time::Instant::now();
    let mut restarts = 0;
    loop {
        match port.receive().await {
            Err(error) if sealed_original && receiver_overrun(&error) && restarts < MAX_RECEIVER_RESTARTS => {
                restarts += 1;
                // The port has already dropped/joined its storage worker and
                // unsubscribed both lanes. A new attempt validates/reopens the
                // persisted cursor, rather than trusting the in-memory offset.
                eprintln!("recording pull receive_queue_restart id={recording_id} attempt={restarts}/{MAX_RECEIVER_RESTARTS} durable_cursor=1 same_protected_connection=1 cause={error}");
            },
            result => {
                if restarts > 0 {
                    // Keep recovery/setup/checkpoint time visible. The inner
                    // packet rate describes only that individual attempt.
                    eprintln!("recording pull receive_queue_recovery_end id={recording_id} restarts={restarts} success={} total_receive_ms={} includes_recovery=true", result.is_ok(), started.elapsed().as_millis());
                }
                return result;
            },
        }
    }
}

#[cfg(test)]
mod tests;
