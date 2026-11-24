//! One saved-source selection for text, documents, clipboard and file sharing.
//! No service calls, inferred facts or edits to the source session.
use serde::{Deserialize,Serialize};
use crate::companion_v1::CompanionV1HostSession;
use super::export::{MeetingExportFormat as Format,PreparedMeetingExport};

#[derive(Clone,Debug,Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Selection {
    pub minutes:bool,
    #[serde(default)]
    pub minutes_followup_only: bool,
    pub transcript:bool,
    pub highlights:bool,
    pub timeline:bool,
    #[serde(default)]
    pub note_ids:Vec<String>,
}

pub fn source(session:&CompanionV1HostSession,mode:&str,choice:&Selection)->Result<String,String>{
    selected_source(session,mode,choice,false)
}

// Presentation for ordinary handoff only. Complete JSON/legacy raw exports
// and the saved source remain untouched. Remove only our exact generated
// transport header; speech, manual material, unknown sections and code stay literal.
fn readable_minutes(markdown:&str)->String {
    let lines:Vec<_>=markdown.lines().collect();
    let mut result=Vec::new();let mut i=0;let mut fence:Option<(u8,usize)>=None;
    while i<lines.len(){
        let line=lines[i];let trimmed=line.trim_start();
        let bytes=trimmed.as_bytes();
        if matches!(bytes.first(),Some(b'`'|b'~')) {
            let marker=bytes[0];let count=bytes.iter().take_while(|&&b|b==marker).count();
            if count>=3 {
                if let Some((kind,length))=fence {if marker==kind&&count>=length&&trimmed[count..].trim().is_empty(){fence=None;}}
                else {fence=Some((marker,count));}
                result.push(line.to_owned());i+=1;continue;
            }
        }
        if fence.is_none()&&i+5<lines.len()&&line.starts_with("# ")&&!line[2..].trim().is_empty()
            &&lines[i+1].is_empty()&&lines[i+2].strip_prefix("Generated: ").is_some_and(|s|!s.is_empty())
            &&lines[i+3].strip_prefix("Duration: ").and_then(|s|s.strip_suffix(" ms")).is_some_and(|s|s.parse::<u64>().is_ok())
            &&lines[i+4].strip_prefix("Source: ").is_some_and(|s|!s.is_empty())
            &&matches!(lines[i+5],"Minutes engine: rules_l0 (draft)"|"Minutes engine: llm_deepseek (final)") {
            result.push(line.to_owned());result.push(String::new());i+=6;continue;
        }
        let presented=if fence.is_none(){match line.trim_end(){
            "## Summary"=>"## 会议摘要", "## Decisions"=>"## 讨论结论（需核对）",
            "## Action Items"=>"## 行动事项", "## Questions"|"## Open Questions"=>"## 待确认问题",
            "## Keywords"=>"## 关键词", _=>line,
        }}else{line};
        result.push(presented.to_owned());i+=1;
    }
    let mut output=result.join("\n");if markdown.ends_with('\n'){output.push('\n');}output
}

fn saved_followup(session: &CompanionV1HostSession, mode: &str, markdown: &str) -> Result<String, String> {
    let ready = super::export::minutes_variant_for_mode(session, mode).filter(|minutes| {
        minutes.source == "llm_local_qwen" && minutes.status == "minutesReady" && minutes.quality == "final"
            && minutes.processing.as_ref().is_none_or(|progress| progress.is_complete())
            && super::transcript_review::minutes_current(session, minutes.source_review_revision)
            && super::minutes_context::current(session, &minutes.source_note_context)
    });
    let Some(ready) = ready else {
        return Err("请先完成并核对当前版本的本地纪要，再提取决定与跟进。".into());
    };
    let mut output = Vec::new();
    let mut include = false;
    for line in markdown.lines() {
        if let Some(heading) = line.strip_prefix("## ") {
            if heading.trim_end() == "主题原话" { break; }
            include = matches!(heading.trim_end(), "Decisions" | "Action Items" | "Open Questions" | "协作要求");
        }
        if include {
            output.push(line);
        }
    }
    if output.is_empty() {
        return Err("已保存的纪要没有决定、行动或待确认事项，可导出完整纪要。".into());
    }
    let title = session.title.lines().next().unwrap_or("").trim();
    let title = if title.is_empty() { "会议跟进" } else { title };
    let grouped = ready.source_action_evidence.as_ref()
        .and_then(|evidence| super::followup_handoff::grouped(session,evidence,&output));
    let body = grouped.unwrap_or_else(|| output.join("\n").trim_end().to_owned());
    Ok(readable_minutes(&format!("# {title}\n\n> 已保存纪要中的决定与跟进，发送前请核对。\n\n{}",
        body)))
}

fn selected_source(session:&CompanionV1HostSession,mode:&str,choice:&Selection,literal_transcript:bool)->Result<String,String>{
    super::library_lifecycle::require_available(session)?;
    if !matches!(mode,"offlineStore"|"onlineLive") {return Err("不支持的会议版本。".into());}
    if !choice.minutes&&!choice.transcript&&!choice.highlights&&choice.note_ids.is_empty(){return Err("请选择要导出或复制的内容。".into());}
    if choice.minutes_followup_only && !choice.minutes {return Err("请选择要导出的整理结果。".into());}
    if choice.timeline&&!choice.transcript{return Err("分段时间和说话人需要同时选择录音文字。".into());}
    let ids:std::collections::HashSet<_>=choice.note_ids.iter().collect();
    if ids.len()!=choice.note_ids.len()||ids.len()>128 {return Err("所选材料重复或过多，请重新选择。".into());}
    if ids.iter().any(|id|!session.meeting_notes.iter().any(|note|&note.id==*id)){return Err("所选材料已不存在，请重新选择；未导出其他材料。".into());}
    let mut parts=Vec::new();
    if choice.minutes {
        let markdown = super::export::saved_minutes_markdown_for_mode(session, mode)?;
        parts.push(if choice.minutes_followup_only {
            saved_followup(session, mode, &markdown)?
        } else {
            readable_minutes(&markdown)
        });
    }
    if choice.transcript {
        super::export::require_final_transcript(session)?;
        if !super::transcript_review::effective_unrecognized(session).is_empty(){
            parts.push("> 部分原音没有完整文字，以下仅为已保存内容，请回听原音核对。".into());
        }
        let text=super::transcript_review::effective_text(session);
        // Rich renderers treat a quote as one verbatim paragraph. Protect
        // saved speech before interpreting document structure, while keeping
        // clipboard/TXT/Markdown/XLSX source text unchanged.
        let presented=if literal_transcript {super::export_text_layout::quote_literal_lines(&text)} else {text.to_owned()};
        parts.push(format!("## 录音文字\n\n{presented}"));
        if choice.timeline {
            let rows=super::transcript_review::effective_utterances(session);
            if rows.is_empty(){return Err("这份录音没有可用的分段时间。".into());}
            let mut timeline=String::from("## 分段时间与说话人\n\n以下沿用识别分段；近似时间已标明，与人工修订全文可能不完全一致。\n\n");
            for (i,row) in rows.iter().enumerate(){
                let time=if row.end_ms>row.start_ms {format!("{}–{}{}",super::export::pdf_time(row.start_ms),super::export::pdf_time(row.end_ms),if row.approximate_timing{"（约）"}else{""})}else{"时间未提供".into()};
                let speaker=super::transcript_review::speaker_label(session,i).unwrap_or_default();
                timeline.push_str(&format!("- {time} {speaker}：{}\n",row.text));
            }
            parts.push(timeline);
        }
    }
    if choice.highlights {
        let text=super::export::render_bookmarks(session);
        if !text.trim().is_empty(){parts.push(text);}
    }
    if !choice.note_ids.is_empty(){
        let mut selected=session.clone();
        selected.meeting_notes.retain(|note|ids.contains(&note.id));
        parts.push(super::meeting_notes::render(&selected));
    }
    let content=parts.join("\n\n");
    if content.trim().is_empty(){return Err("所选内容为空，请选择其他内容。".into());}
    Ok(content)
}

pub fn prepare(session:&CompanionV1HostSession,mode:&str,format:Format,choice:&Selection)->Result<PreparedMeetingExport,String>{
    if !matches!(format,Format::Markdown|Format::Txt|Format::Docx|Format::Pdf|Format::Mindmap|Format::Xlsx|Format::Srt|Format::Pptx|Format::Png|Format::Bundle){
        return Err("此格式不支持内容选择，请使用对应的完整数据或日历入口。".into());
    }
    if format==Format::Srt {
        if !choice.transcript||choice.minutes||choice.highlights||!choice.note_ids.is_empty(){return Err("字幕文件只包含有有效时间轴的录音文字，请取消其他内容。".into());}
        return super::export::prepare_meeting_export(session,mode,format);
    }
    let rich_document=matches!(format,Format::Docx|Format::Pdf|Format::Mindmap|Format::Pptx|Format::Png);
    let content=selected_source(session,mode,choice,rich_document)?;
    let bytes=match format {
        Format::Bundle=>super::meeting_note_images::bundle(session,&content,&choice.note_ids)?,
        Format::Docx=>super::meeting_document_export::word(&session.title,&content)?,
        Format::Mindmap=>super::meeting_document_export::mindmap(&session.title,&content),
        Format::Xlsx=>super::spreadsheet_export::render(&session.title,&content)?,
        Format::Pptx=>super::presentation_export::render(&session.title,&content)?,
        Format::Png=>{super::mindmap_image_export::page(&session.title,&content)?;content.into_bytes()},
        _=>content.into_bytes(),
    };
    Ok(PreparedMeetingExport{bytes,suggested_name:format!("{}-所选内容.{}",super::export::safe_file_stem(&session.title,&session.id),format.extension()),format,warning:None,calendar_items:None})
}

pub fn materialize(title:&str,prepared:PreparedMeetingExport)->Result<Vec<u8>,String>{
    materialize_bytes(title,prepared.format,prepared.bytes)
}
pub(crate) fn materialize_bytes(title:&str,format:Format,bytes:Vec<u8>)->Result<Vec<u8>,String>{
    match format {
        Format::Pdf|Format::Png=>{
            let text=std::str::from_utf8(&bytes).map_err(|_|"无法读取所选正文。")?;
            if format==Format::Pdf{super::pdf_export::render(title,text)}else{super::mindmap_image_export::render(title,text)}
        },
        _=>Ok(bytes),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn content109_readable_handoff_keeps_facts_and_raw_saved_source(){
        let raw="# 采购沟通\n\nGenerated: 2026-11-12T01:00:00Z\nDuration: 12000 ms\nSource: importedTranscript\nMinutes engine: llm_deepseek (final)\n\n## Summary\n预算12,000.00尚未批准，FALSE和0保留。\n\n## Action Items\n- [ ] 核对采购清单\n\n## Open Questions\n- 等待书面确认。\n\n```text\n## Summary\nGenerated: 用户原文\n```\n";
        let text=readable_minutes(raw);
        assert!(!text.contains("Minutes engine: llm_deepseek (final)"));
        assert!(!text.contains("Duration: 12000 ms"));assert!(text.contains("# 采购沟通"));
        assert!(text.contains("## 会议摘要")&&text.contains("## 行动事项")&&text.contains("## 待确认问题"));
        assert!(text.contains("预算12,000.00尚未批准，FALSE和0保留。"));
        assert!(text.contains("```text\n## Summary\nGenerated: 用户原文\n```"));
        let mut row=sample();
        row.minutes.as_mut().unwrap().markdown=raw.into();
        row.minutes_by_mode.offline_store.as_mut().unwrap().markdown=raw.into();
        let before=serde_json::to_vec(&row).unwrap();
        let choice=Selection{minutes_followup_only:false,minutes:true,transcript:false,highlights:false,timeline:false,note_ids:vec![]};
        let selected=source(&row,"offlineStore",&choice).unwrap();
        assert!(selected.contains("## 会议摘要")&&!selected.contains("Minutes engine:"));
        assert_eq!(prepare(&row,"offlineStore",Format::Txt,&choice).unwrap().bytes,selected.as_bytes());
        assert_eq!(serde_json::to_vec(&row).unwrap(),before);
        let manual="用户原文：Generated: 自述\nDuration: 5 ms\n## 未知自定义标题\n- FALSE 0 未批准";
        assert_eq!(readable_minutes(manual),manual);
    }

    #[test]
    fn followup_export_keeps_the_decision_conditions_action_and_unresolved_heading() {
        let mut row = sample();
        let current = row.minutes_by_mode.offline_store.as_mut().unwrap();
        current.source = "llm_local_qwen".into();
        current.status = "minutesReady".into();
        current.quality = "final".into();
        current.source_review_revision = None;
        current.source_note_context = None;
        current.processing = None;
        current.markdown = "## 主题脉络\n\n- 非所选讨论\n\n## Decisions\n\n- 验收后才能上线。\n\n## Action Items\n\n- 李明核对差额（日期待定）。\n\n## Open Questions\n\n- 外包价格待确认。\n\n## 主题原话\n\n### 行动项 · 原话\n\n- 不导出的原话\n".into();
        let choice: Selection = serde_json::from_value(serde_json::json!({
            "minutes":true,"minutesFollowupOnly":true,"transcript":false,"highlights":false,"timeline":false
        })).unwrap();
        let text = source(&row, "offlineStore", &choice).unwrap();
        for piece in ["验收后才能上线", "李明核对差额（日期待定）", "外包价格待确认", "发送前请核对"] {
            assert!(text.contains(piece));
        }
        assert!(!text.contains("非所选讨论") && !text.contains("不导出的原话"));
        assert_eq!(prepare(&row, "offlineStore", Format::Txt, &choice).unwrap().bytes, text.as_bytes());
        row.minutes_by_mode.offline_store.as_mut().unwrap().quality = "draft".into();
        assert!(source(&row, "offlineStore", &choice).is_err());
    }

    #[test]
    fn followup_short_draft_groups_verified_contacts_and_separates_requests() {
        use sha2::{Digest,Sha256};
        let mut row=sample();
        let intro="说话人2: 零零四啊我是初一";
        let work="说话人2: 在期末考试前，我会进行三次模拟。";
        let notice="说话人1: 考试时候要向家长说明考试时间。";
        let transcript=format!("{intro}\n说话人4: 主任。\n说话人2: 班主任。\n{work}\n{notice}");
        row.transcript_text=transcript.clone();
        let v=row.minutes_by_mode.offline_store.as_mut().unwrap();
        v.source="llm_local_qwen".into();
        v.status="minutesReady".into();
        v.quality="final".into();
        v.source_review_revision=None;
        v.source_note_context=None;
        v.processing=None;
        let action="初一｜在期末考试前，进行三次模拟";
        let pending="初一｜向家长说明考试时间，通知安排待确认。";
        v.markdown=format!("## Action Items\n\n- {action}\n\n## Open Questions\n\n- {pending}\n- 领取教材的人选尚未确认。\n");
        v.source_action_evidence=Some(serde_json::from_value(serde_json::json!({
            "transcriptSha256":format!("{:x}",Sha256::digest(transcript.as_bytes())),
            "reviewRevision":null,
            "actions":[{"text":action,"segments":[],"transcriptQuotes":[work,intro]}],
            "questions":[{"text":pending,"segments":[],"transcriptQuotes":[notice,intro]}],
        })).unwrap());
        let choice=Selection{minutes_followup_only:true,minutes:true,transcript:false,highlights:false,timeline:false,note_ids:vec![]};
        let draft=source(&row,"offlineStore",&choice).unwrap();
        let section=draft.split("## 请初一班主任核对").nth(1).unwrap();
        assert!(section.contains("- 已明确 · 在期末考试前，进行三次模拟。"));
        assert!(section.contains("- 请确认 · 上述安排的具体日期或时间。"));
        assert!(section.contains("- 请确认 · 向家长说明考试时间的通知安排。"));
        assert!(draft.contains("## 待确认问题\n\n- 领取教材的人选尚未确认。"));
        assert!(!draft.contains("初一｜")&&!draft.contains("## 请初一主任核对"));
        assert_eq!(prepare(&row,"offlineStore",Format::Txt,&choice).unwrap().bytes,draft.as_bytes());
        let v=row.minutes_by_mode.offline_store.as_mut().unwrap();
        v.source_action_evidence.as_mut().unwrap().transcript_sha256="stale".into();
        let legacy=source(&row,"offlineStore",&choice).unwrap();
        assert!(legacy.contains(action)&&legacy.contains(pending));
        assert!(!legacy.contains("## 请初一班主任核对"));
    }

    fn sample()->CompanionV1HostSession {
        let mut rows:Vec<CompanionV1HostSession>=serde_json::from_str(include_str!("../calendar_test_fixtures/p738-sessions.json")).unwrap();
        let mut row=rows.remove(0);row.transcript_text="李明：11月8日前核对20%差额，尚未确认采购。".into();row.transcript_final=true;
        row.meeting_notes=vec![super::super::meeting_notes::Note{kind:Default::default(),references:vec![],id:"11111111-1111-4111-8111-111111111111".into(),text:"AI 材料（请核对）｜英语译文\nThe purchase has not been approved.\n原文依据：尚未确认采购。".into(),bookmark_id:None,image:None,created_at:"2026-11-05T00:00:00Z".into(),updated_at:"2026-11-05T00:00:00Z".into()},super::super::meeting_notes::Note{kind:Default::default(),references:vec![],id:"22222222-2222-4222-8222-222222222222".into(),text:"UNSELECTED_PRIVATE_MATERIAL".into(),bookmark_id:None,image:None,created_at:"2026-11-05T00:00:00Z".into(),updated_at:"2026-11-05T00:00:00Z".into()}];row
    }
    #[test]
    fn content051_selection_is_identical_across_text_and_document_routes_without_unselected_data(){
        use std::io::{Cursor,Read};
        let row=sample();let before=serde_json::to_vec(&row).unwrap();
        let choice=Selection{minutes_followup_only:false,minutes:false,transcript:true,highlights:false,timeline:false,note_ids:vec![row.meeting_notes[0].id.clone()]};
        let selected=source(&row,"offlineStore",&choice).unwrap();
        assert!(selected.contains("20%差额，尚未确认采购"));assert!(selected.contains("The purchase has not been approved."));assert!(!selected.contains("UNSELECTED_PRIVATE_MATERIAL"));
        for format in [Format::Txt,Format::Markdown] {
            let p=prepare(&row,"offlineStore",format,&choice).unwrap();assert_eq!(String::from_utf8(p.bytes).unwrap(),selected);
        }
        let p=prepare(&row,"offlineStore",Format::Docx,&choice).unwrap();
        let mut zip=zip::ZipArchive::new(Cursor::new(p.bytes)).unwrap();let mut xml=String::new();zip.by_name("word/document.xml").unwrap().read_to_string(&mut xml).unwrap();
        assert!(xml.contains("20%差额，尚未确认采购"));assert!(!xml.contains("UNSELECTED_PRIVATE_MATERIAL"));
        assert_eq!(serde_json::to_vec(&row).unwrap(),before);
        let mut missing=choice.clone();missing.note_ids.push("missing".into());assert!(prepare(&row,"offlineStore",Format::Txt,&missing).is_err());
        let empty=Selection{minutes_followup_only:false,minutes:false,transcript:false,highlights:false,timeline:false,note_ids:vec![]};assert!(prepare(&row,"offlineStore",Format::Txt,&empty).is_err());
        let prepared=prepare(&row,"offlineStore",Format::Txt,&choice).unwrap();let hash=super::super::export::content_hash(&prepared);
        let mut changed=row.clone();changed.transcript_text.push_str("会后修订");assert!(super::super::export::require_unchanged(&prepare(&changed,"offlineStore",Format::Txt,&choice).unwrap(),Some(&hash)).is_err());
    }
    #[test]
    fn content067_literal_transcript_prefixes_are_not_document_structure(){
        use std::io::{Cursor,Read};
        let mut row=sample();row.transcript_review=None;
        let literal="# 原样井号\n## 不是文档标题\n> 原样引用符\n- 原样短横线\n  # 保留缩进\n**原样星号** <A&B> 😀\n=HYPERLINK(\"https://example.invalid\",\"literal\")";
        row.transcript_text=literal.into();
        let choice=Selection{minutes_followup_only:false,minutes:false,transcript:true,highlights:false,timeline:false,note_ids:vec![]};
        let exact=source(&row,"offlineStore",&choice).unwrap();assert!(exact.ends_with(literal));
        for format in [Format::Txt,Format::Markdown] {
            assert_eq!(prepare(&row,"offlineStore",format,&choice).unwrap().bytes,exact.as_bytes());
        }
        let word=prepare(&row,"offlineStore",Format::Docx,&choice).unwrap();
        let mut archive=zip::ZipArchive::new(Cursor::new(word.bytes)).unwrap();let mut body=String::new();archive.by_name("word/document.xml").unwrap().read_to_string(&mut body).unwrap();
        for line in literal.lines(){assert!(body.contains(&super::super::meeting_document_export::xml(line)),"Word lost literal line: {line}");}
        assert!(!body.contains("UNSELECTED_PRIVATE_MATERIAL"));
        let pdf=prepare(&row,"offlineStore",Format::Pdf,&choice).unwrap();
        let markup=super::super::pdf_export::html(&row.title,std::str::from_utf8(&pdf.bytes).unwrap());
        for line in ["# 原样井号","## 不是文档标题","&gt; 原样引用符","- 原样短横线","  # 保留缩进"]{assert!(markup.contains(line),"PDF lost: {line}");}
        let map=prepare(&row,"offlineStore",Format::Mindmap,&choice).unwrap();let map=String::from_utf8(map.bytes).unwrap();
        for line in ["# 原样井号","## 不是文档标题","> 原样引用符","- 原样短横线","  # 保留缩进"]{assert!(map.contains(&super::super::meeting_document_export::xml(line)),"Map lost: {line}");}
        let ppt=prepare(&row,"offlineStore",Format::Pptx,&choice).unwrap();let mut archive=zip::ZipArchive::new(Cursor::new(ppt.bytes)).unwrap();let mut slides=String::new();
        for i in 0..archive.len(){let mut file=archive.by_index(i).unwrap();if file.name().starts_with("ppt/slides/slide")&&file.name().ends_with(".xml"){file.read_to_string(&mut slides).unwrap();}}
        for line in ["# 原样井号","## 不是文档标题","> 原样引用符","- 原样短横线","  # 保留缩进"]{assert!(slides.contains(&super::super::meeting_document_export::xml(line)),"Slides lost: {line}");}
        let png=prepare(&row,"offlineStore",Format::Png,&choice).unwrap();let page=super::super::mindmap_image_export::page("> 原样会议名",std::str::from_utf8(&png.bytes).unwrap()).unwrap();
        for line in ["> 原样会议名","# 原样井号","## 不是文档标题","> 原样引用符","- 原样短横线","  # 保留缩进"]{assert!(page.html.contains(&super::super::meeting_document_export::xml(line)),"Image lost: {line}");}
        assert_eq!(row.transcript_text,literal);
    }
    #[test]
    fn content051_can_export_a_saved_material_without_ai_minutes_or_audio(){
        let mut row=sample();row.minutes=None;row.minutes_by_mode.offline_store=None;row.minutes_by_mode.online_live=None;row.transcript_text.clear();row.transcript_final=false;
        let choice=Selection{minutes_followup_only:false,minutes:false,transcript:false,highlights:false,timeline:false,note_ids:vec![row.meeting_notes[0].id.clone()]};
        for f in [Format::Txt,Format::Markdown,Format::Docx,Format::Pdf,Format::Xlsx,Format::Mindmap,Format::Pptx,Format::Png]{assert!(prepare(&row,"offlineStore",f,&choice).is_ok());}
        assert!(prepare(&row,"offlineStore",Format::Srt,&choice).is_err());
    }
    #[test]
    fn content051_generate_files_for_external_reader_checks(){
        let Some(root)=std::env::var_os("COMPANION_CONTENT_EXPORT_FIXTURE_DIR") else{return};
        let root=std::path::PathBuf::from(root);assert!(!root.exists(),"use a fresh explicit artifact folder");std::fs::create_dir_all(&root).unwrap();
        let mut row=sample();row.title="公开示例·采购与交付复盘".into();row.source="importedTranscript".into();row.transcript_review=None;
        row.utterances=vec![crate::companion_v1::CompanionV1UtteranceSegment{text:row.transcript_text.clone(),start_ms:0,end_ms:4000,speaker:Some(0),approximate_timing:false}];
        std::fs::write(root.join("public-session.json"),serde_json::to_vec_pretty(&vec![row.clone()]).unwrap()).unwrap();
        let mut manifest=Vec::new();
        for (label,choice) in [("transcript",Selection{minutes_followup_only:false,minutes:false,transcript:true,highlights:false,timeline:false,note_ids:vec![]}),
            ("material",Selection{minutes_followup_only:false,minutes:false,transcript:false,highlights:false,timeline:false,note_ids:vec![row.meeting_notes[0].id.clone()]})]{
            let expected=source(&row,"offlineStore",&choice).unwrap();
            for format in [Format::Txt,Format::Markdown,Format::Docx,Format::Pdf,Format::Xlsx,Format::Mindmap,Format::Pptx,Format::Png]{
                let prepared=prepare(&row,"offlineStore",format,&choice).unwrap();let file=format!("{label}.{}",format.extension());
                let bytes=materialize(&row.title,prepared).unwrap();std::fs::write(root.join(&file),&bytes).unwrap();
                manifest.push(serde_json::json!({"file":file,"selectedText":expected,"title":row.title,"bytes":bytes.len()}));
            }
        }
        let srt=prepare(&row,"offlineStore",Format::Srt,&Selection{minutes_followup_only:false,minutes:false,transcript:true,highlights:false,timeline:true,note_ids:vec![]}).unwrap();
        std::fs::write(root.join("transcript.srt"),srt.bytes).unwrap();
        std::fs::write(root.join("manifest.json"),serde_json::to_vec_pretty(&manifest).unwrap()).unwrap();
        println!("CONTENT051_EXTERNAL_FILES={}",root.display());
    }
}
