import type { CompanionV1HostSession } from './companionV1';

export interface CompanionRecordingBookmark {
  id: string;
  label: string;
  /** Board capture time for live marks; original playback time for replay marks. */
  positionMs: number;
  audioPositionMs?: number | null;
  createdAt: string;
  origin: 'boardRecording' | 'boardOffline' | 'playback';
  sourceDeviceId?: string | null;
  recordingId?: number | null;
  sourceSha256?: string | null;
  sourceRecordingKey?: { deviceUid: string; formatEpoch: string; sessionId: string } | null;
}
export interface CompanionBookmarkRequest {
  sessionId: string;
  bookmarkId: string;
  expectedRevision: number;
  action: 'addLive' | 'addAt' | 'rename' | 'delete';
  label?: string;
  positionMs?: number;
}
const deviceKey = (id: string) => id.trim().toLowerCase().replace(/[:-]/g, '');

export function companionBookmarkAudioPosition(session: CompanionV1HostSession, point: CompanionRecordingBookmark): number | null {
  if (!session.audioStored || !session.retention.audioCached || !session.audioPath
      || !Number.isSafeInteger(point.audioPositionMs) || point.audioPositionMs! < 0
      || point.audioPositionMs! > session.durationMs) return null;
  if (point.origin === 'boardOffline') {
    const a=point.sourceRecordingKey, b=session.deviceRecordingKey;
    if (!a || !b || a.deviceUid !== b.deviceUid || a.formatEpoch !== b.formatEpoch || a.sessionId !== b.sessionId
        || !point.sourceSha256 || !/^[0-9a-f]{64}$/i.test(point.sourceSha256)
        || !point.sourceDeviceId || !session.sourceDeviceId || deviceKey(point.sourceDeviceId) !== deviceKey(session.sourceDeviceId)
        || !Number.isSafeInteger(point.recordingId) || point.recordingId! <= 0) return null;
  } else if (point.sourceSha256 && point.sourceSha256 !== session.deviceSha256) return null;
  if (point.origin === 'boardRecording' && (!point.sourceSha256 || !point.sourceDeviceId || !session.sourceDeviceId
      || deviceKey(point.sourceDeviceId) !== deviceKey(session.sourceDeviceId)
      || point.recordingId == null || point.recordingId !== session.deviceRecordingId)) return null;
  return point.audioPositionMs!;
}

/** Only an actual timed utterance containing the point is a transcript link.
 * Silence/gaps/untimed ASR never get a fabricated nearest-line match. */
export function companionBookmarkUtteranceIndex(session: CompanionV1HostSession, point: CompanionRecordingBookmark): number | null {
  const position = companionBookmarkAudioPosition(session, point);
  if (position == null || !session.transcriptFinal) return null;
  const index = (session.utterances ?? []).findIndex((u) => Number.isSafeInteger(u.startMs) && Number.isSafeInteger(u.endMs)
    && u.startMs >= 0 && u.endMs > u.startMs && position >= u.startMs && position < u.endMs && u.text.trim());
  return index < 0 ? null : index;
}
