import assert from 'node:assert/strict';
import {manualChecklist,toggleManualChecklist,manualQuotePreview,manualTableRowQuote} from '../packages/core/src/manualNoteContext';

const original='人工准备🙂，不是会议决定\r\n- [ ] 征集需求，负责人未定\r\n正文中的 - [ ] 不变\n  * [X] 已由我人工核对\n- [] 不是任务\n- [ ] \n原文末尾';
const items=manualChecklist(original);assert.equal(items.length,2);assert.deepEqual(items.map(i=>i.checked),[false,true]);assert.equal(items[0].text,'征集需求，负责人未定');
const next=toggleManualChecklist(original,original,items[0].markerOffset,true)!;assert.equal(next.slice(0,items[0].markerOffset),original.slice(0,items[0].markerOffset));assert.equal(next.slice(items[0].markerOffset+1),original.slice(items[0].markerOffset+1));assert.equal(next[items[0].markerOffset],'x');
assert.equal(toggleManualChecklist(next,original,items[0].markerOffset,false),null,'Stale text must not edit the new body');assert.equal(toggleManualChecklist(original,original,0,true),null);assert.equal(toggleManualChecklist(original,original,1.5,true),null);
assert.equal(manualQuotePreview('一🙂末尾',2),'一');assert.equal(manualQuotePreview('一🙂末尾',3),'一🙂');assert.equal(manualQuotePreview('原文\r\n原样',100),'原文\r\n原样');assert.equal(manualQuotePreview('a',NaN),'');
assert.equal(manualTableRowQuote({row:2,cells:[{column:'A',text:'预算\n草案'},{column:'B',text:'12,000.00'},{column:'C',text:'FALSE'},{column:'D',text:'0'}]}),'A2\t预算\n草案\nB2\t12,000.00\nC2\tFALSE\nD2\t0');
console.log('PASS literal manual checklist changes one marker only, stale edit rejection, original line endings/emoji and exact source row values.');
