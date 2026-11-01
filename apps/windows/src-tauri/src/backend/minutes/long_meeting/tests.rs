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
#[ignore = "replays the saved real-provider public long meeting without another cloud call"]
fn replay_long_meeting_conditional_actions() {
    let text=fs::read_to_string(std::env::var_os("COMPANION_MINUTES_PUBLIC_TEXT").unwrap()).unwrap();
    let checkpoint=read_checkpoint(Path::new(&std::env::var_os("COMPANION_MINUTES_REPLAY_CHECKPOINT").unwrap())).unwrap();
    let out=std::env::var_os("COMPANION_MINUTES_PUBLIC_OUTPUT").unwrap();
    let source=session(&text);let root=root();
    let result=run_with(&root,"https://fixture.invalid","replay","test",&source,"replay",|index,_,part,_| {
        let chapter=checkpoint.chapters[index].as_ref().ok_or("recorded chapter missing")?;
        if chapter.source_hash!=hash(part.transcript_text.as_bytes()) {return Err("recorded chapter source mismatch".into());}
        Ok((chapter.minutes.clone(),chapter.evidence.clone()))
    }).unwrap();
    fs::write(out,serde_json::to_vec_pretty(&result).unwrap()).unwrap();
    assert!(result.processing.as_ref().unwrap().complete);
    let action=result.action_items.iter().find(|a|a.text.contains("小陈")&&a.text.contains("交货日期")).unwrap();
    assert!(action.text.contains("如果客户提出修改")); assert!(action.due.is_none());
    assert!(result.action_items.iter().any(|a|a.text.contains("小林")&&a.text.contains("参会材料")));
    assert!(result.action_items.iter().any(|a|a.text.contains("小赵")&&a.text.contains("费用清单")));
    assert!(!result.action_items.iter().any(|a|a.text.contains("小吴")));
    cleanup(root);
}

#[test]
fn conditional_action_from_summary_also_restores_condition_before_reminder() {
    let source=format!("{}\n如果客户提出修改，小陈下周一再确认交货日期。", "前文".repeat(1000));
    let part=session(&source);let (mut minutes,mut evidence)=response(&part);
    minutes.action_items.push(crate::companion_v1::CompanionV1ActionItem {
        text:"客户提出修改，小陈下周一再确认交货日期。".into(),owner:Some("小陈".into()),due:Some("下周一".into()) });
    evidence.push(Evidence {field:"actionItems".into(),index:0,quote:"客户提出修改，小陈下周一再确认交货日期。".into()});
    preserve_conditional_actions(&mut minutes,&mut evidence,&source);
    assert_eq!(minutes.action_items[0].text,"如果客户提出修改，小陈下周一再确认交货日期。");
    assert_eq!(minutes.action_items[0].due,None);
    assert!(evidence.iter().any(|e|e.field=="actionItems" && e.quote.starts_with("如果")));
    assert_eq!(retain_source_backed(&mut minutes,&mut evidence,&source),0);
    validate_chapter(&minutes,&evidence,&source).unwrap();
}

#[test]
fn literal_conditional_followup_is_added_without_unrelated_or_cancelled_items() {
    let source="小林负责整理材料。\n如果客户提出修改，小陈下周一再确认交货日期。\n如果客户还有问题小周再跟进报价\n如果客户取消订单小王再联系退款\n如果取消订单不需要再确认交货日期。";
    let part=session(source);let (mut minutes,mut evidence)=response(&part);
    append_conditional_source_actions(&mut minutes,&mut evidence,source);
    preserve_conditional_actions(&mut minutes,&mut evidence,source);
    assert_eq!(minutes.action_items.len(),3);
    assert!(minutes.action_items.iter().any(|a|a.text.contains("如果客户取消订单小王再联系退款")));
    assert!(minutes.action_items.iter().any(|a|a.text.contains("如果客户还有问题小周再跟进报价")));
    assert!(minutes.action_items[0].text.contains("如果客户提出修改"));
    assert!(minutes.action_items[0].due.is_none());
    assert_eq!(retain_source_backed(&mut minutes,&mut evidence,source),0);
    validate_chapter(&minutes,&evidence,source).unwrap();
}

#[test]
fn unrelated_previous_line_is_not_a_condition_for_a_task() {
    let source="如果是参与这个\n请小赵明天下午把费用清单发给我。";
    let part=session(source);let (mut minutes,mut evidence)=response(&part);
    minutes.action_items.push(crate::companion_v1::CompanionV1ActionItem{text:"发费用清单".into(),owner:Some("小赵".into()),due:Some("明天下午".into())});
    evidence.push(Evidence{field:"actionItems".into(),index:0,quote:"请小赵明天下午把费用清单发给我".into()});
    preserve_conditional_actions(&mut minutes,&mut evidence,source);
    assert_eq!(minutes.action_items[0].due.as_deref(),Some("明天下午"));
    assert!(!minutes.action_items[0].text.contains("如果"));
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
fn cancelled_long_minutes_keep_completed_chapters_and_resume_without_resending() {
    use crate::backend::meeting_processing_job::{self,Kind,MINUTES_CANCELLED};
    let root=root();let text=format!("{}最后结论：保留原音并等待实板验收。", "讨论内容用于分段压力，不包含新的决定或任务。\n".repeat(1400));
    let source=session(&text);let total=plan(&text).unwrap().len();assert!(total>3);
    let mut calls=Vec::new();
    let stopped=meeting_processing_job::run(&source.id,"minutes-job",Kind::Minutes,||
        run_with(&root,"https://fixture.invalid","model","private",&source,"first",|index,_,part,_|{
            calls.push(index);
            if index==1 {assert!(meeting_processing_job::cancel(&source.id,"minutes-job").unwrap());}
            Ok(response(part))
        }));
    assert_eq!(stopped.unwrap_err(),MINUTES_CANCELLED);assert_eq!(calls,vec![0,1]);
    let checkpoint=read_checkpoint(&root.join(Identity::new("https://fixture.invalid","model","private",&source).filename())).unwrap();
    assert_eq!(checkpoint.chapters.iter().flatten().count(),2);assert_eq!(source.transcript_text,text);
    calls.clear();let resumed=run_with(&root,"https://fixture.invalid","model","private",&source,"retry",|index,_,part,_|{
        calls.push(index);Ok(response(part))
    }).unwrap();
    assert_eq!(calls,(2..total).collect::<Vec<_>>());assert!(resumed.processing.unwrap().complete);
    assert_eq!(source.transcript_text,text);cleanup(root);
}

#[test]
fn cancelled_malformed_minutes_response_does_not_send_a_retry() {
    use crate::backend::meeting_processing_job::{self,Kind,MINUTES_CANCELLED};
    let root=root();let source=session(&"公开会议内容。\n".repeat(2000));let mut calls=0;
    let result=meeting_processing_job::run(&source.id,"minutes-job",Kind::Minutes,||
        run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,_,_|{
            calls+=1;assert!(meeting_processing_job::cancel(&source.id,"minutes-job").unwrap());Err(MISSING_EVIDENCE.into())
        }));
    assert_eq!(result.unwrap_err(),MINUTES_CANCELLED);assert_eq!(calls,1);cleanup(root);
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
fn missing_evidence_retries_once_then_preserves_finished_chapters() {
    let root=root();let source=session(&"公开会议内容。\n".repeat(2000));
    let mut calls=Vec::new();
    let result=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|index,_,part,_| {
        calls.push(index);
        if calls.len()==1 {Err(MISSING_EVIDENCE.into())} else {Ok(response(part))}
    }).unwrap();
    assert_eq!(&calls[..2],&[0,0]);assert!(result.processing.unwrap().is_complete());
    let mut repeated=0;
    let other=session(&"另一场公开会议内容。\n".repeat(2000));
    let partial=run_with(&root,"https://fixture.invalid","model","key",&other,"now",|_,_,_,_| {
        repeated+=1;Err(MISSING_EVIDENCE.into())
    }).unwrap();
    // One malformed chapter may be deferred; stop after the next chapter also
    // fails rather than retrying the whole meeting indefinitely.
    assert_eq!(repeated,4);assert_eq!(partial.quality,"draft");assert_eq!(partial.processing.unwrap().completed_chunks,0);
    cleanup(root);
}

#[test]
fn missing_evidence_defers_one_chapter_and_completes_without_repeating_others() {
    let root=root();
    let text=format!("{}最后结论：保留原音并等待实板验收。", "讨论内容用于分段压力，不包含新的决定或任务。\n".repeat(1400));
    let source=session(&text);let total=plan(&text).unwrap().len();assert!(total>3);
    let mut calls=Vec::new();let mut bad_attempts=0;
    let result=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|index,_,part,_| {
        calls.push(index);
        if index==2 && bad_attempts<2 {bad_attempts+=1;Err(MISSING_EVIDENCE.into())}
        else {Ok(response(part))}
    }).unwrap();
    let mut expected=vec![0,1,2,2];expected.extend(3..total);expected.push(2);
    assert_eq!(calls,expected);assert_eq!(bad_attempts,2);
    assert_eq!(result.quality,"final");assert!(result.processing.unwrap().is_complete());
    assert!(result.markdown.contains("最后结论：保留原音并等待实板验收"));
    assert_eq!(source.transcript_text,text);cleanup(root);
}

#[test]
fn deferred_chapter_and_later_service_failure_remain_partial_and_retryable() {
    let root=root();let source=session(&"公开会议内容。\n".repeat(5000));
    let total=plan(&source.transcript_text).unwrap().len();assert!(total>3);
    let mut calls=Vec::new();
    let partial=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|index,_,part,_| {
        calls.push(index);
        if index==2 {Err(MISSING_EVIDENCE.into())}
        else if index==3 {Err("controlled service failure".into())}
        else {Ok(response(part))}
    }).unwrap();
    assert_eq!(calls,vec![0,1,2,2,3]);assert_eq!(partial.quality,"draft");
    assert_eq!(partial.processing.as_ref().unwrap().completed_chunks,2);
    let note=partial.llm_note.unwrap();assert!(note.contains("第3段") && note.contains("第4段"));
    let mut retry=Vec::new();
    let result=run_with(&root,"https://fixture.invalid","model","key",&source,"retry",|index,_,part,_| {
        retry.push(index);Ok(response(part))
    }).unwrap();
    assert_eq!(retry,(2..total).collect::<Vec<_>>());assert!(result.processing.unwrap().is_complete());
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
fn extra_quote_does_not_erase_an_assignment_already_supported_by_one_excerpt() {
    let s=session("小王负责整理报价，周五前发送。\n报价已经确定。\n");
    let (mut m,mut e)=response(&s);
    m.action_items.push(crate::companion_v1::CompanionV1ActionItem {
        text:"整理并发送报价".into(),owner:Some("小王".into()),due:Some("周五".into())
    });
    for quote in ["小王负责整理报价，周五前发送。","报价已经确定。"] {
        e.push(Evidence{field:"actionItems".into(),index:0,quote:quote.into()});
    }
    assert_eq!(retain_source_backed(&mut m,&mut e,&s.transcript_text),0);
    mark_uncertain_items(&mut m,&e);
    validate_chapter(&m,&e,&s.transcript_text).unwrap();
    assert_eq!(m.action_items[0].owner.as_deref(),Some("小王"));
    assert_eq!(m.action_items[0].due.as_deref(),Some("周五"));
    assert!(!m.action_items[0].text.starts_with("待核对："));

    let separate=session("小王负责整理报价。\n客户要求周五发送。\n");
    let (mut m,mut e)=response(&separate);
    m.action_items.push(crate::companion_v1::CompanionV1ActionItem {
        text:"整理并发送报价".into(),owner:Some("小王".into()),due:Some("周五".into())
    });
    for quote in ["小王负责整理报价。","客户要求周五发送。"] {
        e.push(Evidence{field:"actionItems".into(),index:0,quote:quote.into()});
    }
    retain_source_backed(&mut m,&mut e,&separate.transcript_text);
    mark_uncertain_items(&mut m,&e);
    validate_chapter(&m,&e,&separate.transcript_text).unwrap();
    assert_eq!(m.action_items[0].owner,None);
    assert_eq!(m.action_items[0].due,None);
    assert!(m.action_items[0].text.starts_with("待核对："));
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
    let mut current=next;
    while !current.processing.as_ref().unwrap().is_complete() {
        current=run_with(&root,"https://fixture.invalid","model","key",&source,"continue",|_,_,p,_|Ok(response(p))).unwrap();
    }
    assert_eq!(current.processing.unwrap().processed_source_bytes,source.transcript_text.len()); cleanup(root);
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

#[test]
fn concise_overview_preserves_complete_minutes_and_checks_sources() {
    let source = session("会议原文");
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["讨论包装方案".into(), "周五前发送报价".into(), "下周确认交付".into()];
    minutes.markdown = "# 完整纪要\n\n## 分段原文依据\n\n原文不变".into();
    let original = minutes.markdown.clone();let summary = minutes.summary.clone();
    let points = parse_concise_overview(r#"{"overview":[{"text":"讨论包装、报价和交付安排。","sources":[0,1,2]}]}"#,3).unwrap();
    prepend_concise_overview(&mut minutes,&points);
    assert!(minutes.markdown.starts_with("## 会议概览\n\n> AI根据详细纪要整理"));
    assert!(minutes.markdown.contains("- 讨论包装、报价和交付安排。"));
    assert!(minutes.markdown.ends_with(&original));assert_eq!(minutes.summary,summary);
    for bad in [r#"{"overview":[{"text":"错误引用","sources":[3]}]}"#,
        r#"{"overview":[{"text":"无引用","sources":[]}]}"#,
        r#"{"overview":[{"text":"重复引用","sources":[0,0]}]}"#,
        r#"{"overview":[{"text":"一行\n另一行","sources":[0]}]}"#] {
        assert!(parse_concise_overview(bad,3).is_err());
    }
}

#[test]
fn overview_keeps_full_minutes_and_uses_only_selected_items_in_original_order() {
    let source = session("会议原文");
    let (mut minutes, _) = response(&source);
    minutes.summary = (0..15).map(|i| format!("原有重点{i}")).collect();
    minutes.markdown = "# 原来的完整纪要\n\n## 行动项\n\n- 跟进报价".into();
    let full = minutes.markdown.clone();
    let details = minutes.summary.clone();
    prepend_overview(&mut minutes, &[12, 1, 8]);
    assert!(minutes.markdown.starts_with("## 全会重点\n\n- 原有重点1\n- 原有重点8\n- 原有重点12"));
    assert!(minutes.markdown.ends_with(&full));
    assert_eq!(minutes.summary, details);
    for bad in [vec![], vec![1, 1], vec![15], (0..13).collect()] {
        let previous = minutes.markdown.clone();
        prepend_overview(&mut minutes, &bad);
        assert_eq!(minutes.markdown, previous);
    }
}

#[test]
fn overview_provider_response_must_be_valid_unique_indices() {
    use std::{io::{Read, Write}, net::TcpListener, thread};
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let worker = thread::spawn(move || {
        for content in [r#"{"indices":[2,0]}"#, r#"{"indices":[1,1]}"#] {
            let (mut stream, _) = listener.accept().unwrap();
            stream.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
            let mut data = Vec::new(); let mut buffer = [0u8; 4096];
            loop {
                let n = stream.read(&mut buffer).unwrap(); if n == 0 { break; }
                data.extend_from_slice(&buffer[..n]);
                if let Some(i) = data.windows(4).position(|w| w == b"\r\n\r\n") {
                    let headers = String::from_utf8_lossy(&data[..i]);
                    let length: usize = headers.lines().find_map(|l| l.split_once(':')
                        .filter(|(k,_)| k.eq_ignore_ascii_case("content-length"))
                        .and_then(|(_,v)| v.trim().parse().ok())).unwrap();
                    if data.len() >= i + 4 + length { break; }
                }
            }
            let start = data.windows(4).position(|w| w == b"\r\n\r\n").unwrap() + 4;
            let request: Value = serde_json::from_slice(&data[start..]).unwrap();
            let input = request["messages"][1]["content"].as_str().unwrap();
            assert!(input.find("\"title\"").unwrap() < input.find("\"summary\"").unwrap());
            assert!(input.find("\"summary\"").unwrap() < input.find("\"actions\"").unwrap());
            let payload = serde_json::json!({"choices":[{"finish_reason":"stop","message":{"content":content}}]}).to_string();
            write!(stream,"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}",payload.len(),payload).unwrap();
        }
    });
    let endpoint = format!("http://{address}/chat/completions");
    let client = reqwest::blocking::Client::builder().no_proxy().timeout(Duration::from_secs(5)).build().unwrap();
    let items = vec!["第一项".into(), "第二项".into(), "第三项".into()];
    assert_eq!(request_overview_section(&endpoint, "test", "test-key", &items, 0, items.len(), &client).unwrap(), vec![2,0]);
    assert!(request_overview_section(&endpoint, "test", "test-key", &items, 0, items.len(), &client).is_err());
    worker.join().unwrap();
}

#[test]
#[ignore = "live public benchmark and configured DeepSeek service"]
fn real_public_long_meeting_overview() {
    let input = std::env::var("COMPANION_PUBLIC_MINUTES_RESULT").unwrap();
    let output = std::env::var("COMPANION_PUBLIC_OVERVIEW_RESULT").unwrap();
    let value: Value = serde_json::from_slice(&fs::read(input).unwrap()).unwrap();
    let mut minutes: CompanionV1MeetingMinutes = serde_json::from_value(value["minutes"].clone()).unwrap();
    let original = minutes.markdown.clone();
    let key = std::env::var("DEEPSEEK_API_KEY").unwrap();
    let model = std::env::var("DEEPSEEK_MODEL").unwrap_or_else(|_| "deepseek-chat".into());
    let base = std::env::var("DEEPSEEK_BASE_URL").unwrap_or_else(|_| "https://api.deepseek.com".into());
    let endpoint = format!("{}/chat/completions", base.trim_end_matches('/'));
    let client = super::super::deepseek_http_client(&endpoint).unwrap();
    let points = request_concise_overview(&endpoint, &model, &key, &minutes.summary, &client).unwrap();
    prepend_concise_overview(&mut minutes, &points);
    assert!(minutes.markdown.ends_with(&original));
    fs::write(output, serde_json::to_vec_pretty(&serde_json::json!({"minutes":minutes})).unwrap()).unwrap();
}


#[test]
fn background_review_marks_only_selected_tasks_and_preserves_full_evidence() {
    let source = session("项目报价。旁边聊家务。");
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["会议讨论项目报价。".into(), "旁边出现家务闲聊。".into()];
    minutes.action_items = vec![
        crate::companion_v1::CompanionV1ActionItem { text:"周五发报价".into(), owner:Some("小王".into()), due:Some("周五".into()) },
        crate::companion_v1::CompanionV1ActionItem { text:"买猫粮".into(), owner:None, due:None },
    ];
    minutes.markdown = "> 原会议已完成。\n\n# 原纪要\n\n## 分段原文依据\n\n### 第1段\n- 原始引用。".into();
    let before = minutes.clone();
    apply_action_review(&source, &mut minutes, &[], &ActionReview {background:vec![1],duplicates:vec![]});
    assert_eq!(minutes.action_items.len(), 2);
    assert_eq!(minutes.action_items[0].text, "周五发报价");
    assert_eq!(minutes.action_items[0].owner.as_deref(), Some("小王"));
    assert_eq!(minutes.action_items[0].due.as_deref(), Some("周五"));
    assert_eq!(minutes.action_items[1].text, "可能来自背景对话，请核对：买猫粮");
    assert!(minutes.markdown.contains("- 可能来自背景对话，请核对：买猫粮"));
    assert!(minutes.markdown.ends_with("### 第1段\n- 原始引用。"));
    assert_eq!(minutes.summary, before.summary);
    let marked = minutes.markdown.clone();
    apply_action_review(&source, &mut minutes, &[], &ActionReview {background:vec![0,0],duplicates:vec![]});
    apply_action_review(&source, &mut minutes, &[], &ActionReview {background:vec![3],duplicates:vec![]});
    assert_eq!(minutes.markdown, marked);
    let mut malformed = before.clone(); malformed.markdown = "unexpected".into();
    apply_action_review(&source, &mut malformed, &[], &ActionReview {background:vec![0],duplicates:vec![]});
    assert_eq!(malformed.action_items[0].text, before.action_items[0].text);
}

#[test]
fn background_keyword_review_requires_source_and_preserves_legitimate_topic_changes() {
    let quote="旁人说要盘点仓库里的库存。";
    let source=session(&format!("会议讨论发布计划。{quote}会议确认后续工作。"));
    let (mut minutes,_) = response(&source);
    minutes.summary=vec!["会议讨论发布计划。".into()];
    minutes.keywords=vec!["库存盘点".into(),"发布计划".into(),"仓库".into()];
    minutes.action_items=vec![crate::companion_v1::CompanionV1ActionItem{text:"盘点仓库库存".into(),owner:None,due:None}];
    minutes.markdown=format!("> 原会议已完成。\n\n# 原纪要\n\n## 分段原文依据\n\n### 第1段\n- {quote}");
    let quotes=vec![vec![quote.to_string()]];
    assert_eq!(background_keyword_indices(&source,&minutes,&quotes,&[0]),vec![0]);
    assert!(background_keyword_indices(&source,&minutes,&quotes,&[]).is_empty());
    assert!(background_keyword_indices(&source,&minutes,&[vec!["不存在的原话".into()]],&[0]).is_empty());
    let mut switched=source.clone();
    switched.transcript_text.push_str(&format!("{}下月会议改为盘点仓库库存。", "会议继续讨论。".repeat(30)));
    assert!(background_keyword_indices(&switched,&minutes,&quotes,&[0]).is_empty(),"a real later topic change must not be labelled as background");
    let mut summarized=minutes.clone();summarized.summary.push("会议决定盘点仓库库存。".into());
    assert!(background_keyword_indices(&source,&summarized,&quotes,&[0]).is_empty(),"a keyword supported by the meeting summary remains ordinary");
    let mut repeated=source.clone();repeated.transcript_text.push_str(quote);
    assert!(background_keyword_indices(&repeated,&minutes,&quotes,&[0]).is_empty(),"ambiguous repeated source cannot establish provenance");
    let original=minutes.keywords.clone();
    apply_action_review(&source,&mut minutes,&quotes,&ActionReview{background:vec![0],duplicates:vec![]});
    assert_eq!(minutes.keywords,original,"structured keywords are never removed or renamed");
    assert!(minutes.markdown.contains("库存盘点（可能来自背景对话，请核对）"));
    assert!(!minutes.markdown.contains("发布计划（可能来自背景"));
    assert!(minutes.markdown.contains(quote),"the original evidence is retained");
}

#[test]
#[ignore = "requires a previously authorized isolated real-meeting result and checkpoint; no network"]
fn replay_real_background_keyword_against_validated_source() {
    let input=std::env::var_os("COMPANION_BACKGROUND_REPLAY_RESULT").unwrap();
    let checkpoint=std::env::var_os("COMPANION_BACKGROUND_REPLAY_CHECKPOINT").unwrap();
    let target=std::env::var("COMPANION_BACKGROUND_EXPECTED_KEYWORD").unwrap();
    let source:CompanionV1HostSession=serde_json::from_slice(&fs::read(input).unwrap()).unwrap();
    let mut minutes=source.minutes.clone().unwrap();
    let mut background=Vec::new();
    for (index,item) in minutes.action_items.iter_mut().enumerate() {
        if let Some(text)=item.text.strip_prefix("可能来自背景对话，请核对：") {
            item.text=text.to_string();background.push(index);
        }
    }
    let quotes=action_source_quotes(&read_checkpoint(Path::new(&checkpoint)).unwrap(),&minutes);
    let flagged=background_keyword_indices(&source,&minutes,&quotes,&background);
    let target_index=minutes.keywords.iter().position(|keyword|keyword==&target).expect("known source keyword");
    assert!(flagged.contains(&target_index));
    if let Ok(excluded)=std::env::var("COMPANION_BACKGROUND_EXCLUDED_IDS") {
        for index in excluded.split(',').filter(|v|!v.is_empty()).map(|v|v.parse::<usize>().unwrap()) {
            assert!(!flagged.contains(&index),"unrelated model-only candidate must not be marked");
        }
    }
    let before=minutes.keywords.clone();
    apply_action_review(&source,&mut minutes,&quotes,&ActionReview{background,duplicates:vec![]});
    assert_eq!(minutes.keywords,before);
    assert!(minutes.markdown.contains(&format!("{target}（可能来自背景对话，请核对）")));
}

#[test]
fn background_review_accepts_valid_ids_and_rejects_invalid_responses() {
    use std::{io::{Read, Write}, net::TcpListener, thread};
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let worker = thread::spawn(move || {
        for content in [r#"{"possiblyUnrelated":[1]}"#, r#"{"possiblyUnrelated":[1,1]}"#, r#"{"possiblyUnrelated":[2]}"#] {
            let (mut stream, _) = listener.accept().unwrap();
            stream.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
            let mut data = Vec::new(); let mut buffer = [0u8; 4096];
            loop {
                let n = stream.read(&mut buffer).unwrap(); if n == 0 { break; }
                data.extend_from_slice(&buffer[..n]);
                if let Some(i) = data.windows(4).position(|w| w == b"\r\n\r\n") {
                    let headers = String::from_utf8_lossy(&data[..i]);
                    let length: usize = headers.lines().find_map(|l| l.split_once(':')
                        .filter(|(k,_)| k.eq_ignore_ascii_case("content-length"))
                        .and_then(|(_,v)| v.trim().parse().ok())).unwrap();
                    if data.len() >= i + 4 + length { break; }
                }
            }
            let payload = serde_json::json!({"choices":[{"finish_reason":"stop","message":{"content":content}}]}).to_string();
            write!(stream,"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}",payload.len(),payload).unwrap();
        }
    });
    let source = session("会议原文"); let (mut minutes, _) = response(&source);
    minutes.action_items = vec![
        crate::companion_v1::CompanionV1ActionItem{text:"项目报价".into(),owner:None,due:None},
        crate::companion_v1::CompanionV1ActionItem{text:"其他闲聊".into(),owner:None,due:None},
    ];
    let endpoint = format!("http://{address}/chat/completions");
    let client = reqwest::blocking::Client::builder().no_proxy().timeout(Duration::from_secs(5)).build().unwrap();
    assert_eq!(request_background_review(&endpoint,"test","test-key",&source,&minutes,&[],&client).unwrap().background, vec![1]);
    assert!(request_background_review(&endpoint,"test","test-key",&source,&minutes,&[],&client).is_err());
    assert!(request_background_review(&endpoint,"test","test-key",&source,&minutes,&[],&client).is_err());
    worker.join().unwrap();
}


#[test]
fn background_context_reuses_only_matching_source_backed_actions() {
    let root = root();
    let source = session("小王周五整理报价。旁边说周六买猫粮。\n");
    let minutes = run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,part,_| {
        let (mut m, mut e) = response(part);
        m.action_items = vec![
            crate::companion_v1::CompanionV1ActionItem{text:"整理报价".into(),owner:Some("小王".into()),due:Some("周五".into())},
            crate::companion_v1::CompanionV1ActionItem{text:"买猫粮".into(),owner:None,due:Some("周六".into())},
        ];
        e.push(Evidence{field:"actionItems".into(),index:0,quote:"小王周五整理报价".into()});
        e.push(Evidence{field:"actionItems".into(),index:1,quote:"旁边说周六买猫粮".into()});
        Ok((m,e))
    }).unwrap();
    let path = root.join(Identity::new("https://fixture.invalid","model","key",&source).filename());
    let checkpoint = read_checkpoint(&path).unwrap();
    let quotes = action_source_quotes(&checkpoint,&minutes);
    assert_eq!(quotes.len(), 2);
    assert_eq!(quotes[0], vec!["小王周五整理报价"]);
    assert_eq!(quotes[1], vec!["旁边说周六买猫粮"]);
    let mut other = minutes.clone(); other.action_items[0].due = Some("周一".into());
    assert!(action_source_quotes(&checkpoint,&other)[0].is_empty());
    cleanup(root);
}


#[test]
fn action_review_merges_only_same_source_and_attribution_and_retains_quotes() {
    let source = session("原始会议语音。"); let (mut minutes, _) = response(&source);
    let action = |text: &str, owner: Option<&str>, due: Option<&str>| crate::companion_v1::CompanionV1ActionItem {
        text:text.into(), owner:owner.map(str::to_string), due:due.map(str::to_string)
    };
    minutes.action_items = vec![action("客户提出修改的话，确认交货时间",None,Some("下周一")),
        action("若客户提出修改，确认交货时间",None,Some("下周一")),
        action("确认其他产品的交货时间",None,Some("下周一")),
        action("小李确认交货时间",Some("小李"),Some("下周一"))];
    minutes.markdown = "> 原会议已完成。\n\n# 原纪要\n\n## 分段原文依据\n\n### 第1段\n- 客户提出修改，下周一确认交货时间。".into();
    let quotes=vec![vec!["客户提出修改，下周一确认交货时间。".into()],vec!["客户提出修改，下周一确认交货时间。".into()],
        vec!["另一产品的原话".into()],vec!["客户提出修改，下周一确认交货时间。".into()]];
    let review=ActionReview {background:vec![1],duplicates:vec![vec![0,1],vec![2,3]]};
    apply_action_review(&source,&mut minutes,&quotes,&review);
    assert_eq!(minutes.action_items.len(),3);
    assert!(minutes.action_items[0].text.starts_with("可能来自背景对话，请核对："));
    assert!(minutes.action_items[1].text.contains("其他产品"));
    assert_eq!(minutes.action_items[2].owner.as_deref(),Some("小李"));
    assert!(minutes.markdown.ends_with("### 第1段\n- 客户提出修改，下周一确认交货时间。"));
}
