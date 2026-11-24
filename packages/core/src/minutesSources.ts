import type { CompanionMinutesActionEvidence, CompanionV1HostSession } from './companionV1';
import { companionSessionHasFinalTranscript } from './companionV1';
import { companionReviewedUtterances, companionTranscriptReviewIsStale,
  companionTranscriptReviewRevision, companionTranscriptReviewedSpeakerName, companionTranscriptSpeakerLabel } from './transcriptReview';

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
  /** Current display label, including explicit human attribution when present. */
  speakerLabel?: string;
  approximateTiming?: boolean;
  reviewRevision: number | null;
  /** Adjacent rows joined without a separator in the exact saved ASR text. */
  joinedToPrevious?: boolean;
}

function savedConcatenatedTurns(text: string, rows: ReturnType<typeof companionReviewedUtterances>): boolean {
  // Windows Volcengine groups equal consecutive IDs, including unknowns, and
  // joins their words directly. Other providers and reviewed text use different
  // layouts. Require the entire original to match before using this layout.
  if (!text.startsWith('说话人') || !rows.some(row => row.speaker != null)) return false;
  const rendered: string[] = [];
  let previous: number | null | undefined;
  for (const row of rows) {
    const speaker = row.speaker ?? null;
    if (speaker !== previous) {
      if (rendered.length) rendered.push('\n');
      rendered.push(`说话人${speaker == null ? '?' : speaker + 1}: `);
    }
    rendered.push(row.text);
    previous = speaker;
  }
  return rendered.join('') === text.replace(/\r\n/g, '\n');
}

export function companionTranscriptSources(session: CompanionV1HostSession): CompanionTranscriptSource[] {
  if (!companionSessionHasFinalTranscript(session) || companionTranscriptReviewIsStale(session)) return [];
  const revision = companionTranscriptReviewRevision(session);
  // A whole-document rewrite has no verified alignment to the ASR segments.
  if (revision !== null && session.transcriptReview?.text) return [];
  const rows = companionReviewedUtterances(session);
  const concatenated = revision === null && savedConcatenatedTurns(session.transcriptText, rows);
  return rows.flatMap((row, index) =>
    row.text.trim() && Number.isSafeInteger(row.startMs) && Number.isSafeInteger(row.endMs)
      && row.startMs >= 0 && row.endMs > row.startMs
      ? [{ sessionId: session.id, index, text: row.text, startMs: row.startMs, endMs: row.endMs,
        speaker: row.speaker ?? null,
        speakerLabel: companionTranscriptSpeakerLabel(session,index) === '未分配说话人'
          ? undefined : companionTranscriptSpeakerLabel(session,index),
        approximateTiming: Boolean(row.approximateTiming), reviewRevision: revision,
        joinedToPrevious: concatenated && index > 0 && (rows[index - 1].speaker ?? null) === (row.speaker ?? null) }] : []);
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
    && (source.speakerLabel === undefined || source.speakerLabel === companionTranscriptSpeakerLabel(session,source.index))
    && Boolean(current.approximateTiming) === Boolean(source.approximateTiming)
    && revision === source.reviewRevision && Number.isSafeInteger(current.startMs)
    && Number.isSafeInteger(current.endMs) && current.startMs >= 0 && current.endMs > current.startMs);
}

/** The native minutes input drops unreviewed diarization labels. Keep this
 * projection in sync with transcript_review::minutes_input. */
export function companionActionEvidenceInputText(session: CompanionV1HostSession): string {
  const active = companionTranscriptReviewRevision(session) !== null;
  const review = active ? session.transcriptReview : undefined;
  if (review && !review.text) {
    return companionReviewedUtterances(session).map((row, index) => {
      const label = companionTranscriptReviewedSpeakerName(session, index);
      return label ? label + ': ' + row.text : row.text;
    }).join('\n');
  }
  const text = review?.text ?? session.transcriptText;
  const recording = !!(session.utterances?.length || session.audioStored || session.audioPath)
    || ['boardDevice', 'deviceFlash', 'hostMicrophone', 'hostMeeting', 'importedAudio', 'derivedAudio'].includes(session.source);
  return recording ? text.replace(/^说话人(?:[0-9]+|[?？])[:：] ?/gm, '') : text;
}

/** Call only after verifying the transcript digest. Every cited utterance must
 * still be the same saved utterance; a partial match cannot stand in for it. */
export function companionStoredActionSources(evidence: CompanionMinutesActionEvidence,
  sources: readonly CompanionTranscriptSource[]): ReadonlyMap<string, CompanionTranscriptSource[]> {
  const byIndex = new Map(sources.map(source => [source.index, source]));
  const links = new Map<string, CompanionTranscriptSource[]>();
  for (const item of evidence.actions) {
    if (evidence.actions.filter(other => other.text === item.text).length !== 1) continue;
    const matching = item.segments.flatMap(segment => {
      const source = byIndex.get(segment.index);
      return source && source.reviewRevision === evidence.reviewRevision && !source.approximateTiming
        && source.text === segment.text && source.startMs === segment.startMs && source.endMs === segment.endMs
        ? [source] : [];
    });
    if (matching.length > 0 && matching.length === item.segments.length) links.set(item.text.trim(), matching);
  }
  return links;
}

/** Call only after verifying the adopted transcript digest. */
export function companionStoredActionQuotes(evidence: CompanionMinutesActionEvidence): ReadonlyMap<string, string[]> {
  return storedQuotes(evidence.actions);
}

export function companionStoredDecisionQuotes(evidence: CompanionMinutesActionEvidence): ReadonlyMap<string, string[]> {
  return storedQuotes(evidence.decisions ?? []);
}

function storedQuotes(items: readonly {text:string;transcriptQuotes?:string[]}[]): ReadonlyMap<string, string[]> {
  const links = new Map<string, string[]>();
  for (const item of items) {
    if (items.filter(other => other.text.trim() === item.text.trim()).length !== 1) continue;
    const quotes = item.transcriptQuotes?.filter(quote => quote.trim());
    if (quotes?.length) links.set(item.text.trim(), quotes);
  }
  return links;
}

// Long-meeting evidence replaces the newline between ASR segments with a
// space when displayed. Link a unique, exact cross-segment quote to its first
// segment; never bridge a missing segment or pick one of several occurrences.
function sourceLabel(row: CompanionTranscriptSource): string | null {
  return row.speakerLabel ?? (row.speaker == null ? null : `说话人${row.speaker + 1}`);
}
function crossSegmentSource(sources: readonly CompanionTranscriptSource[], quote: string,
  labels: 'none' | 'each' | 'turns' | 'reviewed' = 'none'): [CompanionTranscriptSource | null, number] {
  if (labels !== 'none' && !sources.some(row => sourceLabel(row) !== null)) return [null, 0];
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
    let previousLabel: string | null = null;
    for (const row of group) {
      const joined = offsets.length > 0 && row.joinedToPrevious && (labels === 'none' || labels === 'turns');
      if (offsets.length && !joined) text += ' ';
      offsets.push(text.length);
      const label=sourceLabel(row);
      if (labels === 'reviewed') {
        // Human review renders one line per source, leaving unnamed fragments
        // unlabelled. Their timestamps remain approximate when the model said so.
        if (label !== null) text += `${label}: `;
      } else if (labels !== 'none' && !joined && (labels === 'each' || offsets.length === 1
        || label === null || label !== previousLabel)) {
        text += `${label ?? '说话人?'}: `;
      }
      text += row.text;
      previousLabel = label;
    }
    for (let position = text.indexOf(quote); position !== -1; position = text.indexOf(quote, position + 1)) {
      let index = offsets.length - 1;
      while (index > 0 && offsets[index] > position) index--;
      if (labels !== 'none' || position + quote.length > offsets[index] + group[index].text.length) {
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
  const knownLabels=[...new Set(sources.map(sourceLabel).filter((label):label is string=>label !== null))];
  for (const quote of new Set(candidates)) {
    if (Array.from(quote).length < 4) continue;
    const matches = sources.filter((row) => row.text.includes(quote));
    if (matches.length > 1 || (matches[0] && matches[0].text.indexOf(quote, matches[0].text.indexOf(quote) + 1) !== -1))
      continue;
    const [firstCrossSegment, crossCount] = crossSegmentSource(sources, quote);
    // Quotes can include the verified source labels between sentences. Match
    // both current grouped turns and older per-row formatting; never strip a
    // label and accidentally link another person's identical words.
    if (/说话人(?:[1-9]\d*|[?？]):/.test(quote) || knownLabels.some(label=>quote.includes(`${label}:`))) {
      let words=quote.replace(/说话人(?:[1-9]\d*|[?？]):\s*/g, '');
      for (const label of knownLabels) words=words.split(`${label}:`).join('');
      if (Array.from(words.trim()).length < 4) continue;
      const labelled = [crossSegmentSource(sources, quote, 'each'), crossSegmentSource(sources, quote, 'turns'),
        crossSegmentSource(sources, quote, 'reviewed')] as const;
      if (crossCount > 1 || labelled.some(([, count]) => count > 1)) continue;
      const options = new Map<number, CompanionTranscriptSource>();
      for (const row of [matches[0], firstCrossSegment, ...labelled.map(([row]) => row)]) {
        if (row) options.set(row.index, row);
      }
      if (options.size === 1) { const row = options.values().next().value!; result.set(row.index, row); }
      continue;
    }
    if (matches.length === 1 && crossCount === 0) result.set(matches[0].index, matches[0]);
    else if (matches.length === 0 && crossCount === 1 && firstCrossSegment) {
      result.set(firstCrossSegment.index, firstCrossSegment);
    }
  }
  return [...result.values()].sort((a, b) => a.index - b.index);
}
