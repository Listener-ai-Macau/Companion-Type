import {useEffect,useRef,useState} from 'react';
import {invoke} from '@tauri-apps/api/core';
type Settings={mapping:'relative'|'laser';sensitivity:number;smoothing:number;deadzone:number;acceleration:number;invertHorizontal:boolean;invertVertical:boolean;desktopMotion:boolean};
type Status={enabled:boolean;ready:boolean;controlsCursor:boolean;message:string;metrics:{samples:number;missing:number;sensorHz:number;calibrated:boolean;dragging:boolean;paused:boolean}};
const defaults:Settings={mapping:'laser',sensitivity:1,smoothing:0.55,deadzone:3,acceleration:0.6,invertHorizontal:false,invertVertical:false,desktopMotion:false};
const idle:Status={enabled:false,ready:false,controlsCursor:false,message:'',metrics:{samples:0,missing:0,sensorHz:0,calibrated:false,dragging:false,paused:false}};
export function DesktopPointer({connected,blocked}:{connected:boolean;blocked:boolean}){
 const [settings,setSettings]=useState(defaults),[status,setStatus]=useState(idle),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const pending=useRef(false),mounted=useRef(true);
 useEffect(()=>{mounted.current=true;let reading=false;const read=async()=>{if(reading||pending.current)return;reading=true;try{const next=await invoke<Status>('get_companion_pointer');if(mounted.current)setStatus(next);}catch{}finally{reading=false;}};
  void read();const timer=setInterval(()=>void read(),500);return()=>{mounted.current=false;clearInterval(timer);};},[]);
 const run=async(command:string,args:Record<string,unknown>)=>{if(pending.current)return;pending.current=true;setBusy(true);setError('');try{const next=await invoke<Status>(command,args);if(mounted.current)setStatus(next);}catch(e){if(mounted.current)setError(String(e));}finally{pending.current=false;if(mounted.current)setBusy(false);}};
 const control=(action:string)=>void run('control_companion_pointer',{action});
 return <details className="ct-desktop-input" aria-label="空中鼠标">
  <summary>空中鼠标 · 转动卡片移动光标</summary>
  <p>{settings.desktopMotion?'连接后启用，先把卡片放稳约1秒。桌面平移或拿起转动都可以控制方向，移动幅度自然即可。':'连接后点击启用，把卡片放稳约1秒完成校准。拿起卡片，长边朝前，左右转动移动光标，上下转动控制高度。'}</p>
  <p>{settings.desktopMotion?'轻敲机身或短按卡片按键点击；':'双敲机身或短按卡片按键点击；'}按住超过约半秒拖拽，松开结束。此模式下按键用于鼠标，退出后恢复录音；随时按电脑 Esc 键退出。</p>
  <div className="ct-button-row">
   <label>移动方式 <select aria-label="空中鼠标移动方式" value={settings.mapping} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,mapping:e.target.value as Settings['mapping'],desktopMotion:e.target.value==='relative'&&settings.desktopMotion})}><option value="relative">相对移动 · AirCursor</option><option value="laser">指向屏幕 · WatchPointer</option></select></label>
   <label><input type="checkbox" checked={settings.desktopMotion} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,desktopMotion:e.target.checked,mapping:e.target.checked?'relative':settings.mapping})}/>桌面平移和转动一起控制</label>
   <label>灵敏度 <input aria-label="空中鼠标灵敏度" type="range" min="0.2" max="3" step="0.1" value={settings.sensitivity} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,sensitivity:Number(e.target.value)})}/>{settings.sensitivity.toFixed(1)}</label>
   <label><input type="checkbox" checked={settings.invertHorizontal} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,invertHorizontal:e.target.checked})}/>反转左右</label>
   <label><input type="checkbox" checked={settings.invertVertical} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,invertVertical:e.target.checked})}/>反转上下</label>
  </div>
  <div className="ct-button-row">
   {!status.enabled?<button className="ct-action" disabled={busy||blocked||!connected} onClick={()=>void run('start_companion_pointer',{settings,controlsCursor:true})}>启用空中鼠标</button>:<>
    <button disabled={busy||!status.ready} onClick={()=>control(status.metrics.paused?'resume':'pause')}>{status.metrics.paused?'继续控制':'暂停控制'}</button>
    <button disabled={busy||!status.ready} onClick={()=>control('recenter')}>重新定位</button>
    <button className="ct-action" disabled={busy} onClick={()=>control('stop')}>退出并回到录音</button>
   </>}
  </div>
  {!connected&&!status.enabled&&<p>先连接 Companion 录音卡。</p>}
  {status.message&&<p role="status" aria-live="polite">{status.message}</p>}
  {status.enabled&&<p>{status.metrics.calibrated?'已校准':'等待放稳'} · {status.metrics.paused?'已暂停':status.metrics.dragging?'正在拖拽':status.ready?'动作已连接':'连接中'}</p>}
  {error&&<p role="alert">{error}</p>}
  <p>算法适配自 AirCursor 与 WatchPointer；不采集麦克风音频。</p>
 </details>;
}
