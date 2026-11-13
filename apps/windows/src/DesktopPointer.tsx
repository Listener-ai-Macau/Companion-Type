import {useEffect,useRef,useState} from 'react';
import {invoke} from '@tauri-apps/api/core';
type Profile={left:number[];right:number[]};
type Settings={mapping:'relative'|'laser';sensitivity:number;smoothing:number;deadzone:number;acceleration:number;invertHorizontal:boolean;invertVertical:boolean;desktopMotion:boolean;contactProfile?:Profile|null;contactDevice?:string|null};
type ContactStatus={learning:'left'|'right'|null;leftSamples:number;rightSamples:number;calibrated:boolean;missedWindows:number;uncertain:number;lastSide:'left'|'right'|null};
type Status={enabled:boolean;ready:boolean;controlsCursor:boolean;message:string;deviceId?:string;settings?:Settings;contacts?:ContactStatus;metrics:{samples:number;missing:number;sensorHz:number;calibrated:boolean;dragging:boolean;paused:boolean}};
const defaults:Settings={mapping:'laser',sensitivity:1,smoothing:0.55,deadzone:3,acceleration:0.6,invertHorizontal:false,invertVertical:false,desktopMotion:false};
const idle:Status={enabled:false,ready:false,controlsCursor:false,message:'',metrics:{samples:0,missing:0,sensorHz:0,calibrated:false,dragging:false,paused:false}};
const savedKey='companion-pointer-contact-v1';
function savedSettings():Settings{try{
 const saved=JSON.parse(localStorage.getItem(savedKey)||'null') as Settings|null;
 if(saved?.desktopMotion||saved?.contactProfile){
  // Owner paused planar/contact experiments. Keep those examples for a later
  // explicit mode rather than restoring mixed motion in the current product.
  if(!localStorage.getItem(savedKey+'-planar-paused'))localStorage.setItem(savedKey+'-planar-paused',JSON.stringify(saved));
 }
 return {...defaults,...saved,desktopMotion:false,contactProfile:null,contactDevice:null};
}catch{return defaults;}}
export function DesktopPointer({connected,blocked}:{connected:boolean;blocked:boolean}){
 const [settings,setSettings]=useState(savedSettings),[status,setStatus]=useState(idle),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const pending=useRef(false),mounted=useRef(true);
 useEffect(()=>{mounted.current=true;let reading=false;const read=async()=>{if(reading||pending.current)return;reading=true;try{const next=await invoke<Status>('get_companion_pointer');if(mounted.current){setStatus(next);if(next.enabled&&next.settings)setSettings(next.settings);}}catch{}finally{reading=false;}};
  void read();const timer=setInterval(()=>void read(),500);return()=>{mounted.current=false;clearInterval(timer);};},[]);
 const run=async(command:string,args:Record<string,unknown>)=>{if(pending.current)return;pending.current=true;setBusy(true);setError('');try{const next=await invoke<Status>(command,args);if(mounted.current){setStatus(next);if(next.settings&&(command==='start_companion_pointer'||args.action==='contact-save'||args.action==='contact-clear')){setSettings(next.settings);try{localStorage.setItem(savedKey,JSON.stringify(next.settings));}catch{/* This session remains usable when local settings cannot be saved. */}}}}catch(e){if(mounted.current)setError(String(e));}finally{pending.current=false;if(mounted.current)setBusy(false);}};
 const control=(action:string)=>void run('control_companion_pointer',{action});
 return <details className="ct-desktop-input" aria-label="空中鼠标">
  <summary>空中鼠标 · 转动卡片移动光标</summary>
  <p>点击启用后，将卡片稳住约1秒，放在桌面或拿稳都可以，不必严格水平。校准完成后，左右转动、上下倾斜来移动光标；桌面平移已暂停。</p><p>换握姿时，稳住卡片，点“以当前握姿居中”即可，不需要重新校准传感器。</p>
  <p>敲击机身或短按卡片按键点击；按住超过约半秒拖拽，松开结束。此模式下按键用于鼠标，退出后恢复录音；随时按电脑 Esc 键退出。</p>
  <div className="ct-button-row">
   <label>移动方式 <select aria-label="空中鼠标移动方式" value={settings.mapping} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,mapping:e.target.value as Settings['mapping'],desktopMotion:false,contactProfile:null,contactDevice:null})}><option value="relative">相对移动 · AirCursor</option><option value="laser">指向屏幕 · WatchPointer</option></select></label>
   <label>灵敏度 <input aria-label="空中鼠标灵敏度" type="range" min="0.2" max="3" step="0.1" value={settings.sensitivity} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,sensitivity:Number(e.target.value)})}/>{settings.sensitivity.toFixed(1)}</label>
   <label><input type="checkbox" checked={settings.invertHorizontal} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,invertHorizontal:e.target.checked})}/>反转左右</label>
   <label><input type="checkbox" checked={settings.invertVertical} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,invertVertical:e.target.checked})}/>反转上下</label>
  </div>
  <div className="ct-button-row">
   {!status.enabled?<button className="ct-action" disabled={busy||blocked||!connected} onClick={()=>void run('start_companion_pointer',{settings,controlsCursor:true})}>启用空中鼠标</button>:<>
    <button disabled={busy||!status.ready} onClick={()=>control(status.metrics.paused?'resume':'pause')}>{status.metrics.paused?'继续控制':'暂停控制'}</button>
    <button disabled={busy||!status.ready} onClick={()=>control('recenter')}>以当前握姿居中</button>
    <button className="ct-action" disabled={busy} onClick={()=>control('stop')}>退出并回到录音</button>
   </>}
  </div>
  {!connected&&!status.enabled&&<p>先连接 Companion 录音卡。</p>}
  {status.message&&<p role="status" aria-live="polite">{status.message}</p>}
  {status.enabled&&<p>{status.metrics.calibrated?'已就绪':'请稳住卡片约1秒，无需水平'} · {status.metrics.paused?'已暂停':status.metrics.dragging?'正在拖拽':status.ready?'动作已连接':'连接中'}</p>}
  {error&&<p role="alert">{error}</p>}
  <p>移动算法适配自 AirCursor 与 WatchPointer；不采集麦克风音频。</p>
 </details>;
}
