/** Local file handoff only. Reading this help never imports, edits or deletes a calendar. */
export function CompanionCalendarUpdateHelp({ onReturn }: { onReturn?: () => void }) {
  return <details className="ct-checklist-handoff">
    <summary>改了日期，已经导入的日历怎么办？</summary>
    <p>Type 清单和接收日历分别保存。修改清单后，已经导入的日程不会自动更新。</p>
    <ol>
      <li><strong>先找到原日程：</strong>返回原记录，展开“查看已保存的日历副本”，对照最近保存或上一份副本的事项名称、原截止时间和提醒，在接收日历搜索。没有副本说明的旧文件，可对照自己保留的原 .ics 文件或已有日程；不用重录或重写清单。</li>
      <li><strong>直接修改已有日程：</strong>确认是同一件事后，在接收日历里修改日期、时区和提醒，保存后重新打开核对。这样不需要再导入一份相同事项。</li>
      <li><strong>确实需要重新导入：</strong>先确认接收日历怎样处理重复文件，再导入新文件；它可能新增日程，不能保证替换旧条目。导入后核对新旧名称、时间和提醒，再决定保留哪条。</li>
    </ol>
    <p className="ct-step-meta">副本说明只证明 Type 成功保存过该文件，不能确认接收端是否导入。更新前未记录来源的历史文件不会被自动补成已导入。</p>
    {onReturn ? <button type="button" className="ct-action" onClick={onReturn}>返回当前记录</button> : null}
  </details>;
}
