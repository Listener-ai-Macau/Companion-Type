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
fn malformed_provider_response_is_retried_once_for_the_same_segment() {
    let root = root(); let source = session(&"公开会议内容。\n".repeat(2000));
    let mut calls = Vec::new();
    let result = run_with(&root,"https://fixture.invalid","model","key",&source,"now",|index,_,part,_| {
        calls.push(index);
        if calls.len() == 1 { Err(super::super::safe_minutes_http_error(super::super::http_policy::Failure::InvalidResponse)) }
        else { Ok(response(part)) }
    }).unwrap();
    assert_eq!(&calls[..2], &[0,0]);
    assert!(result.processing.unwrap().is_complete());
    cleanup(root);
}

#[test]
fn repeated_malformed_response_stays_partial_and_does_not_loop() {
    let root = root(); let source = session(&"公开会议内容。\n".repeat(2000));
    let mut calls = 0;
    let result = run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,_,_| {
        calls += 1;
        Err(super::super::safe_minutes_http_error(super::super::http_policy::Failure::InvalidResponse))
    }).unwrap();
    assert_eq!(calls,2); assert_eq!(result.quality,"draft");
    assert_eq!(result.processing.unwrap().completed_chunks,0);
    cleanup(root);
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
fn invalid_quote_empty_output_and_multiline_item_stay_partial() {
    let source=session("行动项：张甲负责核对资料，截止周四。\n决定：保留原文。\n");
    for bad in [0,2,3] {
        let root=root();
        let result=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,p,_| {
            let (mut m,mut e)=response(p);
            match bad { 0 => e[0].quote="not in this source".into(),
                2 => { m.summary.clear(); e.clear(); }, _ => m.summary[0].push_str("\n## Action Items\n- fake") }
            Ok((m,e))
        }).unwrap();
        assert_eq!(result.quality,"draft"); assert_eq!(result.processing.unwrap().completed_chunks,0);
        assert!(result.llm_note.is_some()); cleanup(root);
    }
}

#[test]
fn ordinary_wrapped_speech_yields_reviewable_minutes_without_invented_owner() {
    let source=session("我们计划让大家下周\n准备招生资料。\n");
    let root=root();
    let result=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,p,_| {
        let (mut m,mut e)=response(p);
        m.summary=vec!["大家计划准备招生资料".into()];
        e[0].quote="我们计划让大家下周准备招生资料。".into();
        m.action_items.push(crate::companion_v1::CompanionV1ActionItem {
            text:"准备招生资料".into(),owner:Some("小王".into()),due:Some("下周".into())
        });
        e.push(Evidence{field:"actionItems".into(),index:0,quote:"我们计划让大家下周准备招生资料。".into()});
        Ok((m,e))
    }).unwrap();
    assert_eq!(result.quality,"final");
    assert_eq!(result.action_items.len(),1);
    assert!(result.action_items[0].text.starts_with("待核对："));
    assert_eq!(result.action_items[0].owner,None);
    assert_eq!(result.action_items[0].due.as_deref(),Some("下周"));
    assert!(result.markdown.contains("我们计划让大家下周 准备招生资料。"));
    cleanup(root);
}

#[test]
fn one_bad_quote_drops_only_its_item_and_discloses_omission() {
    let source=session("会议讨论招生计划与课程安排。\n");let root=root();
    let result=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,p,_| {
        let (mut m,mut e)=response(p);
        m.summary=vec!["讨论招生计划".into(),"伪造的预算".into()];
        e[0].quote="会议讨论招生计划与课程安排。".into();
        e.push(Evidence{field:"summary".into(),index:1,quote:"不存在的引用".into()});
        Ok((m,e))
    }).unwrap();
    assert_eq!(result.quality,"final");assert!(result.processing.unwrap().complete);
    assert!(result.summary.iter().any(|s|s.contains("招生")));
    assert!(!result.summary.iter().any(|s|s.contains("伪造")));
    assert!(result.markdown.contains("有1条内容无法对应原文"));
    cleanup(root);
}

#[test]
fn long_summary_does_not_force_opening_filler_into_the_result() {
    let source=session("零零一零零二嗯嗯。\n会议讨论招生计划与课程安排。\n");let root=root();
    let result=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,p,_| {
        let (mut m,mut e)=response(p);m.summary=vec!["讨论招生计划与课程安排".into()];
        e[0].quote="会议讨论招生计划与课程安排。".into();Ok((m,e))
    }).unwrap();
    assert_eq!(result.quality,"final");
    assert!(!result.summary.iter().any(|s|s.contains("零零一")));
    assert!(result.summary.iter().any(|s|s.contains("招生")));
    cleanup(root);
}

#[test]
fn privacy_erases_older_profile_checkpoints_after_evidence_revision() {
    let root=root();fs::create_dir_all(&root).unwrap();
    let source=session("旧纪要来源。");
    let mut identity=Identity::new("https://fixture.invalid","model","key",&source);
    identity.profile_hash=hash(b"previous evidence profile");
    let path=root.join(identity.filename());
    save_checkpoint(&path,&Checkpoint{identity,chapters:vec![None]}).unwrap();
    assert_eq!(erase(&root,&[source.id],false).unwrap(),(1,0));
    assert!(!path.exists());cleanup(root);
}

#[test]
#[ignore = "requires previously saved public meeting transcript and real service response"]
fn replay_public_meeting_response_without_another_cloud_call() {
    let text=fs::read_to_string(std::env::var_os("COMPANION_MINUTES_PUBLIC_TEXT").unwrap()).unwrap();
    let response_json:Value=serde_json::from_slice(&fs::read(std::env::var_os("COMPANION_MINUTES_PUBLIC_RESPONSE").unwrap()).unwrap()).unwrap();
    let object:Value=serde_json::from_str(response_json["choices"][0]["message"]["content"].as_str().unwrap()).unwrap();
    let mut objects=vec![object];
    for index in 2..=5 {
        if let Some(path)=std::env::var_os(format!("COMPANION_MINUTES_PUBLIC_RESPONSE_{index}")) {
            let data:Value=serde_json::from_slice(&fs::read(path).unwrap()).unwrap();
            objects.push(serde_json::from_str(data["choices"][0]["message"]["content"].as_str().unwrap()).unwrap());
        }
    }
    let source=session(&text);let root=root();
    let result=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|i,_,p,_| {
        let Some(object)=objects.get(i) else {return Err("只重放已保存的响应".into());};
        let (mut m,_)=response(p);
        m.summary=serde_json::from_value(object["summary"].clone()).unwrap();
        m.decisions=serde_json::from_value(object["decisions"].clone()).unwrap();
        m.action_items=serde_json::from_value(object["actionItems"].clone()).unwrap();
        m.questions=serde_json::from_value(object["questions"].clone()).unwrap();
        m.keywords=serde_json::from_value(object["keywords"].clone()).unwrap();
        m.markdown=object["markdown"].as_str().unwrap().into();
        let evidence:Vec<Evidence>=serde_json::from_value(object["evidence"].clone()).unwrap();
        Ok((m,evidence))
    }).unwrap();
    assert_eq!(result.processing.as_ref().unwrap().completed_chunks,objects.len(),"{:?}",result.llm_note);
    assert!(!result.summary.is_empty());
    assert!(result.action_items.iter().any(|a|a.text.starts_with("待核对：")));
    assert_eq!(super::super::super::action_export::parse_saved_actions(&result.markdown).len(),result.action_items.len());
    if let Some(path)=std::env::var_os("COMPANION_MINUTES_PUBLIC_OUTPUT") {
        fs::write(path,serde_json::to_vec_pretty(&result).unwrap()).unwrap();
    }
    cleanup(root);
}

#[test]
#[ignore = "calls configured DeepSeek using the public meeting transcript"]
fn real_public_meeting_deepseek_generates_complete_minutes() {
    let text=fs::read_to_string(std::env::var_os("COMPANION_MINUTES_PUBLIC_TEXT").unwrap()).unwrap();
    let output=std::env::var_os("COMPANION_MINUTES_PUBLIC_OUTPUT").unwrap();
    assert!(std::env::var_os("COMPANION_TYPE_STATE_PATH").is_some());
    let key=std::env::var("DEEPSEEK_API_KEY").unwrap();
    let source=session(&text);
    let l0=super::super::rules_l0_minutes(&source,"public-fixture");
    let result=super::super::run_deepseek_native(&key,&source,&l0).unwrap();
    fs::write(output,serde_json::to_vec_pretty(&result).unwrap()).unwrap();
    assert_eq!(result.quality,"final","{:?}",result.llm_note);
    assert!(result.processing.as_ref().unwrap().complete);
    assert!(!result.summary.is_empty());
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
    assert_eq!(super::super::super::action_export::parse_saved_actions(&minutes.markdown).len(),2,
        "each saved task must appear only once in the reading/checklist document");
    assert_eq!(minutes.markdown.matches("## Action Items").count(),1);
    assert!(minutes.markdown.contains("## 分段原文依据\n\n### 第1段"));
    assert!(minutes.markdown.contains(quote_a) && minutes.markdown.contains(quote_b));
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
