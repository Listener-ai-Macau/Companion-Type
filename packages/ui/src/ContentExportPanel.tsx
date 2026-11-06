import {useEffect,useRef,useState} from 'react';
import {Download,Copy,Share2} from 'lucide-react';
import {savedExportPreview,SavedPreviewInterrupted} from './savedExportPreview';
import {shareHandoffMessage,type ShareDestination,type ShareHandoffResult} from './shareHandoff';
import type {CompanionMeetingExportRequest} from './CompanionDashboard';
export type ContentSelection={minutes:boolean;transcript:boolean;highlights:boolean;timeline:boolean;noteIds:string[]};
type Format='pdf'|'docx'|'txt'|'markdown'|'xlsx'|'mindmap'|'srt'|'pptx'|'png';
const formats:readonly [Format,string][]=[['pdf','PDF'],['docx','Word'],['pptx','PowerPoint'],['txt','TXT'],['markdown','Markdown'],['xlsx','Excel'],['mindmap','思维导图（可编辑）'],['png','思维导图 PNG'],['srt','字幕 SRT']];
type Preview={contentHash:string;textContent?:string|null};
type Props={sessionId:string;meetingMode:'offlineStore'|'onlineLive';sourceVersion:string;minutes:boolean;transcript:boolean;highlights:boolean;timing:boolean;exactTiming:boolean;notes:{id:string;text:string}[];blocked:boolean;unsaved:{title:boolean;minutes:boolean;transcript:boolean;highlights:boolean;notes:boolean};
 onPreview?:(request:CompanionMeetingExportRequest)=>Promise<Preview>;
 onSave?:(request:CompanionMeetingExportRequest)=>Promise<{path:string;bytes:number;warning?:string|null}|null>;
 onCopy?:(request:CompanionMeetingExportRequest)=>Promise<{status:string}>;
 onShare?:(request:CompanionMeetingExportRequest,destination?:ShareDestination)=>Promise<ShareHandoffResult>;
};
export function ContentExportPanel(props:Props){
 const [selection,setSelection]=useState<ContentSelection>({minutes:props.minutes,transcript:!props.minutes&&props.transcript,highlights:false,timeline:false,noteIds:[]});
 const [format,setFormat]=useState<Format>('pdf');
 const [phase,setPhase]=useState<'preview'|'save'|'copy'|'share'|'folder'|null>(null);
 const [preview,setPreview]=useState<{key:string;text:string}|null>(null);
 const [feedback,setFeedback]=useState<{key:string;kind:'saved'|'copied'|'opened'|'cancelled'|'error';text:string;manual?:string}|null>(null);
 const task=useRef<ReturnType<typeof savedExportPreview<Preview>>|null>(null),active=useRef(false),mounted=useRef(true);
 const choice:ContentSelection={minutes:selection.minutes&&props.minutes,transcript:selection.transcript&&props.transcript,highlights:selection.highlights&&props.highlights,
   timeline:selection.timeline&&selection.transcript&&props.transcript&&props.timing,noteIds:selection.noteIds.filter(id=>props.notes.some(note=>note.id===id))};
 const key=JSON.stringify([props.sessionId,props.meetingMode,props.sourceVersion,choice,format]);
 const currentKey=useRef(key);currentKey.current=key;
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;task.current?.cancel();};},[]);
 useEffect(()=>()=>{task.current?.cancel();},[key]);
 const any=choice.minutes||choice.transcript||choice.highlights||choice.noteIds.length>0;
 const dirty=props.unsaved.title||(choice.minutes&&props.unsaved.minutes)||(choice.transcript&&props.unsaved.transcript)||(choice.highlights&&props.unsaved.highlights)||(choice.noteIds.length>0&&props.unsaved.notes);
 const request=():CompanionMeetingExportRequest=>({sessionId:props.sessionId,meetingMode:props.meetingMode,format,contentSections:choice});
 const run=async(action:'preview'|'save'|'copy'|'share'|'folder')=>{
   if(active.current||props.blocked||!props.onPreview||!any)return;
   const operationKey=key,current=()=>mounted.current&&currentKey.current===operationKey;
   if(dirty){setFeedback({key,kind:'error',text:'所选内容有未保存的修改，请先保存或取消。'});return;}
   active.current=true;setPhase('preview');setFeedback(null);
   try{
     const pending=savedExportPreview(()=>props.onPreview!(request()));task.current=pending;
     const source=await pending.result;
     if(task.current===pending)task.current=null;
     if(!current())return;
     if(!/^[a-f0-9]{64}$/.test(source.contentHash)||typeof source.textContent!=='string'||!source.textContent.trim())throw Error('没有可用的已保存内容，请重新选择。');
     setPreview({key:operationKey,text:source.textContent});
     if(action==='preview')return;
     setPhase(action);const checked={...request(),expectedContentHash:source.contentHash};
     if(action==='save'){
       if(!props.onSave)throw Error('当前环境不能保存文件，请在Windows应用中打开。');
       const result=await props.onSave(checked);if(!current())return;
       setFeedback({key:operationKey,kind:result?'saved':'cancelled',text:result?`已保存：${result.path.split(/[\\/]/).pop()}${result.warning?`。${result.warning}`:''}`:'已取消保存，原内容保持不变。'});
     }else if(action==='copy'){
       try{
         if(props.onCopy){const result=await props.onCopy(checked);if(result.status!=='copied')throw Error('复制未完成。');}
         else {if(!navigator.clipboard?.writeText)throw Error('剪贴板不可用。');await navigator.clipboard.writeText(source.textContent);}
         if(current())setFeedback({key:operationKey,kind:'copied',text:'已复制所选内容，可粘贴到常用应用。'});
       }catch(error){
         if(!current())return;
         if(props.onCopy&&!/剪贴板|复制未完成|内存/.test(String(error)))throw error;
         setFeedback({key:operationKey,kind:'error',text:'自动复制未完成。可选择下方文字后复制。',manual:source.textContent});
       }
     }else{
       if(!props.onShare)throw Error('当前环境不能打开系统分享，请先保存文件。');
       const destination=action==='folder'?'folder':'system';
       const result=await props.onShare(checked,destination);if(!current())return;
       setFeedback({key:operationKey,kind:'opened',text:shareHandoffMessage(result,destination)});
     }
   }catch(error){if(current())setFeedback({key:operationKey,kind:'error',text:error instanceof SavedPreviewInterrupted?error.message:error instanceof Error?error.message:String(error)});}
   finally{active.current=false;if(mounted.current)setPhase(null);}
 };
 const disabled=props.blocked||phase!==null;
 const setChecked=(name:'minutes'|'transcript'|'highlights'|'timeline',checked:boolean)=>setSelection(old=>({...old,[name]:checked,...(name==='transcript'&&!checked?{timeline:false}:{})}));
 const subtitles=format==='srt';
 return <details className="ct-result-tools ct-content-export">
   <summary>导出、复制与分享</summary>
   <p className="ct-step-meta">选择需要带走的已保存内容。复制、文件预览与导出使用同一份选择。</p>
   <fieldset disabled={disabled} style={{border:0,padding:0,margin:0}}>
     <div className="ct-button-row" aria-label="导出内容选择">
       <label><input type="checkbox" checked={choice.minutes} disabled={!props.minutes||subtitles} onChange={e=>setChecked('minutes',e.currentTarget.checked)}/>整理结果</label>
       <label><input type="checkbox" checked={choice.transcript} disabled={!props.transcript||subtitles} onChange={e=>setChecked('transcript',e.currentTarget.checked)}/>录音文字</label>
       <label><input type="checkbox" checked={choice.highlights} disabled={!props.highlights||subtitles} onChange={e=>setChecked('highlights',e.currentTarget.checked)}/>录音重点</label>
       <label><input type="checkbox" checked={choice.timeline} disabled={!choice.transcript||!props.timing||subtitles} onChange={e=>setChecked('timeline',e.currentTarget.checked)}/>分段时间与说话人</label>
     </div>
     {props.notes.length>0?<details className="ct-content-materials"><summary>材料与补充（已选 {choice.noteIds.length} / {props.notes.length}）</summary>
       <div style={{display:'grid',gap:8,margin:'10px 0'}}>{props.notes.map(note=>{const title=note.text.split('\n')[0].slice(0,90)||'未命名补充';return <label key={note.id} style={{display:'flex',alignItems:'flex-start',gap:8}}><input type="checkbox" checked={choice.noteIds.includes(note.id)} disabled={subtitles} aria-label={`选择材料：${title}`} onChange={e=>{const checked=e.currentTarget.checked;setSelection(old=>({...old,noteIds:checked?[...old.noteIds,note.id]:old.noteIds.filter(id=>id!==note.id)}));}}/><span>{title}</span></label>;})}</div>
     </details>:null}
     <label>文件格式 <select aria-label="所选内容文件格式" value={format} onChange={e=>{const value=e.currentTarget.value as Format;setFormat(value);if(value==='srt')setSelection({minutes:false,transcript:true,highlights:false,timeline:true,noteIds:[]});}}>
       {formats.map(([value,label])=><option key={value} value={value} disabled={value==='srt'&&!props.exactTiming}>{label}</option>)}
     </select></label>
   </fieldset>
   {subtitles?<p className="ct-step-meta">字幕只包含有真实时间轴的原文；近似分段不能作为精确字幕。</p>:format==='xlsx'?<p className="ct-step-meta">Excel按章节保留所选正文，适合筛选和后续编辑。</p>:format==='pptx'?<p className="ct-step-meta">按已保存内容分页，文字可在PowerPoint中继续编辑；材料和原文依据一起保留。</p>:format==='png'?<p className="ct-step-meta">将所选内容绘成完整导图图片。长会议建议只选需要的材料；可编辑版本请选“思维导图（可编辑）”。</p>:null}
   <div className="ct-button-row" style={{marginTop:12}}>
     <button type="button" className="ct-action" disabled={disabled||!props.onPreview||!any} onClick={()=>void run('preview')}>预览所选内容</button>
     <button type="button" className="ct-action" disabled={disabled||!props.onPreview||!any} onClick={()=>void run('copy')}><Copy size={14}/>复制所选内容</button>
     <button type="button" className="ct-action ct-action-primary" disabled={disabled||!props.onSave||!any} onClick={()=>void run('save')}><Download size={14}/>保存 {formats.find(([value])=>value===format)?.[1]}…</button>
     <button type="button" className="ct-action" disabled={disabled||!props.onShare||!any} onClick={()=>void run('share')}><Share2 size={14}/>分享所选文件…</button>
   </div>
   {props.onShare?<details className="ct-content-share-alternative"><summary>面板无法使用？其他分享方式</summary>
     <p className="ct-step-meta">在文件夹中准备相同选择的临时副本，再通过资源管理器分享。接收应用由你选择。</p>
     <button type="button" className="ct-action" disabled={disabled||!any} onClick={()=>void run('folder')}>在文件夹中分享所选文件…</button>
   </details>:null}
   {phase?<p role="status">{phase==='preview'?'正在核对所选内容…':phase==='save'?'正在保存所选文件…':phase==='copy'?'正在复制所选内容…':phase==='folder'?'正在准备文件夹分享…':'正在准备系统分享…'} {phase==='preview'?<button type="button" className="ct-text-button" onClick={()=>task.current?.cancel()}>取消等待</button>:null}</p>:null}
   {feedback?.key===key?<div aria-label="所选内容操作结果"><p role={feedback.kind==='error'?'alert':'status'} className={feedback.kind==='error'?'ct-step-warn':'ct-step-meta'}>{feedback.text}</p>
     {feedback.manual?<textarea readOnly aria-label="手动复制所选内容" value={feedback.manual} onFocus={event=>event.currentTarget.select()} style={{width:'100%',minHeight:160}}/>:null}
   </div>:null}
   {preview?.key===key?<details className="ct-content-preview"><summary>查看所选正文</summary><pre aria-label="所选内容预览" style={{whiteSpace:'pre-wrap',maxHeight:280,overflow:'auto'}}>{preview.text}</pre></details>:null}
 </details>;
}
