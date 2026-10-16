//! Portable local library data. No credentials, pairing secrets, queued device
//! commands or cloud jobs are restored. Source media remain byte-identical.
use std::{collections::{BTreeMap,BTreeSet},fs::{self,File,OpenOptions},io::{Read,Write},path::{Path,PathBuf}};
use serde::{Deserialize,Serialize};
use sha2::{Digest,Sha256};
use crate::companion_v1::CompanionV1HostSession as Row;
use super::{audio_artifacts::{self,Purpose},audio_storage,export,session_store};
const REFERENCE:&str="companion-backup://";
const MISSING:&str="companion-backup-missing://";
const MAX_MANIFEST:u64=64*1024*1024;
#[derive(Clone,Debug,Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Asset {id:String,name:String,bytes:u64,sha256:String,purpose:Purpose,owners:BTreeSet<String>}
#[derive(Clone,Debug,Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Warning {pub session_id:String,pub title:String,pub message:String}
#[derive(Clone,Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Bundle {schema:u32,minimum_reader:u32,id:String,created_at:String,sessions:Vec<Row>,assets:Vec<Asset>,warnings:Vec<Warning>}
#[derive(Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct PreparedAsset {asset:Asset,created:bool}
#[derive(Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Prepared {schema:u32,id:String,root:String,files:Vec<PreparedAsset>}
fn pending(index:&Path)->Result<PathBuf,String>{Ok(index.parent().ok_or("资料库位置无效。")?.join("library-restore-pending.json"))}
fn temporary(root:&Path,id:&str,n:usize)->PathBuf{root.join(format!(".library-restore-{id}-{n}.tmp"))}
#[derive(Debug,Serialize)]
#[serde(rename_all="camelCase")]
pub struct BackupReport {pub path:String,pub sessions:usize,pub files:usize,pub bytes:u64,pub complete_local_media:bool,pub warnings:Vec<Warning>}
#[derive(Clone,Debug,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct RestoreRequest {pub path:String,pub package_token:String,pub library_token:String,#[serde(default)]pub new_only:bool}
#[derive(Clone,Debug,Serialize)]
#[serde(rename_all="camelCase")]
pub struct Conflict {pub session_id:String,pub title:String,pub message:String}
#[derive(Debug,Serialize)]
#[serde(rename_all="camelCase")]
pub struct Preview {pub path:String,pub package_token:String,pub library_token:String,pub sessions:usize,pub files:usize,pub bytes:u64,
 pub new_sessions:Vec<String>,pub matching_sessions:Vec<String>,pub repair_sessions:Vec<String>,pub conflicts:Vec<Conflict>,pub warnings:Vec<Warning>}
#[derive(Debug,Serialize)]
#[serde(rename_all="camelCase")]
pub struct RestoreReport {pub added:Vec<String>,pub repaired:Vec<String>,pub skipped:Vec<String>,pub warnings:Vec<Warning>,pub files_prepared:usize}
fn hash(bytes:&[u8])->String{format!("{:x}",Sha256::digest(bytes))}
fn digest(v:&str)->bool{v.len()==64&&v.bytes().all(|b|b.is_ascii_hexdigit()&&!b.is_ascii_uppercase())}
fn name(v:&str)->bool{let stem=v.split('.').next().unwrap_or("").to_ascii_uppercase();
 !v.is_empty()&&v.len()<=220&&!matches!(v,"."|"..")&&!v.chars().any(|c|c.is_control()||"/\\:<>\"|?*".contains(c))
 &&!v.ends_with(['.',' '])&&!v.starts_with(".audio-")&&!v.starts_with(".library-")&&!v.starts_with(".legacy-")
 &&!matches!(stem.as_str(),"CON"|"PRN"|"AUX"|"NUL"|"COM1"|"COM2"|"COM3"|"COM4"|"COM5"|"COM6"|"COM7"|"COM8"|"COM9"|"LPT1"|"LPT2"|"LPT3"|"LPT4"|"LPT5"|"LPT6"|"LPT7"|"LPT8"|"LPT9")}
fn local_directory(path:&Path)->Result<PathBuf,String>{
 let p=path.canonicalize().map_err(|e|format!("无法打开本机目录：{e}"))?;let s=p.to_string_lossy().to_ascii_lowercase();
 if !p.is_dir()||s.starts_with("\\\\?\\unc\\")||(s.starts_with("\\\\")&&!s.starts_with("\\\\?\\")){return Err("请选择本机目录；备份可完成后再自行移动或分享。".into());}Ok(p)
}
fn regular(path:&Path)->Result<(),String>{let m=fs::symlink_metadata(path).map_err(|e|format!("备份文件不可用 {}：{e}",path.display()))?;
 if !m.is_file()||m.file_type().is_symlink(){return Err("备份文件必须是普通文件，不能用符号链接替代。".into());}Ok(())}
fn rows(path:&Path)->Result<Vec<Row>,String>{let loaded=session_store::load(path);
 if loaded.state.status!="ready"{return Err("请先恢复或保存会议库，再备份或恢复。".into());}
 let rows:Vec<Row>=loaded.bytes.map(|b|serde_json::from_slice(&b)).transpose().map_err(|e|e.to_string())?.unwrap_or_default();
 idle(&rows)?;Ok(rows)
}
fn idle(rows:&[Row])->Result<(),String>{
 if rows.iter().any(|r|r.status=="recording"||r.recorder_control_uncertain||matches!(r.recovery.stage.as_str(),"transcribing"|"generatingMinutes")){
  return Err("请先结束并保存录音，完成或暂停当前处理，再备份或恢复。".into());}Ok(())
}
fn token(rows:&[Row])->Result<String,String>{serde_json::to_vec(rows).map(|b|hash(&b)).map_err(|e|e.to_string())}
fn source_key(path:&Path)->Result<String,String>{Ok(path.canonicalize().map_err(|e|e.to_string())?.to_string_lossy().replace('/',"\\").to_lowercase())}
fn source_file(path:&Path)->Result<File,String>{regular(path)?;let mut options=OpenOptions::new();options.read(true);
 #[cfg(windows)]{use std::os::windows::fs::OpenOptionsExt;options.share_mode(1);}
 options.open(path).map_err(|e|format!("原件正在变化或被占用，未完成备份：{e}"))
}
fn copy_checked(source:&Path,destination:&Path,bytes:u64,sha:&str)->Result<(),String>{
 let mut input=source_file(source)?;let mut output=OpenOptions::new().write(true).create_new(true).open(destination).map_err(|e|e.to_string())?;
 let mut count=0u64;let mut hasher=Sha256::new();let mut buffer=[0u8;65536];
 let result=(||{loop{let n=input.read(&mut buffer).map_err(|e|e.to_string())?;if n==0{break;}count=count.checked_add(n as u64).ok_or("文件长度溢出。")?;
  if count>bytes{return Err("文件在备份或恢复时发生变化。".into());}hasher.update(&buffer[..n]);output.write_all(&buffer[..n]).map_err(|e|e.to_string())?;}
  output.sync_all().map_err(|e|e.to_string())?;if count!=bytes||format!("{:x}",hasher.finalize())!=sha{return Err("文件长度或SHA校验失败；资料库未改动。".into());}Ok(())})();
 drop(output);if result.is_err(){let _=fs::remove_file(destination);}result
}
fn warning(row:&Row,message:&str)->Warning{Warning{session_id:row.id.clone(),title:row.title.clone(),message:message.into()}}
struct Inventory {managed_key:String,assets:BTreeMap<String,Asset>,paths:BTreeMap<String,PathBuf>,by_source:BTreeMap<String,String>,warnings:Vec<Warning>}
impl Inventory{
 fn add(&mut self,path:&Path,purpose:Purpose,owner:&Row)->Result<Option<String>,String>{
  if !path.is_absolute()||!path.is_file(){self.warnings.push(warning(owner,"有原件尚未保存在本机或已移动；备份只包含可用资料。"));return Ok(None);}
  regular(path)?;let key=source_key(path)?;
  if let Some(id)=self.by_source.get(&key){self.assets.get_mut(id).unwrap().owners.insert(owner.id.clone());return Ok(Some(id.clone()));}
  let (bytes,sha256)=audio_storage::fingerprint(path)?;let id=hash(key.as_bytes());
  let original=path.file_name().and_then(|n|n.to_str()).ok_or("原件文件名不可用。")?;
  let managed=path.parent().is_some_and(|p|source_key(p).is_ok_and(|key|key==self.managed_key));
  let file_name=if managed||original.starts_with("board-session-")||original.starts_with(".board-session-"){original.to_string()}
   else{let ext=path.extension().and_then(|e|e.to_str()).ok_or("原件格式不可用。")?;format!("backup-{sha256}.{ext}")};
  if !name(&file_name)||!purpose.accepts(Path::new(&file_name)){return Err(format!("原件格式或文件名不受支持：{original}"));}
  if self.assets.values().any(|a|a.name.eq_ignore_ascii_case(&file_name)&&a.sha256!=sha256){return Err("两份原件使用同一文件身份但内容不同，请先核对。".into());}
  self.assets.insert(id.clone(),Asset{id:id.clone(),name:file_name,bytes,sha256,purpose,owners:BTreeSet::from([owner.id.clone()])});
  self.by_source.insert(key,id.clone());self.paths.insert(id.clone(),path.into());Ok(Some(id))
 }
 fn reference(&mut self,path:&mut Option<String>,purpose:Purpose,row:&Row)->Result<(),String>{
  let Some(raw)=path.as_deref() else{return Ok(())};
  if !Path::new(raw).is_absolute(){if !raw.starts_with("host://")&&!raw.starts_with("board://"){return Err("资料库含不支持的原件引用，请先核对。".into());}
   self.warnings.push(warning(row,"这场录音仍需从来源设备同步，设备上的数据不包含在本机备份中。"));return Ok(());}
  *path=Some(match self.add(Path::new(raw),purpose,row)?{Some(id)=>format!("{REFERENCE}{id}"),None=>format!("{MISSING}{}",hash(raw.as_bytes()))});Ok(())
 }
}
pub fn create(index:&Path,recordings:&Path,parent:&Path)->Result<BackupReport,String>{
 let _operation=super::library_lifecycle::action_lock(index)?;cleanup_pending(index,recordings)?;let original=rows(index)?;let index_token=token(&original)?;
 let parent=local_directory(parent)?;let mut inventory=Inventory{managed_key:source_key(recordings)?,assets:BTreeMap::new(),paths:BTreeMap::new(),by_source:BTreeMap::new(),warnings:Vec::new()};let mut portable=original.clone();
 for (row,out) in original.iter().zip(&mut portable){
  let sources=row.audio_path.iter().chain(row.chunks.iter().filter_map(|c|c.path.as_ref())).filter(|s|Path::new(s).is_absolute()).cloned().collect::<Vec<_>>();
  for (path,purpose) in audio_artifacts::backup_inventory(recordings,&sources)?{inventory.add(&path,purpose,row)?;}
  inventory.reference(&mut out.audio_path,Purpose::Recording,row)?;
  for chunk in &mut out.chunks{let purpose=if chunk.path.as_deref().is_some_and(|p|p.to_lowercase().ends_with(".opus")){Purpose::CompressedOriginal}else{Purpose::Recording};inventory.reference(&mut chunk.path,purpose,row)?;}
  if let Some(key)=row.device_recording_key.as_ref(){
   let key=super::recording_wire::SessionKey::from_public(key)?;let stem=format!("board-session-{}",hash(&serde_json::to_vec(&key).map_err(|e|e.to_string())?));
   let root=row.audio_path.as_deref().filter(|p|Path::new(p).is_absolute()).and_then(|p|Path::new(p).parent()).unwrap_or(recordings);
   let receipt=root.join(format!(".{stem}.json"));
   if receipt.is_file(){inventory.add(&receipt,Purpose::SessionReceipt,row)?;}else{inventory.warnings.push(warning(row,"本机缺少收取记录；已保存原音可备份，但暂停原始时间轴/未完成收取不能据此补全。"));}
  }
 }
 if inventory.assets.len()>16384||portable.len()>50000{return Err("资料库过大，请联系支持分批处理；本次未发布备份。".into());}
 let id=uuid::Uuid::new_v4().to_string();let staging=parent.join(format!(".Companion-backup-{id}.pending"));let destination=parent.join(format!("Companion-backup-{id}"));
 fs::create_dir(&staging).map_err(|e|e.to_string())?;fs::create_dir(staging.join("media")).map_err(|e|e.to_string())?;
 let result=(||{
  let mut bytes=0u64;for asset in inventory.assets.values(){copy_checked(&inventory.paths[&asset.id],&staging.join("media").join(format!("{}.bin",asset.id)),asset.bytes,&asset.sha256)?;bytes=bytes.checked_add(asset.bytes).ok_or("备份长度溢出。")?;}
  if token(&rows(index)?)?!=index_token{return Err("备份期间资料库已变化，未发布混合版本；请在空闲后重试。".into());}
  let bundle=Bundle{schema:1,minimum_reader:49,id,created_at:chrono::Utc::now().to_rfc3339(),sessions:portable,assets:inventory.assets.values().cloned().collect(),warnings:inventory.warnings};
  let manifest=serde_json::to_vec_pretty(&bundle).map_err(|e|e.to_string())?;if manifest.len() as u64>MAX_MANIFEST{return Err("备份索引超过支持大小。".into());}
  bytes+=export::write_atomic(&staging.join("backup.json"),&manifest)?;
  if destination.exists(){return Err("备份目录已存在，未覆盖。".into());}fs::rename(&staging,&destination).map_err(|e|e.to_string())?;
  Ok(BackupReport{path:destination.to_string_lossy().into(),sessions:bundle.sessions.len(),files:bundle.assets.len()+1,bytes,complete_local_media:bundle.warnings.is_empty(),warnings:bundle.warnings})
 })();
 if result.is_err(){let canonical=staging.canonicalize().ok();if canonical.as_deref().is_some_and(|p|p.parent()==Some(parent.as_path())){let _=fs::remove_dir_all(&staging);}}result
}
fn load(path:&Path)->Result<(PathBuf,Bundle,String),String>{
 let root=local_directory(path)?;let manifest=root.join("backup.json");regular(&manifest)?;let mut bytes=Vec::new();source_file(&manifest)?.take(MAX_MANIFEST+1).read_to_end(&mut bytes).map_err(|e|e.to_string())?;
 if bytes.len() as u64>MAX_MANIFEST{return Err("备份索引超过支持大小。".into());}
 let raw:serde_json::Value=serde_json::from_slice(&bytes).map_err(|_|"备份索引格式损坏。")?;let bundle:Bundle=serde_json::from_value(raw.clone()).map_err(|_|"备份格式或字段不受支持。")?;
 if serde_json::to_value(&bundle).map_err(|e|e.to_string())?!=raw||bundle.schema!=1||bundle.minimum_reader>49||bundle.assets.len()>16384||bundle.sessions.len()>50000||uuid::Uuid::parse_str(&bundle.id).is_err(){return Err("备份版本或字段不受支持，请使用兼容版本；未恢复资料。".into());}
 idle(&bundle.sessions)?;let mut ids=BTreeSet::new();if bundle.sessions.iter().any(|s|s.id.is_empty()||!ids.insert(s.id.clone())){return Err("备份含空白或重复会议ID。".into());}
 let media=root.join("media");if fs::symlink_metadata(&media).map_err(|e|e.to_string())?.file_type().is_symlink()||media.canonicalize().map_err(|e|e.to_string())?!=media{return Err("备份媒体目录不能转向其它目录。".into());}
 let mut assets=BTreeSet::new();let mut names:BTreeMap<String,String>=BTreeMap::new();
 for a in &bundle.assets{
  if !digest(&a.id)||!digest(&a.sha256)||!assets.insert(a.id.clone())||!name(&a.name)||!a.purpose.accepts(Path::new(&a.name))||a.owners.is_empty()||a.owners.iter().any(|id|!ids.contains(id)) {return Err("备份原件引用或名称无效。".into());}
  if names.insert(a.name.to_lowercase(),a.sha256.clone()).is_some_and(|old|old!=a.sha256){return Err("备份文件身份冲突。".into());}
  let file=media.join(format!("{}.bin",a.id));regular(&file)?;
  if audio_storage::fingerprint(&file)?!=(a.bytes,a.sha256.clone()){return Err("备份文件长度或SHA校验失败，未恢复资料。".into());}
 }
 for row in &bundle.sessions{for raw in row.audio_path.iter().chain(row.chunks.iter().filter_map(|c|c.path.as_ref())){
  if let Some(id)=raw.strip_prefix(REFERENCE){if !assets.contains(id){return Err("备份引用缺少原件。".into());}}
  else if let Some(id)=raw.strip_prefix(MISSING){if !digest(id){return Err("缺失文件标记无效。".into());}}
  else if !raw.starts_with("host://")&&!raw.starts_with("board://"){return Err("备份包含非便携文件路径，未访问该路径。".into());}
 }
 if row.audio_stored{if let Some(a)=row.audio_path.as_deref().and_then(|p|p.strip_prefix(REFERENCE)).and_then(|id|bundle.assets.iter().find(|a|a.id==id)){
  super::meeting_workspace::validate_wav(&media.join(format!("{}.bin",a.id)))?;
 }}
 }
 Ok((root,bundle,hash(&bytes)))
}
fn relocated(bundle:&Bundle,root:&Path)->Result<Vec<Row>,String>{
 let assets=bundle.assets.iter().map(|a|(a.id.as_str(),a)).collect::<BTreeMap<_,_>>();let mut rows=bundle.sessions.clone();
 for row in &mut rows{
  let map=|raw:&mut Option<String>|->Result<(),String>{if let Some(value)=raw.as_deref(){
   if let Some(id)=value.strip_prefix(REFERENCE){*raw=Some(root.join(&assets.get(id).ok_or("备份原件引用缺失。")?.name).to_string_lossy().into());}
   else if value.starts_with(MISSING){*raw=None;}
  }Ok(())};map(&mut row.audio_path)?;for chunk in &mut row.chunks{map(&mut chunk.path)?;}
  row.recovery=Default::default();
  if row.audio_path.as_deref().is_none_or(|p|!Path::new(p).is_absolute()){
   row.audio_stored=false;row.retention.audio_cached=false;
   if row.audio_bytes>0{row.pending_reason=Some(if row.source=="boardDevice"{"needs_device_sync"}else{"missing_backup_audio"}.into());}
  }
 }Ok(rows)
}
fn metadata(row:&Row)->Result<Vec<u8>,String>{let mut value=row.clone();value.audio_path=None;for c in &mut value.chunks{c.path=None;}value.recovery=Default::default();
 serde_json::to_vec(&value).map_err(|e|e.to_string())}
fn classify(bundle:&Bundle,current:&[Row],root:&Path,package_token:String,path:&Path)->Result<Preview,String>{
 let incoming=relocated(bundle,root)?;let expected=bundle.assets.iter().map(|a|(root.join(&a.name),a)).collect::<BTreeMap<_,_>>();
 let bytes=bundle.assets.iter().try_fold(0u64,|sum,a|sum.checked_add(a.bytes).ok_or("备份长度溢出。"))?;
 let mut out=Preview{path:path.to_string_lossy().into(),package_token,library_token:token(current)?,sessions:incoming.len(),files:bundle.assets.len(),bytes,new_sessions:Vec::new(),matching_sessions:Vec::new(),repair_sessions:Vec::new(),conflicts:Vec::new(),warnings:bundle.warnings.clone()};
 for row in &incoming{let Some(existing)=current.iter().find(|r|r.id==row.id) else{out.new_sessions.push(row.id.clone());continue;};
  if metadata(existing)?!=metadata(row)?{out.conflicts.push(Conflict{session_id:row.id.clone(),title:row.title.clone(),message:"本机分类、保护、文字、重点或原件身份已变化，不覆盖。".into()});continue;}
  let mut missing=false;let mut different=false;
  for (old,new) in std::iter::once((&existing.audio_path,&row.audio_path)).chain(existing.chunks.iter().zip(&row.chunks).map(|(a,b)|(&a.path,&b.path))){
   let Some(new)=new.as_deref().filter(|p|Path::new(p).is_absolute()) else{continue;};let Some(asset)=expected.get(Path::new(new)) else{continue;};
   match old.as_deref().filter(|p|Path::new(p).is_file()) {Some(old)=>different|=audio_storage::fingerprint(Path::new(old))?!=(asset.bytes,asset.sha256.clone()),None=>missing=true}
  }
  if different{out.conflicts.push(Conflict{session_id:row.id.clone(),title:row.title.clone(),message:"本机已有同ID的不同原音，保留本机资料。".into()});}
  else if missing{out.repair_sessions.push(row.id.clone());}else{out.matching_sessions.push(row.id.clone());}
 }Ok(out)
}
pub fn recover_pending(index:&Path,recordings:&Path)->Result<(),String>{let _operation=super::library_lifecycle::action_lock(index)?;cleanup_pending(index,recordings)}
pub(crate) fn cleanup_pending(index:&Path,recordings:&Path)->Result<(),String>{
 let journal=pending(index)?;if !journal.exists(){return Ok(());}
 regular(&journal)?;let mut raw=Vec::new();source_file(&journal)?.take(MAX_MANIFEST+1).read_to_end(&mut raw).map_err(|e|e.to_string())?;
 if raw.len() as u64>MAX_MANIFEST{return Err("未完成恢复记录过大，未删除资料。".into());}
 let job:Prepared=serde_json::from_slice(&raw).map_err(|_|"未完成恢复记录损坏，已保留文件。")?;let root=local_directory(recordings)?;
 if job.schema!=1||uuid::Uuid::parse_str(&job.id).is_err()||Path::new(&job.root)!=root||job.files.len()>16384{return Err("未完成恢复记录身份不符，未清理文件。".into());}
 let provenance=session_store::inspect_locked(index,|current|{
 let mut provenance=Vec::new();idle(current)?;
 let sources=current.iter().flat_map(|r|r.audio_path.iter().chain(r.chunks.iter().filter_map(|c|c.path.as_ref()))).filter(|p|Path::new(p).is_absolute()).cloned().collect::<Vec<_>>();
 let related=audio_artifacts::referenced_files(&root,&sources)?;
 let retained=sources.iter().map(PathBuf::from).chain(related).filter_map(|p|source_key(&p).ok()).collect::<BTreeSet<_>>();
 for (n,item) in job.files.iter().enumerate(){let asset=&item.asset;
  if !name(&asset.name)||!digest(&asset.sha256)||!asset.purpose.accepts(Path::new(&asset.name)){return Err("未完成恢复的文件身份无效，已保留资料。".into());}
  let temp=temporary(&root,&job.id,n);if temp.exists(){regular(&temp)?;fs::remove_file(&temp).map_err(|e|format!("恢复临时文件仍被占用：{e}"))?;}
  let target=root.join(&asset.name);if !target.exists(){continue;}regular(&target)?;
  if audio_storage::fingerprint(&target)?!=(asset.bytes,asset.sha256.clone()){return Err("恢复准备文件已被外部修改，未删除或覆盖，请核对。".into());}
  let owners=current.iter().filter(|r|asset.owners.contains(&r.id)||r.audio_path.as_deref()==Some(target.to_string_lossy().as_ref())||r.chunks.iter().any(|c|c.path.as_deref()==Some(target.to_string_lossy().as_ref())))
    .filter_map(|r|r.audio_path.as_deref().filter(|p|Path::new(p).is_absolute()).or_else(||r.chunks.iter().filter_map(|c|c.path.as_deref()).find(|p|Path::new(p).is_absolute()))).map(PathBuf::from).collect::<Vec<_>>();
  if owners.is_empty(){if item.created&&!retained.contains(&source_key(&target)?){fs::remove_file(&target).map_err(|e|format!("未提交的恢复文件仍被占用，可解除占用后重试：{e}"))?;}}
  else{provenance.push(audio_artifacts::RestoredArtifact{file:asset.name.clone(),purpose:asset.purpose,owners,bytes:asset.bytes,sha256:asset.sha256.clone()});}
 }
 Ok(provenance)})?;
 if !provenance.is_empty(){audio_artifacts::register_restored(&root,&provenance)?;session_store::update_checked(index,|_|Ok(()))?;}
 fs::remove_file(&journal).map_err(|e|format!("恢复准备结果尚未清理：{e}"))?;Ok(())
}
pub fn preview(index:&Path,recordings:&Path,path:&Path)->Result<Preview,String>{let _operation=super::library_lifecycle::action_lock(index)?;cleanup_pending(index,recordings)?;let (path,bundle,package)=load(path)?;classify(&bundle,&rows(index)?,recordings,package,&path)}
pub fn restore(index:&Path,recordings:&Path,request:&RestoreRequest)->Result<RestoreReport,String>{
 let _operation=super::library_lifecycle::action_lock(index)?;let root=local_directory(recordings)?;cleanup_pending(index,&root)?;let (path,bundle,package)=load(Path::new(&request.path))?;
 if package!=request.package_token{return Err("备份在预览后已变化，请重新检查。".into());}
 let current=rows(index)?;if token(&current)?!=request.library_token{return Err("本机资料库在预览后已变化，请重新检查冲突。".into());}
 let preview=classify(&bundle,&current,&root,package,&path)?;
 if !request.new_only&&!preview.conflicts.is_empty(){return Err("备份与本机已有录音冲突，未开始恢复；可明确选择仅恢复新增。".into());}
 let selected=preview.new_sessions.iter().chain(if request.new_only{[].iter()}else{preview.repair_sessions.iter()}).cloned().collect::<BTreeSet<_>>();
 let incoming=relocated(&bundle,&root)?;let mut staged=0usize;let selected_assets=bundle.assets.iter().filter(|a|a.owners.iter().any(|id|selected.contains(id))).cloned().collect::<Vec<_>>();
 // Preflight every destination before creating files; never replace originals.
 for asset in &selected_assets{let target=root.join(&asset.name);
  if target.exists(){regular(&target)?;if audio_storage::fingerprint(&target)?!=(asset.bytes,asset.sha256.clone()){return Err("本机存在同名不同内容文件，未覆盖；请核对原件。".into());}}
 }
 let job=Prepared{schema:1,id:uuid::Uuid::new_v4().to_string(),root:root.to_string_lossy().into(),files:selected_assets.iter().map(|a|PreparedAsset{asset:a.clone(),created:!root.join(&a.name).exists()}).collect()};
 let journal=pending(index)?;export::write_atomic(&journal,&serde_json::to_vec_pretty(&job).map_err(|e|e.to_string())?)?;
 let result=(||{
 for (n,asset) in selected_assets.iter().enumerate(){let target=root.join(&asset.name);if target.exists(){continue;}
  let temp=temporary(&root,&job.id,n);copy_checked(&path.join("media").join(format!("{}.bin",asset.id)),&temp,asset.bytes,&asset.sha256)?;
  let published=fs::hard_link(&temp,&target);let _=fs::remove_file(&temp);
  if let Err(e)=published{if !target.is_file()||audio_storage::fingerprint(&target)?!=(asset.bytes,asset.sha256.clone()){return Err(format!("原件准备未完成，已有资料未覆盖，可重新检查后重试：{e}"));}}
  OpenOptions::new().write(true).open(&target).and_then(|f|f.sync_all()).map_err(|e|format!("原件尚未耐久保存，资料库未提交：{e}"))?;
  staged+=1;
 }
 let mut provenance=Vec::new();
 for asset in &selected_assets{
  let owners=incoming.iter().filter(|r|asset.owners.contains(&r.id)).filter_map(|r|r.audio_path.as_deref().filter(|p|Path::new(p).is_absolute()).or_else(||r.chunks.iter().filter_map(|c|c.path.as_deref()).find(|p|Path::new(p).is_absolute()))).map(PathBuf::from).collect::<Vec<_>>();
  provenance.push(audio_artifacts::RestoredArtifact{file:asset.name.clone(),purpose:asset.purpose,owners:if owners.is_empty(){vec![root.join(&asset.name)]}else{owners},bytes:asset.bytes,sha256:asset.sha256.clone()});
 }
 session_store::update_checked(index,|rows|{
  if token(rows)?!=request.library_token{return Err("文件已准备，但资料库已变化；未覆盖新内容，请重新检查后重试。".into());}
  for row in incoming.iter().filter(|r|selected.contains(&r.id)){
   if let Some(old)=rows.iter_mut().find(|s|s.id==row.id){*old=row.clone();}else{rows.push(row.clone());}
  }Ok(())
 })?;
 audio_artifacts::register_restored(&root,&provenance)?;fs::remove_file(&journal).map_err(|e|e.to_string())?;
 Ok(RestoreReport{added:preview.new_sessions.clone(),repaired:if request.new_only{Vec::new()}else{preview.repair_sessions.clone()},
  skipped:incoming.iter().filter(|r|!selected.contains(&r.id)).map(|r|r.id.clone()).collect(),warnings:bundle.warnings.clone(),files_prepared:staged})
 })();
 if let Err(error)=result{let cleanup=cleanup_pending(index,&root).err();return Err(format!("{error}{}",cleanup.map(|e|format!("；恢复准备需重试：{e}")).unwrap_or_default()));}result
}
