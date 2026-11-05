//! Local protection and reversible trash keep the original row/audio in place.
//! The separate action lock serializes protection changes against file erasure.
use std::{fs::{File,OpenOptions},path::Path};
use serde::Deserialize;
use crate::companion_v1::{CompanionV1ControlAction as Action,CompanionV1ControlRequest,CompanionV1HostSession,CompanionV1Snapshot};
use super::library_organization::Target;

#[derive(Clone,Copy,Debug,Deserialize,PartialEq,Eq)]
#[serde(rename_all="camelCase")]
pub enum Operation { Protect, Unprotect, Trash, Restore }
#[derive(Clone,Debug,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Request {pub targets:Vec<Target>,pub action:Operation}
pub const LOCAL_TRASH_PERMANENT:&str="__companion_local_trash_permanent__";
#[derive(Clone,Debug,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct PurgeRequest {pub targets:Vec<Target>}
pub fn validate_purge(snapshot:&CompanionV1Snapshot,request:&PurgeRequest)->Result<(),String>{
 if snapshot.device.recording||snapshot.meeting.active||snapshot.host.sessions.iter().any(|s|s.status=="recording"){return Err("请先结束并保存录音，再永久清除回收站。".into());}
 if request.targets.is_empty()||request.targets.len()>1000{return Err("请选择1到1000场回收站录音。".into());}
 let mut ids=std::collections::HashSet::new();
 for target in &request.targets{
  if !ids.insert(&target.session_id){return Err("选择包含重复录音。".into());}
  let row=snapshot.host.sessions.iter().find(|s|s.id==target.session_id).ok_or("回收站录音已移除，请刷新核对。")?;
  if row.organization.revision!=target.expected_revision||row.organization.trashed_at.is_none()||row.organization.protected{
   return Err("所选录音已变化、已恢复或受保护；未开始永久清除，请刷新核对。".into());
  }
 }Ok(())
}

pub fn require_available(row:&CompanionV1HostSession)->Result<(),String>{
 if row.organization.trashed_at.is_some(){Err("录音已在回收站；请先恢复，再回听、编辑或处理。".into())}else{Ok(())}
}
pub(super) fn action_lock(path:&Path)->Result<File,String>{
 let mut name=path.as_os_str().to_os_string();name.push(".library-actions.lock");
 if let Some(parent)=path.parent(){std::fs::create_dir_all(parent).map_err(|e|e.to_string())?;}
 let lock=OpenOptions::new().read(true).write(true).create(true).truncate(false).open(std::path::PathBuf::from(name)).map_err(|e|format!("无法取得录音保护锁：{e}"))?;
 lock.try_lock().map_err(|_|"另一项保护或清理正在执行，请稍后重试。")?;Ok(lock)
}
fn destructive(action:Action)->bool{matches!(action,Action::PrivacyEraseAudio|Action::PrivacyEraseTranscript|Action::PrivacyDeleteSession|Action::PrivacyEraseAll)}
pub fn validate_privacy(snapshot:&CompanionV1Snapshot,request:&CompanionV1ControlRequest)->Result<(),String>{
 if !destructive(request.action){return Ok(());}
 if request.action==Action::PrivacyEraseAll {
  if snapshot.host.sessions.iter().any(|r|r.organization.protected){return Err("资料库含受保护录音；请先明确解除保护，再清除全部资料。".into());}
 }else if request.session_id.as_deref().and_then(|id|snapshot.host.sessions.iter().find(|r|r.id==id)).is_some_and(|r|r.organization.protected){
  return Err("这场录音已受保护，未删除任何音频、文字或设备数据；请先解除保护。".into());
 }Ok(())
}
pub fn privacy_guard(snapshot:&CompanionV1Snapshot,request:&CompanionV1ControlRequest,path:&Path)->Result<Option<File>,String>{
 if !destructive(request.action){return Ok(None);}
 validate_privacy(snapshot,request)?;
 if cfg!(test)&&std::env::var_os("COMPANION_TYPE_STATE_PATH").is_none(){return Ok(None);}
 privacy_guard_current(snapshot,request,path).map(Some)
}
fn privacy_guard_current(snapshot:&CompanionV1Snapshot,request:&CompanionV1ControlRequest,path:&Path)->Result<File,String>{
 let lock=action_lock(path)?;
 let loaded=super::session_store::load(path);if loaded.state.status!="ready"{return Err("请先恢复会议库，再清理资料。".into());}
 let rows:Vec<CompanionV1HostSession>=serde_json::from_slice(&loaded.bytes.ok_or("找不到已保存资料库；未清理资料。")?).map_err(|e|e.to_string())?;
 let all=request.action==Action::PrivacyEraseAll;
 if all&&rows.len()!=snapshot.host.sessions.len(){return Err("资料库已在另一进程变化，请刷新后重新确认清理。".into());}
 for current in rows.iter().filter(|r|all||request.session_id.as_deref()==Some(&r.id)){
  if current.organization.protected{return Err("磁盘中的录音已受保护，未删除资料；请刷新后核对。".into());}
  if current.status=="recording"||current.recorder_control_uncertain{return Err("磁盘中的原录音仍在采集或待核对，未清理资料。".into());}
  if snapshot.host.sessions.iter().find(|s|s.id==current.id).is_none_or(|s|s.organization!=current.organization){
   return Err("磁盘中的录音状态已变化，未删除资料；请刷新后重新确认。".into());
  }
  let cached=snapshot.host.sessions.iter().find(|s|s.id==current.id).unwrap();
  if cached.audio_path!=current.audio_path||cached.audio_bytes!=current.audio_bytes||cached.device_recording_key!=current.device_recording_key
    ||cached.device_sha256!=current.device_sha256||cached.device_total_length!=current.device_total_length{
    return Err("磁盘中的原音身份或长度已变化，未清理资料；请刷新后核对。".into());
  }
 }
 if !all&&request.session_id.as_deref().is_some_and(|id|!rows.iter().any(|r|r.id==id)){return Err("所选录音已从磁盘移除，未清理其它资料。".into());}
 Ok(lock)
}

pub fn apply(rows:&mut [CompanionV1HostSession],request:&Request,now:&str)->Result<(),String>{
 if request.targets.is_empty()||request.targets.len()>1000{return Err("请选择1到1000场录音。".into());}
 let mut seen=std::collections::HashSet::new();let mut changes=Vec::new();
 for target in &request.targets {
  if !seen.insert(&target.session_id){return Err("选择包含重复录音，整批未修改。".into());}
  let row=rows.iter().find(|r|r.id==target.session_id).ok_or("所选录音已移除，整批未修改。")?;
  if row.organization.revision!=target.expected_revision{return Err("所选录音的分类、保护或回收站状态已变化；请刷新选择，整批未修改。".into());}
  if row.status=="recording"||matches!(row.recovery.stage.as_str(),"transcribing"|"generatingMinutes"){return Err("所选录音仍在采集或处理，整批未修改。".into());}
  let mut metadata=row.organization.clone();
  match request.action{
   Operation::Protect=>{require_available(row)?;metadata.protected=true;},
   Operation::Unprotect=>metadata.protected=false,
   Operation::Trash=>{if metadata.protected{return Err("所选内容含受保护录音，整批未移入回收站；请先解除保护。".into());}if metadata.trashed_at.is_none(){metadata.trashed_at=Some(now.into());}},
   Operation::Restore=>metadata.trashed_at=None,
  }
  if metadata!=row.organization{metadata.revision=metadata.revision.checked_add(1).ok_or("录音状态版本超出范围。")?;}
  changes.push((row.id.clone(),metadata));
 }
 for (id,metadata) in changes {let row=rows.iter_mut().find(|r|r.id==id).unwrap();row.organization=metadata;
  if request.action==Operation::Trash{row.recovery=Default::default();}}
 Ok(())
}
pub fn commit(path:&Path,request:&Request,now:&str)->Result<Vec<CompanionV1HostSession>,String>{
 let _lock=action_lock(path)?;
 super::session_store::update_checked(path,|rows|apply(rows,request,now))?;
 super::persistence::load_sessions_from(path).ok_or("录音状态已提交，但重新读取未完成，请刷新核对。".into())
}

#[cfg(test)]
mod tests{
 use super::*;
 fn row(id:&str)->CompanionV1HostSession{let mut r=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap()).unwrap().host.sessions.remove(0);r.id=id.into();r}
 fn request(rows:&[CompanionV1HostSession],action:Operation)->Request{Request{targets:rows.iter().map(|r|Target{session_id:r.id.clone(),expected_revision:r.organization.revision}).collect(),action}}
 #[test]fn protection_trash_restore_keep_original_and_prevalidate_entire_batch(){
  let mut rows=vec![row("a"),row("b")];let original=rows.clone();let q=request(&rows,Operation::Protect);apply(&mut rows,&q,"now").unwrap();
  let before=serde_json::to_vec(&rows).unwrap();let q=request(&rows,Operation::Trash);assert!(apply(&mut rows,&q,"now").is_err());assert_eq!(serde_json::to_vec(&rows).unwrap(),before);
  let q=request(&rows,Operation::Unprotect);apply(&mut rows,&q,"now").unwrap();let q=request(&rows,Operation::Trash);apply(&mut rows,&q,"trash-time").unwrap();
  for (a,b) in original.iter().zip(&rows){assert_eq!(a.audio_path,b.audio_path);assert_eq!(a.transcript_text,b.transcript_text);assert_eq!(a.meeting_notes,b.meeting_notes);assert_eq!(b.organization.trashed_at.as_deref(),Some("trash-time"));assert_eq!(b.recovery.intent,"none");assert!(require_available(b).is_err());}
  let stale=q;assert!(apply(&mut rows,&stale,"later").is_err());let q=request(&rows,Operation::Restore);apply(&mut rows,&q,"restore-time").unwrap();assert!(rows.iter().all(|r|r.organization.trashed_at.is_none()));
  let mut q=request(&rows,Operation::Trash);q.targets[1].session_id="missing".into();let before=serde_json::to_vec(&rows).unwrap();assert!(apply(&mut rows,&q,"x").is_err());assert_eq!(serde_json::to_vec(&rows).unwrap(),before);
 }
 #[test]fn durable_trash_and_restore_reject_stale_general_snapshots(){
  let root=std::env::temp_dir().join(format!("companion-trash-{}",uuid::Uuid::new_v4()));std::fs::create_dir(&root).unwrap();let path=root.join("sessions.json");
  let original=vec![row("a")];super::super::session_store::save(&path,&original).unwrap();let trashed=commit(&path,&request(&original,Operation::Trash),"now").unwrap();
  assert!(super::super::session_store::save(&path,&original).is_err());assert_eq!(super::super::persistence::load_sessions_from(&path).unwrap()[0].organization.trashed_at.as_deref(),Some("now"));
  assert!(super::super::audio_export::source(&{let mut s=crate::companion_v1::fixture_snapshot();s.host.sessions=trashed.clone();s},"a").is_err());
  let restored=commit(&path,&request(&trashed,Operation::Restore),"later").unwrap();assert!(restored[0].organization.trashed_at.is_none());std::fs::remove_dir_all(root).unwrap();
 }
 #[test]fn every_privacy_entry_rejects_protected_and_new_workspace_keeps_library(){
  let mut snapshot=crate::companion_v1::fixture_snapshot();let mut r=row("a");r.organization.protected=true;r.organization.revision=1;
  snapshot.host.sessions=vec![r];snapshot.host.selected_session_id=Some("a".into());snapshot.meeting.active=false;snapshot.device.recording=false;
  for action in ["privacyEraseAudio","privacyEraseTranscript","privacyDeleteSession","privacyEraseAll"]{
   let q:CompanionV1ControlRequest=serde_json::from_value(serde_json::json!({"action":action,"sessionId":"a"})).unwrap();
   assert!(validate_privacy(&snapshot,&q).is_err(),"{action}");assert!(crate::companion_v1::apply_fixture_control(snapshot.clone(),q).is_err());
  }
  let reset=crate::companion_v1::apply_fixture_control(snapshot.clone(),serde_json::from_value(serde_json::json!({"action":"meetingResetSession"})).unwrap()).unwrap();
  assert_eq!(serde_json::to_vec(&reset.host.sessions).unwrap(),serde_json::to_vec(&snapshot.host.sessions).unwrap());
 }
 #[test]fn latest_disk_protection_and_action_lock_close_stale_process_gap(){
  let root=std::env::temp_dir().join(format!("companion-privacy-protection-{}",uuid::Uuid::new_v4()));std::fs::create_dir(&root).unwrap();let path=root.join("sessions.json");
  let mut snapshot=crate::companion_v1::fixture_snapshot();snapshot.host.sessions=vec![row("a")];snapshot.host.selected_session_id=Some("a".into());
  super::super::session_store::save(&path,&snapshot.host.sessions).unwrap();
  let q:CompanionV1ControlRequest=serde_json::from_value(serde_json::json!({"action":"privacyDeleteSession","sessionId":"a"})).unwrap();
  let guard=privacy_guard_current(&snapshot,&q,&path).unwrap();assert!(commit(&path,&request(&snapshot.host.sessions,Operation::Protect),"now").is_err());drop(guard);
  let protected=commit(&path,&request(&snapshot.host.sessions,Operation::Protect),"now").unwrap();
  assert!(privacy_guard_current(&snapshot,&q,&path).is_err());assert!(super::super::session_store::save(&path,&[]).is_err());
  assert_eq!(super::super::persistence::load_sessions_from(&path).unwrap()[0].organization,protected[0].organization);
  std::fs::remove_dir_all(root).unwrap();
 }
}
