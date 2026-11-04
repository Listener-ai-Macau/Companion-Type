import assert from 'node:assert/strict';
import { companionMinutesReferencedSources, type CompanionTranscriptSource } from '../packages/core/src/minutesSources';
const source = (index: number, speaker: number | null, text: string): CompanionTranscriptSource =>
  ({ sessionId: 'synthetic', index, text, speaker, startMs: index * 2000, endMs: index * 2000 + 1000, reviewRevision: null });
const rows = [source(0, 0, '先核对预算。'), source(1, 0, '再决定交付。'), source(2, 1, '暂不承诺日期。')];
const first = (quote: string) => companionMinutesReferencedSources(rows, quote).map(row => row.index);
assert.deepEqual(first('先核对预算。 说话人1: 再决定交付。'), [0]);
assert.deepEqual(first('说话人1: 先核对预算。 再决定交付。'), [0]);
assert.deepEqual(first('说话人1: 再决定交付。 说话人2: 暂不承诺日期。'), [1]);
assert.deepEqual(first('说话人2: 先核对预算。'), []);
assert.deepEqual(first('说话人1: 啊'), []);
const repeated = [source(0, 0, '核对预算后再决定。'), source(1, 1, '核对预算后再决定。')];
assert.deepEqual(companionMinutesReferencedSources(repeated, '核对预算后再决定。'), []);
assert.deepEqual(companionMinutesReferencedSources(repeated, '说话人2: 核对预算后再决定。').map(row => row.index), [1]);
const missing = [source(0, 0, '先核对预算。'), source(2, 1, '暂不承诺日期。')];
assert.deepEqual(companionMinutesReferencedSources(missing, '先核对预算。 说话人2: 暂不承诺日期。'), []);
console.log('speaker-labelled source references: passed');
