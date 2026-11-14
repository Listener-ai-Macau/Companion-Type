import {useEffect,useRef,useState,type ReactNode} from 'react';
import {Folder,Tag,Check,CheckSquare,Trash2,Shield} from 'lucide-react';
import './recordingLibraryManager.css';
import {LibraryScopeChips,type LibraryScopeChip} from '../../../packages/ui/src/LibraryScopeChips';

export type RecordingOrganization={folder:string;tags:string[]};
export type OrganizationStatus={available:boolean;revision:number;libraryToken:string;error?:string};
export type OrganizationRequest={libraryToken:string;revision:number;keys:string[];action:'move'|'addTags'|'removeTags';folder?:string;tags?:string[]};
export type BatchLifeRequest={libraryToken:string;action:'trash'|'protect'|'unprotect';targets:{key:string;revision:number}[]};
export type BatchLifeResult={libraryToken:string;completed:string[];pending:string[];warning:string|null};
type ManagedRow={key:string;title:string;organization?:RecordingOrganization;lifecycle?:{revision:number;protected:boolean}};

export function RecordingLibraryManager<T extends ManagedRow>({rows,allRows,status,blocked,searching,title,onOpen,renderRow,onChange,onBatch,onDirty}: {
 rows:T[];allRows:T[];status:OrganizationStatus|null;blocked:boolean;searching:boolean;title:string;
 onOpen:(row:T)=>void;renderRow:(row:T,activate:()=>void)=>ReactNode;
 onChange:(request:OrganizationRequest)=>Promise<boolean>;onBatch:(request:BatchLifeRequest)=>Promise<BatchLifeResult|undefined>;
 onDirty?:(dirty:boolean)=>void;
}){
 const [folder,setFolder]=useState('*'),[tag,setTag]=useState('*'),[managing,setManaging]=useState(false),[selected,setSelected]=useState<string[]>([]);
 const [destination,setDestination]=useState(''),[labels,setLabels]=useState(''),[message,setMessage]=useState(''),[error,setError]=useState(''),[working,setWorking]=useState(false);
 const active=useRef(false),disabled=blocked||working,ready=!!status?.available;
 const filterDetails=useRef<HTMLDetailsElement>(null);
 useEffect(()=>{if(!status?.available){setFolder('*');setTag('*');}},[status?.available]);
 useEffect(()=>{onDirty?.(managing&&!!selected.length&&!!(destination.trim()||labels.trim()));},[managing,selected.length,destination,labels,onDirty]);
 useEffect(()=>()=>onDirty?.(false),[onDirty]);
 const folders=Array.from(new Set(allRows.flatMap(r=>{const parts=r.organization?.folder?.split('/')??[];return parts.map((_,i)=>parts.slice(0,i+1).join('/'));}))).sort((a,b)=>a.localeCompare(b,'zh-CN'));
 const tags=Array.from(new Map(allRows.flatMap(r=>(r.organization?.tags??[]).map(t=>[t.toLowerCase(),t] as const))).values()).sort((a,b)=>a.localeCompare(b,'zh-CN'));
 const filtered=rows.filter(r=>(folder==='*'||(folder===''?!(r.organization?.folder):r.organization?.folder===folder||r.organization?.folder.startsWith(folder+'/')))&&(tag==='*'||r.organization?.tags.some(t=>t.toLowerCase()===tag.toLowerCase())));
 const missing=selected.filter(key=>!allRows.some(row=>row.key===key));
 function toggle(key:string){setError('');setMessage('');setSelected(old=>old.includes(key)?old.filter(id=>id!==key):old.length<500?[...old,key]:old);if(selected.length>=500&&!selected.includes(key))setError('一次最多选择500条录音，请先缩小范围。');}
 function selectAll(){if(filtered.length>500){setError('当前结果超过500条，请先筛选后再全选。');return;}setSelected(filtered.map(r=>r.key));setError('');setMessage('');}
 function clearSelection(){if(selected.length&&(destination.trim()||labels.trim())&&!window.confirm('还有未应用的分类输入，清除选择并放弃这些输入？'))return;setSelected([]);setDestination('');setLabels('');setError('');}
 async function change(action:OrganizationRequest['action']){
  if(active.current||disabled||!ready||!status||!selected.length)return;
  active.current=true;setWorking(true);setError('');setMessage('');
  try{
   const entered=labels.split(/[,，、]/).map(t=>t.trim()).filter(Boolean);
   if(action!=='move'&&!entered.length)throw Error('请先填写要添加或移除的标签，用逗号分隔。');
   const saved=await onChange({libraryToken:status.libraryToken,revision:status.revision,keys:[...selected],action,...(action==='move'?{folder:destination}:{tags:entered})});
   if(!saved)return;
   setMessage(action==='move'?`已将 ${selected.length} 条录音${destination.trim()?`归入“${destination.trim()}”`:'移出文件夹'}。`: `已为 ${selected.length} 条录音${action==='addTags'?'添加':'移除'}标签。`);
   if(action==='move')setDestination('');else setLabels('');
  }catch(e){setError(e instanceof Error?e.message:'分类尚未完成，选择与输入仍保留。');}
  finally{active.current=false;setWorking(false);}
 }
 async function batch(action:BatchLifeRequest['action']){
  if(active.current||disabled||!status||!selected.length)return;
  if(action==='trash'&&!window.confirm(`将选中的 ${selected.length} 条录音移入本机回收站？可以恢复；不会删除录音卡、其它资料库或已导出副本。${destination.trim()||labels.trim()?'当前未应用的分类输入不会因此保存。':''}`))return;
  active.current=true;setWorking(true);setError('');setMessage('');
  try{
   const targets=selected.map(key=>{const row=allRows.find(r=>r.key===key);if(!row)throw Error('部分选择已不在当前录音列表，请刷新并核对回收站后再操作。');return {key,revision:row.lifecycle?.revision??0};});
   const result=await onBatch({libraryToken:status.libraryToken,action,targets});if(!result)return;
   if(result.libraryToken!==status.libraryToken)throw Error('资料库已变化，请重新读取当前资料。');
   if(action==='trash')setSelected(old=>old.filter(key=>!result.completed.includes(key)));
   if(result.pending.length)setError(`已确认 ${result.completed.length} 条，另有 ${result.pending.length} 条尚未确认。${result.warning??'请刷新核对，未完成的选择仍保留。'}`);
   else setMessage(`已${action==='trash'?'移入回收站':action==='protect'?'保护':'解除保护'} ${result.completed.length} 条录音。`);
  }catch(e){setError(e instanceof Error?e.message:'批量操作尚未完成，选择仍保留。');}
  finally{active.current=false;setWorking(false);}
 }
 function finish(){if((destination.trim()||labels.trim())&&selected.length&&!window.confirm('还有未应用的分类输入，离开选择模式并放弃这些输入？'))return;setManaging(false);setSelected([]);setDestination('');setLabels('');setError('');}
 const filterChips:LibraryScopeChip[]=[];
 if(folder!=='*')filterChips.push({id:'folder',label:`文件夹：${folder||'未分类'}`,removeLabel:'取消文件夹筛选',onRemove:()=>setFolder('*')});
 if(tag!=='*')filterChips.push({id:'tag',label:`标签：${tag}`,removeLabel:'取消标签筛选',onRemove:()=>setTag('*')});
 const hiddenSelected=selected.filter(key=>!filtered.some(row=>row.key===key)).length;
 return <section className="library-manager" aria-label="录音分类与批量管理">
  <details ref={filterDetails} className="library-filter-details"><summary>筛选{filterChips.length?' · 已筛选':''}</summary>
  <div className="library-organization-filters">
   <label><Folder size={16} aria-hidden="true"/><span className="visually-hidden">按文件夹筛选</span><select aria-label="按文件夹筛选" value={folder} disabled={disabled||!ready} onChange={e=>setFolder(e.target.value)}><option value="*">全部文件夹</option><option value="">未分类</option>{folder!=='*'&&folder!==''&&!folders.includes(folder)&&<option value={folder}>{folder}（暂无录音）</option>}{folders.map(value=><option key={value} value={value}>{value.replaceAll('/',' / ')}</option>)}</select></label>
   <label><Tag size={16} aria-hidden="true"/><span className="visually-hidden">按标签筛选</span><select aria-label="按标签筛选" value={tag} disabled={disabled||!ready} onChange={e=>setTag(e.target.value)}><option value="*">全部标签</option>{tag!=='*'&&!tags.includes(tag)&&<option value={tag}>{tag}（暂无录音）</option>}{tags.map(value=><option key={value} value={value}>{value}</option>)}</select></label>
  </div></details>
  <LibraryScopeChips chips={filterChips} disabled={disabled} onClear={()=>{setFolder('*');setTag('*');}} onEmptyFocus={()=>filterDetails.current?.querySelector('summary')?.focus()}/>
  {status&&!ready&&<p className="library-management-error" role="alert">{status.error??'分类暂不能读取；原音仍可打开或备份。'}</p>}
  <div className="library-management-heading"><div><strong>{title}</strong><span>{searching?'查找中':`${filtered.length} 条${folder!=='*'||tag!=='*'?' · 已筛选':''}`}</span></div><button className="text-button" type="button" disabled={disabled} onClick={()=>managing?finish():setManaging(true)}>{managing?'完成':'选择'}</button></div>
  {managing&&<div className="library-selection-bar"><strong><CheckSquare size={16}/>已选 {selected.length} 条</strong><div><button type="button" className="text-button" disabled={disabled||!filtered.length} onClick={selectAll}>全选当前结果</button><button type="button" className="text-button" disabled={disabled||!selected.length} onClick={clearSelection}>取消选择</button></div></div>}
  {managing&&hiddenSelected>0&&<p className="library-selection-scope" role="status">已选录音中有 {hiddenSelected} 条不在当前范围，整理时仍包含这些录音。</p>}
  {managing&&!!selected.length&&<details className="library-management-panel">
   <summary><Folder size={16} aria-hidden="true"/><span>整理已选 {selected.length} 条录音</span>{(destination.trim()||labels.trim())&&<small>有未应用修改</small>}</summary>
   <div className="library-management-body"><p className="hint">分类和标签保存在当前资料库，会随完整备份保留。</p>
   <label className="library-management-field">移至文件夹<input aria-label="目标文件夹" maxLength={160} list="library-folder-options" value={destination} disabled={disabled||!ready} placeholder="例如：客户 / 产品会议；留空为未分类" onChange={e=>setDestination(e.target.value)}/></label><datalist id="library-folder-options">{folders.map(f=><option key={f} value={f}/>)}</datalist>
   <button type="button" className="secondary" disabled={disabled||!ready} onClick={()=>void change('move')}>应用文件夹</button>
   <label className="library-management-field">标签<input aria-label="批量标签" maxLength={840} value={labels} disabled={disabled||!ready} placeholder="用逗号分隔，例如：项目A，待跟进" onChange={e=>setLabels(e.target.value)}/></label>
   <div className="library-management-buttons"><button type="button" className="secondary" disabled={disabled||!ready||!labels.trim()} onClick={()=>void change('addTags')}>添加标签</button><button type="button" className="text-button" disabled={disabled||!ready||!labels.trim()} onClick={()=>void change('removeTags')}>移除标签</button></div>
   <details className="library-management-safety-more"><summary>保护与删除</summary><div className="library-management-safety"><button type="button" className="text-button" disabled={disabled} onClick={()=>void batch('protect')}><Shield size={15}/>保护录音</button><button type="button" className="text-button" disabled={disabled} onClick={()=>void batch('unprotect')}>解除保护</button><button type="button" className="library-trash-button" disabled={disabled} onClick={()=>void batch('trash')}><Trash2 size={15}/>移入回收站</button></div></details>
   {!!missing.length&&<p role="status">有 {missing.length} 条选择已不在当前列表，请核对回收站。<button type="button" className="text-button" onClick={()=>setSelected(old=>old.filter(id=>!missing.includes(id)))}>清除失效选择</button></p>}
  </div></details>}
  {message&&<p className="library-management-result" role="status"><Check size={16}/>{message}</p>}{error&&<p className="library-management-error" role="alert">{error}</p>}
  {filtered.length?<div className="list library-managed-list">{filtered.map(row=><div className={selected.includes(row.key)?'library-managed-row is-selected':'library-managed-row'} key={row.key} data-recording-key={row.key}>
   {managing&&<label className="library-row-check"><input type="checkbox" aria-label={`选择录音：${row.title}`} checked={selected.includes(row.key)} disabled={disabled} onChange={()=>toggle(row.key)}/></label>}
   <div className="library-managed-content">{renderRow(row,()=>managing?toggle(row.key):onOpen(row))}{!!(row.organization?.folder||row.organization?.tags.length)&&<div className="library-row-labels">{row.organization.folder&&<span title={row.organization.folder}><Folder size={12}/>{row.organization.folder}</span>}{row.organization.tags.map(t=><span key={t} title={t}>#{t}</span>)}</div>}</div>
  </div>)}</div>:!searching?<div className="library-filter-empty"><Folder size={22}/><p>当前范围没有录音。</p>{folder!=='*'||tag!=='*'?<button type="button" className="text-button" onClick={()=>{setFolder('*');setTag('*');}}>清除分类筛选</button>:null}</div>:null}
 </section>;
}
