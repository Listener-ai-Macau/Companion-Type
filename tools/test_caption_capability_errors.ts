import assert from 'node:assert/strict';
import {operationErrorText} from '../packages/ui/src/operationFailure';
// The broad safe-error filter must not turn a protocol refusal into advice to
// start another recording, change credentials, or repeatedly retry the service.
for(const text of [
  '当前字幕协议版本不受支持；回复已保留，请更新匹配的 Companion Type 与固件。',
  '字幕状态无法核对；回复已保留，请重新读取设备状态。',
  '当前连接未提供可核对的字幕读写接口；回复已保留。',
  '这块固件还不支持宠物聊天字幕，请先安装匹配的联合固件。',
]) assert.equal(operationErrorText(new Error(text),'chat'),text);
const privateFailure='unknown PCS1 failure path=C:/private/example.wav token=not-a-real-token';
assert.ok(!operationErrorText(privateFailure,'chat').includes('example.wav'));
assert.ok(!operationErrorText(privateFailure,'chat').includes('not-a-real-token'));
console.log('PASS explicit caption compatibility advice remains visible; unknown diagnostics stay private.');
