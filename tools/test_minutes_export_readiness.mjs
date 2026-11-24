import assert from 'node:assert/strict';
import {test} from 'node:test';
import {minutesActionExportBlock} from '../packages/ui/src/minutesExportReadiness.ts';

const final = {stale:false,incomplete:false,reviewDraft:false};
test('pending, partial and stale minutes block all action handoff paths, not draft Markdown or source',()=>{
  for (const format of ['todo','todotxt','ics','calendar','calendarreminder','calendarreminder30','calendarreminder60']){
    assert.match(minutesActionExportBlock(format,{...final,incomplete:true,reviewDraft:true}),/待核对/);
    assert.match(minutesActionExportBlock(format,{...final,incomplete:true}),/未整理完整/);
    assert.match(minutesActionExportBlock(format,{...final,stale:true,incomplete:true}),/已变化/);
    assert.equal(minutesActionExportBlock(format,final),undefined);
  }
  for (const format of ['markdown','txt','srt']) assert.equal(minutesActionExportBlock(format,{...final,incomplete:true,reviewDraft:true}),undefined);
});

import {readFile} from 'node:fs/promises';
test('dashboard export handler stops before the native export boundary and gives settings feedback', async()=>{
  const source=await readFile(new URL('../packages/ui/src/CompanionDashboard.tsx',import.meta.url),'utf8');
  const from=source.indexOf('    if (!selectedSession || !onExportMeeting',source.indexOf('  const exportMeeting ='));
  const to=source.indexOf('    const savedCalendarReview=',from);
  assert(from>=0&&to>from);
  const exercise=new Function('format','origin','actionExportBlock','setExportResult','onExportMeeting',`
    const selectedSession={id:'meeting-one'},copySourceKey='revision-two',controlsBusy=false,oobeBlockedByRecording=false,exportActive={current:false};
    ${source.slice(from,to)}
    onExportMeeting();
  `);
  const receipts=[];let reachedNative=0;
  const run=(format,state)=>exercise(format,'settings',f=>minutesActionExportBlock(f,state),r=>receipts.push(r),()=>++reachedNative);
  run('todotxt',{...final,incomplete:true,reviewDraft:true});
  run('ics',{...final,stale:true});
  assert.equal(reachedNative,0);
  assert.deepEqual(receipts.map(({sessionId,format,origin,kind})=>[sessionId,format,origin,kind]),[
    ['meeting-one','todotxt','settings','error'],['meeting-one','ics','settings','error'],
  ]);
  run('markdown',{...final,reviewDraft:true,incomplete:true});run('todotxt',final);
  assert.equal(reachedNative,2);
});
