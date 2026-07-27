import { useEffect, useMemo, useState } from 'react';
import {
  Bluetooth,
  Check,
  ChevronDown,
  ChevronUp,
  Download,
  Eraser,
  FileText,
  HardDrive,
  Link2,
  ListChecks,
  Mic,
  Play,
  RefreshCw,
  Search,
  Shield,
  Square,
  Trash2,
  Unlink,
  Upload,
  Volume2,
} from 'lucide-react';

import {
  type CompanionV1ControlAction,
  type CompanionV1ControlRequest,
  type CompanionV1Snapshot,
  companionBleNameIsValid,
  describeSessionPendingReason,
  selectedCompanionHostSession,
} from '@companion-type/core';

export interface CompanionDashboardProps {
  snapshot: CompanionV1Snapshot | null;
  busyAction: CompanionV1ControlAction | 'refresh' | null;
  error: string | null;
  surface: 'windows' | 'mobile';
  onRefresh: () => void;
  onControl: (request: CompanionV1ControlRequest) => void;
}

const DEFAULT_TRANSCRIPT = [
  'Decision: Companion host owns long meeting recordings.',
  'Action owner: Chen due: Friday validates minutes export.',
  'Question: should offline show needs_transcription?',
].join('\n');

export function CompanionDashboard({
  snapshot,
  busyAction,
  error,
  surface,
  onRefresh,
  onControl,
}: CompanionDashboardProps) {
  const [draftName, setDraftName] = useState('companion');
  const [draftTitle, setDraftTitle] = useState('设备会议');
  const [draftMinutes, setDraftMinutes] = useState('60');
  const [transcriptDraft, setTranscriptDraft] = useState(DEFAULT_TRANSCRIPT);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const selectedSession = useMemo(
    () => (snapshot ? selectedCompanionHostSession(snapshot) : null),
    [snapshot],
  );
  const device = snapshot?.device;
  const oobe = snapshot?.oobe;
  const privacy = snapshot?.privacy;
  const connected = Boolean(snapshot?.connected || device?.connected);

  useEffect(() => {
    if (snapshot) setDraftName(snapshot.bleName.stagedName);
  }, [snapshot?.bleName.stagedName]);

  useEffect(() => {
    if (!selectedSession) return;
    setDraftTitle(selectedSession.title);
    if (selectedSession.transcriptText) setTranscriptDraft(selectedSession.transcriptText);
  }, [selectedSession?.id, selectedSession?.transcriptText, selectedSession?.title]);

  const nameError = draftName.length > 0 && !companionBleNameIsValid(draftName)
    ? 'BLE 名称不合法'
    : null;

  const minutesMarkdown = selectedSession?.exportMarkdown
    || selectedSession?.minutes?.markdown
    || '';
  const hasMinutes = Boolean(minutesMarkdown.trim());
  const hasSyncedAudio = Boolean(
    selectedSession
    && (selectedSession.source === 'deviceFlash' || selectedSession.audioBytes > 0 || selectedSession.audioPath),
  );
  const pendingHint = describeSessionPendingReason(selectedSession?.pendingReason ?? null);
  const canGenerate = Boolean(selectedSession?.transcriptText.trim());
  const canTranscribe = Boolean(
    selectedSession
    && selectedSession.status !== 'recording'
    && (selectedSession.audioPath || selectedSession.audioBytes || selectedSession.source === 'deviceFlash'),
  );
  const canEraseAudio = Boolean(selectedSession?.audioPath || selectedSession?.audioBytes);
  const canEraseTranscript = Boolean(selectedSession?.transcriptText || selectedSession?.minutes);
  const requestedDurationMs = Math.max(1, Number.parseInt(draftMinutes, 10) || 60) * 60000;

  // Product path: board required for primary minutes flow.
  let step = 1;
  if (connected) step = 2;
  if (connected && hasSyncedAudio) step = 3;
  if (connected && hasSyncedAudio && selectedSession?.transcriptText) step = 4;
  if (hasMinutes && selectedSession?.source === 'deviceFlash') step = 5;

  const simpleStatus = !connected
    ? '请先连接板子'
    : hasMinutes
      ? '纪要已生成'
      : selectedSession?.pendingReason
        ? '已同步，待转写'
        : hasSyncedAudio
          ? '已同步设备录音'
          : '已连接，请同步短录';

  const footer = useMemo(() => {
    if (error) return error;
    if (nameError) return nameError;
    if (!connected) return '主路径：连接板子 → 同步录音 → 转写 → 纪要';
    if (hasMinutes) return '纪要已就绪';
    return '按步骤 1→2→3→4 操作';
  }, [error, nameError, connected, hasMinutes]);

  return (
    <main className={`ct-shell ct-simple ct-${surface}`}>
      <header className="ct-topbar">
        <div>
          <p className="ct-kicker">Companion Type</p>
          <h1>会议纪要</h1>
        </div>
        <button
          className="ct-icon-button"
          type="button"
          onClick={onRefresh}
          disabled={busyAction !== null}
          title="刷新"
          aria-label="刷新"
        >
          <RefreshCw size={18} />
        </button>
      </header>

      <section className="ct-simple-status" aria-live="polite">
        <span className={`ct-simple-dot ${connected ? 'ok' : 'idle'}`} />
        <strong>{simpleStatus}</strong>
        <span className="ct-simple-sub">
          {connected
            ? `已连接 ${device?.deviceId ?? snapshot?.bleName.activeName ?? 'companion'}`
            : '主路径必须连接板子'}
        </span>
      </section>

      {error ? (
        <section className="ct-pending-banner" role="alert">{error}</section>
      ) : null}

      {pendingHint && connected ? (
        <section className="ct-pending-banner" role="status">{pendingHint}</section>
      ) : null}

      {/* Step path: board first */}
      <section className="ct-steps" aria-label="主路径步骤">
        <div className={`ct-step ${step >= 1 ? 'active' : ''} ${connected ? 'done' : ''}`}>
          <span className="ct-step-n">1</span>
          <div className="ct-step-body">
            <strong>连接板子</strong>
            <p>扫描并连接 Companion</p>
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action"
                disabled={busyAction !== null}
                onClick={() => onControl({ action: 'deviceScan' })}
              >
                <Search size={16} />
                <span>扫描</span>
              </button>
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={busyAction !== null}
                onClick={() => onControl({
                  action: 'deviceConnect',
                  deviceId: device?.deviceId ?? undefined,
                })}
              >
                <Link2 size={16} />
                <span>连接</span>
              </button>
              {connected ? (
                <button
                  type="button"
                  className="ct-icon-button"
                  disabled={busyAction !== null}
                  onClick={() => onControl({ action: 'deviceDisconnect' })}
                  title="断开"
                >
                  <Unlink size={17} />
                </button>
              ) : null}
            </div>
            <p className="ct-step-meta">
              {device?.message ?? '尚未扫描'}
              {device?.recordingsAvailable != null
                ? ` · 设备录音 ${device.recordingsAvailable} 条`
                : ''}
            </p>
          </div>
        </div>

        <div className={`ct-step ${step >= 2 ? 'active' : ''} ${hasSyncedAudio ? 'done' : ''}`}>
          <span className="ct-step-n">2</span>
          <div className="ct-step-body">
            <strong>同步设备短录</strong>
            <p>
              必须先在<strong>板子上录完一段</strong>，设备里才有录音列表。
              然后点同步，把音频拉到电脑。
            </p>
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={busyAction !== null || !connected}
                onClick={() => onControl({ action: 'deviceSyncRecordings', title: draftTitle })}
                title={!connected ? '请先连接板子' : '同步设备录音'}
              >
                <HardDrive size={16} />
                <span>同步短录</span>
              </button>
            </div>
            {!connected ? (
              <p className="ct-step-warn">未连接板子，无法同步</p>
            ) : hasSyncedAudio ? (
              <p className="ct-step-ok">
                已同步
                {selectedSession?.audioBytes
                  ? ` · ${(selectedSession.audioBytes / 1024).toFixed(0)} KB`
                  : ''}
                {selectedSession?.source === 'deviceFlash' ? ' · 来源 deviceFlash' : ''}
              </p>
            ) : (
              <p className="ct-step-meta">
                当前设备报告录音条数：{device?.recordingsAvailable ?? 0}
                {(device?.recordingsAvailable ?? 0) === 0
                  ? '（0 条 = 同步会提示没有录音，请先在板子上录）'
                  : '（有条目再点同步）'}
              </p>
            )}
          </div>
        </div>

        <div className={`ct-step ${step >= 3 ? 'active' : ''} ${selectedSession?.transcriptText ? 'done' : ''}`}>
          <span className="ct-step-n">3</span>
          <div className="ct-step-body">
            <strong>转写</strong>
            <p>有 ASR 点转写；没有就粘贴文本后点导入</p>
            <textarea
              className="ct-textarea ct-step-textarea"
              value={transcriptDraft}
              onChange={(event) => setTranscriptDraft(event.target.value)}
              spellCheck={false}
              placeholder="转写文本…"
              disabled={!hasSyncedAudio && !selectedSession}
            />
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action"
                disabled={busyAction !== null || !canTranscribe}
                onClick={() => onControl({ action: 'meetingTranscribeAudio' })}
              >
                <FileText size={16} />
                <span>转写</span>
              </button>
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={busyAction !== null || !transcriptDraft.trim() || !hasSyncedAudio}
                onClick={() => onControl({
                  action: 'meetingImportTranscript',
                  title: draftTitle,
                  transcriptText: transcriptDraft,
                })}
              >
                <Upload size={16} />
                <span>导入文本</span>
              </button>
            </div>
          </div>
        </div>

        <div className={`ct-step ${step >= 4 ? 'active' : ''} ${hasMinutes ? 'done' : ''}`}>
          <span className="ct-step-n">4</span>
          <div className="ct-step-body">
            <strong>生成纪要</strong>
            <p>根据转写生成草稿纪要</p>
            <div className="ct-button-row">
              <button
                type="button"
                className="ct-action ct-action-primary"
                disabled={busyAction !== null || !canGenerate}
                onClick={() => onControl({ action: 'meetingGenerateMinutes' })}
              >
                <FileText size={16} />
                <span>生成纪要</span>
              </button>
              <button
                type="button"
                className="ct-action"
                disabled={busyAction !== null || !canGenerate}
                onClick={() => onControl({ action: 'meetingExportMarkdown' })}
              >
                <Download size={16} />
                <span>导出 Markdown</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="ct-result-card" aria-label="纪要结果">
        <div className="ct-result-head">
          <h2>纪要结果</h2>
          {hasMinutes ? (
            <span className="ct-pill ct-pill-good">已生成</span>
          ) : (
            <span className="ct-pill">完成上面 1→4 后出现</span>
          )}
        </div>
        <textarea
          className="ct-textarea ct-minutes-output ct-result-box"
          value={minutesMarkdown || '连接板子并同步录音、转写后，这里显示纪要…'}
          readOnly
          spellCheck={false}
        />
        {hasMinutes ? (
          <div className="ct-button-row">
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null}
              onClick={() => onControl({ action: 'meetingResetSession' })}
            >
              <Trash2 size={16} />
              <span>清空会话</span>
            </button>
          </div>
        ) : null}
      </section>

      <button
        type="button"
        className="ct-advanced-toggle"
        onClick={() => setShowAdvanced((value) => !value)}
      >
        {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        <span>{showAdvanced ? '收起高级功能' : '展开高级功能（本机长会 / 演示 / 隐私）'}</span>
      </button>

      {showAdvanced ? (
        <div className="ct-advanced">
          <section className="ct-panel">
            <div className="ct-panel-title">
              <Mic size={18} />
              <span>本机长会（可选，不用板子）</span>
            </div>
            <p className="ct-meeting-hint">
              产品主路径是板子短录同步。这里仅用于主机麦克风长会或开发调试。
            </p>
            <div className="ct-meeting-grid">
              <label className="ct-field">
                <span>标题</span>
                <input
                  value={draftTitle}
                  onChange={(event) => setDraftTitle(event.target.value)}
                  spellCheck={false}
                />
              </label>
              <label className="ct-field ct-duration-field">
                <span>时长(分)</span>
                <input
                  value={draftMinutes}
                  onChange={(event) => setDraftMinutes(event.target.value.replace(/[^0-9]/g, ''))}
                  inputMode="numeric"
                />
              </label>
            </div>
            <div className="ct-button-row">
              <button type="button" className="ct-action" disabled={busyAction !== null} onClick={() => onControl({ action: 'meetingStart', title: draftTitle })}>
                <Play size={16} /><span>本机开始录音</span>
              </button>
              <button type="button" className="ct-action" disabled={busyAction !== null} onClick={() => onControl({ action: 'meetingStop', title: draftTitle, durationMs: requestedDurationMs })}>
                <Square size={16} /><span>停止</span>
              </button>
              <button type="button" className="ct-action" disabled={busyAction !== null} onClick={() => onControl({ action: 'meetingLoadDemo', title: '调试演示纪要' })}>
                <FileText size={16} /><span>调试：无板演示</span>
              </button>
            </div>
          </section>

          <section className="ct-ops-grid">
            <section className="ct-panel">
              <div className="ct-panel-title"><ListChecks size={18} /><span>检查</span></div>
              <div className="ct-check-list">
                {(oobe?.checks ?? []).map((check) => (
                  <span key={check.id} className={`ct-check ct-check-${check.status}`}>
                    <Check size={14} />{check.label}
                  </span>
                ))}
              </div>
              <button type="button" className="ct-action" disabled={busyAction !== null} onClick={() => onControl({ action: 'oobeRunChecks' })}>
                <ListChecks size={16} /><span>运行检查</span>
              </button>
            </section>
            <section className="ct-panel">
              <div className="ct-panel-title"><Shield size={18} /><span>隐私</span></div>
              <div className="ct-metric-grid">
                <InfoMetric label="音频" value={privacy ? formatBytes(privacy.audioCacheBytes) : '0'} />
                <InfoMetric label="文本" value={privacy ? formatBytes(privacy.transcriptBytes + privacy.minutesBytes) : '0'} />
                <InfoMetric label="天数" value={String(privacy?.retentionDays ?? 7)} />
              </div>
              <div className="ct-button-row">
                <button type="button" className="ct-action" disabled={busyAction !== null || !canEraseAudio} onClick={() => onControl({ action: 'privacyEraseAudio' })}>
                  <Eraser size={16} /><span>删音频</span>
                </button>
                <button type="button" className="ct-action" disabled={busyAction !== null || !canEraseTranscript} onClick={() => onControl({ action: 'privacyEraseTranscript' })}>
                  <FileText size={16} /><span>删文本</span>
                </button>
                <button type="button" className="ct-icon-button" disabled={busyAction !== null} onClick={() => onControl({ action: 'privacyEraseAll' })} title="全删">
                  <Trash2 size={17} />
                </button>
              </div>
            </section>
          </section>

          <section className="ct-panel">
            <div className="ct-panel-title"><Bluetooth size={18} /><span>蓝牙名 / 实验</span></div>
            <div className="ct-name-row">
              <input value={draftName} onChange={(event) => setDraftName(event.target.value)} spellCheck={false} />
              <button type="button" className="ct-action" disabled={busyAction !== null || Boolean(nameError)} onClick={() => onControl({ action: 'stageBleName', bleName: draftName })}>暂存</button>
              <button type="button" className="ct-action" disabled={busyAction !== null} onClick={() => onControl({ action: 'applyBleName' })}>应用</button>
              <button type="button" className="ct-action" disabled={busyAction !== null} onClick={() => onControl({ action: 'resetBleName' })}>重置</button>
            </div>
            <div className="ct-button-row" style={{ marginTop: 10 }}>
              <button type="button" className="ct-action" disabled={busyAction !== null} onClick={() => onControl({ action: 'speakerPrompt' })}><Volume2 size={16} />扬声器</button>
              <button type="button" className="ct-action" disabled={busyAction !== null} onClick={() => onControl({ action: 'wakeArm' })}>唤醒布防</button>
            </div>
          </section>
        </div>
      ) : null}

      <footer className="ct-footer">{footer}</footer>
    </main>
  );
}

function InfoMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="ct-metric">
      <span className="ct-metric-label">{label}</span>
      <strong className="ct-metric-value">{value}</strong>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
