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
#[test] fn calendar_independent_reminders_keep_date_only_deadline_and_bind_source_and_copy() {
    use super::super::action_export::{CalendarAlarm as A,CalendarReminderSelection as S};
    let s=row();let original=serde_json::to_vec(&s).unwrap();
    let base=export::prepare_meeting_export(&s,"offlineStore",F::CalendarReminder60).unwrap();
    let items=base.calendar_items.as_ref().unwrap();
    let choices=vec![S{uid:items[0].uid.clone(),reminder:A::None},S{uid:items[1].uid.clone(),reminder:A::At{at:"2026-11-06T18:00:00+08:00".into()}}];
    let selected=export::prepare_meeting_export_with_reminders(&s,"offlineStore",F::CalendarReminder60,Some(&choices)).unwrap();
    let file=String::from_utf8_lossy(&selected.bytes);
    assert!(file.contains("DTSTART;VALUE=DATE:20261107\r\n"));
    assert!(file.contains("DTSTART:20261106T070000Z\r\n"));
    assert!(file.contains("TRIGGER;VALUE=DATE-TIME:20261106T100000Z\r\n"));
    assert_eq!(file.matches("BEGIN:VALARM").count(),1);
    assert!(!file.contains("TRIGGER;RELATED"));
    assert!(export::require_unchanged(&selected,Some(&export::content_hash(&base))).is_err());
    let copy=prepare(&s,"offlineStore",&selected,std::path::Path::new("independent.ics")).unwrap().unwrap();
    assert_eq!(copy.schema,2);assert_eq!(copy.entries[1].deadline,"2026-11-07");
    assert_eq!(copy.entries[1].reminder_at.as_deref(),Some("2026-11-06T18:00:00+08:00"));
    assert!(copy.entries.iter().all(|e|e.reminder_minutes.is_none()));
    let path=path();session_store::save(&path,&[s.clone()]).unwrap();
    let (_,copies,_,_)=commit(&path,"original",copy.clone()).unwrap();assert_eq!(copies[0].entries,copy.entries);
    let loaded:Vec<CompanionV1HostSession>=serde_json::from_slice(&session_store::load(&path).bytes.unwrap()).unwrap();
    assert_eq!(loaded[0].calendar_copies[0].entries,copy.entries);
    let mut changed=s.clone();changed.minutes.as_mut().unwrap().markdown=changed.minutes.as_ref().unwrap().markdown.replace("2026-11-07","2026-11-09");
    assert!(export::prepare_meeting_export_with_reminders(&changed,"offlineStore",F::Calendar,Some(&choices)).is_err());
    assert_eq!(serde_json::to_vec(&s).unwrap(),original);
    // Legacy snapshots remain schema 1 and omit the new field.
    let legacy=draft(&s,F::CalendarReminder30);assert_eq!(legacy.schema,1);
    let bytes=serde_json::to_vec(&legacy).unwrap();assert!(!String::from_utf8_lossy(&bytes).contains("reminderAt"));
    assert_eq!(serde_json::from_slice::<Copy>(&bytes).unwrap(),legacy);
    std::fs::remove_dir_all(path.parent().unwrap()).unwrap();
}
#[test] fn calendar_reminders_reject_ambiguous_instants_duplicate_and_excluded_targets() {
    use super::super::action_export::{CalendarAlarm as A,CalendarReminderSelection as S};
    let s=row();let base=export::prepare_meeting_export(&s,"offlineStore",F::Calendar).unwrap();let items=base.calendar_items.unwrap();
    for at in ["2026-11-06","2026-11-06T18:00:00-00:00","2026-11-06T18:00:00.001Z","2026-11-06T18:00:00Z前","2026-11-06T18:00:60Z","0000-01-01T18:00:00Z"] {
        let choices=[S{uid:items[1].uid.clone(),reminder:A::At{at:at.into()}}];
        assert!(export::prepare_meeting_export_with_reminders(&s,"offlineStore",F::Calendar,Some(&choices)).is_err(),"{at}");
    }
    for (uid,reminder) in [(items[1].uid.clone(),A::Before{minutes:60}),(items[0].uid.clone(),A::Before{minutes:29}),(items[2].uid.clone(),A::None),("wrong-source".into(),A::None)] {
        assert!(export::prepare_meeting_export_with_reminders(&s,"offlineStore",F::Calendar,Some(&[S{uid,reminder}])).is_err());
    }
    let duplicate=[S{uid:items[0].uid.clone(),reminder:A::None},S{uid:items[0].uid.clone(),reminder:A::Before{minutes:60}}];
    assert!(export::prepare_meeting_export_with_reminders(&s,"offlineStore",F::Calendar,Some(&duplicate)).is_err());
    let choices=[S{uid:items[0].uid.clone(),reminder:A::Before{minutes:1440}}];
    let selected=export::prepare_meeting_export_with_reminders(&s,"offlineStore",F::Calendar,Some(&choices)).unwrap();
    assert!(String::from_utf8_lossy(&selected.bytes).contains("TRIGGER;RELATED=START:-PT1440M"));
    assert!(export::prepare_meeting_export_with_reminders(&s,"offlineStore",F::Markdown,Some(&choices)).is_err());
    let choices=[S{uid:items[0].uid.clone(),reminder:A::None}];
    let selected=export::prepare_meeting_export_with_reminders(&s,"offlineStore",F::CalendarReminder60,Some(&choices)).unwrap();
    assert!(!String::from_utf8_lossy(&selected.bytes).contains("VALARM"));
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
#[test] fn calendar_saved_summary_uses_the_same_deduplicated_actions_as_the_file() {
    let mut s=row();let m=s.minutes.as_mut().unwrap();
    m.markdown="## 行动项\n- [ ] 核对样品 (due: 2026-11-08T15:00:00+08:00)\n- [ ] 核对样品 (due: 2026-11-08T15:00:00+08:00)\n- [ ] 核对包装 (due: 2026-11-07)".into();
    m.processing=Some(crate::companion_v1::CompanionV1MinutesProcessing{strategy:"chunkedSourceBacked".into(),source_bytes:1,processed_source_bytes:1,total_chunks:1,completed_chunks:1,resumed_chunks:0,complete:true});
    let prepared=export::prepare_meeting_export(&s,"offlineStore",F::CalendarReminder30).unwrap();
    let file=String::from_utf8(prepared.bytes.clone()).unwrap().replace("\r\n ","");
    let copy=prepare(&s,"offlineStore",&prepared,std::path::Path::new("sample.ics")).unwrap().unwrap();
    assert_eq!(file.matches("BEGIN:VEVENT").count(),2);
    assert_eq!(copy.entries.len(),2,"saved summary must not report a removed duplicate");
    for entry in copy.entries {assert!(file.contains(&format!("UID:{}\r\n",entry.uid)));}
}
#[test] fn commit_reopens_exact_copy_and_preserves_concurrent_text_not_stale_window() {
    let path=path();let original=vec![row()];session_store::save(&path,&original).unwrap();let copy=draft(&original[0],F::CalendarReminder30);
    let mut current=original.clone();current[0].title="另一窗口的新标题".into();current[0].minutes.as_mut().unwrap().markdown.push_str("\n补充：先确认样品");session_store::save(&path,&current).unwrap();
    let (rev,copies,_,_)=commit(&path,"original",copy.clone()).unwrap();assert_eq!(rev,1);assert_eq!(copies[0].source_title,original[0].title);
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

#[test] fn execution_slots_commit_reopen_and_privacy_clear_refuses_stale_receipt() {
    use super::super::action_export::{CalendarExecutionSlot,CalendarSlotSelection};
    let path=path();let row=row();let rows=vec![row.clone()];session_store::save(&path,&rows).unwrap();
    let base=export::prepare_meeting_export(&row,"offlineStore",F::CalendarReminder60).unwrap();
    let uid=base.calendar_items.as_ref().unwrap()[0].uid.clone();
    let selection=CalendarSlotSelection{uid,slot:CalendarExecutionSlot{start:"2026-11-06T09:00:00+08:00".into(),end:"2026-11-06T10:00:00+08:00".into()}};
    let selected=export::prepare_meeting_export_with_calendar_choices(&row,"offlineStore",F::CalendarReminder60,None,Some(&[selection.clone()])).unwrap();
    assert!(export::require_unchanged(&selected,Some(&export::content_hash(&base))).is_err());
    let copy=prepare(&row,"offlineStore",&selected,std::path::Path::new("样品.ics")).unwrap().unwrap();
    let serialized=serde_json::to_value(&copy).unwrap();assert!(serialized.get("transientSlots").is_none());
    let (revision,copies,slots,_)=commit(&path,"original",copy.clone()).unwrap();assert_eq!(revision,1);assert_eq!(copies.len(),1);assert_eq!(slots.len(),1);assert_eq!(slots[0].content_hash,copies[0].content_hash);assert_eq!(slots[0].selections,vec![selection]);
    let reloaded:Vec<CompanionV1HostSession>=serde_json::from_slice(&session_store::load(&path).bytes.unwrap()).unwrap();
    assert_eq!(reloaded[0].calendar_slot_copies,slots);
    assert_eq!(latest_saved_slots(&reloaded[0],"offlineStore").unwrap().unwrap(),slots[0].selections.as_slice());
    assert!(latest_saved_slots(&reloaded[0],"onlineLive").unwrap().is_none());
    let mut duplicate=reloaded[0].clone();duplicate.calendar_slot_copies.push(duplicate.calendar_slot_copies[0].clone());assert!(latest_saved_slots(&duplicate,"offlineStore").is_err());
    let mut orphan=reloaded[0].clone();orphan.calendar_copies.clear();assert!(latest_saved_slots(&orphan,"offlineStore").is_err());
    let again=export::prepare_meeting_export_with_calendar_choices(&reloaded[0],"offlineStore",F::CalendarReminder60,None,Some(&slots[0].selections)).unwrap();
    assert_eq!(export::content_hash(&selected),export::content_hash(&again));
    let mut cleared=crate::companion_v1::fixture_snapshot();cleared.host.sessions=reloaded;cleared.host.selected_session_id=Some("original".into());
    let cleared=crate::companion_v1::apply_fixture_control(cleared,serde_json::from_value(serde_json::json!({"action":"privacyEraseTranscript","sessionId":"original"})).unwrap()).unwrap();
    assert!(cleared.host.sessions[0].calendar_slot_copies.is_empty());assert!(cleared.host.sessions[0].calendar_copies.is_empty());
    session_store::save(&path,&cleared.host.sessions).unwrap();let before=std::fs::read(&path).unwrap();assert!(commit(&path,"original",copy).is_err());assert_eq!(std::fs::read(&path).unwrap(),before);
    std::fs::remove_dir_all(path.parent().unwrap()).unwrap();
}

#[test] fn cli_preserves_matching_saved_slot_and_never_overwrites_when_source_changed() {
    use super::super::action_export::{CalendarExecutionSlot,CalendarSlotSelection};
    let path=path();let input=path.with_file_name("input.json");let output=path.with_file_name("output.ics");
    let mut session=row();let base=export::prepare_meeting_export(&session,"offlineStore",F::Calendar).unwrap();
    let selection=CalendarSlotSelection{uid:base.calendar_items.as_ref().unwrap()[0].uid.clone(),slot:CalendarExecutionSlot{start:"2026-11-06T09:00:00+08:00".into(),end:"2026-11-06T10:00:00+08:00".into()}};
    let prepared=export::prepare_meeting_export_with_calendar_choices(&session,"offlineStore",F::Calendar,None,Some(&[selection])).unwrap();
    let copy=prepare(&session,"offlineStore",&prepared,std::path::Path::new("样品.ics")).unwrap().unwrap();apply(std::slice::from_mut(&mut session),"original",copy).unwrap();
    std::fs::write(&input,serde_json::to_vec(&session).unwrap()).unwrap();
    let args=vec!["companion-type".into(),"--export-meeting-json".into(),input.to_string_lossy().into_owned(),"offlineStore".into(),"calendar".into(),output.to_string_lossy().into_owned()];
    crate::run_diagnostics_cli(&args).unwrap().unwrap();let generated=std::fs::read_to_string(&output).unwrap();
    assert!(generated.contains("DTSTART:20261106T010000Z\r\nDTEND:20261106T020000Z\r\n"));
    let updated=session.minutes.as_ref().unwrap().markdown.replace("2026-11-06T15:00:00+08:00前","2026-11-06T16:00:00+08:00前");session.minutes.as_mut().unwrap().markdown=updated;
    std::fs::write(&input,serde_json::to_vec(&session).unwrap()).unwrap();std::fs::write(&output,b"original target").unwrap();
    assert!(crate::run_diagnostics_cli(&args).unwrap().is_err());assert_eq!(std::fs::read(&output).unwrap(),b"original target");
    std::fs::remove_file(input).unwrap();std::fs::remove_file(output).unwrap();std::fs::remove_dir(path.parent().unwrap()).unwrap();
}
