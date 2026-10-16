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
enum RestoreOutcome { Unchanged, Waiting, Restored(LocalRestoredRecording) }

pub(crate) fn restore_local_product() -> Result<LocalRestoreReport,String> {
    restore_local(&crate::backend::audio_storage::recording_root()?,
        &crate::backend::persistence::state_file_path())
}
pub(crate) fn restore_local(root: &Path, index: &Path) -> Result<LocalRestoreReport,String> {
    let root=root.canonicalize().map_err(|e|format!("本机录音目录不可用，未修改恢复记录：{e}"))?;
    let loaded=session_store::load(index);
    if loaded.state.status=="blocked" {
        return Err(loaded.state.message.unwrap_or_else(fail));
    }
    let mut report=LocalRestoreReport::default();
    let Some(bytes)=loaded.bytes else {return Ok(report)};
    let rows:Vec<crate::companion_v1::CompanionV1HostSession>=serde_json::from_slice(&bytes).map_err(|_|fail())?;
    for row in rows.iter().filter(|row| row.source=="boardDevice" && row.device_recording_key.is_some() && row.retention.audio_cached) {
        let result=(|| {
            let key=super::super::SessionKey::from_public(row.device_recording_key.as_ref().unwrap())?;
            let device=row.source_device_id.as_deref().filter(|id|
                crate::backend::device_connection::stable_device_id(id)).ok_or_else(fail)?;
            let stem=format!("board-session-{:x}",Sha256::digest(serde_json::to_vec(&key).map_err(|_|fail())?));
            if row.audio_stored {
                // An indexed owned path is required. Privacy-disabled audio is
                // filtered above; never recreate a deliberately discarded copy.
                let expected=root.join(format!("{stem}.wav"));
                if row.audio_path.as_deref()!=expected.to_str() {return Err(fail())};
                if regular(&expected)? {return Ok(RestoreOutcome::Unchanged)};
            }
            let receipt=root.join(format!(".{stem}.json"));
            // No manifest means missing device data, not an invitation to create
            // a new receiver intent from a filename or a temporary tail.
            if !regular(&receipt)? {
                if row.audio_stored {return Err("本机回听文件及原音恢复记录缺失，未生成空录音或修改回收状态。".into())};
                return Ok(RestoreOutcome::Waiting)
            };
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
            if saved.device.as_deref().is_some_and(|id|
                !crate::backend::device_connection::same_device_id(id,device)) {return Err(fail())};
            let mut receiver=Receiver::open_for_local_repair(&root,&first.wire)?;
            if !receiver.plan()?.payloads_complete {return Ok(RestoreOutcome::Waiting)};
            let audio=receiver.assemble()?;
            let id=receiver.publish(index,device)?;
            if id!=row.id {return Err(fail())};
            let originals=receiver.descriptors()?.iter().map(|d|u64::from(d.encoded_length)).sum();
            let stored=receiver.receipt.audio.as_ref().ok_or_else(fail)?;
            Ok(RestoreOutcome::Restored(LocalRestoredRecording { session_id:id,audio_path:audio.to_string_lossy().into_owned(),
                original_bytes:originals,audio_bytes:stored.bytes,
                reclaim_pending:receiver.receipt.segments.iter().any(|segment|!segment.acked) }))
            // Tail replicas remain until normal authenticated sync retires them;
            // no fabricated radio Peer/ACK is used for local recovery.
        })();
        match result {
            Ok(RestoreOutcome::Restored(saved))=>report.restored.push(saved),
            Ok(RestoreOutcome::Waiting)=>report.waiting_for_segments.push(row.id.clone()),
            Ok(RestoreOutcome::Unchanged)=>(),
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
    fn saved_case()->(PathBuf,PathBuf,Descriptor,Vec<u8>,String,PathBuf,Vec<u8>,PathBuf) {
        let(root,index,d,payload,id)=case();
        session_store::update_checked(&index,|rows|{rows[0].processing_policy=
            crate::companion_v1::CompanionV1ProcessingPolicy::Manual;Ok(())}).unwrap();
        let mut r=Receiver::open(&root,&d.encode().unwrap()).unwrap();
        r.accept_segment(&d.encode().unwrap(),&payload).unwrap();let audio=r.assemble().unwrap();
        r.publish(&index,"C8:92:FF:DD:3B:CA").unwrap();
        let wav=fs::read(&audio).unwrap();let receipt=r.receipt_path();drop(r);
        (root,index,d,payload,id,audio,wav,receipt)
    }
    #[test]
    fn r62_missing_wav_rebuilds_exactly_after_reclaim_without_radio_or_repeat_decode() {
        let(root,index,d,payload,id,audio,wav,receipt)=saved_case();
        let mut r=Receiver::open(&root,&d.encode().unwrap()).unwrap();
        let acks=r.ack_candidates(&index).unwrap();assert_eq!(acks.len(),1);
        r.confirm_acked(&acks[0]).unwrap();r.publish(&index,"C8:92:FF:DD:3B:CA").unwrap();
        let original=r.payload_path(&d);drop(r);let before=fs::read(&receipt).unwrap();
        if let Some(destination)=std::env::var_os("COMPANION_LOCAL_RECOVERY_EVIDENCE_DIR") {
            // Optional isolated fixture for the installed ordinary CLI. It is
            // synthetic file-recovery evidence, never a physical recording.
            let destination=PathBuf::from(destination);fs::create_dir(&destination).unwrap();
            let destination=destination.canonicalize().unwrap();let old_root=root.canonicalize().unwrap();
            fn relocate(value:&mut serde_json::Value,old:&str,new:&str) {
                match value {
                    serde_json::Value::String(s) if s.starts_with(old)=>*s=format!("{new}{}",&s[old.len()..]),
                    serde_json::Value::Array(a)=>for v in a {relocate(v,old,new);},
                    serde_json::Value::Object(m)=>for v in m.values_mut() {relocate(v,old,new);},
                    _=>(),
                }
            }
            for entry in fs::read_dir(&root).unwrap() {
                let entry=entry.unwrap();let name=entry.file_name();let path=entry.path();
                if !path.is_file()||name.to_string_lossy().ends_with(".lock") {continue;}
                let mut bytes=fs::read(&path).unwrap();
                if path.extension().is_some_and(|e|e=="json"||e=="bak") {
                    let mut value:serde_json::Value=serde_json::from_slice(&bytes).unwrap();
                    relocate(&mut value,&old_root.to_string_lossy(),&destination.to_string_lossy());
                    bytes=serde_json::to_vec(&value).unwrap();
                }
                fs::write(destination.join(name),bytes).unwrap();
            }
            fs::write(destination.join("expected-wav.sha256"),format!("{:x}",Sha256::digest(&wav))).unwrap();
            fs::remove_file(destination.join(audio.file_name().unwrap())).unwrap();
        }
        fs::remove_file(&audio).unwrap();
        assert!(Receiver::open(&root,&d.encode().unwrap()).is_err(),"ordinary verification cannot silently rebuild or authorize consumption");
        assert!(!audio.exists());
        let report=restore_local(&root,&index).unwrap();assert!(report.failures.is_empty());
        assert_eq!(report.restored.len(),1);assert_eq!(report.restored[0].session_id,id);
        assert!(!report.restored[0].reclaim_pending);assert_eq!(report.device_commands,0);assert_eq!(report.cloud_calls,0);
        assert_eq!(fs::read(&audio).unwrap(),wav);assert_eq!(fs::read(original).unwrap(),payload);
        assert_eq!(fs::read(&receipt).unwrap(),before,"same receipt/SHA/timeline/reclaim history");
        let rows=crate::backend::persistence::load_sessions_from(&index).unwrap();
        assert!(rows[0].audio_stored&&rows[0].device_reclaimed);assert_eq!(rows[0].id,id);
        Receiver::verify_completed_row(&rows[0]).unwrap();
        let again=restore_local(&root,&index).unwrap();
        assert!(again.restored.is_empty()&&again.failures.is_empty()&&again.waiting_for_segments.is_empty());
        fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn r62_missing_wav_with_bad_raw_or_saved_hash_cannot_replace_evidence() {
        for bad_raw in [true,false] {
            let(root,index,d,payload,_,audio,_,receipt)=saved_case();
            let raw={let r=Receiver::open(&root,&d.encode().unwrap()).unwrap();r.payload_path(&d)};
            fs::remove_file(&audio).unwrap();
            if bad_raw {let mut corrupted=payload.clone();corrupted[15]^=1;fs::write(&raw,corrupted).unwrap();}
            else {
                let mut body:serde_json::Value=serde_json::from_slice(&fs::read(&receipt).unwrap()).unwrap();
                body["audio"]["sha256"]=serde_json::json!("00".repeat(32));
                fs::write(&receipt,serde_json::to_vec(&body).unwrap()).unwrap();
            }
            let before=fs::read(&receipt).unwrap();let old_index=fs::read(&index).unwrap();let source=fs::read(&raw).unwrap();
            let report=restore_local(&root,&index).unwrap();
            assert_eq!(report.failures.len(),1);assert!(report.restored.is_empty());
            assert_eq!(report.device_commands,0);assert!(!audio.exists());
            assert_eq!(fs::read(&receipt).unwrap(),before);assert_eq!(fs::read(&index).unwrap(),old_index);
            assert_eq!(fs::read(&raw).unwrap(),source);fs::remove_dir_all(root).unwrap();
        }
    }
    #[test]
    fn r62_privacy_disabled_audio_and_foreign_index_path_are_never_recreated() {
        for privacy in [true,false] {
            let(root,index,_,_,_,audio,_,receipt)=saved_case();fs::remove_file(&audio).unwrap();
            session_store::update_checked(&index,|rows| {
                if privacy {rows[0].retention.audio_cached=false;}
                else {rows[0].audio_path=Some(root.join("unowned.wav").to_string_lossy().into_owned());}
                Ok(())
            }).unwrap();
            let before=fs::read(&receipt).unwrap();let old_index=fs::read(&index).unwrap();
            let report=restore_local(&root,&index).unwrap();assert!(report.restored.is_empty());
            assert_eq!(report.failures.len(),usize::from(!privacy));
            assert!(!audio.exists()&&!root.join("unowned.wav").exists());
            assert_eq!(fs::read(&receipt).unwrap(),before);assert_eq!(fs::read(&index).unwrap(),old_index);
            fs::remove_dir_all(root).unwrap();
        }
    }
    #[cfg(windows)]
    #[test]
    fn r62_real_locked_index_keeps_original_and_recovers_after_unlock() {
        use std::os::windows::fs::OpenOptionsExt;
        let(root,index,d,payload,id)=case();
        let mut r=Receiver::open(&root,&d.encode().unwrap()).unwrap();
        r.accept_segment(&d.encode().unwrap(),&payload).unwrap();let raw=r.payload_path(&d);let receipt=r.receipt_path();drop(r);
        let original_index=fs::read(&index).unwrap();
        let guard=OpenOptions::new().read(true).share_mode(1).open(&index).unwrap();
        let failed=restore_local(&root,&index).unwrap();assert_eq!(failed.failures.len(),1);assert!(failed.restored.is_empty());
        assert_eq!(failed.device_commands,0);assert_eq!(fs::read(&index).unwrap(),original_index);
        let saved:Receipt=serde_json::from_slice(&fs::read(receipt).unwrap()).unwrap();
        assert!(saved.segments[0].received&&!saved.segments[0].acked);assert_eq!(fs::read(raw).unwrap(),payload);
        drop(guard);let recovered=restore_local(&root,&index).unwrap();
        assert!(recovered.failures.is_empty());assert_eq!(recovered.restored.len(),1);
        assert_eq!(recovered.restored[0].session_id,id);assert!(recovered.restored[0].reclaim_pending);
        assert_eq!(recovered.device_commands,0);assert_eq!(recovered.cloud_calls,0);
        fs::remove_dir_all(root).unwrap();
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
