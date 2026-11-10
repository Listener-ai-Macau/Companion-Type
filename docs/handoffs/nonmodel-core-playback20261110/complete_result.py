from pathlib import Path
from datetime import datetime
import json,os,hashlib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/nonmodel-playback20261110');now=datetime.now().astimezone().isoformat(timespec='seconds')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
end=read(C/'android121/end-session.json');assert end['expectedLibraryIndexChangeOnly'] and end['ownedAppAndVirtualDisplayClosed']
checks={key:read(C/name) for key,name in {'playbackCorrection':'android120/playback-ui-result.json','interruption':'android120/interruption-result.json','settings':'android121/settings-ui-result.json','backupRestorePurge':'android121/backup-restore-purge-result.json','finalUi':'android121/final-ui-result.json','installation':'android121/installation.json','packageBackup':'android121/remote-candidate-backup.json','usbAwake':'android121/usb-keep-awake.json'}.items()}
assert all(checks[key]['state']=='PASSED' for key in ['playbackCorrection','settings','backupRestorePurge','finalUi'])
ci_path=next(p for p in (P/'android121-ci').rglob('result.json') if p.parent.name=='core-ui-output');ci=read(ci_path);assert ci['sourceCommit']=='76da5cf6ec359f49aa36b618d4710159c9431569' and ci['state']=='GROUPED_MEETING_UI_SOURCE_CONTRACTS_PASSED'
(C/'source-contracts-settings121.json').write_text(json.dumps(ci,indent=2)+'\n')
logs=C/'checks';logs.mkdir(exist_ok=True)
for f in ci_path.parent.glob('*.log'):
 raw=f.read_bytes();(logs/('settings121-'+f.name+'.json')).write_text(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'utf8':raw.decode('utf8',errors='replace')},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
failures={'at':now,'productRegressionsObservedInPassedScope':False,'retainedToolFindings':[{'finding':'First restore selector included an ellipsis absent from actual button text.','decision':'Corrected selector to actual UI; no product/source change.'},{'finding':'Session-long main-screen fingerprint changed independently when phone locked.','decision':'Guard owned-app restart against its actual per-operation main fingerprint and reject own package on main display; never manipulate owner main display.'},{'finding':'Immediate pidof after app restart returned empty before process launch completed.','decision':'Preserved failed attempt and checkpoint; bounded wait for actual PID, then resumed the same interrupted state; actual resume passed.'},{'finding':'Initial installation adapter omitted the re import required by retained version primitive.','decision':'Fixed adapter before installation; no product change.'},{'finding':'Phone entered Dozing/secure keyguard; CDP connection and file selection did not complete.','decision':'No locked-screen completion claim. After explicit unlock reply, actual picker selection/restore passed. Owner then explicitly requested USB keep-awake; original0 changed to2, actual USB powered/StayOn true verified.'},{'finding':'DocumentsUI accessibility click acknowledgement was not proof that file selection completed.','decision':'Used input at observed owned-display bounds after unlock and waited for durable library publication before continuing. Native UI, source/default playback, backup/purge and final original-library result passed.'}]}
(C/'validation-tool-findings.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
result={'at':now,'state':'ANDROID121_PLAYBACK_CORRECTION_SETTINGS_AND_PUBLIC_BACKUP_LIFECYCLE_DELIVERED','windowsVersion':'0.1.82','androidVersion':'0.1.121','sourceCommit':ci['sourceCommit'],'nativeBuildRun':42743230795,'apkSha256':checks['installation']['apkSha256'],'installed':True,'remotePackageReadbackVerified':True,'nativePhoneQualifiedForDeclaredScope':True,'phoneResults':checks,'cleanup':end,'notCovered':['Native transition between multiple decoded WAV parts was not separately triggered by this public sample.','Physical listening quality, microphone/recording-card capture, BLE, OTA and power/battery qualification were outside this local UI batch.','Model quality and complex overlapping speakers were not improved or retested.','No new customer or real buyer trial; owner acceptance remains pending.'],'saleQualified':False,'allNonmodelComplete':False,'newModelRuns':0,'boardAccessed':False,'ownerPrivateDataUploaded':False}
(C/'delivered-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for code in [120,121]:
 p=C/f'android{code}/build-result.json';d=read(p);d.update(installed=True,installationReceipt=str(C/f'android{code}/installation.json'));p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=R/'docs/product_backlog.json';raw=p.read_bytes();d=json.loads(raw);n=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104'];b=n['ownerCoreAcceptanceCandidate20261109'];a=b['activeNonmodelCompletion20261110'];a.update(updatedAt=now,state=result['state'],sourceCommit=result['sourceCommit'],candidateVersion='0.1.121',candidateApkSha256=result['apkSha256'],buildRun=42743230795,sourceAndNativePackagePassed=True,currentInstalledAndroid='0.1.121',installed=True,nativePhoneRuntimeQualified=True,nativePhoneQualifiedScope='Local public QA: original-time10s jumps, native rate/paused-state preservation, resume including owned process interruption, per-library isolation, draft correction/undo/original preservation, native preferences/settings, ordinary SAF backup/restore and exact-record lifecycle.',nativeAcceptanceRemaining=result['notCovered'],nativePhoneResults=checks,deliveryReceipt=str(C/'delivered-result.json'),allNonmodelComplete=False,saleQualified=False)
a['settingsAddition'].update(runtimeQualified=True,version='0.1.121',receipt=str(C/'android121/settings-ui-result.json'))
a['remotePackageReadbackByteIdentical']=True;a['phoneSessionClosed']=True;a['originalLibraryRestored']=True;a['usbKeepAwakeOwnerRequested']=checks['usbAwake'];a['scope'].extend([s for s in ['常用设置、原生持久化和外观跟随实际系统','未保存AI服务草稿离开保护','Owner明确要求的USB接线保持唤醒'] if s not in a['scope']])
a['next']='本批手机回听/校对/设置/备份恢复与精确清除已交付并关闭会话，不重跑未受影响流程。下一完整软件缺口沿CP27-01/import：Android普通音频/视频系统导入→原音耐久保存→本地转写/纪要→导出备份；复用现有后端与数据模型。模型训练继续后置，硬件门沿原分工。'
b['next']=a['next'];b['lastOutcome']=result['state'];b['currentCheckpoint'].update(windows='0.1.82实际安装，源e72d16ed941cb7070cc7bd6e8d21f3b830192254；本批Windows未改，既有事项跟进/复制等证据沿原收据。',phone='0.1.121实际同签名安装，源76da5cf6ec359f49aa36b618d4710159c9431569；回听/文字校对/设置/公开备份恢复及精确清除真机通过，原资料恢复、会话关闭、原1911内容文件完全一致。',windowsRemaining='当前Windows其它未验门按原待办和实际收据保留，不沿旧080/110状态重复派发。',model='原模型质量门仍开放；本批无训练/推理/新准确率结果，固定基线和复杂多人待办保留。')
for row in n['ownerCompetitiveParity20261105']['coverage']:
 if row['id']=='playback':row['current']='Windows082原倍速/续听/A-B保留；Android121实际倍速、暂停改速不误播、原音10s跳转、异常退出续播、逐资料库隔离、备份恢复和精确删除联动通过。静音跳过与多WAV边界真机未在本批验证，原完整对标和用户验收仍开。'
 if row['id']=='editing':row['current']='Windows082已有逐段/分人修订和批量替换；Android121实际公开会议29处精确替换、草稿未自动保存、撤销、保存重开、首次原文保留及旧纪要来源变化提示通过。原完整易读稿/定位和用户验收范围保留。'
 if row['id']=='premium_ui':row['current']='Android121常用设置优先，AI服务折叠；实际深色/浅色/跟随当前系统、默认倍速、续播、权限/版本状态、未保存服务草稿退出保护及进程重开保留通过。完整客户自选用途与双端一致性仍按原门验收。'
 if row['id'] in ['playback','editing','premium_ui']:row['engineering']['android121ScopedDelivery']={'version':'0.1.121','sourceCommit':result['sourceCommit'],'receipt':str(C/'delivered-result.json'),'declaredScopeNativePassed':True,'ownerAccepted':False}
temp=p.with_suffix('.playback121-complete.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');assert p.read_bytes()==raw;os.replace(temp,p)
log=R/'docs/development_log.md';text=log.read_text(encoding='utf8');marker='<!-- nonmodel-playback-settings121-delivered -->';assert marker not in text
entry=f'''{marker}
## {now} — Android121回听、文字校对和常用设置整批真机交付

沿原CP27-01/playback、editing、premium_ui和非模型优先待办，承接Owner“测试手机一直插着、尽快完成并考虑设置”，实际USB调试从MTP-only切为ADB在线后继续。Android117→120→121，同签名，最终源码76da5cf6ec359f49aa36b618d4710159c9431569、原生构建42743230795；Windows082本批未改，冻结AAR6087901、JNI和模型资源均未改。121源码检查、受影响组件与真实Gradle包通过。最终同签名安装包已上传原私有草稿、下载SHA256一致；未发布、未上传私人资料/密钥。

实际公开38分47秒S_R004S03C01副本在手机独立显示10完成：暂停时改为1.5倍不误播，按原音前后10秒跳转；1427ms墙钟前进2023ms原音；离开重开保持位置/倍速。强制结束自有应用后原退出88506ms、耐久检查点86189ms、实际续播86189ms，未用正常暂停冒充异常退出。相同录音key跨资料库保留独立位置和修订；新未播放副本实际采用1.25默认倍速，已有副本保留1.5。公开转写29处“超市”精确替换、草稿未自动保存、撤销、保存/重开、首次识别文字不变、旧纪要提示来源变更通过。

设置页将外观/回听放在前面，AI服务折叠：实际深浅色与跟随当前原生系统状态、默认倍速、续播开关、真实附近设备/通知权限和版本展示通过；关闭续播后从头播放，未误改已有录音倍速。设置在Web重载及完整进程重启后保留。未保存AI密钥草稿离开时取消保留，确认才离开，“返回会议”复用同一保护；测试密钥仅草稿，未保存、未发请求，不动原服务凭据。

普通系统文件选择器保存4618144B公开备份，包含86189ms/1.5倍检查点、修订/首次原文/旧纪要。实际恢复新资料库后回听位置86412ms、倍速1.5，文字/原文和来源变化状态保留；移入回收站再恢复仍在；仅新副本永久清除时实际检查点文件被移除，所有此前资料库保留。多WAV边界未单独触发，不据此算通过；物理听音质量、BLE/录音卡/OTA、电池、复杂多人、模型质量和新客户购买体验均未在本批合格。

保留工具失败而不当产品改善：首轮按钮选择器误带省略号；长会话主屏指纹因独立锁屏改变；重启后pidof读取过早；安装适配器漏re导入；锁屏Dozing时CDP/文件选择不能完成；DocumentsUI的无障碍点击确认不等于恢复成功。分别修选择器/按操作保护/有界等新进程/适配器，在Owner明确解锁后实际点击并等耐久资料库发布才记通过，未重打产品包或绕过锁屏。Owner随后明确要求接线不自动锁屏，USB保持唤醒原0→2，系统实际USB powered=true、mStayOn=true核验，保留此设置；拔线后的原超时策略未修改。

收尾原有1912文件核验，1911内容文件逐字节一致，唯一预期变化为资料库索引保留3份本批公开QA库（包含已精确清除的空测试库）；原有库及旧公开库均保留，原库已恢复为当前。测试设置恢复为原选择，独立应用/显示/转发和精确公开临时ZIP/驱动关闭/清理，手机保留已解除，未触及板卡或Owner日用主屏。完整[本批交付收据](handoffs/20261110-nonmodel-core-playback/delivered-result.json)，[设置真机结果](handoffs/20261110-nonmodel-core-playback/android121/settings-ui-result.json)，[原资料与会话收尾](handoffs/20261110-nonmodel-core-playback/android121/end-session.json)。

本批交付的是可回听、校对和管理设置的一整块实际手机流程，非全部非模型范围。原Android普通音视频导入、图片/时间备注、分类批量与剪辑合并及外部售卖依赖继续保留；下一完整软件批次从Android普通导入进入现有处理/导出/备份链，不切回模型训练，不重跑未受影响旧检查。没有新客户轮次，工程通过不替代用户验收或整机售卖资格。
<!-- /nonmodel-playback-settings121-delivered -->

'''
log.write_text(entry+text,encoding='utf8');print(json.dumps({'state':result['state'],'originalTaskAndTimelineUpdated':True,'source':result['sourceCommit'],'saleQualified':False}))
