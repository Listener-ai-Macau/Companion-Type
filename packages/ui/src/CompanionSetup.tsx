import { useEffect, useState } from 'react';
import { AlertTriangle, Bluetooth, Check, ChevronDown, ChevronUp, CircleDashed, Link2, ListChecks, Mic, Search, Settings2, Unlink, Volume2, XCircle } from 'lucide-react';
import type { CompanionV1ControlRequest, CompanionV1Snapshot } from '@companion-type/core';
import { companionCanChangeOfflineRecordingLink } from '@companion-type/core';
import type { CompanionProductSettingsPublic } from './CompanionDashboard';
import {operationErrorText} from './operationFailure';

function deviceStatus(snapshot:CompanionV1Snapshot|null):string{
  const device=snapshot?.device;
  if(!device)return '设备状态尚未读取。';
  if(device.connectionPhase==='pairingRequired')return 'Windows 配对未完成，已暂停自动重试。请检查设备配对入口后主动连接；原录音保留。';
  if(device.connectionPhase==='checking')return '正在核对设备连接，请稍候。';
  if(device.connectionPhase==='reconnecting')return '正在寻找已记住的设备；已有录音保留。';
  if(device.connected||snapshot?.connected)return '已识别设备连接；模块状态以最近一次检查结果为准。';
  if(device.connectionPhase==='manualDisconnected')return '已主动断开；需要时可重新连接，已有录音保留。';
  if(snapshot?.lastControl?.accepted===false)return operationErrorText(device.message,'device');
  if(snapshot?.oobe.lastRunAt)return '检查已结束，当前设备未连接；最近一次结果保留在下方。';
  return '设备尚未连接；已有本机录音仍可查看。';
}

function checkMessage(check:{status:string;message:string}):string{
  if(check.status!=='fail')return check.message;
  // Keep these exact authored results distinct from arbitrary native errors.
  if(['未检查：设备连接失败','DEVICE_STATUS 已读取，但身份字段不完整',
    'DEVICE_STATUS 未读到；设备可能未配对、未授权或固件协议不匹配',
    '录音/会议核心 GATT 不完整，未启动实录','未取得校时写后读回证据','已装配，但未在线'].includes(check.message))return check.message;
  return operationErrorText(check.message,'device');
}

export function CompanionSetup({ snapshot, settings, busy, recording, checking, onControl, onSettings, onWorkflow, onLibrary }: {
  snapshot: CompanionV1Snapshot | null;
  settings: CompanionProductSettingsPublic | null;
  busy: boolean;
  recording: boolean;
  checking: boolean;
  onControl: (request: CompanionV1ControlRequest) => void;
  onSettings: () => void;
  onWorkflow: () => void;
  onLibrary?: () => void;
}) {
  const device = snapshot?.device;
  const known = Boolean(snapshot?.connected || device?.connected);
  const preview = snapshot?.source === 'fixture' || device?.mode === 'fixture';
  const asrReady = settings?.asrProvider === 'volcengine'
    ? settings.volcAppKeySet && settings.volcAccessKeySet
    : settings?.openaiAsrApiKeySet;
  const speaker = snapshot?.speaker;
  const checks = snapshot?.oobe.checks ?? [];
  const checked = Boolean(snapshot?.oobe.lastRunAt);
  const issueCount = checks.filter((check) => check.status === 'fail').length;
  const blocked = busy || recording;
  const offlineLink = companionCanChangeOfflineRecordingLink(snapshot, { action: 'deviceConnect', deviceId: device?.deviceId ?? undefined });
  const linkBlocked = busy || (recording && !offlineLink);
  const guideDeviceId = preview ? '' : normalizeGuideDeviceId(device?.deviceId || device?.rememberedDeviceId || '');
  const [storedGuide, setStoredGuide] = useState({ deviceId: '', open: true, heardReply: false, recordedSample: false, sawRecording: false });
  const guide = storedGuide.deviceId === guideDeviceId
    ? storedGuide : { deviceId: guideDeviceId, open: true, heardReply: false, recordedSample: false, sawRecording: false };
  useEffect(() => {
    if (!guideDeviceId) {
      setStoredGuide({ deviceId: '', open: true, heardReply: false, recordedSample: false, sawRecording: false });
      return;
    }
    try {
      const parsed = JSON.parse(window.localStorage.getItem(guideStorageKey(guideDeviceId)) ?? '{}');
      setStoredGuide({ deviceId: guideDeviceId, open: parsed.open !== false,
        heardReply: parsed.heardReply === true, recordedSample: parsed.recordedSample === true, sawRecording: parsed.sawRecording === true });
    } catch {
      setStoredGuide({ deviceId: guideDeviceId, open: true, heardReply: false, recordedSample: false, sawRecording: false });
    }
  }, [guideDeviceId]);
  const updateGuide = (patch: Partial<Omit<typeof guide, 'deviceId'>>) => {
    const next = { ...guide, ...patch, deviceId: guideDeviceId };
    setStoredGuide(next);
    if (!guideDeviceId || preview) return;
    try { window.localStorage.setItem(guideStorageKey(guideDeviceId), JSON.stringify(next)); } catch { /* The guide still works for this session. */ }
  };
  const hasVisibleRecording = Boolean(snapshot?.host.sessions.length);
  const guideComplete = Boolean(guideDeviceId) && !preview && guide.heardReply && guide.recordedSample && guide.sawRecording;
  const guideConnectionDone = known && !preview || guideComplete;

  return (
    <section className="ct-setup" aria-label="Companion 连接与准备">
      <header className="ct-setup-head">
        <div className="ct-setup-identity">
          <span className="ct-setup-symbol"><Bluetooth size={23} /></span>
          <div><h2>你的 Companion</h2><p>{known ? snapshot?.bleName.activeName : '先连接，再带它认识你的电脑'}</p></div>
        </div>
        <span className={`ct-pill ${known && !preview ? 'ct-pill-good' : ''}`}>{preview ? '浏览器演示' : known ? '已识别' : '待连接'}</span>
      </header>
      {preview ? <p className="ct-setup-note">这是界面演示，连接和检查结果不代表真实设备。</p> : null}
      {settings?.storageWarning ? <p className="ct-step-warn" role="alert">
        {settings.storageWarning} <button type="button" className="ct-text-button" onClick={onSettings}>查看服务设置</button>
      </p> : null}
      <div className="ct-button-row">
        <button type="button" className="ct-action" disabled={blocked} onClick={() => onControl({ action: 'deviceScan' })}><Search size={16} />扫描设备</button>
        <button type="button" className="ct-action ct-action-primary" disabled={linkBlocked} onClick={() => onControl({ action: 'deviceConnect', deviceId: device?.deviceId ?? undefined })}><Link2 size={16} />{known ? '重新连接' : '连接 Companion'}</button>
        {known ? <button type="button" className="ct-action" disabled={linkBlocked} onClick={() => onControl({ action: 'deviceDisconnect' })}><Unlink size={16} />断开</button> : null}
        <button type="button" className="ct-action" disabled={blocked} onClick={() => onControl({ action: 'oobeRunChecks', deviceId: device?.deviceId ?? undefined })}><ListChecks size={16} />{checking ? '正在检查…' : '检查设备'}</button>
      </div>
      <p className="ct-setup-note">{offlineLink ? '断开蓝牙后设备继续录音；重新连接可继续标记，结束后保存原音。'
        : recording ? '录音进行中，连接与设备检查暂时停用。' : '首次连接时让设备靠近电脑，并在设备菜单中开启配对。检查只读取模块与校准时间，不会开始录音。'}</p>
      <section className={`ct-first-run ${guideComplete ? 'complete' : ''}`} aria-label="第一次使用向导">
        <button type="button" className="ct-first-run-head" aria-expanded={guide.open}
          onClick={() => updateGuide({ open: !guide.open })}>
          <span><strong>{guideComplete ? '第一次使用已完成' : '第一次使用 · 约 1 分钟'}</strong><small>连接、听回应、录 10 秒、确认记录</small></span>
          {guide.open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        {guide.open ? <ol className="ct-first-run-list">
          <li className={guideConnectionDone ? 'done' : ''}><span>{guideConnectionDone ? <Check size={13} /> : '1'}</span><div><strong>连接真实 Companion</strong><p>{preview ? '浏览器演示不能完成这一步。' : known ? '已识别真实设备。' : guideComplete ? '设备暂不在线；这台设备的引导记录已保留。' : '点击上方“连接 Companion”。'}</p></div></li>
          <li className={guide.heardReply ? 'done' : ''}><span>{guide.heardReply ? <Check size={13} /> : '2'}</span><div><strong>听一声宠物回应</strong><p>先点“听一声回应”；只有你实际听到后再确认。</p><div className="ct-button-row"><button type="button" className="ct-text-button" disabled={blocked || !known || !speaker?.supported || !speaker.online || speaker.muted} onClick={() => onControl({ action: 'speakerPrompt' })}><Volume2 size={14} />播放宠物音</button><button type="button" className="ct-text-button" disabled={!known || !guideDeviceId || preview || recording} onClick={() => updateGuide({ heardReply: true })}>我已听到</button></div></div></li>
          <li className={guide.recordedSample ? 'done' : ''}><span>{guide.recordedSample ? <Check size={13} /> : '3'}</span><div><strong>长按实体键，录一段约 10 秒的声音</strong><p>若已睡着，先短按唤醒。长按实体键约 1 秒开始，录约 10 秒后，再长按约 1 秒停止。</p><div className="ct-button-row"><button type="button" className="ct-text-button" disabled={!known || preview || busy} onClick={onWorkflow}><Mic size={14} />查看同步步骤</button><button type="button" className="ct-text-button" disabled={!known || !guideDeviceId || preview || recording} onClick={() => updateGuide({ recordedSample: true })}>我已完成试录</button></div></div></li>
          <li className={guide.sawRecording ? 'done' : ''}><span>{guide.sawRecording ? <Check size={13} /> : '4'}</span><div><strong>在“我的录音”找到刚才的记录</strong><p>{hasVisibleRecording ? '“我的录音”已有记录，请按录制时间或时长核对。' : '同步完成后，记录会出现在“我的录音”。'}</p><div className="ct-button-row">{onLibrary ? <button type="button" className="ct-text-button" onClick={onLibrary}>打开我的录音</button> : null}<button type="button" className="ct-text-button" disabled={!hasVisibleRecording || !guide.recordedSample || preview} onClick={() => updateGuide({ sawRecording: true, open: false })}>我已看到记录</button></div></div></li>
          <li className="ct-first-run-note">这些勾选只记录你的引导进度，不代表硬件验收结果；更换 Companion 后会使用独立进度。</li>
        </ol> : null}
      </section>
      {device?.rememberedDeviceId ? <div className="ct-reconnect-setting">
        <label><input type="checkbox" checked={device.autoReconnectEnabled} disabled={blocked} onChange={(event) => onControl({ action: event.target.checked ? 'deviceEnableAutoReconnect' : 'deviceDisableAutoReconnect' })} />自动连接我的 Companion</label>
        <small>{!device.autoReconnectEnabled ? '自动连接已关闭；需要时可主动连接设备。'
          : device.manualDisconnect ? '你已主动断开。点击连接或重新开启此选项后才会恢复。'
          : device.connectionPhase === 'pairingRequired' ? 'Windows 配对未完成，已暂停自动重试。请检查设备配对入口后点击连接；原录音保留。'
          : device.connectionPhase === 'reconnecting' || device.connectionPhase === 'checking' ? '正在寻找上次连接的设备…'
            : device.connectionPhase === 'offline' ? '设备暂时不在附近，稍后会重试；已有会议可继续查看。'
              : '只连接已记住的设备；不会自动开始录音或上传内容。'}</small>
      </div> : null}
      <div className="ct-setup-grid">
        <div><span className="ct-setup-index">01</span><strong>连接与时间</strong><p>{checking ? '正在读取设备，请稍候' : issueCount ? '检查发现问题，请展开详情' : checked ? '检查已结束，详情保留在下方' : known ? '已识别设备，可检查模块与时间' : '连接后自动同步设备时间'}</p></div>
        <div><span className="ct-setup-index">02</span><strong>互动与声音</strong><p>{!known ? '连接后读取动作传感器与扬声器' : snapshot?.imu.online ? '动作传感器已响应；实际灵敏度需体验' : '动作传感器尚未就绪'}</p><button type="button" className="ct-text-button" disabled={blocked || !known || !speaker?.supported || !speaker.online || speaker.muted} onClick={() => onControl({ action: 'speakerPrompt' })}><Volume2 size={14} />{speaker?.muted ? '设备已静音' : '听一声回应'}</button></div>
        <div><span className="ct-setup-index">03</span><strong>会议整理</strong><p>{!settings ? '服务设置尚未读取，可刷新后重试' : settings.storageSaveBlocked ? '服务设置暂不可用，请查看上方提示' : !asrReady ? '配置转写服务后，可把录音转为文字' : settings.deepseekMinutesEnabled && settings.deepseekApiKeySet ? '服务凭据已保存，实际调用待验证' : '转写凭据已保存，可配置智能纪要'}</p><button type="button" className="ct-text-button" onClick={onSettings}><Settings2 size={14} />服务设置</button></div>
      </div>
      <details className="ct-setup-details" open={checked && issueCount > 0}>
        <summary>设备与检查详情{checked ? ` · ${issueCount ? `${issueCount} 项需处理` : '查看各项结果'}` : ' · 尚未检查'}</summary>
        <p className="ct-step-meta">{device?.hardwareRevision ?? '型号未读取'}{device?.firmwareVersion != null ? ` · 固件 ${formatFirmware(device.firmwareVersion)}` : ''}{device?.deviceId ? ` · ${device.deviceId}` : ''}</p>
        {device?.message ? <p className="ct-step-meta">{deviceStatus(snapshot)}</p> : null}
        <div className="ct-check-list">{checks.map((check) => (
          <div key={check.id} className={`ct-check ct-check-${check.status}`}>
            {check.status === 'pass' ? <Check size={15} /> : check.status === 'warn' ? <AlertTriangle size={15} /> : check.status === 'fail' ? <XCircle size={15} /> : <CircleDashed size={15} />}
            <span className="ct-check-copy"><strong>{check.label}</strong><small>{checkMessage(check)}</small></span>
          </div>
        ))}</div>
        <p className="ct-step-meta">这里只显示最近一次读取结果。屏幕观感、触摸手感和实际录音效果仍需在设备上检查。</p>
      </details>
    </section>
  );
}

function formatFirmware(version: number) {
  return `${(version >>> 16) & 255}.${(version >>> 8) & 255}.${version & 255}`;
}

function normalizeGuideDeviceId(value: string): string {
  return value.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
}

function guideStorageKey(deviceId: string): string {
  return `companion-type:first-run:v1:${deviceId}`;
}
