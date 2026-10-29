import { useEffect, useRef, useState } from 'react';
import { readableCalendarTime } from './calendarTime';
import type { CompanionCalendarCopy, CompanionV1HostSession, CompanionV1MeetingMode } from '@companion-type/core';

const reminderLabel = (entry:CompanionCalendarCopy['entries'][number]) => entry.reminderAt ? readableCalendarTime(entry.reminderAt) : entry.reminderMinutes === null ? '未附提醒' : entry.reminderMinutes === 0 ? '在已确认的时刻' : entry.reminderMinutes === 60 ? '提前1小时' : entry.reminderMinutes === 1440 ? '提前1天' : `提前${entry.reminderMinutes}分钟`;
function savedTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '保存时间待核对' : date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

export function calendarCopyDetailsText(copy: CompanionCalendarCopy): string {
  return [`日历文件：${copy.fileName}`, ...copy.entries.map(entry =>
    `${entry.title}\n时间：${readableCalendarTime(entry.deadline)}\n提醒：${reminderLabel(entry)}`),
    '这是导出文件当时的设置，接收日历中的后续修改不会同步回来；请在接收日历核对。'].join('\n\n');
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
    <p className="ct-step-meta">最近文件记录：<time dateTime={copies[0].savedAt}>{savedTime(copies[0].savedAt)}</time> · {copies[0].entries.length}项日程，{copies[0].entries.filter(entry=>entry.reminderMinutes!==null||!!entry.reminderAt).length}项附提醒，{copies[0].entries.filter(entry=>entry.reminderMinutes===null&&!entry.reminderAt).length}项不提醒。请在接收日历核对日期、提醒和来源；文件记录不代表接收端已读取。</p>
    <details className="ct-calendar-handoff-help">
      <summary>导入后核对三步</summary>
      <ol>
        <li>在常用日历导入刚保存的文件，并确认接收日历。首次使用本地 Thunderbird 时可收起账号引导、启用本地日历，再打开原文件；本地日历不需要邮箱账号。</li>
        <li>按下方副本中的名称找到每项，逐项核对日期、时区和提醒；找不到时扩大日期范围。这里列的是文件设置，无法代替接收日历的实际结果。</li>
        <li>需要另排执行时段时，在接收日历明确修改开始与结束，保存后重新查看。Type 保留原截止记录，日历的修改不会写回清单；若日历关联了可写文件，修改可能写入该文件，以后用 Type 覆盖前请先确认是否需要保留。</li>
      </ol>
    </details>
    {changed ? <p className="ct-step-warn">清单已有修改，日历文件尚需重新保存。只导入的旧副本不会更新；已关联同一文件的日历，可在保存后刷新读取。</p> : null}
    <details>
      <summary>查看已保存的日历副本：逐项日期和提醒</summary>
      <p className="ct-step-meta">这是导出文件当时的设置，接收日历中的后续修改不会同步回来。这里只记录本机成功保存的文件，无法确认是否已导入日历。若已导入旧文件，重新导入是否替换取决于接收日历，也可能新增；可按下面的原名称找到日程后修改。</p>
      <p className="ct-step-meta">每种整理方式只保留最近和上一份内容不同的副本说明；重复保存相同内容会更新文件名与保存时间。这里不保存全部历史版本，也不会删除你导出的原文件。</p>
      <p className="ct-step-meta">改期时，进入“导出到日历”，展开“对照旧日程与本次日期、提醒”，可把原文件与当前设置放在一起核对。</p>
      <p className="ct-step-meta">找回原日程时，复制对应名称，再粘贴到接收日历的搜索框；找不到时，请扩大接收日历的日期范围。</p>
      {copies.map((copy, index) => <section key={`${copy.fileSha256}:${copy.savedAt}`} aria-label={index === 0 ? '最近保存的日历文件' : '上一份日历文件'}>
        <p><strong>{index === 0 ? '最近保存' : '上一份副本'}</strong>：{copy.fileName}<br /><time dateTime={copy.savedAt}>{savedTime(copy.savedAt)}</time></p>
        <ul>{copy.entries.map((entry, n) => <li key={`${entry.uid}:${n}`}>
          <strong>{entry.title}</strong><br />时间：{readableCalendarTime(entry.deadline)}<br />提醒：{reminderLabel(entry)}
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
