import assert from 'node:assert/strict';
import React,{useState} from 'react';
import {act,create,type ReactTestRenderer} from 'react-test-renderer';
import {TranscriptReplace} from '../apps/mobile/src/TranscriptReplace';
let tree:ReactTestRenderer,saved='千问确认金额100；千问没有确认金额100。a.b 与 axb。',draft=saved;
function View(){const [text,setText]=useState(draft);return <><TranscriptReplace text={text} disabled={false} onChange={next=>{draft=next;setText(next);}}/><button data-manual onClick={()=>{draft=text+'人工补充';setText(draft);}}>manual</button></>;}
act(()=>{tree=create(<View/>);});
const fill=(label:string,value:string)=>act(()=>tree.root.findByProps({'aria-label':label}).props.onChange({target:{value}}));
const button=(name:string)=>tree.root.findAllByType('button').find(node=>node.children.join('')===name)!;
fill('查找要替换的文字','千问');fill('替换成的文字','千问模型');act(()=>button('替换 2 处').props.onClick());
assert.equal(draft,'千问模型确认金额100；千问模型没有确认金额100。a.b 与 axb。');assert.equal(saved,'千问确认金额100；千问没有确认金额100。a.b 与 axb。','replacement must not save or alter the original source');
act(()=>button('撤销这次替换').props.onClick());assert.equal(draft,saved);
fill('查找要替换的文字','a.b');fill('替换成的文字','$&');act(()=>button('替换 1 处').props.onClick());assert.ok(draft.endsWith('$& 与 axb。'),'search and replacement must both remain literal');
act(()=>tree.root.findByProps({'data-manual':true}).props.onClick());assert.equal(button('撤销这次替换').props.disabled,true,'undo must not erase a newer manual edit');
fill('查找要替换的文字','');assert.equal(button('替换 0 处').props.disabled,true);act(()=>tree.unmount());
act(()=>{tree=create(<TranscriptReplace text={'a'.repeat(2000)} disabled={false} onChange={()=>{throw Error('oversized edit must not apply');}}/>);});fill('查找要替换的文字','a');fill('替换成的文字','b'.repeat(2000));assert.equal(button('替换 2000 处').props.disabled,true);act(()=>tree.unmount());
console.log('PASS literal draft-only correction, preserved negation/numbers, original unchanged, safe undo, literal symbols, empty search and oversized expansion.');
