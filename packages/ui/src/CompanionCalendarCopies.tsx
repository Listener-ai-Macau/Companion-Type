import { useEffect, useRef, useState } from 'react';
import { readableCalendarTime } from './calendarTime';
import type { CompanionCalendarCopy, CompanionV1HostSession, CompanionV1MeetingMode } from '@companion-type/core';

const reminderLabel = (minutes: number | null) => minutes === null ? '未附提醒' : minutes === 0 ? '在已确认的时刻' : minutes === 60 ? '提前1小时' : `提前${minutes}分钟`;
function savedTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '保存时间待核对' : date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
}

export function calendarCopyDetailsText(copy: CompanionCalendarCopy): string {
  return [`日历文件：${copy.fileName}`, ...copy.entries.map(entry =>
    `${entry.title}\n时间：${readableCalendarTime(entry.deadline)}\n提醒：${reminderLabel(entry.reminderMinutes)}`),
    '这是本机保存文件时的内容；请在接收日历搜索并核对是否已导入。'].join('\n\n');
}

export function CompanionCalendarCopies({ session, mode, markdown }: {
  session: CompanionV1HostSession; mode: CompanionV1MeetingMode; markdown: string;
}) {
  const copies = (session.calendarCopies ?? []).filter(copy => copy.meetingMode === mode);
  const [copyState, setCopyState] = useState<{ index: number; entryIndex: number | null; message: string; text?: string } | null>(null);
  const copyRequest = useRef(0);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  if (!copies.length) return null;
  const changed = copies[0].sourceMarkdown !== markdown || copies[0].sourceTitle !== session.title;
  const copyText = async (copy: CompanionCalendarCopy, index: number, entryIndex: number | null) => {
    const request = ++copyRequest.current;
    const text = entryIndex === null ? calendarCopyDetailsText(copy) : copy.entries[entryIndex].title;
    setCopyState(null);
    try {
      await navigator.clipboard.writeText(text);
      if (alive.current && request === copyRequest.current) setCopyState({ index, entryIndex,
        message: entryIndex === null ? '已复制整份副本信息，可用于对照。' : '已复制日程名称，可粘贴到接收日历的搜索框。' });
    } catch {
      if (alive.current && request === copyRequest.current) setCopyState({ index, entryIndex,
        message: entryIndex === null ? '无法直接复制，可选中下面的副本信息复制。' : '无法直接复制，可选中下面的日程名称复制。', text });
    }
  };
  const feedback = (index: number, entryIndex: number | null) => copyState?.index === index && copyState.entryIndex === entryIndex ?
    <div role="status"><p>{copyState.message}</p>{copyState.text ?
      <textarea readOnly aria-label={entryIndex === null ? '日历副本信息' : '日程名称查找文字'} value={copyState.text}
        onFocus={event => event.currentTarget.select()} style={{ width: '100%', minHeight: entryIndex === null ? 110 : 70, boxSizing: 'border-box' }} /> : null}</div> : null;
  return <div className="ct-calendar-copies">
    {changed ? <p className="ct-step-warn">清单已修改，接收日历不会自动更新。可先查看上次保存的副本，找到原日程再核对。</p> : null}
    <details>
      <summary>查看已保存的日历副本</summary>
      <p className="ct-step-meta">这里只记录本机成功保存的文件，无法确认是否已导入日历。若已导入旧文件，重新导入是否替换取决于接收日历，也可能新增；可按下面的原名称找到日程后修改。</p>
      <p className="ct-step-meta">找回原日程时，复制对应名称，再粘贴到接收日历的搜索框。</p>
      {copies.map((copy, index) => <section key={`${copy.fileSha256}:${copy.savedAt}`} aria-label={index === 0 ? '最近保存的日历文件' : '上一份日历文件'}>
        <p><strong>{index === 0 ? '最近保存' : '上一份副本'}</strong>：{copy.fileName}<br /><time dateTime={copy.savedAt}>{savedTime(copy.savedAt)}</time></p>
        <ul>{copy.entries.map((entry, n) => <li key={`${entry.uid}:${n}`}>
          <strong>{entry.title}</strong><br />提醒：{reminderLabel(entry.reminderMinutes)}
          <br /><button type="button" className="ct-text-button" aria-label={`复制日程名称：${entry.title}`}
            onClick={() => void copyText(copy, index, n)}>复制日程名称</button>
          {feedback(index, n)}
        </li>)}</ul>
        <button type="button" className="ct-action" onClick={() => void copyText(copy, index, null)}>复制整份副本信息</button>
        {feedback(index, null)}
      </section>)}
    </details>
  </div>;
}
