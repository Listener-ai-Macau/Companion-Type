import assert from 'node:assert/strict';
import {transcriptMatches,transcriptLookupTerms} from '../packages/ui/src/transcriptMatching';
const rows=['嗯，周五交付。周五再核对。','预算 .* [1] 不变。','İ 计划 🎙️ i'];
const source=JSON.stringify(rows);
assert.deepEqual(transcriptMatches(rows,'周五'),[{row:0,start:2,end:4},{row:0,start:7,end:9}]);
assert.equal(transcriptMatches(rows,'.*').length,1,'regex metacharacters must be literal');
assert.equal(transcriptMatches(rows,'[1]').length,1);
assert.deepEqual(transcriptMatches(rows,'不存在'),[]);
assert.deepEqual(transcriptMatches(rows,'  '),[]);
assert.deepEqual(transcriptMatches(['aAAa'],'aa'),[{row:0,start:0,end:2},{row:0,start:2,end:4}]);
for(const term of ['İ','🎙️','i'])for(const match of transcriptMatches(rows,term))assert.equal(rows[match.row].slice(match.start,match.end).toLocaleLowerCase(),term.toLocaleLowerCase());
assert.equal(JSON.stringify(rows),source,'reading must never change saved text');
const suggested=transcriptLookupTerms(['请在周五前采购消毒湿巾。周五交货。'],'待核对：周五采购消毒湿巾，负责人未明确');
assert.ok(suggested.length>0);
for(const suggestion of suggested){assert.ok('待核对：周五采购消毒湿巾，负责人未明确'.includes(suggestion.term));assert.equal(suggestion.count,transcriptMatches(['请在周五前采购消毒湿巾。周五交货。'],suggestion.term).length);assert.ok(suggestion.count>0);}
assert.deepEqual(transcriptLookupTerms(['无相关原话'],'这条事项完全没有对应文字'),[]);
console.log('PASS literal, Unicode, multi-row and source-preserving transcript matching');
