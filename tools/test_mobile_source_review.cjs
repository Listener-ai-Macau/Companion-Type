// Exact source linking must never manufacture a time for ambiguous or stale text.
const assert=require('node:assert/strict');
const vm=require('node:vm');
const {buildSync}=require('esbuild');
const out=buildSync({entryPoints:['apps/mobile/src/mobileSourceReview.ts'],bundle:true,write:false,platform:'node',format:'cjs'}).outputFiles[0].text;
const sandbox={module:{exports:{}},exports:{},require};sandbox.exports=sandbox.module.exports;vm.runInNewContext(out,sandbox);
const {splitMobileEvidence,uniqueMobileEvidenceWindow:match,uniqueMobileQuote}=sandbox.module.exports;
const detail={transcript:'前文。小周周五发送报告。后文。',before:null,minutesChanged:false};
const quote='小周周五发送报告。';
const timed={available:true,original:false,windows:[{text:'前文。',startMs:0,endMs:4000},{text:quote,startMs:4000,endMs:9000}]};
assert.equal(match(detail,timed,quote),1);
assert.equal(match({...detail,transcript:detail.transcript+quote},timed,quote),null,'repeated transcript quote');
assert.equal(match(detail,{...timed,windows:[...timed.windows,{text:quote,startMs:10000,endMs:12000}]},quote),null,'repeated time window');
assert.equal(match(detail,{...timed,windows:[{text:quote+quote,startMs:0,endMs:5000}]},quote),null,'repeated quote in one window');
assert.equal(match({...detail,minutesChanged:true},timed,quote),null,'changed source');
assert.equal(match({...detail,transcriptUnreadable:true},timed,quote),null,'unreadable source');
assert.equal(match(detail,{...timed,available:false},quote),null,'no timing');
assert.equal(match(detail,{...timed,windows:[{text:quote,startMs:100,endMs:100}]},quote),null,'invalid interval');
assert.equal(match(detail,{...timed,original:true},quote),null,'missing saved original');
assert.equal(match({...detail,before:'旧内容不含引用'}, {...timed,original:true},quote),null,'quote absent from original');
assert.equal(match({...detail,before:detail.transcript}, {...timed,original:true},quote),1,'same quote survives a text revision');
assert.equal(match({...detail,before:detail.transcript},timed,quote),null,'timing origin conflicts with saved original');
assert.equal(match(detail,timed,'周五'),null,'short ambiguous quote');
const across={transcript:'前文。小周周五\n发送报告。后文。',before:null,minutesChanged:false};
const acrossTiming={available:true,original:false,windows:[
  {text:'前文。小周周五',startMs:0,endMs:4000},
  {text:'发送报告。后文。',startMs:4000,endMs:9000}
]};
assert.equal(match(across,acrossTiming,'小周周五\n发送报告。'),0,'a verified quote spanning two windows points to the first window');
assert.equal(match(across,acrossTiming,'小周周五 发送报告。'),0,'line breaks in the source may be spaces in the evidence');
assert.equal(uniqueMobileQuote(across.transcript,'小周周五 发送报告。'),true,'long-minutes source link is available across line breaks');
assert.equal(uniqueMobileQuote(across.transcript,'小周周五，发送报告。'),false,'punctuation changes must not be treated as the original quote');
assert.equal(match({...across,transcript:'前文。小周周五发送报告。后文。'},acrossTiming,'小周周五发送报告。'),0,'single-line evidence crossing a window is locatable');
assert.equal(match(across,{...acrossTiming,windows:[acrossTiming.windows[0],{...acrossTiming.windows[1],text:'发送报告。不同后文。'}]},'小周周五\n发送报告。'),null,'partial timing source cannot locate an otherwise matching quote');
assert.equal(match(across,{...acrossTiming,windows:[acrossTiming.windows[0],{...acrossTiming.windows[1],startMs:3999}]},'小周周五\n发送报告。'),null,'overlapping timing windows cannot be joined');
assert.equal(match({...across,minutesChanged:true},acrossTiming,'小周周五\n发送报告。'),null,'changed minutes cannot use cross-window matching');
const repeated={transcript:'小周周五\n发送报告。小周 周五发送报告。',before:null,minutesChanged:false};
const repeatedTiming={available:true,original:false,windows:[{text:'小周周五',startMs:0,endMs:2000},{text:'发送报告。小周 周五发送报告。',startMs:2000,endMs:9000}]};
assert.equal(match(repeated,repeatedTiming,'小周周五\n发送报告。'),null,'whitespace-only differences must not create a false unique match');
const markdown='## 摘要\n\n- 发送报告\n\n## 原话核对\n\n> 以下原话由 AI 关联，仅供核对；关联和转写可能有误。\n\n- 事项：发送报告\n- 原话：“'+quote+'”\n';
const parsed=splitMobileEvidence(markdown,detail);assert.equal(parsed.entries[0].quote,quote);
assert.equal(splitMobileEvidence(markdown,{...detail,transcript:'不同内容'}),null,'unsupported source');
assert.equal(splitMobileEvidence(markdown,{...detail,transcriptUnreadable:true}),null,'unreadable source');
vm.runInNewContext('String.prototype.matchAll=undefined',sandbox);
assert.equal(splitMobileEvidence(markdown,detail),null,'old WebView must keep the original minutes instead of crashing');
console.log('Mobile exact evidence: unique, repeated, changed, unavailable and invalid timings passed.');
