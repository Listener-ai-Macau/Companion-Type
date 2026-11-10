from pathlib import Path
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055')
def edit(name,old,new):
 p=S/name;s=p.read_text(encoding='utf-8');assert s.count(old)==1,(name,old[:90],s.count(old));p.write_text(s.replace(old,new),encoding='utf-8',newline='\r\n')
edit('apps/windows/src-tauri/src/backend/mod.rs','pub(crate) mod meeting_notes;','pub(crate) mod meeting_notes;\npub(crate) mod meeting_note_images;')
edit('apps/windows/src-tauri/src/backend/mod.rs','    fn save_meeting_note(&self, request: meeting_notes::Request) -> Result<CompanionV1Snapshot, String>;', '    fn save_meeting_note(&self, request: meeting_notes::Request) -> Result<CompanionV1Snapshot, String>;\n    fn save_meeting_image_note(&self,_request:meeting_note_images::Request)->Result<CompanionV1Snapshot,String>{Err("当前环境未提供图片备注。".into())}')
edit('apps/windows/src-tauri/src/backend/mod.rs','    fn save_meeting_note(&self, request: meeting_notes::Request) -> Result<CompanionV1Snapshot, String> {','''    fn save_meeting_image_note(&self,request:meeting_note_images::Request)->Result<CompanionV1Snapshot,String>{
        let mut snapshot=self.snapshot.lock().map_err(|_|"会议库暂不可用。")?;
        if snapshot.host.persistence.status!="ready"{return Err("请先恢复或重试保存会议库；输入仍保留。".into());}
        let row=snapshot.host.sessions.iter_mut().find(|s|s.id==request.session_id).ok_or("这场会议已不存在，未修改其它会议。")?;
        meeting_note_images::commit(row,&request,&connection_timestamp())?;snapshot.updated_at=connection_timestamp();refresh_privacy_counts(&mut snapshot);Ok(snapshot.clone())
    }
    fn save_meeting_note(&self, request: meeting_notes::Request) -> Result<CompanionV1Snapshot, String> {''')
edit('apps/windows/src-tauri/src/coordinator.rs','    pub fn save_meeting_note(&self, request:', '''    pub fn save_meeting_image_note(&self,request:crate::backend::meeting_note_images::Request)->Result<CompanionV1Snapshot,String>{
        if self.device_operation.load(Ordering::Acquire)==11{return Err("软件正在更新，请稍后保存图片。".into());}self.backend.save_meeting_image_note(request)
    }
    pub fn save_meeting_note(&self, request:''')
edit('apps/windows/src-tauri/src/commands.rs','#[tauri::command]\npub async fn save_companion_meeting_note', '''#[derive(serde::Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct NoteImageChoice {session_id:String,note_id:String,expected_revision:u64,text:String,bookmark_id:Option<String>}
#[tauri::command]
pub async fn add_companion_image_note(app:AppHandle,coordinator:CompanionCoordinatorState<'_>,request:NoteImageChoice)->Result<Option<CompanionV1Snapshot>,String>{
    let chosen=app.dialog().file().add_filter("图片（每张最多20MB）",&["jpg","jpeg","png","webp"]).blocking_pick_file();
    let Some(chosen)=chosen else{return Ok(None);};let path=chosen.into_path().map_err(|_|"请选择保存在本机的图片。")?;let coordinator=coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move||coordinator.save_meeting_image_note(crate::backend::meeting_note_images::Request{session_id:request.session_id,note_id:request.note_id,expected_revision:request.expected_revision,text:request.text,bookmark_id:request.bookmark_id,image_path:path.to_string_lossy().into_owned()})).await.map_err(|_|"图片保存任务未完成，输入仍保留。".to_string())?.map(Some)
}
#[tauri::command]
pub async fn preview_companion_note_image(coordinator:CompanionCoordinatorState<'_>,session_id:String,note_id:String)->Result<String,String>{
    let coordinator=coordinator.inner().clone();tauri::async_runtime::spawn_blocking(move||{let snapshot=coordinator.snapshot()?;let row=snapshot.host.sessions.iter().find(|s|s.id==session_id).ok_or("这场会议已不存在。")?;crate::backend::meeting_note_images::preview(row,&note_id)}).await.map_err(|_|"图片预览尚未完成。".to_string())?
}
#[tauri::command]
pub async fn save_companion_meeting_note''')
edit('apps/windows/src-tauri/src/lib.rs','            commands::save_companion_meeting_note,','            commands::save_companion_meeting_note,\n            commands::add_companion_image_note,\n            commands::preview_companion_note_image,')
# Preserve old Note struct literals while adding a defaulted optional field.
count=0
for p in (S/'apps/windows/src-tauri/src').rglob('*.rs'):
 if p.name in ['meeting_notes.rs','meeting_note_images.rs']:continue
 s=p.read_text(encoding='utf-8');original=s
 # Existing fixture literals all put bookmark_id immediately before created_at.
 import re
 s,n=re.subn(r'(bookmark_id:\s*(?:None|Some\([^\n]*?\)),\s*)(created_at:)',r'\1image:None,\2',s);count+=n
 if s!=original:p.write_text(s,encoding='utf-8',newline='\r\n')
print('Windows image-note native integration; optional field added to',count,'existing fixture literals')
