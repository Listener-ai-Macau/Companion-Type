import {useEffect,useRef,useState} from 'react';
import {BookOpen,Check,FileText,MessageSquare,Plus} from 'lucide-react';
import './minutesTemplates.css';
export type MinutesTemplate={id:'meeting'|'interview'|'lecture'|'custom';name?:string;instructions?:string};
export type TemplateLibrary={version:1;libraryToken:string;etag:string;items:Array<MinutesTemplate&{key:string}>;selected:MinutesTemplate};
export type TemplateSelection={template:MinutesTemplate;libraryToken:string};
export const templateName=(t?:MinutesTemplate)=>t?.id==='custom'?t.name||'自定义':({meeting:'会议',interview:'访谈',lecture:'课堂'} as Record<string,string>)[t?.id||'meeting']||'会议';
const same=(a?:MinutesTemplate,b?:MinutesTemplate)=>a?.id===b?.id&&(a?.name||'')===(b?.name||'')&&(a?.instructions||'')===(b?.instructions||'');
const presets=[{id:'meeting' as const,name:'会议',note:'议题、决定与下一步',icon:FileText},{id:'interview' as const,name:'访谈',note:'问题、回答与原话',icon:MessageSquare},{id:'lecture' as const,name:'课堂',note:'知识点、讲解与例子',icon:BookOpen}];
export function MinutesTemplates({busy,savedTemplate,initialSelection,onLoad,onChange,onSelect,onPending}:{busy:boolean;savedTemplate?:MinutesTemplate;initialSelection?:TemplateSelection|null;onLoad:()=>Promise<TemplateLibrary>;onChange:(args:object)=>Promise<TemplateLibrary|undefined>;onSelect:(selection:TemplateSelection|null)=>void;onPending:(pending:boolean)=>void}){
 const picker=useRef<HTMLDetailsElement>(null);
 const [library,setLibrary]=useState<TemplateLibrary|null>(null),[selected,setSelected]=useState<MinutesTemplate>({id:'meeting'}),[loading,setLoading]=useState(true),[working,setWorking]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [editing,setEditing]=useState(false),[name,setName]=useState(''),[instructions,setInstructions]=useState('');
 const validate=(v:TemplateLibrary)=>{if(v.version!==1||!v.libraryToken||!v.etag||!Array.isArray(v.items)||!v.selected?.id)throw new Error('模板资料未能确认，请重新读取。');return v;};
 const adopt=(v:TemplateLibrary,t:MinutesTemplate=v.selected)=>{setLibrary(v);setSelected(t);onSelect({template:t,libraryToken:v.libraryToken});};
 useEffect(()=>{let active=true;onSelect(null);void onLoad().then(v=>{if(active){validate(v);adopt(v,initialSelection?.libraryToken===v.libraryToken?initialSelection.template:v.etag==='empty'&&savedTemplate?savedTemplate:v.selected);}}).catch(e=>{if(active)setError(e instanceof Error?e.message:String(e));}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[]);
 const reload=async()=>{setLoading(true);setError('');setNotice('');onSelect(null);try{adopt(validate(await onLoad()));setEditing(false);onPending(false);}catch(e){setError(e instanceof Error?e.message:String(e));}finally{setLoading(false);}};
 const change=async(action:string,template?:MinutesTemplate,key?:string)=>{
  if(!library||busy||working||loading)return;setWorking(true);setError('');setNotice('');
  try{const result=await onChange({action,template,key,etag:library.etag,libraryToken:library.libraryToken});if(!result)throw new Error('模板尚未保存，请重试；原有模板仍保留。');adopt(validate(result));setEditing(false);onPending(false);if(action!=='delete'&&picker.current)picker.current.open=false;setNotice(action==='save'?'模板已保存在这份资料中，下次可直接使用。':action==='delete'?'已移除这份模板，已有纪要及历史不受影响。':'已选择，下次打开可继续使用。');}
  catch(e){setError(e instanceof Error?e.message:String(e));}finally{setWorking(false);}
 };
 const edit=(t?:MinutesTemplate)=>{setName(t?.name||'');setInstructions(t?.instructions||'');setEditing(true);onPending(true);setNotice('');};
 const disabled=busy||working||loading||!library;
 const bytes=(s:string)=>new TextEncoder().encode(s.trim()).length;
 const valid=!!name.trim()&&!!instructions.trim()&&bytes(name)<=256&&bytes(instructions)<=8192;
 return <section className="minutes-templates" aria-label="纪要模板"><span className="template-compact-label">整理方式</span><details className="template-picker" ref={picker}><summary><strong>{templateName(selected)}</strong><span>切换模板</span></summary><div className="template-picker-body">
  <div className="template-heading"><div><span>按你的工作方式整理</span><h4>纪要模板</h4></div><span className="template-current">{templateName(selected)}</span></div>
  <p className="template-intro">同一份原文，选择更适合的整理侧重点。</p>
  {savedTemplate&&<p className="template-source">已有纪要使用「{templateName(savedTemplate)}」。重新生成会保留旧版本。</p>}
  {loading&&<p role="status">正在读取已保存的模板…</p>}
  {error&&<div className="template-error" role="alert"><p>{error}</p><button type="button" disabled={busy||working||loading} onClick={()=>void reload()}>重新读取模板</button></div>}
  <div className="template-presets">{presets.map(p=><button key={p.id} type="button" aria-pressed={selected.id===p.id&&!editing} disabled={disabled||editing} onClick={()=>void change('select',{id:p.id})}><p.icon size={19}/><strong>{p.name}</strong><small>{p.note}</small>{selected.id===p.id&&!editing&&<Check className="template-check" size={14}/>}</button>)}</div>
  {!!library?.items.length&&<details className="template-saved" open={selected.id==='custom'}><summary>我的模板 · {library.items.length}</summary>{library.items.map((t,index)=><div className="template-saved-row" key={t.key}><button type="button" className="template-use" disabled={disabled||editing} aria-pressed={same(selected,t)&&!editing} onClick={()=>void change('select',t)}><strong>{t.name}</strong><small>{t.instructions}</small>{library.items.filter(x=>x.name===t.name).length>1&&<em>同名版本 {library.items.slice(0,index+1).filter(x=>x.name===t.name).length}</em>}</button><div><button type="button" disabled={disabled||editing} onClick={()=>edit(t)}>编辑副本</button><button type="button" disabled={disabled||editing} onClick={()=>{if(window.confirm(`移除模板「${t.name}」？已有纪要和历史版本仍保留。`))void change('delete',undefined,t.key);}}>移除</button></div></div>)}</details>}
  {selected.id==='custom'&&!library?.items.some(t=>same(t,selected))&&!editing&&<button type="button" className="text-button" disabled={disabled} onClick={()=>edit(selected)}>把本次纪要的模板存入我的模板</button>}
  {editing?<div className="template-editor"><h5>保存自己的整理方式</h5><label>模板名称<input aria-label="模板名称" value={name} onChange={e=>setName(e.target.value)} placeholder="例如：项目复盘" disabled={busy||working}/></label><label>整理要求<textarea aria-label="整理要求" rows={5} value={instructions} onChange={e=>setInstructions(e.target.value)} placeholder="例如：按进展、风险、已定事项和下一步整理。保留原话中的负责人和时间；没有明确的内容请标为待确认。" disabled={busy||working}/></label><p className={bytes(name)>256||bytes(instructions)>8192?'template-limit template-invalid':'template-limit'}>{bytes(name)>256||bytes(instructions)>8192?'内容较长，请缩短名称或整理要求。':'名称保持简短，整理要求可分段填写。'}</p><p className="template-help">这里只填写整理方式，生成结果仍需结合原文核对。编辑副本会保留原模板。</p><div className="template-editor-actions"><button type="button" className="secondary" disabled={busy||working} onClick={()=>{setEditing(false);onPending(false);setError('');}}>取消编辑</button><button type="button" className="primary" disabled={busy||working||!valid} onClick={()=>void change('save',{id:'custom',name:name.trim(),instructions:instructions.trim()})}>保存并选用</button></div></div>:<button type="button" className="template-create" disabled={disabled} onClick={()=>edit()}><Plus size={16}/>新建自定义模板</button>}
  {notice&&<p className="template-notice" role="status">{notice}</p>}
  <p className="template-help">模板保存在当前资料中，随整份资料备份。选择、保存模板不会调用 AI；生成纪要时才发送文字和整理要求。</p>
 </div></details></section>;
}
