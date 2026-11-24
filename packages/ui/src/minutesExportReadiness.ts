// Task and calendar formats turn saved minutes into actionable handoff files.
export function minutesActionExportBlock(
  format: string,
  {stale, incomplete, reviewDraft}: {stale: boolean; incomplete: boolean; reviewDraft: boolean},
): string | undefined {
  if (!['todo', 'todotxt', 'ics', 'calendar'].includes(format) && !format.startsWith('calendarreminder')) return;
  if (stale) return '原话或补充已变化。请重新整理后再导出待办或日历。';
  if (reviewDraft) return '这版纪要仍待核对。可以保存纪要草稿，但暂不能导出待办或日历。';
  if (incomplete) return '还未整理完整段录音。可以保存部分纪要，但暂不能导出整场待办或日历。';
}
