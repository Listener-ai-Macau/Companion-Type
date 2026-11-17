import assert from 'node:assert/strict';
import React from 'react';
import {act,create,ReactTestRenderer} from 'react-test-renderer';
import {DesktopPointer} from '../apps/windows/src/DesktopPointer';

// Real component rendering with a stub transport. No native pointer, BLE,
// microphone, customer data or browser/desktop window is opened.
const storage=new Map<string,string>();
(globalThis as any).localStorage={getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,value)};
(globalThis as any).__pointerStatus={enabled:false,ready:false,controlsCursor:false,message:'',metrics:{samples:0,missing:0,sensorHz:0,calibrated:false,dragging:false,paused:false,regripping:false}};
(globalThis as any).__pointerCalls=[];
let rendered:ReactTestRenderer;
const text=()=>JSON.stringify(rendered.toJSON());
const selector=()=>rendered.root.findByProps({'aria-label':'空中鼠标移动方式'});
await act(async()=>{rendered=create(<DesktopPointer connected blocked={false}/>);});
assert.equal(selector().props.value,'laser');
assert.match(text(),/激光指向/);assert.match(text(),/对着屏幕中心/);
assert.doesNotMatch(text(),/右边压低向右/);
await act(async()=>{selector().props.onChange({target:{value:'turn'}});});
assert.match(text(),/转向式空中鼠标/);assert.match(text(),/停止转动就停/);
await act(async()=>{selector().props.onChange({target:{value:'tilt'}});});
assert.equal(selector().props.value,'tilt');assert.match(text(),/右边压低向右/);
assert.doesNotMatch(text(),/把前端向左或向右转/);
await act(async()=>{selector().props.onChange({target:{value:'laser'}});});
assert.match(text(),/重新对准/);assert.doesNotMatch(text(),/右边压低向右/);
await act(async()=>{selector().props.onChange({target:{value:'surface'}});});
assert.match(text(),/前后左右推动/);assert.doesNotMatch(text(),/把前端向左或向右转/);
await act(async()=>{rendered.unmount();});
// A changed new-user default must not erase an intentionally saved mode.
storage.set('companion-pointer-relative-v4',JSON.stringify({mapping:'relative',relativeDirect:true,relativeHorizontal:'tilt',desktopMotion:false,sensitivity:1.7,invertHorizontal:true}));
await act(async()=>{rendered=create(<DesktopPointer connected blocked={false}/>);});
assert.equal(selector().props.value,'tilt');
assert.equal(rendered.root.findByProps({'aria-label':'空中鼠标灵敏度'}).props.value,1.7);
assert.match(text(),/右边压低向右/);
await act(async()=>{rendered.unmount();});
storage.clear();
(globalThis as any).__pointerStatus={...(globalThis as any).__pointerStatus,enabled:true,ready:true,metrics:{...(globalThis as any).__pointerStatus.metrics,calibrated:true}};
await act(async()=>{rendered=create(<DesktopPointer connected blocked={false}/>);});
const center=rendered.root.findAllByType('button').find(b=>b.children.join('')==='对准屏幕中心');
assert.ok(center);assert.equal(center.props.disabled,false);
await act(async()=>{center.props.onClick();});
assert.ok((globalThis as any).__pointerCalls.some((call:any)=>call.command==='control_companion_pointer'&&call.args.action==='center-screen'));
await act(async()=>{rendered.unmount();});
console.log('PASS: default laser, mode-specific instructions, explicit center action and saved preference');
// The bundled React development scheduler retains a MessagePort on Node.
// All renderer/effect cleanup and assertions have completed in this process.
process.exit(0);
