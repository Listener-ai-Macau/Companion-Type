/** Local file handoff only. Reading this help never imports, edits or deletes a calendar. */
export function CompanionCalendarUpdateHelp({ onReturn }: { onReturn?: () => void }) {
  return <details className="ct-checklist-handoff">
    <summary>已经导入过，怎样改期并避免重复？</summary>
    <p>Type 清单、保存的日历文件与普通导入副本分别保存。只导入的旧日程不会随 Type 修改；如果日历已关联同一文件，重新保存该文件后可刷新读取。</p>
    <p>关联文件若允许日历写入，在日历中修改可能直接改动该文件，但不会改 Type 清单。以后用 Type 覆盖保存同一文件前，请先确认是否需要保留日历里的修改；保存后在日历刷新并核对。</p>
    <details><summary>以后想用同一文件更新</summary>
      <ol>
        <li>先保留原导入副本。重新导出日历后，在保存结果展开“关联本地文件”，按本机日历的说明建立只读关联。</li>
        <li>核对关联日历名称、日期和提醒正确后，再隐藏专门用于旧导入的独立日历；若旧事项混在其他日历，不要整本隐藏或删除。</li>
        <li>以后在 Type 修改并保存清单，再导出并保存到同一路径，核对本次提醒；日历刷新后重新打开事项查看。下面仍保留直接修改普通导入副本的方法。</li>
      </ol>
    </details>
    <ol>
      <li><strong>先找到原日程：</strong>返回原记录，展开“查看已保存的日历副本”，对照最近保存或上一份副本的事项名称、原截止时间和提醒，在接收日历搜索。没有副本说明的旧文件，可对照自己保留的原 .ics 文件或已有日程；不用重录或重写清单。</li>
      <li><strong>对照本次设置：</strong>在当前记录点“导出到日历”，展开“对照旧日程与本次日期、提醒”。选原文件、原日程和当前事项，核对两边名称、时间和提醒；可复制原名称用于搜索，也可复制整份改期对照。这里不会自动配对或改动接收日历。</li>
      <li><strong>直接修改已有日程：</strong>确认是同一件事后，在接收日历里修改日期、时区和提醒，保存后重新打开核对。这样不需要再导入一份相同事项。</li>
      <li><strong>确实需要重新导入：</strong>先确认接收日历怎样处理重复文件，再导入新文件；它可能新增日程，不能保证替换旧条目。导入后核对新旧名称、时间和提醒，再决定保留哪条。</li>
    </ol>
    <p className="ct-step-meta">副本说明只证明 Type 成功保存过该文件，不能确认接收端是否导入。更新前未记录来源的历史文件不会被自动补成已导入。</p>
    {onReturn ? <button type="button" className="ct-action" onClick={onReturn}>返回当前记录</button> : null}
  </details>;
}
