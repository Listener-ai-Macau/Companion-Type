import { useEffect, useState } from 'react';

import {
  type CompanionV1ControlAction,
  type CompanionV1ControlRequest,
  type CompanionV1Snapshot,
} from '@companion-type/core';
import { CompanionDashboard } from '@companion-type/ui';
import '../../../packages/ui/src/companionUi.css';

import { applyCompanionControl, getCompanionSnapshot } from './companionClient';

export function App() {
  const [snapshot, setSnapshot] = useState<CompanionV1Snapshot | null>(null);
  const [busyAction, setBusyAction] = useState<CompanionV1ControlAction | 'refresh' | null>('refresh');
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setBusyAction('refresh');
    setError(null);
    try {
      setSnapshot(await getCompanionSnapshot());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyAction(null);
    }
  };

  const runControl = async (request: CompanionV1ControlRequest) => {
    setBusyAction(request.action);
    setError(null);
    try {
      setSnapshot(await applyCompanionControl(request));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyAction(null);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <CompanionDashboard
      snapshot={snapshot}
      busyAction={busyAction}
      error={error}
      surface="windows"
      onRefresh={() => void refresh()}
      onControl={(request) => void runControl(request)}
    />
  );
}

