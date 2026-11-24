//! State concurrency only; no cloud, BLE, host capture or physical qualification.
use super::*;
use std::sync::mpsc;
use std::time::Duration;

fn request(action:CompanionV1ControlAction,id:&str)->CompanionV1ControlRequest {
    CompanionV1ControlRequest { minutes_template: None, recording_source: None,action,session_id:Some(id.into()),context_note_revision: None, ble_name:None,
        prompt_id:None,title:None,transcript_text:None,meeting_mode:None,
        audio_path:None,audio_bytes:None,device_id:None,duration_ms:None}
}
fn backend()->Arc<FixtureCompanionBackend> {
    let backend=Arc::new(FixtureCompanionBackend::new());
    let mut state=fixture_snapshot();
    let mut source=request(CompanionV1ControlAction::DeviceSyncRecordings,"old");
    source.audio_path=Some("unit-only-original.wav".into());source.audio_bytes=Some(1000);
    let mut session=crate::companion_v1::synced_device_session(&state,&source,"test");
    session.recovery.intent="processMeeting".into();session.recovery.stage="transcribing".into();
    session.recovery.retry_stage="transcription".into();session.recovery.attempt_count=1;
    state.host.sessions=vec![session];state.host.selected_session_id=Some("old".into());
    state.host.active_session_id=None;state.meeting.active=false;state.device.recording=false;
    *backend.snapshot.lock().unwrap()=state;
    backend
}
fn worker(backend:Arc<FixtureCompanionBackend>)->(mpsc::Receiver<()>,mpsc::Sender<()>,std::thread::JoinHandle<Result<(),String>>) {
    let (entered,ready)=mpsc::channel();let (release,wait)=mpsc::channel();
    let job=std::thread::spawn(move|| {
        let mut request=request(CompanionV1ControlAction::MeetingTranscribeAudio,"old");
        let guard=backend.snapshot.lock().unwrap();
        let (mut guard,())=backend.run_meeting_work(guard,&request,|| {
            entered.send(()).unwrap();wait.recv().unwrap();
        })?;
        request.transcript_text=Some("late service result".into());
        let next=apply_control_at(guard.clone(),request,"after-external-work")?;
        *guard=merge_meeting_work(&guard,next,Some("old"));
        Ok(())
    });
    (ready,release,job)
}

#[test]
fn recovery_external_work_allows_snapshot_and_preserves_a_new_recording() {
    let backend=backend();let (ready,release,job)=worker(backend.clone());ready.recv().unwrap();
    let (done,result)=mpsc::channel();let reader=backend.clone();
    let view=std::thread::spawn(move|| {
        let snapshot=reader.snapshot().unwrap();
        let mut start=request(CompanionV1ControlAction::MeetingStart,"new");
        start.audio_path=Some("unit-only-supplied.wav".into());start.meeting_mode=Some("offlineStore".into());
        let started=apply_control_at(snapshot,start,"while-old-work-blocked").unwrap();
        *reader.snapshot.lock().unwrap()=started;
        done.send(()).unwrap();
    });
    let responsive=result.recv_timeout(Duration::from_secs(2));
    release.send(()).unwrap();job.join().unwrap().unwrap();view.join().unwrap();
    assert!(responsive.is_ok(),"snapshot waited behind external processing");
    let state=backend.snapshot().unwrap();assert!(state.meeting.active);
    assert_eq!(state.host.active_session_id.as_deref(),Some("new"));
    assert_eq!(state.host.selected_session_id.as_deref(),Some("new"));
    assert_eq!(state.host.sessions.iter().find(|s|s.id=="new").unwrap().status,"recording");
    assert_eq!(state.host.sessions.iter().find(|s|s.id=="old").unwrap().transcript_text,"late service result");
}

#[test]
fn recovery_external_late_result_does_not_overwrite_imported_transcript() {
    let backend=backend();let (ready,release,job)=worker(backend.clone());ready.recv().unwrap();
    let (done,result)=mpsc::channel();let editor=backend.clone();
    let edit=std::thread::spawn(move|| {
        let mut import=request(CompanionV1ControlAction::MeetingImportTranscript,"old");
        import.transcript_text=Some("new user transcript".into());
        editor.apply_control(import).unwrap();done.send(()).unwrap();
    });
    let responsive=result.recv_timeout(Duration::from_secs(2));release.send(()).unwrap();
    let outcome=job.join().unwrap();edit.join().unwrap();
    assert!(responsive.is_ok(),"import waited behind external processing");
    assert_eq!(outcome.unwrap_err(),MEETING_WORK_SUPERSEDED);
    backend.record_meeting_recovery_failure("old","transcription",MEETING_WORK_SUPERSEDED).unwrap();
    let state=backend.snapshot().unwrap();assert_eq!(state.host.sessions[0].transcript_text,"new user transcript");
    assert_eq!(state.host.sessions[0].recovery.stage,"pendingMinutes");
}

#[test]
fn recovery_external_late_result_never_recreates_deleted_session() {
    let backend=backend();let (ready,release,job)=worker(backend.clone());ready.recv().unwrap();
    let (done,result)=mpsc::channel();let editor=backend.clone();
    let edit=std::thread::spawn(move|| {
        let mut guard=editor.snapshot.lock().unwrap();
        *guard=apply_control_at(guard.clone(),request(CompanionV1ControlAction::PrivacyDeleteSession,"old"),"deleted").unwrap();
        done.send(()).unwrap();
    });
    let responsive=result.recv_timeout(Duration::from_secs(2));release.send(()).unwrap();
    let outcome=job.join().unwrap();edit.join().unwrap();
    assert!(responsive.is_ok(),"delete waited behind external processing");
    assert_eq!(outcome.unwrap_err(),MEETING_WORK_SUPERSEDED);
    backend.record_meeting_recovery_failure("old","transcription",MEETING_WORK_SUPERSEDED).unwrap();
    assert!(backend.snapshot().unwrap().host.sessions.is_empty());
}

#[test]
fn original_only_minutes_accepts_an_independently_saved_note() {
    for include_notes in [false, true] {
        let backend = backend();
        let mut request = request(CompanionV1ControlAction::MeetingGenerateMinutes, "old");
        request.context_note_revision = include_notes.then_some(0);
        let save = meeting_notes::Request {
            session_id: "old".into(),
            note_id: uuid::Uuid::new_v4().to_string(),
            expected_revision: 0,
            action: meeting_notes::Action::Add,
            text: Some("Ask the group about the next review date.".into()),
            bookmark_id: None,
            kind: None,
            references: None,
        };
        let before = backend.snapshot.lock().unwrap();
        let outcome = backend.run_meeting_work(before, &request, || backend.save_meeting_note(save).unwrap());
        if include_notes {
            assert!(matches!(outcome, Err(ref error) if error == MEETING_WORK_SUPERSEDED));
            assert_eq!(backend.snapshot().unwrap().host.sessions[0].note_revision, 1);
        } else {
            let (current, receipt) = outcome.unwrap();
            assert_eq!(current.host.sessions[0].note_revision, 1);
            assert_eq!(current.host.sessions[0].meeting_notes, receipt.host.sessions[0].meeting_notes);
        }
    }
}
