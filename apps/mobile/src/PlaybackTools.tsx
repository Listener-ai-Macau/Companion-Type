import {RotateCcw,RotateCw} from 'lucide-react';
import './playbackTools.css';
export function PlaybackTools({active,disabled,position,duration,speed,onSeek,onSpeed,onRestart}:{active:boolean;disabled:boolean;position:number;duration:number;speed:number;onSeek:(position:number)=>void;onSpeed:(speed:number)=>void;onRestart:()=>void}){
 if(!active&&position<=0)return null;
 return <div className={`playback-tools${active?'':' playback-tools-idle'}`} aria-label="回听控制">{active&&<div className="playback-tools-row">
  <button type="button" disabled={disabled||!active} aria-label="后退10秒" onClick={()=>onSeek(Math.max(0,position-10000))}><RotateCcw size={16}/><span>10秒</span></button>
  <label><span className="visually-hidden">回听倍速</span><select aria-label="回听倍速" disabled={disabled||!active} value={speed} onChange={event=>onSpeed(Number(event.target.value))}>{[.75,1,1.25,1.5,1.75,2].map(value=><option key={value} value={value}>{value}×{value===1?' 正常':''}</option>)}</select></label>
  <button type="button" disabled={disabled||!active} aria-label="前进10秒" onClick={()=>onSeek(Math.max(0,Math.min(duration-1,position+10000)))}><span>10秒</span><RotateCw size={16}/></button>
 </div>}<button type="button" className="playback-restart" disabled={disabled} onClick={onRestart}>从头播放</button></div>;
}
