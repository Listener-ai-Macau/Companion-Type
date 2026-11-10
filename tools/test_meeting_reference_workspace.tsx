import assert from 'node:assert/strict';
import React,{useEffect,useState} from 'react';
import {act,create,type ReactTestRenderer} from 'react-test-renderer';
import {MeetingReferenceWorkspace,type ReferenceView} from '../packages/ui/src/MeetingReferenceWorkspace';

let mounted=0,unmounted=0;
function Draft({name}:{name:string}){const [text,setText]=useState('');useEffect(()=>{mounted++;return()=>{unmounted++;};},[]);return <textarea aria-label={name} value={text} onChange={e=>setText(e.target.value)}/>;}
function Harness(){const [view,setView]=useState<ReferenceView>('notes');return <MeetingReferenceWorkspace view={view} onViewChange={setView} notes={<Draft name="人工便签草稿"/>} documents={<p>原件阅读位置</p>} assistant={<Draft name="AI问题草稿"/>}/>;}
let tree:ReactTestRenderer;act(()=>{tree=create(<Harness/>);});
const tabs=()=>tree!.root.findAllByProps({role:'tab'}),panels=()=>tree!.root.findAllByProps({role:'tabpanel'});
assert.equal(panels().filter(n=>!n.props.hidden).length,1);assert.equal(tabs()[0].props['aria-selected'],true);assert.equal(mounted,2);
act(()=>tree!.root.findByProps({'aria-label':'人工便签草稿'}).props.onChange({target:{value:'尚未保存，全文必须保留\n末尾'}}));
act(()=>tabs()[1].props.onClick());assert.equal(panels()[0].props.hidden,true);assert.equal(panels()[1].props.hidden,false);
act(()=>tabs()[2].props.onClick());act(()=>tree!.root.findByProps({'aria-label':'AI问题草稿'}).props.onChange({target:{value:'尚未发送的问题'}}));
act(()=>tabs()[0].props.onClick());assert.equal(tree!.root.findByProps({'aria-label':'人工便签草稿'}).props.value,'尚未保存，全文必须保留\n末尾');assert.equal(tree!.root.findByProps({'aria-label':'AI问题草稿'}).props.value,'尚未发送的问题');assert.equal(mounted,2);assert.equal(unmounted,0,'Reading-pane changes must not unmount or discard drafts');
let prevented=false;act(()=>tree!.root.findByProps({role:'tablist'}).props.onKeyDown({key:'End',preventDefault(){prevented=true;}}));assert(prevented);assert.equal(tabs()[2].props['aria-selected'],true);assert.equal(tabs().filter(n=>n.props.tabIndex===0).length,1);
for(const tab of tabs()){assert(panels().some(panel=>panel.props.id===tab.props['aria-controls']&&panel.props['aria-labelledby']===tab.props.id));}
act(()=>tree!.unmount());assert.equal(unmounted,2);
act(()=>{tree=create(<MeetingReferenceWorkspace view="assistant" onViewChange={()=>{}} notes={<p>仅本机便签</p>}/>);});assert.equal(tabs().length,1);assert.equal(tabs()[0].props['aria-selected'],true);assert.equal(panels()[0].props.hidden,false,'Unavailable panes fall back to the actual available content');act(()=>tree!.unmount());
console.log('PASS independent readable panes, stable mounted manual and AI drafts, keyboard/tab linkage and unavailable-content fallback.');
