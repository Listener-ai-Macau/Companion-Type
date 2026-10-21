import { useEffect, useRef, useState } from 'react';
import { Pencil, StickyNote, Trash2 } from 'lucide-react';
import { type CompanionMeetingNoteRequest, type CompanionV1HostSession, type CompanionV1Snapshot,
  companionBookmarkAudioPosition, normalizeCompanionNoteText } from '@companion-type/core';

type Edit = { text:string; anchor:string; originalText:string; originalAnchor:string; revision:number };
type Draft = { text?:string; anchor?:string; pending?:CompanionMeetingNoteRequest; edits?:Record<string,Edit> };
const time = (ms:number) => `${Math.floor(ms/60000).toString().padStart(2,'0')}:${(Math.floor(ms/1000)%60).toString().padStart(2,'0')}`;

export function CompanionMeetingNotes({session,blocked,persistenceReady,anyRecording,onSave,onSeek,onExport,onUnsavedChange,onBusyChange,compact=false}: {
  compact?:boolean;
  session:CompanionV1HostSession;
  blocked:boolean;
  persistenceReady:boolean;
  anyRecording:boolean;
  onSave?:(request:CompanionMeetingNoteRequest)=>Promise<CompanionV1Snapshot>;
  onSeek:(sessionId:string,bookmarkId:string,positionMs:number)=>Promise<void>;
  onExport?:(format:'txt'|'json')=>Promise<void>;
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
  const dirty=Object.values(drafts).some((d)=>Boolean(d.text?.trim()||d.pending
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
        return {...d,pending:undefined,edits,text:request.action==='add'?'':d.text,anchor:request.action==='add'?'':d.anchor};
      });
      message(request.sessionId,request.action==='delete'?'备注已删除，原始录音和转写保留。':'备注已保存到本机。');
      if(compact&&request.action==='add')setComposers(all=>({...all,[request.sessionId]:false}));
    } catch(error) {message(request.sessionId,error instanceof Error?error.message:String(error));}
    finally {active.current=false;setBusy(false);onBusyChange?.(false);}
  };
  const selectAnchor=(value:string,onChange:(value:string)=>void,label:string)=><select aria-label={label} disabled={busy}
    value={value} onChange={(event)=>onChange(event.target.value)}>
    <option value="">整条录音，不关联时间点</option>
    {value&&!points.some((p)=>p.id===value)?<option value={value}>关联的重点已删除，请重新选择</option>:null}
    {points.map((point)=><option key={point.id} value={point.id}>{time(point.audioPositionMs??point.positionMs)} · {point.label}</option>)}
  </select>;
  const recheck=()=>change(session.id,(d)=>{
    const edits=Object.fromEntries(Object.entries(d.edits??{}).map(([id,edit])=>[id,{...edit,revision:session.noteRevision??0}]));
    return {...d,pending:undefined,edits};
  });
  const composer=<>
    <p>{compact?'补充单独保存，不改原话，也不自动加入整理。':'补充背景或待确认事项，可关联已标记的位置。备注单独保存，不会改写原始转写，也不自动加入整理。'}</p>
    <textarea aria-label="新录音备注" maxLength={4000} rows={3} placeholder="记下背景，或需要回头核对的事情…"
      value={draft.text??''} disabled={busy} onChange={(event)=>{message(session.id,'');change(session.id,(d)=>({...d,text:event.target.value,pending:undefined}));}}/>
    <div className="ct-notes-controls">
      {!compact||points.length>0||draft.anchor?selectAnchor(draft.anchor??'',(anchor)=>change(session.id,(d)=>({...d,anchor,pending:undefined})),'新备注关联重点'):null}
      <button type="button" className="ct-action" disabled={disabled||(!draft.pending&&!draft.text?.trim())} onClick={()=>void save(draft.pending??{
        sessionId:session.id,noteId:crypto.randomUUID(),expectedRevision:session.noteRevision??0,action:'add',
        text:draft.text??'',bookmarkId:draft.anchor||null,
      })}>{busy?'正在保存…':draft.pending?'重试保存备注':'保存备注'}</button>
      {draft.pending?<button type="button" className="ct-action" disabled={busy} onClick={recheck}>保留输入，重新核对</button>:null}
    </div>
  </>;
  return <section id="ct-recording-notes" className={compact?"ct-meeting-notes ct-notes-inline":"ct-meeting-notes"} aria-label="录音备注">
    {!compact||notes.length>0?<div className="ct-notes-heading"><h4><StickyNote size={16}/>{compact?'补充':'录音备注'}</h4><span>用户补充 · {notes.length} 条</span></div>:null}
    {compact?<details className="ct-note-composer" open={Boolean(composers[session.id])} onToggle={event=>{
      const open=event.currentTarget.open;
      setComposers(all=>all[session.id]===open?all:{...all,[session.id]:open});
      if(open)event.currentTarget.querySelector<HTMLTextAreaElement>('textarea')?.focus({preventScroll:true});
    }}><summary>补充一句{draft.text?.trim()||draft.pending?' · 未保存':''}</summary>{composer}</details>:composer}
    {messages[session.id]?<p role="status" className="ct-notes-message">{messages[session.id]}</p>:null}
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
        </div>:<p className="ct-note-body">{note.text}</p>}
        <div className="ct-notes-controls">
          {!compact||note.bookmarkId?<small>{point?`关联重点 · ${time(position??point.positionMs)} ${point.label}`:note.bookmarkId?'关联的重点已删除；备注仍保留。':'整条录音的补充内容'}</small>:null}
          {point?<button type="button" className="ct-action" disabled={blocked||busy||anyRecording||position==null} onClick={()=>void onSeek(session.id,point.id,position!)
            .catch((error)=>message(session.id,error instanceof Error?error.message:String(error)))}>定位原音</button>:null}
          {!edit?<button type="button" className="ct-action" aria-label={`编辑备注 ${note.id}`} disabled={disabled} onClick={()=>change(session.id,(d)=>({...d,edits:{...d.edits,[note.id]:{
            text:note.text,anchor:note.bookmarkId??'',originalText:note.text,originalAnchor:note.bookmarkId??'',revision:session.noteRevision??0,
          }}}))}><Pencil size={13}/>编辑</button>:null}
          <button type="button" className="ct-action" aria-label={`删除备注 ${note.id}`} disabled={disabled} onClick={()=>void save({
            sessionId:session.id,noteId:note.id,expectedRevision:session.noteRevision??0,action:'delete',
          })}><Trash2 size={13}/>删除</button>
        </div>
      </li>;
    })}</ol>:null}
    {notes.length&&onExport?<div className="ct-note-takeaway">
      <button type="button" className="ct-action" disabled={blocked||busy||anyRecording||!persistenceReady}
        onClick={()=>void onExport('txt')}>保存文字和补充</button>
      <details className="ct-note-export"><summary>其他格式</summary>
        <button type="button" className="ct-action" disabled={blocked||busy||anyRecording||!persistenceReady}
          onClick={()=>void onExport('json')}>保存完整数据（JSON）</button>
      </details>
    </div>:null}
    {!onSave?<small>请在 Companion Type 桌面版保存备注。</small>:null}
  </section>;
}
