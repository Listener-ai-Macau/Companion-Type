import { useEffect, useMemo, useState } from 'react';
import {
  Bluetooth,
  Check,
  Clock,
  Database,
  Download,
  Eraser,
  FileText,
  HardDrive,
  Link2,
  ListChecks,
  Mic,
  Play,
  RefreshCw,
  RotateCcw,
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
  'Alex opened the weekly product meeting and reviewed Companion recording status.',
  'Decision: Companion keeps the STM32 flash as a short cache while the host app owns one hour meeting recordings.',
  'Action: Maya will wire the BLE recording trigger into the Windows app before Friday.',
  'Action owner: Chen due: July 5 should validate imported transcripts and exported Markdown.',
  'Question: do we need local wake word before the first hardware beta?',
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
  const [draftTitle, setDraftTitle] = useState('Companion host workflow');
  const [draftMinutes, setDraftMinutes] = useState('60');
  const [transcriptDraft, setTranscriptDraft] = useState(DEFAULT_TRANSCRIPT);

  const selectedSession = useMemo(
    () => (snapshot ? selectedCompanionHostSession(snapshot) : null),
    [snapshot],
  );
  const policy = snapshot?.host.recordingPolicy;
  const device = snapshot?.device;
  const oobe = snapshot?.oobe;
  const privacy = snapshot?.privacy;

  useEffect(() => {
    if (snapshot) setDraftName(snapshot.bleName.stagedName);
  }, [snapshot?.bleName.stagedName]);

  useEffect(() => {
    if (!selectedSession) return;
    setDraftTitle(selectedSession.title);
    if (selectedSession.transcriptText) setTranscriptDraft(selectedSession.transcriptText);
  }, [selectedSession?.id]);

  const nameError = draftName.length > 0 && !companionBleNameIsValid(draftName)
    ? 'Use 1-29 printable ASCII bytes without quotes, semicolons, equals signs, or backslashes.'
    : null;

  const statusText = snapshot?.connected
    ? `Connected to ${snapshot.bleName.activeName}`
    : 'Fixture mode';

  const statusTone = snapshot?.connected ? 'good' : 'quiet';
  const minutes = selectedSession?.minutes;
  const canGenerate = Boolean(selectedSession?.transcriptText.trim());
  const canTranscribe = Boolean(selectedSession?.audioPath && selectedSession.status !== 'recording');
  const canEraseAudio = Boolean(selectedSession?.audioPath || selectedSession?.audioBytes);
  const canEraseTranscript = Boolean(selectedSession?.transcriptText || selectedSession?.minutes);
  const sessionDurationMs = selectedSession?.durationMs ?? 0;
  const requestedDurationMs = Math.max(1, Number.parseInt(draftMinutes, 10) || 60) * 60000;

  const footer = useMemo(() => {
    if (error) return error;
    if (nameError) return nameError;
    if (snapshot?.lastControl) {
      return `${snapshot.lastControl.action} -> ${snapshot.lastControl.characteristicUuid}`;
    }
    return surface === 'windows' ? 'Windows shell' : 'Mobile shell';
  }, [error, nameError, snapshot?.lastControl, surface]);

  return (
    <main className={`ct-shell ct-${surface}`}>
      <header className="ct-topbar">
        <div>
          <p className="ct-kicker">Companion Type</p>
          <h1>Companion</h1>
        </div>
        <button
          className="ct-icon-button"
          type="button"
          onClick={onRefresh}
          disabled={busyAction !== null}
          title="Refresh"
          aria-label="Refresh"
        >
          <RefreshCw size={18} />
        </button>
      </header>

      <section className="ct-device-strip" aria-label="Device status">
        <StatusPill tone={statusTone} label={statusText} />
        <StatusPill tone={snapshot?.bleName.pendingRestart ? 'warn' : 'quiet'} label={snapshot?.bleName.status ?? 'loading'} />
        <StatusPill tone="quiet" label={`Device cache ${policy?.deviceFlashRawCacheSeconds ?? 60}s`} />
        <StatusPill tone={device?.connected ? 'good' : 'quiet'} label={device?.message ?? 'Device idle'} />
        <StatusPill tone={oobe?.complete ? 'good' : 'warn'} label={oobe?.complete ? 'Setup ready' : 'Setup pending'} />
      </section>

      <section className="ct-status-grid">
        <StatusTile
          label="Capture"
          value={snapshot?.meeting.status ?? 'loading'}
          meta={selectedSession ? formatDuration(sessionDurationMs) : 'no session'}
        />
        <StatusTile
          label="Transcript"
          value={selectedSession?.transcriptSegments ? `${selectedSession.transcriptSegments} segments` : 'empty'}
          meta={`${snapshot?.meeting.transcriptCount ?? 0} imported`}
        />
        <StatusTile
          label="Minutes"
          value={minutes ? 'ready' : 'draft'}
          meta={minutes ? `${minutes.actionItems.length} actions` : 'not generated'}
        />
        <StatusTile
          label="Storage"
          value="host"
          meta={policy ? `${policy.oneHourChunkCount} chunks / hr` : 'policy loading'}
        />
        <StatusTile
          label="Privacy"
          value={privacy ? formatBytes(privacy.audioCacheBytes) : 'loading'}
          meta={privacy ? `${formatBytes(privacy.transcriptBytes + privacy.minutesBytes)} text` : 'cache loading'}
        />
      </section>

      <section className="ct-ops-grid">
        <section className="ct-panel" aria-label="Device">
          <div className="ct-panel-title">
            <Bluetooth size={18} />
            <span>Device</span>
          </div>
          <div className="ct-metric-grid">
            <InfoMetric label="BLE" value={device?.mode ?? 'loading'} />
            <InfoMetric label="ID" value={device?.deviceId ?? 'none'} />
            <InfoMetric label="Recordings" value={String(device?.recordingsAvailable ?? 0)} />
          </div>
          <div className="ct-button-row">
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null}
              onClick={() => onControl({ action: 'deviceScan' })}
            >
              <Search size={16} />
              <span>Scan</span>
            </button>
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null}
              onClick={() => onControl({ action: 'deviceConnect', deviceId: device?.deviceId ?? undefined })}
            >
              <Link2 size={16} />
              <span>Connect</span>
            </button>
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null}
              onClick={() => onControl({ action: 'deviceSyncRecordings', title: draftTitle })}
            >
              <HardDrive size={16} />
              <span>Sync</span>
            </button>
            <button
              type="button"
              className="ct-icon-button"
              disabled={busyAction !== null}
              onClick={() => onControl({ action: 'deviceDisconnect' })}
              title="Disconnect"
              aria-label="Disconnect"
            >
              <Unlink size={17} />
            </button>
          </div>
        </section>

        <section className="ct-panel" aria-label="Setup">
          <div className="ct-panel-title">
            <ListChecks size={18} />
            <span>Setup</span>
          </div>
          <div className="ct-check-list">
            {(oobe?.checks ?? []).map((check) => (
              <span key={check.id} className={`ct-check ct-check-${check.status}`}>
                <Check size={14} />
                {check.label}
              </span>
            ))}
          </div>
          <div className="ct-button-row">
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null}
              onClick={() => onControl({ action: 'oobeRunChecks' })}
            >
              <ListChecks size={16} />
              <span>Check</span>
            </button>
          </div>
        </section>

        <section className="ct-panel" aria-label="Retention">
          <div className="ct-panel-title">
            <Shield size={18} />
            <span>Retention</span>
          </div>
          <div className="ct-metric-grid">
            <InfoMetric label="Audio" value={privacy ? formatBytes(privacy.audioCacheBytes) : '0'} />
            <InfoMetric label="Text" value={privacy ? formatBytes(privacy.transcriptBytes + privacy.minutesBytes) : '0'} />
            <InfoMetric label="Days" value={String(privacy?.retentionDays ?? 7)} />
          </div>
          <div className="ct-button-row">
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null || !canEraseAudio}
              onClick={() => onControl({ action: 'privacyEraseAudio' })}
            >
              <Eraser size={16} />
              <span>Audio</span>
            </button>
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null || !canEraseTranscript}
              onClick={() => onControl({ action: 'privacyEraseTranscript' })}
            >
              <FileText size={16} />
              <span>Text</span>
            </button>
            <button
              type="button"
              className="ct-icon-button"
              disabled={busyAction !== null}
              onClick={() => onControl({ action: 'privacyEraseAll' })}
              title="Erase all"
              aria-label="Erase all"
            >
              <Trash2 size={17} />
            </button>
          </div>
        </section>
      </section>

      <section className="ct-panel" aria-label="Meeting workflow">
        <div className="ct-panel-title">
          <Mic size={18} />
          <span>Meeting</span>
        </div>
        <div className="ct-meeting-grid">
          <label className="ct-field">
            <span>Title</span>
            <input
              value={draftTitle}
              onChange={(event) => setDraftTitle(event.target.value)}
              spellCheck={false}
            />
          </label>
          <label className="ct-field ct-duration-field">
            <span>Minutes</span>
            <input
              value={draftMinutes}
              onChange={(event) => setDraftMinutes(event.target.value.replace(/[^0-9]/g, ''))}
              inputMode="numeric"
            />
          </label>
          <div className="ct-button-row ct-meeting-actions">
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null}
              onClick={() => onControl({ action: 'meetingStart', title: draftTitle })}
            >
              <Play size={16} />
              <span>Start</span>
            </button>
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null}
              onClick={() => onControl({ action: 'meetingStop', title: draftTitle, durationMs: requestedDurationMs })}
            >
              <Square size={16} />
              <span>Stop</span>
            </button>
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null}
              onClick={() => onControl({ action: 'meetingFinalize' })}
            >
              <Check size={16} />
              <span>Done</span>
            </button>
          </div>
        </div>
        <div className="ct-policy-row">
          <span><Clock size={14} /> {policy ? `${Math.round(policy.targetMeetingSeconds / 60)} min` : 'loading'}</span>
          <span><Database size={14} /> {policy ? `${formatBytes(policy.maxAsrUploadBytes)} ASR chunk` : 'loading'}</span>
          <span><HardDrive size={14} /> {policy ? `${formatBytes(policy.oneHourRawPcmBytes)} raw/hr` : 'loading'}</span>
        </div>
      </section>

      <section className="ct-workflow-grid">
        <section className="ct-panel" aria-label="Transcript">
          <div className="ct-panel-title">
            <FileText size={18} />
            <span>Transcript</span>
          </div>
          <textarea
            className="ct-textarea"
            value={transcriptDraft}
            onChange={(event) => setTranscriptDraft(event.target.value)}
            spellCheck={false}
          />
          <div className="ct-button-row">
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null || !canTranscribe}
              onClick={() => onControl({ action: 'meetingTranscribeAudio' })}
            >
              <FileText size={16} />
              <span>Transcribe</span>
            </button>
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null || !transcriptDraft.trim()}
              onClick={() => onControl({ action: 'meetingImportTranscript', title: draftTitle, transcriptText: transcriptDraft })}
            >
              <Upload size={16} />
              <span>Import</span>
            </button>
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null || !canGenerate}
              onClick={() => onControl({ action: 'meetingGenerateMinutes' })}
            >
              <FileText size={16} />
              <span>Minutes</span>
            </button>
          </div>
        </section>

        <section className="ct-panel" aria-label="Minutes">
          <div className="ct-panel-title">
            <Download size={18} />
            <span>Export</span>
          </div>
          <textarea
            className="ct-textarea ct-minutes-output"
            value={selectedSession?.exportMarkdown || minutes?.markdown || selectedSession?.transcriptPreview || ''}
            readOnly
            spellCheck={false}
          />
          <div className="ct-button-row">
            <button
              type="button"
              className="ct-action"
              disabled={busyAction !== null || !canGenerate}
              onClick={() => onControl({ action: 'meetingExportMarkdown' })}
            >
              <Download size={16} />
              <span>Markdown</span>
            </button>
            <button
              type="button"
              className="ct-icon-button"
              disabled={busyAction !== null}
              onClick={() => onControl({ action: 'meetingResetSession' })}
              title="Reset session"
              aria-label="Reset session"
            >
              <Trash2 size={17} />
            </button>
          </div>
        </section>
      </section>

      <section className="ct-panel" aria-label="BLE name">
        <div className="ct-panel-title">
          <Bluetooth size={18} />
          <span>BLE name</span>
        </div>
        <div className="ct-name-row">
          <input
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
            maxLength={29}
            spellCheck={false}
            aria-label="BLE name"
          />
          <button
            type="button"
            className="ct-action"
            disabled={Boolean(nameError) || busyAction !== null}
            onClick={() => onControl({ action: 'stageBleName', bleName: draftName })}
          >
            <Bluetooth size={16} />
            <span>Stage</span>
          </button>
          <button
            type="button"
            className="ct-action"
            disabled={busyAction !== null}
            onClick={() => onControl({ action: 'applyBleName' })}
          >
            <Check size={16} />
            <span>Apply</span>
          </button>
          <button
            type="button"
            className="ct-icon-button"
            disabled={busyAction !== null}
            onClick={() => onControl({ action: 'resetBleName' })}
            title="Reset"
            aria-label="Reset BLE name"
          >
            <RotateCcw size={17} />
          </button>
        </div>
      </section>

      <section className="ct-control-grid">
        <ControlGroup
          title="Speaker"
          actions={[
            ['speakerPrompt', 'Prompt', <Volume2 size={16} key="volume" />],
            ['speakerStop', 'Stop', <Square size={16} key="stop" />],
          ]}
          busyAction={busyAction}
          onControl={onControl}
        />
        <ControlGroup
          title="Wake"
          actions={[
            ['wakeArm', 'Arm', <Mic size={16} key="mic" />],
            ['wakeDisable', 'Off', <Square size={16} key="off" />],
            ['wakeTestDetect', 'Test', <Check size={16} key="test" />],
          ]}
          busyAction={busyAction}
          onControl={onControl}
        />
      </section>

      {snapshot?.host.sessions.length ? (
        <section className="ct-panel" aria-label="Sessions">
          <div className="ct-panel-title">
            <FileText size={18} />
            <span>Sessions</span>
          </div>
          <div className="ct-session-list">
            {snapshot.host.sessions.slice(0, 5).map((session) => (
              <div key={session.id} className="ct-session-row">
                <span>{session.title}</span>
                <small>{session.status} / {formatDuration(session.durationMs)} / {formatBytes(session.audioBytes)}</small>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <footer className={error ? 'ct-footer ct-error' : 'ct-footer'}>{footer}</footer>
    </main>
  );
}

function StatusPill({ label, tone }: { label: string; tone: 'good' | 'warn' | 'quiet' }) {
  return <span className={`ct-pill ct-pill-${tone}`}>{label}</span>;
}

function StatusTile({ label, value, meta }: { label: string; value: string; meta: string }) {
  return (
    <article className="ct-tile">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{meta}</small>
    </article>
  );
}

function ControlGroup({
  title,
  actions,
  busyAction,
  onControl,
}: {
  title: string;
  actions: Array<[CompanionV1ControlAction, string, React.ReactNode]>;
  busyAction: CompanionV1ControlAction | 'refresh' | null;
  onControl: (request: CompanionV1ControlRequest) => void;
}) {
  return (
    <section className="ct-panel">
      <div className="ct-panel-title">
        <span>{title}</span>
      </div>
      <div className="ct-button-row">
        {actions.map(([action, label, icon]) => (
          <button
            key={action}
            type="button"
            className="ct-action"
            disabled={busyAction !== null}
            onClick={() => onControl({ action })}
          >
            {icon}
            <span>{label}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function InfoMetric({ label, value }: { label: string; value: string }) {
  return (
    <span className="ct-metric">
      <small>{label}</small>
      <strong>{value}</strong>
    </span>
  );
}

function formatDuration(durationMs: number): string {
  const totalSeconds = Math.max(0, Math.round(durationMs / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function formatBytes(bytes: number): string {
  const mib = bytes / 1024 / 1024;
  return `${mib.toFixed(1)} MiB`;
}
