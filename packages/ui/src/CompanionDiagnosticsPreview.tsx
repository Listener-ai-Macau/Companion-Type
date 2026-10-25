import {useEffect,useRef,useState} from 'react';
import {operationErrorText} from './operationFailure';

const operations:Record<string,string>={deviceControl:'设备操作',reconnect:'重新连接',recordingSync:'收取录音',boardRecording:'设备采集',hostRecordingStart:'本机采集开始',hostRecordingStop:'本机采集结束',transcription:'转文字',minutes:'整理重点',audioDecode:'准备原音',speakerEmbedding:'区分说话人',otaValidate:'检查升级包',otaTransfer:'传送升级包',deviceLogPull:'读取设备日志',recordingSaved:'原音已在本机保存',recordingFragmentSaved:'已保存原音片段',recordingRestored:'恢复本机原音'};
const results:Record<string,string>={started:'开始',succeeded:'完成该步',cancelled:'已取消',failed:'未完成',timeout:'等待超时'};
type Event={operation:string;result:string;time:number;operationId:string|null;recordingTrace:string|null;processInstance:string|null;traceUnavailable:boolean};
type Preview={count:number;unreadable:number;unlinked:number;unknownBuild:number;conflicts:number;writeFailed:boolean;exe:string|null;library:string|null;process:string|null;firmware:number|null;ui:number|null;events:Event[]};
const object=(value:unknown):Record<string,unknown>=>value&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:{};
const count=(value:unknown,max=100000)=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=0&&value<=max?value:0;
const hex=(value:unknown,size:number)=>typeof value==='string'&&new RegExp(`^[0-9a-f]{${size}}$`,'i').test(value)?value.toLowerCase():null;
/** Copy only displayable metadata. Never render an arbitrary backend object. */
export function safeDiagnosticsPreview(value:unknown):Preview {
  const v=object(value);if(v.schema!=='companion.diagnostics.preview.v1'||!Array.isArray(v.recentEvents)||v.recentEvents.length>24)throw Error('Invalid diagnostics preview');
  return {count:count(v.hostEventCount),unreadable:count(v.unreadableLines),unlinked:count(v.unlinkedEvents),unknownBuild:count(v.unknownBuildEvents),conflicts:count(v.buildConflicts),writeFailed:v.writeFailed===true,
    exe:hex(v.executableSha256,64),library:hex(v.librarySha256,64),process:hex(v.currentProcessInstance,16),
    firmware:count(v.cachedFirmwareVersion,0xffffffff)||null,ui:count(v.cachedUiGeneration,0xffffffff)||null,
    events:v.recentEvents.map(raw=>{const e=object(raw);return {operation:typeof e.operation==='string'&&Object.hasOwn(operations,e.operation)?operations[e.operation]:'其它阶段',result:typeof e.result==='string'&&Object.hasOwn(results,e.result)?results[e.result]:'未知结果',time:count(e.unixMs,8640000000000000),operationId:hex(e.operationId,16),recordingTrace:hex(e.recordingTrace,16),processInstance:hex(e.processInstance,16),traceUnavailable:e.traceUnavailable===true};})};
}
export function CompanionDiagnosticsPreview({blocked,onPreview}:{blocked:boolean;onPreview?:()=>Promise<unknown>}){
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[value,setValue]=useState<Preview|null>(null),[error,setError]=useState<string|null>(null);
  const epoch=useRef(0),active=useRef(false);
  useEffect(()=>()=>{epoch.current++;},[]);
  if(!onPreview)return null;
  const close=()=>{epoch.current++;active.current=false;setBusy(false);setOpen(false);setError(null);setValue(null);};
  const load=async()=>{
    if(blocked||active.current)return;active.current=true;const token=++epoch.current;setOpen(true);setBusy(true);setValue(null);setError(null);
    try{const raw=await onPreview();if(token===epoch.current)setValue(safeDiagnosticsPreview(raw));}
    catch(e){if(token===epoch.current)setError(operationErrorText(e,'diagnosticsRead'));}
    finally{if(token===epoch.current){active.current=false;setBusy(false);}}
  };
  return <section className="ct-diagnostics-preview" aria-label="本机日志预览">
    <button type="button" className="ct-action" disabled={blocked&&!open} aria-expanded={open} onClick={()=>open?close():void load()}>{open?'收起日志预览':'先查看本机日志'}</button>
    {open?<div>
      <p className="ct-step-meta">只看本机已有的阶段记录，不连接设备、不开始录音，也不会上传。导出时会重新读取；设备日志不在本次预览内。</p>
      {busy?<p role="status">正在读取本机日志…</p>:null}
      {error?<p role="alert">{error} <button type="button" className="ct-text-button" disabled={blocked||busy} onClick={()=>void load()}>重新查看</button></p>:null}
      {value?<>
        <p role="status">{value.count?`本机保留 ${value.count} 条阶段记录。`:'目前没有可用的本机阶段记录。'}{value.unreadable?` ${value.unreadable} 行无法读取。`:''}{value.writeFailed?' 日志曾写入失败，记录可能不完整。':''}{value.conflicts?' 部分程序身份记录冲突，未据此判断版本。':''}</p>
        <p className="ct-step-meta">{value.unlinked?`${value.unlinked} 条没有录音关联；`:'当前记录含录音关联时，可用于对照同一条录音。'}{value.unknownBuild?`${value.unknownBuild} 条缺少可核对的程序身份。`:''}步骤完成不代表整条录音已验收。</p>
        <details><summary>程序与关联标识</summary>
          <dl style={{overflowWrap:'anywhere'}}><dt>当前程序 SHA-256</dt><dd><code>{value.exe??'尚未取得'}</code></dd><dt>程序库 SHA-256</dt><dd><code>{value.library??'尚未取得'}</code></dd><dt>本次运行标识</dt><dd><code>{value.process??'未知'}</code></dd><dt>设备版本（上次读取）</dt><dd>{value.firmware?`0x${value.firmware.toString(16).padStart(8,'0')}`:'未读取'} · UI {value.ui??'未读取'}</dd></dl>
          <p className="ct-step-meta">程序指纹来自磁盘文件。录音关联使用本机随机盐，不包含原录音 ID；旧记录、其它运行或缺失标识不会按当前版本补猜。</p>
        </details>
        {value.events.length?<div tabIndex={0} aria-label="最近阶段记录" style={{maxHeight:300,overflow:'auto',overflowWrap:'anywhere'}}><ol>{value.events.map((event,index)=><li key={index}>
          <strong>{event.operation} · {event.result}</strong><span> · {event.time?new Date(event.time).toLocaleString():'电脑时间未知'}</span>
          <details><summary>关联信息</summary><p>操作 <code>{event.operationId??'未知'}</code> · 录音 <code>{event.recordingTrace??(event.traceUnavailable?'暂不可关联':'未绑定')}</code> · 运行 <code>{event.processInstance??'旧记录未提供'}</code></p></details>
        </li>)}</ol></div>:null}
        <p className="ct-step-meta">需要协助时可先导出到本机，再决定是否分享；这里不会自动发送给任何人。</p>
      </>:null}
    </div>:null}
  </section>;
}
