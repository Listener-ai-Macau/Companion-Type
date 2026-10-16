//! Finish an already received device original without a radio or cloud service.
//! Only indexed, exact logical identities are admitted; this cannot consume a
//! device segment or turn a growing prefix into a sealed original.
use super::*;

#[derive(Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct LocalRestoreReport {
    pub(crate) restored: Vec<LocalRestoredRecording>,
    pub(crate) waiting_for_segments: Vec<String>,
    pub(crate) failures: Vec<LocalRestoreFailure>,
    device_commands: u32,
    cloud_calls: u32,
}
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct LocalRestoredRecording {
    pub(crate) session_id: String,
    audio_path: String,
    original_bytes: u64,
    audio_bytes: u64,
    reclaim_pending: bool,
}
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct LocalRestoreFailure { session_id: String, error: String }

pub(crate) fn restore_local_product() -> Result<LocalRestoreReport,String> {
    restore_local(&crate::backend::audio_storage::recording_root()?,
        &crate::backend::persistence::state_file_path())
}
pub(crate) fn restore_local(root: &Path, index: &Path) -> Result<LocalRestoreReport,String> {
    let loaded=session_store::load(index);
    if loaded.state.status=="blocked" {
        return Err(loaded.state.message.unwrap_or_else(fail));
    }
    let mut report=LocalRestoreReport::default();
    let Some(bytes)=loaded.bytes else {return Ok(report)};
    let rows:Vec<crate::companion_v1::CompanionV1HostSession>=serde_json::from_slice(&bytes).map_err(|_|fail())?;
    for row in rows.iter().filter(|row| row.source=="boardDevice" && row.device_recording_key.is_some() && !row.audio_stored) {
        let result=(|| {
            let key=super::super::SessionKey::from_public(row.device_recording_key.as_ref().unwrap())?;
            let device=row.source_device_id.as_deref().filter(|id|
                crate::backend::device_connection::stable_device_id(id)).ok_or_else(fail)?;
            let stem=format!("board-session-{:x}",Sha256::digest(serde_json::to_vec(&key).map_err(|_|fail())?));
            let receipt=root.join(format!(".{stem}.json"));
            // No manifest means missing device data, not an invitation to create
            // a new receiver intent from a filename or a temporary tail.
            if !regular(&receipt)? {return Ok(None)};
            let mut bytes=Vec::new();read_locked(&receipt)?.take(MAX_RECEIPT+1)
                .read_to_end(&mut bytes).map_err(|_|fail())?;
            if bytes.len() as u64>MAX_RECEIPT {return Err(fail())};
            let saved:Receipt=serde_json::from_slice(&bytes).map_err(|_|fail())?;
            let first=saved.segments.first().ok_or_else(fail)?;
            let descriptor=Descriptor::decode(&first.wire)?;
            if descriptor.key!=key || saved.segments.iter().any(|segment|
                Descriptor::decode(&segment.wire).map_or(true,|d| d.key!=key || d.source_mode!=super::super::SOURCE_MIC_SAI)) {
                return Err(fail());
            }
            // open/plan revalidate exact full original hashes, CRCs, frame/sample
            // axes and the receiver lock. A partial body cannot become playable.
            let mut receiver=Receiver::open(root,&first.wire)?;
            if !receiver.plan()?.payloads_complete {return Ok(None)};
            let audio=receiver.assemble()?;
            let id=receiver.publish(index,device)?;
            if id!=row.id {return Err(fail())};
            let originals=receiver.descriptors()?.iter().map(|d|u64::from(d.encoded_length)).sum();
            let stored=receiver.receipt.audio.as_ref().ok_or_else(fail)?;
            Ok(Some(LocalRestoredRecording { session_id:id,audio_path:audio.to_string_lossy().into_owned(),
                original_bytes:originals,audio_bytes:stored.bytes,
                reclaim_pending:receiver.receipt.segments.iter().any(|segment|!segment.acked) }))
            // Tail replicas remain until normal authenticated sync retires them;
            // no fabricated radio Peer/ACK is used for local recovery.
        })();
        match result {
            Ok(Some(saved))=>report.restored.push(saved),
            Ok(None)=>report.waiting_for_segments.push(row.id.clone()),
            Err(error)=>report.failures.push(LocalRestoreFailure {session_id:row.id.clone(),error}),
        }
    }
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn case() -> (PathBuf,PathBuf,Descriptor,Vec<u8>,String) {
        let root=std::env::temp_dir().join(format!("companion-local-original-{}",uuid::Uuid::new_v4()));
        fs::create_dir_all(&root).unwrap();let index=root.join("sessions.json");
        let key=super::super::super::SessionKey {device_uid:[7;12],format_epoch:11,session_id:13};
        let mut payload=b"COP1\x01\x01\x14\x00\x80\x3e\x00\x00".to_vec();
        for _ in 0..3 {payload.extend_from_slice(&[3,0,0xf8,0xff,0xfe])}
        let d=Descriptor {key,recording_id:17,segment_index:0,sample_offset:0,sample_count:960,
            encoded_length:payload.len() as u32,content_crc32:crc32fast::hash(&payload),sha256:Sha256::digest(&payload).into(),
            total_segments:1,flags:3,codec:3,source_mode:1,sync_state:1};
        let id="captured-owned-row".to_string();let reference=format!("host://companion-type/recordings/{id}.wav");
        let request=crate::companion_v1::CompanionV1ControlRequest {action:crate::companion_v1::CompanionV1ControlAction::DeviceSyncRecordings,
            ble_name:None,session_id:Some(id.clone()),prompt_id:None,title:None,transcript_text:None,meeting_mode:Some("offlineStore".into()),
            audio_path:Some(reference.clone()),audio_bytes:Some(1920000),device_id:Some("C8:92:FF:DD:3B:CA".into()),duration_ms:Some(60000)};
        let mut row=crate::companion_v1::synced_device_session(&crate::companion_v1::fixture_snapshot(),&request,"capture");
        row.source="boardDevice".into();row.audio_stored=false;row.device_recording_key=Some(d.key.public_key());
        row.chunks=vec![crate::companion_v1::CompanionV1AudioChunk {id:format!("{id}-chunk-1"),path:Some(reference),
            started_at:None,stopped_at:None,duration_ms:60000,bytes:1920000,status:"open".into()}];
        session_store::update_checked(&index,|rows| {rows.push(row);Ok(())}).unwrap();
        (root,index,d,payload,id)
    }
    #[test]
    fn complete_raw_with_unpublished_capture_recovers_without_radio_and_without_ack() {
        let (root,index,d,payload,id)=case();
        {let mut r=Receiver::open(&root,&d.encode().unwrap()).unwrap();r.accept_segment(&d.encode().unwrap(),&payload).unwrap();}
        let report=restore_local(&root,&index).unwrap();assert!(report.failures.is_empty());
        assert_eq!(report.restored.len(),1);assert_eq!(report.restored[0].session_id,id);
        assert!(report.restored[0].reclaim_pending);assert_eq!(report.device_commands,0);
        let rows:Vec<crate::companion_v1::CompanionV1HostSession>=serde_json::from_slice(&session_store::load(&index).bytes.unwrap()).unwrap();
        assert!(rows[0].audio_stored && !rows[0].device_reclaimed);
        let r=Receiver::open(&root,&d.encode().unwrap()).unwrap();assert!(r.receipt.audio.is_some() && !r.receipt.segments[0].acked);
        assert_eq!(rows[0].audio_path.as_deref(),Some(r.audio_path().to_str().unwrap()));drop(r);
        assert!(restore_local(&root,&index).unwrap().restored.is_empty(),"already saved audio is not repeatedly decoded");
        fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn missing_or_corrupt_original_does_not_publish_or_authorize_reclaim() {
        let (root,index,d,payload,_)=case();
        {let r=Receiver::open(&root,&d.encode().unwrap()).unwrap();assert!(r.receipt.audio.is_none());}
        let pending=restore_local(&root,&index).unwrap();assert_eq!(pending.waiting_for_segments.len(),1);assert!(pending.restored.is_empty());
        {let mut r=Receiver::open(&root,&d.encode().unwrap()).unwrap();r.accept_segment(&d.encode().unwrap(),&payload).unwrap();
         let mut corrupt=payload.clone();corrupt[15]^=1;fs::write(r.payload_path(&d),corrupt).unwrap();}
        let failed=restore_local(&root,&index).unwrap();assert_eq!(failed.failures.len(),1);assert!(failed.restored.is_empty());
        let rows:Vec<crate::companion_v1::CompanionV1HostSession>=serde_json::from_slice(&session_store::load(&index).bytes.unwrap()).unwrap();
        assert!(!rows[0].audio_stored && !rows[0].device_reclaimed && rows[0].audio_path.as_ref().unwrap().starts_with("host://"));
        fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn r52_new_local_original_defaults_manual_but_keeps_later_explicit_choice() {
        use crate::companion_v1::CompanionV1ProcessingPolicy as Policy;
        let(root,index,d,payload,_)=case();
        session_store::update_checked(&index,|rows|{rows.clear();Ok(())}).unwrap();
        let mut receiver=Receiver::open(&root,&d.encode().unwrap()).unwrap();
        let id=receiver.publish(&index,"C8:92:FF:DD:3B:CA").unwrap();
        let rows=crate::backend::persistence::load_sessions_from(&index).unwrap();
        assert_eq!(rows.len(),1);assert_eq!(rows[0].processing_policy,Policy::Manual);
        assert_eq!(rows[0].recovery.intent,"none");assert!(!rows[0].audio_stored);
        receiver.accept_segment(&d.encode().unwrap(),&payload).unwrap();receiver.assemble().unwrap();
        receiver.publish(&index,"C8:92:FF:DD:3B:CA").unwrap();
        let rows=crate::backend::persistence::load_sessions_from(&index).unwrap();
        assert_eq!(rows[0].id,id);assert_eq!(rows[0].processing_policy,Policy::Manual);
        assert_eq!(rows[0].recovery.intent,"none");assert!(rows[0].audio_stored);
        assert_eq!(receiver.ack_candidates(&index).unwrap().len(),1,"local saving still authorizes exact consumption without ASR");
        session_store::update_checked(&index,|rows|{rows[0].processing_policy=Policy::Automatic;Ok(())}).unwrap();
        receiver.publish(&index,"C8:92:FF:DD:3B:CA").unwrap();
        let rows=crate::backend::persistence::load_sessions_from(&index).unwrap();
        assert_eq!(rows[0].processing_policy,Policy::Automatic);
        assert_eq!(rows[0].recovery.intent,"processMeeting","a later explicit choice is not overwritten by the manual default");
        drop(receiver);fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn manual_processing_policy_survives_partial_and_complete_source_publication() {
        use crate::companion_v1::CompanionV1ProcessingPolicy as Policy;
        let (root,index,d,payload,id)=case();
        session_store::update_checked(&index,|rows| {
            let row=rows.iter_mut().find(|r|r.id==id).unwrap();
            row.processing_policy=Policy::Manual;row.recovery=Default::default();Ok(())
        }).unwrap();
        let mut receiver=Receiver::open(&root,&d.encode().unwrap()).unwrap();
        receiver.publish(&index,"C8:92:FF:DD:3B:CA").unwrap();
        receiver.accept_segment(&d.encode().unwrap(),&payload).unwrap();receiver.assemble().unwrap();
        receiver.publish(&index,"C8:92:FF:DD:3B:CA").unwrap();
        let rows=crate::backend::persistence::load_sessions_from(&index).unwrap();
        let row=rows.iter().find(|r|r.id==id).unwrap();assert_eq!(row.processing_policy,Policy::Manual);
        assert_eq!(row.recovery.intent,"none");assert!(row.audio_stored && !row.device_reclaimed);
        assert_eq!(receiver.ack_candidates(&index).unwrap().len(),1,"manual processing still allows exact local sync/consume");
        drop(receiver);fs::remove_dir_all(root).unwrap();
    }
}
