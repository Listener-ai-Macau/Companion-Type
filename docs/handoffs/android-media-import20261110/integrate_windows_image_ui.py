from pathlib import Path
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/companion-device-closure055')
def mutate(name,fn):
 p=S/name;s=p.read_text(encoding='utf-8');p.write_text(fn(s),encoding='utf-8',newline='\r\n')
def edit(name,old,new):
 def apply(s):assert s.count(old)==1,(name,old[:100],s.count(old));return s.replace(old,new)
 mutate(name,apply)
edit('apps/windows/src/companionClient.ts','export async function saveCompanionMeetingNote(','''export async function addCompanionImageNote(request:import('@companion-type/core').CompanionMeetingImageNoteRequest):Promise<CompanionV1Snapshot|null>{
  if(!isTauriRuntime())throw Error('请在桌面版添加本机图片。');return invoke('add_companion_image_note',{request});
}
export async function previewCompanionNoteImage(sessionId:string,noteId:string):Promise<string>{
  if(!isTauriRuntime())throw Error('请在桌面版查看本机图片。');return invoke('preview_companion_note_image',{sessionId,noteId});
}
export async function saveCompanionMeetingNote(''')
edit('apps/windows/src/App.tsx','  saveCompanionMeetingNote,','  saveCompanionMeetingNote,\n  addCompanionImageNote,\n  previewCompanionNoteImage,')
edit('apps/windows/src/App.tsx','      onSaveNote={isTauriRuntime()', '''      onAddImageNote={isTauriRuntime()?(request)=>exclusive('refresh',async()=>{try{const saved=await addCompanionImageNote(request);if(saved)setSnapshot(saved);return saved;}catch(error){try{setSnapshot(await getCompanionSnapshot());}catch{}throw error;}}):undefined}
      onPreviewNoteImage={isTauriRuntime()?previewCompanionNoteImage:undefined}
      onSaveNote={isTauriRuntime()''')
edit('packages/ui/src/CompanionDashboard.tsx','  onSaveNote?: (request:', '''  onAddImageNote?:(request:import('@companion-type/core').CompanionMeetingImageNoteRequest)=>Promise<CompanionV1Snapshot|null>;
  onPreviewNoteImage?:(sessionId:string,noteId:string)=>Promise<string>;
  onSaveNote?: (request:''')
edit('packages/ui/src/CompanionDashboard.tsx','  onSaveNote,','  onSaveNote,\n  onAddImageNote,\n  onPreviewNoteImage,')
edit('packages/ui/src/CompanionDashboard.tsx','persistenceReady={!storageBlocked} onSave={onSaveNote} onBusyChange=', 'persistenceReady={!storageBlocked} onSave={onSaveNote} onAddImage={onAddImageNote} onPreviewImage={onPreviewNoteImage} onBusyChange=')
edit('packages/ui/src/CompanionMeetingNotes.tsx',"import {operationErrorText}","import {NoteImagePreview} from './NoteImagePreview';\nimport type {CompanionMeetingImageNoteRequest} from '@companion-type/core';\nimport {operationErrorText}")
edit('packages/ui/src/CompanionMeetingNotes.tsx','pending?:CompanionMeetingNoteRequest;', 'pending?:CompanionMeetingNoteRequest; pendingImage?:CompanionMeetingImageNoteRequest;')
edit('packages/ui/src/CompanionMeetingNotes.tsx','anyRecording,onSave,onSeek', 'anyRecording,onSave,onAddImage,onPreviewImage,onSeek')
edit('packages/ui/src/CompanionMeetingNotes.tsx','  onSave?:(request:CompanionMeetingNoteRequest)', '''  onAddImage?:(request:CompanionMeetingImageNoteRequest)=>Promise<CompanionV1Snapshot|null>;
  onPreviewImage?:(sessionId:string,noteId:string)=>Promise<string>;
  onSave?:(request:CompanionMeetingNoteRequest)''')
edit('packages/ui/src/CompanionMeetingNotes.tsx','Boolean(d.text?.trim()||d.pending', 'Boolean(d.text?.trim()||d.pending||d.pendingImage')
edit('packages/ui/src/CompanionMeetingNotes.tsx','  const selectAnchor=', '''  const addImage=async()=>{
    if(active.current||disabled||!onAddImage)return;const request=draft.pendingImage??{sessionId:session.id,noteId:crypto.randomUUID(),expectedRevision:session.noteRevision??0,text:draft.text??'',bookmarkId:draft.anchor||null};active.current=true;setBusy(true);onBusyChange?.(true);message(session.id,'');change(session.id,d=>({...d,pendingImage:request}));
    try{const saved=await onAddImage(request);if(!saved){change(session.id,d=>({...d,pendingImage:undefined}));message(session.id,'已取消选择，输入仍保留。');return;}const row=saved.host.sessions.find(s=>s.id===request.sessionId),note=row?.meetingNotes?.find(n=>n.id===request.noteId);if(saved.host.persistence.status!=='ready'||!note?.image||note.text!==(normalizeCompanionNoteText(request.text??'')||'图片备注')||(note.bookmarkId??null)!==(request.bookmarkId??null))throw Error('图片尚未确认保存，输入仍保留。');change(session.id,d=>({...d,text:'',anchor:'',pendingImage:undefined}));message(session.id,'图片与备注已保存在本机，原图会随录音备份。');}
    catch(error){message(session.id,operationErrorText(error,'save'));}finally{active.current=false;setBusy(false);onBusyChange?.(false);}
  };
  const selectAnchor=''')
edit('packages/ui/src/CompanionMeetingNotes.tsx','return {...d,pending:undefined,edits};','return {...d,pending:undefined,pendingImage:undefined,edits};')
edit('packages/ui/src/CompanionMeetingNotes.tsx','      {draft.pending?<button', '''      {onAddImage?<button type="button" className="ct-action" disabled={disabled||anyRecording||!session.audioStored} onClick={()=>void addImage()}>{draft.pendingImage?'重试添加图片':'添加图片'}</button>:null}
      {draft.pendingImage?<button type="button" className="ct-action" disabled={busy} onClick={recheck}>保留输入，重新核对</button>:null}
      {draft.pending?<button''')
edit('packages/ui/src/CompanionMeetingNotes.tsx','    </div>\n  </>;','    </div>\n    {onAddImage?<small>图片支持JPEG、PNG、WebP，每张20MB以内。可关联上方重点位置；图片仅本机保存，不自动上传AI。</small>:null}\n  </>;')
edit('packages/ui/src/CompanionMeetingNotes.tsx','        </div>:<p className="ct-note-body">{note.text}</p>}','        </div>:<p className="ct-note-body">{note.text}</p>}{note.image?<NoteImagePreview sessionId={session.id} note={note} onLoad={onPreviewImage}/>:null}')
# The original text-note deletion remains reversible at recording level; disclose image retention.
edit('packages/ui/src/CompanionMeetingNotes.tsx',"onClick={()=>void save({\n            sessionId:session.id,noteId:note.id", "onClick={()=>{if(note.image&&!window.confirm('删除这条人工图片备注？原图会随录音保留至整条录音永久清除。'))return;void save({\n            sessionId:session.id,noteId:note.id")
edit('packages/ui/src/CompanionMeetingNotes.tsx','          })}><Trash2 size={13}/>删除</button>', '          });}}><Trash2 size={13}/>删除</button>')
print('Windows image note picker/preview wired through existing notes busy, draft, library and source ownership paths')
