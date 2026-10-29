import {useState} from 'react';

/** An address to the exact saved local file; no subscription receipt is inferred. */
export function CalendarFileLink({uri}:{uri:string}) {
  const [message,setMessage]=useState('');
  if(!uri.startsWith('file:'))return null;
  const copy=async()=>{
    try{await navigator.clipboard.writeText(uri);setMessage('已复制文件地址。请在日历的“位置”中粘贴。');}
    catch{setMessage('未能复制。可选中下面的完整地址，手动复制。');}
  };
  return <section aria-label="本地日历文件关联">
    <p><strong>经常改期？可让本机日历读取同一个文件。</strong>首次关联后，在 Type 保存到同一路径，日历刷新即可读取更新，不必重复导入。</p>
    <details>
      <summary>关联本地文件（已验证 Thunderbird 158）</summary>
      <p>适用于这台电脑上的独立日历。文件中的日程由 Type 维护；日历中设为只读，避免两边修改互相覆盖。原先导入到其他日历的副本仍然独立，不会自动移除。</p>
      <ol>
        <li>在 Thunderbird 的日历中选“添加日历（Add Calendar）→ 网络（On the Network）”，把下方地址填入“位置（Location）”，勾选“不需要凭据”，查找日历。</li>
        <li>订阅前打开“属性（Properties）”，勾选“只读（Read Only）”、保留“显示提醒”，取消“离线支持（Offline Support）”。刷新间隔可选“每分钟”，再确认并订阅。本地文件不需要日历账号。</li>
        <li>在日历列表扩大日期范围，打开日程，核对截止时间与提醒。Type 无法确认外部日历是否已完成关联。</li>
        <li>以后改期或增减事项：先在 Type 保存清单，再导出到日历，选择“保存到上次文件…”，在保存窗口确认同一路径并保存。重启 Type 后可自行选择原文件；没有保存到该文件的修改不会出现在日历里。</li>
      </ol>
      <p className="ct-step-meta">日历刷新可能有延迟，也可主动刷新。此路径只验证了上述本机应用；手机、网页日历和其他应用需另行确认支持，不会自动同步。</p>
      <label>本地日历文件地址<textarea aria-label="本地日历文件地址" readOnly value={uri} rows={3} onFocus={event=>event.currentTarget.select()} style={{display:'block',width:'100%',overflowWrap:'anywhere'}}/></label>
      <button type="button" className="ct-action" onClick={()=>void copy()}>复制关联地址</button>
      {message?<p role="status">{message}</p>:null}
      <p className="ct-step-meta">不要移动或删除关联文件。覆盖原文件前，先确认需要保留的内容；取消保存不会更新文件。一次导入仍可使用下方“打开日历文件”。</p>
      <a href="https://support.mozilla.org/en-US/kb/creating-new-calendars" target="_blank" rel="noreferrer">Thunderbird 官方添加日历说明</a>
    </details>
  </section>;
}
