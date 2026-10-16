//! Virtual folders and labels stay in the original durable session index.
//! No path movement, recording deletion, cloud work or caller-supplied rows.
use serde::{Deserialize,Serialize};
use crate::companion_v1::CompanionV1HostSession;
#[derive(Clone,Debug,Default,Deserialize,Serialize,PartialEq,Eq)]
#[serde(default,rename_all="camelCase",deny_unknown_fields)]
pub struct Metadata {pub revision:u64,pub folder:String,pub tags:Vec<String>,pub favorite:bool}
impl Metadata {pub fn is_empty(&self)->bool{self==&Self::default()}}
#[derive(Clone,Debug,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Target {pub session_id:String,pub expected_revision:u64}
#[derive(Clone,Debug,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Request {pub targets:Vec<Target>,pub folder:Option<String>,pub tags:Option<Vec<String>>,pub tag_action:Option<String>,pub favorite:Option<bool>}
fn label(value:&str,max:usize)->Result<String,String> {
 let v=value.trim();if v.is_empty()||v.chars().count()>max||v.chars().any(char::is_control){return Err(format!("名称请填写1到{max}个字符，不含控制字符。"));}Ok(v.into())
}
fn folder(value:&str)->Result<String,String> {
 if value.trim().is_empty(){return Ok(String::new());}
 let parts=value.split('/').map(|p|label(p,40)).collect::<Result<Vec<_>,_>>()?;
 if parts.len()>4||parts.iter().any(|p|matches!(p.as_str(),"."|"..")||p.contains('\\')){return Err("文件夹最多四层，用 / 分隔，不使用 .、.. 或反斜线。".into());}
 let result=parts.join("/");if result.chars().count()>120{return Err("文件夹路径请控制在120个字符以内。".into());}Ok(result)
}
fn tags(values:&[String])->Result<Vec<String>,String> {
 let mut result:Vec<String>=Vec::new();for value in values {let tag=label(value,24)?;
  if !result.iter().any(|v|v.to_lowercase()==tag.to_lowercase()){result.push(tag);}
  if result.len()>16{return Err("每场录音最多16个标签。".into());}}
 Ok(result)
}
pub(crate) fn apply(rows:&mut [CompanionV1HostSession],request:&Request)->Result<(),String> {
 if request.targets.is_empty()||request.targets.len()>1000{return Err("请选择1到1000场录音。".into());}
 if request.folder.is_none()&&request.tags.is_none()&&request.favorite.is_none(){return Err("请选择要修改的分类、标签或收藏。".into());}
 let new_folder=request.folder.as_deref().map(folder).transpose()?;let new_tags=request.tags.as_deref().map(tags).transpose()?;
 let action=request.tag_action.as_deref().unwrap_or("replace");
 if !matches!(action,"replace"|"add"|"remove")||request.tags.is_none()&&request.tag_action.is_some(){return Err("标签操作无效，请重新选择。".into());}
 if matches!(action,"add"|"remove")&&new_tags.as_ref().is_some_and(Vec::is_empty){return Err("请先填写要添加或移除的标签。".into());}
 let mut seen=std::collections::HashSet::new();let mut changes=Vec::new();
 for target in &request.targets {
  if !seen.insert(&target.session_id){return Err("批量选择包含重复录音。".into());}
  let row=rows.iter().find(|r|r.id==target.session_id).ok_or("所选录音已被移除，请刷新后核对；整批未修改。")?;
  if row.status=="recording"||matches!(row.recovery.stage.as_str(),"transcribing"|"generatingMinutes"){return Err("所选录音仍在采集或处理，请完成后整理；整批未修改。".into());}
  if row.organization.revision!=target.expected_revision{return Err("分类在另一窗口中已变化，请刷新后核对；整批未修改，输入仍保留。".into());}
  let mut value=row.organization.clone();if let Some(folder)=&new_folder{value.folder=folder.clone();}
  if let Some(incoming)=&new_tags {value.tags=match action {
   "replace"=>incoming.clone(),"add"=>{let mut all=value.tags.clone();all.extend(incoming.clone());tags(&all)?},
   _=>value.tags.iter().filter(|t|!incoming.iter().any(|v|v.to_lowercase()==t.to_lowercase())).cloned().collect()};}
  if let Some(favorite)=request.favorite{value.favorite=favorite;}
  if value!=row.organization{value.revision=value.revision.checked_add(1).ok_or("分类版本已超出范围。")?;}
  changes.push((row.id.clone(),value));
 }
 for (id,value) in changes {rows.iter_mut().find(|r|r.id==id).unwrap().organization=value;}Ok(())
}
pub(crate) fn commit(path:&std::path::Path,request:&Request)->Result<Vec<CompanionV1HostSession>,String> {
 super::session_store::update_checked(path,|rows|apply(rows,request))?;
 let loaded=super::session_store::load(path);if loaded.state.status!="ready"{return Err("分类已提交，但重新读取未完成，请刷新核对。".into());}
 serde_json::from_slice(&loaded.bytes.ok_or("保存后找不到资料库，请刷新核对。")?).map_err(|e|format!("重新读取资料库：{e}"))
}

#[cfg(test)]
mod tests {
 use super::*;use crate::companion_v1::{fixture_snapshot,apply_fixture_control};
 fn row(id:&str)->CompanionV1HostSession {let mut s=apply_fixture_control(fixture_snapshot(),serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap()).unwrap().host.sessions.remove(0);s.id=id.into();s}
 fn request()->Request{Request{targets:vec![Target{session_id:"a".into(),expected_revision:0},Target{session_id:"b".into(),expected_revision:0}],folder:Some(" 工作 / 项目 ".into()),tags:Some(vec!["重点".into(),"Review".into(),"review".into()]),tag_action:Some("add".into()),favorite:Some(true)}}
 #[test]fn batch_durable_reload_and_stale_snapshot_cannot_erase_metadata(){
  let root=std::env::temp_dir().join(format!("companion-organization-{}",uuid::Uuid::new_v4()));std::fs::create_dir(&root).unwrap();let path=root.join("sessions.json");
  let original=vec![row("a"),row("b")];super::super::session_store::save(&path,&original).unwrap();let saved=commit(&path,&request()).unwrap();
  for s in &saved{assert_eq!(s.organization.folder,"工作/项目");assert_eq!(s.organization.tags,vec!["重点","Review"]);assert!(s.organization.favorite);assert_eq!(s.organization.revision,1);}
  assert_eq!(saved[0].audio_path,original[0].audio_path);assert_eq!(saved[0].transcript_text,original[0].transcript_text);
  let export=super::super::export::prepare_meeting_export(&saved[0],"offlineStore",super::super::export::MeetingExportFormat::Json).unwrap();
  let value:serde_json::Value=serde_json::from_slice(&export.bytes).unwrap();assert_eq!(value["organization"]["folder"],"工作/项目");
  assert!(super::super::session_store::save(&path,&original).is_err());
  let unchanged=std::fs::read(&path).unwrap();assert!(commit(&path,&request()).is_err());assert_eq!(std::fs::read(&path).unwrap(),unchanged);
  assert_eq!(super::super::persistence::load_sessions_from(&path).unwrap()[0].organization,saved[0].organization);std::fs::remove_dir_all(root).unwrap();
 }
 #[test]fn batch_prevalidates_all_rows_and_limits_without_partial_edit(){
  for failure in ["missing","stale","recording","folder","tags","duplicate"]{
   let mut rows=vec![row("a"),row("b")];let mut q=request();match failure{
    "missing"=>q.targets[1].session_id="missing".into(),"stale"=>q.targets[1].expected_revision=1,"recording"=>rows[1].status="recording".into(),
    "folder"=>q.folder=Some("a/../b".into()),"tags"=>q.tags=Some((0..17).map(|n|n.to_string()).collect()),_=>q.targets[1].session_id="a".into()};
   let original=serde_json::to_vec(&rows).unwrap();assert!(apply(&mut rows,&q).is_err(),"{failure}");assert_eq!(serde_json::to_vec(&rows).unwrap(),original,"{failure}");
  }
 }
 #[test]fn replace_remove_and_unfile_preserve_original_fields(){
  let mut rows=vec![row("a"),row("b")];apply(&mut rows,&request()).unwrap();let mut q=request();for t in &mut q.targets{t.expected_revision=1;}
  q.folder=Some(String::new());q.tags=Some(vec!["REVIEW".into()]);q.tag_action=Some("remove".into());q.favorite=Some(false);apply(&mut rows,&q).unwrap();
  assert!(rows.iter().all(|r|r.organization.folder.is_empty()&&!r.organization.favorite&&r.organization.tags==vec!["重点"]));
 }
 #[test]fn old_rows_and_locked_store_do_not_become_partial_saves(){
  let sample=row("a");let value=serde_json::to_value(&sample).unwrap();assert!(value.get("organization").is_none());
  let decoded:CompanionV1HostSession=serde_json::from_value(value).unwrap();assert_eq!(decoded.organization,Metadata::default());
  let root=std::env::temp_dir().join(format!("companion-org-lock-{}",uuid::Uuid::new_v4()));std::fs::create_dir(&root).unwrap();let path=root.join("sessions.json");
  super::super::session_store::save(&path,&[sample,row("b")]).unwrap();let before=std::fs::read(&path).unwrap();
  let lock=std::fs::OpenOptions::new().read(true).write(true).open(root.join("sessions.json.lock")).unwrap();lock.try_lock().unwrap();
  assert!(commit(&path,&request()).is_err());assert_eq!(std::fs::read(&path).unwrap(),before);drop(lock);std::fs::remove_dir_all(root).unwrap();
 }
}
