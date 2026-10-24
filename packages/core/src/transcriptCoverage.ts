import { companionSessionHasFinalTranscript, type CompanionV1HostSession } from './companionV1';

/** A timeline observation, never speech detection or an accuracy verdict. */
export function companionTranscriptUnmappedTail(session: CompanionV1HostSession): {
  startMs: number; durationMs: number;
} | null {
  if (!companionSessionHasFinalTranscript(session) || session.source === 'importedTranscript'
    || session.captureIncomplete || session.recorderControlUncertain
    || ['needs_pull', 'needs_device_sync', 'needs_segments', 'needs_local_audio', 'device_control_pending'].includes(session.pendingReason ?? '')
    || ['transcribing', 'generatingMinutes'].includes(session.recovery?.stage ?? '')
    || !session.audioStored || !session.retention.audioCached || !session.audioPath
    || /^(board|device|host):\/\//i.test(session.audioPath)
    || session.audioBytes <= 0 || !Number.isFinite(session.durationMs) || session.durationMs <= 0) return null;
  const rows = (session.utterances ?? []).filter(row => row.text.trim());
  if (!rows.length || rows.some(row => !Number.isFinite(row.startMs) || !Number.isFinite(row.endMs)
    || row.startMs < 0 || row.endMs <= row.startMs || row.endMs > session.durationMs)) return null;
  const startMs = rows.reduce((end, row) => Math.max(end, row.endMs), 0);
  const durationMs = session.durationMs - startMs;
  // Keep ordinary trailing pauses quiet. A long unmapped tail is worth making
  // visible, but can still be silence; do not mark ASR failed or retry it.
  return durationMs >= 8000 && durationMs >= session.durationMs / 3 ? { startMs, durationMs } : null;
}
