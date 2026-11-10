import {NoteImagePreview} from './NoteImagePreview';
import type {CompanionBookmarkRequest,CompanionMeetingImageNoteRequest} from '@companion-type/core';
import {operationErrorText} from './operationFailure';
import { useEffect, useRef, useState } from 'react';
import { Pencil, StickyNote, Trash2 } from 'lucide-react';
import { CompanionExportFeedback, type CompanionExportFeedbackValue } from './CompanionExportFeedback';
import { type CompanionMeetingNoteRequest, type CompanionV1HostSession, type CompanionV1Snapshot,
  companionBookmarkAudioPosition, normalizeCompanionNoteText } from '@companion-type/core';

type Edit = { text:string; anchor:string; originalText:string; originalAnchor:string; revision:number };
type Draft = { text?:string; anchor?:string; pending?:CompanionMeetingNoteRequest; pendingImage?:CompanionMeetingImageNoteRequest; pendingAnchor?:CompanionBookmarkRequest; edits?:Record<string,Edit> };
const time = (ms:number) => `${Math.floor(ms/60000).toString().padStart(2,'0')}:${(Math.floor(ms/1000)%60).toString().padStart(2,'0')}`;

export function CompanionMeetingNotes({session,blocked,persistenceReady,anyRecording,onSave,onAddImage,onPreviewImage,onSaveAnchor,playbackPosition,onSeek,onExport,exportFeedback,onOrganizeSaved,organizeSavedBlocked=false,onHelp,onUnsavedChange,onBusyChange,compact=false,resultEditLabel}: {
  compact?:boolean;
  resultEditLabel?:string;
  onHelp?:()=>void;
  session:CompanionV1HostSession;
  blocked:boolean;
  persistenceReady:boolean;
  anyRecording:boolean;
  onAddImage?:(request:CompanionMeetingImageNoteRequest)=>Promise<CompanionV1Snapshot|null>;
  onPreviewImage?:(sessionId:string,noteId:string)=>Promise<string>;
  onSaveAnchor?:(request:CompanionBookmarkRequest)=>Promise<CompanionV1Snapshot>;
  playbackPosition?:()=>number|null;
  onSave?:(request:CompanionMeetingNoteRequest)=>Promise<CompanionV1Snapshot>;
  onSeek:(sessionId:string,bookmarkId:string,positionMs:number)=>Promise<void>;
  onExport?:(format:'txt'|'json')=>Promise<void>;
  onOrganizeSaved?:()=>void;
  organizeSavedBlocked?:boolean;
  exportFeedback?:CompanionExportFeedbackValue | null;
  onUnsavedChange?:(dirty:boolean)=>void;
  onBusyChange?:(busy:boolean)=>void;
}) {
  const [drafts,setDrafts]=useState<Record<string,Draft>>({});
  const [messages,setMessages]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(false);
  const [composers,setComposers]=useState<Record<string,boolean>>({});
  const active=useRef(false);
  const draft=drafts[session.id]??{};
  const disabled=blocked||busy||!onSave||!persistenceReady;
  const notes=session.meetingNotes??[];
  const points=session.bookmarks??[];
  const dirty=Object.values(drafts).some((d)=>Boolean(d.text?.trim()||d.anchor||d.pending||d.pendingImage||d.pendingAnchor
    ||Object.values(d.edits??{}).some((e)=>e.text!==e.originalText||e.anchor!==e.originalAnchor)));
  useEffect(()=>{onUnsavedChange?.(dirty);},[dirty,onUnsavedChange]);
  useEffect(()=>()=>{onUnsavedChange?.(false);onBusyChange?.(false);},[onUnsavedChange,onBusyChange]);
  const change=(id:string,update:(d:Draft)=>Draft)=>setDrafts((all)=>({...all,[id]:update(all[id]??{})}));
  const message=(id:string,value:string)=>setMessages((all)=>({...all,[id]:value}));
  const save=async(request:CompanionMeetingNoteRequest)=>{
    if(active.current||disabled||!onSave)return;
    active.current=true;setBusy(true);onBusyChange?.(true);message(request.sessionId,'');
    change(request.sessionId,(d)=>({...d,pending:request}));
    try {
      const saved=await onSave(request);
      const row=saved.host.sessions.find((s)=>s.id===request.sessionId);
      const note=row?.meetingNotes?.find((n)=>n.id===request.noteId);
      if(!row||saved.host.persistence?.status!=='ready'||(request.action==='delete'?Boolean(note)
        : !note||note.text!==normalizeCompanionNoteText(request.text??'')||(note.bookmarkId??null)!==(request.bookmarkId??null))) {
        throw new Error('尚未确认备注已保存到本机；输入仍保留，可以重试。');
      }
      change(request.sessionId,(d)=>{
        const edits={...d.edits};delete edits[request.noteId];
        return {...d,pending:undefined,pendingImage:undefined,pendingAnchor:undefined,edits,text:request.action==='add'?'':d.text,anchor:request.action==='add'?'':d.anchor};
      });
      message(request.sessionId,request.action==='delete'?'备注已删除，原始录音和转写保留。':'备注已保存到本机。');
      if(compact&&request.action==='add')setComposers(all=>({...all,[request.sessionId]:false}));
    } catch(error) {message(request.sessionId,operationErrorText(error,'save'));}
    finally {active.current=false;setBusy(false);onBusyChange?.(false);}
  };
  const addImage=async()=>{
    if(active.current||disabled||!onAddImage)return;const request=draft.pendingImage??{sessionId:session.id,noteId:crypto.randomUUID(),expectedRevision:session.noteRevision??0,text:draft.text??'',bookmarkId:draft.anchor||null};active.current=true;setBusy(true);onBusyChange?.(true);message(session.id,'');change(session.id,d=>({...d,pendingImage:request}));
    try{const saved=await onAddImage(request);if(!saved){change(session.id,d=>({...d,pendingImage:undefined}));message(session.id,'已取消选择，输入仍保留。');return;}const row=saved.host.sessions.find(s=>s.id===request.sessionId),note=row?.meetingNotes?.find(n=>n.id===request.noteId);if(saved.host.persistence?.status!=='ready'||!note?.image||note.text!==(normalizeCompanionNoteText(request.text??'')||'图片备注')||(note.bookmarkId??null)!==(request.bookmarkId??null))throw Error('图片尚未确认保存，输入仍保留。');change(session.id,d=>({...d,text:'',anchor:'',pending:undefined,pendingImage:undefined,pendingAnchor:undefined}));message(session.id,'图片与备注已保存在本机，原图会随录音备份。');}
    catch(error){message(session.id,operationErrorText(error,'save'));}finally{active.current=false;setBusy(false);onBusyChange?.(false);}
  };
  const markPosition=async()=>{
    if(active.current||disabled||anyRecording||!onSaveAnchor)return;
    const position=playbackPosition?.();
    if(!draft.pendingAnchor&&(position==null||!Number.isSafeInteger(position)||position<0)){
      message(session.id,'先打开回听，选好原音位置，再关联到这条补充。');return;
    }
    const request=draft.pendingAnchor??{sessionId:session.id,bookmarkId:crypto.randomUUID(),expectedRevision:session.bookmarkRevision??0,action:'addAt' as const,label:'补充位置',positionMs:position!};
    active.current=true;setBusy(true);onBusyChange?.(true);message(session.id,'');
    change(session.id,d=>({...d,pendingAnchor:request}));
    try{
      const saved=await onSaveAnchor(request),row=saved.host.sessions.find(s=>s.id===request.sessionId),point=row?.bookmarks?.find(p=>p.id===request.bookmarkId);
      if(saved.host.persistence?.status!=='ready'||!point||point.positionMs!==request.positionMs)throw Error('尚未确认这个重点已保存到会议库，请保留输入并重试保存。');
      change(session.id,d=>({...d,anchor:point.id,pendingAnchor:undefined,pending:undefined,pendingImage:undefined}));
      message(session.id,`已选择回听位置 ${time(point.audioPositionMs??point.positionMs)}，继续保存文字或添加图片。`);
    }catch(error){message(session.id,operationErrorText(error,'save'));}
    finally{active.current=false;setBusy(false);onBusyChange?.(false);}
  };
  const selectAnchor=(value:string,onChange:(value:string)=>void,label:string)=><select aria-label={label} disabled={busy}
    value={value} onChange={(event)=>onChange(event.target.value)}>
    <option value="">整条录音，不关联时间点</option>
    {value&&!points.some((p)=>p.id===value)?<option value={value}>关联的重点已删除，请重新选择</option>:null}
    {points.map((point)=><option key={point.id} value={point.id}>{time(point.audioPositionMs??point.positionMs)} · {point.label}</option>)}
  </select>;
  const recheck=()=>change(session.id,(d)=>{
    const edits=Object.fromEntries(Object.entries(d.edits??{}).map(([id,edit])=>[id,{...edit,revision:session.noteRevision??0}]));
    return {...d,pending:undefined,pendingImage:undefined,pendingAnchor:undefined,edits};
  });
  const composer=<>
    <p>{compact?`这里单独记背景，不改原话，也不自动加入整理。${resultEditLabel?`要修改整理内容，请在“整理结果”里选“${resultEditLabel}”。`:''}`:'补充背景或待确认事项，可关联已标记的位置。备注单独保存，不会改写原始转写，也不自动加入整理。'}</p>
    <textarea aria-label="新录音备注" maxLength={4000} rows={3} placeholder="记下背景，或需要回头核对的事情…"
      value={draft.text??''} disabled={busy} onChange={(event)=>{message(session.id,'');change(session.id,(d)=>({...d,text:event.target.value,pending:undefined,pendingImage:undefined}));}}/>
    <div className="ct-notes-controls">
      {!compact||points.length>0||draft.anchor?selectAnchor(draft.anchor??'',(anchor)=>change(session.id,(d)=>({...d,anchor,pending:undefined,pendingAnchor:undefined,pendingImage:undefined})),'新备注关联重点'):null}
      {onSaveAnchor&&playbackPosition?<button type="button" className="ct-action" disabled={disabled||anyRecording||!session.audioStored} onClick={()=>void markPosition()}>{draft.pendingAnchor?'重试关联位置':'关联当前回听位置'}</button>:null}

      <button type="button" className="ct-action" disabled={disabled||(!draft.pending&&!draft.text?.trim())} onClick={()=>void save(draft.pending??{
        sessionId:session.id,noteId:crypto.randomUUID(),expectedRevision:session.noteRevision??0,action:'add',
        text:draft.text??'',bookmarkId:draft.anchor||null,
      })}>{busy?'正在保存…':draft.pending?'重试保存备注':'保存备注'}</button>
      {onAddImage?<button type="button" className="ct-action" disabled={disabled||anyRecording||!session.audioStored} onClick={()=>void addImage()}>{draft.pendingImage?'重试添加图片':'添加图片'}</button>:null}
      {draft.pendingImage||draft.pending||draft.pendingAnchor?<button type="button" className="ct-action" disabled={busy} onClick={recheck}>保留输入，重新核对</button>:null}
    </div>
    {onAddImage?<small>图片支持JPEG、PNG、WebP，每张20MB以内。可关联上方重点位置；图片仅本机保存，不自动上传AI。</small>:null}
  </>;
  return <section id="ct-recording-notes" className={compact?"ct-meeting-notes ct-notes-inline":"ct-meeting-notes"} aria-label="录音备注">
    {!compact||notes.length>0?<div className="ct-notes-heading"><h4><StickyNote size={16}/>{compact?'补充':'录音备注'}</h4><span>用户补充 · {notes.length} 条</span></div>:null}
    {compact?<details className="ct-note-composer" open={Boolean(composers[session.id])} onToggle={event=>{
      const open=event.currentTarget.open;
      setComposers(all=>all[session.id]===open?all:{...all,[session.id]:open});
      if(open){
        const field=event.currentTarget.querySelector<HTMLTextAreaElement>('textarea');
        field?.focus({preventScroll:true});
        field?.scrollIntoView({block:'center'});
      }
    }}><summary>添加备注或图片{draft.text?.trim()||draft.anchor||draft.pending||draft.pendingImage||draft.pendingAnchor?' · 未保存':''}</summary>{composer}</details>:composer}
    {messages[session.id]?<p role="status" className="ct-notes-message">{messages[session.id]}{draft.pending&&onHelp?<button type="button" className="ct-text-button" onClick={onHelp}>查看恢复方法</button>:null}</p>:null}
    {onOrganizeSaved && notes.length>0 && messages[session.id]==='备注已保存到本机。' ? <div className="ct-notes-controls">
      <button type="button" className="ct-action" disabled={disabled||anyRecording||dirty||organizeSavedBlocked}
        onClick={onOrganizeSaved}>用原话＋补充整理</button>
    </div> : null}
    {notes.length?<ol className="ct-notes-list">{notes.map((note)=>{
      const edit=draft.edits?.[note.id];
      const point=points.find((p)=>p.id===note.bookmarkId);
      const position=point?companionBookmarkAudioPosition(session,point):null;
      return <li key={note.id}>
        {edit?<div className="ct-notes-edit">
          <textarea aria-label={`编辑备注 ${note.id}`} maxLength={4000} rows={3} value={edit.text} disabled={busy}
            onChange={(event)=>change(session.id,(d)=>({...d,pending:undefined,edits:{...d.edits,[note.id]:{...edit,text:event.target.value}}}))}/>
          <div className="ct-notes-controls">
            {selectAnchor(edit.anchor,(anchor)=>change(session.id,(d)=>({...d,pending:undefined,edits:{...d.edits,[note.id]:{...edit,anchor}}})),`备注关联重点 ${note.id}`)}
            <button type="button" className="ct-action" disabled={disabled||!edit.text.trim()} onClick={()=>void save({
              sessionId:session.id,noteId:note.id,expectedRevision:edit.revision,action:'edit',text:edit.text,bookmarkId:edit.anchor||null,
            })}>保存修改</button>
            <button type="button" className="ct-action" disabled={busy} onClick={()=>change(session.id,(d)=>{
              const edits={...d.edits};delete edits[note.id];return {...d,edits,pending:undefined};
            })}>取消编辑</button>
          </div>
        </div>:<p className="ct-note-body">{note.text}</p>}{note.image?<NoteImagePreview sessionId={session.id} note={note} onLoad={onPreviewImage}/>:null}
        <div className="ct-notes-controls">
          {!compact||note.bookmarkId?<small>{point?`关联重点 · ${time(position??point.positionMs)} ${point.label}`:note.bookmarkId?'关联的重点已删除；备注仍保留。':'整条录音的补充内容'}</small>:null}
          {point?<button type="button" className="ct-action" disabled={blocked||busy||anyRecording||position==null} onClick={()=>void onSeek(session.id,point.id,position!)
            .catch((error)=>message(session.id,operationErrorText(error,'playback')))}>定位原音</button>:null}
          {!edit?<button type="button" className="ct-action" aria-label={`编辑备注 ${note.id}`} disabled={disabled} onClick={()=>change(session.id,(d)=>({...d,edits:{...d.edits,[note.id]:{
            text:note.text,anchor:note.bookmarkId??'',originalText:note.text,originalAnchor:note.bookmarkId??'',revision:session.noteRevision??0,
          }}}))}><Pencil size={13}/>编辑</button>:null}
          <button type="button" className="ct-action" aria-label={`删除备注 ${note.id}`} disabled={disabled} onClick={()=>{if(note.image&&!window.confirm('删除这条人工图片备注？原图会随录音保留至整条录音永久清除。'))return;void save({
            sessionId:session.id,noteId:note.id,expectedRevision:session.noteRevision??0,action:'delete',
          });}}><Trash2 size={13}/>删除</button>
        </div>
      </li>;
    })}</ol>:null}
    {exportFeedback?<CompanionExportFeedback feedback={exportFeedback} className="ct-export-result ct-note-export-feedback"/>:null}
    {notes.length&&onExport?<div className="ct-note-takeaway">
      <button type="button" className="ct-action" disabled={blocked||busy||anyRecording||!persistenceReady||exportFeedback?.kind==='pending'}
        onClick={()=>void onExport('txt')}>{exportFeedback?.kind==='pending'?'正在导出…':'导出文字与补充'}</button>
      <details className="ct-note-export"><summary>其他格式</summary>
        <button type="button" className="ct-action" disabled={blocked||busy||anyRecording||!persistenceReady||exportFeedback?.kind==='pending'}
          onClick={()=>void onExport('json')}>保存完整数据（JSON）</button>
      </details>
    </div>:null}
    {!onSave?<small>请在 Companion Type 桌面版保存备注。</small>:null}
  </section>;
}
