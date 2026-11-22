use super::*;

#[test]
fn correcting_model_timing_invalidates_minutes_even_when_words_match() {
    let mut source=session("同意周五检查。");
    source.utterances=vec![crate::companion_v1::CompanionV1UtteranceSegment {
        text:"同意周五检查。".into(),start_ms:1000,end_ms:2000,speaker:Some(0),approximate_timing:false
    }];
    let first=Identity::new("https://fixture.invalid","model","key",&source);
    source.utterances[0].start_ms=1100;
    let corrected=Identity::new("https://fixture.invalid","model","key",&source);
    assert_ne!(first.filename(),corrected.filename());
}

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
fn chapter_summary_rebinds_a_relative_speaker_across_the_cut() {
    let source = session("说话人2: 开场。\n说话人6：先谈参与者的作用。规模确认后再讨论成本。\n说话人2: 统计已完成。");
    let quote = "规模确认后再讨论成本。";
    let start = source.transcript_text.find(quote).unwrap();
    let end = start + quote.len();
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["一位发言者（说话人2之前的发言者）主张先确认规模。".into()];
    let mut evidence = vec![Evidence {field: "summary".into(), index: 0, quote: quote.into()}];
    summary_review::review(&source, start..end, &mut minutes, &mut evidence);
    assert_eq!(minutes.summary[0], "说话人6主张先确认规模。");
    assert_eq!(evidence[0].quote, quote);
}

#[test]
fn chapter_summary_keeps_relative_attribution_unresolved_for_repeated_or_mixed_quotes() {
    let source = session("说话人5: 样品需要冷藏。再核一次。\n说话人2: 再核一次。箱子已到。");
    for quotes in [vec!["再核一次。"], vec!["样品需要冷藏。", "箱子已到。"]] {
        let (mut minutes, _) = response(&source);
        minutes.summary = vec!["说话人2之前的发言者说明样品需要冷藏。".into()];
        let mut evidence = quotes.into_iter().map(|quote| Evidence {
            field: "summary".into(), index: 0, quote: quote.into(),
        }).collect();
        summary_review::review(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
        assert_eq!(minutes.summary[0], "一位发言者（归属待核对）说明样品需要冷藏。");
    }
}

#[test]
fn chapter_summary_marks_only_the_inverted_frequency_for_the_same_activity() {
    let source = session("说话人3：目前调试完成。大家每天每周 都会有一次例会，另每周归档、每天备份。");
    let (mut minutes, _) = response(&source);
    minutes.summary = vec![
        "目前调试完成；每星期每日召开例会；每周归档、每天备份。".into(),
        "每周每天检查机房。".into(),
    ];
    let mut evidence = (0..minutes.summary.len()).map(|index| Evidence {
        field: "summary".into(), index, quote: "目前调试完成。".into(),
    }).collect::<Vec<_>>();
    let range = 0..source.transcript_text.len();
    summary_review::review(&source, range.clone(), &mut minutes, &mut evidence);
    assert_eq!(minutes.summary[0], "目前调试完成；（频率待核对）召开例会；每周归档、每天备份。");
    assert_eq!(minutes.summary[1], "每周每天检查机房。");
    assert_eq!(evidence[2].quote, "每天每周 都会有一次例会");
    summary_review::review(&source, range, &mut minutes, &mut evidence);
    assert_eq!(evidence.len(), 3);
}

#[test]
fn chapter_coverage_keeps_stage_range_and_cumulative_count_distinct() {
    let quote = "这批零件的检验流程已经上线";
    let range = "这个阶段里我们每月也复核 10 到 20 件";
    let source = session(&format!(
        "说话人2：{quote}。\n说话人2：现在都在第二车间完成。\n说话人2：{range}，和供应商复盘了几轮。已复核160多件。"
    ));
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["第二车间检查，已复核160多件。".into()];
    let mut evidence = vec![Evidence {field: "summary".into(), index: 0, quote: quote.into()}];
    let chapter = 0..source.transcript_text.len();
    summary_coverage::restore(&source, chapter.clone(), &mut minutes, &mut evidence);
    assert_eq!(minutes.summary[0], format!("第二车间检查，已复核160多件。补充原话「{range}」。"));
    assert_eq!(evidence[1].quote, range);
    summary_coverage::restore(&source, chapter, &mut minutes, &mut evidence);
    assert_eq!(evidence.len(), 2);
}

#[test]
fn chapter_coverage_never_joins_another_speaker_or_an_unrelated_range() {
    let prefix = "说话人2：复核流程上线。";
    let variants = [
        "说话人3：这个阶段里我们每月复核10到20件。已复核160多件。",
        "说话人2：如果继续协作，这个阶段里我们每月复核10到20件。已复核160多件。",
        "说话人2：这个阶段里我们每月复核10到20件。已复核220多件。",
        "说话人2：这个阶段里我们每月交付10到20件。已复核160多件。",
        "说话人2：这个阶段里我们每月复核10到20件，这个阶段里我们每月复核30到40件。已复核160多件。",
        "说话人2：这个阶段里我们每月复核10到20件？已复核160多件。",
        "说话人2：无关讨论。\n没有明确说话人。\n说话人2：这个阶段里我们每月复核10到20件。已复核160多件。",
    ];
    for suffix in variants {
        let source = session(&format!("{prefix}\n{suffix}"));
        let (mut minutes, _) = response(&source);
        minutes.summary = vec!["已复核160多件。".into()];
        let mut evidence = vec![Evidence {field: "summary".into(), index: 0, quote: "复核流程上线".into()}];
        summary_coverage::restore(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
        assert_eq!(minutes.summary[0], "已复核160多件。", "{suffix}");
        assert_eq!(evidence.len(), 1);
    }
}

#[test]
fn chapter_coverage_keeps_a_cited_limit_with_its_scope_and_activity() {
    let quote = "我们学校只有这个安排。因为确实小学，在线课程就三节课，所以主科在线上，其他科目做居家锻炼记录。";
    let source = session(&format!("说话人2：{quote}"));
    for (body, expected) in [
        ("学校说明了主科线上和居家锻炼记录。", true),
        ("学校说明采购安排已完成。", false),
        ("学校小学线上就排三节课，其他科目做居家锻炼记录。", false),
    ] {
        let (mut minutes, _) = response(&source);
        minutes.summary = vec![body.into()];
        let mut evidence = vec![Evidence {field: "summary".into(), index: 0, quote: quote.into()}];
        summary_coverage::restore(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
        if expected {
            assert_eq!(minutes.summary[0], format!("{body}补充原话「小学，在线课程就三节课」。"));
            assert_eq!(evidence[1].quote, "小学，在线课程就三节课");
        } else {
            assert_eq!(minutes.summary[0], body);
        }
    }
    let clipped = "小学，在线课程就三节课，所以在家记录锻炼过程。";
    let source = session(&format!("说话人2：假设学校下周改个方案，{clipped}"));
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["在家记录锻炼过程。".into()];
    let mut evidence = vec![Evidence {field: "summary".into(), index: 0, quote: clipped.into()}];
    summary_coverage::restore(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
    assert_eq!(minutes.summary[0], "在家记录锻炼过程。");
}

#[test]
fn chapter_relations_adds_a_negative_outcome_to_its_original_condition() {
    let first = "先确定如何呈现人物和世界观";
    let source = session(&format!(
        "说话人2：{first}。\n说话人2：如果读者对人物无感，那么世界观设定再漂亮也没有用。"
    ));
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["世界观设定要能承载人物。".into()];
    let mut evidence = vec![Evidence {field:"summary".into(),index:0,quote:first.into()}];
    let range = 0..source.transcript_text.len();
    summary_relations::restore(&source, range.clone(), &mut minutes, &mut evidence);
    assert_eq!(minutes.summary[0],
        "世界观设定要能承载人物。补充条件原话「如果读者对人物无感，那么世界观设定再漂亮也没有用」。");
    assert_eq!(evidence[1].quote, "如果读者对人物无感，那么世界观设定再漂亮也没有用");
    summary_relations::restore(&source, range, &mut minutes, &mut evidence);
    assert_eq!(evidence.len(), 2);
    assert!(minutes.action_items.is_empty() && minutes.decisions.is_empty());
}

#[test]
fn chapter_relations_retains_an_exception_and_its_changed_interpretation() {
    let first = "先谈常规的设计范围";
    let source = session(&format!(
        "说话人2：{first}。\n说话人2：它可以超过标准范围，比如另一个方案，不过用户的预期会变化，就会把它看作临时安排，所以要标明用途。"
    ));
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["超过标准范围会改变用户预期。".into()];
    let mut evidence = vec![Evidence {field:"summary".into(),index:0,quote:first.into()}];
    summary_relations::restore(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
    assert_eq!(minutes.summary[0],
        "超过标准范围会改变用户预期。补充条件原话「可以超过标准范围」、「用户的预期会变化，就会把它看作临时安排」。");
    assert_eq!(evidence[1].quote, "可以超过标准范围");
    assert_eq!(evidence[2].quote, "用户的预期会变化，就会把它看作临时安排");
}

#[test]
fn chapter_relations_keeps_explicit_requirements_for_a_future_outcome() {
    let first = "人工审查仍需要经验和判断";
    let related = "拐点应该是在识别技术高度成熟之后，只有当平台能识别情绪才可以让机器替代人工审查";
    let source = session(&format!("说话人2：{first}。\n说话人2：{related}但是还要考虑风险。"));
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["人工审查很难被机器取代。".into()];
    let mut evidence = vec![Evidence {field:"summary".into(),index:0,quote:first.into()}];
    summary_relations::restore(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
    assert_eq!(minutes.summary[0], format!("人工审查很难被机器取代。补充条件原话「{related}」。"));
    assert_eq!(evidence[1].quote, related);
}

#[test]
fn chapter_relations_skips_questions_duplicate_sources_other_speakers_and_covered_claims() {
    let quote = "先谈如何呈现人物和世界观";
    let simple = "世界观设定要能承载人物。";
    let cases = [
        (format!("说话人2：{quote}。\n说话人3：如果读者对人物无感，那么世界观设定再漂亮也没有用。"), simple),
        (format!("说话人2：{quote}。\n说话人2：如果读者对人物无感，那么世界观设定再漂亮也没有用？"), simple),
        (format!("说话人2：{quote}。\n说话人2：如果需要更换材料，那么大号的插座不能混用。"), simple),
        (format!("说话人2：{quote}。\n说话人2：如果读者对人物无感，那么世界观设定再漂亮也没有用。\n说话人4：{quote}。"), simple),
        (format!("说话人2：{quote}。\n说话人2：如果读者对人物无感，那么世界观设定再漂亮也没有用。"),
        "人物不能打动读者时，世界观设定再漂亮也无效。"),
    ];
    for (text, body) in cases {
        let source = session(&text);
        let (mut minutes, _) = response(&source);
        minutes.summary = vec![body.into()];
        let mut evidence = vec![Evidence {field:"summary".into(),index:0,quote:quote.into()}];
        summary_relations::restore(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
        assert_eq!(minutes.summary[0], body);
        assert_eq!(evidence.len(), 1);
    }
}

#[test]
fn chapter_roles_preserves_both_dimensions_from_one_speaker_in_a_mixed_summary() {
    let first = "个人长期负责复核更稳定";
    let second = "团队轮班可以尽快处理";
    let source = session(&format!(
        "说话人1：分享另一个方案。\n说话人3：从连续性来说，{first}。从速度来说，{second}，整体响应更快。"
    ));
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["比较了连续性和速度。".into()];
    let mut evidence = [first, second, "分享另一个方案"].into_iter().map(|quote| Evidence {
        field:"summary".into(), index:0, quote:quote.into(),
    }).collect();
    let range = 0..source.transcript_text.len();
    summary_roles::restore(&source, range.clone(), &mut minutes, &mut evidence);
    assert_eq!(minutes.summary[0],
        "比较了连续性和速度。补充对比原话「从连续性来说」「个人长期负责复核更稳定」。另一侧原话「从速度来说」「团队轮班可以尽快处理」「整体响应更快」。");
    assert_eq!(evidence.len(), 6);
    summary_roles::restore(&source, range, &mut minutes, &mut evidence);
    assert_eq!(evidence.len(), 6);
}

#[test]
fn chapter_roles_will_not_join_unrelated_or_already_captured_comparisons() {
    for (source, summary) in [
        ("说话人1：从连续性来说，个人长期负责复核更稳定。\n说话人2：从速度来说，团队轮班更快。","比较了连续性和速度。"),
        ("说话人1：从连续性来说，个人长期负责复核更稳定。从速度来说，团队轮班更快。","个人负责的连续性更好，团队轮班的速度更快。"),
        ("说话人1：从连续性来说，个人长期负责复核更稳定。从速度来说，团队轮班更快。从密度来看，还有其他因素。","比较了连续性和速度。"),
        ("说话人1：从连续性来说，个人长期负责复核更稳定。从速度来说，个人临时加班更快。","比较了连续性和速度。"),
    ] {
        let source = session(source);
        let (mut minutes, _) = response(&source);
        minutes.summary = vec![summary.into()];
        let mut evidence = ["长期负责复核", "更快"].into_iter().map(|quote| Evidence {
            field:"summary".into(), index:0, quote:quote.into(),
        }).collect();
        summary_roles::restore(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
        assert_eq!(minutes.summary[0], summary);
        assert_eq!(evidence.len(), 2);
    }
}

#[test]
fn chapter_roles_keeps_the_time_and_each_actor_in_a_reported_handoff() {
    let anchor = "周会说明了工作要求";
    let spoken = "由品控组把这批物料的抽检要求收集好，然后提前两天让运营组发给各班负责人，由负责人一次性把它转给各个车间";
    let source = session(&format!("说话人2：{anchor}。\n说话人2：各项检测前后要注意抽样。\n说话人2：先把所有抽检要求落实到纸面。\n说话人2：所有抽检要求统一用纸面传达，{spoken}。"));
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["所有抽检要求统一用纸面传达。".into()];
    let mut evidence = vec![Evidence {field:"summary".into(),index:0,quote:anchor.into()}];
    summary_roles::restore(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
    assert_eq!(minutes.summary[0], format!("所有抽检要求统一用纸面传达。补充分发原话「{spoken}」。"));
    assert_eq!(evidence[1].quote, spoken);
    assert!(minutes.action_items.is_empty() && minutes.decisions.is_empty());
}

#[test]
fn chapter_roles_skips_inferred_handoffs_and_other_speakers() {
    let anchor = "周会说明了工作要求";
    let handoff = "所有抽检要求统一用纸面传达，由品控组把这批物料的抽检要求收集好，然后提前两天让运营组发给各班负责人，由负责人一次性把它转给各个车间。";
    let variants = [
        format!("说话人2：{anchor}。\n说话人3：{handoff}"),
        format!("说话人2：{anchor}。\n说话人2：{}", handoff.replace("提前两天", "")),
        format!("说话人2：{anchor}。\n说话人2：{}", handoff.replace("由负责人", "由行政经理")),
        format!("说话人2：{anchor}。\n说话人2：假设一些零件返工，{handoff}"),
    ];
    for text in variants {
        let source = session(&text);
        let (mut minutes, _) = response(&source);
        let body = "所有抽检要求统一用纸面传达。";
        minutes.summary = vec![body.into()];
        let mut evidence = vec![Evidence {field:"summary".into(),index:0,quote:anchor.into()}];
        summary_roles::restore(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
        assert_eq!(minutes.summary[0], body, "{text}");
        assert_eq!(evidence.len(), 1);
    }
}

#[test]
fn chapter_stance_retains_an_intention_separately_from_a_period_description() {
    let anchor = "先学习合作机构的做法，开展共享资料评估";
    let plan = "就想把外部经验和本组流程整合起来，建立一套可检索的工具";
    let stage = "资料归档管理就是这个阶段";
    let source = session(&format!(
        "说话人2：{anchor}。\n说话人2：参考合作机构分享的资料评估结果，{plan}。{stage}。"
    ));
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["学习合作机构的做法，开展共享资料评估。".into()];
    let mut evidence = vec![Evidence {field:"summary".into(),index:0,quote:anchor.into()}];
    let range = 0..source.transcript_text.len();
    summary_stance::restore(&source, range.clone(), &mut minutes, &mut evidence);
    assert_eq!(minutes.summary[0], format!("学习合作机构的做法，开展共享资料评估。补充设想原话「{plan}」。相关阶段原话「{stage}」。"));
    assert_eq!(evidence[1].quote, plan);
    assert_eq!(evidence[2].quote, stage);
    assert!(minutes.action_items.is_empty() && minutes.decisions.is_empty());
    summary_stance::restore(&source, range, &mut minutes, &mut evidence);
    assert_eq!(evidence.len(), 3);
}

#[test]
fn chapter_stance_does_not_restore_an_unmatched_canceled_or_unrelated_intention() {
    let anchor = "先学习合作机构的做法，开展共享资料评估";
    let related = "参考合作机构分享的资料评估结果，";
    let plan = "就想把外部经验和本组流程整合起来，建立一套可检索的工具。资料归档管理就是这个阶段";
    let cases = [
        format!("说话人2：{anchor}。\n说话人3：{related}{plan}。"),
        format!("说话人2：{anchor}。\n说话人2：{related}{plan}。\n说话人2：后来放弃这个想法。"),
        format!("说话人2：{anchor}。\n说话人2：{related}是不是{plan}？"),
        format!("说话人2：{anchor}。\n说话人2：{related}{}", plan.replace("就想把", "已经把")),
        format!("说话人2：{anchor}。\n说话人2：{related}{plan}。\n说话人3：另一个小组介绍资料评估。"),
        format!("说话人2：{anchor}。\n说话人2：接下来讨论展会的设计。{plan}。"),
    ];
    for (index, transcript) in cases.into_iter().enumerate() {
        let source = session(&transcript);
        let (mut minutes, _) = response(&source);
        let summary = "学习合作机构的做法，开展共享资料评估。";
        minutes.summary = vec![summary.into()];
        let mut evidence = vec![Evidence {field:"summary".into(),index:0,quote:anchor.into()}];
        if index == 4 {
            evidence.push(Evidence {field:"summary".into(),index:0,quote:"另一个小组介绍资料评估。".into()});
        }
        let initial = evidence.len();
        summary_stance::restore(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
        assert_eq!(minutes.summary[0], summary, "{transcript}");
        assert_eq!(evidence.len(), initial);
    }
}

#[test]
fn chapter_stance_leaves_an_uncertain_explanation_in_source_evidence() {
    let anchor = "这里的客观规律特别重要";
    let observation = "展览里的不同参与者采用了各式各样的解决办法";
    let dialogue = format!(
        "因为你看看{observation}。那么这类变化据原话是一万年的时候虚拟拓找出来的。所以我认为这种客观规律是值得讨论的创新模式"
    );
    let source = session(&format!("说话人2：{anchor}。{dialogue}。\n说话人3：接着谈展览安排。"));
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["某位嘉宾看重客观规律，并讨论展览安排。".into()];
    let mut evidence = vec![
        Evidence {field:"summary".into(),index:0,quote:anchor.into()},
        Evidence {field:"summary".into(),index:0,quote:"接着谈展览安排。".into()},
    ];
    summary_stance::restore(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
    assert_eq!(minutes.summary[0], format!("某位嘉宾看重客观规律，并讨论展览安排。补充观察原话「{observation}」。发言者观点「所以我认为这种客观规律是值得讨论的创新模式」。中间论述待核对。"));
    assert_eq!(evidence[2].quote, dialogue);
    assert!(!minutes.summary[0].contains("一万年"));
    assert!(minutes.action_items.is_empty() && minutes.decisions.is_empty());
}

#[test]
fn chapter_stance_skips_already_represented_and_unrelated_viewpoints() {
    let anchor = "这里的客观规律特别重要";
    let reasoning = "因为周围很多人在实际做事时采用了各式各样的解决办法。那么这类变化在三年的时候发生。所以我认为这种客观规律是值得讨论的创新模式。";
    let rows = [
        (format!("说话人2：{anchor}。{reasoning}"), "嘉宾认为客观规律是创新模式。"),
        (format!("说话人2：{anchor}。{reasoning}"), "嘉宾讨论明年的人员配置。"),
        (format!("说话人2：{anchor}。\n说话人3：{reasoning}"), "嘉宾认为客观规律重要。"),
    ];
    for (transcript, summary) in rows {
        let source = session(&transcript);
        let (mut minutes, _) = response(&source);
        minutes.summary = vec![summary.into()];
        let mut evidence = vec![Evidence {field:"summary".into(),index:0,quote:anchor.into()}];
        summary_stance::restore(&source, 0..source.transcript_text.len(), &mut minutes, &mut evidence);
        assert_eq!(minutes.summary[0], summary);
    }
}

#[test]
fn context_merge_retains_unverified_drafts_and_source_evidence() {
    let original="# 旧分段汇总\n\n## 未核对的参考草稿\n\n可能需要寄样品\n\n## 分段原文依据\n\n样品待确认";
    let retained=reference_sections(original);
    assert!(!retained.contains("旧分段汇总"));
    assert!(retained.contains("未核对的参考草稿"));
    assert!(retained.contains("可能需要寄样品"));
    assert!(retained.contains("分段原文依据"));
    assert_eq!(reference_sections("只剩原始草稿"),"只剩原始草稿");
}

#[test]
fn long_context_reconciles_later_cancellation_and_keeps_separate_sources() {
    use std::{io::{Read,Write}, net::TcpListener, sync::{Arc,Mutex,atomic::{AtomicBool,Ordering}}, thread};
    let dir=root();fs::create_dir_all(&dir).unwrap();
    std::env::set_var("COMPANION_TYPE_STATE_PATH",dir.join("state.json"));
    let listener=TcpListener::bind("127.0.0.1:0").unwrap();let address=listener.local_addr().unwrap();
    listener.set_nonblocking(true).unwrap();
    let stop=Arc::new(AtomicBool::new(false));let seen=Arc::new(Mutex::new(Vec::<String>::new()));
    let worker_stop=stop.clone();let worker_seen=seen.clone();
    let worker=thread::spawn(move || {
        while !worker_stop.load(Ordering::SeqCst) {
            let (mut stream,_)=match listener.accept() {Ok(v)=>v,Err(e) if e.kind()==std::io::ErrorKind::WouldBlock=>{thread::sleep(Duration::from_millis(10));continue},Err(e)=>panic!("{e}")};
            stream.set_nonblocking(false).unwrap();
            stream.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
            let mut data=Vec::new();let mut buf=[0u8;4096];
            loop {let n=stream.read(&mut buf).unwrap();if n==0{break}data.extend_from_slice(&buf[..n]);
                if let Some(i)=data.windows(4).position(|w|w==b"\r\n\r\n") {
                    let h=String::from_utf8_lossy(&data[..i]);let len:usize=h.lines().find_map(|l|l.split_once(':')
                        .filter(|(k,_)|k.eq_ignore_ascii_case("content-length")).and_then(|(_,v)|v.trim().parse().ok())).unwrap();
                    if data.len()>=i+4+len {break}
                }}
            let start=data.windows(4).position(|w|w==b"\r\n\r\n").unwrap()+4;
            let request:Value=serde_json::from_slice(&data[start..]).unwrap();
            let prompt=request["messages"][1]["content"].as_str().unwrap().to_string();
            worker_seen.lock().unwrap().push(prompt.clone());
            let reconciles=prompt.contains("请综合下列全部分段结果");
            let quote=if prompt.contains("小王周五发送报价") {"小王周五发送报价"} else {"取消发送报价"};
            let answer=if reconciles {serde_json::json!({"summary":["报价已取消"],"decisions":["取消发送报价"],"actionItems":[],"questions":[],"keywords":[],"markdown":"# 当前纪要"})}
              else {serde_json::json!({"summary":[quote],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"# 分段","evidence":[{"field":"summary","index":0,"quote":quote}]})};
            let payload=serde_json::json!({"choices":[{"finish_reason":"stop","message":{"content":answer.to_string()}}]}).to_string();
            write!(stream,"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}",payload.len(),payload).unwrap();
        }
    });
    let mut s=session(&"小王周五发送报价。".repeat(1300));s.duration_ms=7_200_000;s.note_revision=1;
    s.meeting_notes.push(super::super::super::meeting_notes::Note{kind:Default::default(),references:vec![],id:"n".into(),text:"取消发送报价".into(),bookmark_id:None,image:None,created_at:"now".into(),updated_at:"now".into()});
    let original=s.transcript_text.clone();let endpoint=format!("http://{address}/chat/completions");
    let client=reqwest::blocking::Client::builder().no_proxy().timeout(Duration::from_secs(5)).build().unwrap();
    assert!(super::super::super::minutes_context::validate(&s,1).is_ok());
    let result=run_with_context(&endpoint,"fixture","key",&s,"now",&client,None).unwrap();
    assert_eq!(result.quality,"final");assert!(result.processing.as_ref().unwrap().is_complete());
    assert!(result.summary.iter().any(|s|s.contains("已取消")));assert!(result.action_items.is_empty());
    assert!(result.markdown.contains("用户补充依据"));assert_eq!(s.transcript_text,original);
    let requests=seen.lock().unwrap().clone();assert!(requests.iter().filter(|p|p.contains("第1段")).count()>=1);
    assert!(requests.iter().any(|p|p.contains("用户明确选择的补充")));
    assert!(requests.iter().any(|p|p.contains("请综合下列全部分段结果") && p.contains("取消发送报价")));
    let original_id=Identity::new(&endpoint,"fixture","key",&session(&original));
    let with_context=Identity::new(&endpoint,"fixture","key",&s);assert_ne!(original_id.filename(),with_context.filename());
    stop.store(true,Ordering::SeqCst);worker.join().unwrap();std::env::remove_var("COMPANION_TYPE_STATE_PATH");cleanup(dir);
}

#[test]
fn unverified_chapter_remains_visible_without_becoming_an_action_or_complete() {
    let source=session("公开会议内容。");
    let mut checkpoint=Checkpoint {identity:Identity::new("https://fixture.invalid","model","key",&source),chapters:vec![None]};
    let (mut draft,evidence)=response(&source);
    draft.summary=vec!["讨论产品包装".into()];
    draft.action_items=vec![crate::companion_v1::CompanionV1ActionItem {
        text:"发送报价".into(),owner:Some("小王".into()),due:Some("周五".into()) }];
    let mut partial=assemble(&source,&checkpoint,0,"now",Some("缺少原文引用".into()));
    append_unverified_chapters(&mut partial,&checkpoint,&[Some(draft.clone())], &[vec![]], &[(0,source.transcript_text.len())], &source.transcript_text);
    assert_eq!(partial.quality,"draft");assert!(!partial.processing.as_ref().unwrap().is_complete());
    assert!(partial.action_items.is_empty());assert!(partial.summary.is_empty());
    assert!(partial.markdown.contains("未核对的参考草稿"));assert!(partial.markdown.contains("讨论产品包装"));
    assert!(partial.markdown.contains("可能的行动：发送报价"));assert!(partial.markdown.contains("可能的负责人：小王"));
    assert!(partial.markdown.find("未核对的参考草稿").unwrap()<partial.markdown.find("分段原文依据").unwrap());
    let (verified,evidence)={let (m,_)=response(&source);(m,evidence)};
    let result_hash=chapter_digest(&verified,&evidence,0);
    checkpoint.chapters[0]=Some(Chapter{start:0,end:source.transcript_text.len(),source_hash:hash(source.transcript_text.as_bytes()),minutes:verified,evidence,omitted_items:0,result_hash});
    let mut partial_draft=draft.clone();
    partial_draft.summary.insert(0,"已经核对的内容".into());
    let cited=vec![Evidence {field:"summary".into(),index:0,quote:"公开会议内容".into()}];
    checkpoint.chapters[0].as_mut().unwrap().omitted_items=2;
    let mut partially_verified=assemble(&source,&checkpoint,0,"now",None);
    append_unverified_chapters(&mut partially_verified,&checkpoint,&[Some(partial_draft)], &[cited], &[(0,source.transcript_text.len())], &source.transcript_text);
    let section=partially_verified.markdown.split("## 未核对的参考草稿").nth(1).unwrap();
    assert!(section.contains("讨论产品包装"));
    assert!(section.contains("可能的行动：发送报价"));
    assert!(!section.contains("已经核对的内容"));
    assert!(partially_verified.action_items.is_empty());
    checkpoint.chapters[0].as_mut().unwrap().omitted_items=0;
    let mut complete=assemble(&source,&checkpoint,0,"now",None);
    let verified=checkpoint.chapters[0].as_ref().unwrap();
    append_unverified_chapters(&mut complete,&checkpoint,&[Some(verified.minutes.clone())], &[verified.evidence.clone()], &[(0,source.transcript_text.len())], &source.transcript_text);
    assert!(!complete.markdown.contains("未核对的参考草稿"));
}

#[test]
fn earlier_reference_survives_retry_without_duplicating_verified_items() {
    let source=session("公开会议内容。");let checkpoint=Checkpoint {identity:Identity::new("https://fixture.invalid","model","key",&source),chapters:vec![None]};
    let mut result=assemble(&source,&checkpoint,0,"now",Some("服务失败".into()));
    result.summary.push("已经核对".into());
    let previous="## 未核对的参考草稿\n\n> 供核对\n\n### 第1段\n\n- 讨论：已经核对\n- 讨论：旧的讨论\n- 可能的行动：发送报价（可能的负责人：小王）（可能的时间：周五）\n\n## 分段原文依据\n\n来源";
    append_previous_reference(&mut result,previous);
    assert!(result.markdown.contains("- 讨论：旧的讨论"));
    assert!(result.markdown.contains("- 可能的行动：发送报价（可能的负责人：小王）（可能的时间：周五）"));
    assert!(!result.markdown.contains("- 讨论：已经核对"));
    assert!(result.action_items.is_empty());
    let once=result.markdown.clone();append_previous_reference(&mut result,previous);assert_eq!(result.markdown,once);
}

#[test]
fn reference_cache_uses_existing_erasable_format_and_never_recreates_deleted_session() {
    let root=root();fs::create_dir_all(&root).unwrap();
    let source=session("公开会议内容。");
    let identity=Identity::new("https://fixture.invalid","model","key",&source);
    let checkpoint=Checkpoint {identity:identity.clone(),chapters:vec![None]};
    save_checkpoint(&root.join(identity.filename()),&checkpoint).unwrap();
    let (mut draft,_)=response(&source);draft.summary=vec!["尚待核对".into()];
    let mut result=assemble(&source,&checkpoint,0,"now",Some("缺少引用".into()));
    append_cached_unverified(&root,&identity,&mut result,&[Some(draft.clone())],&[vec![]],&[(0,source.transcript_text.len())],&source.transcript_text);
    assert!(result.markdown.contains("尚待核对"));
    let cache_files=fs::read_dir(&root).unwrap().filter_map(Result::ok).map(|e|e.path())
        .filter(|p|p.extension().is_some_and(|s|s=="json")).collect::<Vec<_>>();
    assert_eq!(cache_files.len(),2);
    assert!(cache_files.iter().all(|p|read_checkpoint(p).is_ok()));
    assert_eq!(erase(&root,&[source.id.clone()],false).unwrap(),(2,0));
    append_cached_unverified(&root,&identity,&mut result,&[Some(draft)],&[vec![]],&[(0,source.transcript_text.len())],&source.transcript_text);
    assert_eq!(fs::read_dir(&root).unwrap().filter_map(Result::ok).filter(|e|e.path().extension().is_some_and(|s|s=="json")).count(),0);
    cleanup(root);
}

#[test]
fn template_changes_isolate_long_meeting_cache_without_invalidating_default() {
    let source=session("明天下午讨论包装，周五发报价。");
    let meeting=crate::companion_v1::MinutesTemplate{id:"meeting".into(),name:String::new(),instructions:String::new()}.normalized().unwrap();
    let interview=crate::companion_v1::MinutesTemplate{id:"interview".into(),name:String::new(),instructions:String::new()}.normalized().unwrap();
    let default=Identity::new("https://fixture.invalid","model","key",&source);
    assert_eq!(default.filename(),Identity::new_with_template("https://fixture.invalid","model","key",&source,None).filename());
    let a=Identity::new_with_template("https://fixture.invalid","model","key",&source,Some(&meeting));
    let b=Identity::new_with_template("https://fixture.invalid","model","key",&source,Some(&interview));
    assert_ne!(a.filename(),b.filename());assert_ne!(a.filename(),default.filename());
    assert_eq!(a.source_hash,b.source_hash,"all views refer to the same original transcript");
}

#[test]
fn computer_capture_prompt_invalidates_only_its_own_chapter_cache() {
    let source=session("【麦克风】小李寄样品。\n【电脑声音】小王整理报价。");
    let endpoint="https://fixture.invalid";let model="model";let key="private";
    let regular=Identity::new(endpoint,model,key,&source);
    let old_profile=serde_json::to_vec(&(endpoint,model,key,super::super::DEEPSEEK_SYSTEM_PROMPT,
        EVIDENCE_PROMPT,EVIDENCE_REVISION,MAX_PROMPT_BYTES,MAX_OUTPUT_TOKENS,CHUNK_BYTES)).unwrap();
    assert_eq!(regular.profile_hash,hash(&old_profile));
    let mut computer=source.clone();computer.source="hostMeeting".into();
    let dual=Identity::new(endpoint,model,key,&computer);
    assert_ne!(dual.profile_hash,regular.profile_hash);
    assert_ne!(dual.filename(),regular.filename());
    assert_eq!(dual.source_hash,regular.source_hash);
}

#[test]
fn regenerated_chapter_keeps_previous_questions_actions_and_quotes() {
    let text="小王周五发报价。监管如何？额度如何？";
    let part=session(text);let (mut old,mut old_evidence)=response(&part);
    old.summary=vec!["原摘要".into()];old.questions=vec!["监管如何？".into()];
    old.action_items=vec![crate::companion_v1::CompanionV1ActionItem{text:"发报价".into(),owner:Some("小王".into()),due:Some("周五".into())}];
    old_evidence.clear();old_evidence.extend([
        Evidence{field:"summary".into(),index:0,quote:"小王周五发报价".into()},
        Evidence{field:"questions".into(),index:0,quote:"监管如何".into()},
        Evidence{field:"actionItems".into(),index:0,quote:"小王周五发报价".into()},
    ]);
    let mut newer=old.clone();newer.summary=vec!["新摘要".into()];newer.questions=vec!["额度如何？".into()];newer.action_items.clear();
    let new_evidence=vec![Evidence{field:"summary".into(),index:0,quote:"额度如何".into()},Evidence{field:"questions".into(),index:0,quote:"额度如何".into()}];
    let previous=Chapter{start:0,end:text.len(),source_hash:hash(text.as_bytes()),minutes:old,evidence:old_evidence,omitted_items:1,result_hash:String::new()};
    let mut candidate=Chapter{start:0,end:text.len(),source_hash:hash(text.as_bytes()),minutes:newer,evidence:new_evidence,omitted_items:0,result_hash:String::new()};
    merge_previous_chapter(&previous,&mut candidate,text).unwrap();
    assert!(candidate.minutes.summary.contains(&"原摘要".into()));
    assert!(candidate.minutes.questions.contains(&"监管如何？".into()));
    assert!(candidate.minutes.questions.contains(&"额度如何？".into()));
    assert_eq!(candidate.minutes.action_items.len(),1);
    assert_eq!(candidate.minutes.action_items[0].owner.as_deref(),Some("小王"));
    assert_eq!(candidate.minutes.action_items[0].due.as_deref(),Some("周五"));
    assert!(candidate.evidence.iter().any(|e|e.field=="questions"&&e.quote=="监管如何"));
    assert!(is_current(&candidate,0,text.len(),text));
}

#[test]
#[ignore = "checks previously authorized real chapter results without a cloud call"]
fn replay_real_regenerated_chapters_preserves_all_prior_items() {
    let previous=read_checkpoint(Path::new(&std::env::var_os("COMPANION_PRIOR_MINUTES_CHECKPOINT").unwrap())).unwrap();
    let newer=read_checkpoint(Path::new(&std::env::var_os("COMPANION_NEW_MINUTES_CHECKPOINT").unwrap())).unwrap();
    let source=fs::read_to_string(std::env::var_os("COMPANION_MINUTES_SOURCE").unwrap()).unwrap();
    for index in [1usize,3] {
        let old=previous.chapters[index].as_ref().unwrap();let mut candidate=newer.chapters[index].clone().unwrap();
        let chunk=&source[old.start..old.end];merge_previous_chapter(old,&mut candidate,chunk).unwrap();
        for item in &old.minutes.summary {assert!(candidate.minutes.summary.contains(item));}
        for item in &old.minutes.decisions {assert!(candidate.minutes.decisions.contains(item));}
        for item in &old.minutes.questions {assert!(candidate.minutes.questions.contains(item));}
        for item in &old.minutes.action_items {assert!(candidate.minutes.action_items.iter().any(|v|v.text==item.text&&v.owner==item.owner&&v.due==item.due));}
        assert!(is_current(&candidate,old.start,old.end,chunk));
        if index==3 {assert!(candidate.minutes.questions.len()>=4);}
    }
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
fn explicit_conditional_assignment_is_recovered_from_a_cached_chapter() {
    let text="会议讨论报价。\n如果客户提出修改，王芳负责下周一确认产品交货时间。\n假如样品不合格，由李明负责整理问题清单。\n如果客户提出疑问，王芳负责吗？\n如果时间允许，我们负责讨论。\n如果订单更改，之前王芳负责处理。\n如果方案不行，建议王芳负责调整。";
    let part=session(text); let (minutes,evidence)=response(&part);
    let mut chapter=Chapter {start:0,end:text.len(),source_hash:hash(text.as_bytes()),
        result_hash:chapter_digest(&minutes,&evidence,0),minutes,evidence,omitted_items:0};
    assert!(is_current(&chapter,0,text.len(),text));
    let original_summary=chapter.minutes.summary.clone();
    repair_cached_chapter(&mut chapter,&part);
    assert_eq!(chapter.minutes.summary,original_summary);
    assert_eq!(chapter.minutes.action_items.len(),2);
    for (owner,condition) in [("王芳","如果客户提出修改"),("李明","假如样品不合格")] {
        let action=chapter.minutes.action_items.iter().find(|a|a.owner.as_deref()==Some(owner)).unwrap();
        assert!(action.text.contains(condition)); assert!(action.due.is_none());
    }
    assert!(is_current(&chapter,0,text.len(),text));
    let first=chapter.result_hash.clone();
    repair_cached_chapter(&mut chapter,&part);
    assert_eq!(chapter.result_hash,first);
    assert!(is_current(&chapter,0,text.len(),text));
}

#[test]
fn conditional_time_is_not_a_responsible_person_even_in_cached_results() {
    let text="会议讨论报价。\n如果客户修改，下周一负责确认交货时间。\n假如预算通过，明天上午负责发报价。\n如果收到样品，周一鸣负责检查包装。";
    let part=session(text);let (mut minutes,mut evidence)=response(&part);
    minutes.action_items.push(crate::companion_v1::CompanionV1ActionItem {
        text:"如果客户修改，下周一负责确认交货时间".into(),owner:Some("下周一".into()),due:None });
    evidence.push(Evidence {field:"actionItems".into(),index:0,quote:"如果客户修改，下周一负责确认交货时间".into()});
    let mut chapter=Chapter {start:0,end:text.len(),source_hash:hash(text.as_bytes()),
        result_hash:chapter_digest(&minutes,&evidence,0),minutes,evidence,omitted_items:0};
    assert!(is_current(&chapter,0,text.len(),text));repair_cached_chapter(&mut chapter,&part);
    assert_eq!(chapter.minutes.action_items.len(),3);
    for phrase in ["下周一负责确认交货时间","明天上午负责发报价"] {
        let action=chapter.minutes.action_items.iter().find(|a|a.text.contains(phrase)).unwrap();
        assert!(action.owner.is_none());assert!(action.due.is_none());assert!(action.text.contains('如'));
    }
    assert_eq!(chapter.minutes.action_items.iter().find(|a|a.text.contains("周一鸣负责")).unwrap().owner.as_deref(),Some("周一鸣"));
    assert!(is_current(&chapter,0,text.len(),text));let digest=chapter.result_hash.clone();
    repair_cached_chapter(&mut chapter,&part);assert_eq!(chapter.result_hash,digest);
}

#[test]
#[ignore = "reuses the previously saved public and fictional meeting; no network"]
fn replay_saved_provider_chapters_repairs_conditional_assignment_without_resending() {
    let sessions: Vec<CompanionV1HostSession> = serde_json::from_slice(
        &fs::read(std::env::var_os("COMPANION_REPLAY_SESSIONS").unwrap()).unwrap()).unwrap();
    let original=&sessions[0];
    let source=crate::backend::transcript_review::minutes_input(original);
    let mut checkpoint=read_checkpoint(Path::new(&std::env::var_os("COMPANION_REPLAY_CHECKPOINT").unwrap())).unwrap();
    let root=root();fs::create_dir_all(&root).unwrap();
    let identity=Identity::new("https://fixture.invalid","replay","test",&source);
    let count=checkpoint.chapters.len();checkpoint.identity=identity;
    let path=root.join(checkpoint.identity.filename());save_checkpoint(&path,&checkpoint).unwrap();
    let result=run_with(&root,"https://fixture.invalid","replay","test",&source,"replay",|_,_,_,_| {
        panic!("saved valid provider chapters must not be resent")
    }).unwrap();
    assert_eq!(result.processing.as_ref().unwrap().resumed_chunks,count);
    let action=result.action_items.iter().find(|a|a.text.contains("王芳")&&a.text.contains("交货时间")).unwrap();
    assert!(action.text.contains("如果客户提出修改"));assert_eq!(action.owner.as_deref(),Some("王芳"));
    assert!(action.due.is_none());
    assert!(result.action_items.iter().any(|a|a.text.contains("李明")&&a.text.contains("报价")));
    assert!(result.action_items.iter().any(|a|a.owner.as_deref()==Some("赵强")&&a.text.contains("风险清单")));
    assert!(original.transcript_review.is_some());cleanup(root);
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
fn unsupported_source_quotes_retry_then_defer_without_losing_completed_chapters() {
    let root=root();let text="公开会议内容用于分段整理。\n".repeat(5000);let source=session(&text);
    let total=plan(&text).unwrap().len();assert!(total>3);
    let mut calls=Vec::new();let mut invalid=0;
    let result=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|index,_,part,_| {
        calls.push(index);let (minutes,mut evidence)=response(part);
        if index==2 && invalid<2 {invalid+=1;for item in &mut evidence {item.quote="不在原文的引用".into();}}
        Ok((minutes,evidence))
    }).unwrap();
    let mut expected=vec![0,1,2,2];expected.extend(3..total);expected.push(2);
    assert_eq!(calls,expected);assert_eq!(invalid,2);
    assert!(result.processing.unwrap().is_complete());assert_eq!(source.transcript_text,text);
    cleanup(root);
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
fn long_exact_quote_is_retained_and_fabricated_quote_is_dropped() {
    let quote="真实会议内容".repeat(220);assert!(quote.len()>1024);
    let source=session(&quote);let root=root();
    let result=run_with(&root,"https://fixture.invalid","model","key",&source,"now",|_,_,p,_| {
        let (mut m,_)=response(p);m.summary=vec!["真实讨论".into(),"不存在的内容".into()];
        Ok((m,vec![Evidence{field:"summary".into(),index:0,quote:quote.clone()},Evidence{field:"summary".into(),index:1,quote:"不存在的原话".into()}]))
    }).unwrap();
    assert!(result.summary.contains(&"真实讨论".into()));assert!(!result.summary.contains(&"不存在的内容".into()));
    assert!(result.markdown.contains("有1条内容无法对应原文"));cleanup(root);
}

#[test]
fn long_conditional_quote_never_becomes_unconditional_deadline() {
    let quote=format!("{}周五发报价", "会议讨论".repeat(150));assert!(quote.len()>1024);
    let text=format!("如果客户同意，{quote}");let source=session(&text);let (mut m,_)=response(&source);
    m.action_items=vec![crate::companion_v1::CompanionV1ActionItem{text:"周五发报价".into(),owner:None,due:Some("周五".into())}];
    let mut evidence=vec![Evidence{field:"actionItems".into(),index:0,quote}];
    preserve_conditional_actions(&mut m,&mut evidence,&text);
    assert_eq!(m.action_items[0].due,None);assert!(m.action_items[0].text.starts_with("待核对："));
    assert!(evidence[0].quote.starts_with("如果客户同意"));assert!(text.contains(&evidence[0].quote));
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
    let many_sources = parse_concise_overview(r#"{"overview":[{"text":"综合多个议题。","sources":[0,1,2,3,4,5,6,7,8]}]}"#, 9).unwrap();
    assert_eq!(many_sources[0].sources.len(), 9);
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
fn concise_long_overview_requires_sources_across_the_meeting() {
    // A real 25-item meeting generated an opening-only overview; valid IDs
    // alone do not reveal that all later topics were missed.
    let opening_only = r#"{"overview":[{"text":"只覆盖前段","sources":[0,1,5,7]}]}"#;
    assert!(parse_concise_overview(opening_only, 25).is_err());
    let all_sections = r#"{"overview":[{"text":"前段","sources":[0]},{"text":"中段","sources":[8]},{"text":"后段","sources":[24]}]}"#;
    assert!(parse_concise_overview(all_sections, 25).is_ok());
}

#[test]
fn overview_keeps_full_minutes_and_uses_only_selected_items_in_original_order() {
    let source = session("会议原文");
    let (mut minutes, _) = response(&source);
    minutes.summary = (0..15).map(|i| format!("原有重点{i}")).collect();
    minutes.markdown = "# 原来的完整纪要\n\n## 行动项\n\n- 跟进报价".into();
    let full = minutes.markdown.clone();
    let details = minutes.summary.clone();
    prepend_overview(&mut minutes, &details, &[12, 1, 8]);
    assert!(minutes.markdown.starts_with("## 全会重点\n\n- 原有重点1\n- 原有重点8\n- 原有重点12"));
    assert!(minutes.markdown.ends_with(&full));
    assert_eq!(minutes.summary, details);
    for bad in [vec![], vec![1, 1], vec![15], (0..13).collect()] {
        let previous = minutes.markdown.clone();
        prepend_overview(&mut minutes, &details, &bad);
        assert_eq!(minutes.markdown, previous);
    }
}

#[test]
fn fallback_overview_selects_the_filtered_items_not_the_unfiltered_indices() {
    let source = session("会议原文");
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["背景谈话".into(), "正常议题一".into(), "正常议题二".into()];
    minutes.markdown = "# 完整纪要".into();
    let filtered = vec!["正常议题一".into(), "正常议题二".into()];
    prepend_overview(&mut minutes, &filtered, &[0, 1]);
    assert!(minutes.markdown.starts_with("## 全会重点\n\n- 正常议题一\n- 正常议题二"));
    assert!(!minutes.markdown.contains("背景谈话"));
    assert_eq!(minutes.summary[0], "背景谈话");
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
    apply_action_review(&source, &mut minutes, &[], &[], &ActionReview {background:vec![1],duplicates:vec![],..Default::default()});
    assert_eq!(minutes.action_items.len(), 2);
    assert_eq!(minutes.action_items[0].text, "周五发报价");
    assert_eq!(minutes.action_items[0].owner.as_deref(), Some("小王"));
    assert_eq!(minutes.action_items[0].due.as_deref(), Some("周五"));
    assert_eq!(minutes.action_items[1].text, "可能来自背景对话，请核对：买猫粮");
    assert!(minutes.markdown.contains("- 可能来自背景对话，请核对：买猫粮"));
    assert!(minutes.markdown.ends_with("### 第1段\n- 原始引用。"));
    assert_eq!(minutes.summary, before.summary);
    let marked = minutes.markdown.clone();
    apply_action_review(&source, &mut minutes, &[], &[], &ActionReview {background:vec![0,0],duplicates:vec![],..Default::default()});
    apply_action_review(&source, &mut minutes, &[], &[], &ActionReview {background:vec![3],duplicates:vec![],..Default::default()});
    assert_eq!(minutes.markdown, marked);
    let mut malformed = before.clone(); malformed.markdown = "unexpected".into();
    apply_action_review(&source, &mut malformed, &[], &[], &ActionReview {background:vec![0],duplicates:vec![],..Default::default()});
    assert_eq!(malformed.action_items[0].text, before.action_items[0].text);
}

#[test]
fn background_review_keeps_multitopic_meeting_when_most_items_are_flagged() {
    let source = session("会议先讨论包装，后来讨论售后和发货。");
    let (mut minutes, _) = response(&source);
    minutes.summary = (0..16).map(|i| format!("正常议题{i}")).collect();
    minutes.decisions = vec!["包装确定".into(), "售后确定".into()];
    minutes.questions = vec!["发货时间？".into()];
    minutes.action_items = vec![crate::companion_v1::CompanionV1ActionItem {
        text: "周五发报价".into(), owner: None, due: None,
    }];
    minutes.markdown = "> 原会议已完成。\n\n# 正常议题\n\n## 分段原文依据\n\n- 原文。".into();
    let before = minutes.clone();
    let review = ActionReview { background: vec![0], background_summary: (0..8).collect(),
        background_decisions: vec![0,1], background_questions: vec![0], ..Default::default() };
    apply_action_review(&source, &mut minutes, &[], &[], &review);
    assert_eq!(minutes.markdown, before.markdown);
    assert_eq!(minutes.summary, before.summary);
    assert_eq!(minutes.action_items[0].text, before.action_items[0].text);
}

#[test]
fn background_sections_move_only_flagged_reading_items_and_keep_originals() {
    let source = session("包装使用蓝色纸盒。旁人讨论猫粮。\n");
    let (mut minutes, _) = response(&source);
    minutes.summary = vec!["会议决定蓝色包装。".into(), "旁人讨论猫粮。".into()];
    minutes.decisions = vec!["使用蓝色纸盒。".into(), "购买猫粮。".into()];
    minutes.questions = vec!["如何交付？".into(), "猫粮在哪里买？".into()];
    minutes.markdown = "> 长会议已完成。\n\n# 原纪要\n\n## 分段原文依据\n\n- 包装使用蓝色纸盒。\n- 旁人讨论猫粮。".into();
    let before = minutes.clone();
    let review = ActionReview { background_summary: vec![1], background_decisions: vec![1],
        background_questions: vec![1], ..Default::default() };
    apply_action_review(&source, &mut minutes, &[], &[], &review);
    let (main, background) = minutes.markdown.split_once("## 可能来自背景对话，请核对").unwrap();
    assert!(main.contains("会议决定蓝色包装。"));
    assert!(!main.contains("旁人讨论猫粮。"));
    assert!(background.contains("摘要：旁人讨论猫粮。"));
    assert!(background.contains("决定：购买猫粮。"));
    assert!(background.contains("问题：猫粮在哪里买？"));
    assert!(background.contains("## 分段原文依据\n\n- 包装使用蓝色纸盒。\n- 旁人讨论猫粮。"));
    assert_eq!(minutes.summary, before.summary);
    assert_eq!(minutes.decisions, before.decisions);
    assert_eq!(minutes.questions, before.questions);
}

#[test]
fn mixed_background_summary_is_annotated_without_removing_meeting_content() {
    let quote="旁边说先更新软件并确保安装都是最新版本";
    let source=session(&format!("会议讨论正常报价。{quote}会议继续讨论价格。"));
    let (mut minutes,_)=response(&source);
    minutes.summary=vec!["会议讨论正常报价，旁边说确保安装都是最新版本。".into(),
        "另一段也提到确保安装都是最新版本。".into()];
    minutes.action_items=vec![crate::companion_v1::CompanionV1ActionItem{text:"更新软件".into(),owner:None,due:None}];
    minutes.markdown=format!("> 原会议已完成。\n\n# 原纪要\n\n## 分段原文依据\n\n- {quote}");
    let actions=vec![vec![quote.to_string()]];
    let sources=vec![vec![quote.to_string()],vec!["另一段完全不同的原话内容".into()]];
    let mixed=mixed_background_summary_indices(&source,&minutes,&actions,&sources,&[0]);
    assert_eq!(mixed,vec![0]);
    assert!(mixed_background_summary_indices(&source,&minutes,&actions,&sources,&[]).is_empty());
    let mut repeated=source.clone();repeated.transcript_text.push_str(quote);
    assert!(mixed_background_summary_indices(&repeated,&minutes,&actions,&sources,&[0]).is_empty());
    let before=minutes.summary.clone();
    apply_action_review(&source,&mut minutes,&actions,&mixed,&ActionReview{background:vec![0],..Default::default()});
    assert_eq!(minutes.summary,before,"structured summary must remain unchanged");
    assert!(minutes.markdown.contains("会议讨论正常报价"));
    assert!(minutes.markdown.contains("部分内容可能来自背景对话，请核对"));
    assert!(minutes.markdown.contains(quote));
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
    apply_action_review(&source,&mut minutes,&quotes, &[], &ActionReview{background:vec![0],duplicates:vec![],..Default::default()});
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
    apply_action_review(&source,&mut minutes,&quotes, &[], &ActionReview{background,duplicates:vec![],..Default::default()});
    assert_eq!(minutes.keywords,before);
    assert!(minutes.markdown.contains(&format!("{target}（可能来自背景对话，请核对）")));
}

#[test]
fn background_review_keeps_valid_summary_when_provider_returns_action_ids_without_actions() {
    use std::{io::{Read, Write}, net::TcpListener, thread};
    let listener=TcpListener::bind("127.0.0.1:0").unwrap();let address=listener.local_addr().unwrap();
    let worker=thread::spawn(move || {
        let (mut stream,_)=listener.accept().unwrap();stream.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
        let mut data=Vec::new();let mut buffer=[0u8;4096];
        loop {
            let n=stream.read(&mut buffer).unwrap();if n==0 {break;}data.extend_from_slice(&buffer[..n]);
            if let Some(i)=data.windows(4).position(|w|w==b"\r\n\r\n") {
                let headers=String::from_utf8_lossy(&data[..i]);
                let len:usize=headers.lines().find_map(|line|line.split_once(':')
                    .filter(|(key,_)|key.eq_ignore_ascii_case("content-length"))
                    .and_then(|(_,value)|value.trim().parse().ok())).unwrap();
                if data.len()>=i+4+len {break;}
            }
        }
        let result=serde_json::json!({"possiblyUnrelated":[5,6],"duplicateGroups":[],
            "backgroundSummary":[1],"backgroundDecisions":[],"backgroundQuestions":[]}).to_string();
        let payload=serde_json::json!({"choices":[{"finish_reason":"stop","message":{"content":result}}]}).to_string();
        write!(stream,"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}",payload.len(),payload).unwrap();
    });
    let source=session("会议讨论报价。旁边聊猫粮。");let (mut minutes,_)=response(&source);
    minutes.summary=vec!["会议讨论报价".into(),"旁边聊猫粮".into()];minutes.action_items.clear();
    minutes.markdown="> 原会议已完成。\n\n# 原纪要\n\n## 分段原文依据\n\n- 会议讨论报价。旁边聊猫粮。".into();
    let evidence=vec![Evidence{field:"summary".into(),index:0,quote:"会议讨论报价".into()},
        Evidence{field:"summary".into(),index:1,quote:"旁边聊猫粮".into()}];
    let checkpoint=Checkpoint{identity:Identity::new("https://fixture.invalid","model","key",&source),
        chapters:vec![Some(Chapter{start:0,end:source.transcript_text.len(),source_hash:String::new(),
            minutes:minutes.clone(),evidence,omitted_items:0,result_hash:String::new()})]};
    let endpoint=format!("http://{address}/chat/completions");
    let client=reqwest::blocking::Client::builder().no_proxy().timeout(Duration::from_secs(5)).build().unwrap();
    let review=request_background_review(&endpoint,"test","test-key",&source,&minutes,&[],Some(&checkpoint),&client).unwrap();
    assert!(review.background.is_empty());assert_eq!(review.background_summary,vec![1]);
    apply_action_review(&source,&mut minutes,&[], &[], &review);
    assert!(minutes.markdown.contains("## 可能来自背景对话，请核对\n\n- 摘要：旁边聊猫粮"));
    worker.join().unwrap();
}

#[test]
#[ignore = "uses an isolated checkpoint and previously authorized real-card transcript with the configured AI service"]
fn real_card_complete_mixed_background_review() {
    let input=std::env::var_os("COMPANION_MIXED_BACKGROUND_RESULT").unwrap();
    let source:CompanionV1HostSession=serde_json::from_slice(&fs::read(input).unwrap()).unwrap();
    let base=std::env::var("DEEPSEEK_BASE_URL").unwrap();
    let endpoint=format!("{}/chat/completions",base.trim_end_matches('/'));
    let client=reqwest::blocking::Client::builder().timeout(Duration::from_secs(90)).build().unwrap();
    let result=run_with_boundary(&endpoint,&std::env::var("DEEPSEEK_MODEL").unwrap(),
        &std::env::var("DEEPSEEK_API_KEY").unwrap(),&source,"now",&client,None,None).unwrap();
    let flagged=result.action_items.iter().filter(|a|a.text.contains("可能来自背景对话")).count();
    let mixed=result.markdown.matches("部分内容可能来自背景对话，请核对").count();
    println!("real-card review: {flagged} background actions, {mixed} mixed summary warnings");
    assert_eq!(flagged,2);assert!(mixed>=2);assert_eq!(result.quality,"final");
    assert!(result.markdown.contains("原文依据"));
}

#[test]
#[ignore = "uses previously authorized isolated real-card result; no network"]
fn replay_real_mixed_background_summaries() {
    let result=std::env::var_os("COMPANION_MIXED_BACKGROUND_RESULT").unwrap();
    let checkpoint=std::env::var_os("COMPANION_MIXED_BACKGROUND_CHECKPOINT").unwrap();
    let source:CompanionV1HostSession=serde_json::from_slice(&fs::read(result).unwrap()).unwrap();
    let mut minutes=source.minutes.clone().unwrap();let mut background=Vec::new();
    for (index,item) in minutes.action_items.iter_mut().enumerate() {
        if let Some(text)=item.text.strip_prefix("可能来自背景对话，请核对：") {
            item.text=text.to_string();background.push(index);
        }
    }
    let checkpoint=read_checkpoint(Path::new(&checkpoint)).unwrap();
    let actions=action_source_quotes(&checkpoint,&minutes);
    let summaries=content_source_quotes(&checkpoint,&minutes.summary,"summary");
    let mixed=mixed_background_summary_indices(&source,&minutes,&actions,&summaries,&background);
    assert_eq!(mixed,vec![47,48]);
    println!("real-card mixed paragraphs identified for review: {}",mixed.len());
}

#[test]
#[ignore = "uses previously authorized real-card transcript-derived material and the configured AI service"]
fn real_card_background_review_with_context() {
    let result=std::env::var_os("COMPANION_REAL_BACKGROUND_RESULT").unwrap();
    let checkpoint=std::env::var_os("COMPANION_REAL_BACKGROUND_CHECKPOINT").unwrap();
    let source:CompanionV1HostSession=serde_json::from_slice(&fs::read(result).unwrap()).unwrap();
    let minutes=source.minutes.as_ref().unwrap();
    let checkpoint=read_checkpoint(Path::new(&checkpoint)).unwrap();
    let quotes=action_source_quotes(&checkpoint,minutes);
    assert_eq!(minutes.action_items.len(),2);assert!(quotes.iter().all(|q|!q.is_empty()));
    let base=std::env::var("DEEPSEEK_BASE_URL").unwrap();
    let endpoint=format!("{}/chat/completions",base.trim_end_matches('/'));
    let client=reqwest::blocking::Client::builder().timeout(Duration::from_secs(45)).build().unwrap();
    let review=request_background_review(&endpoint,&std::env::var("DEEPSEEK_MODEL").unwrap(),
        &std::env::var("DEEPSEEK_API_KEY").unwrap(),&source,minutes,&quotes,Some(&checkpoint),&client).unwrap();
    assert_eq!(review.background,vec![0,1]);
    assert!(review.background_summary.iter().all(|i|*i==54));
    assert!(review.background_decisions.is_empty());
    assert!(review.background_questions.iter().all(|i|*i==2||*i==7));
    println!("real-card actions marked for review: {}; no original removed",review.background.len());
}

#[test]
fn action_context_requires_unique_source_and_respects_unicode_boundaries() {
    let transcript=format!("{}说话人在这里说话。{}", "前".repeat(200), "后".repeat(200));
    let result=action_quote_context(&transcript,&["这里说话".into()]);
    assert_eq!(result.len(),1);assert!(result[0].contains("这里说话"));
    assert_eq!(result[0].chars().count(),160+4+160);
    assert!(action_quote_context("重复内容重复内容",&["重复".into()]).is_empty());
    assert!(action_quote_context("短原文",&["不存在".into(),"".into()]).is_empty());
    assert_eq!(review_index(&serde_json::json!("a1"),'a',2),Some(1));
    assert_eq!(review_index(&serde_json::json!("s1"),'a',2),None);
}

#[test]
fn background_review_keeps_valid_typed_ids_and_ignores_mixed_fields() {
    use std::{io::{Read, Write}, net::TcpListener, thread};
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    let worker = thread::spawn(move || {
        for content in [r#"{"possiblyUnrelated":["a1","q1"],"duplicateGroups":[["a0","d0"]]}"#, r#"{"possiblyUnrelated":[1,1]}"#, r#"{"possiblyUnrelated":[2]}"#] {
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
            let parsed: Value=serde_json::from_str(input).unwrap();
            assert_eq!(parsed["actions"][1]["id"],"a1");
            assert_eq!(parsed["actions"][1]["sourceContext"][0],"会议原文");
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
    let quotes=vec![vec![],vec!["原文".to_string()]];
    let first=request_background_review(&endpoint,"test","test-key",&source,&minutes,&quotes,None,&client).unwrap();
    assert_eq!(first.background,vec![1]);assert!(first.duplicates.is_empty());
    assert_eq!(request_background_review(&endpoint,"test","test-key",&source,&minutes,&quotes,None,&client).unwrap().background, vec![1]);
    assert!(request_background_review(&endpoint,"test","test-key",&source,&minutes,&quotes,None,&client).unwrap().background.is_empty());
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
    let review=ActionReview {background:vec![1],duplicates:vec![vec![0,1],vec![2,3]],..Default::default()};
    apply_action_review(&source,&mut minutes,&quotes, &[], &review);
    assert_eq!(minutes.action_items.len(),3);
    assert!(minutes.action_items[0].text.starts_with("可能来自背景对话，请核对："));
    assert!(minutes.action_items[1].text.contains("其他产品"));
    assert_eq!(minutes.action_items[2].owner.as_deref(),Some("小李"));
    assert!(minutes.markdown.ends_with("### 第1段\n- 客户提出修改，下周一确认交货时间。"));
}

#[test]
#[ignore = "live public benchmark and configured DeepSeek service"]
fn real_public_long_meeting_fallback() {
    let input = std::env::var("COMPANION_PUBLIC_MINUTES_RESULT").unwrap();
    let output = std::env::var("COMPANION_PUBLIC_FALLBACK_RESULT").unwrap();
    let value: Value = serde_json::from_slice(&fs::read(input).unwrap()).unwrap();
    let mut minutes: CompanionV1MeetingMinutes = serde_json::from_value(value["minutes"].clone()).unwrap();
    let original = minutes.markdown.clone();
    let key = std::env::var("DEEPSEEK_API_KEY").unwrap();
    let model = std::env::var("DEEPSEEK_MODEL").unwrap_or_else(|_| "deepseek-chat".into());
    let base = std::env::var("DEEPSEEK_BASE_URL").unwrap_or_else(|_| "https://api.deepseek.com".into());
    let endpoint = format!("{}/chat/completions", base.trim_end_matches('/'));
    let client = super::super::deepseek_http_client(&endpoint).unwrap();
    let items = minutes.summary.clone();
    let indices = request_overview(&endpoint, &model, &key, &items, &client).unwrap();
    let selected: Vec<_> = indices.iter().map(|&i| &items[i]).collect();
    fs::write(output, serde_json::to_vec_pretty(&serde_json::json!({"indices":indices,"selected":selected})).unwrap()).unwrap();
    prepend_overview(&mut minutes, &items, &indices);
    assert!(minutes.markdown.ends_with(&original));
    assert!(indices.iter().any(|&i| i < items.len()/3));
    assert!(indices.iter().any(|&i| i >= items.len()/3 && i < items.len()*2/3));
    assert!(indices.iter().any(|&i| i >= items.len()*2/3));
}

#[test]
fn chapter_index_rejects_rewritten_or_incomplete_topic_output() {
    let valid = r#"{"groups":[[8,9],[1,2],[4,6]]}"#;
    assert_eq!(parse_chapter_index(valid, 12).unwrap(), vec![1,4,8]);
    let valid = r#"{"groups":[[10,9],[1,2],[5,6]]}"#;
    assert_eq!(parse_chapter_index(valid, 15).unwrap(), vec![1,5,10]);
    for invalid in [
        r#"{"groups":[[1,2],[5,10]]}"#,
        r#"{"groups":[[1,1],[5],[10]]}"#,
        r#"{"groups":[[1,9],[5,9],[10]]}"#,
        r#"{"groups":[[1],[5],[15]]}"#,
        r#"{"groups":[[1],[],[10]]}"#,
        r#"{"groups":[[1],[5],[10]],"takeaway":"已同意执行"}"#,
    ] {
        assert!(parse_chapter_index(invalid, 15).is_err(), "{invalid}");
    }
}
