import assert from 'node:assert/strict';
import React from 'react';
import {act,create} from 'react-test-renderer';
import {cleanHesitations,transcriptParagraphs} from '../packages/ui/src/transcriptReading';
import {MeetingTopic,topicReadingParts} from '../packages/ui/src/MeetingTopic';
import {TranscriptFind} from '../packages/ui/src/TranscriptFind';
import {readFileSync} from 'node:fs';
import {libraryPreview} from '../packages/ui/src/libraryPreview';

const original='嗯，我们呃，不能把三个月改成两个月。\n嗯。\n啊？\n他说“嗯、呃是原话”，那个那个产品仍需核对。';
const cleaned=cleanHesitations(original);
assert.equal(cleaned.text,'我们不能把三个月改成两个月。\n嗯。\n啊？\n他说“嗯、呃是原话”，那个产品仍需核对。');
assert.equal(original.includes('呃，'),true,'reading must not mutate saved recognition');
for(const t of ['嗯。','啊？','那个产品不能下架。','这就是三个产品，然后再判断。','“嗯不是同意”','不要把四十到四十五天改成四十五天。'])assert.equal(cleanHesitations(t).text,t);
assert.equal(topicReadingParts('陈列与鲜度要求：不能超过四层；需冷藏的放冷柜。').body,'不能超过四层；需冷藏的放冷柜。');
const full='连续三个月处于末尾三位，且促销后仍不佳，才考虑淘汰。';
let topic:any;act(()=>{topic=create(<MeetingTopic text={full}/>);});
assert.equal(topic.root.findAllByType('details').length,0,'ordinary note content is visible without opening each item');
assert.equal(topic.root.findByType('h5').children.join(''),'连续三个月处于末尾三位');
assert(topic.root.findByType('p').children.join('').includes('且促销后仍不佳'));
act(()=>topic.unmount());

// Search spans remain in the original full string even when display has paragraphs.
const text='甲'.repeat(125)+'。不能删除条件。';const paragraphs=transcriptParagraphs(text);
assert.equal(paragraphs.length,2);
let tree:any;act(()=>{tree=create(<TranscriptFind texts={[text]}>{highlight=><><p>{highlight(paragraphs[0],0,0)}</p><p>{highlight(paragraphs[1],0,126)}</p></>}</TranscriptFind>);});
const input=tree.root.findByType('input');act(()=>input.props.onChange({target:{value:'不能删除'}}));
assert.equal(tree.root.findByType('mark').children.join(''),'不能删除');
act(()=>tree.unmount());
const savedSample=process.env.COMPANION_TEST_POLISH_MINUTES??process.env.COMPANION_TEST_PUBLIC_SOURCE_MINUTES;
if(savedSample){
 const session=JSON.parse(readFileSync(savedSample,'utf8'));
 const before=JSON.stringify(session);const view=libraryPreview(session,'');
 // A validated stored overview is a useful library identity; the source is
 // still searchable literally and must keep its existing source destination.
 if(session.minutesByMode.offlineStore.markdown.includes('## 会议概览')){
  assert.equal(view.label,'纪要');assert.equal(view.target,'result');assert(view.text.includes('果蔬'));
 }
 assert(libraryPreview(session,'呃').text.includes('呃'));
 assert.equal(libraryPreview(session,'呃').target,'source');
 assert.equal(JSON.stringify(session),before);
}
console.log('PASS note hierarchy, reversible cleanup, short-answer/quote/number conditions and paragraph source search.');
