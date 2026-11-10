from pathlib import Path
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';B=S/'apps/windows/src-tauri/src/backend'
p=B/'meeting_note_images.rs';raw=p.read_bytes();text=raw.decode('utf-8').replace('\r\n','\n');start=text.index('fn write_new(');end=text.index('fn prepare(',start);helper=text[start:end].replace('fn write_new(','pub(crate) fn write_new(',1).replace('图片','材料')
prefix='''//! Immutable recording-owned attachments share backup and exact cleanup.
use std::{fs::{self,OpenOptions},io::Write,path::Path};
use sha2::{Digest,Sha256};
use super::audio_artifacts::{self,Purpose};
fn hash(bytes:&[u8])->String{format!("{:x}",Sha256::digest(bytes))}
fn verify(path:&Path,bytes:u64,sha:&str)->Result<(),String>{let meta=fs::symlink_metadata(path).map_err(|_|"材料文件缺失，原资料保留。")?;if !meta.is_file()||meta.file_type().is_symlink()||meta.len()!=bytes||super::audio_storage::fingerprint(path)?!=(bytes,sha.into()){return Err("材料文件已变化，原资料保留。".into());}Ok(())}
'''
(B/'owned_attachments.rs').write_text(prefix+helper,encoding='utf-8',newline='\n');text=text[:start]+text[end:];text='use super::owned_attachments::write_new;\n'+text;text=text.replace('File,OpenOptions','File');p.write_bytes(text.replace('\n','\r\n' if b'\r\n' in raw else '\n').encode('utf-8'))
def edit(path,old,new):
    raw=path.read_bytes();text=raw.decode('utf-8').replace('\r\n','\n');assert text.count(old)==1,(path,old[:100]);path.write_bytes(text.replace(old,new).replace('\n','\r\n' if b'\r\n' in raw else '\n').encode('utf-8'))
edit(B/'audio_artifacts.rs','    NotePreview,','    NotePreview,\n    DocumentOriginal,\n    DocumentText,')
edit(B/'audio_artifacts.rs','            Self::NotePreview => ext.eq_ignore_ascii_case("jpg"),','            Self::NotePreview => ext.eq_ignore_ascii_case("jpg"),\n            Self::DocumentOriginal => ["pdf","docx","xlsx","pptx","txt","md","csv"].iter().any(|allowed|ext.eq_ignore_ascii_case(allowed)),\n            Self::DocumentText => ext.eq_ignore_ascii_case("json"),')
edit(B/'audio_artifacts.rs','Purpose::NoteImage|Purpose::NotePreview','Purpose::NoteImage|Purpose::NotePreview|Purpose::DocumentOriginal|Purpose::DocumentText')
edit(B/'mod.rs','pub(crate) mod meeting_note_images;','pub(crate) mod meeting_note_images;\npub(crate) mod document_context;\npub(crate) mod owned_attachments;')
edit(B/'mod.rs','    fn save_meeting_note(&self, request: meeting_notes::Request) -> Result<CompanionV1Snapshot, String>;','''    fn save_meeting_note(&self, request: meeting_notes::Request) -> Result<CompanionV1Snapshot, String>;
    fn change_document_context(&self,_request:document_context::Request)->Result<document_context::View,String>{Err("当前环境不支持文档材料。".into())}''')
edit(B/'mod.rs','    fn save_meeting_image_note(&self,request:meeting_note_images::Request)->Result<CompanionV1Snapshot,String>{','''    fn change_document_context(&self,request:document_context::Request)->Result<document_context::View,String>{
        let mut snapshot=self.snapshot.lock().map_err(|_|"会议库暂不可用。")?;if snapshot.host.persistence.status!="ready"{return Err("请先恢复会议库，原资料保留。".into());}
        let row=snapshot.host.sessions.iter_mut().find(|s|s.id==request.session_id).ok_or("这场会议已不存在。")?;let result=document_context::commit(row,&request)?;snapshot.updated_at=connection_timestamp();refresh_privacy_counts(&mut snapshot);Ok(result)
    }
    fn save_meeting_image_note(&self,request:meeting_note_images::Request)->Result<CompanionV1Snapshot,String>{''')
p=S/'apps/windows/src-tauri/src/companion_v1.rs'
edit(p,'    pub meeting_notes: Vec<crate::backend::meeting_notes::Note>,','''    pub meeting_notes: Vec<crate::backend::meeting_notes::Note>,
    #[serde(default,skip_serializing_if="crate::backend::document_context::Metadata::is_empty")]
    pub document_context: crate::backend::document_context::Metadata,''')
edit(p,'    CompanionV1HostSession { meeting_tracks: None,','    CompanionV1HostSession { document_context: Default::default(), meeting_tracks: None,')
for relative in ['audio_storage.rs','export.rs','minutes.rs','persistence.rs']:
    edit(B/relative,'        CompanionV1HostSession { meeting_tracks: None,','        CompanionV1HostSession { document_context: Default::default(), meeting_tracks: None,')
edit(S/'apps/windows/src-tauri/src/coordinator.rs','    pub fn save_meeting_image_note(&self,request:crate::backend::meeting_note_images::Request)->Result<CompanionV1Snapshot,String>{','''    pub fn change_document_context(&self,request:crate::backend::document_context::Request)->Result<crate::backend::document_context::View,String>{
        if self.device_operation.load(Ordering::Acquire)==11{return Err("软件正在更新，请稍后保存文档。".into());}self.backend.change_document_context(request)
    }
    pub fn save_meeting_image_note(&self,request:crate::backend::meeting_note_images::Request)->Result<CompanionV1Snapshot,String>{''')
print('Windows recording-owned document metadata, durable immutable attachment storage, shared image writer and lifecycle ownership integrated. Native compile pending.')
