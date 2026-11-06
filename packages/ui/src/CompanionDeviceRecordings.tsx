import {useEffect,useState} from 'react';
export type DeviceRecordingKey={deviceUid:string;formatEpoch:string;sessionId:string};
export type DeviceRecording={key:DeviceRecordingKey;startedAtUnixSeconds:number|null;durationMs:number;bytes:number;segments:number;complete:boolean};
export type DeviceRecordingActions={
 list:()=>Promise<DeviceRecording[]>;
 sync:(key:DeviceRecordingKey)=>Promise<void>;
 delete:(key:DeviceRecordingKey)=>Promise<{status:string;message:string}>;
};
export function CompanionDeviceRecordings({deviceId,busy,actions}:{deviceId:string;busy:boolean;actions:DeviceRecordingActions}) {
 const [rows,setRows]=useState<DeviceRecording[]|null>(null),[working,setWorking]=useState(false),[message,setMessage]=useState('');
 useEffect(()=>{setRows(null);setMessage('');},[deviceId]);
 async function run(action:()=>Promise<void>){if(working||busy)return;setWorking(true);setMessage('');try{await action();}catch(e){setMessage(e instanceof Error?e.message:String(e));}finally{setWorking(false);}}
 return <section className="ct-device-recordings" aria-label="设备上的录音">
  <h3>设备上的录音</h3><p>按场接收或删除。删除设备副本会释放空间，本机已保存的录音保留。</p>
  <button type="button" disabled={busy||working} onClick={()=>void run(async()=>{setRows(await actions.list());})}>{working?'正在读取或处理…':'刷新设备录音'}</button>
  {rows?.length===0?<p>设备上没有待接收的录音。</p>:null}
  {rows?.map(row=><article key={`${row.key.deviceUid}/${row.key.formatEpoch}/${row.key.sessionId}`} data-device-session={row.key.sessionId}>
   <strong>{row.startedAtUnixSeconds?new Date(row.startedAtUnixSeconds*1000).toLocaleString():'录音日期未知'}</strong>
   <p>约{Math.ceil(row.durationMs/1000)}秒 · {(row.bytes/1024).toFixed(1)} KiB · {row.complete?'完整录音':'部分片段，尚未收齐'}</p>
   <button type="button" disabled={busy||working} onClick={()=>void run(async()=>{await actions.sync(row.key);setRows(await actions.list());setMessage('这场录音已接收，请到记录库查看。');})}>接收这场</button>
   <button type="button" disabled={busy||working} onClick={()=>void run(async()=>{const result=await actions.delete(row.key);setMessage(result.message);setRows(await actions.list());})}>删除设备副本</button>
  </article>)}
  {message?<p role="status">{message}</p>:null}
 </section>;
}
