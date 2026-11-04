import assert from 'node:assert/strict';
import {splitLongMinutesEvidence} from '../packages/ui/src/briefMinutes';
import {savedActions} from '../packages/ui/src/savedActions';

const markdown=`> 部分纪要：已完成3/4段。尚未处理的内容未计入完整结果。

# 会议纪要

## Action Items

- [ ] 已核对事项

## 未核对的参考草稿

> 以下是 AI 返回但未能自动对应原文的内容，仅供回听核对；可能有误，不作为已确认的决定或待办。

### 第1段

- 讨论：产品包装
- 可能的行动：发送报价（可能的负责人：小王）

## 分段原文依据

### 第1段

> 尚未整理；原文仍在完整转写中。`;
const projected=splitLongMinutesEvidence(markdown);
assert.ok(projected);assert.match(projected.overview,/未核对的参考草稿/);
assert.match(projected.overview,/可能的行动：发送报价/);
assert.deepEqual(savedActions(markdown).map(item=>item.text),['已核对事项']);
console.log('PASS unverified long-meeting content remains visible without becoming a saved action');
