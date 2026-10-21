//! Exact-selection batch export. A fresh directory is published only after every
//! selected recording succeeds; this is an export, not a restorable library backup.
use std::{collections::HashSet, fs, path::{Path, PathBuf}};
use serde::{Deserialize, Serialize};
use crate::companion_v1::CompanionV1Snapshot;
use super::{audio_export, audio_storage, export, library_organization::Target};

#[derive(Clone, Copy, Debug, Deserialize, Serialize)]
#[serde(rename_all="lowercase")]
pub enum Format { Audio, Txt, Json, Markdown, Srt }
#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all="camelCase", deny_unknown_fields)]
pub struct Request {
    pub targets: Vec<Target>,
    pub format: Format,
    #[serde(default)] pub meeting_mode: Option<String>,
}
#[derive(Debug, Serialize)]
#[serde(rename_all="camelCase")]
pub struct Report { pub path: String, pub sessions: usize, pub files: usize, pub bytes: u64 }
#[derive(Serialize)]
#[serde(rename_all="camelCase")]
struct Entry {
    session_id: String, title: String, started_at: Option<String>, duration_ms: u64,
    organization: super::library_organization::Metadata,
    meeting_mode: String, file: String, bytes: u64, sha256: String,
}
enum Content { Audio(PathBuf), Document(Vec<u8>) }
struct Plan { entry: Entry, content: Content }

fn plans(snapshot: &CompanionV1Snapshot, request: &Request) -> Result<Vec<Plan>, String> {
    if snapshot.meeting.active || snapshot.device.recording || snapshot.host.sessions.iter().any(|s|s.status=="recording") {
        return Err("请先结束并保存录音，再批量导出。".into());
    }
    if request.targets.is_empty() || request.targets.len()>1000 { return Err("请选择1到1000场录音。".into()); }
    if request.meeting_mode.as_deref().is_some_and(|m|!matches!(m,"recorded"|"offlineStore"|"onlineLive")) {
        return Err("请选择原录音模式、离线纪要或在线纪要。".into());
    }
    let mut seen=HashSet::new();
    request.targets.iter().enumerate().map(|(index,target)| {
        if !seen.insert(&target.session_id) { return Err("批量选择包含重复录音，未导出。".into()); }
        let row=snapshot.host.sessions.iter().find(|s|s.id==target.session_id).ok_or("所选录音已移除，请刷新后核对。")?;
        super::library_lifecycle::require_available(row)?;
        if row.organization.revision!=target.expected_revision { return Err(format!("“{}”的分类已变化，请刷新选择后重试；整批未导出。",row.title)); }
        if matches!(row.recovery.stage.as_str(),"transcribing"|"generatingMinutes") { return Err(format!("“{}”仍在处理，请完成后导出。",row.title)); }
        let mode=match request.meeting_mode.as_deref() {None|Some("recorded")=>row.meeting_mode.as_str(),Some(m)=>m};
        let (content,extension)=match request.format {
            Format::Audio=>(Content::Audio(audio_export::source(snapshot,&row.id).map_err(|e|format!("“{}”：{e}",row.title))?.0),"wav"),
            format=>{
                let format=match format { Format::Txt=>export::MeetingExportFormat::Txt,Format::Json=>export::MeetingExportFormat::Json,
                    Format::Markdown=>export::MeetingExportFormat::Markdown,Format::Srt=>export::MeetingExportFormat::Srt,Format::Audio=>unreachable!() };
                let prepared=export::prepare_meeting_export(row,mode,format).map_err(|e|format!("“{}”：{e}；整批未导出。",row.title))?;
                (Content::Document(prepared.bytes),format.extension())
            }
        };
        // The ordinal disambiguates equal titles and Windows case folding; no ID
        // or virtual folder supplied by the user becomes a directory component.
        let title=export::safe_file_stem(&row.title,&row.id).chars().take(48).collect::<String>();
        let file=format!("{:04}-{title}.{extension}",index+1);
        Ok(Plan{entry:Entry{session_id:row.id.clone(),title:row.title.clone(),started_at:row.started_at.clone(),duration_ms:row.duration_ms,
            organization:row.organization.clone(),meeting_mode:mode.into(),file,bytes:0,sha256:String::new()},content})
    }).collect()
}

pub fn validate(snapshot: &CompanionV1Snapshot, request: &Request) -> Result<(),String> { plans(snapshot,request).map(|_|()) }

pub fn save(snapshot: &CompanionV1Snapshot, request: &Request, parent: &Path) -> Result<Report,String> {
    let mut plans=plans(snapshot,request)?;
    let parent=parent.canonicalize().map_err(|e|format!("无法打开导出目录：{e}"))?;
    if !parent.is_dir() { return Err("请选择本机导出目录。".into()); }
    let path_text=parent.to_string_lossy().to_ascii_lowercase();
    if path_text.starts_with("\\\\?\\unc\\") || (path_text.starts_with("\\\\")&&!path_text.starts_with("\\\\?\\")) {
        return Err("请先导出到本机目录，再按需要分享。".into());
    }
    let nonce=uuid::Uuid::new_v4();
    let staging=parent.join(format!(".companion-export-{nonce}.pending"));
    let destination=parent.join(format!("Companion-export-{nonce}"));
    fs::create_dir(&staging).map_err(|e|format!("无法创建导出目录：{e}"))?;
    let result=(|| {
        let mut bytes=0u64;
        for plan in &mut plans {
            let file=staging.join(&plan.entry.file);
            match &plan.content {
                Content::Audio(source)=>{audio_export::copy_atomic(source,&file)?;},
                Content::Document(content)=>{export::write_atomic(&file,content)?;},
            }
            let (length,hash)=audio_storage::fingerprint(&file)?;
            plan.entry.bytes=length;plan.entry.sha256=hash;bytes=bytes.checked_add(length).ok_or("导出容量溢出。")?;
        }
        let manifest=serde_json::to_vec_pretty(&serde_json::json!({
            "schema":"companion.library.export.v1","restorableBackup":false,"format":request.format,
            "entries":plans.iter().map(|p|&p.entry).collect::<Vec<_>>()
        })).map_err(|e|e.to_string())?;
        bytes+=export::write_atomic(&staging.join("manifest.json"),&manifest)?;
        // UUID destination is new. A collision is an error, never replacement.
        if destination.exists() { return Err("导出目录已存在，请重试。".into()); }
        fs::rename(&staging,&destination).map_err(|e|format!("导出尚未提交：{e}"))?;
        Ok(Report{path:destination.to_string_lossy().into(),sessions:plans.len(),files:plans.len()+1,bytes})
    })();
    if result.is_err() {
        // Only the fresh private staging directory created above is removable.
        let _=fs::remove_dir_all(&staging);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    fn setup()->(CompanionV1Snapshot,PathBuf) {
        let root=std::env::temp_dir().join(format!("companion-batch-export-{}",uuid::Uuid::new_v4()));fs::create_dir(&root).unwrap();
        let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap()).unwrap();
        let mut a=snapshot.host.sessions[0].clone();a.id="one".into();a.title="同名/访谈".into();a.organization.folder="项目/访谈".into();
        let mut b=a.clone();b.id="two".into();snapshot.host.sessions=vec![a,b];snapshot.device.recording=false;snapshot.meeting.active=false;(snapshot,root)
    }
    fn request(snapshot:&CompanionV1Snapshot,format:&str)->Request {
        serde_json::from_value(serde_json::json!({"targets":snapshot.host.sessions.iter().map(|s|serde_json::json!({"sessionId":s.id,"expectedRevision":s.organization.revision})).collect::<Vec<_>>(),"format":format})).unwrap()
    }
    #[test]
    fn same_title_exact_selection_manifest_hashes_and_original_index_unchanged() {
        let (snapshot,root)=setup();let before=serde_json::to_vec(&snapshot).unwrap();
        let report=save(&snapshot,&request(&snapshot,"json"),&root).unwrap();assert_eq!(report.sessions,2);assert_eq!(report.files,3);
        let dir=PathBuf::from(&report.path);let manifest:serde_json::Value=serde_json::from_slice(&fs::read(dir.join("manifest.json")).unwrap()).unwrap();
        assert_eq!(manifest["restorableBackup"],false);let entries=manifest["entries"].as_array().unwrap();assert_eq!(entries.len(),2);
        assert_ne!(entries[0]["file"],entries[1]["file"]);
        for entry in entries {let file=dir.join(entry["file"].as_str().unwrap());let (bytes,hash)=audio_storage::fingerprint(&file).unwrap();
            assert_eq!(entry["sha256"],hash);assert_eq!(entry["bytes"],bytes);assert_eq!(entry["organization"]["folder"],"项目/访谈");}
        assert_eq!(serde_json::to_vec(&snapshot).unwrap(),before);fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn stale_missing_duplicate_unready_and_invalid_destination_leave_no_partial_exports() {
        let (mut snapshot,root)=setup();
        let mut req=request(&snapshot,"txt");req.targets[1].expected_revision=99;assert!(save(&snapshot,&req,&root).is_err());
        req=request(&snapshot,"json");req.targets[1].session_id="missing".into();assert!(save(&snapshot,&req,&root).is_err());
        req=request(&snapshot,"json");req.targets[1].session_id=req.targets[0].session_id.clone();assert!(save(&snapshot,&req,&root).is_err());
        req=request(&snapshot,"audio");assert!(save(&snapshot,&req,&root).is_err());
        snapshot.host.sessions[1].transcript_text.clear();snapshot.host.sessions[1].transcript_final=false;
        assert!(save(&snapshot,&request(&snapshot,"txt"),&root).is_err());assert_eq!(fs::read_dir(&root).unwrap().count(),0);
        let mut empty=request(&snapshot,"json");empty.targets.clear();assert!(save(&snapshot,&empty,&root).is_err());
        fs::remove_dir_all(root).unwrap();
    }
}
