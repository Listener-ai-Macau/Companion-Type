import { invoke } from '@tauri-apps/api/core';

import {
  type CompanionV1ControlRequest,
  type CompanionV1Snapshot,
  applyCompanionV1ControlFixture,
  createCompanionV1Fixture,
} from '@companion-type/core';

let fixtureSnapshot: CompanionV1Snapshot = createCompanionV1Fixture();

export async function getCompanionSnapshot(): Promise<CompanionV1Snapshot> {
  if (isTauriRuntime()) {
    return invoke<CompanionV1Snapshot>('get_companion_v1_snapshot');
  }
  return fixtureSnapshot;
}

export async function applyCompanionControl(
  request: CompanionV1ControlRequest,
): Promise<CompanionV1Snapshot> {
  if (isTauriRuntime()) {
    return invoke<CompanionV1Snapshot>('apply_companion_v1_control', { request });
  }
  fixtureSnapshot = applyCompanionV1ControlFixture(fixtureSnapshot, request);
  return fixtureSnapshot;
}

function isTauriRuntime(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

