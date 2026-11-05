//! One saved-source selection for text, documents, clipboard and file sharing.
//! No service calls, inferred facts or edits to the source session.
use serde::{Deserialize,Serialize};
use crate::companion_v1::CompanionV1HostSession;
use super::export::{MeetingExportFormat as Format,PreparedMeetingExport};

#[derive(Clone,Debug,Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Selection {
    pub minutes:bool,
    pub transcript:bool,
    pub highlights:bool,
    pub timeline:bool,
    #[serde(default)]
    pub note_ids:Vec<String>,
}

pub fn source(session:&CompanionV1HostSession,mode:&str,choice:&Selection)->Result<String,String>{
    super::library_lifecycle::require_available(session)?;
    if !matches!(mode,"offlineStore"|"onlineLive") {return Err("不支持的会议版本。".into());}
    if !choice.minutes&&!choice.transcript&&!choice.highlights&&choice.note_ids.is_empty(){return Err("请选择要导出或复制的内容。".into());}
    if choice.timeline&&!choice.transcript{return Err("分段时间和说话人需要同时选择录音文字。".into());}
    let ids:std::collections::HashSet<_>=choice.note_ids.iter().collect();
    if ids.len()!=choice.note_ids.len()||ids.len()>128 {return Err("所选材料重复或过多，请重新选择。".into());}
    if ids.iter().any(|id|!session.meeting_notes.iter().any(|note|&note.id==*id)){return Err("所选材料已不存在，请重新选择；未导出其他材料。".into());}
    let mut parts=Vec::new();
    if choice.minutes {parts.push(super::export::saved_minutes_markdown_for_mode(session,mode)?);}
    if choice.transcript {
        super::export::require_final_transcript(session)?;
        if !super::transcript_review::effective_unrecognized(session).is_empty(){
            parts.push("> 部分原音没有完整文字，以下仅为已保存内容，请回听原音核对。".into());
        }
        parts.push(format!("## 录音文字\n\n{}",super::transcript_review::effective_text(session)));
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
    if !matches!(format,Format::Markdown|Format::Txt|Format::Docx|Format::Pdf|Format::Mindmap|Format::Xlsx|Format::Srt){
        return Err("此格式不支持内容选择，请使用对应的完整数据或日历入口。".into());
    }
    if format==Format::Srt {
        if !choice.transcript||choice.minutes||choice.highlights||!choice.note_ids.is_empty(){return Err("字幕文件只包含有有效时间轴的录音文字，请取消其他内容。".into());}
        return super::export::prepare_meeting_export(session,mode,format);
    }
    let content=source(session,mode,choice)?;
    let bytes=match format {
        Format::Docx=>super::meeting_document_export::word(&session.title,&content)?,
        Format::Mindmap=>super::meeting_document_export::mindmap(&session.title,&content),
        Format::Xlsx=>super::spreadsheet_export::render(&session.title,&content)?,
        _=>content.into_bytes(),
    };
    Ok(PreparedMeetingExport{bytes,suggested_name:format!("{}-所选内容.{}",super::export::safe_file_stem(&session.title,&session.id),format.extension()),format,warning:None,calendar_items:None})
}

pub fn materialize(title:&str,prepared:PreparedMeetingExport)->Result<Vec<u8>,String>{
    if prepared.format==Format::Pdf {
        let text=std::str::from_utf8(&prepared.bytes).map_err(|_|"无法读取PDF正文。")?;
        super::pdf_export::render(title,text)
    }else{Ok(prepared.bytes)}
}

#[cfg(test)]
mod tests {
    use super::*;
    fn sample()->CompanionV1HostSession {
        let mut rows:Vec<CompanionV1HostSession>=serde_json::from_str(include_str!("../calendar_test_fixtures/p738-sessions.json")).unwrap();
        let mut row=rows.remove(0);row.transcript_text="李明：11月8日前核对20%差额，尚未确认采购。".into();row.transcript_final=true;
        row.meeting_notes=vec![super::super::meeting_notes::Note{id:"11111111-1111-4111-8111-111111111111".into(),text:"AI 材料（请核对）｜英语译文\nThe purchase has not been approved.\n原文依据：尚未确认采购。".into(),bookmark_id:None,created_at:"2026-11-05T00:00:00Z".into(),updated_at:"2026-11-05T00:00:00Z".into()},super::super::meeting_notes::Note{id:"22222222-2222-4222-8222-222222222222".into(),text:"UNSELECTED_PRIVATE_MATERIAL".into(),bookmark_id:None,created_at:"2026-11-05T00:00:00Z".into(),updated_at:"2026-11-05T00:00:00Z".into()}];row
    }
    #[test]
    fn content051_selection_is_identical_across_text_and_document_routes_without_unselected_data(){
        use std::io::{Cursor,Read};
        let row=sample();let before=serde_json::to_vec(&row).unwrap();
        let choice=Selection{minutes:false,transcript:true,highlights:false,timeline:false,note_ids:vec![row.meeting_notes[0].id.clone()]};
        let selected=source(&row,"offlineStore",&choice).unwrap();
        assert!(selected.contains("20%差额，尚未确认采购"));assert!(selected.contains("The purchase has not been approved."));assert!(!selected.contains("UNSELECTED_PRIVATE_MATERIAL"));
        for format in [Format::Txt,Format::Markdown,Format::Pdf] {
            let p=prepare(&row,"offlineStore",format,&choice).unwrap();assert_eq!(String::from_utf8(p.bytes).unwrap(),selected);
        }
        let p=prepare(&row,"offlineStore",Format::Docx,&choice).unwrap();
        let mut zip=zip::ZipArchive::new(Cursor::new(p.bytes)).unwrap();let mut xml=String::new();zip.by_name("word/document.xml").unwrap().read_to_string(&mut xml).unwrap();
        assert!(xml.contains("20%差额，尚未确认采购"));assert!(!xml.contains("UNSELECTED_PRIVATE_MATERIAL"));
        assert_eq!(serde_json::to_vec(&row).unwrap(),before);
        let mut missing=choice.clone();missing.note_ids.push("missing".into());assert!(prepare(&row,"offlineStore",Format::Txt,&missing).is_err());
        let empty=Selection{minutes:false,transcript:false,highlights:false,timeline:false,note_ids:vec![]};assert!(prepare(&row,"offlineStore",Format::Txt,&empty).is_err());
        let prepared=prepare(&row,"offlineStore",Format::Txt,&choice).unwrap();let hash=super::super::export::content_hash(&prepared);
        let mut changed=row.clone();changed.transcript_text.push_str("会后修订");assert!(super::super::export::require_unchanged(&prepare(&changed,"offlineStore",Format::Txt,&choice).unwrap(),Some(&hash)).is_err());
    }
    #[test]
    fn content051_can_export_a_saved_material_without_ai_minutes_or_audio(){
        let mut row=sample();row.minutes=None;row.minutes_by_mode.offline_store=None;row.minutes_by_mode.online_live=None;row.transcript_text.clear();row.transcript_final=false;
        let choice=Selection{minutes:false,transcript:false,highlights:false,timeline:false,note_ids:vec![row.meeting_notes[0].id.clone()]};
        for f in [Format::Txt,Format::Markdown,Format::Docx,Format::Pdf,Format::Xlsx,Format::Mindmap]{assert!(prepare(&row,"offlineStore",f,&choice).is_ok());}
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
        for (label,choice) in [("transcript",Selection{minutes:false,transcript:true,highlights:false,timeline:false,note_ids:vec![]}),
            ("material",Selection{minutes:false,transcript:false,highlights:false,timeline:false,note_ids:vec![row.meeting_notes[0].id.clone()]})]{
            let expected=source(&row,"offlineStore",&choice).unwrap();
            for format in [Format::Txt,Format::Markdown,Format::Docx,Format::Pdf,Format::Xlsx,Format::Mindmap]{
                let prepared=prepare(&row,"offlineStore",format,&choice).unwrap();let file=format!("{label}.{}",format.extension());
                let bytes=materialize(&row.title,prepared).unwrap();std::fs::write(root.join(&file),&bytes).unwrap();
                manifest.push(serde_json::json!({"file":file,"selectedText":expected,"title":row.title,"bytes":bytes.len()}));
            }
        }
        let srt=prepare(&row,"offlineStore",Format::Srt,&Selection{minutes:false,transcript:true,highlights:false,timeline:true,note_ids:vec![]}).unwrap();
        std::fs::write(root.join("transcript.srt"),srt.bytes).unwrap();
        std::fs::write(root.join("manifest.json"),serde_json::to_vec_pretty(&manifest).unwrap()).unwrap();
        println!("CONTENT051_EXTERNAL_FILES={}",root.display());
    }
}
