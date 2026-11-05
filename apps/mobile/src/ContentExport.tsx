import {useEffect,useRef,useState,type RefObject} from 'react';
import {Check,ChevronDown,Copy,Download,FileAudio,GitBranch,RefreshCw,Share2} from 'lucide-react';
import './contentExport.css';
type Content='minutes'|'transcript'|'translation'|'notes';
export type ExportInfo={key:string;title:string;libraryToken:string;binding:string;available:Record<Content,boolean>;minutesStale:boolean;minutesDraft:boolean;minutesManual:boolean;translationStale:boolean;translationLanguage:string;problems:string[]};
export type PreparedExport={id:string;filename:string;mime:string;bytes:number;copyAllowed:boolean;preview:string;warnings:string[]};
type Call=<T>(method:string,args?:object)=>Promise<T>;
type Run=<T>(label:string,work:()=>Promise<T>)=>Promise<T|undefined>;
const labels:Record<Content,string>={minutes:'会议纪要',transcript:'会议转写',translation:'已保存译文',notes:'补充与事项'};
const captions:Record<Content,string>={minutes:'讨论结论、行动事项与原文依据',transcript:'当前保存的完整转写文字',translation:'按保存的目标语言输出',notes:'独立保存的个人补充与事项'};
export function ContentExport({recordingKey,busy,readingPreview,panelRef,initialContent,onCall,onRun,onSave,onAudioSave,onMindmap}:{recordingKey:string;busy:boolean;readingPreview:boolean;panelRef:RefObject<HTMLDetailsElement>;initialContent:Content;onCall:Call;onRun:Run;onSave:(id:string)=>Promise<boolean>;onAudioSave:()=>Promise<unknown>;onMindmap:()=>Promise<unknown>}){
 const [info,setInfo]=useState<ExportInfo|null>(null),[selected,setSelected]=useState<Content[]>([]),[format,setFormat]=useState('pdf'),[loading,setLoading]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[prepared,setPrepared]=useState<PreparedExport|null>(null);
 const alive=useRef(true),epoch=useRef(0),working=useRef(false),initial=useRef(initialContent);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;epoch.current++;};},[]);
 useEffect(()=>{if(initial.current!==initialContent){initial.current=initialContent;epoch.current++;setLoading(false);setInfo(null);setSelected([]);setPrepared(null);setNotice('');setError('');}},[initialContent]);
 const load=async()=>{if(busy||working.current||readingPreview)return;const generation=++epoch.current;setLoading(true);setError('');setNotice('');setPrepared(null);try{
  const v=await onCall<ExportInfo>('exportInfo',{key:recordingKey});if(v.key!==recordingKey||!v.binding||!v.libraryToken||!v.available||!Array.isArray(v.problems))throw new Error('当前内容尚未确认，请重新读取。');if(!alive.current||generation!==epoch.current)return;
  setInfo(v);setSelected(old=>{const retained=old.filter(x=>v.available[x]);if(retained.length)return retained;const preferred=v.available[initialContent]?initialContent:v.available.minutes?'minutes':v.available.transcript?'transcript':v.available.translation?'translation':v.available.notes?'notes':null;return preferred?[preferred]:[];});
 }catch(e){if(alive.current&&generation===epoch.current){setInfo(null);setError(e instanceof Error?e.message:String(e));}}finally{if(alive.current&&generation===epoch.current)setLoading(false);}};
 const toggle=(id:Content)=>{setSelected(old=>{const next=old.includes(id)?old.filter(x=>x!==id):[...old,id];if(format==='srt'&&(next.length!==1||next[0]!=='transcript')){setFormat('txt');setNotice('多项内容使用文档或文字格式，已切换为TXT。');}else setNotice('');return next;});setPrepared(null);};
 const valid=(v:PreparedExport)=>{if(!v.id||!v.filename||!v.mime||!Number.isSafeInteger(v.bytes)||v.bytes<=0||!Array.isArray(v.warnings))throw new Error('文件准备结果尚未确认，请重新操作。');return v;};
 const action=async(kind:'save'|'copy'|'share')=>{if(!info||!selected.length||busy||loading||working.current)return;working.current=true;setError('');setNotice('');setPrepared(null);
  try{await onRun(kind==='copy'?'正在准备所选文字':'正在准备所选内容',async()=>{try{
   const file=valid(await onCall<PreparedExport>('prepareExport',{key:recordingKey,libraryToken:info.libraryToken,binding:info.binding,sections:selected,format:kind==='copy'?'txt':format}));setPrepared(file);
   if(kind==='copy'){if(!file.copyAllowed)throw new Error('所选文字较长，请保存或分享文件。');if(await onCall<boolean>('copyExport',{id:file.id})!==true)throw new Error('尚未确认复制成功。');setNotice('所选文字已复制，包含必要的来源与核对提示。');}
   else if(kind==='save'){const saved=await onSave(file.id);setNotice(saved?'文件已保存到你选择的位置。':'已取消保存，原资料仍保留。');}
   else{const result=await onCall<{opened:boolean}>('shareExport',{id:file.id});if(!result.opened)throw new Error('分享面板尚未打开。');setNotice('已打开系统分享面板，请继续选择应用；这不代表已经发送。');}
  }catch(e){setError(e instanceof Error?e.message:String(e));throw e;}});}finally{working.current=false;}
 };
 const shareAudio=async()=>{if(!info||busy||loading||working.current)return;working.current=true;setError('');setNotice('');try{await onRun('正在准备录音分享副本',async()=>{try{const file=valid(await onCall<PreparedExport>('prepareAudioShare',{key:recordingKey,libraryToken:info.libraryToken,binding:info.binding}));setPrepared(file);const result=await onCall<{opened:boolean}>('shareExport',{id:file.id});if(!result.opened)throw new Error('分享面板尚未打开。');setNotice('已打开系统分享面板，请继续选择应用；这不代表已经发送。');}catch(e){setError(e instanceof Error?e.message:String(e));throw e;}});}finally{working.current=false;}};
 const disabled=busy||loading||!info||!selected.length||readingPreview;
 return <details ref={panelRef} className="export-card content-export" onToggle={e=>{if(e.currentTarget.open)void load();}}><summary className="disclosure-title"><span>导出、复制与分享</span><ChevronDown size={15} aria-hidden="true"/></summary>
  <div className="export-intro"><span>把会议材料，交到需要的人手里</span><p>先选内容，再保存文件、复制文字或交给其他应用。</p></div>
  {readingPreview?<p className="export-state">本轮阅读预览未提供系统文件保存与分享。</p>:<>
  {loading&&<p className="export-state" role="status">正在核对已保存内容…</p>}{error&&<p className="export-error" role="alert">{error}</p>}
  <div className="export-selection-heading"><h3>选择内容</h3><button type="button" disabled={busy||loading} onClick={()=>void load()}><RefreshCw size={13}/>重新读取</button></div>
  {info&&<><div className="export-sections" role="group" aria-label="选择导出内容">{(['minutes','transcript','translation','notes'] as Content[]).map(id=><label key={id} className={selected.includes(id)?'selected':undefined}><input type="checkbox" checked={selected.includes(id)} disabled={busy||loading||!info.available[id]} onChange={()=>toggle(id)}/><span><strong>{labels[id]}{id==='translation'&&info.translationLanguage?` · ${info.translationLanguage}`:''}</strong><small>{info.available[id]?captions[id]:'暂无可用的已保存内容'}</small></span>{selected.includes(id)&&<Check size={14} aria-hidden="true"/>}</label>)}</div>
  {info.problems.map((text,index)=><p className="export-warning" key={index}>{text}</p>)}
  {selected.includes('minutes')&&(info.minutesStale||info.minutesDraft||info.minutesManual)&&<p className="export-warning" role="status">{info.minutesStale?'纪要来源已变化，请先核对。 ':''}{info.minutesDraft?'包含未完成草稿。 ':''}{info.minutesManual?'包含人工核对或安排。 ':''}这些提示会保留在文件和复制的文字中。</p>}
  {selected.includes('translation')&&info.translationStale&&<p className="export-warning" role="status">译文依据较早的原文版本，文件和复制文字会保留来源提示。</p>}
  {selected.includes('translation')&&selected.includes('transcript')&&<p className="export-help">原文与译文将分节排列，不做逐句对齐。</p>}
  <label className="export-format">文件格式<select aria-label="导出文件格式" value={format} disabled={busy||loading} onChange={e=>{setFormat(e.target.value);setPrepared(null);setNotice('');}}><option value="pdf">PDF · 便于阅读</option><option value="word">Word · 可编辑文档</option><option value="txt">TXT · 纯文字</option><option value="markdown">Markdown · 保留结构</option><option value="srt" disabled={selected.length!==1||selected[0]!=='transcript'}>SRT · 转写字幕</option></select></label>
  {format==='srt'&&<p className="export-warning">仅导出当前原文已有的分段时间，属于近似时间，不是逐字对齐。没有可核验时间时会提示选择其它格式。</p>}
  <div className="export-main-actions"><button type="button" className="primary" disabled={disabled} onClick={()=>void action('save')}><Download size={16}/>保存文件</button><button type="button" className="secondary" disabled={disabled} onClick={()=>void action('share')}><Share2 size={16}/>分享文件</button></div><button type="button" className="export-copy" disabled={disabled} onClick={()=>void action('copy')}><Copy size={15}/>复制所选文字</button>
  <p className="export-help">复制不带文件标题，保留所选正文和必要提示。分享使用临时副本；需要长期留存时，请保存文件。</p>
  {prepared&&<div className="export-prepared"><strong>{prepared.filename}</strong><small>{prepared.bytes<1024?`${prepared.bytes} B`:`${Math.ceil(prepared.bytes/1024)} KB`} · 已准备副本</small>{prepared.warnings.map((w,i)=><p key={i}>{w}</p>)}</div>}
  </>}
  {notice&&<p className="export-notice" role="status">{notice}</p>}
  <details className="export-extra"><summary>录音与思维导图</summary><div><button type="button" disabled={busy||loading} onClick={()=>void onAudioSave()}><FileAudio size={16}/>保存录音音频</button><button type="button" disabled={busy||loading||!info} onClick={()=>void shareAudio()}><Share2 size={16}/>分享录音音频</button>{info?.available.minutes&&<button type="button" disabled={busy||loading} onClick={()=>void onMindmap()}><GitBranch size={16}/>保存思维导图 .mm</button>}</div><p className="export-help">音频为WAV，多个分段会打包为ZIP；保留原音。设备重点清单仍可在重点区域单独保存。</p></details>
  </>}
 </details>;
}
