use super::*;

fn root() -> PathBuf {
    std::env::temp_dir().join(format!("companion-minutes-chapters-{}", uuid::Uuid::new_v4()))
}
fn cleanup(root: PathBuf) {
    let resolved = root.canonicalize().unwrap();
    assert_eq!(resolved.parent().unwrap(), std::env::temp_dir().canonicalize().unwrap());
    assert!(resolved.file_name().unwrap().to_string_lossy().starts_with("companion-minutes-chapters-"));
    fs::remove_dir_all(resolved).unwrap();
}
fn session(text: &str) -> CompanionV1HostSession {
    let request = serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap();
    let mut s = crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(), request).unwrap().host.sessions[0].clone();
    s.id = "chapter-session".into(); s.title = "Long minutes test".into();
    s.transcript_text = text.into(); s.transcript_review = None;
    s.transcript_final = true; s.meeting_mode = "offlineStore".into();
    s.utterances.clear(); s.minutes = None; s.minutes_by_mode = Default::default(); s
}
fn response(part: &CompanionV1HostSession) -> (CompanionV1MeetingMinutes, Vec<Evidence>) {
    let quote = if part.transcript_text.contains("最后结论：保留原音并等待实板验收") {
        "最后结论：保留原音并等待实板验收".into()
    } else {
        part.transcript_text.lines().find(|l| !l.trim().is_empty()).unwrap().trim().chars().take(120).collect::<String>()
    };
    let mut m = super::super::rules_l0_minutes(part, "controlled-fixture");
    m.source = "llm_deepseek".into(); m.quality = "final".into();
    m.summary = vec![quote.clone()]; m.decisions.clear(); m.action_items.clear();
    m.questions.clear(); m.keywords = vec!["fixture".into()]; m.markdown = "# Fixture".into();
    (m, vec![Evidence { field: "summary".into(), index: 0, quote }])
}

#[test]
fn source_partition_is_lossless_for_unicode_crlf_whitespace_and_long_lines() {
    for text in ["说话人2: 讨论👋、保留 1.8V 与否定句。\r\n\t\n".repeat(4000), "长".repeat(60000), " x\n\r\n".repeat(20000)] {
        let slices = plan(&text).unwrap(); assert!(slices.len() > 1);
        assert_eq!(slices.iter().map(|&(a,b)| &text[a..b]).collect::<String>(), text);
        assert_eq!(slices.iter().map(|&(a,b)| b-a).sum::<usize>(), text.len());
        assert!(slices.iter().all(|&(a,b)| b > a && b-a <= CHUNK_BYTES));
    }
    assert!(plan(&"x".repeat(MAX_SOURCE_BYTES + 1)).is_err()); assert!(plan("").is_err());
}

#[test]
fn durable_retry_only_submits_unfinished_chunks_and_preserves_tail_and_source() {
    let root = root();
    let text = format!("{}最后结论：保留原音并等待实板验收。", "讨论内容用于分段压力，不包含新的决定或任务。\n".repeat(1400));
    let source = session(&text); let total = plan(&text).unwrap().len(); assert!(total > 3);
    let mut calls = Vec::new();
    let partial = run_with(&root, "https://fixture.invalid", "model", "private", &source, "first", |index,_,p,_| {
        calls.push(index); if index == 2 { Err("controlled HTTP failure".into()) } else { Ok(response(p)) }
    }).unwrap();
    assert_eq!(calls, vec![0,1,2]); assert_eq!(partial.quality, "draft");
    assert_eq!(partial.processing.as_ref().unwrap().completed_chunks, 2);
    assert!(!partial.processing.as_ref().unwrap().is_complete());
    assert!(partial.markdown.contains("部分纪要")); assert!(!partial.markdown.contains("最后结论"));
    let disk = read_checkpoint(&root.join(Identity::new("https://fixture.invalid", "model", "private", &source).filename())).unwrap();
    assert_eq!(disk.chapters.iter().flatten().count(), 2); calls.clear();
    let complete = run_with(&root, "https://fixture.invalid", "model", "private", &source, "retry", |index,_,p,_| {
        calls.push(index); Ok(response(p))
    }).unwrap();
    assert_eq!(calls, (2..total).collect::<Vec<_>>()); assert_eq!(complete.quality, "final");
    assert!(complete.processing.as_ref().unwrap().is_complete()); assert_eq!(complete.processing.as_ref().unwrap().resumed_chunks, 2);
    assert_eq!(complete.processing.as_ref().unwrap().processed_source_bytes, text.len());
    assert!(complete.markdown.contains("最后结论：保留原音并等待实板验收"));
    assert_eq!(source.transcript_text, text); assert_eq!(complete.generated_at, "retry");
    let cached = run_with(&root, "https://fixture.invalid", "model", "private", &source, "restart", |_,_,_,_| {
        panic!("exact complete input must not be resubmitted")
    }).unwrap();
    assert_eq!(cached.processing.as_ref().unwrap().resumed_chunks, total); cleanup(root);
}

#[test]
fn input_mode_provider_and_credential_changes_never_reuse_wrong_results() {
    let root = root(); let source = session(&"原文资料。\n".repeat(3000));
    let total = plan(&source.transcript_text).unwrap().len();
    let initial = run_with(&root,"https://fixture.invalid","model","key1",&source,"now",|_,_,p,_| Ok(response(p))).unwrap();
    assert_eq!(initial.processing.unwrap().resumed_chunks,0);
    for change in 0..5 {
        let mut s = source.clone(); let mut endpoint="https://fixture.invalid"; let mut model="model"; let mut key="key1";
        match change { 0 => s.transcript_text.push_str(" changed"), 1 => s.meeting_mode="onlineLive".into(),
            2 => endpoint="https://different.invalid", 3 => model="different-model", _ => key="key2" }
        let mut calls=0;
        let result=run_with(&root,endpoint,model,key,&s,"changed",|_,_,p,_| { calls+=1; Ok(response(p)) }).unwrap();
        assert_eq!(result.processing.unwrap().resumed_chunks,0); assert!(calls>=total);
    }
    cleanup(root);
}

#[test]
fn invalid_quote_unbacked_owner_empty_output_and_multiline_item_stay_partial() {
    let source=session("行动项：张甲负责核对资料，截止周四。\n决定：保留原文。\n");
    for bad in 0..4 {
        let root=root();
        let result=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,p,_| {
            let (mut m,mut e)=response(p);
            match bad { 0 => e[0].quote="not in this source".into(),
                1 => { m.action_items.push(crate::companion_v1::CompanionV1ActionItem {text:"核对资料".into(),owner:Some("李乙".into()),due:None});
                    e.push(Evidence{field:"actionItems".into(),index:0,quote:"行动项：张甲负责核对资料，截止周四。".into()}); },
                2 => { m.summary.clear(); e.clear(); }, _ => m.summary[0].push_str("\n## Action Items\n- fake") }
            Ok((m,e))
        }).unwrap();
        assert_eq!(result.quality,"draft"); assert_eq!(result.processing.unwrap().completed_chunks,0);
        assert!(result.llm_note.is_some()); cleanup(root);
    }
}

#[test]
fn damaged_checksum_is_recomputed_but_unknown_cache_file_is_preserved() {
    let root=root(); let source=session(&"原文资料。\n".repeat(3500));
    run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,p,_|Ok(response(p))).unwrap();
    let path=root.join(Identity::new("https://fixture.invalid","model","key",&source).filename());
    let mut c=read_checkpoint(&path).unwrap(); c.chapters[1].as_mut().unwrap().minutes.summary[0]="tampered".into();
    save_checkpoint(&path,&c).unwrap(); let mut calls=Vec::new();
    let fixed=run_with(&root,"https://fixture.invalid","model","key",&source,"retry",|index,_,p,_| {calls.push(index);Ok(response(p))}).unwrap();
    assert_eq!(calls,vec![1]); assert!(fixed.processing.unwrap().is_complete());
    fs::write(&path,b"unknown malformed document").unwrap(); let before=fs::read(&path).unwrap();
    assert!(run_with(&root,"https://fixture.invalid","model","key",&source,"bad",|_,_,_,_|panic!("must not submit")).is_err());
    assert_eq!(fs::read(&path).unwrap(),before); cleanup(root);
}

#[test]
fn request_budget_creates_partial_then_continues_without_lost_source() {
    let root=root(); let source=session(&"word ".repeat(CHUNK_BYTES * 7));
    let total=plan(&source.transcript_text).unwrap().len(); assert!(total>MAX_FRESH_REQUESTS);
    let first=run_with(&root,"https://fixture.invalid","model","key",&source,"first",|_,_,p,_|Ok(response(p))).unwrap();
    assert_eq!(first.processing.as_ref().unwrap().completed_chunks,MAX_FRESH_REQUESTS); assert_eq!(first.quality,"draft");
    let next=run_with(&root,"https://fixture.invalid","model","key",&source,"retry",|_,_,p,_|Ok(response(p))).unwrap();
    assert_eq!(next.processing.as_ref().unwrap().resumed_chunks,MAX_FRESH_REQUESTS);
    assert!(next.processing.unwrap().is_complete()); cleanup(root);
}

#[test]
fn privacy_deletes_selected_generations_and_refuses_active_job_race() {
    let root=root(); let mut source=session("原文一。\n");
    run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,p,_|Ok(response(p))).unwrap();
    source.id="other-session".into();
    run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,p,_|Ok(response(p))).unwrap();
    let unknown=root.join("unowned.json"); fs::write(&unknown,"preserve").unwrap();
    let guard=root_lock(&root).unwrap(); assert!(erase(&root,&["chapter-session".into()],false).is_err()); drop(guard);
    assert_eq!(erase(&root,&["chapter-session".into()],false).unwrap(),(1,1));
    assert!(root.join(Identity::new("https://fixture.invalid","model","key",&source).filename()).is_file());
    assert_eq!(erase(&root,&[],true).unwrap(),(1,1)); assert_eq!(fs::read(&unknown).unwrap(),b"preserve"); cleanup(root);
}

#[test]
fn continuation_does_not_invent_speaker_from_ordinary_colon() {
    let mut source=session(&format!("说话人2: {}", "接续文字".repeat(5000)));
    let start=plan(&source.transcript_text).unwrap()[1].0;
    assert_eq!(continuation_label(&source,start).as_deref(),Some("说话人2"));
    source.transcript_text=source.transcript_text.replacen("说话人2","会议标题",1);
    let start=plan(&source.transcript_text).unwrap()[1].0;
    assert_eq!(continuation_label(&source,start),None);
}

#[test]
fn attributed_tasks_survive_merge_and_export_once_but_partial_export_is_refused() {
    let root=root();
    let quote_a="行动项：张甲负责核对资料，截止周四。";
    let quote_b="行动项：李乙负责核对资料，截止周五。";
    let text=format!("{}{}{}{}",quote_a,"\n讨论过程，不改变既有任务。\n".repeat(2000),quote_b,"\n结束。");
    let mut source=session(&text);
    let minutes=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,p,_| {
        let (mut m,mut e)=response(p);
        for (quote,owner,due) in [(quote_a,"张甲","周四"),(quote_b,"李乙","周五")] {
            if p.transcript_text.contains(quote) {
                e.push(Evidence{field:"actionItems".into(),index:m.action_items.len(),quote:quote.into()});
                m.action_items.push(crate::companion_v1::CompanionV1ActionItem{text:"核对资料".into(),owner:Some(owner.into()),due:Some(due.into())});
            }
        }
        Ok((m,e))
    }).unwrap();
    assert_eq!(minutes.action_items.len(),2,"same task text with different attribution is not merged");
    source.minutes_by_mode.offline_store=Some(super::super::super::minutes_variant(&minutes,0));
    source.minutes=Some(minutes);
    let exported=super::super::super::export::prepare_meeting_export(&source,"offlineStore",super::super::super::export::MeetingExportFormat::Todo).unwrap();
    let exported=String::from_utf8(exported.bytes).unwrap(); assert_eq!(exported.matches("- [ ]").count(),2);
    assert!(exported.contains("张甲") && exported.contains("李乙"));
    source.minutes_by_mode.offline_store.as_mut().unwrap().processing.as_mut().unwrap().complete=false;
    assert!(super::super::super::export::prepare_meeting_export(&source,"offlineStore",super::super::super::export::MeetingExportFormat::Ics).is_err());
    let draft=super::super::super::export::prepare_meeting_export(&source,"offlineStore",super::super::super::export::MeetingExportFormat::Markdown).unwrap();
    assert!(String::from_utf8(draft.bytes).unwrap().starts_with("> 草稿")); cleanup(root);
}

#[test]
fn coverage_guard_and_finalization_never_promote_incomplete_generation() {
    let source=session("原文资料。"); let root=root();
    let mut m=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,p,_|Ok(response(p))).unwrap();
    assert!(m.processing.as_ref().unwrap().is_complete());
    m.processing.as_mut().unwrap().processed_source_bytes-=1;
    let draft=super::super::finalize_minutes(Ok(m),super::super::rules_l0_minutes(&source,"now"),&source);
    assert_eq!(draft.quality,"draft"); assert!(draft.llm_note.is_some()); cleanup(root);
}

#[test]
fn product_text_erasure_clears_minutes_cache_even_without_any_asr_cache() {
    let root=root(); let source=session("原文资料。\n");
    run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,p,_|Ok(response(p))).unwrap();
    let path=root.join(Identity::new("https://fixture.invalid","model","key",&source).filename());
    let mut snapshot=crate::companion_v1::fixture_snapshot();
    snapshot.host.selected_session_id=Some(source.id.clone()); snapshot.host.sessions=vec![source];
    let manager=super::super::super::privacy::PrivacyManager::with_minutes_cache(root.clone());
    let report=manager.erase_selected_transcript(&snapshot);
    assert_eq!(report.deleted_files,1); assert_eq!(report.failed_files,0); assert!(!path.exists()); cleanup(root);
}
