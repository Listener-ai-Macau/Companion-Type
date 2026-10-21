import type { CompanionV1HostSession } from './companionV1';
import { companionSessionHasFinalTranscript } from './companionV1';
import { companionReviewedUtterances, companionTranscriptReviewIsStale,
  companionTranscriptReviewRevision } from './transcriptReview';

/** A local, exact timed transcript anchor. This is not a claim that a summary
 * is semantically correct. Keep text/timing/revision so async navigation can
 * reject replaced transcripts instead of silently seeking another segment. */
export interface CompanionTranscriptSource {
  sessionId: string;
  index: number;
  text: string;
  startMs: number;
  endMs: number;
  speaker: number | null;
  reviewRevision: number | null;
}

export function companionTranscriptSources(session: CompanionV1HostSession): CompanionTranscriptSource[] {
  if (!companionSessionHasFinalTranscript(session) || companionTranscriptReviewIsStale(session)) return [];
  const revision = companionTranscriptReviewRevision(session);
  // A whole-document rewrite has no verified alignment to the ASR segments.
  if (revision !== null && session.transcriptReview?.text) return [];
  return companionReviewedUtterances(session).flatMap((row, index) =>
    row.text.trim() && Number.isSafeInteger(row.startMs) && Number.isSafeInteger(row.endMs)
      && row.startMs >= 0 && row.endMs > row.startMs
      ? [{ sessionId: session.id, index, text: row.text, startMs: row.startMs, endMs: row.endMs,
        speaker: row.speaker ?? null, reviewRevision: revision }] : []);
}

export function companionTranscriptSourceIsCurrent(session: CompanionV1HostSession,
  source: CompanionTranscriptSource): boolean {
  if (source.sessionId !== session.id || !Number.isSafeInteger(source.index) || source.index < 0) return false;
  if (!companionSessionHasFinalTranscript(session) || companionTranscriptReviewIsStale(session)) return false;
  const revision = companionTranscriptReviewRevision(session);
  if (revision !== null && session.transcriptReview?.text) return false;
  const current = session.utterances?.[source.index];
  const edit = revision !== null ? session.transcriptReview?.utteranceEdits.find((e) => e.index === source.index) : null;
  return Boolean(current && (edit?.text ?? current.text) === source.text && current.startMs === source.startMs
    && current.endMs === source.endMs && (current.speaker ?? null) === source.speaker
    && revision === source.reviewRevision && Number.isSafeInteger(current.startMs)
    && Number.isSafeInteger(current.endMs) && current.startMs >= 0 && current.endMs > current.startMs);
}

/** Match a complete item or quoted original literally to exactly one timed
 * segment. Repeated phrases, paraphrases and cross-segment quotes keep their
 * text but get no fabricated timestamp. No fuzzy/LLM matching or cloud call. */
export function companionMinutesReferencedSources(sources: readonly CompanionTranscriptSource[],
  item: string): CompanionTranscriptSource[] {
  const candidates = [item.trim(), ...Array.from(item.matchAll(/[“「『]([^”」』]+)[”」』]|"([^"\n]+)"/g),
    (match) => (match[1] ?? match[2]).trim())];
  const result = new Map<number, CompanionTranscriptSource>();
  for (const quote of new Set(candidates)) {
    if (Array.from(quote).length < 4) continue;
    const matches = sources.filter((row) => row.text.includes(quote));
    if (matches.length === 1) result.set(matches[0].index, matches[0]);
  }
  return [...result.values()].sort((a, b) => a.index - b.index);
}
