use super::*;
use crate::companion_v1::{apply_fixture_control, fixture_snapshot};

fn session() -> CompanionV1HostSession {
    apply_fixture_control(fixture_snapshot(), serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap())
        .unwrap().host.sessions.remove(0)
}
fn add(session:&CompanionV1HostSession,text:&str)->Request {
    Request { session_id:session.id.clone(), note_id:uuid::Uuid::new_v4().to_string(), expected_revision:session.note_revision,
        action:Action::Add, text:Some(text.into()), bookmark_id:None }
}
fn source(session:&CompanionV1HostSession)->serde_json::Value {
    serde_json::json!([session.audio_path,session.audio_bytes,session.device_sha256,session.transcript_text,
        session.utterances,session.transcript_review,session.minutes,session.minutes_by_mode])
}

#[test]
fn notes_are_user_context_with_exact_retries_and_conflict_protection() {
    let mut session=session();let original=source(&session);
    let first=add(&session,"  议程：核对材料\r\n下次补充方案。  ");
    assert!(apply(&mut session,&first,"one").unwrap());
    assert_eq!(session.meeting_notes[0].text,"议程：核对材料\n下次补充方案。");
    let after=serde_json::to_value(&session).unwrap();
    assert!(!apply(&mut session,&first,"two").unwrap());
    assert_eq!(serde_json::to_value(&session).unwrap(),after);
    let mut stale=first.clone();stale.action=Action::Edit;stale.text=Some("旧窗口的内容".into());
    assert!(apply(&mut session,&stale,"two").is_err());
    assert_eq!(serde_json::to_value(&session).unwrap(),after);
    stale.expected_revision=session.note_revision;apply(&mut session,&stale,"three").unwrap();
    assert_eq!(session.meeting_notes[0].created_at,"one");
    assert_eq!(session.meeting_notes[0].updated_at,"three");
    assert_eq!(source(&session),original);
    assert!(super::super::transcript_review::minutes_input(&session).meeting_notes.is_empty());
    assert_eq!(session.meeting_notes.len(),1,"provider copy does not erase local context");
}

#[test]
fn invalid_notes_and_foreign_anchors_never_partially_write() {
    let mut session=session();
    for failure in ["otherSession","invalidId","blank","oversize","control","missingAnchor"] {
        let mut request=add(&session,"有效备注");
        match failure {
            "otherSession"=>request.session_id="elsewhere".into(),
            "invalidId"=>request.note_id="not-a-request-id".into(),
            "blank"=>request.text=Some(" \n ".into()),
            "oversize"=>request.text=Some("字".repeat(4001)),
            "control"=>request.text=Some("bad\0text".into()),
            "missingAnchor"=>request.bookmark_id=Some(uuid::Uuid::new_v4().to_string()),
            _=>unreachable!(),
        }
        let before=serde_json::to_value(&session).unwrap();
        assert!(apply(&mut session,&request,"now").is_err(),"{failure}");
        assert_eq!(serde_json::to_value(&session).unwrap(),before,"{failure}");
    }
    session.note_revision=u64::MAX;
    let request=add(&session,"cannot wrap");
    assert!(apply(&mut session,&request,"now").is_err());
}

#[test]
fn durable_notes_keep_newer_asr_and_deletion_sanitizes_both_index_copies() {
    let dir=std::env::temp_dir().join(format!("companion-user-notes-{}",uuid::Uuid::new_v4()));
    let path=dir.join("sessions.json");
    let mut current=session();let mut disk=current.clone();
    disk.transcript_text="较新的真实转写仍保留".into();
    super::super::persistence::save_sessions_to(&path,&[disk.clone()]).unwrap();
    let request=add(&current,"用户临时写的背景");
    commit_to(&path,&mut current,&request,"one").unwrap();
    let mut loaded=super::super::persistence::load_sessions_from(&path).unwrap().remove(0);
    assert_eq!(loaded.transcript_text,disk.transcript_text);
    assert_eq!(loaded.meeting_notes,current.meeting_notes);
    commit_to(&path,&mut current,&request,"two").unwrap();
    assert_eq!(current.note_revision,1,"restart/lost-reply retry does not add a duplicate");
    let original=std::fs::read(&path).unwrap();
    assert!(super::super::persistence::save_sessions_to(&path,&[session()]).is_err(),"stale whole-session save cannot discard notes");
    assert_eq!(std::fs::read(&path).unwrap(),original);
    let delete=Request { action:Action::Delete,text:None,bookmark_id:None,expected_revision:loaded.note_revision,..request };
    commit_to(&path,&mut loaded,&delete,"three").unwrap();
    commit_to(&path,&mut loaded,&delete,"four").unwrap();
    for file in [&path,&path.with_extension("json.bak")] {
        let bytes=std::fs::read_to_string(file).unwrap();
        assert!(!bytes.contains("用户临时写的背景"));
        assert!(bytes.contains(&disk.transcript_text));
    }
    std::fs::remove_dir_all(dir).unwrap();
}

#[test]
fn notes_export_without_asr_and_privacy_clear_removes_context() {
    let mut session=session();session.transcript_text.clear();session.transcript_final=false;session.utterances.clear();
    session.minutes=None;session.minutes_by_mode=Default::default();
    let request=add(&session,"背景备注\n## Action Items\n- [ ] 不是音频事实");
    apply(&mut session,&request,"now").unwrap();
    let original=source(&session);
    let export=super::super::export::prepare_meeting_export(&session,&session.meeting_mode,super::super::export::MeetingExportFormat::Json).unwrap();
    let value:serde_json::Value=serde_json::from_slice(&export.bytes).unwrap();
    assert!(value["originalTranscriptText"].as_str().unwrap().is_empty());
    assert_eq!(value["userNotes"][0]["text"],session.meeting_notes[0].text);
    let txt=super::super::export::render_txt(&session);
    assert!(txt.contains("用户补充"));assert!(txt.contains("> ## Action Items"));
    assert!(super::super::action_export::parse_saved_actions(&render(&session)).is_empty());
    assert_eq!(source(&session),original);
    let mut snapshot=fixture_snapshot();snapshot.host.selected_session_id=Some(session.id.clone());snapshot.host.sessions=vec![session];
    let id=snapshot.host.sessions[0].id.clone();
    let erased=apply_fixture_control(snapshot,serde_json::from_value(serde_json::json!({"action":"privacyEraseTranscript","sessionId":id})).unwrap()).unwrap();
    assert!(erased.host.sessions[0].meeting_notes.is_empty());assert_eq!(erased.host.sessions[0].note_revision,2);
}
