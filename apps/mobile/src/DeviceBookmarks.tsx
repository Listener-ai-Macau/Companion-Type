import {useEffect,useRef,useState} from 'react';
import {Bookmark,Play,Download,RefreshCw} from 'lucide-react';
export type DeviceMark={sequence:string;sourceSamples:number;elapsedMs:number};
export type DeviceMarkList={key:string;libraryToken:string;binding:string;complete:boolean;marks:DeviceMark[]};
function clock(ms:number){const seconds=Math.floor(ms/1000);return `${seconds>=3600?`${Math.floor(seconds/3600)}:`:''}${String(Math.floor(seconds/60)%60).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;}
export function DeviceBookmarks({recordingKey,busy,onLoad,onPlay,onExport}:{recordingKey:string;busy:boolean;onLoad:()=>Promise<DeviceMarkList>;onPlay:(list:DeviceMarkList,mark:DeviceMark)=>void;onExport:()=>void}){
 const [value,setValue]=useState<DeviceMarkList|null>(null),[loading,setLoading]=useState(false),[error,setError]=useState('');const alive=useRef(true);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const load=async()=>{if(loading||busy)return;setLoading(true);setError('');try{const v=await onLoad();const seen=new Set<string>();
  if(v.key!==recordingKey||!v.libraryToken||!v.binding||typeof v.complete!=='boolean'||!Array.isArray(v.marks)||v.marks.some(mark=>{const id=JSON.stringify([mark.sequence,mark.sourceSamples,mark.elapsedMs]);if(typeof mark.sequence!=='string'||!/^\d+$/.test(mark.sequence)||!Number.isSafeInteger(mark.sourceSamples)||mark.sourceSamples<0||!Number.isSafeInteger(mark.elapsedMs)||mark.elapsedMs<0||seen.has(id))return true;seen.add(id);return false;}))throw new Error('当前重点资料未能确认，请重新读取。');
  if(alive.current)setValue(v);
 }catch(e){if(alive.current)setError(e instanceof Error?e.message:String(e));}finally{if(alive.current)setLoading(false);}};
 const card=(mark:DeviceMark,index:number)=><button type="button" className="device-mark" key={JSON.stringify([mark.sequence,mark.sourceSamples,mark.elapsedMs])} disabled={busy||loading||!!error} aria-label={`回听设备重点 ${index+1}，录音经过 ${clock(mark.elapsedMs)}`} onClick={()=>value&&onPlay(value,mark)}><span className="device-mark-icon"><Play size={14}/></span><span><strong>设备重点 {index+1}</strong><small>录音经过 {clock(mark.elapsedMs)}</small></span><span className="device-mark-play">回听</span></button>;
 return <section className="device-bookmarks" aria-label="录音卡重点"><div className="device-bookmarks-heading"><div><Bookmark size={16}/><h2>录音重点</h2>{value&&<small>{value.marks.length} 处</small>}</div><button type="button" disabled={busy||loading} onClick={()=>void load()}>{loading?'正在读取…':value?<><RefreshCw size={13}/>重新读取</>:'读取设备重点'}</button></div>
  {!value&&!error&&<p>录音时在卡上按键标记的时刻，可在这里找到并回听。无需转写或 AI。</p>}
  {error&&<p className="device-bookmarks-error" role="alert">{error}{value?' 当前保留上次读取的结果。':''}</p>}
  {value&&!value.complete&&<p className="device-bookmarks-partial" role="status">仅显示已接收分段中的重点，完整录音可能还有其他重点。</p>}
  {value&&value.marks.length===0&&<p>{value.complete?'已读取这条录音，未发现设备按键标记的重点。':'当前已接收分段中未发现设备重点。'}</p>}
  {value&&value.marks.length>0&&<><div className="device-mark-list">{value.marks.slice(0,5).map(card)}</div>{value.marks.length>5&&<details className="device-mark-more"><summary>查看其余 {value.marks.length-5} 处重点</summary>{value.marks.slice(5).map((mark,index)=>card(mark,index+5))}</details>}<p className="device-bookmarks-note">这些是设备按键标记，不是 AI 结论。回听位置会按已保存音频匹配；暂停或缺失分段可能使回听时间不同。</p><button type="button" className="device-mark-export" disabled={busy||loading||!!error} onClick={onExport}><Download size={14}/>导出重点清单</button></>}
 </section>;
}
