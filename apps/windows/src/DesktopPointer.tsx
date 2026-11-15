import {useEffect,useRef,useState} from 'react';
import {invoke} from '@tauri-apps/api/core';
type Profile={schema:2;left:number[][];right:number[][];leftThreshold:number;rightThreshold:number};
type Settings={mapping:'relative'|'laser';sensitivity:number;smoothing:number;deadzone:number;acceleration:number;invertHorizontal:boolean;invertVertical:boolean;desktopMotion:boolean;relativeDirect:boolean;relativeHorizontal:'tilt'|'turn';keyRole:'regrip'|'clickDrag';tapClick:boolean;contactRegions:boolean;contactProfile?:Profile|null;contactDevice?:string|null};
type ContactStatus={learning:'left'|'right'|null;leftSamples:number;rightSamples:number;calibrated:boolean;missedWindows:number;uncertain:number;lastSide:'left'|'right'|null};
type Status={enabled:boolean;ready:boolean;controlsCursor:boolean;message:string;deviceId?:string;settings?:Settings;contacts?:ContactStatus;metrics:{samples:number;missing:number;sensorHz:number;calibrated:boolean;dragging:boolean;paused:boolean;regripping:boolean;surfacePaused?:boolean}};
const defaults:Settings={mapping:'relative',sensitivity:1,smoothing:0,deadzone:0,acceleration:0,invertHorizontal:false,invertVertical:false,desktopMotion:false,relativeDirect:true,relativeHorizontal:'tilt',keyRole:'regrip',tapClick:true,contactRegions:false};
const idle:Status={enabled:false,ready:false,controlsCursor:false,message:'',metrics:{samples:0,missing:0,sensorHz:0,calibrated:false,dragging:false,paused:false,regripping:false}};
// Keep the old laser/planar settings intact under their original key. This
// profile has deliberately different motion and physical-key semantics.
const savedKey='companion-pointer-relative-v4';
function savedSettings():Settings{try{
 const saved=JSON.parse(localStorage.getItem(savedKey)||'null') as Settings|null;
 if((saved?.desktopMotion&&!saved.relativeDirect)||(saved?.contactProfile&&saved.contactProfile.schema!==2)){
  // Archive the old mixed planar mode. The explicit surface mode uses only
  // acceleration for XY; it may retain the accepted personal contact profile.
  if(!localStorage.getItem(savedKey+'-planar-paused'))localStorage.setItem(savedKey+'-planar-paused',JSON.stringify(saved));
 }
 const valid=saved?.contactProfile?.schema===2;
 return {...defaults,...saved,desktopMotion:!!(saved?.desktopMotion&&saved.relativeDirect),contactProfile:valid?saved.contactProfile:null,contactDevice:valid?saved.contactDevice:null};
}catch{return defaults;}}
export function DesktopPointer({connected,blocked}:{connected:boolean;blocked:boolean}){
 const [settings,setSettings]=useState(savedSettings),[status,setStatus]=useState(idle),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const pending=useRef(false),mounted=useRef(true);
 useEffect(()=>{mounted.current=true;let reading=false;const read=async()=>{if(reading||pending.current)return;reading=true;try{const next=await invoke<Status>('get_companion_pointer');if(mounted.current){setStatus(next);if(next.enabled&&next.settings)setSettings(next.settings);}}catch{}finally{reading=false;}};
  void read();const timer=setInterval(()=>void read(),500);return()=>{mounted.current=false;clearInterval(timer);};},[]);
 const run=async(command:string,args:Record<string,unknown>)=>{if(pending.current)return;pending.current=true;setBusy(true);setError('');try{const next=await invoke<Status>(command,args);if(mounted.current){setStatus(next);if(next.settings&&(command==='start_companion_pointer'||args.action==='contact-save'||args.action==='contact-clear')){setSettings(next.settings);try{localStorage.setItem(savedKey,JSON.stringify(next.settings));}catch{/* This session remains usable when local settings cannot be saved. */}}}}catch(e){if(mounted.current)setError(String(e));}finally{pending.current=false;if(mounted.current)setBusy(false);}};
 const control=(action:string)=>void run('control_companion_pointer',{action});
 return <details className="ct-desktop-input" aria-label="空中鼠标">
  <summary>Companion 鼠标 · {settings.desktopMotion?'桌面平移试用':'倾斜遥控'}</summary>
  <p>{settings.desktopMotion?'Type-C端朝前，先在桌面放稳约1秒。前后左右推动来移动光标；抬起回位暂停约2秒，放稳后继续。若未恢复，点“重新放稳”。':'Type-C端朝前，先稳住约1秒。像小跷跷板一样侧倾：右边压低向右、左边压低向左；抬高Type-C端向上，放低向下。转动才移动，停手光标停在当前位置。'}</p>
  <p>{settings.contactRegions?'Type-C朝前，敲左前是左键、敲右前是右键，连敲左前两下是双击。首次先校准两个前角。':'轻敲外壳一下是左键，连敲两下是双击。'}{settings.keyRole==='regrip'?'需要点得更稳时，可以按住实体键稳住光标，再轻敲外壳。要拿回舒服的握姿时，按住实体键再把卡片拿回来，松开继续。':'短按实体键也能点击，按住片刻并转动可拖拽；换握姿时点“暂停换握姿”，调整好再继续。'}退出后恢复录音和双敲标记；电脑 Esc 随时退出。</p>
  <div className="ct-button-row">
   <label>移动方式 <select aria-label="空中鼠标移动方式" value={settings.desktopMotion?'surface':settings.mapping==='laser'?'laser':settings.relativeHorizontal} disabled={busy||status.enabled} onChange={e=>{const relative=e.target.value!=='laser',surface=e.target.value==='surface';setSettings({...defaults,mapping:relative?'relative':'laser',relativeDirect:relative,desktopMotion:surface,invertHorizontal:surface,invertVertical:surface,relativeHorizontal:e.target.value==='turn'?'turn':'tilt',sensitivity:settings.sensitivity,contactRegions:relative&&(surface||settings.contactRegions),contactProfile:relative?settings.contactProfile:null,contactDevice:relative?settings.contactDevice:null,...(!relative?{smoothing:0.55,deadzone:3,acceleration:0.6,keyRole:'clickDrag' as const}:{})});}}><option value="surface">桌面平移 · 试用</option><option value="tilt">左右侧倾</option><option value="turn">左右转向</option><option value="laser">激光指向 · 进阶</option></select></label>
   {settings.relativeDirect&&<label>实体键用途 <select aria-label="空中鼠标实体键用途" value={settings.keyRole} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,keyRole:e.target.value as Settings['keyRole']})}><option value="regrip">按住换握姿 · 推荐</option><option value="clickDrag">短按点击／按住拖拽</option></select></label>}
   <label>灵敏度 <input aria-label="空中鼠标灵敏度" type="range" min="0.2" max="3" step="0.1" value={settings.sensitivity} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,sensitivity:Number(e.target.value)})}/>{settings.sensitivity.toFixed(1)}</label>
   <label><input type="checkbox" checked={settings.invertHorizontal} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,invertHorizontal:e.target.checked})}/>反转左右</label>
   <label><input type="checkbox" checked={settings.invertVertical} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,invertVertical:e.target.checked})}/>反转上下</label>
   {settings.relativeDirect&&<label><input type="checkbox" checked={settings.contactRegions} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,contactRegions:e.target.checked,contactProfile:e.target.checked?settings.contactProfile:null,contactDevice:e.target.checked?settings.contactDevice:null})}/>左右前角分别点击 · 首次需校准</label>}
   <label><input type="checkbox" checked={settings.tapClick} disabled={busy||status.enabled} onChange={e=>setSettings({...settings,tapClick:e.target.checked})}/>轻敲外壳点击</label>
  </div>
  <div className="ct-button-row">
   {!status.enabled?<button className="ct-action" disabled={busy||blocked||!connected} onClick={()=>void run('start_companion_pointer',{settings,controlsCursor:true})}>{settings.desktopMotion?'启用桌面鼠标':'启用空中鼠标'}</button>:<>
    <button disabled={busy||!status.ready} onClick={()=>control(status.metrics.paused?'resume':'pause')}>{status.metrics.paused?'从这里继续':'暂停换握姿'}</button>
    {settings.desktopMotion&&<button disabled={busy||!status.ready} onClick={()=>control('calibrate')}>重新放稳</button>}
    {settings.mapping==='laser'&&<button disabled={busy||!status.ready} onClick={()=>control('recenter')}>以当前握姿居中</button>}
    <button className="ct-action" disabled={busy} onClick={()=>control('stop')}>退出并回到录音</button>
   </>}
  </div>
  {status.enabled&&settings.contactRegions&&<div aria-label="前角敲击校准">
   <p>Type-C端朝前，按平时的方式握住。校准时光标暂不移动；同一次敲击的回弹只计一次。左右各三次，保存后会记住这块卡片的设置。</p>
   <div className="ct-button-row">
    <button disabled={busy||!status.ready||!status.metrics.calibrated||status.metrics.paused} onClick={()=>control('contact-left')}>校准左前 · {status.contacts?.leftSamples||0}/3</button>
    <button disabled={busy||!status.ready||(status.contacts?.leftSamples||0)<3} onClick={()=>control('contact-right')}>校准右前 · {status.contacts?.rightSamples||0}/3</button>
    <button disabled={busy||(status.contacts?.leftSamples||0)<3||(status.contacts?.rightSamples||0)<3} onClick={()=>control('contact-save')}>保存左右敲击</button>
    {status.contacts?.learning&&<button disabled={busy} onClick={()=>control('contact-cancel')}>取消校准</button>}
    {status.contacts?.calibrated&&<button disabled={busy} onClick={()=>control('contact-clear')}>重新校准</button>}
   </div>
   {status.contacts?.learning&&<p role="status">请轻敲{status.contacts.learning==='left'?'左前':'右前'}角；每次敲后稍等，看到计数再继续。不需要敲得很重。</p>}
  </div>}
  {!connected&&!status.enabled&&<p>先连接 Companion 录音卡。</p>}
  {status.message&&<p role="status" aria-live="polite">{status.message}</p>}
  {status.enabled&&<p>{status.metrics.calibrated?'已就绪':settings.desktopMotion?'请在桌面放稳约1秒':'请稳住卡片约1秒，无需水平'} · {status.metrics.paused?'已暂停':status.metrics.regripping?'正在换握姿，松开按键继续':status.metrics.surfacePaused?'回位暂停中，请放回平面':status.metrics.dragging?'正在拖拽':status.ready?'动作已连接':'连接中'}</p>}
  {error&&<p role="alert">{error}</p>}
  <p>{settings.desktopMotion?'桌面平移仍在试用，请在同一桌面短距离使用。':'适合临时遥控、演示和点选，无需一直瞄准屏幕中心。'}轻敲需要短促触碰外壳；需要拖拽时，可在启用前把实体键用途改成“短按点击／按住拖拽”。可同时使用普通鼠标。鼠标模式不采集麦克风音频。</p>
 </details>;
}
