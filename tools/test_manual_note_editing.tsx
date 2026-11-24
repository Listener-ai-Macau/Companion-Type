import assert from 'node:assert/strict';
import React from 'react';
import {act,create,type ReactTestRenderer} from 'react-test-renderer';
import {ManualNoteEditor} from '../packages/ui/src/ManualNoteEditor';
import {TranscriptQuoteCapture} from '../packages/ui/src/TranscriptQuoteCapture';
import type {ManualEvidenceDraft} from '../packages/core/src/manualNoteContext';

let tree:ReactTestRenderer,value='准备说明😀\r\n1. 核对预算12000元\r\n2. 负责人待定\r\n\r\n保留原句，不是决定',captured:ManualEvidenceDraft|undefined,captureDone:(()=>void)|undefined;
const original=value;
const text=(node:any):string=>typeof node==='string'?node:(node?.children??[]).map(text).join('');
const button=(label:string)=>{const found=tree.root.findAllByType('button').find(node=>text(node)===label);assert(found,label+' is visible');return found;};
function renderEditor(){tree.update(<ManualNoteEditor kind="followup" text={value} label="完整原始输入" onChange={next=>{value=next;renderEditor();}}/>);}
await act(async()=>{tree=create(<ManualNoteEditor kind="followup" text={value} label="完整原始输入" onChange={next=>{value=next;renderEditor();}}/>);});
act(()=>button('将编号列表转为待办').props.onClick());
assert.equal(value,'准备说明😀\r\n- [ ] 核对预算12000元\r\n- [ ] 负责人待定\r\n\r\n保留原句，不是决定');
act(()=>tree.root.findByProps({'aria-label':'跟进事项 2'}).props.onChange({target:{value:'核对预算12000元，仍待确认'}}));
assert(value.includes('\r\n- [ ] 核对预算12000元，仍待确认\r\n'));
act(()=>tree.root.findByProps({'aria-label':'完成跟进事项 3'}).props.onChange({target:{checked:true}}));
assert(value.includes('- [x] 负责人待定\r\n\r\n保留原句，不是决定'));
const beforeLarge=value;
act(()=>tree.root.findByProps({'aria-label':'新增跟进事项'}).props.onChange({target:{value:'字'.repeat(4001)}}));
assert.equal(value,beforeLarge);assert(text(tree.toJSON()).includes('最多4000字符'));
act(()=>tree.root.findByProps({'aria-label':'新增跟进事项'}).props.onChange({target:{value:'下次确认具体日期，不猜周二是哪天'}}));
assert.equal(value,beforeLarge+'\n- [ ] 下次确认具体日期，不猜周二是哪天');
let pastePrevented=false;
const beforePaste=value;
act(()=>tree.root.findByProps({'aria-label':'新增跟进事项'}).props.onPaste({
 currentTarget:{},clipboardData:{getData:()=> '通知负责人\r\n2.核对名单\r\n- [ ] 回看原话'},
 preventDefault:()=>{pastePrevented=true;},
}));
assert(pastePrevented);
assert.equal(value,beforePaste+'\n- [ ] 通知负责人\n- [ ] 核对名单\n- [ ] 回看原话');
act(()=>button('按原格式编辑').props.onClick());assert.equal(tree.root.findByProps({'aria-label':'完整原始输入'}).props.value,value);
act(()=>button('按事项编辑').props.onClick());
act(()=>tree.root.findByProps({'aria-label':'移除跟进事项 2'}).props.onClick());
assert(!value.includes('核对预算'));assert(value.includes('- [x] 负责人待定'));assert(value.includes('保留原句，不是决定'));
act(()=>tree.unmount());
// Capture must use literal current source and its full source hash. Search is
// only a reading aid; the excerpt cannot be paraphrased or cleaned.
const source='😀开头。'+('公开连续原文，没有会议结论。'.repeat(80))+'预算 FALSE 0 尚未确认。尾句';
window.getSelection=()=>null;
await act(async()=>{tree=create(<TranscriptQuoteCapture contextId="public-a" text={source} onQuote={draft=>{captured=draft;captureDone?.();}}/>);});
act(()=>button('引用转写到备注').props.onClick());
act(()=>tree.root.findByProps({'aria-label':'查找可引用的原文'}).props.onChange({target:{value:'预算 FALSE 0'}}));
const displayed=tree.root.findAllByType('blockquote')[0].children.join('');
assert(displayed.includes('预算 FALSE 0'));assert(source.includes(displayed));assert(!/[\uD800-\uDBFF]$/.test(displayed));
await act(async()=>{const done=new Promise<void>(resolve=>captureDone=resolve);button('引用此段到备注').props.onClick();await done;captureDone=undefined;});
assert(captured);assert.equal(captured.contextId,'public-a');assert.equal(captured.evidence.quote,displayed);
const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(source));assert.equal(captured.evidence.sourceSha256,[...new Uint8Array(hash)].map(b=>b.toString(16).padStart(2,'0')).join(''));
captured=undefined;
// Android focus may collapse selection between pointerdown and click.
window.getSelection=()=>({toString:()=> '预算 FALSE 0 尚未确认。'}) as Selection;
act(()=>button('引用转写到备注').props.onPointerDown());
window.getSelection=()=>null;
await act(async()=>{const done=new Promise<void>(resolve=>captureDone=resolve);button('引用转写到备注').props.onClick();await done;captureDone=undefined;});assert.equal(captured?.evidence.quote,'预算 FALSE 0 尚未确认。');
act(()=>button('引用转写到备注').props.onClick());
act(()=>tree.root.findByProps({'aria-label':'引用的转写原文'}).props.onChange({target:{value:'预算已确认'}}));
captured=undefined;await act(async()=>button('加入备注草稿').props.onClick());assert.equal(captured,undefined);assert(text(tree.toJSON()).includes('连续的一段文字'));
act(()=>tree.unmount());
assert(original.includes('1. 核对预算'),'The original fixture was never rewritten.');
console.log('PASS ordinary follow-up conversion/edit/checked state, CRLF/emoji/mixed literal paragraphs, bounded rejected edit, exact original format access; literal source selection/search/full hash and pointer-focus preservation.');
