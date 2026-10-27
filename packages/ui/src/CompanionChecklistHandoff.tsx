/** Next steps for an actually saved checklist. No account, upload or reminder is created here. */
export function CompanionChecklistHandoff({format,onReturn}:{format:'todo'|'todotxt'|'ics';onReturn?:()=>void}) {
  return <details className="ct-checklist-handoff">
    <summary>{format==='ics'?'日历待办已保存，接下来怎么用？':'清单怎样带到手机、设置提醒？'}</summary>
    <ol>
      <li><strong>只想随手查看：</strong>短清单可返回已保存的清单，点“带到手机”，用支持文字二维码的扫码工具取用。{format==='todotxt'?'也可把导出的 .txt 清单传到手机，或放进你自己的同步文件夹，用文本应用打开。':'也可把导出的 .md 清单传到手机，用支持文本或 Markdown 的应用打开。'}“[ ]”表示未完成事项。</li>
      <li><strong>需要手机提醒：</strong>在常用的手机待办或提醒应用里新建事项，填入清单内容、日期和提醒时间。Type 保存或导出后，不会自动创建提醒。</li>
    </ol>
    <details open={format==='ics'||undefined}>
    <summary>日历待办的导入说明</summary>
    <p>先确认应用支持导入待办，再导入 .ics，逐项核对事项、日期、时区和提醒。仅支持导入普通日程，并不代表支持待办。</p>
    <p>.ics 里的待办采用 VTODO 格式；Outlook 会忽略这类内容。如果所用应用不支持，保留清单，使用手机手动设提醒即可。</p>
    <p>例如，Infomaniak 官方公布的路径是“日历 → 高级操作 → 导入”，导入的待办位于“任务”区。Type 尚未完成该应用的实际兼容验证；查看清单不需要另开服务账号。</p>
    </details>
    {onReturn?<button type="button" className="ct-action" onClick={onReturn}>返回当前记录</button>:null}
  </details>;
}
