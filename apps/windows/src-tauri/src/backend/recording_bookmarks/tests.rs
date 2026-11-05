use super::*;
use crate::companion_v1::{apply_fixture_control,fixture_snapshot};
fn session() -> CompanionV1HostSession {
    let mut s=apply_fixture_control(fixture_snapshot(),serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap()).unwrap().host.sessions.remove(0);
    s.id="own-meeting".into(); s.bookmarks.clear(); s.bookmark_revision=0;
    s.status="recording".into(); s.source="boardDevice".into(); s.device_recording_id=Some(17);
    s.source_device_id=Some("AA:BB:CC:DD:EE:FF".into()); s.device_sha256=None; s
}
fn request(s:&CompanionV1HostSession) -> Request { Request { session_id:s.id.clone(), bookmark_id:uuid::Uuid::new_v4().to_string(),
    expected_revision:s.bookmark_revision, action:Action::AddLive, label:Some("确认预算".into()), position_ms:None } }
fn stamp(s:&CompanionV1HostSession,ms:u64) -> LiveStamp { LiveStamp { session_id:s.id.clone(), device_id:s.source_device_id.clone().unwrap(),
    recording_id:s.device_recording_id.unwrap(), position_ms:ms,recording_key:s.device_recording_key.clone() } }

#[test]
fn live_time_is_board_authored_idempotent_and_edits_preserve_original() {
    let mut s=session(); let r=request(&s); let raw=s.transcript_text.clone();
    assert!(apply(&mut s,&r,Some(&stamp(&session(),2460)),None,"now").unwrap());
    assert_eq!(s.bookmarks[0].position_ms,2460); assert_eq!(s.bookmarks[0].audio_position_ms,None);
    assert!(!apply(&mut s,&r,None,None,"later").unwrap()); // lost reply never shifts time
    let mut rename=r.clone(); rename.action=Action::Rename; rename.expected_revision=1; rename.label=Some("讨论预算".into());
    assert!(apply(&mut s,&rename,None,None,"later").unwrap());
    assert!(!apply(&mut s,&rename,None,None,"retry").unwrap());
    assert_eq!(s.bookmarks[0].position_ms,2460); assert_eq!(s.transcript_text,raw);
    let mut delete=rename; delete.action=Action::Delete; delete.expected_revision=2;
    assert!(apply(&mut s,&delete,None,None,"later").unwrap());
    assert!(!apply(&mut s,&delete,None,None,"retry").unwrap()); assert!(s.bookmarks.is_empty());
}

#[test]
fn foreign_stale_estimated_out_of_audio_and_malformed_marks_are_atomic() {
    for failure in ["foreignSession","foreignDevice","foreignRecording","foreignLogical","staleRevision","hostTime","missingStamp","zeroTime","badLabel","badId","outOfAudio","duringCapture"] {
        let mut s=session(); let mut r=request(&s); let mut time=stamp(&s,2000);
        match failure {
            "foreignSession" => time.session_id="other".into(), "foreignDevice" => time.device_id="11:22:33:44:55:66".into(),
            "foreignRecording" => time.recording_id=99, "staleRevision" => r.expected_revision=44,
            "foreignLogical" => s.device_recording_key=Some(super::super::recording_wire::SessionKey {
                device_uid:[0x35;12],format_epoch:7,session_id:23}.public_key()),
            "hostTime" => r.position_ms=Some(1234), "zeroTime" => time.position_ms=0,
            "badLabel" => r.label=Some("bad\nlabel".into()), "badId" => r.bookmark_id="bad".into(),
            "outOfAudio" => {s.status="captured".into(); r.action=Action::AddAt; r.position_ms=Some(3000);},
            "duringCapture" => {r.action=Action::AddAt; r.position_ms=Some(1000);}, _=>{}
        }
        let before=serde_json::to_value(&s).unwrap();
        assert!(apply(&mut s,&r,if failure=="missingStamp" {None} else {Some(&time)},Some(2000),"now").is_err(),"{failure}");
        assert_eq!(serde_json::to_value(s).unwrap(),before,"{failure}");
    }
}

fn captured() -> (CompanionV1HostSession,std::path::PathBuf) {
    use sha2::{Digest,Sha256};
    let root=std::env::temp_dir().join(format!("companion-bookmark-{}",uuid::Uuid::new_v4()));
    std::fs::create_dir_all(&root).unwrap(); let wav=root.join("original.wav");
    let mut raw=b"COP1\x01\x01\x14\x00".to_vec(); raw.extend_from_slice(&16000u32.to_le_bytes());
    // Structural COP1 timing test, explicitly not a microphone/ASR substitute.
    for _ in 0..101 {raw.extend_from_slice(&1u16.to_le_bytes()); raw.push(0);}
    std::fs::write(wav.with_extension("opus"),&raw).unwrap();
    let data=64000u32; let mut bytes=b"RIFF".to_vec(); bytes.extend_from_slice(&(data+36).to_le_bytes());
    bytes.extend_from_slice(b"WAVEfmt \x10\0\0\0\x01\0\x01\0"); bytes.extend_from_slice(&16000u32.to_le_bytes());
    bytes.extend_from_slice(&32000u32.to_le_bytes()); bytes.extend_from_slice(b"\x02\0\x10\0data"); bytes.extend_from_slice(&data.to_le_bytes());
    bytes.resize(44+data as usize,0); std::fs::write(&wav,bytes).unwrap();
    let mut s=session(); let r=request(&s); let time=stamp(&s,1260); apply(&mut s,&r,Some(&time),None,"now").unwrap();
    s.status="captured".into(); s.audio_stored=true; s.retention.audio_cached=true; s.audio_path=Some(wav.to_string_lossy().into());
    s.device_sha256=Some(format!("{:x}",Sha256::digest(&raw))); s.device_total_length=Some(raw.len() as u32);
    (s,root)
}

#[test]
fn sealed_cop1_maps_decoder_skip_without_shifting_capture_or_wrong_source() {
    let (mut s,root)=captured(); let original=s.bookmarks[0].position_ms;
    bind_received(&mut s); assert_eq!(s.bookmarks[0].audio_position_ms,Some(1240));
    assert_eq!(s.bookmarks[0].position_ms,original); assert_eq!(s.bookmarks[0].source_sha256,s.device_sha256);
    for failure in ["differentHash","corruptRaw","shortWav","changedDevice","pastEnd"] {
        let (mut bad,_)=captured();
        match failure {
            "differentHash" => bad.device_sha256=Some("f".repeat(64)),
            "corruptRaw" => {std::fs::write(std::path::Path::new(bad.audio_path.as_ref().unwrap()).with_extension("opus"),b"bad").unwrap();},
            "shortWav" => {std::fs::write(bad.audio_path.as_ref().unwrap(),b"bad").unwrap();},
            "changedDevice" => bad.source_device_id=Some("other".into()),
            "pastEnd" => bad.bookmarks[0].position_ms=2021, _=>{}
        }
        bind_received(&mut bad); assert_eq!(bad.bookmarks[0].audio_position_ms,None,"{failure}");
    }
    let index=root.join("index.json"); super::super::persistence::save_sessions_to(&index,&[s.clone()]).unwrap();
    let restored=super::super::persistence::load_sessions_from(&index).unwrap(); assert_eq!(restored[0].bookmarks,s.bookmarks);
    let mut r=request(&s); r.action=Action::AddAt; r.position_ms=Some(2000);
    assert!(apply(&mut s,&r,None,Some(2000),"now").unwrap()); assert_eq!(s.bookmarks[1].audio_position_ms,Some(2000));
}

#[test]
fn locked_commit_preserves_other_rows_and_rejects_stale_disk_revision() {
    let (mut s,root)=captured(); let index=root.join("index.json");
    let mut prior=s.clone(); prior.bookmarks.clear(); prior.bookmark_revision=0;
    let mut other=prior.clone(); other.id="other".into(); other.title="不能覆盖".into();
    super::super::persistence::save_sessions_to(&index,&[prior,other]).unwrap();
    commit_to(&index,&mut s,0).ok().unwrap();
    let rows=super::super::persistence::load_sessions_from(&index).unwrap();
    assert_eq!(rows[1].title,"不能覆盖"); assert_eq!(rows[0].bookmarks[0].audio_position_ms,Some(1240));
    let before=std::fs::read(&index).unwrap();
    assert!(matches!(commit_to(&index,&mut s,0),Err(CommitError::Conflict(_))));
    assert_eq!(std::fs::read(&index).unwrap(),before);
}

#[test]
fn old_index_defaults_to_empty_and_ipc_cannot_supply_native_stamp() {
    let s=session(); let mut json=serde_json::to_value(&s).unwrap();
    json.as_object_mut().unwrap().remove("bookmarkRevision"); json.as_object_mut().unwrap().remove("bookmarks");
    let old:CompanionV1HostSession=serde_json::from_value(json).unwrap(); assert_eq!(old.bookmark_revision,0); assert!(old.bookmarks.is_empty());
    let bad=serde_json::json!({"sessionId":"s","bookmarkId":uuid::Uuid::new_v4().to_string(),"expectedRevision":0,"action":"addLive","stamp":{"positionMs":123}});
    assert!(serde_json::from_value::<Request>(bad).is_err());
}

#[test]
fn exports_keep_user_marks_separate_from_asr_and_srt_does_not_fabricate_times() {
    use super::super::export::{prepare_meeting_export,MeetingExportFormat};
    let (mut s,_)=captured();s.meeting_mode="offlineStore".into();s.minutes=None;s.minutes_by_mode=Default::default();
    s.transcript_text.clear();s.utterances.clear();s.transcript_final=false;
    bind_received(&mut s);
    let data=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Json).unwrap();
    let json:serde_json::Value=serde_json::from_slice(&data.bytes).unwrap();
    assert_eq!(json["transcriptFinal"],false);assert_eq!(json["transcriptText"],"");
    assert_eq!(json["bookmarks"][0]["audioPositionMs"],1240);
    let data=prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Txt).unwrap();
    let text=String::from_utf8(data.bytes).unwrap();assert!(text.contains("尚无最终转写"));assert!(text.contains("00:01.240 确认预算"));
    assert!(prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Srt).is_err());
}
