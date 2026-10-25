use super::*;
use sha2::Digest;
use std::panic::{catch_unwind,AssertUnwindSafe};
fn temp()->PathBuf{let p=std::env::temp_dir().join(format!("companion-trace-{}",uuid::Uuid::new_v4()));fs::create_dir(&p).unwrap();p}

#[test]
fn seed_is_persistent_bounded_and_never_overwrites_corruption(){
    let root=temp();let path=root.join("link.key");let first=identity::seed_at(&path).unwrap();
    assert_eq!(first,identity::seed_at(&path).unwrap());assert_eq!(fs::metadata(&path).unwrap().len(),32);
    assert_eq!(identity::derive(&first,"private-recording"),identity::derive(&identity::seed_at(&path).unwrap(),"private-recording"));
    let bad=vec![7;33];fs::write(&path,&bad).unwrap();assert!(identity::seed_at(&path).is_err());assert_eq!(fs::read(&path).unwrap(),bad);
    fs::write(&path,[0;32]).unwrap();assert!(identity::seed_at(&path).is_err());
    fs::remove_dir_all(root).unwrap();
}
#[test]
fn trace_is_stable_local_and_scope_restores_even_after_failure(){
    identity::with_test_seed([21;32],||{
        assert_eq!(identity::current_trace().recording,None);
        let first=identity::derive(&[21;32],"SESSION_PRIVATE_MARKER").unwrap();
        assert_ne!(Some(first),identity::derive(&[22;32],"SESSION_PRIVATE_MARKER"));
        assert_ne!(Some(first),identity::derive(&[21;32],"other"));
        assert!(identity::derive(&[21;32],"").is_none());assert!(identity::derive(&[21;32],&"x".repeat(513)).is_none());
        {let _scope=RecordingScope::enter("SESSION_PRIVATE_MARKER");assert_eq!(identity::current_trace().recording,Some(first));
            {let _inner=RecordingScope::enter("other");assert_ne!(identity::current_trace().recording,Some(first));}
            assert_eq!(identity::current_trace().recording,Some(first));
            let _=catch_unwind(AssertUnwindSafe(||{let _inner=RecordingScope::enter("panic");panic!("isolated scope check")}));
            assert_eq!(identity::current_trace().recording,Some(first));}
        assert_eq!(identity::current_trace().recording,None);
    });
}
#[test]
fn recording_linkage_does_not_replace_operation_ids_or_leak_input(){
    let (_,events)=capture_with_test_trace(||{
        let _scope=RecordingScope::enter("SESSION_PRIVATE_MARKER");
        Span::start(Operation::Transcription).finish(Some("provider secret=PRIVATE_TOKEN"));
        Span::start(Operation::Minutes).finish(None);
    });
    assert_eq!(events.len(),4);let trace=events[0].recording_trace.unwrap();
    assert!(events.iter().all(|e|e.recording_trace==Some(trace)&&!e.trace_unavailable&&e.process_instance!=0));
    assert_eq!(events[0].event.correlation_id,events[1].event.correlation_id);
    assert_ne!(events[0].event.correlation_id,events[2].event.correlation_id);
    let text=serde_json::to_string(&events).unwrap();assert!(!text.contains("SESSION_PRIVATE_MARKER")&&!text.contains("PRIVATE_TOKEN"));
    let (_,outside)=capture_test_events(||Span::start(Operation::DeviceControl).finish(None));assert!(outside.iter().all(|e|e.recording_trace.is_none()&&!e.trace_unavailable));
}
#[test]
fn unavailable_key_is_visible_and_never_blocks_or_fabricates_link(){
    let(value,events)=capture_test_events(||{let _scope=RecordingScope::enter("key-unavailable-in-this-test");Span::start(Operation::Transcription).result(Ok::<_,String>(7))});
    assert_eq!(value.unwrap(),7);assert_eq!(events.len(),2);assert!(events.iter().all(|e|e.recording_trace.is_none()&&e.trace_unavailable));
}
#[test]
fn image_identity_observes_actual_bounded_bytes_and_handles_missing(){
    let root=temp();let path=root.join("own-image.bin");assert_eq!(identity::image_at(&path).status,identity::ImageStatus::Missing);
    fs::write(&path,b"first own test image").unwrap();let first=identity::image_at(&path);assert_eq!(first.status,identity::ImageStatus::Observed);
    assert_eq!(first.sha256.unwrap(),sha2::Sha256::digest(b"first own test image").as_slice());
    fs::write(&path,b"second own test image").unwrap();assert_ne!(first,identity::image_at(&path));
    fs::write(&path,[]).unwrap();assert!(identity::image_at(&path).sha256.is_none());assert_eq!(identity::image_at(&root).status,identity::ImageStatus::Unreadable);
    fs::remove_dir_all(root).unwrap();
}
fn image(process:u64)->BuildIdentity{BuildIdentity{kind:identity::BuildKind::ProcessImage,process_instance:process,observed_at_unix_ms:1,
    executable:identity::Image{sha256:Some([7;32]),status:identity::ImageStatus::Observed},companion_library:identity::Image{sha256:None,status:identity::ImageStatus::Missing}}}
#[test]
fn historical_lines_remain_unlinked_and_conflicting_or_unsafe_images_are_not_inferred(){
    let root=temp();let path=root.join("log.jsonl");
    let record=Record{operation:Operation::Transcription,unix_ms:1,event:EventEnvelope::new(11,1,2,EventSource::Type,Capability::Audio),process_instance:0,recording_trace:None,trace_unavailable:false};
    let mut legacy=serde_json::to_value(&record).unwrap();legacy.as_object_mut().unwrap().insert("secret".into(),serde_json::json!("PRIVATE_LEGACY_TOKEN"));
    let good=image(23);let mut conflict=good.clone();conflict.executable.sha256=Some([8;32]);
    let mut invalid=good.clone();invalid.process_instance=24;invalid.executable.status=identity::ImageStatus::Missing;
    let mut log=vec![legacy,serde_json::to_value(&good).unwrap(),serde_json::to_value(&good).unwrap(),serde_json::to_value(&conflict).unwrap(),serde_json::to_value(&invalid).unwrap()];
    let mut raw=serde_json::to_value(image(25)).unwrap();raw.as_object_mut().unwrap().insert("path".into(),serde_json::json!("PRIVATE_PATH"));log.push(raw);
    fs::write(&path,log.iter().map(|v|v.to_string()+"\n").collect::<String>()).unwrap();let journal=read_journal(&path);
    assert_eq!(journal.events.len(),1);assert_eq!(journal.build_conflicts,1);assert!(journal.build_identities.is_empty());assert_eq!(journal.unreadable_lines,2);
    let exported=serde_json::to_string(&journal).unwrap();assert!(!exported.contains("PRIVATE_")&&!exported.contains("recordingTrace"));
    fs::remove_dir_all(root).unwrap();
}
#[test]
fn preview_uses_lossless_hex_ids_and_no_raw_session_or_path(){
    let (_,events)=capture_with_test_trace(||{let _scope=RecordingScope::enter("OWNER_PRIVATE_SESSION");Span::start(Operation::Minutes).finish(None);});
    let journal=HostJournal{events,unreadable_lines:0,write_failed:false,build_identities:vec![],build_conflicts:0};
    let preview=preview_value(&crate::companion_v1::fixture_snapshot(),&journal,Some(&image(identity::process_instance())));
    for row in preview["recentEvents"].as_array().unwrap(){assert_eq!(row["operationId"].as_str().unwrap().len(),16);assert_eq!(row["recordingTrace"].as_str().unwrap().len(),16);}
    assert_eq!(preview["executableSha256"].as_str().unwrap().len(),64);let text=preview.to_string();assert!(!text.contains("OWNER_PRIVATE_SESSION")&&!text.contains("audioPath"));
}
