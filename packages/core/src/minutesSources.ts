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
  approximateTiming?: boolean;
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
        speaker: row.speaker ?? null, approximateTiming: Boolean(row.approximateTiming), reviewRevision: revision }] : []);
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
    && Boolean(current.approximateTiming) === Boolean(source.approximateTiming)
    && revision === source.reviewRevision && Number.isSafeInteger(current.startMs)
    && Number.isSafeInteger(current.endMs) && current.startMs >= 0 && current.endMs > current.startMs);
}

// Long-meeting evidence replaces the newline between ASR segments with a
// space when displayed. Link a unique, exact cross-segment quote to its first
// segment; never bridge a missing segment or pick one of several occurrences.
function crossSegmentSource(sources: readonly CompanionTranscriptSource[], quote: string): [CompanionTranscriptSource | null, number] {
  let found: CompanionTranscriptSource | null = null;
  let matches = 0;
  for (let start = 0; start < sources.length;) {
    let end = start + 1;
    while (end < sources.length && sources[end].sessionId === sources[end - 1].sessionId
      && sources[end].reviewRevision === sources[end - 1].reviewRevision
      && sources[end].index === sources[end - 1].index + 1
      && sources[end].startMs >= sources[end - 1].startMs) end++;
    const group = sources.slice(start, end);
    const offsets: number[] = [];
    let text = '';
    for (const row of group) {
      if (offsets.length) text += ' ';
      offsets.push(text.length);
      text += row.text;
    }
    for (let position = text.indexOf(quote); position !== -1; position = text.indexOf(quote, position + 1)) {
      let index = offsets.length - 1;
      while (index > 0 && offsets[index] > position) index--;
      if (position + quote.length > offsets[index] + group[index].text.length) {
        matches++;
        if (matches > 1) return [null, matches];
        found = group[index];
      }
    }
    start = end;
  }
  return [found, matches];
}

/** Match a complete item or quoted original to exactly one timed segment, or
 * to the first of uniquely matching adjacent segments. Paraphrases, missing
 * segments and repeated quotes get no fabricated timestamp. */
export function companionMinutesReferencedSources(sources: readonly CompanionTranscriptSource[],
  item: string): CompanionTranscriptSource[] {
  const candidates = [item.trim(), ...Array.from(item.matchAll(/[“「『]([^”」』]+)[”」』]|"([^"\n]+)"/g),
    (match) => (match[1] ?? match[2]).trim())];
  const result = new Map<number, CompanionTranscriptSource>();
  for (const quote of new Set(candidates)) {
    if (Array.from(quote).length < 4) continue;
    const matches = sources.filter((row) => row.text.includes(quote));
    if (matches.length > 1) continue;
    const [firstCrossSegment, crossCount] = crossSegmentSource(sources, quote);
    if (matches.length === 1 && crossCount === 0) result.set(matches[0].index, matches[0]);
    else if (matches.length === 0 && crossCount === 1 && firstCrossSegment) {
      result.set(firstCrossSegment.index, firstCrossSegment);
    }
  }
  return [...result.values()].sort((a, b) => a.index - b.index);
}
