use super::*;
use super::super::{export::{self,MeetingExportFormat as F},session_store};
fn row()->CompanionV1HostSession {
    let mut s=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap()).unwrap().host.sessions.remove(0);
    s.id="original".into();s.title="样品条件".into();s.meeting_mode="offlineStore".into();s.minutes_by_mode=Default::default();
    let m=s.minutes.as_mut().unwrap();m.markdown="## 行动项\n- [ ] 样品不要深色 (due: 2026-11-06T15:00:00+08:00前)\n- [ ] 只确定日期 (due: 2026-11-07)\n- [x] 完成 (due: 2026-11-08)".into();m.processing=None;m.source_note_context=None;m.source_review_revision=None;
    s
}
fn draft(s:&CompanionV1HostSession,format:F)->Copy {
    let prepared=export::prepare_meeting_export(s,"offlineStore",format).unwrap();
    prepare(s,"offlineStore",&prepared,std::path::Path::new("sample.ics")).unwrap().unwrap()
}
fn path()->std::path::PathBuf {
    let root=std::env::temp_dir().join(format!("companion-calendar-copy-{}",uuid::Uuid::new_v4()));std::fs::create_dir(&root).unwrap();root.join("sessions.json")
}
#[test] fn exact_file_identity_reminder_and_existing_uid_are_preserved() {
    let s=row();let prepared=export::prepare_meeting_export(&s,"offlineStore",F::CalendarReminder60).unwrap();
    let copy=prepare(&s,"offlineStore",&prepared,std::path::Path::new("sample.ics")).unwrap().unwrap();
    let ics=String::from_utf8(prepared.bytes.clone()).unwrap().replace("\r\n ","");
    assert_eq!(copy.entries.len(),2);assert_eq!(copy.entries[0].reminder_minutes,Some(60));assert_eq!(copy.entries[1].reminder_minutes,None);
    for e in &copy.entries {assert!(ics.contains(&format!("UID:{}\r\n",e.uid)));assert!(ics.contains(&format!("SUMMARY:{}\r\n",e.title)));}
    assert_eq!(copy.file_sha256,format!("{:x}",Sha256::digest(&prepared.bytes)));assert_eq!(copy.content_hash,export::content_hash(&prepared));
    assert_eq!(copy.source_markdown,s.minutes.as_ref().unwrap().markdown);assert!(copy.entries[0].deadline.ends_with('前'));
    // Preserve the original algorithm's byte identity, rather than using row position alone.
    let actions=super::super::action_export::parse_saved_actions(&copy.source_markdown);let mut h=Sha256::new();
    for part in ["calendar-deadline-event","original","offlineStore","0",&actions[0].text] {h.update(part.as_bytes());h.update([0]);}
    assert_eq!(copy.entries[0].uid,format!("{}@companion-type",&format!("{:x}",h.finalize())[..40]));
    assert!(prepare(&s,"offlineStore",&export::prepare_meeting_export(&s,"offlineStore",F::Markdown).unwrap(),std::path::Path::new("sample.md")).unwrap().is_none());
}
#[test] fn commit_reopens_exact_copy_and_preserves_concurrent_text_not_stale_window() {
    let path=path();let original=vec![row()];session_store::save(&path,&original).unwrap();let copy=draft(&original[0],F::CalendarReminder30);
    let mut current=original.clone();current[0].title="另一窗口的新标题".into();current[0].minutes.as_mut().unwrap().markdown.push_str("\n补充：先确认样品");session_store::save(&path,&current).unwrap();
    let (rev,copies,_)=commit(&path,"original",copy.clone()).unwrap();assert_eq!(rev,1);assert_eq!(copies[0].source_title,original[0].title);
    let loaded:Vec<CompanionV1HostSession>=serde_json::from_slice(&session_store::load(&path).bytes.unwrap()).unwrap();
    assert_eq!(loaded[0].title,current[0].title);assert_eq!(serde_json::to_value(&loaded[0].minutes).unwrap(),serde_json::to_value(&current[0].minutes).unwrap());assert_eq!(loaded[0].calendar_copies,copies);
    assert!(session_store::save(&path,&current).is_err());
    std::fs::write(&path,b"broken-primary").unwrap();
    let fallback:Vec<CompanionV1HostSession>=serde_json::from_slice(&session_store::load(&path).bytes.unwrap()).unwrap();assert_eq!(fallback[0].calendar_copies,copies);
    std::fs::remove_dir_all(path.parent().unwrap()).unwrap();
}
#[test] fn bounded_current_previous_per_mode_deduplicates_without_erasing_old_target() {
    let s=row();let first=draft(&s,F::Calendar);let mut rows=vec![s];apply(&mut rows,"original",first.clone()).unwrap();
    let second=draft(&rows[0],F::CalendarReminder30);apply(&mut rows,"original",second.clone()).unwrap();apply(&mut rows,"original",second.clone()).unwrap();
    assert_eq!(rows[0].calendar_copies.len(),2);assert_eq!(rows[0].calendar_copies[1].content_hash,first.content_hash);
    let mut online=second.clone();online.meeting_mode="onlineLive".into();apply(&mut rows,"original",online).unwrap();
    let mut third=second;third.content_hash="a".repeat(64);apply(&mut rows,"original",third).unwrap();
    assert_eq!(rows[0].calendar_copies.len(),3);assert_eq!(rows[0].calendar_copies.iter().filter(|c|c.meeting_mode=="offlineStore").count(),2);
}
#[test] fn privacy_clear_blocks_late_receipt_and_backup_never_resurrects_text() {
    let path=path();let mut state=crate::companion_v1::fixture_snapshot();state.host.sessions=vec![row()];state.host.selected_session_id=Some("original".into());
    let stale=draft(&state.host.sessions[0],F::Calendar);apply(&mut state.host.sessions,"original",stale.clone()).unwrap();session_store::save(&path,&state.host.sessions).unwrap();
    let cleared=crate::companion_v1::apply_fixture_control(state,serde_json::from_value(serde_json::json!({"action":"privacyEraseTranscript","sessionId":"original"})).unwrap()).unwrap();
    assert!(cleared.host.sessions[0].calendar_copies.is_empty());assert_eq!(cleared.host.sessions[0].calendar_copy_epoch,1);session_store::save(&path,&cleared.host.sessions).unwrap();
    let before=std::fs::read(&path).unwrap();assert!(commit(&path,"original",stale).is_err());assert_eq!(std::fs::read(&path).unwrap(),before);
    std::fs::write(&path,b"broken").unwrap();let loaded:Vec<CompanionV1HostSession>=serde_json::from_slice(&session_store::load(&path).bytes.unwrap()).unwrap();assert!(loaded[0].calendar_copies.is_empty());assert!(loaded[0].minutes.is_none());
    std::fs::remove_dir_all(path.parent().unwrap()).unwrap();
}
#[test] fn legacy_missing_trashed_locked_and_malformed_inputs_do_not_invent_saved_history() {
    let original=row();let copy=draft(&original,F::Calendar);let mut old=serde_json::to_value(&original).unwrap();old.as_object_mut().unwrap().remove("calendarCopyRevision");old.as_object_mut().unwrap().remove("calendarCopyEpoch");old.as_object_mut().unwrap().remove("calendarCopies");
    let legacy:CompanionV1HostSession=serde_json::from_value(old).unwrap();assert!(legacy.calendar_copies.is_empty());assert_eq!(legacy.calendar_copy_revision,0);
    for kind in ["missing","trash","malformed"] {let mut rows=vec![original.clone()];let mut c=copy.clone();if kind=="missing"{rows.clear();}else if kind=="trash"{rows[0].organization.trashed_at=Some("now".into());}else{c.file_sha256="fake".into();}
        let before=serde_json::to_vec(&rows).unwrap();assert!(apply(&mut rows,"original",c).is_err());assert_eq!(serde_json::to_vec(&rows).unwrap(),before);}
    let path=path();session_store::save(&path,&[original]).unwrap();let before=std::fs::read(&path).unwrap();
    let file=std::fs::OpenOptions::new().read(true).write(true).open(path.with_file_name("sessions.json.lock")).unwrap();file.try_lock().unwrap();assert!(commit(&path,"original",copy).is_err());assert_eq!(std::fs::read(&path).unwrap(),before);drop(file);
    std::fs::remove_dir_all(path.parent().unwrap()).unwrap();
}
