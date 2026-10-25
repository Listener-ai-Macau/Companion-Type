import {operationErrorText} from './operationFailure';
import {useEffect,useRef,useState} from 'react';
import type {CompanionV1HostSession,CompanionV1Snapshot} from '../../core/src/companionV1';
import {emptyLibraryOrganization,type CompanionLibraryOrganizationRequest} from '../../core/src/libraryOrganization';
import type {CompanionLibraryExportRequest,CompanionLibraryExportResult} from '../../core/src/libraryOrganization';
import type {CompanionLibraryStateRequest,CompanionLibraryPurgeRequest,CompanionLibraryPurgeResult} from '../../core/src/libraryOrganization';
import {CompanionLibraryLifeActions} from './CompanionLibraryLifeActions';
export interface LibraryFilters {folder:string;tag:string;favorites:boolean;from?:string;to?:string;trash?:boolean}
export function CompanionLibraryTools({sessions,visible,selection,setSelection,filters,setFilters,blocked,onSave,onExport,onSaveLifecycle,onPurge,onBusyChange,onUnsavedChange}:{
  sessions:CompanionV1HostSession[];visible:CompanionV1HostSession[];selection:Record<string,number>;
  setSelection:(v:Record<string,number>)=>void;filters:LibraryFilters;setFilters:(v:LibraryFilters)=>void;blocked:boolean;
  onSave?:(request:CompanionLibraryOrganizationRequest)=>Promise<CompanionV1Snapshot>;
  onExport?:(request:CompanionLibraryExportRequest)=>Promise<CompanionLibraryExportResult|null>;
  onSaveLifecycle?:(request:CompanionLibraryStateRequest)=>Promise<CompanionV1Snapshot>;
  onPurge?:(request:CompanionLibraryPurgeRequest)=>Promise<CompanionLibraryPurgeResult>;
  onBusyChange?:(v:boolean)=>void;onUnsavedChange?:(v:boolean)=>void;
}) {
 const [folder,setFolder]=useState('');const [applyFolder,setApplyFolder]=useState(false);
 const [tags,setTags]=useState('');const [tagAction,setTagAction]=useState('keep');const [favorite,setFavorite]=useState('keep');
 const [busy,setBusy]=useState(false);const active=useRef(false);const [message,setMessage]=useState('');
 const [exportFormat,setExportFormat]=useState<CompanionLibraryExportRequest['format']>('audio');
 const [exportMode,setExportMode]=useState<NonNullable<CompanionLibraryExportRequest['meetingMode']>>('recorded');
 const draft=applyFolder||tagAction!=='keep'||favorite!=='keep';const ids=Object.keys(selection);
 const folders=[...new Set(sessions.flatMap(s=>{const f=s.organization?.folder??'';return f?f.split('/').map((_,i)=>f.split('/').slice(0,i+1).join('/')):[];}))].sort();
 const allTags=[...new Set(sessions.flatMap(s=>s.organization?.tags??[]))].sort();
 useEffect(()=>{onUnsavedChange?.(draft);},[draft,onUnsavedChange]);
 useEffect(()=>{const known=new Set(sessions.map(s=>s.id));if(ids.some(id=>!known.has(id)))setSelection(Object.fromEntries(Object.entries(selection).filter(([id])=>known.has(id))));},[sessions.map(s=>s.id).join('\0')]);
 const save=async()=>{
  if(blocked||active.current||!onSave||!ids.length||!draft)return;
  const request:CompanionLibraryOrganizationRequest={targets:ids.map(sessionId=>({sessionId,expectedRevision:selection[sessionId]}))};
  if(applyFolder)request.folder=folder;
  if(tagAction!=='keep'){request.tags=tags.split(/[,，]/).map(t=>t.trim()).filter(Boolean);request.tagAction=tagAction as 'add'|'remove'|'replace';}
  if(favorite!=='keep')request.favorite=favorite==='yes';
  active.current=true;setBusy(true);onBusyChange?.(true);setMessage('');
  try {await onSave(request);setSelection({});setApplyFolder(false);setTagAction('keep');setFavorite('keep');setMessage(`已保存 ${ids.length} 场录音的分类，原音文件保持原位置。`);}
  catch(e){setMessage(`未完成保存，选择和输入仍保留：${operationErrorText(e,'save')}`);}
  finally {active.current=false;setBusy(false);onBusyChange?.(false);}
 };
 const exportSelection=async()=>{
  if(blocked||active.current||!onExport||!ids.length||ids.length>1000||draft)return;
  active.current=true;setBusy(true);onBusyChange?.(true);setMessage('');
  try {
   const result=await onExport({targets:ids.map(sessionId=>({sessionId,expectedRevision:selection[sessionId]})),format:exportFormat,meetingMode:exportMode});
   setMessage(result?`已导出 ${result.sessions} 场录音到 ${result.path}。含文件清单；这是分享导出，不用于整库恢复。`:'已取消导出，所选录音仍保留。');
  } catch(e){setMessage(`未完成整批导出，选择仍保留：${operationErrorText(e,'export')}`);}
  finally{active.current=false;setBusy(false);onBusyChange?.(false);}
 };
 return <section className="ct-library-tools" aria-label="录音分类与批量整理">
  <div className="ct-audio-tools">
   <label>文件夹 <select aria-label="筛选录音文件夹" value={filters.folder} onChange={e=>setFilters({...filters,folder:e.target.value})}>
    <option value="*">全部文件夹</option><option value="">未分类</option>{folders.map(f=><option key={f} value={f}>{f}</option>)}
   </select></label>
   <label>标签 <select aria-label="筛选录音标签" value={filters.tag} onChange={e=>setFilters({...filters,tag:e.target.value})}>
    <option value="">全部标签</option>{allTags.map(t=><option key={t} value={t}>{t}</option>)}
   </select></label>
   <button type="button" className="ct-action" aria-pressed={filters.favorites} onClick={()=>setFilters({...filters,favorites:!filters.favorites})}>{filters.favorites?'查看全部收藏状态':'只看收藏'}</button>
   <button type="button" className="ct-action" disabled={blocked||busy||draft} aria-pressed={Boolean(filters.trash)} onClick={()=>{setFilters({folder:'*',tag:'',favorites:false,trash:!filters.trash});setSelection({});}}>{filters.trash?'返回录音库':`回收站（${sessions.filter(s=>s.organization?.trashedAt).length}）`}</button>
   <label>开始日期 <input type="date" aria-label="筛选录音开始日期" value={filters.from??''} onChange={e=>setFilters({...filters,from:e.target.value})}/></label>
   <label>结束日期 <input type="date" aria-label="筛选录音结束日期" value={filters.to??''} onChange={e=>setFilters({...filters,to:e.target.value})}/></label>
  </div>
  {filters.from||filters.to?<p role="status">{filters.from&&filters.to&&filters.from>filters.to?'开始日期不能晚于结束日期，请调整日期范围。':'按录音开始的本地日期筛选，包含首尾两天；时间未知的录音在清除日期后可见。'}</p>:null}
  <details><summary>整理所选录音 · 已选 {ids.length} 场</summary>
   <p>文件夹是本机资料分类，不移动原音文件。支持四层路径，如“工作/项目”；标签用逗号分隔。批量保存只改已选录音。</p>
   <div className="ct-audio-tools">
    <button type="button" className="ct-action" disabled={blocked||(!onSave&&!onExport&&!onSaveLifecycle)||!visible.length||visible.length>1000} onClick={()=>setSelection(Object.fromEntries(visible.map(s=>[s.id,(s.organization??emptyLibraryOrganization()).revision])))}>选择当前筛选结果（{visible.length} 场）</button>
    <button type="button" className="ct-action" disabled={busy||!ids.length} onClick={()=>setSelection({})}>清除整理选择</button>
    <span>其中 {ids.filter(id=>!visible.some(s=>s.id===id)).length} 场不在当前筛选中</span>
   </div>
   <fieldset disabled={blocked||busy||!onSave||filters.trash}>
    <label><input type="checkbox" aria-label="修改文件夹" checked={applyFolder} onChange={e=>setApplyFolder(e.target.checked)}/>修改文件夹</label>
    <input aria-label="目标录音文件夹" maxLength={120} value={folder} disabled={!applyFolder} onChange={e=>setFolder(e.target.value)} placeholder="留空表示移到未分类"/>
    <label>标签操作 <select aria-label="批量标签操作" value={tagAction} onChange={e=>setTagAction(e.target.value)}>
     <option value="keep">保持标签</option><option value="add">添加标签</option><option value="remove">移除标签</option><option value="replace">替换全部标签</option>
    </select></label>
    <input aria-label="批量录音标签" maxLength={500} value={tags} disabled={tagAction==='keep'} onChange={e=>setTags(e.target.value)} placeholder="例如：访谈，重点"/>
    <label>收藏 <select aria-label="批量收藏操作" value={favorite} onChange={e=>setFavorite(e.target.value)}>
     <option value="keep">保持收藏状态</option><option value="yes">设为收藏</option><option value="no">取消收藏</option>
    </select></label>
    <button type="button" className="ct-action" disabled={!ids.length||!draft} onClick={()=>void save()}>{busy?'正在保存分类…':`保存 ${ids.length} 场分类`}</button>
   </fieldset>
   {onExport&&!filters.trash?<fieldset disabled={blocked||busy}>
    <legend>导出所选录音</legend>
    <label>内容 <select aria-label="批量导出格式" value={exportFormat} onChange={e=>setExportFormat(e.target.value as CompanionLibraryExportRequest['format'])}>
     <option value="audio">原音 WAV</option><option value="txt">转写与笔记 TXT</option><option value="json">结构化记录 JSON</option>
     <option value="markdown">已保存纪要 Markdown</option><option value="srt">带真实时间轴的字幕 SRT</option>
    </select></label>
    {exportFormat==='markdown'||exportFormat==='json'?<label>纪要版本 <select aria-label="批量导出纪要版本" value={exportMode} onChange={e=>setExportMode(e.target.value as typeof exportMode)}>
     <option value="recorded">各录音原模式</option><option value="offlineStore">离线纪要</option><option value="onlineLive">在线纪要</option>
    </select></label>:null}
    <p>选择保存目录后，每次建立新目录，附录音清单。同名文件不会互相覆盖；任一录音尚不具备所选内容时整批不导出，不调用云端补内容。</p>
    {draft?<p>请先保存或撤销上面的分类修改，再导出。</p>:null}
    <button type="button" className="ct-action" disabled={!ids.length||ids.length>1000||draft} onClick={()=>void exportSelection()}>{busy?'正在处理所选录音…':`导出 ${ids.length} 场录音`}</button>
   </fieldset>:null}
   {onSaveLifecycle||onPurge?<CompanionLibraryLifeActions sessions={sessions} selection={selection} setSelection={setSelection} trash={Boolean(filters.trash)}
    blocked={blocked||busy} draft={draft} onSave={onSaveLifecycle} onPurge={onPurge} onBusyChange={onBusyChange}/>:null}
   {visible.length>1000?<p>一次最多整理1000场，请先缩小筛选范围。</p>:null}
  </details>
  {message?<p role="status">{message}</p>:null}
 </section>;
}
