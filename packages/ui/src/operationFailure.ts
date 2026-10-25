import {knownOperationErrors} from './knownOperationErrors';

export type OperationScope='general'|'device'|'recording'|'save'|'export'|'playback'|'settings'|'update'|'diagnostics'|'diagnosticsRead'|'serviceCheck'|'components'|'chat'|'profile';
export type OperationFailureKind='permission'|'storage'|'rateLimit'|'network'|'device'|'configuration'|'busy'|'conflict'|'integrity'|'cancelled'|'unknown';
export type OperationFailure={kind:OperationFailureKind;message:string};

const known=new Set(knownOperationErrors);
const advice={
  permission:'无法访问所需文件或功能。请检查当前用户的权限，或解除其它程序对相关文件和功能的占用；不要清空已有录音。',
  storage:'本机磁盘空间不足。请释放保存位置所在磁盘的空间，再重试；尚未确认保存的修改请先保留。',
  rateLimit:'服务暂时限制请求。请稍后再试，或核对当前服务额度；不要连续重复提交。',
  network:'服务连接未完成。请检查网络和服务状态后再试；原有内容请保留，不需要重新录音。',
  device:'设备操作尚未确认。请先到“设备与同步”读取当前状态，避免重复开录、停录或写入。',
  configuration:'服务配置或授权尚不可用。请到“设置与工具”检查当前配置，不要在反馈中附上密钥。',
  busy:'上一项操作仍未结束。请先查看当前录音或处理状态，结束后再操作，不要重复提交。',
  conflict:'内容或设备状态已经变化。请重新读取当前内容，核对后再操作；未确认的修改请先保留。',
  integrity:'内容或软件包未通过完整性核对。请保留原文件和当前提示，不要强行覆盖或混用软件包。',
  cancelled:'操作已取消；未确认的保存或设备操作请先核对当前状态。',
} satisfies Record<Exclude<OperationFailureKind,'unknown'>,string>;
const fallback:Record<OperationScope,string>={
  general:'操作未完成或结果尚未确认。请保留当前内容，查看“使用帮助”中的恢复方法；仍有问题可手动导出诊断日志。',
  device:advice.device,recording:advice.device,
  save:'保存尚未确认。请保留当前修改，不要关闭应用；检查本机存储状态后再重试保存。',
  export:'文件导出未完成。请检查保存位置是否可用；不要用导出文件覆盖原音，已有内容请保留。',
  playback:'暂时无法准备或定位原音。请查看这条录音的原音是否已收齐，保留当前内容后再试。',
  settings:'设置尚未确认保存。请保留当前填写内容，检查本机存储或服务配置后再试。',
  update:'升级操作尚未确认。请保留当前软件包，查看升级状态和恢复说明，不要强行覆盖正在使用的程序。',
  diagnostics:'诊断日志未能导出。请检查保存位置；已有录音和文字不需要清理。',
  diagnosticsRead:'本机日志暂未能读取。可以收起预览，稍后再查看；已有录音和文字不需要清理。',
  components:'说话人区分组件尚未准备完成。请检查下载连接和本机存储后再试；已有录音会保留，不需要重新录音。',
  serviceCheck:'服务测试未完成。请检查已保存的服务配置和当前连接；本次测试不处理已有录音，不需要重新录音。',
  chat:'这次聊天操作尚未确认。请先查看当前聊天和设备状态，再决定结束或重新开始，不要重复开聊。',
  profile:'宠物档案操作尚未确认。请先重新读取当前宠物档案，核对结果后再修改，避免重复写入。',
};

const permissionAdvice:Partial<Record<OperationScope,string>>={
  save:'本机录音库保存被权限或文件占用阻止。请先保留当前输入，解除文件占用、检查本机存储权限，再用原来的保存入口重试。不要关闭应用或清空录音。',
  settings:'设置保存被权限或文件占用阻止。请先保留填写内容，检查本机存储权限或解除文件占用，再重试保存设置。',
  export:'无法写入导出位置。请解除目标文件占用、检查目录权限，或另选可写的本机位置；不要覆盖原音。',
  diagnosticsRead:'读取本机日志被权限或文件占用阻止。请检查本机状态目录的读取权限或解除占用，再明确重试；不要清空录音或文字。',
  playback:'读取原音被权限或文件占用阻止。请检查原音是否仍在本机，并解除文件占用后再回听；不要删除原音。',
  device:'设备访问被权限或占用阻止。请先到“设备与同步”核对当前连接和状态，不要连续重复设备操作。',
  profile:'档案操作所需的访问未获确认。请核对当前连接和本机权限，先重新读取宠物档案，不要连续重复写入。',
};
for(const message of [...Object.values(advice),...Object.values(fallback),...Object.values(permissionAdvice)])known.add(message);

function messageOf(error:unknown):string{
  // Never stringify arbitrary objects or expose stacks, server JSON or paths.
  try{return typeof error==='string'?error.slice(0,4096):error instanceof Error?error.message.slice(0,4096):'';}
  catch{return '';}
}
function classify(text:string,scope:OperationScope):OperationFailureKind{
  if(/(?:\b(?:ENOSPC|StorageFull)\b|no space left on device|os error 112\b|磁盘空间不足)/i.test(text))return 'storage';
  if(/(?:(?:^(?:HTTP\s*)?(?:401|403)\b|\bHTTP(?: status)?[:= ]+(?:401|403)\b|\b(?:Unauthorized|Forbidden)\b)|服务.{0,8}(?:密钥|授权|配置)|未配置|not configured|missing (?:api|access)[ _-]?key)/i.test(text))return 'configuration';
  if(/(?:\bHTTP(?: status)?[:= ]+(?:402|429)\b|^429\b|quota exceeded|rate limit)/i.test(text))return 'rateLimit';
  if(/(?:\b(?:EACCES|EPERM|EROFS|PermissionDenied|ReadOnlyFilesystem)\b|access (?:is )?denied|permission denied|os error (?:5|32|33)\b|sharing violation|lock violation|文件正在使用中|只读文件系统|目录权限|拒绝访问)/i.test(text))return 'permission';
  if(/(?:签名|哈希|完整性|checksum|hash mismatch|invalid signature|invalid manifest)/i.test(text))return 'integrity';
  if(/(?:已改变|已变化|已更新|旧回复已撤回|期间发生变化|revision (?:conflict|mismatch))/i.test(text))return 'conflict';
  if(/(?:请先结束|正在录音|上一项操作|上一句聊天|\b(?:device_busy|operation_busy)\b)/i.test(text))return 'busy';
  if(/(?:设备未连接|尚未连接|没有连接|请先正常连接|宠物身份|device (?:not connected|disconnected)|BLE.{0,15}(?:disconnect|unavailable))/i.test(text))return 'device';
  if(/(?:\b(?:ECONNREFUSED|ECONNRESET|ENOTFOUND|EAI_AGAIN)\b|failed to (?:fetch|connect)|network (?:error|unreachable)|DNS|没连上.{0,8}服务)/i.test(text))return 'network';
  if(/(?:timed? ?out|timeout|超时)/i.test(text))return ['chat','settings','serviceCheck'].includes(scope)?'network':['device','recording','profile'].includes(scope)?'device':'unknown';
  if(/^(?:操作已取消。?|聊天已取消。?|cancelled|canceled)$/i.test(text))return 'cancelled';
  return 'unknown';
}

/** Presentation only: does not retry, change state, confirm a save, or discard
 * diagnostics. Existing exact native guard contracts retain their semantics;
 * arbitrary OS/service details become bounded, actionable public guidance. */
export function describeOperationFailure(error:unknown,scope:OperationScope='general'):OperationFailure{
  const text=messageOf(error).replace(/^Error:\s*/,''),kind=classify(text,scope);
  if(known.has(text))return {kind,message:text};
  return {kind,message:kind==='unknown'?fallback[scope]:kind==='permission'?(permissionAdvice[scope]??advice.permission):advice[kind]};
}
export function operationErrorText(error:unknown,scope:OperationScope='general'):string{
  return describeOperationFailure(error,scope).message;
}
