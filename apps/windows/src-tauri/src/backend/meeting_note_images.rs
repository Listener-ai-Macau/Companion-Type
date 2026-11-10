//! Recording-owned raster attachments. Originals and bounded previews share the
//! existing verified audio ownership, backup and permanent cleanup mechanism.
use std::{fs::{self,File,OpenOptions},io::{Cursor,Read,Write},path::{Path,PathBuf}};
use serde::{Deserialize,Serialize};
use sha2::{Digest,Sha256};
use crate::companion_v1::CompanionV1HostSession;
use super::{audio_artifacts::{self,Purpose},meeting_notes::{self,Action}};
const MAX_IMAGE:u64=20*1024*1024;

#[derive(Clone,Debug,Deserialize,Serialize,PartialEq,Eq)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Attachment {
    pub file:String,pub name:String,pub bytes:u64,pub sha256:String,
    pub preview:String,pub preview_bytes:u64,pub preview_sha256:String,
}
#[derive(Clone,Debug,Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Request {
    pub session_id:String,pub note_id:String,pub expected_revision:u64,
    pub text:String,pub bookmark_id:Option<String>,pub image_path:String,
}
fn hash(bytes:&[u8])->String{format!("{:x}",Sha256::digest(bytes))}
fn root()->Result<PathBuf,String>{super::audio_storage::recording_root()?.canonicalize().map_err(|_|"本机资料目录不可用。".into())}
fn anchor(session:&CompanionV1HostSession,root:&Path)->Result<PathBuf,String>{
    super::library_lifecycle::require_available(session)?;
    if !session.audio_stored||!session.retention.audio_cached {return Err("请先保存或导入这条录音，再添加图片；文字输入仍保留。".into());}
    let source=Path::new(session.audio_path.as_deref().ok_or("录音原音尚未保存。")?).canonicalize().map_err(|_|"录音来源暂不可用。")?;
    if source.parent()!=Some(root)||!audio_artifacts::is_managed(&source){return Err("录音来源不在当前资料目录，原文件保留。".into());}Ok(source)
}
fn leaf(value:&str)->bool{!value.is_empty()&&!value.contains(['/', '\\', ':'])&&Path::new(value).file_name().and_then(|n|n.to_str())==Some(value)}
fn validate_metadata(session:&CompanionV1HostSession,note_id:&str,a:&Attachment)->Result<(),String>{
    let prefix=format!("note-{}-{}-",&hash(session.id.as_bytes())[..24],note_id);
    if !leaf(&a.file)||!leaf(&a.preview)||!a.file.starts_with(&prefix)||!a.preview.starts_with(&prefix)
        ||!a.preview.ends_with(".preview.jpg")||a.bytes==0||a.bytes>MAX_IMAGE||a.preview_bytes==0||a.preview_bytes>4*1024*1024
        ||a.sha256.len()!=64||a.preview_sha256.len()!=64||!a.sha256.bytes().chain(a.preview_sha256.bytes()).all(|b|b.is_ascii_hexdigit())
        ||!["jpg","png","webp"].iter().any(|ext|a.file.ends_with(&format!(".{ext}"))) {
        return Err("图片归属资料无效，原文件保留。".into());
    }Ok(())
}
fn verify(path:&Path,bytes:u64,sha:&str)->Result<(),String>{
    let meta=fs::symlink_metadata(path).map_err(|_|"图片原件或预览缺失，备注仍保留。")?;
    if !meta.is_file()||meta.file_type().is_symlink()||meta.len()!=bytes||super::audio_storage::fingerprint(path)?!=(bytes,sha.into()) {return Err("图片已变化或校验失败，备注与原文件保留。".into());}Ok(())
}
fn write_new(source:&Path,target:&Path,purpose:Purpose,bytes:&[u8])->Result<(),String>{
    if target.exists(){
        verify(target,bytes.len() as u64,&hash(bytes))?;
        return audio_artifacts::seal_note_retry(source,target,purpose,bytes.len() as u64,&hash(bytes));
    }
    let lease=match audio_artifacts::WriteLease::begin(source,target,purpose){
        Ok(lease)=>lease,
        Err(first)=>{
            let root=target.parent().ok_or("图片目录无效。")?;let source_leaf=source.file_name().and_then(|n|n.to_str()).ok_or("图片来源无效。")?;let file=target.file_name().and_then(|n|n.to_str()).ok_or("图片名称无效。")?;
            let item=audio_artifacts::BackupFile{file:file.into(),sources:vec![source_leaf.into()],purpose,bytes:bytes.len() as u64,sha256:hash(bytes)};
            // An earlier failed write may have safely checkpointed this exact
            // absent owned leaf as Gone. Reuse backup's proven no-file retry.
            audio_artifacts::retry_absent_backup_file(root,&item).map_err(|_|first)?;
            audio_artifacts::WriteLease::begin(source,target,purpose)?
        }
    };
    let result=(||{
        let temp=target.with_file_name(format!(".note-image-{}.tmp",uuid::Uuid::new_v4()));
        let result=(||{let mut file=OpenOptions::new().write(true).create_new(true).open(&temp).map_err(|_|"图片暂不能保存，输入仍保留。")?;file.write_all(bytes).and_then(|_|file.sync_all()).map_err(|_|"图片写入未完成，输入仍保留。")?;drop(file);
            // Publish only a previously absent leaf, as in library backup restore.
            fs::hard_link(&temp,target).map_err(|_|"图片尚未提交，已有资料未覆盖，请重试。")?;Ok(())})();let _=fs::remove_file(temp);result
    })();if result.is_ok(){if let Some(lease)=lease{lease.finish()?;}}result
}
fn prepare(session:&CompanionV1HostSession,request:&Request)->Result<Attachment,String>{
    let root=root()?;let source=anchor(session,&root)?;
    if session.id.is_empty()||session.id.len()>200||uuid::Uuid::parse_str(&request.note_id).is_err(){return Err("会议或图片标识无效。".into());}
    let input=Path::new(&request.image_path);let meta=fs::symlink_metadata(input).map_err(|_|"所选图片暂不可读，输入仍保留。")?;
    if !meta.is_file()||meta.file_type().is_symlink()||meta.len()==0||meta.len()>MAX_IMAGE{return Err("请选择20MB以内的JPEG、PNG或WebP原图片。".into());}
    let mut bytes=Vec::with_capacity(meta.len() as usize);File::open(input).map_err(|_|"所选图片暂不可读。")?.take(MAX_IMAGE+1).read_to_end(&mut bytes).map_err(|_|"所选图片读取未完成。")?;
    if bytes.len() as u64!=meta.len(){return Err("图片在读取期间发生变化，请重新选择。".into());}
    let format=image::guess_format(&bytes).map_err(|_|"图片无法读取，请选择JPEG、PNG或WebP。")?;
    let ext=match format{image::ImageFormat::Jpeg=>"jpg",image::ImageFormat::Png=>"png",image::ImageFormat::WebP=>"webp",_=>return Err("请选择JPEG、PNG或WebP图片。".into())};
    let (w,h)=image::ImageReader::with_format(Cursor::new(&bytes),format).into_dimensions().map_err(|_|"图片尺寸无法读取。")?;
    if w==0||h==0||w>24000||h>24000||u64::from(w)*u64::from(h)>32_000_000{return Err("图片尺寸过大，请缩小至3200万像素以内。".into());}
    let mut reader=image::ImageReader::with_format(Cursor::new(&bytes),format);let mut limits=image::Limits::default();limits.max_alloc=Some(192*1024*1024);limits.max_image_width=Some(24000);limits.max_image_height=Some(24000);reader.limits(limits);
    let decoded=reader.decode().map_err(|_|"图片无法完整解码或需要过多内存，请缩小后重试。")?;let small=decoded.thumbnail(1280,1280).to_rgb8();drop(decoded);let mut preview=Vec::new();image::codecs::jpeg::JpegEncoder::new_with_quality(&mut preview,85).encode_image(&image::DynamicImage::ImageRgb8(small)).map_err(|_|"图片预览生成未完成。")?;
    if preview.len()>4*1024*1024{return Err("图片预览过大，请缩小图片后重试。".into());}
    let digest=hash(&bytes);
    if let Some(prior)=session.meeting_notes.iter().find(|n|n.id==request.note_id){if prior.image.as_ref().is_none_or(|a|a.sha256!=digest){return Err("这个备注标识已用于其它内容，请重新打开核对。".into());}}
    let stem=format!("note-{}-{}-{}",&hash(session.id.as_bytes())[..24],request.note_id,&digest[..16]);let name=input.file_name().and_then(|n|n.to_str()).unwrap_or("图片").chars().filter(|c|!c.is_control()).take(200).collect();
    let result=Attachment{file:format!("{stem}.{ext}"),name,bytes:bytes.len() as u64,sha256:digest,preview:format!("{stem}.preview.jpg"),preview_bytes:preview.len() as u64,preview_sha256:hash(&preview)};
    write_new(&source,&root.join(&result.file),Purpose::NoteImage,&bytes)?;write_new(&source,&root.join(&result.preview),Purpose::NotePreview,&preview)?;Ok(result)
}
pub(crate) fn commit(session:&mut CompanionV1HostSession,request:&Request,now:&str)->Result<(),String>{
    let mut saved=None;
    super::session_store::update_checked(&super::persistence::state_file_path(),|rows|{
        let row=rows.iter_mut().find(|r|r.id==session.id).ok_or("这场会议已不存在，输入仍保留。")?;
        if row.device_recording_id!=session.device_recording_id||row.source_device_id!=session.source_device_id{return Err("录音归属已变化，未修改其它会议。".into());}
        let text=if request.text.trim().is_empty(){"图片备注".to_owned()}else{request.text.clone()};let note=meeting_notes::Request{session_id:request.session_id.clone(),note_id:request.note_id.clone(),expected_revision:request.expected_revision,action:Action::Add,text:Some(text),bookmark_id:request.bookmark_id.clone()};
        // Prevalidate optimistic revision, bookmark identity and limits before any file write.
        let mut next=row.clone();let changed=meeting_notes::apply(&mut next,&note,now)?;
        let attachment=prepare(row,request)?;
        if !changed {
            let prior=row.meeting_notes.iter().find(|n|n.id==request.note_id).and_then(|n|n.image.as_ref());if prior!=Some(&attachment){return Err("这个备注标识已用于其它内容，请重新打开核对。".into());}
        }else{next.meeting_notes.iter_mut().find(|n|n.id==request.note_id).ok_or("图片备注保存结果缺失。")?.image=Some(attachment);*row=next;}
        saved=Some((row.note_revision,row.meeting_notes.clone()));Ok(())
    })?;
    if let Some((revision,notes))=saved{session.note_revision=revision;session.meeting_notes=notes;session.exported_at=None;}Ok(())
}
pub(crate) fn preview(session:&CompanionV1HostSession,note_id:&str)->Result<String,String>{
    use base64::Engine;
    let root=root()?;let source=anchor(session,&root)?;let a=session.meeting_notes.iter().find(|n|n.id==note_id).and_then(|n|n.image.as_ref()).ok_or("这条备注没有图片。")?;validate_metadata(session,note_id,a)?;let file=root.join(&a.preview);verify(&file,a.preview_bytes,&a.preview_sha256)?;
    if !audio_artifacts::source_references(&file)?.contains(&audio_artifacts::reference_key(&source)?){return Err("图片预览不属于这条录音。".into());}
    let bytes=fs::read(file).map_err(|_|"图片预览暂不可读。")?;Ok(format!("data:image/jpeg;base64,{}",base64::engine::general_purpose::STANDARD.encode(bytes)))
}
pub(crate) fn original(session:&CompanionV1HostSession,note_id:&str)->Result<PathBuf,String>{
    let root=root()?;let source=anchor(session,&root)?;let a=session.meeting_notes.iter().find(|n|n.id==note_id).and_then(|n|n.image.as_ref()).ok_or("图片不存在。")?;validate_metadata(session,note_id,a)?;let path=root.join(&a.file);verify(&path,a.bytes,&a.sha256)?;
    if !audio_artifacts::source_references(&path)?.contains(&audio_artifacts::reference_key(&source)?){return Err("图片不属于这条录音，原文件保留。".into());}Ok(path)
}
fn html(value:&str)->String{value.replace('&',"&amp;").replace('<',"&lt;").replace('>',"&gt;").replace('"',"&quot;").replace('\'',"&#39;")}
pub(crate) fn bundle(session:&CompanionV1HostSession,content:&str,ids:&[String])->Result<Vec<u8>,String>{
    let selected=session.meeting_notes.iter().filter(|n|ids.contains(&n.id)).collect::<Vec<_>>();
    let total=selected.iter().filter_map(|n|n.image.as_ref()).try_fold(0u64,|sum,a|sum.checked_add(a.bytes)).ok_or("所选图片过大，请分批导出。")?;
    if total>64*1024*1024||content.len()>8*1024*1024{return Err("所选图文超过64MB，请减少图片后分批导出。".into());}
    let mut zip=zip::ZipWriter::new(Cursor::new(Vec::new()));let options=zip::write::SimpleFileOptions::default();
    let mut page=format!("<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none';img-src 'self';style-src 'unsafe-inline'\"><title>{}</title><style>body{{font:17px/1.8 system-ui;max-width:900px;margin:40px auto;padding:0 24px;color:#242631}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}}figure{{margin:24px 0;padding-top:20px;border-top:1px solid #ddd}}img{{max-width:100%;height:auto}}figcaption{{color:#657080}}</style><h1>{}</h1><pre>{}</pre>",html(&session.title),html(&session.title),html(content));
    zip.start_file("会议材料.md",options).map_err(|_|"无法准备图文文件。")?;zip.write_all(format!("# {}\n\n{content}",session.title).as_bytes()).map_err(|_|"图文写入未完成。")?;
    for note in &selected {if let Some(a)=&note.image{
        let source=original(session,&note.id)?;let ext=source.extension().and_then(|v|v.to_str()).ok_or("图片格式无效。")?;let name=format!("images/{}.{ext}",note.id);
        zip.start_file(&name,options).map_err(|_|"无法写入所选图片。")?;let mut file=File::open(source).map_err(|_|"原图片暂不可读取。")?;let mut digest=Sha256::new();let mut count=0u64;let mut buffer=[0u8;65536];loop{let n=file.read(&mut buffer).map_err(|_|"原图片读取未完成。")?;if n==0{break;}count+=n as u64;if count>a.bytes{return Err("图片在导出时发生变化，请重试。".into());}digest.update(&buffer[..n]);zip.write_all(&buffer[..n]).map_err(|_|"图片导出未完成。")?;}if count!=a.bytes||format!("{:x}",digest.finalize())!=a.sha256{return Err("图片在导出时发生变化，请重试。".into());}
        page.push_str(&format!("<figure><h3>{}</h3><img src=\"{}\" alt=\"{}\"><figcaption>{} · 用户添加原图</figcaption></figure>",html(&note.text),name,html(&a.name),html(&a.name)));
    }}
    page.push_str("</html>");zip.start_file("打开阅读.html",options).map_err(|_|"图文网页准备未完成。")?;zip.write_all(page.as_bytes()).map_err(|_|"图文网页写入未完成。")?;zip.start_file("备注来源.json",options).map_err(|_|"备注来源准备未完成。")?;zip.write_all(&serde_json::to_vec_pretty(&selected).map_err(|_|"备注来源无法读取。")?).map_err(|_|"备注来源写入未完成。")?;
    zip.finish().map(|v|v.into_inner()).map_err(|_|"图文ZIP尚未完整生成。".into())
}

#[cfg(test)]
mod tests {
 use super::*;
 #[test]
 fn image_notes_preserve_sources_roundtrip_selected_export_backup_and_exact_cleanup(){
    use crate::companion_v1::{apply_fixture_control,fixture_snapshot,CompanionV1AudioChunk};
    let base=std::env::temp_dir().join(format!("companion-note-images-{}",uuid::Uuid::new_v4()));let source=base.join("source");let target=base.join("restored");let backups=base.join("backups");for p in [&source,&target,&backups]{fs::create_dir_all(p).unwrap();}let source=source.canonicalize().unwrap();let target=target.canonicalize().unwrap();let index=base.join("sessions.json");
    let old_root=std::env::var_os("COMPANION_TYPE_RECORDING_DIR");let old_state=std::env::var_os("COMPANION_TYPE_STATE_PATH");std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&source);std::env::set_var("COMPANION_TYPE_STATE_PATH",&index);
    let mut sound=denzic_host_audio_v1_core::wav::wav_header(32000).to_vec();sound.extend(vec![0;32000]);let audio=source.join("public-a.wav");let other=source.join("public-b.wav");fs::write(&audio,&sound).unwrap();fs::write(&other,&sound).unwrap();
    let mut snapshot=apply_fixture_control(fixture_snapshot(),serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap()).unwrap();snapshot.host.persistence.status="ready".into();snapshot.meeting.active=false;snapshot.device.recording=false;let mut row=snapshot.host.sessions.remove(0);row.id=format!("import-{}",uuid::Uuid::new_v4().simple());row.source="hostMicrophone".into();row.status="minutesReady".into();row.device_recording_key=None;row.device_recording_id=None;row.source_device_id=None;row.device_sha256=None;row.audio_path=Some(audio.to_string_lossy().into());row.audio_stored=true;row.retention.audio_cached=true;row.audio_bytes=sound.len() as u64;row.duration_ms=1000;row.meeting_tracks=None;row.chunks=vec![CompanionV1AudioChunk{id:"a".into(),path:row.audio_path.clone(),started_at:None,stopped_at:None,duration_ms:1000,bytes:sound.len() as u64,status:"sealed".into()}];row.meeting_notes.clear();row.note_revision=0;row.bookmarks.clear();row.recovery=Default::default();let mut second=row.clone();second.id="other-public-recording".into();second.audio_path=Some(other.to_string_lossy().into());second.chunks[0].path=second.audio_path.clone();super::super::session_store::save(&index,&[row.clone(),second.clone()]).unwrap();
    let input=base.join("public-board.png");image::RgbImage::from_pixel(24,18,image::Rgb([20,40,60])).save(&input).unwrap();let original_image=fs::read(&input).unwrap();let text_before=row.transcript_text.clone();let request=Request{session_id:row.id.clone(),note_id:uuid::Uuid::new_v4().to_string(),expected_revision:0,text:"公开图片备注 <script> & 12000元".into(),bookmark_id:None,image_path:input.to_string_lossy().into()};
    commit(&mut row,&request,"2026-11-10T05:00:00Z").unwrap();assert_eq!(row.note_revision,1);let attachment=row.meeting_notes[0].image.clone().unwrap();assert_eq!(fs::read(original(&row,&request.note_id).unwrap()).unwrap(),original_image);assert!(preview(&row,&request.note_id).unwrap().starts_with("data:image/jpeg;base64,"));assert_eq!(row.transcript_text,text_before);assert_eq!(fs::read(&audio).unwrap(),sound);
    commit(&mut row,&request,"2026-11-10T05:00:01Z").unwrap();assert_eq!(row.note_revision,1,"exact lost-reply retry must not duplicate a note");
    let bad=base.join("broken.png");fs::write(&bad,b"not a raster").unwrap();let mut bad_request=request.clone();bad_request.note_id=uuid::Uuid::new_v4().to_string();bad_request.expected_revision=1;bad_request.image_path=bad.to_string_lossy().into();let saved=fs::read(&index).unwrap();assert!(commit(&mut row,&bad_request,"now").is_err());assert_eq!(fs::read(&index).unwrap(),saved);
    bad_request.expected_revision=0;bad_request.image_path="missing-private-path".into();assert!(commit(&mut row,&bad_request,"now").unwrap_err().contains("备注已变化"));assert_eq!(fs::read(&index).unwrap(),saved);
    let mut foreign=second.clone();foreign.meeting_notes=row.meeting_notes.clone();assert!(preview(&foreign,&request.note_id).is_err(),"cross-recording image must not be exposed");
    // Reproduce an interrupted ownership checkpoint, then retry with identical
    // selected bytes. Only this known image can be sealed; no unknown adoption.
    let manifest=source.join(".audio-artifacts.json");let mut intent:serde_json::Value=serde_json::from_slice(&fs::read(&manifest).unwrap()).unwrap();for item in intent["files"].as_array_mut().unwrap(){if item["file"]==attachment.file{item["phase"]="prepared".into();item["identity"]=serde_json::Value::Null;}}fs::write(&manifest,serde_json::to_vec(&intent).unwrap()).unwrap();commit(&mut row,&request,"retry").unwrap();
    fs::remove_file(source.join(&attachment.preview)).unwrap();let mut intent:serde_json::Value=serde_json::from_slice(&fs::read(&manifest).unwrap()).unwrap();for item in intent["files"].as_array_mut().unwrap(){if item["file"]==attachment.preview{item["phase"]="gone".into();item["identity"]=serde_json::Value::Null;}}fs::write(&manifest,serde_json::to_vec(&intent).unwrap()).unwrap();commit(&mut row,&request,"retry-absent-owned-preview").unwrap();assert!(preview(&row,&request.note_id).is_ok());assert_eq!(row.note_revision,1);
    let hidden=meeting_notes::Request{session_id:row.id.clone(),note_id:uuid::Uuid::new_v4().to_string(),expected_revision:1,action:Action::Add,text:Some("UNSELECTED_PRIVATE_NOTE".into()),bookmark_id:None};meeting_notes::commit(&mut row,&hidden,"now").unwrap();
    let choice=super::super::content_export::Selection{minutes:false,transcript:false,highlights:false,timeline:false,note_ids:vec![request.note_id.clone()]};let prepared=super::super::content_export::prepare(&row,"offlineStore",super::super::export::MeetingExportFormat::Bundle,&choice).unwrap();let mut archive=zip::ZipArchive::new(Cursor::new(prepared.bytes)).unwrap();let mut html=String::new();archive.by_name("打开阅读.html").unwrap().read_to_string(&mut html).unwrap();assert!(html.contains("&lt;script&gt;")&&!html.contains("<script>")&&!html.contains("UNSELECTED_PRIVATE_NOTE"));let image_name=format!("images/{}.png",request.note_id);let mut packed=Vec::new();archive.by_name(&image_name).unwrap().read_to_end(&mut packed).unwrap();assert_eq!(packed,original_image);
    snapshot.host.sessions=vec![row.clone(),second.clone()];let report=super::super::library_backup::save(&snapshot,&source,&backups).unwrap();assert_eq!(report.files,4);std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&target);let restored=super::super::library_backup::restore_files(Path::new(&report.path),&target).unwrap();let mut copy=restored.iter().find(|r|r.id==row.id).unwrap().clone();assert_eq!(copy.meeting_notes,row.meeting_notes);assert_eq!(fs::read(original(&copy,&request.note_id).unwrap()).unwrap(),original_image);assert!(preview(&copy,&request.note_id).is_ok());
    let copy_index=base.join("restored.json");super::super::session_store::save(&copy_index,&restored).unwrap();std::env::set_var("COMPANION_TYPE_STATE_PATH",&copy_index);let delete=meeting_notes::Request{session_id:copy.id.clone(),note_id:request.note_id.clone(),expected_revision:copy.note_revision,action:Action::Delete,text:None,bookmark_id:None};meeting_notes::commit(&mut copy,&delete,"now").unwrap();assert!(target.join(&attachment.file).exists(),"entry deletion must keep owned original until recording purge");
    let protected=restored.iter().find(|r|r.id==second.id).unwrap().audio_path.clone().unwrap();audio_artifacts::erase(&target,&[copy.audio_path.clone().unwrap()],&[protected.clone()]).unwrap();assert!(!target.join(&attachment.file).exists()&&!target.join(&attachment.preview).exists());assert_eq!(fs::read(protected).unwrap(),sound,"exact cleanup must preserve another recording");
    match old_root{Some(v)=>std::env::set_var("COMPANION_TYPE_RECORDING_DIR",v),None=>std::env::remove_var("COMPANION_TYPE_RECORDING_DIR")};match old_state{Some(v)=>std::env::set_var("COMPANION_TYPE_STATE_PATH",v),None=>std::env::remove_var("COMPANION_TYPE_STATE_PATH")};assert!(base.canonicalize().unwrap().starts_with(std::env::temp_dir().canonicalize().unwrap()));fs::remove_dir_all(base).unwrap();
 }
}
