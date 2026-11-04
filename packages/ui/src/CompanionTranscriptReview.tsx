import {operationErrorText} from './operationFailure';
import { useEffect, useRef, useState } from 'react';
import { Pencil, RotateCcw } from 'lucide-react';
import {TranscriptFind} from './TranscriptFind';
import type {TranscriptLookup} from './transcriptMatching';
import {
  companionReviewedTranscript, companionReviewedUtterances, companionSessionHasFinalTranscript,
  companionTranscriptReviewIsStale, companionTranscriptReviewRevision, companionTranscriptSpeakerLabel,
  companionTranscriptReviewedSpeakerName,
  companionTranscriptSources, companionTranscriptSourceIsCurrent, type CompanionTranscriptSource,
  type CompanionV1HostSession, type CompanionV1Snapshot, type CompanionV1UtteranceSegment,
} from '@companion-type/core';
import type { CompanionMeetingSaveRequest } from './CompanionDashboard';

type Draft = {
  sourceText: string; sourceUtterances: CompanionV1UtteranceSegment[]; revision: number;
  text: string; rows: Array<{ text: string; speakerName: string }>; names: Record<number, string>;
};
function draftFrom(session: CompanionV1HostSession): Draft {
  const stale = companionTranscriptReviewIsStale(session);
  const review = stale ? null : session.transcriptReview;
  return {
    sourceText: session.transcriptText, sourceUtterances: structuredClone(session.utterances ?? []),
    revision: session.transcriptReview?.revision ?? 0,
    text: companionReviewedTranscript(session),
    rows: companionReviewedUtterances(session).map((u, index) => ({ text: u.text,
      speakerName: review?.utteranceEdits.find((e) => e.index === index)?.speakerName ?? '' })),
    names: Object.fromEntries((review?.speakerNames ?? []).map((n) => [n.speaker, n.name])),
  };
}
function stamp(ms: number) {
  const seconds = Math.floor(ms / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

export function CompanionTranscriptReview({ session, visible, blocked, onSave, onUnsavedChange, onDraftSessionsChange,
  sourceSelection, onSeekSource, audioSeekBlocked = false, lookup, onReturnLookup }: {
  session: CompanionV1HostSession; visible: boolean; blocked: boolean;
  onSave?: (request: CompanionMeetingSaveRequest) => Promise<CompanionV1Snapshot>;
  onUnsavedChange: (unsaved: boolean) => void;
  onDraftSessionsChange?: (sessionIds: string[]) => void;
  sourceSelection?: CompanionTranscriptSource | null;
  onSeekSource?: (source: CompanionTranscriptSource) => Promise<void>;
  audioSeekBlocked?: boolean;
  lookup?:TranscriptLookup|null;
  onReturnLookup?:()=>void;
}) {
  // Keep per-meeting drafts mounted even when the user switches content tabs.
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [result, setResult] = useState<{ id: string; message: string } | null>(null);
  const [seeking, setSeeking] = useState(false);
  const [findText, setFindText] = useState('');
  const [replacementText, setReplacementText] = useState('');
  const [replacementMessage, setReplacementMessage] = useState('');
  const seekInFlight = useRef(false);
  const selectedElement = useRef<HTMLDivElement | null>(null);
  const importedText = session.source === 'importedTranscript';
  const originalLabel = importedText ? '导入原文' : '原始识别结果';
  const draft = drafts[session.id];
  useEffect(() => { setFindText(''); setReplacementText(''); setReplacementMessage(''); }, [session.id]);
  const replacementCount = !draft || !findText ? 0 : (draft.rows.length ? draft.rows.map((row) => row.text) : [draft.text])
    .reduce((count, text) => count + text.split(findText).length - 1, 0);
  const stale = companionTranscriptReviewIsStale(session);
  const revision = companionTranscriptReviewRevision(session);
  const rows = draft ? (draft.rows.length ? draft.sourceUtterances : []) : companionReviewedUtterances(session);
  const sources = companionTranscriptSources(session);
  const sourcesByIndex = new Map(sources.map((source) => [source.index, source]));
  const selection = sourceSelection && companionTranscriptSourceIsCurrent(session, sourceSelection)
    ? sourceSelection : null;
  useEffect(() => {
    if (visible && !draft && selection) {
      // An explicit source link should open a readable paragraph, rather than
      // merely expose its bottom edge below unrelated tools.
      selectedElement.current?.scrollIntoView?.({ block: 'start' });
      selectedElement.current?.focus?.({ preventScroll: true });
    }
  // Selection identity changes only on an explicit link click. Repeating the
  // same link should locate again; background snapshots must not scroll.
  }, [visible, Boolean(draft), selection]);

  async function seek(source: CompanionTranscriptSource) {
    if (!onSeekSource || blocked || audioSeekBlocked || seekInFlight.current) return;
    seekInFlight.current = true; setSeeking(true);
    try { await onSeekSource(source); }
    catch (error) { setResult({ id: source.sessionId, message: operationErrorText(error,'playback') }); }
    finally { seekInFlight.current = false; setSeeking(false); }
  }
  const speakers = [...new Set(rows.flatMap((u) => u.speaker == null ? [] : [u.speaker]))].sort((a,b) => a-b);
  const changedSource = draft && (draft.sourceText !== session.transcriptText
    || JSON.stringify(draft.sourceUtterances) !== JSON.stringify(session.utterances ?? [])
    || draft.revision !== (session.transcriptReview?.revision ?? 0));
  const canEdit = Boolean(onSave && companionSessionHasFinalTranscript(session) && !blocked && !saving
    && !['transcribing','generatingMinutes'].includes(session.recovery?.stage ?? ''));
  useEffect(() => {
    const ids = Object.keys(drafts);
    onUnsavedChange(ids.length > 0);
    onDraftSessionsChange?.(ids);
  }, [drafts, onUnsavedChange, onDraftSessionsChange]);

  function start() {
    setDrafts((previous) => ({ ...previous, [session.id]: draftFrom(session) })); setResult(null);
    setFindText(''); setReplacementText(''); setReplacementMessage('');
  }
  function cancel(id: string) {
    setDrafts((previous) => { const next = { ...previous }; delete next[id]; return next; });
  }
  function change(update: (draft: Draft) => Draft) {
    setDrafts((previous) => ({ ...previous, [session.id]: update(previous[session.id]) }));
  }
  function replaceInDraft() {
    if (!draft || !findText || !replacementCount || !canEdit || changedSource) return;
    const replace = (text: string) => text.split(findText).join(replacementText);
    const emptyAfter = (draft.rows.length ? draft.rows.map((row) => row.text) : [draft.text])
      .some((text) => !replace(text).trim());
    setReplacementMessage(`已替换 ${replacementCount} 处；${emptyAfter ? '部分文字为空，请补充后保存。' : '请保存转写修订。'}`);
    change((value) => value.rows.length
      ? { ...value, rows: value.rows.map((row) => ({ ...row, text: replace(row.text) })) }
      : { ...value, text: replace(value.text) });
  }
  async function save(restoreOriginal = false) {
    if (!onSave || saving || blocked) return;
    const id = session.id;
    const value = restoreOriginal ? draftFrom(session) : draft;
    if (!value) return;
    const transcriptReview = {
      expectedTranscriptText: value.sourceText, expectedUtterances: value.sourceUtterances,
      expectedRevision: value.revision, restoreOriginal,
      text: !restoreOriginal && value.rows.length === 0 ? value.text : undefined,
      utteranceEdits: restoreOriginal ? [] : value.rows.flatMap((row, index) => (
        row.text.trim() !== value.sourceUtterances[index].text.trim() || row.speakerName.trim()
          ? [{ index, text: row.text, speakerName: row.speakerName.trim() || undefined }] : []
      )),
      speakerNames: restoreOriginal ? [] : Object.entries(value.names).flatMap(([speaker,name]) => name.trim() ? [{ speaker: Number(speaker), name }] : []),
    };
    setSaving(id); setResult(null);
    try {
      const saved = await onSave({ sessionId: id, transcriptReview });
      if (saved.host.persistence && saved.host.persistence.status !== 'ready') {
        setResult({ id, message: '修订尚未保存到磁盘，草稿已保留。请先使用“重试保存”，不要关闭应用。' });
      } else {
        cancel(id);
        setResult({ id, message: restoreOriginal ? `已恢复${originalLabel}。已有整理结果会继续提示是否需要更新。`
          : `修订已保存在本机，${originalLabel}仍保留。相关整理结果会标记为待更新，可按需重新整理。` });
      }
    } catch (error) {
      setResult({ id, message: `${operationErrorText(error,'save')} 草稿仍保留。` });
    } finally { setSaving(null); }
  }

  return <section className="ct-transcript-document" hidden={!visible} aria-label="转写核对">
    <div className="ct-document-head"><strong>{draft ? '修正文字' : !stale && revision !== null ? '修订后的文字' : originalLabel}</strong><span>{companionReviewedTranscript(session).length} 字{!stale && revision !== null ? ' · 已修订' : ''}</span></div>
    <p className="ct-step-meta">{draft ? importedText ? '导入原文会保留。这条记录没有原录音。' : '可对照原音修正文字和说话人。回听位置与原始识别结果会保留。' : importedText ? '只读查看。这条记录来自导入文字，没有原录音。' : '只读查看识别文字，可对照原音核对。'}</p>
    {stale ? <div className="ct-step-warn" role="status">原始转写已更新，旧修订已保留供核对，没有套用到新的时间轴。请重新核对，或恢复原始转写。
      <details><summary>查看之前的修订</summary>
        {session.transcriptReview?.text ? <p>{session.transcriptReview.text}</p> : session.transcriptReview?.sourceUtterances.map((u,i) => {
          const edit = session.transcriptReview?.utteranceEdits.find((e) => e.index === i);
          const name = edit?.speakerName || session.transcriptReview?.speakerNames.find((n) => n.speaker === u.speaker)?.name;
          return <p key={i}>{stamp(u.startMs)} · {name || (u.speaker == null ? '' : `说话人${u.speaker + 1}`)} {edit?.text ?? u.text}</p>;
        })}
      </details></div> : null}
    {draft ? <div className="ct-transcript-review-editor">
      {changedSource ? <p className="ct-step-warn" role="status">后台内容已变化，当前草稿仍保留。请复制需要保留的修改，再载入最新内容核对。
        <button type="button" className="ct-text-button" disabled={Boolean(saving)} onClick={start}>载入最新内容</button></p> : null}
      <details className="ct-transcript-replace"><summary>批量替换文字</summary>
        <p className="ct-step-meta">只修改当前草稿中的匹配文字；保存后可用于重新整理，原始识别和录音保留。</p>
        <div className="ct-transcript-replace-fields">
          <label>查找<input aria-label="查找文字" value={findText} disabled={Boolean(saving)}
            onChange={(e) => { setFindText(e.target.value); setReplacementMessage(''); }} /></label>
          <label>替换为<input aria-label="替换文字" value={replacementText} disabled={Boolean(saving)}
            onChange={(e) => { setReplacementText(e.target.value); setReplacementMessage(''); }} /></label>
          <button type="button" className="ct-action" disabled={!canEdit || Boolean(changedSource) || !findText || replacementCount === 0}
            onClick={replaceInDraft}>替换 {replacementCount} 处</button>
        </div>
        {replacementMessage ? <p className="ct-step-meta" role="status">{replacementMessage}</p> : null}
      </details>
      {speakers.length ? <div className="ct-speaker-name-fields" aria-label="说话人名称">
        {speakers.map((speaker) => <label key={speaker}>说话人{speaker+1}
          <input aria-label={`说话人${speaker+1}名称`} maxLength={32} placeholder={`说话人${speaker+1}`}
            value={draft.names[speaker] ?? ''} disabled={Boolean(saving)}
            onChange={(e) => change((d) => ({ ...d, names: { ...d.names, [speaker]: e.target.value } }))} />
        </label>)}
      </div> : null}
      {rows.length ? rows.map((source,index) => <div className="ct-transcript-review-row" key={index}>
        <div className="ct-transcript-review-meta"><time>{source.approximateTiming?'约 ':''}{stamp(source.startMs)}–{stamp(source.endMs)}</time>
          {onSeekSource && sourcesByIndex.has(index) ? <button type="button" className="ct-text-button"
            aria-label={`定位第${index + 1}段原音`} disabled={blocked || audioSeekBlocked || seeking || Boolean(changedSource)}
            onClick={() => seek(sourcesByIndex.get(index)!)}>定位原音</button> : null}
          <input aria-label={`第${index+1}段说话人`} maxLength={32} value={draft.rows[index].speakerName}
            placeholder={source.speaker == null ? '此段说话人（可选）' : draft.names[source.speaker] || `说话人${source.speaker+1}`}
            disabled={Boolean(saving)} onChange={(e) => change((d) => ({ ...d, rows: d.rows.map((row,i) => i===index ? { ...row, speakerName: e.target.value } : row) }))} />
        </div>
        <textarea aria-label={`第${index+1}段转写`} value={draft.rows[index].text} spellCheck={false} disabled={Boolean(saving)}
          onChange={(e) => change((d) => ({ ...d, rows: d.rows.map((row,i) => i===index ? { ...row, text: e.target.value } : row) }))} />
      </div>) : <textarea aria-label="修订转写全文" value={draft.text} spellCheck={false} disabled={Boolean(saving)}
        onChange={(e) => change((d) => ({ ...d, text: e.target.value }))} />}
      <div className="ct-button-row">
        <button type="button" className="ct-action ct-action-primary" disabled={!canEdit || Boolean(changedSource)
          || (draft.rows.length ? draft.rows.some((row) => !row.text.trim()) : !draft.text.trim())} onClick={() => void save()}>{saving === session.id ? '正在保存…' : '保存转写修订'}</button>
        <button type="button" className="ct-action" disabled={Boolean(saving)} onClick={() => cancel(session.id)}>取消修订</button>
      </div>
    </div> : <>
      <TranscriptFind key={session.id} texts={rows.length?rows.map(row=>row.text):companionReviewedTranscript(session).split('\n')} lookup={lookup} onReturn={onReturnLookup}>{highlight=><div className="ct-transcript-lines">
        {rows.length ? rows.map((u,index) => <div className="ct-reviewed-utterance" key={index}
          data-source-selected={selection?.index === index ? 'true' : undefined}
          tabIndex={selection?.index === index ? -1 : undefined}
          ref={selection?.index === index ? selectedElement : undefined}>
          <div className="ct-transcript-review-meta"><time>{u.approximateTiming?'约 ':''}{stamp(u.startMs)}–{stamp(u.endMs)}</time><strong>{u.approximateTiming&&!companionTranscriptReviewedSpeakerName(session,index)?'本地转写分段':companionTranscriptSpeakerLabel(session,index)}</strong>
            {onSeekSource && sourcesByIndex.has(index) ? <button type="button"
              className="ct-text-button" disabled={blocked || audioSeekBlocked || seeking}
              aria-label={`定位第${index + 1}段原音`} onClick={() => seek(sourcesByIndex.get(index)!)}>定位原音</button> : null}
          </div>
          <p>{highlight(u.text,index)}</p>
        </div>) : companionReviewedTranscript(session).split('\n').map((line,i) => <p key={i}>{highlight(line,i)||'\u00a0'}</p>)}
      </div>}</TranscriptFind>
      <div className="ct-inline-edit-actions"><button type="button" className="ct-text-button" disabled={!canEdit}
        title={!onSave ? '请在桌面版修订转写' : undefined} onClick={start}><Pencil size={14} />修正文字</button>
        {revision !== null || stale ? <button type="button" className="ct-text-button" disabled={!canEdit} onClick={() => void save(true)}><RotateCcw size={14} />{importedText ? '恢复导入原文' : '恢复原始转写'}</button> : null}
      </div>
    </>}
    {result?.id === session.id ? <p className="ct-step-meta" role="status">{result.message}</p> : null}
    {session.transcriptReview ? <details className="ct-original-transcript"><summary>查看{originalLabel}</summary>
      <p className="ct-step-meta">{importedText ? '导入原文仍保留，可随时查看。' : '原音和原始识别文字仍保留，可随时查看。'}</p>
      <div className="ct-transcript-lines">{session.transcriptText.split('\n').map((line,i) => <p key={i}>{line}</p>)}</div>
    </details> : null}
  </section>;
}
