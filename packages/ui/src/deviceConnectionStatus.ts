import type {CompanionV1Snapshot,CompanionV1ControlAction} from '@companion-type/core';

/** Live link identity stays separate from storage, processing and cached reports. */
export function deviceConnectionStatus(snapshot:CompanionV1Snapshot|null,busyAction:CompanionV1ControlAction|'refresh'|null=null){
  const device=snapshot?.device;
  const cached=snapshot?.source==='lastKnown'||snapshot?.source==='unavailable';
  const preview=snapshot?.source==='fixture'||device?.mode==='fixture';
  const connected=!cached&&!preview&&Boolean(snapshot?.connected||device?.connected);
  const phase=device?.connectionPhase;
  if(preview)return {connected:false,pending:false,tone:'neutral',label:'界面演示',hint:'这里展示界面，真实连接请在配套应用中操作。'};
  if(connected)return {connected:true,pending:false,tone:'connected',label:'已连接',hint:'可以用卡片录音，录音和整理结果都在“我的记录”。'};
  if(phase==='pairingRequired')return {connected:false,pending:false,tone:'attention',label:'需要配对',hint:'先完成系统配对，再点“连接设备”。'};
  if(busyAction==='deviceConnect'||phase==='checking'||phase==='reconnecting')return {connected:false,pending:true,tone:'pending',label:phase==='reconnecting'?'正在重连':'正在连接',hint:'正在寻找并连接录音卡，请稍候。'};
  if(snapshot?.lastControl?.action==='deviceConnect'&&snapshot.lastControl.accepted===false)return {connected:false,pending:false,tone:'attention',label:'连接未成功',hint:'确认卡片已开机并在附近，再点“连接设备”重试。'};
  if(phase==='manualDisconnected')return {connected:false,pending:false,tone:'neutral',label:'已断开',hint:'需要时重新连接，已保存的录音仍可查看。'};
  return {connected:false,pending:false,tone:'neutral',label:'未连接',hint:cached?'当前连接未确认，已保存的录音仍可查看。':'连接后，卡片录音会自动保存到“我的记录”。'};
}
