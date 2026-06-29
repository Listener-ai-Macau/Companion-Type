import { useEffect, useMemo, useState } from 'react';
import {
  Bluetooth,
  Check,
  Mic,
  Play,
  RefreshCw,
  RotateCcw,
  Square,
  Volume2,
} from 'lucide-react';

import {
  type CompanionV1ControlAction,
  type CompanionV1ControlRequest,
  type CompanionV1Snapshot,
  companionBleNameIsValid,
} from '@companion-type/core';

export interface CompanionDashboardProps {
  snapshot: CompanionV1Snapshot | null;
  busyAction: CompanionV1ControlAction | 'refresh' | null;
  error: string | null;
  surface: 'windows' | 'mobile';
  onRefresh: () => void;
  onControl: (request: CompanionV1ControlRequest) => void;
}

export function CompanionDashboard({
  snapshot,
  busyAction,
  error,
  surface,
  onRefresh,
  onControl,
}: CompanionDashboardProps) {
  const [draftName, setDraftName] = useState('companion');

  useEffect(() => {
    if (snapshot) setDraftName(snapshot.bleName.stagedName);
  }, [snapshot?.bleName.stagedName]);

  const nameError = draftName.length > 0 && !companionBleNameIsValid(draftName)
    ? 'Use 1-29 printable ASCII bytes without quotes, semicolons, equals signs, or backslashes.'
    : null;

  const statusText = snapshot?.connected
    ? `Connected to ${snapshot.bleName.activeName}`
    : 'Fixture mode';

  const statusTone = snapshot?.connected ? 'good' : 'quiet';

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
      </section>

      <section className="ct-status-grid">
        <StatusTile
          label="Meeting"
          value={snapshot?.meeting.status ?? 'loading'}
          meta={`${snapshot?.meeting.transcriptCount ?? 0} notes`}
        />
        <StatusTile
          label="IMU"
          value={snapshot?.imu.motion ?? 'loading'}
          meta={`${snapshot?.imu.sampleHz ?? 0} Hz`}
        />
        <StatusTile
          label="Speaker"
          value={snapshot?.speaker.status ?? 'loading'}
          meta={`${snapshot?.speaker.volume ?? 0}%`}
        />
        <StatusTile
          label="Wake"
          value={snapshot?.wakeWord.armed ? 'armed' : 'idle'}
          meta={snapshot?.wakeWord.lastDetectedAt ? 'detected' : snapshot?.wakeWord.keyword ?? 'keyword'}
        />
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
          title="Meeting"
          actions={[
            ['meetingStart', 'Start', <Play size={16} key="play" />],
            ['meetingStop', 'Stop', <Square size={16} key="stop" />],
            ['meetingFinalize', 'Done', <Check size={16} key="done" />],
          ]}
          busyAction={busyAction}
          onControl={onControl}
        />
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

