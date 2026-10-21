import { useEffect, useRef, useState } from 'react';
import { Bookmark, Pencil, Trash2 } from 'lucide-react';
import { type CompanionBookmarkRequest, type CompanionV1HostSession, type CompanionV1Snapshot,
  companionBookmarkAudioPosition, companionBookmarkUtteranceIndex } from '@companion-type/core';

type Draft = { label?: string; pending?: CompanionBookmarkRequest; renames?: Record<string,{value:string;original:string}> };
const time = (ms:number) => `${Math.floor(ms/60000).toString().padStart(2,'0')}:${Math.floor(ms/1000)%60 < 10 ? '0' : ''}${Math.floor(ms/1000)%60}`;

export function CompanionBookmarks({ session, blocked, anyRecording, persistenceReady, onSave, playbackPosition, onSeek,
  onShowOriginal, onExport, onUnsavedChange, onBusyChange }: {
  session:CompanionV1HostSession;
  blocked:boolean;
  anyRecording:boolean;
  persistenceReady:boolean;
  onSave?:(request:CompanionBookmarkRequest)=>Promise<CompanionV1Snapshot>;
  playbackPosition:()=>number|null;
  onSeek:(sessionId:string,bookmarkId:string,positionMs:number)=>Promise<void>;
  onShowOriginal:()=>void;
  onExport?:()=>Promise<void>;
  onUnsavedChange?:(dirty:boolean)=>void;
  onBusyChange?:(busy:boolean)=>void;
}) {
  const [drafts,setDrafts]=useState<Record<string,Draft>>({});
  const [messages,setMessages]=useState<Record<string,string>>({});
  const [selected,setSelected]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(false);
  const active=useRef(false);
  const draft=drafts[session.id]??{};
  const live=session.status==='recording' && ['boardDevice','deviceFlash'].includes(session.source)
    && session.deviceRecordingId != null && Boolean(session.sourceDeviceId);
  const disabled=blocked||busy||!onSave||!persistenceReady;
  const dirty=Object.values(drafts).some((d)=>Boolean(d.label?.trim()||d.pending
    ||Object.values(d.renames??{}).some((r)=>r.value!==r.original)));
  useEffect(()=>{onUnsavedChange?.(dirty);},[dirty,onUnsavedChange]);
  const change=(sessionId:string,edit:(draft:Draft)=>Draft)=>setDrafts((all)=>({...all,[sessionId]:edit(all[sessionId]??{})}));
  const save=async (request:CompanionBookmarkRequest) => {
    if (active.current||disabled||!onSave) return;
    active.current=true; setBusy(true); onBusyChange?.(true);
    change(request.sessionId,(d)=>({...d,pending:request}));
    try {
      const saved=await onSave(request);
      const row=saved.host.sessions.find((s)=>s.id===request.sessionId);
      const point=row?.bookmarks?.find((b)=>b.id===request.bookmarkId);
      if (!row||saved.host.persistence?.status!=='ready'||(request.action==='delete' ? Boolean(point)
        : !point || (request.label != null && point.label!==request.label.trim()))) {
        throw new Error('尚未确认这个重点已保存到会议库，请保留输入并重试保存。');
      }
      change(request.sessionId,(d)=>{
        const renames={...d.renames}; delete renames[request.bookmarkId];
        return {...d, pending:undefined, label:request.action==='addLive'||request.action==='addAt' ? '' : d.label,renames};
      });
      setMessages((all)=>({...all,[request.sessionId]:'重点已保存到本机。'}));
    } catch (error) {
      setMessages((all)=>({...all,[request.sessionId]:error instanceof Error ? error.message : String(error)}));
    } finally {active.current=false; setBusy(false); onBusyChange?.(false);}
  };
  const request=(action:CompanionBookmarkRequest['action'],id:string,label?:string,positionMs?:number):CompanionBookmarkRequest=>({
    sessionId:session.id,bookmarkId:id,expectedRevision:session.bookmarkRevision??0,action,label,positionMs,
  });
  const add=()=>{
    if (draft.pending) { void save(draft.pending); return; }
    const position=live ? undefined : playbackPosition();
    if (!live && (position == null||!Number.isSafeInteger(position)||position<0)) {
      setMessages((all)=>({...all,[session.id]:'先准备回听并选择原音中的位置，再添加重点。'})); return;
    }
    void save(request(live?'addLive':'addAt',crypto.randomUUID(),draft.label?.trim()||'重点',position??undefined));
  };
  const points=[...(session.bookmarks??[])].sort((a,b)=>(a.audioPositionMs??a.positionMs)-(b.audioPositionMs??b.positionMs));
  const selectedPoint=points.find((p)=>p.id===selected[session.id]);
  const originalIndex=selectedPoint ? companionBookmarkUtteranceIndex(session,selectedPoint) : null;
  return <section className="ct-bookmarks" aria-label="会议重点">
    <div className="ct-bookmarks-heading"><h4><Bookmark size={16}/>重点标记</h4>
      <span>{points.length} 个 · 已保存的标记可在重启后继续查看</span></div>
    <p>{live ? '标记设备已保存到的录音位置，不中断录音。收录完成后可定位原音。'
      : '回听时选好位置再添加重点；有真实时间轴的转写可以查看对应原文。'}</p>
    <div className="ct-bookmark-add">
      <input aria-label="重点名称" maxLength={120} placeholder="重点名称（可选）" value={draft.label??''} disabled={busy}
        onChange={(event)=>change(session.id,(d)=>({...d,label:event.target.value,pending:undefined}))}/>
      <button type="button" className="ct-action" disabled={disabled||(!live&&anyRecording)}
        title={!onSave?'请在 Companion Type 桌面版使用重点标记':undefined} onClick={add}>
        {busy?'正在保存…':draft.pending?'重试保存重点':live?'标记当前录音':'标记回听位置'}</button>
    </div>
    {draft.pending ? <button type="button" className="ct-action" disabled={busy}
      onClick={()=>change(session.id,(d)=>({...d,pending:undefined}))}>保留输入，重新核对</button> : null}
    {messages[session.id] ? <p role="status" className="ct-bookmark-message">{messages[session.id]}</p> : null}
    {points.length ? <ol className="ct-bookmark-list">{points.map((point)=>{
      const position=companionBookmarkAudioPosition(session,point);
      const rename=draft.renames?.[point.id];
      return <li key={point.id}>
        <span className="ct-bookmark-time">{time(position??point.positionMs)}</span>
        <div className="ct-bookmark-content">{rename ? <div className="ct-bookmark-edit">
          <input aria-label={`重命名 ${point.label}`} maxLength={120} value={rename.value} disabled={busy}
            onChange={(event)=>change(session.id,(d)=>({...d,pending:undefined,renames:{...d.renames,[point.id]:{...rename,value:event.target.value}}}))}/>
          <button type="button" className="ct-action" disabled={disabled||!rename.value.trim()}
            onClick={()=>void save(request('rename',point.id,rename.value.trim()))}>保存名称</button>
          <button type="button" className="ct-action" disabled={busy} onClick={()=>change(session.id,(d)=>{
            const renames={...d.renames};delete renames[point.id];return {...d,renames,pending:undefined};
          })}>取消</button></div> : <strong>{point.label}</strong>}
          <div className="ct-bookmark-actions">
            <button type="button" className="ct-action" disabled={blocked||busy||anyRecording||position==null}
              onClick={()=>void onSeek(session.id,point.id,position!).catch((error)=>setMessages((all)=>({...all,[session.id]:String(error)})))}>定位原音</button>
            <button type="button" className="ct-action" disabled={blocked||busy} onClick={()=>{
              setSelected((all)=>({...all,[session.id]:point.id})); onShowOriginal();
            }}>查看对应原文</button>
            <button type="button" className="ct-action" aria-label={`编辑重点 ${point.label}`} disabled={disabled}
              onClick={()=>change(session.id,(d)=>({...d,renames:{...d.renames,[point.id]:{value:point.label,original:point.label}}}))}><Pencil size={13}/></button>
            <button type="button" className="ct-action" aria-label={`删除重点 ${point.label}`} disabled={disabled}
              onClick={()=>void save(request('delete',point.id))}><Trash2 size={13}/></button>
          </div>
          {position==null ? <small>录音尚未收齐，或原音已删除/时间映射未确认；标记仍保留。</small> : null}
        </div>
      </li>;
    })}</ol> : null}
    {selectedPoint ? <div className="ct-bookmark-source" role="status">
      <strong>{selectedPoint.label} · 对应原文</strong>
      <p>{originalIndex==null?'这个位置没有可用的真实转写时间轴或处在语音间隔中，可先定位原音核对。'
        : `原始识别片段：${session.utterances![originalIndex].text}`}</p>
    </div> : null}
    {points.length && onExport ? <button type="button" className="ct-action" disabled={blocked||busy||anyRecording||!persistenceReady}
      onClick={()=>void onExport()}>保存重点与完整记录</button> : null}
  </section>;
}
