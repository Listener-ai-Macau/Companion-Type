import { isLocalAsrProvider } from './localAsr';
import type { ReactNode } from 'react';
import { recordingCapacityAvailableSeconds, recordingCapacityCanFit, recordingCapacityRequiredBytes, type CompanionV1RecordingCapacity, type CompanionV1Snapshot } from '@companion-type/core';
import type { CompanionProductSettingsPublic } from './CompanionDashboard';
import {deviceConnectionStatus} from './deviceConnectionStatus';
import type {CompanionV1ControlAction} from '@companion-type/core';

export function recordingRoomLabel(seconds: number) {
  const hours = Math.floor(seconds / 3600), minutes = Math.floor(seconds % 3600 / 60);
  return hours ? `${hours}小时${minutes ? `${minutes}分` : ''}`
    : minutes ? `${minutes}分钟` : `${Math.floor(seconds)}秒`;
}

/** A possibility only: free bytes do not reveal the number of complete extents. */
export function fragmentedSpaceMayFit(c: CompanionV1RecordingCapacity, seconds: number): boolean {
  const values = [c.segmentFrames, c.segmentExtentBytes, c.freeBytes, c.largestFreeExtent, c.usedEntries, c.maxEntries];
  if (c.busy || !Number.isFinite(seconds) || seconds <= 0 || !values.every(v => Number.isSafeInteger(v) && v! >= 0)
    || !c.segmentFrames || !c.segmentExtentBytes || c.usedEntries >= c.maxEntries
    || c.largestFreeExtent < c.segmentExtentBytes || c.freeBytes <= c.largestFreeExtent) return false;
  const required = recordingCapacityRequiredBytes(c, seconds);
  return Number.isSafeInteger(required) && required <= c.freeBytes
    && Math.ceil(seconds * 50 / c.segmentFrames) <= c.maxEntries - c.usedEntries
    && !recordingCapacityCanFit(c, seconds);
}

/** The last device report is advice, not a replacement for START's space check. */
export function CompanionRecordingReadiness({ snapshot, settings, recording, busy, durationSeconds,
  onConnect, onCheck, onSettings, onRefresh, onLibrary, busyAction=null, capacityDetails, actionsAbove = false }: {
  snapshot: CompanionV1Snapshot | null;
  settings: CompanionProductSettingsPublic | null;
  recording: boolean;
  busy: boolean;
  durationSeconds: number | null;
  onConnect: () => void;
  onCheck: () => void;
  onSettings: () => void;
  onRefresh: () => void;
  onLibrary?: () => void;
  busyAction?:CompanionV1ControlAction|'refresh'|null;
  capacityDetails?: ReactNode;
  actionsAbove?: boolean;
}) {
  const device = snapshot?.device;
  const preview = snapshot?.source === 'fixture' || device?.mode === 'fixture';
  const lastKnown = snapshot?.source === 'lastKnown' || snapshot?.source === 'unavailable';
  const connected = !lastKnown && Boolean(snapshot?.connected || device?.connected);
  const capacity = connected ? device?.recordingCapacity : null;
  const seconds = capacity ? recordingCapacityAvailableSeconds(capacity) : 0;
  const full = Boolean(capacity && !capacity.busy && (capacity.usedEntries >= capacity.maxEntries || seconds <= 0));
  const short = Boolean(capacity && !capacity.busy && durationSeconds !== null
    && !recordingCapacityCanFit(capacity, durationSeconds));
  const fragmentedMaybe = Boolean(capacity && durationSeconds !== null && fragmentedSpaceMayFit(capacity, durationSeconds));
  const fragmented = Boolean(capacity?.segmentFrames && capacity.segmentExtentBytes && capacity.freeBytes > capacity.largestFreeExtent);
  const save = snapshot?.host.persistence?.status;
  const saveProblem = save !== undefined && save !== 'ready';
  const recordingCheck = snapshot?.oobe.checks.find(check => check.id === 'boardMicrophone');
  const interfaceProblem = connected && recordingCheck?.status === 'fail';
  const asrConfigured = isLocalAsrProvider(settings?.asrProvider) ? Boolean(settings?.localAsrAvailable) : settings?.asrProvider === 'volcengine'
    ? Boolean(settings.volcAppKeySet && settings.volcAccessKeySet && settings.volcResourceId.trim())
    : Boolean(settings?.openaiAsrApiKeySet && settings.openaiAsrEndpoint.trim() && settings.openaiAsrModel.trim());
  const minutesConfigured = Boolean(settings?.deepseekMinutesEnabled && settings.deepseekApiKeySet
    && settings.deepseekBaseUrl.trim() && settings.deepseekModel.trim());
  const blocked = busy || recording;
  const connection=deviceConnectionStatus(snapshot,busyAction);
  const headline = preview ? '界面演示，尚未确认真实设备'
    : recording ? '录音进行中，结束后再检查准备状态'
      : !connected ? '连接卡片，接收和查看录音。'
        : saveProblem ? '请先恢复本机保存，再从电脑开始录音'
          : interfaceProblem ? '最近检查未通过，请重新检查录音接口'
            : full ? '设备空间不足，请先同步并确认保存'
              : short ? fragmentedMaybe ? '分散空间可能可用，开始前会重新核对' : '上次读取的空间不够本次时长，请先同步或缩短时长'
                : save !== 'ready' ? '本机保存状态待读取，请先刷新'
                  : !capacity || capacity.busy ? '剩余可录时长待确认，开始时由设备检查'
                    : '已连接，可以用卡片录音。';

  return <section className="ct-readiness" aria-label="录前准备">
    <header><div><h2>录音卡</h2>
      <p className={`ct-connection-state ct-connection-${connection.tone}`} role="status"><span aria-hidden="true"/>{connection.label}</p>
      <p>{connection.hint}</p></div>
      {!connected ? <button type="button" className="ct-action ct-action-primary" disabled={blocked||connection.pending} onClick={onConnect}>{connection.pending?'正在连接…':'连接设备'}</button>
        : onLibrary ? <button type="button" className="ct-action ct-action-primary" onClick={onLibrary}>查看我的记录</button>
        : <button type="button" className="ct-action" disabled={blocked} onClick={save !== 'ready' ? onRefresh : onCheck}>{save !== 'ready' ? '刷新保存状态' : '检查设备状态'}</button>}
    </header>
    {connected&&(saveProblem||interfaceProblem||full||short)?<p className="ct-step-warn" role="alert">{headline}</p>:null}
    <details className="ct-readiness-details" open={saveProblem || interfaceProblem || full || short}>
    <summary>设备、存储与服务详情</summary>
    <div className="ct-readiness-grid">
      <section aria-label="录音与保存准备">
        <h3>先录下并保存原音</h3>
        <p className="ct-readiness-note">不需要转写服务或离线识别模型。{actionsAbove?'':'下方'}“开始录音”只保存原音。</p>
        <dl>
          <div><dt>设备连接</dt><dd>{connected ? '已连接' : device?.connectionPhase === 'pairingRequired'
            ? 'Windows 配对未完成；先完成系统配对，再点击连接。'
            : lastKnown ? '当前连接未确认；上次设备结果仅供参考。'
              : '当前未连接；设备不在身边也能查看已保存的内容。'}
            </dd></div>
          <div><dt>本机保存</dt><dd>{save === 'ready' ? '最近一次保存状态正常。'
            : saveProblem ? '本机保存尚未恢复；先在保存提示中重试，当前不会因此删除已有录音。'
              : '尚未读到保存状态，请刷新后确认。'}
            {save !== 'ready' ? <button type="button" className="ct-text-button" disabled={blocked} onClick={onRefresh}>刷新保存状态</button> : null}</dd></div>
          <div><dt>设备空间</dt><dd>{!connected ? '连接后读取剩余可录时间。'
            : !capacity ? '尚未读到容量，不能预估可录时长。'
              : capacity.busy ? '上次读取时设备正在忙，结束后可重新读取。'
                : full ? '空间或录音目录已满，请先同步并确认原音已保存。'
                  : `${fragmented ? '一块连续空间' : '仅靠设备空间'}约可录 ${recordingRoomLabel(seconds)}（上次读取）${capacity.localLimitSeconds ? `；实体键单次上限 ${recordingRoomLabel(capacity.localLimitSeconds)}` : ''}。${fragmented ? '分散空间能否合用由开始时核对。' : ''}连接电脑并完成同步后，设备空间可能增加。`}
            {short && !full ? <span>{fragmentedMaybe ? `一块连续空间不足本次 ${recordingRoomLabel(durationSeconds!)}；开始时会核对分散空间，设备不支持或空间不足时会拒绝开录。` : `不足本次 ${recordingRoomLabel(durationSeconds!)}，请先同步或在“录音与同步”缩短时长。`}</span> : null}
            {connected ? <button type="button" className="ct-text-button" disabled={blocked} onClick={onCheck}>重新检查设备</button> : null}</dd></div>
          <div><dt>电量与供电</dt><dd>当前设备没有可靠电量读数，无法估计续航。长时间录音前请先充电或接稳定电源。</dd></div>
        </dl>
        {interfaceProblem ? <p className="ct-step-warn">最近检查未通过录音接口。请重新检查设备；若仍提示接口缺失，到“设置与工具”检查配套固件更新。此处不会启动麦克风试录。</p> : null}
        {capacityDetails}
      </section>
      <section aria-label="后续整理准备">
        <h3>之后再转文字、整理纪要</h3>
        <p className="ct-readiness-note">这里未准备好，也可以先录音并保存原音。</p>
        <dl>
          <div><dt>转文字</dt><dd>{!settings ? '服务设置尚未读取。' : settings.storageSaveBlocked ? '服务设置暂不可用，请到服务设置处理保存提示。'
            : asrConfigured ? isLocalAsrProvider(settings?.asrProvider) ? '本地转写模型已准备，实际识别效果以使用结果为准。' : '转写配置已保存；是否可调用仍以实际服务结果为准。'
              : '转写配置尚不完整，需要时再到服务设置补齐。'}</dd></div>
          <div><dt>智能纪要</dt><dd>{!settings ? '服务设置尚未读取。' : settings.storageSaveBlocked ? '服务设置暂不可用。'
            : minutesConfigured ? '纪要配置已保存；是否可调用仍以实际服务结果为准。'
              : settings.deepseekMinutesEnabled ? '纪要配置尚不完整；仍可查看文字或手写清单。'
                : '智能纪要未启用；仍可查看文字或手写清单。'}</dd></div>
        </dl>
        <button type="button" className="ct-text-button" onClick={onSettings}>查看服务设置</button>
        <p className="ct-readiness-note">{isLocalAsrProvider(settings?.asrProvider)
          ? '电脑本地转写不会上传录音。'
          : settings?.asrProvider === 'volcengine' || settings?.asrProvider === 'openai-compatible'
            ? '云端转写会把录音发送给所选服务。' : '电脑本地转写不上传录音；选择云端转写时会发送录音。'}
          智能纪要会把选定的文字发送给配置的纪要服务。本地说话人区分组件是可选项，不是录音或保存原音的前提。</p>
      </section>
    </div>
    </details>
  </section>;
}
