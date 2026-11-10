import {useEffect,useRef,useState} from 'react';
import {ArrowDown,ArrowUp,ChevronDown,Plus,Scissors,Trash2} from 'lucide-react';
import {createDerivationPlan,rangeFromMilliseconds,type DerivationPlan,type SourceIdentity} from '../../audio-derivation/src/plan';
import './audioDerivation.css';

export type AudioEditRow={key:string;title:string;state:string};
export type AudioEditStatus={id?:string;operation?:string;running:boolean;state:string;message?:string;processed?:number;total?:number;completed?:number;totalOutputs?:number;retryAvailable?:boolean;outputs?:{key:string;name:string;saved:boolean}[]};
export type AudioEditRequest={libraryToken:string;outputs:{name:string;plan:DerivationPlan}[]};
export type AudioEditAdapter={
 sources:(keys:string[])=>Promise<{libraryToken:string;sources:SourceIdentity[]}>;
 start:(request:AudioEditRequest)=>Promise<unknown>;status:()=>Promise<AudioEditStatus>;
 retry:(id:string)=>Promise<unknown>;cancel:()=>void;
 provenance:()=>Promise<{available:boolean;provenance:{sources:SourceIdentity[];plan:DerivationPlan}|null}>;
 playSource:(index:number)=>Promise<void>;
};
type Clip={id:number;key:string;start:string;end:string};
export type AudioEditHostProps={contextId:string;title:string;rows:AudioEditRow[];busy?:boolean;onChanged:()=>void;onLibrary:()=>void;onDirty?:(dirty:boolean)=>void;onSource:(id:string,positionMs:number)=>Promise<void>};
type Props={contextId:string;libraryToken:string;title:string;rows:AudioEditRow[];adapter:AudioEditAdapter;busy?:boolean;onChanged:()=>void;onLibrary:()=>void;onDirty?:(dirty:boolean)=>void};
function time(ms:number){const value=Math.max(0,Math.ceil(ms)),s=Math.floor(value/1000),fraction=value%1000;return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}${fraction?'.'+String(fraction).padStart(3,'0'):''}`;}
function milliseconds(text:string){const value=text.trim();if(!/^\d+(?::[0-5]\d){0,2}(?:\.\d{1,3})?$/.test(value))throw Error('时间请填写为 分:秒，可精确到三位小数，例如 1:20.500。');const parts=value.split(':').map(Number);let seconds=0;for(const part of parts)seconds=seconds*60+part;const result=Math.round(seconds*1000);if(!Number.isSafeInteger(result))throw Error('所填时间超出当前处理范围。');return result;}
function message(e:unknown){return e instanceof Error?e.message:String(e);}

/** Same ordinary editor for native clients; the adapter owns source resolution,
 * cancellation and publication. No browser-generated audio or fake transcript.
 */
export function AudioDerivationEditor(p:Props){
 const [mode,setMode]=useState<'trim'|'split'|'merge'>('trim'),[name,setName]=useState(p.title+' · 片段'),[cuts,setCuts]=useState(''),[clips,setClips]=useState<Clip[]>([]),[sources,setSources]=useState<SourceIdentity[]>([]),[addKey,setAddKey]=useState(p.contextId);
 const [working,setWorking]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[status,setStatus]=useState<AudioEditStatus|null>(null),[refresh,setRefresh]=useState(0),[cancelling,setCancelling]=useState(false),[origin,setOrigin]=useState<DerivationPlan|null>(null);
 const adapter=useRef(p.adapter),changed=useRef(p.onChanged),dirty=useRef(p.onDirty),alive=useRef(true),gate=useRef(false),nextId=useRef(0),wasRunning=useRef(false),originLoaded=useRef(false);adapter.current=p.adapter;changed.current=p.onChanged;dirty.current=p.onDirty;
 const blocked=!!p.busy||working||!!status?.running;
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;dirty.current?.(false);};},[]);
 useEffect(()=>{let active=true,timer:number|undefined;async function poll(){try{const next=await adapter.current.status();if(!active)return;setStatus(next);if(next.running){wasRunning.current=true;timer=window.setTimeout(()=>void poll(),700);}else{setCancelling(false);if(wasRunning.current){wasRunning.current=false;changed.current();}}}catch(e){if(active)setError(message(e));}}void poll();return()=>{active=false;window.clearTimeout(timer);};},[refresh]);
 async function operate(work:()=>Promise<void>){if(gate.current||p.busy)return;gate.current=true;setWorking(true);setError('');setNotice('');try{await work();}catch(e){if(alive.current)setError(message(e));}finally{gate.current=false;if(alive.current)setWorking(false);}}
 async function readOrigin(){if(originLoaded.current)return;await operate(async()=>{const result=await adapter.current.provenance();if(result.available&&result.provenance){setOrigin(result.provenance.plan);}originLoaded.current=true;});}
 async function add(key:string){await operate(async()=>{const result=await adapter.current.sources([key]);if(result.libraryToken!==p.libraryToken||result.sources.length!==1||result.sources[0]?.key!==key)throw Error('录音来源已变化，请重新打开编辑。');const source=result.sources[0],previous=sources.find(s=>s.key===key);if(previous&&previous.identity!==source.identity)throw Error('原音已变化，请重新打开编辑并选择片段。');createDerivationPlan([source],[{sourceKey:source.key,sourceIdentity:source.identity,startFrame:0,endFrame:source.frames}]);if(!alive.current)return;setSources(current=>[...current.filter(x=>x.key!==key),source]);setClips(current=>[...current,{id:++nextId.current,key,start:'0:00',end:time(source.frames/16)}]);if(clips.length)dirty.current?.(true);setNotice('完整原音已核对。编辑只会创建新录音。');});}
 function slice(clip:Clip){const source=sources.find(s=>s.key===clip.key);if(!source)throw Error('原音尚未准备，请重新读取。');return rangeFromMilliseconds(source,milliseconds(clip.start),milliseconds(clip.end),clip.end.trim()===time(source.frames/16));}
 function outputs(){
  if(!name.trim())throw Error('请填写新录音名称。');const primary=clips.find(c=>c.key===p.contextId);if(mode!=='merge'&&!primary)throw Error('请先准备这条完整录音。');
  if(mode==='split'){
   const source=sources.find(s=>s.key===p.contextId)!;const points=cuts.split(/[,，;；\n]+/).map(s=>s.trim()).filter(Boolean).map(milliseconds).map(ms=>Math.floor(ms*16));
   if(!points.length||points.length>31)throw Error('请填写1至31个切分时间，以逗号分隔。');let previous=0;for(const point of points){if(point<=previous||point>=source.frames)throw Error('切分点须按先后顺序排列，并位于原音起点和终点之间。');previous=point;}
   const bounds=[0,...points,source.frames];return bounds.slice(0,-1).map((start,i)=>({name:`${name.trim()} · 第${i+1}段`,plan:createDerivationPlan([source],[{sourceKey:source.key,sourceIdentity:source.identity,startFrame:start,endFrame:bounds[i+1]}])}));
  }
  return [{name:name.trim(),plan:createDerivationPlan(sources,(mode==='merge'?clips:[primary!]).map(slice))}];
 }
 async function save(){await operate(async()=>{if(status?.running)throw Error('已有录音任务正在进行。');const planned=outputs();if(planned.some(o=>o.name.length>256))throw Error('录音名称过长，请缩短后保存。');await adapter.current.start({libraryToken:p.libraryToken,outputs:planned});dirty.current?.(false);wasRunning.current=true;setNotice('已开始在本机整理，可在通知中查看进度。');setRefresh(v=>v+1);});}
 async function retry(){if(!status?.id)return;await operate(async()=>{await adapter.current.retry(status.id!);wasRunning.current=true;setRefresh(v=>v+1);});}
 function update(id:number,field:'start'|'end',value:string){setClips(current=>current.map(c=>c.id===id?{...c,[field]:value}:c));dirty.current?.(true);}
 function move(index:number,step:number){setClips(current=>{const next=[...current],target=index+step;if(target<0||target>=next.length)return current;[next[index],next[target]]=[next[target],next[index]];return next;});dirty.current?.(true);}
 const primary=clips.find(c=>c.key===p.contextId),displayed=mode==='merge'?clips:primary?[primary]:[];
 return <details className="audio-derivation" onToggle={e=>{if(e.target===e.currentTarget&&e.currentTarget.open)void readOrigin();}}>
  <summary><span><Scissors size={17} aria-hidden="true"/>裁剪、切分与合并</span><ChevronDown size={16} aria-hidden="true"/></summary>
  <div className="audio-derivation-body">
   <p className="audio-derivation-intro">把需要的片段另存为新录音，原音、原转写和纪要保留。新录音从自己的时间轴开始，可独立转写。</p>
   {origin&&<section className="audio-derivation-origin" aria-label="这份录音的来源"><h3>原音出处</h3><p>以下区间来自各自的原录音，拼接后的时间不表示原会议连续发生。</p><ol>{origin.slices.map((s,i)=><li key={i}><div><strong>{p.rows.find(r=>r.key===s.sourceKey)?.title||'原录音暂不在当前列表'}</strong><span>{time(s.startFrame/16)} – {time(s.endFrame/16)} · 对应本片 {time(s.outputStartFrame/16)} – {time(s.outputEndFrame/16)}</span></div><button type="button" className="text-button" disabled={blocked} onClick={()=>void operate(()=>adapter.current.playSource(i))}>回听原片段</button></li>)}</ol></section>}
   <div className="audio-derivation-modes" role="group" aria-label="录音编辑方式">{([['trim','裁剪片段'],['split','按时间切分'],['merge','合并录音']] as const).map(([value,label])=><button type="button" key={value} aria-pressed={mode===value} disabled={blocked} onClick={()=>{setMode(value);if(clips.length)dirty.current?.(true);setName(p.title+(value==='merge'?' · 合并':value==='split'?' · 切分':' · 片段'));setError('');}}>{label}</button>)}</div>
   {!(mode==='merge'?clips.length:primary)?<button type="button" className="secondary" disabled={blocked} onClick={()=>void add(p.contextId)}>{working?'正在准备本机音频…':'准备这条录音'}</button>:<>
    <label className="audio-derivation-name">新录音名称<input value={name} maxLength={240} disabled={blocked} onChange={e=>{setName(e.target.value);dirty.current?.(true);}}/></label>
    {mode==='split'?<label>切分时间<input aria-label="切分时间" value={cuts} disabled={blocked} placeholder="例如 10:00, 25:30, 40:00" onChange={e=>{setCuts(e.target.value);dirty.current?.(true);}}/><small>按先后顺序填写，以逗号分隔。原音 {time((sources.find(s=>s.key===p.contextId)?.frames||0)/16)}，各段会分别保存，并完整保留最后一段。</small></label>:<ol className="audio-derivation-clips">{displayed.map((clip,index)=><li key={clip.id}><div className="audio-derivation-clip-heading"><strong>{index+1}. {p.rows.find(r=>r.key===clip.key)?.title||'所选录音'}</strong>{mode==='merge'&&<span><button type="button" className="text-button" aria-label={`将片段${index+1}上移`} disabled={blocked||index===0} onClick={()=>move(index,-1)}><ArrowUp size={16}/></button><button type="button" className="text-button" aria-label={`将片段${index+1}下移`} disabled={blocked||index===clips.length-1} onClick={()=>move(index,1)}><ArrowDown size={16}/></button><button type="button" className="text-button" aria-label={`移除片段${index+1}`} disabled={blocked||clips.length<=1} onClick={()=>{setClips(current=>current.filter(c=>c.id!==clip.id));dirty.current?.(true);}}><Trash2 size={15}/></button></span>}</div><div className="audio-derivation-range"><label>开始<input aria-label={`片段${index+1}开始时间`} value={clip.start} disabled={blocked} inputMode="decimal" onChange={e=>update(clip.id,'start',e.target.value)}/></label><span aria-hidden="true">→</span><label>结束<input aria-label={`片段${index+1}结束时间`} value={clip.end} disabled={blocked} inputMode="decimal" onChange={e=>update(clip.id,'end',e.target.value)}/></label></div></li>)}</ol>}
    {mode==='merge'&&<div className="audio-derivation-add"><label>加入其他录音<select value={addKey} disabled={blocked} onChange={e=>setAddKey(e.target.value)}>{p.rows.filter(r=>r.state==='COMPLETE').map(r=><option key={r.key} value={r.key}>{r.title}</option>)}</select></label><button type="button" className="secondary" disabled={blocked||clips.length>=512} onClick={()=>void add(addKey)}><Plus size={15}/>加入</button></div>}
    <p className="audio-derivation-footnote">只使用完整本机音频，不上传，也不调用模型。派生音频采用本机16kHz单声道回听格式；较高规格的原始文件仍保留。选择的各场录音不会被视为连续发生。</p>
    <button type="button" className="primary" disabled={blocked} onClick={()=>void save()}>{working?'正在准备…':mode==='split'?'保存切分后的各段':mode==='merge'?'另存合并录音':'另存这个片段'}</button>
   </>}
   {status?.running&&<div className="audio-derivation-job" role="status"><strong>{status.operation==='derive'?'正在整理录音':'另一个音频任务正在进行'}</strong><p>{status.message}</p>{status.totalOutputs!=null&&<span>已确认保存 {status.completed||0} / {status.totalOutputs} 份</span>}{!!status.total&&<progress aria-label="当前音频处理步骤" value={status.processed||0} max={status.total}/>}<button type="button" className="text-button" disabled={cancelling||status.state==='finishing'||status.state==='committing'&&status.operation!=='derive'} onClick={()=>{adapter.current.cancel();setCancelling(true);}}>{cancelling?'正在取消…':status.state==='finishing'?'正在完成保存…':status.state==='committing'?'本段保存后停止':'取消剩余处理'}</button></div>}
   {status?.operation==='derive'&&!status.running&&<div className="audio-derivation-result" role="status"><p>{status.message}</p>{status.outputs?.filter(o=>o.saved).map(o=><p key={o.key}>已保存：{o.name}</p>)}{status.retryAvailable&&<button type="button" className="secondary" disabled={blocked} onClick={()=>void retry()}>核对并重试未完成片段</button>}{!!status.completed&&<button type="button" className="text-button" disabled={blocked} onClick={p.onLibrary}>在录音库查看成品</button>}</div>}
   {notice&&<p role="status" className="audio-derivation-notice">{notice}</p>}{error&&<div role="alert" className="audio-derivation-error"><p>{error}</p><button type="button" className="text-button" disabled={working} onClick={()=>{setRefresh(v=>v+1);if(!originLoaded.current)void readOrigin();}}>重新读取状态</button></div>}
  </div>
 </details>;
}
