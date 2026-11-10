//! Portable meeting library backup. Data and audio remain local.
use std::{collections::HashSet,fs::{self,File,OpenOptions},io::{Read,Write},path::{Path,PathBuf}};
use serde::{Deserialize,Serialize};
use sha2::{Digest,Sha256};
use crate::companion_v1::{CompanionV1HostSession,CompanionV1Snapshot};
use super::audio_artifacts::{self,BackupFile,Purpose};
const SCHEMA:&str="companion.library.backup.v1";

#[derive(Serialize,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Manifest { schema:String, sessions:Vec<CompanionV1HostSession>, files:Vec<BackupFile> }
#[derive(Clone,Debug,Serialize,Deserialize,PartialEq,Eq)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct TemplateDraft {pub name:String,pub instructions:String}
#[derive(Serialize,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct TemplateSidecar {schema:String,templates:Vec<TemplateDraft>}
#[derive(Serialize)]
#[serde(rename_all="camelCase")]
pub struct Report {pub path:String,pub sessions:usize,pub files:usize,pub bytes:u64}

fn leaf(raw:&str,root:&Path)->Result<String,String>{
    let p=Path::new(raw);if !p.is_absolute(){return Err("会议音频路径不完整，请先恢复后备份。".into());}
    let parent=p.parent().ok_or("录音位置不可用。")?.canonicalize().map_err(|_|"录音目录不可用。")?;
    if parent!=root{return Err("有录音不在本机录音目录，请先迁移或恢复后备份。".into());}
    let name=p.file_name().and_then(|s|s.to_str()).filter(|s|valid_leaf(s)).ok_or("录音文件名不可备份。")?;
    Ok(name.into())
}
fn valid_leaf(s:&str)->bool{
    if s.is_empty()||s=="."||s==".."||s.ends_with([' ','.'])
        ||s.chars().any(|c|c.is_control()||matches!(c,'/'|'\\'|':'|'<'|'>'|'"'|'|'|'?'|'*'))
        ||s.to_ascii_lowercase().starts_with(".audio-artifact")
        ||Path::new(s).file_name().and_then(|v|v.to_str())!=Some(s){return false;}
    let base=s.split('.').next().unwrap_or("").to_ascii_uppercase();
    if matches!(base.as_str(),"CON"|"PRN"|"AUX"|"NUL") {return false;}
    if base.len()==4 && (base.starts_with("COM")||base.starts_with("LPT"))
        && matches!(base.as_bytes()[3],b'1'..=b'9'){return false;}
    true
}
fn virtual_path(s:&str)->bool{s.starts_with("board://")||s.starts_with("device://")||s.starts_with("host://")}
fn fingerprint(path:&Path)->Result<(u64,String),String>{super::audio_storage::fingerprint(path)}
fn copy_verified(source:&Path,dest:&Path,expected:&(u64,String))->Result<(),String>{
    let meta=fs::symlink_metadata(source).map_err(|_|"备份文件无法读取。")?;
    if !meta.is_file()||meta.file_type().is_symlink(){return Err("备份文件不是普通文件。".into());}
    let mut input=File::open(source).map_err(|e|format!("无法读取备份来源：{e}"))?;
    let mut output=OpenOptions::new().write(true).create_new(true).open(dest).map_err(|e|format!("无法写入备份：{e}"))?;
    let mut hash=Sha256::new();let mut total=0u64;let mut block=[0u8;65536];
    loop{let n=input.read(&mut block).map_err(|e|e.to_string())?;if n==0{break;}total=total.checked_add(n as u64).ok_or("备份文件过大。")?;
        if total>expected.0{return Err("录音在备份期间发生变化。".into());}hash.update(&block[..n]);output.write_all(&block[..n]).map_err(|e|e.to_string())?;}
    output.sync_all().map_err(|e|e.to_string())?;drop(output);
    if (total,format!("{:x}",hash.finalize()))!=*expected||fingerprint(source)?!=*expected{return Err("录音在备份期间发生变化，请重试。".into());}
    Ok(())
}
fn pack_rows(snapshot:&CompanionV1Snapshot,root:&Path)->Result<(Vec<CompanionV1HostSession>,Vec<BackupFile>),String>{
    if snapshot.host.persistence.status!="ready"||snapshot.meeting.active||snapshot.device.recording||snapshot.host.sessions.iter().any(|s|s.status=="recording"||matches!(s.recovery.stage.as_str(),"transcribing"|"generatingMinutes")){
        return Err("请先完成录音和正在进行的整理，并保存会议库。".into());
    }
    let mut rows=snapshot.host.sessions.clone();let mut anchors=Vec::new();let mut imported_names=HashSet::new();
    for row in &rows {
        if !row.document_context.is_empty(){anchors.push(super::document_context::owner_path(row,root).to_string_lossy().into_owned());}
        if row.source=="importedAudio" && row.audio_stored {
            let original=super::import_audio::verify_original(row,root)?;
            imported_names.insert(leaf(&original.to_string_lossy(),root)?.to_lowercase());
        }
        if !row.audio_stored && row.device_recording_id.is_some() && !row.device_reclaimed {return Err(format!("“{}”的录音还在设备中，请先同步再备份。",row.title));}
        if row.audio_stored && !row.retention.audio_cached{return Err(format!("“{}”的录音状态未完成，请先恢复。",row.title));}
        for raw in row.audio_path.iter().chain(row.chunks.iter().filter_map(|c|c.path.as_ref()))
            .chain(row.meeting_tracks.iter().flat_map(|tracks| tracks.microphone.iter().chain(&tracks.system).map(|part| &part.path))) {
            if virtual_path(raw){if row.audio_stored{return Err("录音尚未保存到电脑，请先同步。".into());}continue;}
            leaf(raw,root)?;anchors.push(raw.clone());
        }
        if let Some(tracks)=&row.meeting_tracks {
            if row.source!="hostMeeting" {return Err("会议音轨来源无效，请先恢复。".into());}
            if !row.audio_stored {return Err(format!("“{}”的会议音轨尚未恢复，请先恢复后备份。",row.title));}
            leaf(&tracks.root,root)?;
            if row.audio_stored {super::meeting_audio_recovery::verify_tracks(tracks,row.audio_bytes,row.duration_ms)?;}
        } else if row.source=="hostMeeting" && row.audio_stored {return Err("会议音轨缺失，请先恢复。".into());}
        if row.audio_stored && row.source!="hostMeeting" {
            let path=row.audio_path.as_deref().ok_or("录音文件缺失，请先恢复。")?;
            super::meeting_workspace::validate_wav(Path::new(path)).map_err(|_|format!("“{}”的回听音频不完整，请先恢复后备份。",row.title))?;
        }
    }
    anchors.sort();anchors.dedup();let mut files=audio_artifacts::backup_files_at(root,&anchors)?;
    let mut names=files.iter().map(|f|f.file.to_lowercase()).collect::<HashSet<_>>();
    // Older, indexed WAVs may predate the ownership manifest. The exact index
    // is the authority; no directory scan or inferred sibling is performed.
    for raw in &anchors {let name=leaf(raw,root)?;if names.contains(&name.to_lowercase()){continue;}
        let path=root.join(&name);let (bytes,sha256)=fingerprint(&path)?;
        let purpose=if imported_names.contains(&name.to_lowercase()){Purpose::ImportedOriginal}
            else if name.to_lowercase().ends_with(".wav"){Purpose::Recording}
            else if name.to_lowercase().ends_with(".opus"){Purpose::CompressedOriginal}
            else if name.to_lowercase().ends_with(".json"){Purpose::SessionReceipt}
            else{return Err("录音包含尚不支持备份的文件类型。".into());};
        files.push(BackupFile{file:name.clone(),sources:vec![name.clone()],purpose,bytes,sha256});names.insert(name.to_lowercase());
    }
    if files.iter().any(|f|f.sources.iter().any(|s|!names.contains(&s.to_lowercase()))) {
        return Err("录音文件的关联信息尚不完整，请先恢复录音后再备份。".into());
    }
    for row in &mut rows {
        for path in row.audio_path.iter_mut().chain(row.chunks.iter_mut().filter_map(|c|c.path.as_mut())){
            if !virtual_path(path){*path=leaf(path,root)?;}
        }
        if let Some(tracks)=&mut row.meeting_tracks {
            tracks.root=leaf(&tracks.root,root)?;
            for part in tracks.microphone.iter_mut().chain(&mut tracks.system) {part.path=leaf(&part.path,root)?;}
        }
    }
    Ok((rows,files))
}

/// Writes a fresh self-contained directory; it never replaces an existing backup.
pub fn save(snapshot:&CompanionV1Snapshot,recording_root:&Path,parent:&Path)->Result<Report,String>{
    save_with_templates(snapshot,recording_root,parent,&[])
}
fn save_with_templates(snapshot:&CompanionV1Snapshot,recording_root:&Path,parent:&Path,templates:&[TemplateDraft])->Result<Report,String>{
    if snapshot.host.persistence.status!="ready"||snapshot.meeting.active||snapshot.device.recording||snapshot.host.sessions.iter().any(|s|s.status=="recording"||matches!(s.recovery.stage.as_str(),"transcribing"|"generatingMinutes")){
        return Err("请先完成录音和正在进行的整理，并保存会议库。".into());
    }
    let root=recording_root.canonicalize().map_err(|_|"录音目录不可用。")?;
    let parent=parent.canonicalize().map_err(|_|"请选择备份目录。")?;
    // The grouped receiver validates all compressed originals, timeline and
    // playback parts before we represent a board session as backed up.
    for row in &snapshot.host.sessions {
        if row.audio_stored { super::host_segmented_capture::saved_parts(row)?; }
        if row.audio_stored && row.device_recording_key.is_some(){
            super::recording_wire::receiver::Receiver::verified_audio_parts(row)
                .map_err(|_|format!("“{}”的录音分段不完整，请先恢复或同步后备份。",row.title))?;
        }
    }
    let mut paths=snapshot.host.sessions.iter().flat_map(|s|s.audio_path.iter().chain(s.chunks.iter().filter_map(|c|c.path.as_ref()))
        .chain(s.meeting_tracks.iter().flat_map(|tracks|tracks.microphone.iter().chain(&tracks.system).map(|part|&part.path))))
        .filter(|p|!virtual_path(p)).cloned().collect::<Vec<_>>();
    paths.sort();paths.dedup();
    let _usage=paths.iter().map(|p|audio_artifacts::usage(Path::new(p))).collect::<Result<Vec<_>,_>>()?;
    let (sessions,files)=pack_rows(snapshot,&root)?;
    let count=files.len();
    let id=uuid::Uuid::new_v4();let pending=parent.join(format!(".companion-backup-{id}.pending"));let final_path=parent.join(format!("Companion-backup-{id}"));
    fs::create_dir(&pending).map_err(|e|format!("无法创建备份：{e}"))?;
    let result=(||{
        let data=pending.join("files");fs::create_dir(&data).map_err(|e|e.to_string())?;let mut bytes=0u64;
        for (i,item) in files.iter().enumerate(){copy_verified(&root.join(&item.file),&data.join(i.to_string()),&(item.bytes,item.sha256.clone()))?;bytes=bytes.checked_add(item.bytes).ok_or("备份容量无效。")?;}
        if !templates.is_empty() {
            let contents=serde_json::to_vec_pretty(&TemplateSidecar{schema:"companion.minutes.templates.v1".into(),templates:templates.to_vec()}).map_err(|e|e.to_string())?;
            if contents.len()>8*1024*1024{return Err("自定义模板过大，无法备份。".into());}
            let mut file=OpenOptions::new().write(true).create_new(true).open(pending.join("minutes-templates.json")).map_err(|e|e.to_string())?;
            file.write_all(&contents).and_then(|_|file.sync_all()).map_err(|e|e.to_string())?;bytes+=contents.len() as u64;
        }
        let manifest=serde_json::to_vec_pretty(&Manifest{schema:SCHEMA.into(),sessions,files}).map_err(|e|e.to_string())?;
        let mut file=OpenOptions::new().write(true).create_new(true).open(pending.join("manifest.json")).map_err(|e|e.to_string())?;
        file.write_all(&manifest).and_then(|_|file.sync_all()).map_err(|e|e.to_string())?;drop(file);bytes+=manifest.len() as u64;
        if final_path.exists(){return Err("备份目录已存在，请重试。".into());}fs::rename(&pending,&final_path).map_err(|e|format!("备份未完成：{e}"))?;
        Ok(Report{path:final_path.to_string_lossy().into(),sessions:snapshot.host.sessions.len(),files:count,bytes})
    })();
    if result.is_err(){let _=fs::remove_dir_all(&pending);}result
}

pub(crate) fn save_product(snapshot:&CompanionV1Snapshot,parent:&Path)->Result<Report,String>{
    save(snapshot,&super::audio_storage::recording_root()?,parent)
}
pub(crate) fn save_product_with_templates(snapshot:&CompanionV1Snapshot,parent:&Path,templates:&[TemplateDraft])->Result<Report,String>{
    save_with_templates(snapshot,&super::audio_storage::recording_root()?,parent,templates)
}
/// An absent sidecar means an older backup; damaged optional templates do not
/// prevent the user from recovering the original recordings and meetings.
pub(crate) fn read_templates(archive:&Path)->Result<Vec<TemplateDraft>,String>{
    let path=archive.join("minutes-templates.json");
    let meta=match fs::symlink_metadata(&path){Ok(m)=>m,Err(e) if e.kind()==std::io::ErrorKind::NotFound=>return Ok(vec![]),Err(_)=>return Err("备份中的自定义模板无法读取。".into())};
    if !meta.is_file()||meta.file_type().is_symlink()||meta.len()>8*1024*1024{return Err("备份中的自定义模板无效。".into());}
    let sidecar:TemplateSidecar=serde_json::from_reader(File::open(path).map_err(|_|"备份中的自定义模板无法读取。")?).map_err(|_|"备份中的自定义模板无效。")?;
    if sidecar.schema!="companion.minutes.templates.v1" {return Err("备份中的自定义模板版本不受支持。".into());}
    Ok(sidecar.templates)
}

pub(crate) fn check_conflicts(archive:&Path,existing:&[CompanionV1HostSession])->Result<(),String>{
    let manifest=read_manifest(&archive.join("manifest.json"))?;
    if let Some(duplicate)=manifest.sessions.iter().find(|row|existing.iter().any(|e|e.id==row.id)) {
        return Err(format!("本机已有“{}”，未覆盖；请先处理重复会议。",duplicate.title));
    }
    Ok(())
}

/// Retry only the optional templates when every meeting in this backup is
/// already present. Never overwrite or treat a partial collision as restored.
pub(crate) fn all_sessions_present(archive:&Path,existing:&[CompanionV1HostSession])->Result<bool,String>{
    let manifest=read_manifest(&archive.join("manifest.json"))?;
    let ids:HashSet<&str>=existing.iter().map(|row|row.id.as_str()).collect();
    Ok(!manifest.sessions.is_empty() && manifest.sessions.iter().all(|row|ids.contains(row.id.as_str())))
}

fn read_manifest(path:&Path)->Result<Manifest,String>{
    let meta=fs::symlink_metadata(path).map_err(|_|"备份清单无法读取。")?;
    if !meta.is_file()||meta.file_type().is_symlink()||meta.len()>64*1024*1024{return Err("备份清单无效。".into());}
    let manifest:Manifest=serde_json::from_reader(File::open(path).map_err(|e|e.to_string())?).map_err(|_|"备份清单格式无效。")?;
    if manifest.schema!=SCHEMA{return Err("此备份格式不受支持。".into());}
    let mut names=HashSet::new();
    for item in &manifest.files {
        if !valid_leaf(&item.file)||!names.insert(item.file.to_lowercase())||item.sources.is_empty()||item.sources.len()>1024
            ||item.sources.iter().any(|s|!valid_leaf(s))||!item.purpose.accepts(Path::new(&item.file))
            ||item.sha256.len()!=64||!item.sha256.bytes().all(|b|b.is_ascii_hexdigit()) {
            return Err("备份文件清单无效。".into());
        }
    }
    if manifest.files.iter().any(|f|f.sources.iter().any(|s|!names.contains(&s.to_lowercase()))) {
        return Err("备份的录音关联无效。".into());
    }
    let mut ids=HashSet::new();
    for row in &manifest.sessions {
        if row.id.trim().is_empty()||!ids.insert(&row.id)||row.status=="recording" {return Err("备份的会议身份或状态无效。".into());}
        for p in row.audio_path.iter().chain(row.chunks.iter().filter_map(|c|c.path.as_ref()))
            .chain(row.meeting_tracks.iter().flat_map(|tracks|tracks.microphone.iter().chain(&tracks.system).map(|part|&part.path))) {
            if !virtual_path(p)&&(!valid_leaf(p)||!names.contains(&p.to_lowercase())) {return Err("备份缺少会议所需的录音文件。".into());}
        }
        if row.source=="importedAudio" && row.audio_stored {
            let original=super::import_audio::original_chunk(row)?;
            let path=original.path.as_deref().ok_or("备份缺少导入原文件。")?;
            let expected=original.id.rsplit('-').next().ok_or("备份原文件身份无效。")?;
            if !manifest.files.iter().any(|f|f.file==path && f.purpose==Purpose::ImportedOriginal && f.bytes==original.bytes && f.sha256==expected) {
                return Err("备份缺少完整的导入原文件。".into());
            }
        }
        if let Some(tracks)=&row.meeting_tracks {
            if row.source!="hostMeeting" || !valid_leaf(&tracks.root)
                || tracks.microphone.iter().chain(&tracks.system).any(|part|virtual_path(&part.path))
                || row.audio_stored && tracks.microphone.is_empty() && tracks.system.is_empty() {
                return Err("备份的会议音轨无效。".into());
            }
        } else if row.audio_stored && row.source=="hostMeeting" {return Err("备份缺少会议音轨。".into());}
        if row.audio_stored&&row.source!="hostMeeting"&&row.audio_path.as_deref().is_none_or(virtual_path){return Err("备份缺少会议录音。".into());}
    }
    Ok(manifest)
}

#[cfg(windows)]
fn publish_new(source:&Path,destination:&Path)->Result<(),String>{
    use std::os::windows::ffi::OsStrExt;
    use windows::{core::PCWSTR,Win32::Storage::FileSystem::{MoveFileExW,MOVEFILE_WRITE_THROUGH}};
    let from:Vec<u16>=source.as_os_str().encode_wide().chain(Some(0)).collect();
    let to:Vec<u16>=destination.as_os_str().encode_wide().chain(Some(0)).collect();
    unsafe{MoveFileExW(PCWSTR(from.as_ptr()),PCWSTR(to.as_ptr()),MOVEFILE_WRITE_THROUGH)}
        .map_err(|e|format!("无法保存恢复文件，已有文件未覆盖：{e}"))
}
#[cfg(not(windows))]
fn publish_new(source:&Path,destination:&Path)->Result<(),String>{
    fs::hard_link(source,destination).map_err(|e|format!("无法保存恢复文件：{e}"))?;
    fs::remove_file(source).map_err(|e|e.to_string())
}

/// Verify every archive member before publishing any restored recording.
/// Index publication is a separate locked operation after this returns.
pub(crate) fn restore_files(archive:&Path,root:&Path)->Result<Vec<CompanionV1HostSession>,String>{
    let archive=archive.canonicalize().map_err(|_|"备份目录不可用。")?;
    let root=root.canonicalize().map_err(|_|"录音目录不可用。")?;
    let directory=archive.join("files");
    if fs::symlink_metadata(&directory).map_err(|_|"备份文件目录不可用。")?.file_type().is_symlink()
        ||directory.canonicalize().map_err(|_|"备份文件目录不可用。")?!=directory {return Err("备份文件目录无效。".into());}
    let mut manifest=read_manifest(&archive.join("manifest.json"))?;
    for (index,item) in manifest.files.iter().enumerate(){
        let source=directory.join(index.to_string());
        let meta=fs::symlink_metadata(&source).map_err(|_|"备份文件缺失。")?;
        if !meta.is_file()||meta.file_type().is_symlink()||fingerprint(&source)?!=(item.bytes,item.sha256.clone()){
            return Err("备份文件缺失或校验失败，未恢复任何会议。".into());
        }
    }
    let managed=manifest.files.iter().filter(|item|item.purpose!=Purpose::ImportedOriginal).cloned().collect::<Vec<_>>();
    audio_artifacts::preflight_backup_targets(&root,&managed)?;
    // Check imported originals too before publishing any restored file.
    for item in manifest.files.iter().filter(|item|item.purpose==Purpose::ImportedOriginal) {
        let target=root.join(&item.file);
        match fs::symlink_metadata(&target) {
            Ok(meta) if !meta.is_file() || meta.file_type().is_symlink() || fingerprint(&target)?!=(item.bytes,item.sha256.clone()) => {
                return Err("本机已有不同的录音文件；原文件未覆盖。".into());
            }
            Ok(_) => {},
            Err(error) if error.kind()==std::io::ErrorKind::NotFound => {},
            Err(error) => return Err(format!("无法核对恢复位置：{error}")),
        }
    }
    for (index,item) in manifest.files.iter().enumerate(){
        let source=directory.join(index.to_string());let target=root.join(&item.file);
        let write=|| {
            if target.exists(){
                if fingerprint(&target)?==(item.bytes,item.sha256.clone()){return Ok(());}
                return Err("本机已有不同的录音文件；原文件未覆盖。".into());
            }
            let temp=root.join(format!(".companion-restore-{}.tmp",uuid::Uuid::new_v4()));
            let result=copy_verified(&source,&temp,&(item.bytes,item.sha256.clone())).and_then(|_|publish_new(&temp,&target));
            if result.is_err(){let _=fs::remove_file(&temp);}result
        };
        if item.purpose==Purpose::ImportedOriginal {write()?;} else {
            audio_artifacts::retry_absent_backup_file(&root,item)?;
            let owner=root.join(item.sources.first().ok_or("备份归属无效。")?);
            audio_artifacts::generated(&owner,&target,item.purpose,write)?;
        }
    }
    audio_artifacts::attach_backup_sources(&root,&managed)?;
    for row in &mut manifest.sessions {
        for path in row.audio_path.iter_mut().chain(row.chunks.iter_mut().filter_map(|c|c.path.as_mut())) {
            if !virtual_path(path){*path=root.join(&*path).to_string_lossy().into_owned();}
        }
        if let Some(tracks)=&mut row.meeting_tracks {
            tracks.root=root.join(&tracks.root).to_string_lossy().into_owned();
            for part in tracks.microphone.iter_mut().chain(&mut tracks.system) {part.path=root.join(&part.path).to_string_lossy().into_owned();}
            if row.audio_stored {super::meeting_audio_recovery::verify_tracks(tracks,row.audio_bytes,row.duration_ms)?;}
        }
        // Restoring a backup never grants new background processing consent.
        row.recovery=Default::default();row.processing_policy=crate::companion_v1::CompanionV1ProcessingPolicy::Manual;
    }
    Ok(manifest.sessions)
}

pub(crate) fn restore_index(index:&Path,rows:&[CompanionV1HostSession])->Result<(),String>{
    super::session_store::restore_backup(index,rows)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn template_drafts_roundtrip_without_changing_existing_backup_manifest() {
        let base=std::env::temp_dir().join(format!("companion-template-backup-{}",uuid::Uuid::new_v4()));
        let source=base.join("source");let target=base.join("target");let backups=base.join("backups");
        for path in [&source,&target,&backups]{fs::create_dir_all(path).unwrap();}
        let mut snapshot=crate::companion_v1::fixture_snapshot();snapshot.host.sessions.clear();
        snapshot.host.persistence.status="ready".into();snapshot.meeting.active=false;snapshot.device.recording=false;
        let drafts=vec![TemplateDraft{name:"项目会议".into(),instructions:"按项目整理".into()},TemplateDraft{name:"".into(),instructions:"未写完的要求".into()}];
        let report=save_with_templates(&snapshot,&source,&backups,&drafts).unwrap();let backup=Path::new(&report.path);
        assert_eq!(read_templates(backup).unwrap(),drafts);
        assert!(read_manifest(&backup.join("manifest.json")).is_ok(),"old manifest format must remain readable");
        assert!(restore_files(backup,&target).unwrap().is_empty());
        fs::write(backup.join("minutes-templates.json"),b"broken").unwrap();
        assert!(read_templates(backup).is_err());
        assert!(restore_files(backup,&target).unwrap().is_empty(),"damaged optional drafts must not block recordings");
        let older=save(&snapshot,&source,&backups).unwrap();assert!(read_templates(Path::new(&older.path)).unwrap().is_empty());
        fs::remove_dir_all(base).unwrap();
    }
    #[test]
    fn dual_track_meeting_backup_restores_both_sources_and_can_be_backed_up_again() {
        use crate::companion_v1::{CompanionV1MeetingTrackPart,CompanionV1MeetingTracks};
        use super::super::meeting_audio_tracks::TrackWriter;
        let base=std::env::temp_dir().join(format!("companion-two-track-backup-{}",uuid::Uuid::new_v4()));
        let source=base.join("source");let target=base.join("target");let backups=base.join("backups");
        for p in [&source,&target,&backups] {fs::create_dir_all(p).unwrap();}
        let source=source.canonicalize().unwrap();let target=target.canonicalize().unwrap();
        unsafe{std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&source)};
        let mut mic=TrackWriter::create_flat(&source,"meeting-mic",2).unwrap();mic.append(&[1,2,3]).unwrap();
        let mut system=TrackWriter::create_flat(&source,"meeting-system",2).unwrap();system.append(&[4,5,6]).unwrap();
        let convert=|parts:Vec<super::super::meeting_audio_tracks::TrackPart>|parts.into_iter().map(|p| CompanionV1MeetingTrackPart {
            path:p.path.to_string_lossy().into_owned(),first_sample:p.first_sample,samples:p.samples }).collect::<Vec<_>>();
        let microphone=convert(mic.finish().unwrap());let system=convert(system.finish().unwrap());
        let bytes=microphone.iter().chain(&system).map(|p|44+p.samples*2).sum();
        let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap()).unwrap();
        snapshot.host.persistence.status="ready".into();snapshot.meeting.active=false;snapshot.device.recording=false;
        let row=&mut snapshot.host.sessions[0];row.id="two-track-backup".into();row.source="hostMeeting".into();row.status="captured".into();
        row.audio_path=None;row.chunks.clear();row.audio_stored=true;row.retention.audio_cached=true;row.audio_bytes=bytes;row.duration_ms=0;
        row.meeting_tracks=Some(CompanionV1MeetingTracks {root:source.join("meeting").to_string_lossy().into_owned(),state:"captured".into(),microphone,system,discontinuity:true,issue:Some("采集时序提示".into())});
        let mix=base.join("meeting-mix.wav");
        assert_eq!(super::super::audio_export::export(&snapshot,"two-track-backup",&mix).unwrap(),50);
        let mixed=fs::read(&mix).unwrap();assert_eq!(&mixed[44..],&[2,0,3,0,4,0]);
        let original_path=PathBuf::from(snapshot.host.sessions[0].meeting_tracks.as_ref().unwrap().microphone[0].path.clone());
        let original=fs::read(&original_path).unwrap();
        assert!(super::super::audio_export::export(&snapshot,"two-track-backup",&original_path).is_err());assert_eq!(fs::read(original_path).unwrap(),original);
        let report=save(&snapshot,&source,&backups).unwrap();assert_eq!(report.files,4);
        let saved=read_manifest(&Path::new(&report.path).join("manifest.json")).unwrap();
        assert_eq!(saved.sessions[0].meeting_tracks.as_ref().unwrap().root,"meeting");
        unsafe{std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&target)};
        let rows=restore_files(Path::new(&report.path),&target).unwrap();let row=&rows[0];let tracks=row.meeting_tracks.as_ref().unwrap();
        assert_eq!(tracks.microphone.len(),2);assert_eq!(tracks.system.len(),2);assert!(tracks.root.starts_with(target.to_str().unwrap()));
        assert_eq!(tracks.issue.as_deref(),Some("采集时序提示"));
        super::super::meeting_audio_recovery::verify_tracks(tracks,row.audio_bytes,row.duration_ms).unwrap();
        let mut restored=snapshot.clone();restored.host.sessions=rows;
        assert_eq!(save(&restored,&target,&backups).unwrap().files,4);
        unsafe{std::env::remove_var("COMPANION_TYPE_RECORDING_DIR")};fs::remove_dir_all(base).unwrap();
    }
    #[test]
    fn recovered_interrupted_meeting_can_be_backed_up_and_restored() {
        let base=std::env::temp_dir().join(format!("companion-recovered-backup-{}",uuid::Uuid::new_v4()));
        let source=base.join("source"); let target=base.join("target"); let backups=base.join("backups");
        for path in [&source,&target,&backups] { fs::create_dir_all(path).unwrap(); }
        let source=source.canonicalize().unwrap(); let target=target.canonicalize().unwrap();
        unsafe { std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&source); }
        let original=source.join("interrupted.wav");
        let lease=audio_artifacts::WriteLease::begin(&original,&original,Purpose::Recording).unwrap();
        let mut raw=denzic_host_audio_v1_core::wav::wav_header(0).to_vec();
        raw.extend_from_slice(&[1,2,3,4,5,6,7,8]); fs::write(&original,&raw).unwrap(); drop(lease);
        let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            crate::control_request(crate::companion_v1::CompanionV1ControlAction::MeetingStart,Some("recover-and-backup".into()))).unwrap();
        let mut row=snapshot.host.sessions.remove(0);row.id="recover-and-backup".into();row.source="hostMicrophone".into();
        row.status="recording".into();row.audio_path=Some(original.to_string_lossy().into());row.audio_stored=false;row.chunks.clear();
        row.transcript_text="之前保存的文字".into();
        let state=base.join("sessions.json");super::super::persistence::save_sessions_to(&state,&[row.clone()]).unwrap();
        let expected=super::super::session_store::privacy_authorization(&row).unwrap();
        super::super::host_interrupted_recovery::recover_session_at(&state,&row.id,&expected).unwrap();
        row=super::super::persistence::load_sessions_from(&state).unwrap().remove(0);
        let recovered=PathBuf::from(row.audio_path.as_ref().unwrap());
        let recovered_bytes=fs::read(&recovered).unwrap();assert_eq!(&recovered_bytes[44..],&raw[44..]);
        snapshot.host.sessions=vec![row];snapshot.host.persistence.status="ready".into();snapshot.meeting.active=false;snapshot.device.recording=false;
        let report=save(&snapshot,&source,&backups).expect("a recovered meeting must remain backupable");
        assert_eq!(report.files,2); assert_eq!(fs::read(&original).unwrap(),raw);
        fs::write(&original,b"changed interrupted original").unwrap();
        assert!(save(&snapshot,&source,&backups).is_err(),"a changed original cannot silently enter the backup");
        fs::write(&original,&raw).unwrap();
        unsafe { std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&target); }
        let restored=restore_files(Path::new(&report.path),&target).unwrap();
        restore_index(&base.join("restored.json"),&restored).unwrap();
        assert_eq!(restored[0].transcript_text,"之前保存的文字");
        assert_eq!(fs::read(restored[0].audio_path.as_ref().unwrap()).unwrap(),recovered_bytes);
        assert_eq!(fs::read(target.join("interrupted.wav")).unwrap(),raw);
        let backed_up_again=save(&{let mut s=snapshot.clone();s.host.sessions=restored;s},&target,&backups).unwrap();
        assert_eq!(backed_up_again.files,2);
        unsafe { std::env::remove_var("COMPANION_TYPE_RECORDING_DIR"); }
        fs::remove_dir_all(base).unwrap();
    }
    #[test]
    fn backup_restore_preserves_owned_files_and_rejects_damage_or_collisions(){
        let base=std::env::temp_dir().join(format!("companion-library-backup-test-{}",uuid::Uuid::new_v4()));
        let source=base.join("source");let target=base.join("target");let backups=base.join("backups");
        for p in [&source,&target,&backups]{fs::create_dir_all(p).unwrap();}
        let source=source.canonicalize().unwrap();let target=target.canonicalize().unwrap();
        // This filtered test runs in its own process and owns the entire root.
        unsafe{std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&target)};
        let wav=source.join("recording.wav");let opus=source.join("recording-original.opus");let receipt=source.join(".recording-receipt.json");
        let mut sound=denzic_host_audio_v1_core::wav::wav_header(8).to_vec();sound.extend_from_slice(&[0,1,2,3,4,5,6,7]);
        fs::write(&wav,&sound).unwrap();fs::write(&opus,b"fictional compressed recording").unwrap();fs::write(&receipt,b"fictional receipt").unwrap();
        let key=audio_artifacts::reference_key(&wav).unwrap();
        let files=[(&wav,"recording"),(&opus,"compressedOriginal"),(&receipt,"sessionReceipt")].iter().map(|(p,purpose)|{
            let (bytes,sha)=fingerprint(p).unwrap();serde_json::json!({"file":p.file_name().unwrap().to_str().unwrap(),"sources":[key],"purpose":purpose,"phase":"sealed","identity":{"bytes":bytes,"sha256":sha}})
        }).collect::<Vec<_>>();
        fs::write(source.join(".audio-artifacts.json"),serde_json::to_vec(&serde_json::json!({"schema":1,"files":files})).unwrap()).unwrap();
        let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap()).unwrap();
        snapshot.host.persistence.status="ready".into();snapshot.meeting.active=false;snapshot.device.recording=false;
        let row=&mut snapshot.host.sessions[0];row.id="backup-original".into();row.status="minutesReady".into();row.source="hostMicrophone".into();
        row.audio_path=Some(wav.to_string_lossy().into());row.audio_bytes=sound.len() as u64;row.audio_stored=true;row.retention.audio_cached=true;
        row.chunks.clear();row.chunks.push(crate::companion_v1::CompanionV1AudioChunk{id:"chunk".into(),path:row.audio_path.clone(),started_at:None,stopped_at:None,duration_ms:1,bytes:sound.len() as u64,status:"sealed".into()});
        row.transcript_text="虚构会议：周五前报价".into();row.transcript_final=true;
        let report=save(&snapshot,&source,&backups).unwrap();assert_eq!(report.files,3);
        let backup_for_retry=Path::new(&report.path);
        assert!(all_sessions_present(backup_for_retry,&snapshot.host.sessions).unwrap());
        assert!(!all_sessions_present(backup_for_retry,&[]).unwrap());
        let two_dir=base.join("two-session-manifest");fs::create_dir(&two_dir).unwrap();
        let mut two=read_manifest(&backup_for_retry.join("manifest.json")).unwrap();
        let mut second=two.sessions[0].clone();second.id="second-session".into();two.sessions.push(second.clone());
        fs::write(two_dir.join("manifest.json"),serde_json::to_vec(&two).unwrap()).unwrap();
        assert!(!all_sessions_present(&two_dir,&snapshot.host.sessions).unwrap(),"a partial collision must not silently skip missing meetings");
        let mut both=snapshot.host.sessions.clone();both.push(second);
        assert!(all_sessions_present(&two_dir,&both).unwrap());
        assert!(check_conflicts(&two_dir,&snapshot.host.sessions).is_err(),"partial collisions retain the original no-overwrite behavior");
        let broken=source.join("broken-legacy.wav");fs::write(&broken,b"not a WAV").unwrap();
        let mut malformed=snapshot.clone();malformed.host.sessions[0].audio_path=Some(broken.to_string_lossy().into());malformed.host.sessions[0].chunks.clear();
        let before=fs::read_dir(&backups).unwrap().count();assert!(save(&malformed,&source,&backups).is_err());assert_eq!(fs::read_dir(&backups).unwrap().count(),before);
        let backup=PathBuf::from(report.path);let m=read_manifest(&backup.join("manifest.json")).unwrap();assert_eq!(m.files.len(),3);
        let damaged_index=m.files.iter().position(|x|x.file=="recording-original.opus").unwrap();let file=backup.join("files").join(damaged_index.to_string());
        let original=fs::read(&file).unwrap();fs::write(&file,b"tampered").unwrap();assert!(restore_files(&backup,&target).is_err());
        assert!(!target.join("recording.wav").exists());fs::write(&file,original).unwrap();
        let restored=restore_files(&backup,&target).unwrap();assert_eq!(restored.len(),1);assert_eq!(restored[0].transcript_text,"虚构会议：周五前报价");
        assert_eq!(fs::read(target.join("recording.wav")).unwrap(),sound);assert_eq!(fs::read(target.join("recording-original.opus")).unwrap(),b"fictional compressed recording");
        assert!(restored[0].audio_path.as_deref().unwrap().starts_with(target.to_str().unwrap()));
        assert_eq!(audio_artifacts::backup_files_at(&target,&[restored[0].audio_path.clone().unwrap()]).unwrap().len(),3);
        let index=base.join("sessions.json");restore_index(&index,&restored).unwrap();restore_index(&index,&restored).unwrap();
        let mut different=restored.clone();different[0].title="another version".into();assert!(restore_index(&index,&different).is_err());
        let loaded=super::super::persistence::load_sessions_from(&index).unwrap();assert_eq!(loaded[0].id,"backup-original");assert_eq!(loaded[0].transcript_text,"虚构会议：周五前报价");
        let damaged=base.join("damaged-sessions.json");let damaged_backup=base.join("damaged-sessions.json.bak");
        fs::write(&damaged,b"broken primary").unwrap();fs::write(&damaged_backup,b"broken backup").unwrap();
        restore_index(&damaged,&restored).unwrap();assert_eq!(super::super::persistence::load_sessions_from(&damaged).unwrap()[0].id,"backup-original");
        let preserved=fs::read_dir(&base).unwrap().filter_map(Result::ok).filter(|e|e.file_name().to_string_lossy().contains(".corrupt-")).map(|e|fs::read(e.path()).unwrap()).collect::<Vec<_>>();
        assert!(preserved.iter().any(|v|v==b"broken primary")&&preserved.iter().any(|v|v==b"broken backup"));
        let pending=PathBuf::from(format!("{}.privacy-pending",damaged.display()));fs::write(&pending,b"broken privacy marker").unwrap();
        let before=fs::read(&damaged).unwrap();assert!(restore_index(&damaged,&different).is_err());assert_eq!(fs::read(&damaged).unwrap(),before);
        restore_index(&damaged,&restored).unwrap();assert!(!pending.exists());
        // No current session or original file is replaced when the same name has different bytes.
        fs::write(target.join("recording.wav"),b"changed destination").unwrap();assert!(restore_files(&backup,&target).is_err());assert_eq!(fs::read(target.join("recording.wav")).unwrap(),b"changed destination");
        unsafe{std::env::remove_var("COMPANION_TYPE_RECORDING_DIR")};fs::remove_dir_all(base).unwrap();
    }
}
