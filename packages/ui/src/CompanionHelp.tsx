import { useEffect, useRef } from 'react';

/** Reading help never starts capture, reconnects, clears data or exports logs. */
export function CompanionHelp({ onClose, onDevice, onLibrary, onDiagnostics, onRecording }: {
  onRecording?: () => void;
  onClose: () => void; onDevice: () => void; onLibrary: () => void; onDiagnostics: () => void;
}) {
  const panel = useRef<HTMLElement>(null);
  useEffect(() => { panel.current?.focus({ preventScroll: true }); }, []);
  return <section ref={panel} id="ct-use-help" className="ct-use-help" tabIndex={-1}
    aria-labelledby="ct-use-help-title" onKeyDown={event => {
      if (event.key === 'Escape') { event.stopPropagation(); onClose(); }
    }}>
    <div className="ct-use-help-heading">
      <div><h2 id="ct-use-help-title">使用帮助</h2><p>先记下一句话，再到电脑找到它。</p></div>
      <button type="button" className="ct-text-button" onClick={onClose}>关闭帮助</button>
    </div>
    <ol className="ct-use-help-steps">
      <li><strong>在宠物上开始</strong><p>回到宠物首页，默认双击左下角开始录音。睡着时先短按实体键唤醒；改过录音手势时，按已选手势操作。</p></li>
      <li><strong>停止，等设备保存</strong><p>录音时再次双击屏幕停止，等待设备显示“已保存”。保存中或异常时，先保留设备上的内容。</p></li>
      <li><strong>回到 Type 找到它</strong><p>在“设备与同步”连接并同步，等本机原音保存完成，再到“我的录音”按标题、日期或内容查找。需要时回听或转文字。</p></li>
    </ol>
    <p className="ct-use-help-key">设备“已保存”与电脑“已收齐”是两步。文字还没生成，不等于原音没有保存。</p>

    <details><summary>文字不对，或有一句话看不懂，怎么办？</summary>
      <p>文字由语音识别生成，显示“文字已生成”不代表每句话都正确。先回到这条录音，点“回听”核对原音；需要改字时，点“核对文字”，修改后保存修订。</p>
      <p>原始识别文字和原音会保留。听不清的地方先保留待核对，不替录音猜出意思；确认文字后再整理重点。没有识别出文字时，也先查看原音，再决定是否重试。</p>
      {onRecording ? <button type="button" className="ct-action" onClick={onRecording}>返回当前录音</button> : null}
    </details>
    <details><summary>双击、实体键和菜单录音，是同一件事吗？</summary>
      <p>都是开始或停止同一台 Companion 的设备录音，选一种顺手的方式即可，不需要依次操作三个入口。</p>
      <ul><li>触摸快捷：宠物首页默认双击左下角开录，录音画面双击停录。也可在设备菜单中改为左下角向右拉开录。</li>
        <li>实体键：清醒时长按约 1 秒开录或停录；睡眠后的第一次完整按压只唤醒。</li>
        <li>菜单：在宠物首页长按约 3 秒，等四格完成后松手，进入“录音 → 开始录音”。</li></ul>
      <p>临时想法可以先按当前模式录下原音，不需要先开始在线会议或配置转写服务。</p>
    </details>
    <details><summary>设备说已保存，为什么电脑里还没有？</summary>
      <p>设备先保存录音，Type 连接并同步后才有电脑副本。先看“设备与同步”的状态，再在“我的录音”查找；有搜索或筛选时，也试着清除筛选。</p>
      <p>如果提示只恢复了片段，先保留已有内容，不把它当成完整录音。没有文字时可先查看原音状态；转文字和整理是后续处理。</p>
    </details>
    <details><summary>连不上，或画面一直不动怎么办？</summary>
      <p>日常连接使用蓝牙，USB-C 用于供电。到“设备与同步”查看连接和报错；首次配对可在宠物菜单的“连接”中开启配对。</p>
      <p>睡着的宠物可先短按实体键唤醒。墨水屏会保留旧画面，单凭画面不能确认录音或保存状态。仍无响应时，保留当时提示和日志，不先清空录音或恢复默认。</p>
    </details>
    <details><summary>没有短音，或想让宠物安静一点</summary>
      <p>先看设备音量、静音、安静模式和安静时段。安静模式会减少打扰并抑制短提示音；录音时普通提示音也会受到限制。安静时段需要设备时间正确。</p>
    </details>
    <details><summary>升级或保存出错时，先做什么？</summary>
      <p>保留当前提示、原录音和原升级包，先确认是否仍在录音或处理中。不要把传输结束当成升级成功；应用确认新版本正常启动后，才算完成。</p>
      <p>使用交付方提供、与设备匹配的整包，不自行混用程序和资源文件。记录问题发生时间、刚才的操作和报错截图，再按需导出日志帮助定位。</p>
    </details>
    <div className="ct-button-row ct-use-help-links">
      <button type="button" className="ct-action" onClick={onDevice}>前往设备与同步</button>
      <button type="button" className="ct-action" onClick={onLibrary}>前往我的录音</button>
      <button type="button" className="ct-text-button" onClick={onDiagnostics}>日志与诊断在哪里</button>
    </div>
    <p className="ct-step-meta">打开帮助不会录音或更改设置。日志由你手动导出和决定是否分享，不会自动发送原音或转写。</p>
  </section>;
}
