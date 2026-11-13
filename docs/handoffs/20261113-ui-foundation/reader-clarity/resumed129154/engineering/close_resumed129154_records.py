from pathlib import Path
from datetime import datetime
import copy, hashlib, json, re

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113')
H=R/'docs/handoffs/20261113-ui-foundation/reader-clarity'
P=O/'public-source-full30-127';C=O/'public-level-control-full30-fixed20261113'
record=json.loads((H/'complete-product129154-software.json').read_bytes())
assert record['privateRemoteReadbackVerified'] and not record['fullAcceptancePassed']
assert record['windowsVersion']=='0.1.129' and record['androidVersion']=='0.1.154'
now=datetime.now().astimezone().isoformat(timespec='seconds')
path=R/'docs/product_backlog.json';raw=path.read_bytes();text=raw.decode();d=json.loads(text)
a=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110']
old=copy.deepcopy(a)
b=a['ownerProductClosure20261112']['ownerUiUsabilityRework20261112']['completeProductRework20261113']
state='SOFTWARE129154_INSTALLED_AND_CHECKED_FULL_PRODUCT_ACCEPTANCE_OPEN'
remaining='实卡复杂/重叠人声的识别可靠性仍开放；手机AI服务未配置；Owner整体使用感受、输入手感和正式售卖未签收。'
point='外放许可已恢复，30分钟真实公开会议播放及新录音停止/收齐/释放完成；01a7混入现场其它人声，仅本地保留，不能充当干净准确率基准。干净公开源音完成普通应用转写/电脑纪要/导出/重开；129/154两端已升级，整场议题阅读和真实重开已自验，一个统一软件包已私有完整回读匹配。'+remaining+'不要求Owner逐功能验收，不为后台工程弹窗，不重复外放/构建无变化路径。'
b.update(updatedAt=now,state=state,actualInstalledWindowsLastKnown='0.1.129',actualInstalledAndroid='0.1.154',actualWindowsCandidate='0.1.129',androidCandidateVersion='0.1.154',androidVersion='0.1.154',androidFrontendSource='cecb43a5e755405a49cb4fe01fc44fd0a0ac591b',androidBackendSource='92f53ef78a8cfd78caa60b98767dddbdf4c37583',windowsInstallation=str(R/'docs/handoffs/20261112-product-closure/windows129/installation.json'),androidClosed=str(R/'docs/handoffs/20261110-android-media-import/android154/end-session.json'),jobs=[],phoneLiveWorker=False,normalPackagesInstalled=True,softwareRevisionReceipt=str(H/'complete-product129154-software.json'),softwareRevisionArchive=record['archive'],softwareRevisionSha256=record['sha256'],privateRemoteReadbackVerified=True,uiWorkflowEngineeringPassed=True,ownerExperienceAccepted=False,asrAccuracyQualified=False,wholeCoreSaleQualified=False,ownerFullAcceptanceInvitationSent=False,inviteOwnerAcceptance=False,currentPoint=point)
b['soundOutputPolicy'].update(allowed=True,resumeRequiresExplicitOwnerPermission=False,engineeringPlaybackCompletedAt='2026-11-13T19:41:17+08:00',latestOwnCaptureClosedAt='2026-11-13T19:43:12+08:00')
b['playbackLevelRepair'].update(state='FULL30_PLAYBACK_AND_DURABLE_CAPTURE_COMPLETE_ACCURACY_SCOPE_OPEN',fullMeetingAccuracyQualified=False,fullMeetingContainsNonSourceRoomSpeech=True,fullMeetingScope=str(C/'content-scope.json'),noActiveOwnPlayback=True)
b['cleanPublicSoftwareRound'].update(firstScreenReview='Actual129 now exposes all8 exact fallback topic entries with ordinary scroll, six visible within720CSSpx; original complete wording remains expandable. Real native light/dark, muted playback, selected export and process reopen passed.',finalReaderPending=False,finalNativeReaderReceipt=str(P/'reader129-result.json'),phoneActual154ReadingReceipt=str(R/'docs/handoffs/20261110-android-media-import/android154/reading-notice-after-restart.json'),phone154ComponentPreview=str(O/'mobile-topic154-component-preview/result.json'),componentPreviewNotNativePhoneOrNewCloudGeneration=True)
b['finalTopicReader'].update(windowsSource='ad84482609f37d7780d6e1518256257d7e361f7e',frozenSource='af02c09d6b7b5773ed9d7ef76ffc0be98937bb81',androidSource='cecb43a5e755405a49cb4fe01fc44fd0a0ac591b',windowsInstallation=str(R/'docs/handoffs/20261112-product-closure/windows129/installation.json'),windowsNativeReading=str(P/'reader129-result.json'),androidBuild=str(O/'android154-local/result.json'),androidNativeReading=str(R/'docs/handoffs/20261110-android-media-import/android154/reading-notice-after-restart.json'),phoneLastObserved='154 normal update from150;5998 old files identical during install. Final5997 content files identical, only library index adds declared public library; all old libraries retained. Original library/theme restored and own display51/app/forward/jar closed. AI service unconfigured; no new phone ASR/cloud/mic/BLE run claimed.',sourceProtection=str(O/'source-protection129154.json'),completeSoftwarePackage=str(H/'complete-product129154-software.json'))
b['readerNoticeRepair'].update(authoringWindows='ad84482609f37d7780d6e1518256257d7e361f7e',frozenWindows='af02c09d6b7b5773ed9d7ef76ffc0be98937bb81',android='cecb43a5e755405a49cb4fe01fc44fd0a0ac591b',androidBuild=str(O/'android154-local/result.json'))
a.update(updatedAt=now,state=state,currentInstalledWindows='0.1.129',currentInstalledAndroid='0.1.154',plannedWindowsVersion='0.1.129',plannedAndroidVersion='0.1.154',plannedVersionsBuilt=True,lastCompleteDeliveryReceipt=str(H/'complete-product129154-software.json'),lastCompletePackageSha256=record['sha256'],lastWindowsSoftwareDeliveryReceipt=str(R/'docs/handoffs/20261112-product-closure/windows129/windows-verification.json'),lastAndroidSoftwareDeliveryReceipt=str(R/'docs/handoffs/20261110-android-media-import/android154/end-session.json'),saleQualified=False,allNonmodelComplete=False,knownJobState=point,next='向Owner一次交付129/154完整软件场景和已完成/未完成范围。下一主要工程收益仍是实卡复杂人声识别可靠性；先对照已保留源音/受影响基线定位，不重复处理含现场私语01a7或盲试已失败降噪。手机AI配置依赖保留，不复制电脑凭据或虚称手机云纪要通过。人工只体验自然完整使用感受，不派工程长测清单。')
matches=[]
for m in re.finditer(r'(?m)^([ \t]*)"activeNonmodelCompletion20261110":\s*',text):
    value,n=json.JSONDecoder().raw_decode(text[m.end():])
    if value==old: matches.append((m,n))
assert len(matches)==1
m,n=matches[0]
out=text[:m.end()]+json.dumps(a,ensure_ascii=False,indent=2).replace('\n','\r\n'+m.group(1))+text[m.end()+n:]
assert path.read_bytes()==raw
path.write_bytes(out.encode())

log=R/'docs/development_log.md';raw=log.read_bytes();text=raw.decode();marker='<!-- ui116-resumed-public20261113 -->'
assert text.count(marker)==1 and '最终129/154集中交付' not in text[text.index(marker):text.find('\n## ',text.index(marker))]
start=text.index(marker);following=text.find('\n## ',start);end=len(text) if following<0 else following
entry=f'''\r\n最终129/154集中交付（{now}）：实际Windows129正常升级127，249份原资料哈希一致；同源载荷/许可/来源检查和原生保存/所选导出/日期/进程重开通过。真实公开半小时结果在129的原生阅读、双主题、静音回听控件、所选导出和重开通过，模型及原文原音未重跑/改写。首轮QA错误要求8条全部塞进720CSSpx首屏，保留失败和几何证据；改为所有8条从加载即存在、普通滚动可达且前6条覆盖中段主题，不靠“显示更多”隐藏后段、无横向溢出，第三轮通过。完整措辞与依据保留，不删长内容凑截图。\r\n\r\n手机153组件预览发现长来源标题撑宽网格，修为minmax(0,1fr)/min-width0后154正常同源构建；同一真实半小时八议题、详情和完整摘要折叠在390px实际组件预览通过，明确不是实机新模型/云端生成。手机重新上线后154于20:57:03从150正常升级，5998旧文件一致；实际公开资料双主题/进程重开通过，读取服务状态AI未配置，本轮未跑手机ASR/云/麦克风/BLE。安装脚本误等待长期显示作业导致外层setup挂起；只暂停并核对自己的控制PID，让自有显示51保持，独立完成原流程后正常恢复原库/主题并关闭显示/app/forward/jar，最后精确结束该挂起父进程，未操作Owner主屏。21:04:44最终5997旧内容字节一致，仅资料库索引加入公开测试库，所有旧库仍在。全部失败/返工原件保留。\r\n\r\n本轮最终源码Windows作者ad844826、冻结af02c09d（继承已保存128兼容输入8f474547而非脏树）、Androidcec b43a5（完整cec b43a5以收据无空格哈希为准），均已私有远端读回；Android沿原生92f53ef7及完全相同150 AAR。实际127已生成的公开源音转写/电脑纪要逐项复用未变源码，未冒充129或154重跑模型。129安装和手机检查没有替其它输入手感/固件832签收，不干扰原单窗。\r\n\r\n一个软件包{record['archive']}，SHA256 {record['sha256']}，已上传原私有草稿并完整下载回读一致；没有公开发布，包内只有正常双端安装包、公开示例文字、界面及有限范围收据，没有原始音频、环境混音、模型、私人资料或密钥。完整范围收据{H/'complete-product129154-software.json'}。缓存最终核约68.65GiB、E剩余约285GiB，未另建Cargo树或自动清理。\r\n\r\n用户可用变化是整场议题先可见、逐条展开、固定阅读/文字/笔记/导出主线，重复生成说明归详情；缺失/失败/过时提醒仍保留。界面与公开软件闭环本轮已自验；{remaining} 不将5.107%单公开源音结果当通用/实卡准确率，不将含现场人声01a7送云端或远端，01a3禁读继续。当前自有构建/播放/手机作业均结束，无新工程/Owner验收弹窗。下一动作沿原UI116当前点交付这一个完整软件场景，识别质量仍回原主要待办，不用继续零碎版本替代。\r\n'''
entry=entry.replace('Androidcec b43a5（完整cec b43a5以收据无空格哈希为准）','Androidcecb43a5e755405a49cb4fe01fc44fd0a0ac591b')
assert log.read_bytes()==raw
log.write_bytes((text[:end]+entry+text[end:]).encode())

rules=R/'AGENTS.md';raw=rules.read_bytes();text=raw.decode()
first=text.split('\n\n',1)[0]
assert 'UI116正在构建Windows129 / Android152' in first
current=f'> {now} UI116本轮软件129/154均已正常升级并自验，单一软件包已私有完整回读；249份电脑旧资料与5997份手机旧内容一致，手机原库/外观已恢复、自有显示51关闭。129继承已保存128兼容输入候选，ASR/纪要/导入/SDK与实际127公开半小时路径相同；不替其它聊天输入130/固件832签收。外放30分钟及新录音停止/收齐/释放完成；01a7混入其它现场人声，仅本地保留并排除后续处理/云端/演示/远端，01a3禁读继续。实卡复杂人声识别、手机AI配置、Owner整体体验与售卖仍开放。原UI116待办和统一交付收据为接续入口；不再沿下方历史127/150或129/152在建注释执行。'
assert rules.read_bytes()==raw
rules.write_bytes((current+text[len(first):]).encode())
verify=json.loads(path.read_bytes())['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110']
assert verify['currentInstalledAndroid']=='0.1.154' and verify['lastCompletePackageSha256']==record['sha256']
print(json.dumps(dict(state=verify['state'],next=verify['next'],ownJobs=b['jobs'],phoneHoldActive=verify['phoneHoldActive']),ensure_ascii=False))
