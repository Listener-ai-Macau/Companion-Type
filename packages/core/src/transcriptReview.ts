import type { CompanionV1HostSession, CompanionV1MinutesProcessing, CompanionV1UtteranceSegment } from './companionV1';

export function companionMinutesProcessingComplete(p?: CompanionV1MinutesProcessing | null): boolean {
  return !p || (p.strategy === 'chunkedSourceBacked' && p.complete
    && [p.sourceBytes, p.processedSourceBytes, p.totalChunks, p.completedChunks, p.resumedChunks].every(Number.isSafeInteger)
    && p.sourceBytes > 0 && p.processedSourceBytes === p.sourceBytes && p.totalChunks > 0
    && p.completedChunks === p.totalChunks && p.resumedChunks >= 0 && p.resumedChunks <= p.completedChunks);
}

function sameUtterances(a: CompanionV1UtteranceSegment[], b: CompanionV1UtteranceSegment[]) {
  return a.length === b.length && a.every((u, i) => u.text === b[i].text && u.startMs === b[i].startMs
    && u.endMs === b[i].endMs && (u.speaker ?? null) === (b[i].speaker ?? null));
}
export function companionTranscriptReviewIsStale(session: CompanionV1HostSession): boolean {
  const review = session.transcriptReview;
  return Boolean(review && (review.text || review.utteranceEdits.length || review.speakerNames.length)
    && (review.sourceTranscriptText !== session.transcriptText
    || !sameUtterances(review.sourceUtterances, session.utterances ?? [])));
}
export function companionTranscriptReviewRevision(session: CompanionV1HostSession): number | null {
  const review = session.transcriptReview;
  return review && !companionTranscriptReviewIsStale(session)
    && Boolean(review.text || review.utteranceEdits.length || review.speakerNames.length) ? review.revision : null;
}
export function companionMinutesMatchTranscript(session: CompanionV1HostSession, revision?: number | null): boolean {
  return !companionTranscriptReviewIsStale(session) && companionTranscriptReviewRevision(session) === (revision ?? null);
}
export function companionTranscriptSpeakerLabel(session: CompanionV1HostSession, index: number): string {
  const speaker = session.utterances?.[index]?.speaker;
  const review = companionTranscriptReviewRevision(session) !== null ? session.transcriptReview : null;
  return review?.utteranceEdits.find((e) => e.index === index)?.speakerName
    || review?.speakerNames.find((n) => n.speaker === speaker)?.name
    || (speaker == null ? '未分配说话人' : `说话人${speaker + 1}`);
}
export function companionReviewedUtterances(session: CompanionV1HostSession): CompanionV1UtteranceSegment[] {
  const edits = companionTranscriptReviewRevision(session) !== null ? session.transcriptReview?.utteranceEdits : undefined;
  return (session.utterances ?? []).map((u, index) => ({ ...u, text: edits?.find((e) => e.index === index)?.text ?? u.text }));
}
export function companionReviewedTranscript(session: CompanionV1HostSession): string {
  if (companionTranscriptReviewRevision(session) === null) return session.transcriptText;
  const review = session.transcriptReview!;
  if (review.text) return review.text;
  return companionReviewedUtterances(session).map((u, index) => {
    const label = companionTranscriptSpeakerLabel(session, index);
    return label === '未分配说话人' ? u.text : `${label}: ${u.text}`;
  }).join('\n');
}
