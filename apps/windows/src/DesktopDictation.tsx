import {useEffect,useRef,useState} from 'react';
import {invoke} from '@tauri-apps/api/core';

type Status={enabled:boolean;ready:boolean;capturing:boolean;processing:boolean;stage:string;message:string;sessionId:string|null;transcript:string;localRecognition:boolean};
const idle:Status={enabled:false,ready:false,capturing:false,processing:false,stage:'off',message:'',sessionId:null,transcript:'',localRecognition:false};
export function DesktopDictation({connected,blocked}:{connected:boolean;blocked:boolean}){
 const [status,setStatus]=useState(idle),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [shortcut,setShortcut]=useState('ctrlV');const active=useRef(false),mounted=useRef(true);
 useEffect(()=>{mounted.current=true;let reading=false;const read=async()=>{if(reading||active.current)return;reading=true;try{const value=await invoke<Status>('get_companion_desktop_input');if(mounted.current)setStatus(value);}catch{}finally{reading=false;}};void read();const timer=setInterval(()=>void read(),1000);return()=>{mounted.current=false;clearInterval(timer);};},[]);
 const run=async(command:string,args?:Record<string,unknown>)=>{if(active.current)return;active.current=true;setBusy(true);setError('');try{const value=await invoke<Status>(command,args);if(mounted.current)setStatus(value);}catch(e){if(mounted.current)setError(String(e));}finally{active.current=false;if(mounted.current)setBusy(false);}};
 return <details className="ct-desktop-input" aria-label="电脑按住说话">
  <summary>电脑输入 · 按住说话，松开输入</summary>
  <p>把光标放在编辑器里，按住卡片按键说话，松开后等待文字。</p>
  <p>{status.localRecognition?'使用当前本机识别配置；原音和文字保存在这台电脑。':'使用当前识别配置；云端识别会将本次原音发送到你配置的服务，可能产生费用。可在设置中选择本机识别。'}</p>
  <p>进入此模式后，卡片按键改为按住录音、松开结束；回到录音模式后恢复单击开停。识别完成的原音和文字仍可从“我的记录”找回。</p>
  <div className="ct-button-row">
   {status.enabled?<button type="button" disabled={busy||status.capturing} onClick={()=>void run('stop_companion_desktop_input')}>回到录音模式</button>:<button type="button" disabled={busy||blocked||!connected||status.processing} onClick={()=>void run('start_companion_desktop_input',{shortcut})}>启用按住说话</button>}
   <label>输入框粘贴方式 <select aria-label="输入框粘贴方式" value={shortcut} disabled={busy||status.enabled||status.processing} onChange={e=>setShortcut(e.target.value)}><option value="ctrlV">普通输入框 · Ctrl+V</option><option value="ctrlShiftV">终端 · Ctrl+Shift+V</option><option value="shiftInsert">Shift+Insert</option></select></label>
  </div>
  {!connected&&!status.enabled&&<p>先连接 Companion 录音卡。</p>}
  {(status.enabled||status.processing||status.message)&&<p role="status" aria-live="polite">{status.capturing?(status.processing?'正在录音；上一段仍在处理，松开按键后会依次接收。':'正在录音，松开按键后开始识别。'):status.message}</p>}
  {error&&<p role="alert">{error}</p>}
  {status.transcript&&<div><h3>最近一次输入</h3><p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{status.transcript}</p><button type="button" disabled={busy||!status.sessionId} onClick={()=>void run('copy_companion_desktop_input',{sessionId:status.sessionId})}>复制完整文字</button></div>}
 </details>;
}
