import { CompanionCalendarUpdateHelp } from './CompanionCalendarUpdateHelp';
import { useEffect, useRef } from 'react';
import { CompanionLicenses } from './CompanionLicenses';
import { CompanionChecklistHandoff } from './CompanionChecklistHandoff';

/** Reading help never starts capture, reconnects, clears data or exports logs. */
export function CompanionHelp({ onClose, onDevice, onLibrary, onDiagnostics, onRecording, onReadLicenses, onPrivacy }: {
  onPrivacy?: () => void;
  onReadLicenses?: () => Promise<string>;
  onRecording?: () => void;
  onClose: () => void; onDevice: () => void; onLibrary: () => void; onDiagnostics: () => void;
}) {
  const panel = useRef<HTMLElement>(null);
  useEffect(() => { panel.current?.focus({ preventScroll: true }); }, []);
  const reveal=(id:string)=>{
    const target=panel.current?.querySelector<HTMLElement>(`#${id}`);if(!target)return;
    const detail=target.tagName==='DETAILS'?target as HTMLDetailsElement:target.querySelector('details');
    if(detail)detail.open=true;
    const focus=detail?.querySelector('summary')??target;
    focus.focus({preventScroll:true});
    window.requestAnimationFrame(()=>focus.scrollIntoView({block:'start',behavior:'auto'}));
  };
  const revealOpened=(target:EventTarget|null)=>{
    const summary=(target as HTMLElement|null)?.closest?.('summary');
    if(!summary||!panel.current?.contains(summary))return;
    window.requestAnimationFrame(()=>{if((summary.parentElement as HTMLDetailsElement)?.open)summary.scrollIntoView({block:'start',behavior:'auto'});});
  };
  return <section ref={panel} id="ct-use-help" className="ct-use-help" tabIndex={-1}
    aria-labelledby="ct-use-help-title" onClick={event=>revealOpened(event.target)} onKeyDown={event => {
      if (event.key === 'Escape') { event.stopPropagation(); onClose(); }
    }}>
    <div className="ct-use-help-heading">
      <div><h2 id="ct-use-help-title">使用帮助</h2><p>找回录音、带走清单，或了解宠物互动。</p></div>
      <button type="button" className="ct-action" onClick={onClose}>关闭帮助</button>
    </div>
    <nav className="ct-use-help-nav" aria-label="帮助目录">
      {([['ct-help-recording','录音与找回'],['ct-help-checklist','清单、手机与提醒'],['ct-help-calendar-update','日历改期'],['ct-help-quiet','安静互动'],['ct-help-recovery','连接与保存问题']] as const).map(([id,label])=>
        <button key={id} type="button" className="ct-action" onClick={()=>reveal(id)}>{label}</button>)}
    </nav>
    <div id="ct-help-calendar-update"><CompanionCalendarUpdateHelp onReturn={onRecording}/></div>
    <details open><summary>怎样和宠物聊天、起名字或记住一件事？</summary>      <p>先在“设备与同步”连接宠物，再展开页面最上方的“我的宠物”。目前聊天需要连接电脑，只用宠物麦克风。</p>      <p>点“开聊”后说一句话，说完点“说完了”；每句最多12秒，短回复显示在宠物屏幕底部。不会在后台持续收音。</p>      <p>在“名字、性格与记忆”查看这只宠物。“改名字与性格”可调整称呼和相处方式；“记住一句”只保存你确认的小事。需要聊天使用时再开启记忆开关，随时可以暂停、修改或删除。</p>    </details>    <h3 id="ct-help-recording" tabIndex={-1}>录音与找回</h3>    <ol className="ct-use-help-steps">
      <li><strong>在宠物上开始</strong><p>回到宠物首页，默认双击左下角开始录音。睡着时先短按实体键唤醒；改过录音手势时，按已选手势操作。</p></li>
      <li><strong>停止，等设备保存</strong><p>录音时再次双击屏幕停止，等待设备显示“已保存”。保存中或异常时，先保留设备上的内容。</p></li>
      <li><strong>回到 Type 找到它</strong><p>在“设备与同步”连接并同步，等本机原音保存完成，再到“我的记录”按标题、日期或内容查找。需要时回听或转文字。</p></li>
    </ol>
    <p className="ct-use-help-key">设备“已保存”与电脑“已收齐”是两步。文字还没生成，不等于原音没有保存。</p>

    <details><summary>文字不对，或有一句话看不懂，怎么办？</summary>
      <p>文字由语音识别生成，显示“文字已生成”不代表每句话都正确。先回到这条录音，点“回听”核对原音；需要改字时，点“核对文字”，修改后保存修订。</p>
      <p>原始识别文字和原音会保留。听不清的地方先保留待核对，不替录音猜出意思；确认文字后再整理重点。没有识别出文字时，也先查看原音，再决定是否重试。</p>
      {onRecording ? <button type="button" className="ct-action" onClick={onRecording}>返回当前记录</button> : null}
    </details>
    <details><summary>待办会提醒吗，“明天”是哪一天？</summary>
      <p>这里保存的是事项清单，不会在到期时自动通知。事项里注明时间，不代表已经设置提醒。</p>
      <p>原话里的“明天”“下周”等是录音当时的说法，请对照录音日期；Type 保留原话，不会把它们自动改成今天的相对时间。补充里的时间请对照补充时的语境，需要时可编辑成明确日期。</p>
      {onRecording ? <button type="button" className="ct-action" onClick={onRecording}>返回当前记录</button> : null}
    </details>
    <div id="ct-help-checklist"><CompanionChecklistHandoff format="todotxt" onReturn={onRecording}/></div>
    <details><summary>双击、实体键和菜单录音，是同一件事吗？</summary>
      <p>都是开始或停止同一台 Companion 的设备录音，选一种顺手的方式即可，不需要依次操作三个入口。</p>
      <ul><li>触摸快捷：宠物首页默认双击左下角开录，录音画面双击停录。也可在设备菜单中改为左下角向右拉开录。</li>
        <li>实体键：清醒时长按约 1 秒开录或停录；睡眠后的第一次完整按压只唤醒。</li>
        <li>菜单：在宠物首页长按约 3 秒，等四格完成后松手，进入“录音 → 开始录音”。</li></ul>
      <p>临时想法可以先按当前模式录下原音，不需要先开始在线会议或配置转写服务。</p>
    </details>
    <details><summary>设备说已保存，为什么电脑里还没有？</summary>
      <p>设备先保存录音，Type 连接并同步后才有电脑副本。先看“设备与同步”的状态，再在“我的记录”查找；有搜索或筛选时，也试着清除筛选。</p>
      <p>如果提示只恢复了片段，先保留已有内容，不把它当成完整录音。没有文字时可先查看原音状态；转文字和整理是后续处理。</p>
    </details>
    <details><summary>连不上，或画面一直不动怎么办？</summary>
      <p>日常连接使用蓝牙，USB-C 用于供电。到“设备与同步”查看连接和报错；首次配对可在宠物菜单的“连接”中开启配对。</p>
      <p>睡着的宠物可先短按实体键唤醒。墨水屏会保留旧画面，单凭画面不能确认录音或保存状态。仍无响应时，保留当时提示和日志，不先清空录音或恢复默认。</p>
    </details>
    <details id="ct-help-quiet"><summary>怎样安静陪着？静音、安静互动和安静时段有什么不同？</summary>
      <ul>
        <li><strong>静音：</strong>关闭提示音，仍保留表情和轻触回应。宠物首页右上往下拉可进入快捷调节，也可在“设备 → 音量与静音”设置。</li>
        <li><strong>安静互动：</strong>到“宠物 → 互动程度”选择“安静·无声轻回应”。它会减少主动变化、抑制短音，轻摸时仍会回应，适合想让它安静陪着的时候。</li>
        <li><strong>安静时段：</strong>到“设备 → 时间与安静”设置夜间抑制短音的时段，需要设备时间正确。目前可选 23:00—07:00、22:00—08:00 或关闭，尚不支持在这里自定白天工作时间。</li>
      </ul>
      <p>这三项分别控制声音、互动程度和夜间时段；其中任一项要求无声时，短音都会受限。录音时普通提示音也会受到限制。</p>
    </details>
    <details id="ct-help-recovery"><summary>保存、连接或服务报错后，怎样继续？</summary>
      <ul>
        <li><strong>磁盘空间不足：</strong>先保留当前修改，释放保存位置所在磁盘的空间，再用页面上的“重试保存”。不要为了重试清空录音。</li>
        <li><strong>没有文件权限或文件被占用：</strong>检查当前用户能否写入该位置；导出时可另选本机目录。先关闭占用目标文件的其它程序，不覆盖原音。</li>
        <li><strong>网络或服务授权失败：</strong>在“设置与工具”核对已有配置和服务状态。转文字失败不需要重新录音；不要把密钥复制到反馈里。</li>
        <li><strong>设备没有回应：</strong>先到“设备与同步”读取当前状态。开始、停止、保存或档案写入尚未确认时，不要连续重复提交；也不要先清配对或恢复默认。</li>
        <li><strong>软件包、电量或录音状态不允许操作：</strong>按该项具体提示处理。这类设备保护不等同于电脑权限不足，不要绕过保护强行安装。</li>
      </ul>
      <p>仍无法继续时，记下发生时间、刚才的操作和当前提示；可手动导出本机日志，确认后再决定是否分享。正式支持入口尚未配置，不会自动发送资料。</p>
      <button type="button" className="ct-text-button" onClick={onDiagnostics}>前往日志与诊断</button>
    </details>
    <details><summary>升级或保存出错时，先做什么？</summary>
      <p>保留当前提示、原录音和原升级包，先确认是否仍在录音或处理中。不要把传输结束当成升级成功；应用确认新版本正常启动后，才算完成。</p>
      <p>使用交付方提供、与设备匹配的整包，不自行混用程序和资源文件。记录问题发生时间、刚才的操作和报错截图，再按需导出日志帮助定位。</p>
    </details>
    <div className="ct-button-row ct-use-help-links">
      <button type="button" className="ct-action" onClick={onDevice}>前往设备与同步</button>
      <button type="button" className="ct-action" onClick={onLibrary}>前往我的记录</button>
      <button type="button" className="ct-text-button" onClick={onDiagnostics}>日志与诊断在哪里</button>
    </div>
    <details><summary>换电脑或转交宠物前，哪些资料需要分别处理？</summary>
      <ul>
        <li><strong>断开与配对：</strong>“断开”只结束连接，不会移除蓝牙配对，也不会删除资料。移除配对与清理资料是两件事。</li>
        <li><strong>恢复名称或设置：</strong>“恢复默认名称”只改蓝牙显示名称；设备“恢复默认”恢复设置。这些操作都不是录音、宠物档案与记忆的清空。</li>
        <li><strong>本机会议：</strong>Type 的本机清理处理本机会议及能确认归属的受管文件。共享文件或无法确认归属的旧缓存会保留，清理结果会列出保留项；另存、导出及其它电脑的副本要单独处理。</li>
        <li><strong>设备和宠物记忆：</strong>设备录音与“名字、性格与记忆”中的内容分别管理，不会随 Type 本机会议清理一起删除。不要把重命名、断连或恢复设置当成换主完成。</li>
        <li><strong>远端资料：</strong>本机清理不会撤回已发送给服务商的内容，也不会清除其它账户或备份。</li>
      </ul>
      <p>当前没有一键完成的换主清除。转交前需分别核对上述资料；完整历史资料擦除仍未提供。</p>
      {onPrivacy ? <button type="button" className="ct-action" onClick={onPrivacy}>查看本机隐私与清理</button> : null}
    </details>
    {onReadLicenses ? <CompanionLicenses readText={onReadLicenses} /> : null}
    <p className="ct-step-meta">打开帮助不会录音或更改设置。日志由你手动导出和决定是否分享，不会自动发送原音或转写。</p>
  </section>;
}
