import { useEffect, useState } from 'react';

import {
  type CompanionV1ControlAction,
  type CompanionV1ControlRequest,
  type CompanionV1Snapshot,
  applyCompanionV1ControlFixture,
  createCompanionV1Fixture,
} from '@companion-type/core';
import { CompanionDashboard } from '@companion-type/ui';
import '../../../packages/ui/src/companionUi.css';

const STORAGE_KEY = 'companion-type.mobile.fixture';

export function App() {
  const [snapshot, setSnapshot] = useState<CompanionV1Snapshot | null>(null);
  const [busyAction, setBusyAction] = useState<CompanionV1ControlAction | 'refresh' | null>('refresh');
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    setBusyAction('refresh');
    setError(null);
    try {
      setSnapshot(readSnapshot());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyAction(null);
    }
  };

  const runControl = (request: CompanionV1ControlRequest) => {
    setBusyAction(request.action);
    setError(null);
    try {
      const next = applyCompanionV1ControlFixture(snapshot ?? readSnapshot(), request);
      writeSnapshot(next);
      setSnapshot(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyAction(null);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <CompanionDashboard
      snapshot={snapshot}
      busyAction={busyAction}
      error={error}
      surface="mobile"
      onRefresh={refresh}
      onControl={runControl}
    />
  );
}

function readSnapshot(): CompanionV1Snapshot {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return createCompanionV1Fixture({ deviceId: 'mobile-fixture-companion-v1' });
  return JSON.parse(raw) as CompanionV1Snapshot;
}

function writeSnapshot(snapshot: CompanionV1Snapshot) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
}

