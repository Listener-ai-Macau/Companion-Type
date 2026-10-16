use super::*;
use crate::companion_v1::{
    CompanionV1AudioChunk, CompanionV1ControlAction, CompanionV1ControlRequest,
};

impl Receiver {
    fn received_device_marks(&self)->Result<Vec<crate::backend::recording_bookmarks::device::DeviceMark>,String> {
        let mut marks=Vec::new();
        for (segment,d) in self.receipt.segments.iter().zip(self.descriptors()?) {
            if !segment.received {continue;}
            let mut file=read_locked(&self.payload_path(&d))?;let mut head=[0;12];
            file.read_exact(&mut head).map_err(|_|fail())?;
            if head[4]!=3 {continue;} // Existing schema1/2 recordings are unchanged.
            file.seek(SeekFrom::Start(0)).map_err(|_|fail())?;
            file=verify_file(file,&d)?;file.seek(SeekFrom::Start(0)).map_err(|_|fail())?;
            let mut reader=cop1::Reader::new(file,d.sample_offset,false)?;
            while let Some(record)=reader.next()? {
                if let cop1::Record::Event(event)=record {
                    if event.kind==4 {
                        if marks.len()>=1024 {return Err("设备重点超过单场上限，原音保留。".into());}
                        marks.push(crate::backend::recording_bookmarks::device::DeviceMark{descriptor:d.clone(),event});
                    }
                }
            }
            reader.finish(d.flags&4!=0)?;
        }
        Ok(marks)
    }
    fn complete_captured_samples(&self)->Option<u64> {
        self.receipt.audio.as_ref().and_then(|a|a.timeline.as_ref().map(|t|t.captured_samples)
            // Schema1 has no pause events; verify_audio/decode still prove the
            // exact frame/sample count and one 320-sample logical pre-skip.
            .or_else(||a.samples.checked_add(320)))
    }
    /// An idempotent user STOP can return the existing completed result only
    /// after reopening the exact receipt and rechecking original segments/WAV.
    /// This performs no GATT, cloud call or physical consume.
    pub(crate) fn verify_completed_row(row: &crate::companion_v1::CompanionV1HostSession) -> Result<(),String> {
        Self::verify_saved_row_inner(row, true, None).map(|_|())
    }
    /// A verified local original remains usable before physical consumption.
    /// This never authorizes an ACK or substitutes for a device reclaim receipt.
    pub(crate) fn verify_saved_row(row: &crate::companion_v1::CompanionV1HostSession) -> Result<(),String> {
        Self::verify_saved_row_inner(row, false, None).map(|_|())
    }
    /// Local deletion may retire a recovered control journal without forging
    /// a STOP acknowledgement. Require a complete LAST original, canonical
    /// raw/WAV receipt and the exact physical START anchor; no device command.
    pub(crate) fn verify_closed_original(row:&crate::companion_v1::CompanionV1HostSession,
        anchor:u32)->Result<(),String> {
        if anchor==0 || row.source!="boardDevice" || row.device_recording_id!=Some(anchor) {
            return Err(fail());
        }
        Self::verify_saved_row_inner(row,false,Some(anchor)).map(|_|())
    }
    pub(crate) fn verified_source_timeline(row:&crate::companion_v1::CompanionV1HostSession)->Result<Option<cop1::Timeline>,String> {
        Self::verify_saved_row_inner(row,false,None)
    }
    fn verify_saved_row_inner(row: &crate::companion_v1::CompanionV1HostSession, require_reclaimed: bool,
        original_anchor:Option<u32>) -> Result<Option<cop1::Timeline>,String> {
        let key = super::super::SessionKey::from_public(row.device_recording_key.as_ref().ok_or_else(fail)?)?;
        let audio = Path::new(row.audio_path.as_deref().ok_or_else(fail)?);
        if !audio.is_absolute() {return Err(fail());}
        let root = audio.parent().ok_or_else(fail)?;
        let stem = format!("board-session-{:x}",Sha256::digest(serde_json::to_vec(&key).map_err(|_| fail())?));
        let receipt_path = root.join(format!(".{stem}.json"));
        let mut body=Vec::new();read_locked(&receipt_path)?.take(MAX_RECEIPT+1).read_to_end(&mut body).map_err(|_| fail())?;
        if body.len() as u64 > MAX_RECEIPT {return Err(fail());}
        let receipt:Receipt=serde_json::from_slice(&body).map_err(|_| fail())?;
        let first=receipt.segments.first().ok_or_else(fail)?;
        let first_descriptor=Descriptor::decode(&first.wire)?;
        if first_descriptor.key != key || original_anchor.is_some_and(|anchor|
            first_descriptor.recording_id!=anchor || first_descriptor.segment_index!=0 || first_descriptor.sample_offset!=0) {
            return Err(fail());
        }
        let mut receiver=Receiver::open(root,&first.wire)?;
        let plan=receiver.plan()?;
        if receiver.descriptors()?.iter().find(|d|d.flags&2!=0).and_then(Descriptor::end_reason)
            .is_some_and(|reason|row.device_recording_end_reason!=Some(reason)) {return Err(fail());}
        if !plan.payloads_complete || receiver.receipt.audio.is_none() || receiver.audio_path()!=audio
            || receiver.receipt.device.as_deref().zip(row.source_device_id.as_deref())
                .is_none_or(|(a,b)|!crate::backend::device_connection::same_device_id(a,b))
            || receiver.receipt.segments.iter().any(|s| !s.received || (require_reclaimed && !s.acked))
            || !row.audio_stored || (require_reclaimed && !row.device_reclaimed) || !row.retention.audio_cached {
            return Err(fail());
        }
        let ds=receiver.descriptors()?;
        for d in ds {
            if !row.chunks.iter().any(|c| c.id==Self::chunk_id(&d)
                && c.path.as_deref()==Some(receiver.payload_path(&d).to_string_lossy().as_ref())
                && c.bytes==u64::from(d.encoded_length) && matches!(c.status.as_str(),"sealed"|"synced")) {return Err(fail());}
        }
        Ok(receiver.receipt.audio.as_ref().and_then(|a|a.timeline.clone()))
    }
    /// Checkpoint an incomplete meeting as well as a complete one. Sealed raw
    /// segments are discoverable after restart before any device consumption;
    /// incomplete rows never arm ASR or claim a playable final WAV.
    pub(crate) fn publish(&mut self, index: &Path, device: &str) -> Result<String, String> {
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
        let end_reason=ds.iter().find(|d|d.flags&2!=0).and_then(Descriptor::end_reason);
        let logical_key = ds.first().ok_or_else(fail)?.key.public_key();
        let device_marks=self.received_device_marks()?;
        let complete_samples=self.complete_captured_samples();
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
        let local_audio_pending=plan.payloads_complete && !complete;
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
        // Known sealed segments can be consumed while the session grows. Only
        // a complete LAST catalogue plus all exact receipts retires the whole
        // session; missing metadata must not hide a tail or a missing segment.
        let reclaimed = plan.metadata_complete && !self.receipt.segments.is_empty()
            && self.receipt.segments.iter().all(|s| s.received && s.acked);
        let mut published_id = self.stem.clone();
        session_store::update_checked(index, |sessions| {
            let mut next = sessions.clone();
            let binding = self.library_binding(&next, &logical_key)?;
            if let Some(old) = binding.map(|i| &next[i]) {
                if old.source != "boardDevice"
                    || (old.audio_path.as_deref().is_some_and(|p| p != audio_path)
                        && !owned_capture_placeholder(old, &logical_key))
                    || (old.audio_path.is_none() && !old.chunks.is_empty())
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
                let mut row=crate::companion_v1::synced_device_session(&snapshot,&request,"verified-v2-session");
                // An unknown device-local original has no host instruction to
                // run paid meeting processing. Saving/consuming is independent
                // of ASR. Existing rows keep their explicit processing choice.
                row.processing_policy=crate::companion_v1::CompanionV1ProcessingPolicy::Manual;
                row.recovery=Default::default();
                next.insert(0,row);
            }
            let s = &mut next[binding.unwrap_or(0)];
            published_id = s.id.clone();
            s.source = "boardDevice".into();
            s.source_device_id = Some(device.into());
            // V1 exact-ID bookkeeping must never reinterpret a V2 session as
            // one of its independent physical recordings.
            s.device_recording_key = Some(logical_key.clone());
            s.device_total_length = None;
            s.device_sha256 = None;
            s.device_reclaimed = reclaimed;
            // A missed terminal control may already have marked this exact
            // original interrupted. Complete payload is not proof of a clean
            // capture; never erase that warning while publishing its audio.
            s.capture_incomplete |= plan.capture_incomplete;
            if let Some(reason)=end_reason {
                if s.device_recording_end_reason.is_some_and(|saved|saved!=reason) {return Err(fail());}
                s.device_recording_end_reason=Some(reason);
            }
            s.audio_path = Some(audio_path.clone());
            s.audio_stored = complete;
            s.retention.audio_cached = true;
            s.audio_bytes = bytes;
            s.duration_ms = if s.status == "recording" && !complete { s.duration_ms.max(duration) } else { duration };
            s.chunks = chunks.clone();
            if !s.transcript_final {
                s.status = if complete || local_audio_pending { "captured" } else if s.status == "recording" { "recording" } else { "pending" }.into();
                s.pending_reason = Some(
                    if complete {
                        "needs_transcription"
                    } else if local_audio_pending {
                        "needs_local_audio"
                    } else {
                        "needs_segments"
                    }
                    .into(),
                );
                if complete {
                    crate::backend::arm_meeting_recovery(s);
                } else if !local_audio_pending && s.processing_policy != crate::companion_v1::CompanionV1ProcessingPolicy::Manual
                    && s.recovery.intent != crate::backend::pet_chat::CAPTURE_INTENT {
                    s.recovery = Default::default();
                }
            }
            crate::backend::recording_bookmarks::device::merge(s,&device_marks,
                &SessionKey::from_public(&logical_key)?,complete_samples)?;
            crate::backend::recording_bookmarks::logical::bind(s,
                &SessionKey::from_public(&logical_key)?,complete_samples)?;
            *sessions = next;
            Ok(())
        })?;
        self.receipt.device = Some(device.into());
        self.save()?;
        Ok(published_id)
    }
    fn library_binding(&self, rows: &[crate::companion_v1::CompanionV1HostSession],
        key: &crate::companion_v1::CompanionV1RecordingKey) -> Result<Option<usize>,String> {
        let mut indices = rows.iter().enumerate().filter(|(_,s)|
            s.device_recording_key.as_ref() == Some(key) || s.id == self.stem);
        let first = indices.next();
        if indices.next().is_some() || first.is_some_and(|(_,s)|
            s.device_recording_key.as_ref().is_some_and(|old| old != key)) { return Err(fail()); }
        Ok(first.map(|(i,_)| i))
    }
    /// Software ACKs only: exact immutable identity and full SHA, never an ID
    /// prefix. A present receipt cannot replace revalidation of payload and the
    /// library row. The caller must have negotiated a protected V2 peer.
    pub(crate) fn ack_candidates(&mut self, index: &Path) -> Result<Vec<Vec<u8>>, String> {
        self.recover()?;
        // Exact hashes do not make a replayed/contradictory pause timeline
        // correct. Validate all saved segments before authorizing consumption.
        self.verify_received_timeline()?;
        let device = self.receipt.device.as_deref().ok_or_else(fail)?;
        let loaded = session_store::load(index);
        if loaded.state.status == "blocked" {
            return Err(fail());
        }
        let sessions: Vec<crate::companion_v1::CompanionV1HostSession> =
            serde_json::from_slice(&loaded.bytes.ok_or_else(fail)?).map_err(|_| fail())?;
        let key = self.descriptors()?.first().ok_or_else(fail)?.key.public_key();
        let row = &sessions[self.library_binding(&sessions,&key)?.ok_or_else(fail)?];
        if self.descriptors()?.iter().find(|d|d.flags&2!=0).and_then(Descriptor::end_reason)
            .is_some_and(|reason|row.device_recording_end_reason!=Some(reason)) {return Err(fail());}
        if row.audio_path.as_deref() != Some(self.audio_path().to_string_lossy().as_ref())
            || !row
                .source_device_id
                .as_deref()
                .is_some_and(|id| crate::backend::device_connection::same_device_id(id, device))
            || !row.retention.audio_cached
        {
            return Err(fail());
        }
        crate::backend::recording_bookmarks::device::require_saved(row,&self.received_device_marks()?,
            &SessionKey::from_public(&key)?,self.complete_captured_samples())?;
        crate::backend::recording_bookmarks::logical::require_saved(row,
            &SessionKey::from_public(&key)?,self.complete_captured_samples())?;
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

// START can bind the verified logical device key before any host file exists.
// Replace only that exact row's virtual capture reference. A stored original,
// another session, a real pathname or a received segment is never reassigned.
fn owned_capture_placeholder(row: &crate::companion_v1::CompanionV1HostSession,
    key: &crate::companion_v1::CompanionV1RecordingKey) -> bool {
    let reference = format!("host://companion-type/recordings/{}.wav", row.id);
    row.source == "boardDevice" && row.device_recording_key.as_ref() == Some(key)
        && !row.audio_stored && !row.device_reclaimed && !row.transcript_final
        && row.audio_path.as_deref() == Some(reference.as_str())
        && row.chunks.iter().all(|chunk| {
            chunk.id.starts_with(&format!("{}-chunk-", row.id))
                && chunk.path.as_deref() == Some(reference.as_str())
                && matches!(chunk.status.as_str(), "open" | "paused")
        })
}

#[cfg(test)]
mod placeholder_tests {
    use super::*;
    #[test]
    fn only_the_unstored_verified_capture_reference_can_be_bound_to_real_segments() {
        let snapshot = crate::companion_v1::fixture_snapshot();
        let request = CompanionV1ControlRequest { action: CompanionV1ControlAction::DeviceSyncRecordings,
            ble_name: None, session_id: Some("owned-capture".into()), prompt_id: None,
            title: None, transcript_text: None, meeting_mode: Some("offlineStore".into()),
            audio_path: Some("host://companion-type/recordings/owned-capture.wav".into()),
            audio_bytes: Some(0), device_id: Some("C8:92:FF:DD:3B:CA".into()), duration_ms: Some(0) };
        let mut row = crate::companion_v1::synced_device_session(&snapshot, &request, "capture");
        let key = super::super::super::SessionKey { device_uid: [1;12], format_epoch: 2, session_id: 3 }.public_key();
        row.source="boardDevice".into();
        row.device_recording_key = Some(key.clone()); row.audio_stored=false;
        row.device_reclaimed=false; row.transcript_final=false;
        row.chunks.clear();
        row.chunks.push(CompanionV1AudioChunk { id:format!("{}-chunk-1",row.id),path:row.audio_path.clone(),
            started_at:None,stopped_at:None,duration_ms:0,bytes:0,status:"open".into() });
        assert!(owned_capture_placeholder(&row,&key));
        let mut other = key.clone(); other.session_id="0000000000000004".into();
        assert!(!owned_capture_placeholder(&row,&other));
        row.audio_stored=true;assert!(!owned_capture_placeholder(&row,&key));row.audio_stored=false;
        row.device_reclaimed=true;assert!(!owned_capture_placeholder(&row,&key));row.device_reclaimed=false;
        row.audio_path=Some("C:/original.wav".into());assert!(!owned_capture_placeholder(&row,&key));
        row.audio_path=request.audio_path;
        row.chunks.push(CompanionV1AudioChunk { id:"segment-0-9-proof".into(),path:row.audio_path.clone(),
            started_at:None,stopped_at:None,duration_ms:0,bytes:42,status:"sealed".into() });
        assert!(!owned_capture_placeholder(&row,&key));
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
