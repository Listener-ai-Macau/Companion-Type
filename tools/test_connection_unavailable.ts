import assert from 'node:assert/strict';
import {describeOperationFailure} from '../packages/ui/src/operationFailure';

const initial=describeOperationFailure('DEVICE_UNREACHABLE: OS diagnostic and C:/private/path','general');
assert.equal(initial.kind,'device');
assert.match(initial.message,/设备有电/);
assert.match(initial.message,/蓝牙已开启/);
assert.match(initial.message,/另一台手机或电脑/);
assert.doesNotMatch(initial.message,/private|diagnostic|DEVICE_UNREACHABLE/);
const ordinary=describeOperationFailure('device disconnected','recording');
assert.match(ordinary.message,/读取当前状态/);
assert.doesNotMatch(ordinary.message,/唤醒状态/);
const similar=describeOperationFailure('prefix DEVICE_UNREACHABLE: unrelated','general');
assert.doesNotMatch(similar.message,/唤醒状态/);
console.log('PASS initial unavailable-recorder guidance; ordinary recording errors and private detail filtering retained');
