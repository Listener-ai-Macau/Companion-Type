"""Preserve one completed phone delivery batch in the existing task and timeline."""
from pathlib import Path
from datetime import datetime
import ast,copy,json,os,re,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=Path(__file__).parent;O=C/'android110/phone-d6'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
now=datetime.now().astimezone().isoformat(timespec='seconds')
installed=read(O/'installation115.json');package=read(C/'android115/build-result.json');remote=read(C/'android115/remote-backup.json');ui=read(O/'reading-ui115.json');owner=read(O/'owner-return.json');ended=read(O/'session-ended.json')
assert installed['versionCode']==115 and installed['apkSha256']==package['apkSha256']==remote['apkSha256']
assert ui['state']=='ANDROID115_REAL_PHONE_FIRST_CONTENT_VISIBLE_SECONDARY_TOOLS_REACHABLE'
assert owner['originalActive'] and ended['ownVirtualDisplayStopped'] and ended['ownerOriginalRows']==104
assert remote['downloadByteIdentical'] and read(O/'public-meeting-remote-backup112.json')['downloadHashIdentical']
record={'at':now,'state':'ANDROID115_PHONE_MEETING_PROCESSING_DELIVERY_RESTORE_AND_READING_BATCH_COMPLETED','ownerOriginal':'继续, 现在有手机了','version':'0.1.115','sourceCommit':installed['sourceCommit'],'backendSourceCommit':'608790132701ede93fa24a00b687874cb7e70c6b','apkSha256':package['apkSha256'],'installed':True,'qualifiedScope':['public COP1 meeting imported through system picker','phone local transcription saved','AI minutes and quoted-source material saved','complete English translation saved','play/pause/seek/resume','system Word/TXT/WAV saving and actual clipboard paste','PDF received by local system print spooler and saved','mindmap XML saving','whole-library backup and new-library restore','public recording trash and restore','saved meeting content visible and secondary tools reachable'],'linkedFunctionalVersions':{'localAsrAndMinutes':111,'contentAndPlayback':111,'fixedTranslationBackupRestoreAndLifecycle':112,'finalReadingUi':115},'localAsr':read(O/'asr111-result.json'),'result':read(O/'completed-public-result112.json'),'ui':ui,'ownerReturn':owner,'sessionEnded':ended,'remotePackage':remote,'publicMeetingBackup':read(O/'public-meeting-remote-backup112.json'),'newDesktopModelTrainingRuns':0,'physicalBoardAccessed':False,'computerUseUsed':False,'wholeProductQualified':False,'newCustomerEvaluationPerformed':False}
(O/'final-phone-batch.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=R/'docs/product_backlog.json';d=read(p);quality=copy.deepcopy(d['quality_targets']);f=d['owner_module_execution']['frontendWindowsMobile20261102'];b=f['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']
b['androidPhoneAcceptance']=record
b['next']='手机会议处理、保存复制、PDF本机接收、备份恢复和阅读入口按本批范围已交付，复用原证据。沿原模型任务继续当前公开实会6.63%字错率与复杂多人/事实门；原实卡和新客户未验范围不虚关，不重复已过的文件交付流程。'
closure=f['ownerDevicePhoneClosure055'];closure['latestAndroidCandidate']={'version':'0.1.115','code':115,'sourceCommit':installed['sourceCommit'],'backendSourceCommit':record['backendSourceCommit'],'apk':package['apk'],'apkSha256':package['apkSha256'],'installed':True,'signerMatchesKnownApplication':True,'actualPhoneMeetingFlowQualified':True,'mobileReadingUiQualified':True,'actualPhoneQualified':False,'wholeProductQualified':False,'qualificationBoundary':'This batch covers the phone meeting software flow. No new physical-board pairing, transfer, OTA or whole-product/customer qualification.','receipt':'docs/handoffs/20261109-core-acceptance/android110/phone-d6/final-phone-batch.json','remoteBackup':remote}
if isinstance(b.get('wholeCandidateCurrent'),dict):b['wholeCandidateCurrent']['androidCurrent']=closure['latestAndroidCandidate']
hold=d['recorder_core']['speed_investigation_handoff']['endpointSelection']['ownerPhoneHold'];assert hold.get('serial')=='d6bd213d';hold.update(active=False,releasedAt=now,releaseReason='Phone meeting software acceptance complete; original library restored, owned UI/app/display closed. No board access or radio connection by this batch.')
assert d['quality_targets']==quality;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=R/'docs/development_log.md';text=p.read_text(encoding='utf8');start='<!-- phone-core-acceptance-20261109-current -->';end='<!-- /phone-core-acceptance-20261109-current -->'
entry=f'''{start}
## {now} — Android115手机会议软件整批交付、原资料恢复

Owner“继续，现在有手机了”沿原核心候选续作。实际d6手机109→110→111→112→113→114→115，最终源码{installed['sourceCommit']}，冻结原生AAR/6087901不变。Windows081本批未改。手机操作在USB独立显示5完成，没有Computer Use、主屏输入、接板、BLE、录音或OTA。

同一38分47秒公开M2MET实会从系统文件选择器恢复、手机本地转写保存，点击至观察完成143.790s，包含首次下载模型，不是纯推理计时。实际转写8,341字；AI纪要按全部2段生成并与原文字节哈希绑定，问答材料2条原话在实际转写中可查，三段完整英文译文26,839字保存。真实Word/TXT/WAV系统落盘、17,579字实际Android剪贴板粘贴逐字节一致、系统打印接收PDF并保存（不是发送联系人或打印机作业）、126节点导图、播放暂停跳转继续通过。整份4,594,647B公开备份恢复到新资料库，13份原音/文字/纪要/依据/译文hash相同；公开录音回收站0→1恢复且内容不变。原文、纪要及材料在升级和恢复后保留。

保留失败：两次测试COP1封装被生产解码器正确拒绝，修准备器不计产品改善。110真实首用报模型metadata缺失，AAR/APK资源漏包，111按原6087901资源补齐并校验；Windows检出换行损坏的首轮CI失败留存。111真实长翻译首段失败，同一公开段旧请求45.516s超时、明确非思考请求18.015s完整返回；112仅对DeepSeek官方服务设置非思考和有界输出，手机整场复验通过。来源为官方API文档及真实诊断收据。113首屏仍只露计数，114正文仅露一行（771.316CSSpx，导航799.435），保留未过证据；最后定位“整理视角”一行被包装成85CSSpx正文卡片。115只把精确匹配的产品模板标签压为说明文字，作者正文/其它引用不变；实际包复验正文顶{ui['layout']['firstContentTop']:.3f}CSSpx、导航{ui['layout']['bottomNavigationTop']:.3f}，首屏能读正文，整理方式、管理和本地重点仍可打开。临时CSS探针已移除，不当实际包通过。114初始TS分支收窄错误及本机256MiB类型检查堆上限失败保留，未安装失败包；修源码后CI类型检查/构建通过。本批UI返工多于一次集中构建，后续先用实际内容和尺寸定位，再收敛打包，不把版本或测试数量算功能进展。

收尾：原有{owner['originalFilesVerified']}份文件逐字节一致，唯一预期变化是资料库索引保留原库和一份可复验公开实会；原库104条已恢复为当前。3份本批公开重复库移入可恢复的应用缓存隔离区，未擦除原资料；约993MB原私有备份仅本机E盘。应用/独立显示/本批转发关闭、手机保留解除。115同签名安装包和完整公开会议备份已上传原私有草稿并下载hash一致，未发布、未上传原私有资料或密钥。详见[本批终态](handoffs/20261109-core-acceptance/android110/phone-d6/final-phone-batch.json)。

实际模型诊断为此公开完整样本6.63%（552/8325），仍未达到原低于5%门；本批没有训练或声称复杂多人、整机可售、新客户愿买通过。下一步按原模型和实卡/客户未验范围续作，已验软件交付不重复重跑。
{end}

'''
if start in text:
    a=text.index(start);z=text.index(end,a)+len(end);text=text[:a]+entry.rstrip()+text[z:]
else:text=entry+text
pattern=r'(<!-- frontend-windows078-current -->).*?(<!-- /frontend-windows078-current -->)'
text=re.sub(pattern,lambda m:m[1]+'\nWindows081保持原已验交付；Android115已完成本批手机会议处理、文件交付、恢复与阅读入口真机验证，原104条资料恢复。手机公开样本字错率6.63%未过原5%目标，整机/实卡和客户门未因此虚关。\n'+m[2],text,flags=re.S)
p.write_text(text,encoding='utf8')
paths=[]
for name in ['product_backlog.json','development_log.md']:
    target=S/'docs'/name;shutil.copyfile(R/'docs'/name,target);paths.append(target.relative_to(S).as_posix())
for folder in ['android110','android111','android112','android113','android114','android115']:
    for file in (C/folder).rglob('*'):
        if file.is_file() and file.suffix in ['.json','.py','.java','.cjs','.png','.css']:
            target=S/'docs/handoffs/core-acceptance-20261109'/folder/file.relative_to(C/folder);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target);paths.append(target.relative_to(S).as_posix())
for name in ['finish_phone_batch.py','finish_android111_package.py','backup_android111.py','build_first_model_fixed_android.py']:
    target=S/'docs/handoffs/core-acceptance-20261109'/name;shutil.copyfile(C/name,target);paths.append(target.relative_to(S).as_posix())
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'os':os,'subprocess':subprocess,'env':{**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15'}}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'existing-publisher','exec'),scope)
commit=scope['ship'](S,paths,'[android] Deliver phone meeting processing, content handoff, recovery and readable saved results')
print(json.dumps({'state':record['state'],'recordsCommit':commit,'sourceCommit':installed['sourceCommit'],'version':'0.1.115','remoteVerified':True,'originalFilesVerified':owner['originalFilesVerified'],'originalRows':ended['ownerOriginalRows']}))
