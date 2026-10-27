/** Next steps for an actually saved checklist. No account, upload or reminder is created here. */
export function CompanionChecklistHandoff({format,onReturn}:{format:'todo'|'todotxt'|'ics'|'calendar';onReturn?:()=>void}) {
  if(format==='calendar')return <details className="ct-checklist-handoff">
    <summary>把日程文件放进常用日历</summary>
    <p>事项和已确认的日期、时刻已写入 .ics 文件，不用重新输入。请在常用日历中选择导入文件，再核对时间、时区和提醒。</p>
    <p>这是一次导入；后续修改清单不会自动同步到日历。重复导入前请检查已有日程。</p>
    <details><summary>查看常用日历的官方导入说明</summary>
      <p><a href="https://support.google.com/calendar/answer/37118?hl=zh-Hans" target="_blank" rel="noreferrer">Google 日历</a> · <a href="https://support.microsoft.com/en-us/outlook/import-or-subscribe-to-a-calendar-in-outlook-com-or-outlook-on-the-web" target="_blank" rel="noreferrer">Outlook 网页版</a></p>
    </details>
    {onReturn?<button type="button" className="ct-action" onClick={onReturn}>返回当前记录</button>:null}
  </details>;
  return <details className="ct-checklist-handoff">
    <summary>{format==='ics'?'日历待办已保存，接下来怎么用？':'清单怎样带到手机、设置提醒？'}</summary>
    <ol>
      <li><strong>只想随手查看：</strong>短清单可返回已保存的清单，点“带到手机”，用支持文字二维码的扫码工具取用。{format==='todotxt'?'也可把导出的 .txt 清单传到手机，或放进你自己的同步文件夹，用文本应用打开。':'也可把导出的 .md 清单传到手机，用支持文本或 Markdown 的应用打开。'}“[ ]”表示未完成事项。</li>
      <li><strong>需要日历提醒：</strong>可返回清单，选择“导出到日历”，把事项和已确认时间一起导入常用日历，再核对提醒。也可按自己的习惯使用手机待办应用。</li>
    </ol>
    <details open={format==='ics'||undefined}>
    <summary>日历待办的导入说明</summary>
    <p>先确认应用支持导入待办，再导入 .ics，逐项核对事项、日期、时区和提醒。仅支持导入普通日程，并不代表支持待办。</p>
    <p>这个待办文件用于支持任务导入的应用。如果日历只接收普通日程，请回到清单选择“导出到日历”，不必重新输入事项。</p>
    <p>例如，Infomaniak 官方公布的路径是“日历 → 高级操作 → 导入”，导入的待办位于“任务”区。Type 尚未完成该应用的实际兼容验证；查看清单不需要另开服务账号。</p>
    </details>
    {onReturn?<button type="button" className="ct-action" onClick={onReturn}>返回当前记录</button>:null}
  </details>;
}
