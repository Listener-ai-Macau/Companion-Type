import type { CompanionV1ControlRequest, CompanionV1Snapshot } from './companionV1';

/** Native IPC independently checks the same ownership before changing a link. */
export function companionCanChangeOfflineRecordingLink(snapshot: CompanionV1Snapshot | null,
  request: CompanionV1ControlRequest): boolean {
  if (!snapshot || !['deviceConnect', 'deviceDisconnect'].includes(request.action)
    || !snapshot.meeting.active || snapshot.source !== 'firmware' || snapshot.device.mode !== 'windowsNative') return false;
  const active = snapshot.host.activeSessionId;
  if (!active || (request.sessionId != null && request.sessionId !== active)) return false;
  const rows = snapshot.host.sessions.filter((s) => s.status === 'recording');
  const row = rows[0];
  if (rows.length !== 1 || !row || row.id !== active || row.source !== 'boardDevice'
    || row.meetingMode !== 'offlineStore' || !row.deviceRecordingId) return false;
  const mac = (value: string | null | undefined) => {
    const normalized = value?.replace(/[:-]/g, '').toLowerCase();
    return normalized && /^[0-9a-f]{12}$/.test(normalized) ? normalized : null;
  };
  const source = mac(row.sourceDeviceId);
  return source != null && mac(snapshot.device.deviceId) === source
    && (request.deviceId == null || mac(request.deviceId) === source);
}
