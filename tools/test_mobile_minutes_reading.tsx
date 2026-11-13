import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MinutesDocument} from '../apps/mobile/src/MinutesDocument';

const notice='> 长会议已按原文顺序处理全部2段。分段原文依据见下文，识别和事实准确性仍需核对。';
const ai='> AI根据详细纪要整理，请结合原文核对。';
const envelope='# 公开会议\n\nGenerated: now\nDuration: 1800000 ms\nSource: boardDevice\nMinutes engine: llm_deepseek (final)\n\n';
const body='## 会议概览\n\n'+ai+'\n\n- 不取消周五发货，数量至少五件。\n\n'+notice+'\n\n'+envelope+'## Summary\n\n- 原文保留。\n\n## Decisions\n\n- 这是建议，尚未决定。';
function render(markdown:string){return renderToStaticMarkup(<MinutesDocument markdown={markdown} renderText={text=><pre>{text}</pre>}/>);}
const saved=body,html=render(saved),disclosure=html.indexOf('minutes-generation');
assert(disclosure>0);
assert(!html.slice(0,disclosure).includes('AI根据详细纪要整理'));
assert(!html.slice(0,disclosure).includes('长会议已按原文顺序处理全部'));
assert(html.slice(disclosure).includes('AI根据详细纪要整理')&&html.slice(disclosure).includes('长会议已按原文顺序处理全部2段'));
assert(html.includes('不取消周五发货，数量至少五件。')&&html.includes('这是建议，尚未决定。'));
assert.equal(body,saved);
const warned=render(body.replace(notice,notice+'其中一段原音未识别。'));
assert(warned.slice(0,warned.indexOf('minutes-generation')).includes('其中一段原音未识别。'),'an additional missing-source warning must remain in the main reading');
const authored=render('## 我的说明\n\n'+ai);
assert(authored.includes('AI根据详细纪要整理')&&!authored.includes('minutes-generation'));
const fenced=render(body.replace('- 原文保留。','```text\n'+ai+'\n```'));
assert(fenced.slice(0,fenced.indexOf('minutes-generation')).includes('AI根据详细纪要整理'),'quoted code remains source text');
console.log('PASS mobile meeting reading: one origin note, complete generated details retained; missing-source warnings and authored words preserved.');
