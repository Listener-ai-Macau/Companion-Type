use super::*;
use crate::companion_v1::{
    CompanionV1AudioChunk, CompanionV1ControlAction, CompanionV1ControlRequest,
};

impl Receiver {
    /// Checkpoint an incomplete meeting as well as a complete one. Sealed raw
    /// segments are discoverable after restart before any device consumption;
    /// incomplete rows never arm ASR or claim a playable final WAV.
    pub(crate) fn publish(&mut self, index: &Path, device: &str) -> Result<(), String> {
        if !crate::backend::device_connection::stable_device_id(device) {
            return Err(fail());
        }
        if self
            .receipt
            .device
            .as_deref()
            .is_some_and(|old| !crate::backend::device_connection::same_device_id(old, device))
        {
            return Err(fail());
        }
        let plan = self.plan()?;
        let ds = self.descriptors()?;
        let mut chunks = Vec::new();
        let mut bytes = 0u64;
        for (segment, d) in self.receipt.segments.iter().zip(&ds) {
            if !segment.received {
                continue;
            }
            chunks.push(CompanionV1AudioChunk {
                id: Self::chunk_id(d),
                path: Some(self.payload_path(d).to_string_lossy().into_owned()),
                started_at: None,
                stopped_at: Some("verified-v2-segment".into()),
                duration_ms: d.sample_count / 16,
                bytes: u64::from(d.encoded_length),
                status: "sealed".into(),
            });
            bytes += u64::from(d.encoded_length);
        }
        let audio_path = self.audio_path().to_string_lossy().into_owned();
        let complete = self.receipt.audio.is_some();
        if let Some(audio) = &self.receipt.audio {
            self.verify_audio(audio)?;
            bytes = audio.bytes;
            chunks.push(CompanionV1AudioChunk {
                id: format!("{}-received", self.stem),
                path: Some(audio_path.clone()),
                started_at: None,
                stopped_at: Some("verified-v2-session".into()),
                duration_ms: audio.samples / 16,
                bytes: audio.bytes,
                status: "synced".into(),
            });
        }
        let duration = self
            .receipt
            .audio
            .as_ref()
            .map(|a| a.samples / 16)
            .unwrap_or(plan.sample_count / 16);
        let reclaimed = !self.receipt.segments.is_empty()
            && self.receipt.segments.iter().all(|s| s.received && s.acked);
        session_store::update_checked(index, |sessions| {
            let mut next = sessions.clone();
            if let Some(old) = next.iter().find(|s| s.id == self.stem) {
                if old.audio_path.as_deref() != Some(audio_path.as_str())
                    || old.source_device_id.as_deref().is_some_and(|old| {
                        !crate::backend::device_connection::same_device_id(old, device)
                    })
                    || old
                        .chunks
                        .iter()
                        .filter(|c| c.id.starts_with("segment-"))
                        .any(|old| {
                            !chunks.iter().any(|c| {
                                c.id == old.id && c.path == old.path && c.bytes == old.bytes
                            })
                        })
                {
                    return Err(fail());
                }
            } else {
                let snapshot = crate::companion_v1::fixture_snapshot();
                let request = CompanionV1ControlRequest {
                    action: CompanionV1ControlAction::DeviceSyncRecordings,
                    ble_name: None,
                    session_id: Some(self.stem.clone()),
                    prompt_id: None,
                    title: Some("设备分段录音".into()),
                    transcript_text: None,
                    meeting_mode: Some("offlineStore".into()),
                    audio_path: Some(audio_path.clone()),
                    audio_bytes: Some(bytes),
                    device_id: Some(device.into()),
                    duration_ms: Some(duration),
                };
                next.insert(
                    0,
                    crate::companion_v1::synced_device_session(
                        &snapshot,
                        &request,
                        "verified-v2-session",
                    ),
                );
            }
            let s = next
                .iter_mut()
                .find(|s| s.id == self.stem)
                .expect("inserted session");
            s.source = "boardDevice".into();
            s.source_device_id = Some(device.into());
            // V1 exact-ID bookkeeping must never reinterpret a V2 session as
            // one of its independent physical recordings.
            s.device_recording_id = None;
            s.device_total_length = None;
            s.device_sha256 = None;
            s.device_reclaimed = reclaimed;
            s.capture_incomplete = plan.capture_incomplete;
            s.audio_path = Some(audio_path.clone());
            s.audio_stored = complete;
            s.retention.audio_cached = true;
            s.audio_bytes = bytes;
            s.duration_ms = duration;
            s.chunks = chunks.clone();
            if !s.transcript_final {
                s.status = if complete { "captured" } else { "pending" }.into();
                s.pending_reason = Some(
                    if complete {
                        "needs_transcription"
                    } else {
                        "needs_segments"
                    }
                    .into(),
                );
                if complete {
                    crate::backend::arm_meeting_recovery(s);
                } else {
                    s.recovery = Default::default();
                }
            }
            *sessions = next;
            Ok(())
        })?;
        self.receipt.device = Some(device.into());
        self.save()
    }
    /// Software ACKs only: exact immutable identity and full SHA, never an ID
    /// prefix. A present receipt cannot replace revalidation of payload and the
    /// library row. The radio remains disabled until WBA implements this schema.
    pub(crate) fn ack_candidates(&mut self, index: &Path) -> Result<Vec<Vec<u8>>, String> {
        self.recover()?;
        let device = self.receipt.device.as_deref().ok_or_else(fail)?;
        let loaded = session_store::load(index);
        if loaded.state.status == "blocked" {
            return Err(fail());
        }
        let sessions: Vec<crate::companion_v1::CompanionV1HostSession> =
            serde_json::from_slice(&loaded.bytes.ok_or_else(fail)?).map_err(|_| fail())?;
        let row = sessions
            .iter()
            .find(|s| s.id == self.stem)
            .ok_or_else(fail)?;
        if row.audio_path.as_deref() != Some(self.audio_path().to_string_lossy().as_ref())
            || !row
                .source_device_id
                .as_deref()
                .is_some_and(|id| crate::backend::device_connection::same_device_id(id, device))
            || !row.retention.audio_cached
        {
            return Err(fail());
        }
        let mut acks = Vec::new();
        for (s, d) in self.receipt.segments.iter().zip(self.descriptors()?) {
            if !s.received || s.acked {
                continue;
            }
            let path = self.payload_path(&d).to_string_lossy().into_owned();
            if !row.chunks.iter().any(|c| {
                c.id == Self::chunk_id(&d)
                    && c.path.as_deref() == Some(&path)
                    && c.bytes == u64::from(d.encoded_length)
                    && matches!(c.status.as_str(), "sealed" | "synced")
            }) {
                return Err(fail());
            }
            acks.push(ack(&d));
        }
        Ok(acks)
    }
    /// Call only after an authenticated exact device response. A lost response
    /// leaves the ACK retryable; a duplicate receipt is idempotent.
    pub(crate) fn confirm_acked(&mut self, wire: &[u8]) -> Result<(), String> {
        if self.receipt.device.is_none()
            || wire.len() != ACK_BYTES
            || &wire[..8] != b"CRA2\x02\x00\x54\x00"
            || crc32fast::hash(&wire[..80]) != super::super::u32le(wire, 80)
        {
            return Err(fail());
        }
        let ds = self.descriptors()?;
        let i = ds.iter().position(|d| ack(d) == wire).ok_or_else(fail)?;
        if !self.receipt.segments[i].received {
            return Err(fail());
        }
        if self.receipt.segments[i].acked {
            return Ok(());
        }
        self.receipt.segments[i].acked = true;
        if let Err(e) = self.save() {
            self.receipt.segments[i].acked = false;
            return Err(e);
        }
        Ok(())
    }
}
pub(super) fn ack(d: &Descriptor) -> Vec<u8> {
    let mut p = vec![0; ACK_BYTES];
    p[..8].copy_from_slice(b"CRA2\x02\x00\x54\x00");
    p[8..20].copy_from_slice(&d.key.device_uid);
    p[20..28].copy_from_slice(&d.key.format_epoch.to_le_bytes());
    p[28..36].copy_from_slice(&d.key.session_id.to_le_bytes());
    p[36..40].copy_from_slice(&d.segment_index.to_le_bytes());
    p[40..44].copy_from_slice(&d.recording_id.to_le_bytes());
    p[44..48].copy_from_slice(&d.encoded_length.to_le_bytes());
    p[48..80].copy_from_slice(&d.sha256);
    let crc = crc32fast::hash(&p[..80]);
    p[80..84].copy_from_slice(&crc.to_le_bytes());
    p
}
