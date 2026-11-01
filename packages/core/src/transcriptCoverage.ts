import { companionSessionHasFinalTranscript, type CompanionV1HostSession } from './companionV1';
import { companionReviewedUtterances } from './transcriptReview';

export type CompanionTranscriptUnmappedEdge = {
  edge: 'start' | 'end'; startMs: number; durationMs: number;
};

/** Timeline observations only: a gap may be silence, never an accuracy verdict. */
export function companionTranscriptUnmappedEdges(session: CompanionV1HostSession): CompanionTranscriptUnmappedEdge[] {
  if (!companionSessionHasFinalTranscript(session) || session.source === 'importedTranscript'
    || session.captureIncomplete || session.recorderControlUncertain
    || ['needs_pull', 'needs_device_sync', 'needs_segments', 'needs_local_audio', 'device_control_pending'].includes(session.pendingReason ?? '')
    || ['transcribing', 'generatingMinutes'].includes(session.recovery?.stage ?? '')
    || !session.audioStored || !session.retention.audioCached || !session.audioPath
    || /^(board|device|host):\/\//i.test(session.audioPath)
    || session.audioBytes <= 0 || !Number.isFinite(session.durationMs) || session.durationMs <= 0) return [];
  const rows = companionReviewedUtterances(session).filter(row => row.text.trim());
  if (!rows.length || rows.some(row => !Number.isFinite(row.startMs) || !Number.isFinite(row.endMs)
    || row.startMs < 0 || row.endMs <= row.startMs || row.endMs > session.durationMs)) return [];
  const firstMs = rows.reduce((start, row) => Math.min(start, row.startMs), session.durationMs);
  const lastMs = rows.reduce((end, row) => Math.max(end, row.endMs), 0);
  const result: CompanionTranscriptUnmappedEdge[] = [];
  const significant = (durationMs: number) => durationMs >= 8000 && durationMs >= session.durationMs / 3;
  // Keep ordinary pauses quiet. Never infer speech from elapsed audio time,
  // alter the provider result, or start another paid request from this cue.
  if (significant(firstMs)) result.push({ edge: 'start', startMs: 0, durationMs: firstMs });
  const tailMs = session.durationMs - lastMs;
  if (significant(tailMs)) result.push({ edge: 'end', startMs: lastMs, durationMs: tailMs });
  return result;
}

/** Retain the established tail-only API and thresholds for existing callers. */
export function companionTranscriptUnmappedTail(session: CompanionV1HostSession): {
  startMs: number; durationMs: number;
} | null {
  const tail = companionTranscriptUnmappedEdges(session).find(row => row.edge === 'end');
  return tail ? { startMs: tail.startMs, durationMs: tail.durationMs } : null;
}
