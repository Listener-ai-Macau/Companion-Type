import {useEffect,useRef,useState} from 'react';
import type {CompanionV1HostSession,CompanionV1Snapshot} from '../../core/src/companionV1';
import {emptyLibraryOrganization,type CompanionLibraryOrganizationRequest} from '../../core/src/libraryOrganization';
export interface LibraryFilters {folder:string;tag:string;favorites:boolean}
export function CompanionLibraryTools({sessions,visible,selection,setSelection,filters,setFilters,blocked,onSave,onBusyChange,onUnsavedChange}:{
  sessions:CompanionV1HostSession[];visible:CompanionV1HostSession[];selection:Record<string,number>;
  setSelection:(v:Record<string,number>)=>void;filters:LibraryFilters;setFilters:(v:LibraryFilters)=>void;blocked:boolean;
  onSave?:(request:CompanionLibraryOrganizationRequest)=>Promise<CompanionV1Snapshot>;
  onBusyChange?:(v:boolean)=>void;onUnsavedChange?:(v:boolean)=>void;
}) {
 const [folder,setFolder]=useState('');const [applyFolder,setApplyFolder]=useState(false);
 const [tags,setTags]=useState('');const [tagAction,setTagAction]=useState('keep');const [favorite,setFavorite]=useState('keep');
 const [busy,setBusy]=useState(false);const active=useRef(false);const [message,setMessage]=useState('');
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
  catch(e){setMessage(`未完成保存，选择和输入仍保留：${e instanceof Error?e.message:String(e)}`);}
  finally {active.current=false;setBusy(false);onBusyChange?.(false);}
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
  </div>
  <details><summary>整理所选录音 · 已选 {ids.length} 场</summary>
   <p>文件夹是本机资料分类，不移动原音文件。支持四层路径，如“工作/项目”；标签用逗号分隔。批量保存只改已选录音。</p>
   <div className="ct-audio-tools">
    <button type="button" className="ct-action" disabled={blocked||!onSave||!visible.length||visible.length>1000} onClick={()=>setSelection(Object.fromEntries(visible.map(s=>[s.id,(s.organization??emptyLibraryOrganization()).revision])))}>选择当前筛选结果（{visible.length} 场）</button>
    <button type="button" className="ct-action" disabled={busy||!ids.length} onClick={()=>setSelection({})}>清除整理选择</button>
    <span>其中 {ids.filter(id=>!visible.some(s=>s.id===id)).length} 场不在当前筛选中</span>
   </div>
   <fieldset disabled={blocked||busy||!onSave}>
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
   {visible.length>1000?<p>一次最多整理1000场，请先缩小筛选范围。</p>:null}
  </details>
  {message?<p role="status">{message}</p>:null}
 </section>;
}
