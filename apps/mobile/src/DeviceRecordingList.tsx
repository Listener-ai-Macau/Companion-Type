export type DeviceSession={index:number;identity?:string;session:string;segment:number;segments:number;bytes:number;startedAtUnixSeconds:number|null;durationMs:number;complete:boolean};
export function DeviceRecordingList({rows,busy,refresh,sync,remove}:{rows:DeviceSession[];busy:boolean;refresh:()=>void;sync:(row:DeviceSession)=>void;remove:(row:DeviceSession)=>void}) {
 return <section aria-label="设备上的录音"><h2>设备上的录音</h2>
  <p className="intro">按场接收或删除。删除设备副本会释放空间，本机已保存的录音保留。</p>
  <button className="secondary" disabled={busy} onClick={refresh}>刷新设备录音</button>
  {!rows.length?<p>设备上没有待接收的录音。</p>:<div className="list">{rows.map(row=><article className="row" key={row.identity??row.session} data-device-session={row.session}>
   <div className="row-body"><strong>{row.startedAtUnixSeconds?new Date(row.startedAtUnixSeconds*1000).toLocaleString():'录音日期未知'}</strong>
    <small>约{Math.ceil(row.durationMs/1000)}秒 · {(row.bytes/1024).toFixed(1)} KiB · {row.complete?'完整录音':'部分片段，尚未收齐'}</small>
    <div className="buttons"><button disabled={busy} onClick={()=>sync(row)}>接收这场</button><button className="secondary" disabled={busy} onClick={()=>remove(row)}>删除设备副本</button></div>
   </div>
  </article>)}</div>}
 </section>;
}
