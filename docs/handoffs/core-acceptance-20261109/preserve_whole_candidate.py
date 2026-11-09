"""One existing batch: complete meeting results and the matched Windows core."""
from pathlib import Path
from datetime import datetime
import argparse,ast,copy,hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=R/'docs/handoffs/20261109-core-acceptance';D=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109');O=C/'candidate080'
parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['checkpoint','final'],required=True);parser.add_argument('--runtime-run',type=int);a=parser.parse_args();at=datetime.now().astimezone().isoformat(timespec='seconds')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
audio=read(D/'same-meeting-asr-ci-42592563926/result.json');delivered=read(D/'same-meeting-delivery-ci-42593867826/result.json');ai=read(C/'same-meeting-ai-current.json')['record'];integration=read(C/'whole-core-integration.json')
assert delivered['state']=='WINDOWS_SAME_REAL_AUDIO_PRODUCT_ASR_AI_DOCUMENT_BACKUP_REOPEN_PASSED'
record={'at':at,'state':'WHOLE_MEETING_PASSED_MATCHED_WINDOWS_CORE_INTEGRATING','phase':a.phase,'ownerPurpose':'完整一场会议的录音与会后处理，集中合并当前接收核心后再交一套候选；不是小版本计进度。','sameSessionId':delivered['sameMeeting']['sessionId'],'sourceAudioSha256':delivered['sameMeeting']['sourceAudioSha256'],'decodedAudioSha256':delivered['sameMeeting']['decodedAudioSha256'],'actualAsrRun':42592563926,'actualAiEvidence':str(C/'whole-805278e2b7214018a4ddef74e361a9e8'),'wholeDeliveryRun':42593867826,'fixedProductAsrSeconds':ai['productAsrSeconds'],'actualAiSeconds':ai['aiSeconds'],'asrDiagnostic':ai['currentProductAsrChronologicalDiagnostic'],'sameAudioAsrAiLineageVerified':True,'actualWordReceived':True,'originalAndDecodedAudioBackupRestoredByteIdentical':True,'integratedWindowsCore':integration,'newProductBuildRun':42594837619,'localHeavyInference':False,'modelResearchOrTraining':False,'fixedProductAsrInferenceOnRemote':True,'newModelProviderSelected':False,'newCustomerAcceptance':False,'wholeCoreCandidateQualified':False,'saleQualified':False}
allowed={'.json','.jsonl','.log','.txt','.png','.md','.pdf','.docx','.py','.cjs','.ps1'}
for name in ['same-meeting-asr-ci-42592563926','same-meeting-delivery-ci-42593867826']:
 for p in (D/name).rglob('*'):
  if not p.is_file() or p.suffix not in allowed or '.private' in p.name:continue
  q=C/name/p.relative_to(D/name);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
record['saleGaps']=[{'block':'双端与实卡同一候选','state':'OPEN','facts':'Windows完整公开会议链已过；Android前端本侧旧100候选未安装，但嵌软共享收据已到109，不能按100或旧65降级。一次只读检查手机absent。实板原377长录属于原会话，在途接收不抢占。','exit':'同源Windows/Android/固件按同一场保存、恢复、回听、转写/AI及交付实际贯通。'},{'block':'长录/连接/异常恢复可靠性','state':'OPEN','facts':'记录当前d00三处接收修复已合并；旧前端079此前不包含它们。最终2h及固件故障自动收尾等只沿嵌软当前原收据，不借软件文本链关闭。','exit':'当前匹配接收核心与固件完成原长录及正常中断恢复，原音完整。'},{'block':'转写/多人/纪要质量','state':'OPEN','facts':'当前产品固定提供器同场严格混合字错率6.4024%，未<5%；复杂多人/重叠与完整事实质量仍未合格，未因本轮功能链通过而改门槛。','exit':'按原多会议、逐人/重叠与事实指标达标。'}]
record['otherExistingDependencies']='实际电池/充电/低电保存与续航、生产签名/出厂及Owner暂停屏幕等仍沿原嵌软任务；不凭软件收据写全产品可售卖。旧WinRT系统分享与聊天附件收件也仍开放，普通Word交付本轮走真实Windows Shell文件粘贴。'
if a.phase=='final':
 assert a.runtime_run
 runtime=read(O/'runtime-result.json');installed=read(O/'installation.json');v=read(O/'windows-verification.json');backup=read(O/'remote-candidate-backup.json')
 assert runtime['state']=='WINDOWS_SAME_REAL_AUDIO_PRODUCT_ASR_AI_DOCUMENT_BACKUP_REOPEN_PASSED' and runtime['appVersion']=='0.1.80'
 assert runtime['appSourceCommit']==v['sourceCommit']==integration['sourceCommit']
 assert installed['state']=='WINDOWS080_INSTALLED_EXISTING_DATA_IDENTICAL' and installed['dataManifestIdentical'] and backup['readbackByteIdentical']
 record.update(state='WINDOWS_COMPLETE_MEETING_AND_MATCHED_RECORDING_CORE_INSTALLED',integratedRuntimeRun=a.runtime_run,installedVersion='0.1.80',installedSource=v['sourceCommit'],installation=installed,package=v,remoteDraft=backup)
 name='integrated-runtime-ci-'+str(a.runtime_run)
 for p in (D/name).rglob('*'):
  if not p.is_file() or p.suffix not in allowed or '.private' in p.name:continue
  q=O/name/p.relative_to(D/name);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
(C/'whole-candidate-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=R/'docs/product_backlog.json';raw=p.read_bytes();d=json.loads(raw);quality=copy.deepcopy(d['quality_targets']);f=d['owner_module_execution']['frontendWindowsMobile20261102'];b=f['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109'];b['wholeCandidateCurrent']=record;b['wholeWindowsCoreIntegration']=integration;b['wholeWindowsCoreIntegration']['buildRun']=42594837619
b['remainingSaleBlocks']=record['saleGaps'];b['planningBudget']['meaning']='原11月16日至23日仍是完整核心验收候选工程预算，不重置起点、不滚动顺延，也不是正式售卖日期；模型、实物和完整候选未过时如实报告差距。'
f['state']='WHOLE_CORE_CANDIDATE_INTEGRATING_CURRENT_WINDOWS_AND_RECORDING_CORE';b['next']='完成同源Windows核心候选的包内核对、受影响原生UI/文档/原音恢复和原资料保留；不重跑已过同一ASR/AI。然后按实际手机/板卡可用条件接续双端同场，模型与既有硬件售卖门继续独立，不能再说只剩模型。'
if a.phase=='final':
 f['state']='WINDOWS_FULL_MEETING_AND_CURRENT_RECEIVER_INTEGRATED_ANDROID_AND_QUALITY_OPEN';b['state']='WHOLE_CORE_CANDIDATE_WINDOWS_COMPLETE_BLOCK_PROVEN_ANDROID_CARD_AND_QUALITY_OPEN';b['currentCheckpoint']['windows']='0.1.80实际安装，源'+record['installedSource']+'；原音→当前固定ASR→实际AI→回听/Word→带原音备份恢复/重开通过，并合入与实卡一致的d00接收恢复实现。'
 b['currentCheckpoint']['windowsRemaining']='旧WinRT系统分享、聊天应用附件仍开放；双端/实卡当前候选与模型/硬件质量门未合格。'
 b['next']='接续Android当前109原生层与当前前端的同源集成，不安装旧100或降级；手机恢复可用后集中走完整会议与后台恢复。实卡原377/770由原会话收尾，按共享新收据承接匹配结果，不抢板、不另开重复2h。旧系统分享与模型/硬件门保持开放。'
 closure=f['ownerDevicePhoneClosure055'];old=closure.get('latestWindowsInstalled')
 if old and old.get('version')!='0.1.80':closure.setdefault('previousWindowsInstalledObservations',[]).append(old)
 closure['latestWindowsInstalled']={'version':'0.1.80','receipt':str(O/'installation.json'),'source':record['installedSource'],'existingFilesByteIdentical':record['installation']['existingDataFiles'],'exeSha256':record['installation']['installedExeSha256'],'dllSha256':record['installation']['installedDllSha256'],'wholeProductQualified':False}
f['next']=b['next'];b['latestOwnerContinuation']['actualCurrent']=record['state'];assert d['quality_targets']==quality and p.read_bytes()==raw
tmp=p.with_suffix('.whole-candidate.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(tmp,p)
if a.phase=='final':
 log=R/'docs/development_log.md';marker='完整实会软件链与录音接收同源候选20261109';assert marker not in log.read_text(encoding='utf8')
 with log.open('a',encoding='utf8') as out:
  out.write('\n\n## '+at+'｜'+marker+'\n\n承接Owner要求“完整的一块东西做完再交付，不要零碎、加快”。已安装079作为中间候选保留，不能把分开的原音和缓存ASR/AI检查称完整。实际同一公开S_R004S03C01、同一import-00817de5e4dc4f55b9119da5a170fcaa：原生界面系统导入38分47秒WAV，当前产品固定Paraformer-large int8实际CPU转写136.076秒、8333字/142段；本机仅公开文字通过已有AI服务49.703秒处理2/2段，原文/音频不变。随后实际原生界面回听、阅读、Word复制到Windows标准Shell、带原音备份到新库恢复和重开全部通过；不是参考文字替代ASR，也不是模拟AI。当前固定产品该场严格混合CER533/8325=6.4024%，仍未<5%，复杂多人/逐人重叠/事实与跨会门不变。\n\n发现前端079与实卡接收079来自不同源，属于此前交付分散的实际问题。本批按078共同基线确认仅三处生产接收文件差异，合入d00冷目录/连接保持/开录恢复，与原在途实板源码一致；ASR/AI/导出/恢复/UI源码未改变，复用其有效输入/推理，不扫模型或重复推理。080同一正常优化包、源码/包内/许可证/升级身份核对、实际集成原生界面和数据交付恢复后再安装；旧源、旧包、旧失败保留。没有停止另一套私人目录接收器、占Owner前台、抢手机/板卡或改网络/全局内存。\n\n完整结果：'+json.dumps(record,ensure_ascii=False)+'\n\n准备失败：私有草稿按tag的REST读取404，沿已有release ID438762888核验已上传的公开模型包，没有重复上传或换模型；独立评分器缺praatio发生在真实AI生成成功之后，保留原失败，仅私有依赖补齐评分，没有重跑ASR/AI。原GitHub草稿新建权限不足沿已授权私有恢复容器用独立版本文件备份，不发布正式版、不请求新权限。下一项仍是同批：'+b['next']+'\n')
guide=R/'docs/CORE_ACCEPTANCE_CANDIDATE.md'
guide.write_text('# Companion 完整核心候选当前状态\n\n'+at+'。'+('Windows当前为0.1.80，已装并保留原应用资料；本次是一场会议从原音到AI文档、连原音备份恢复及重开的完整软件块。' if a.phase=='final' else 'Windows079保留为中间已装版；正在集中合入与实卡一致的接收恢复实现，尚未交付整套核心候选。')+'\n\n实际结果：公开38分47秒录音，当前产品实际本地CPU转写136.076秒，已有AI服务整理49.703秒；同一会议原生阅读/回听、Word实际粘贴、原音与解码音频备份到新库恢复和重开通过。重计算在独占远端，当前电脑不跑重模型；所有音频和文字均为公开资料。\n\n当前产品该场严格混合字错率6.4024%，未达<5%。不把软件流程通过写成模型或全产品合格。Android/实卡匹配候选、长录与异常恢复、复杂多人/重叠与完整纪要事实、既有电源/量产等依赖仍开放；旧系统分享和聊天附件仍待补，Word已实际通过文件夹粘贴交付。\n\n原11月16日至23日是完整核心验收候选工程预算，不能当作正式售卖日期。暂停/blocked不是免验。\n\n[原任务书](C:/Users/Billy/Desktop/Denzic/Companion/docs/product_backlog.json) · [本批实际结果](C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-core-acceptance/whole-candidate-result.json)\n',encoding='utf8')
dest=S/'docs/handoffs/core-acceptance-20261109';mapping=read(dest/'evidence-path-map.json');rename={e['original']:e['mirror'] for e in mapping['entries']}
for p in C.rglob('*'):
 if not p.is_file() or p.suffix not in allowed or '.private' in p.name or '__pycache__' in p.parts:continue
 rel=p.relative_to(C).as_posix()
 if '/ci-artifact/' in '/'+rel or 'public-audio-output/' in rel:continue
 mirrored=rename.get(rel,rel)
 if len(str(dest/mirrored))>235:
  parts=mirrored.split('/');parts=['artifact' if item.startswith(('companion-core-audio-','companion-core-ui-')) else item for item in parts]
  for i,item in enumerate(parts):
   if i and parts[i-1]=='workflow-evidence' and len(item)==32:parts[i]='case-'+item[:8]
  mirrored='/'.join(parts)
 if mirrored!=rel and rel not in rename:rename[rel]=mirrored;mapping['entries'].append({'original':rel,'mirror':mirrored,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 q=dest/mirrored;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
(dest/'evidence-path-map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for p in [R/'docs/product_backlog.json',R/'docs/development_log.md',guide]:shutil.copyfile(p,S/'docs'/p.name)
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'os':os,'subprocess':subprocess,'env':{**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'<existing-publisher>','exec'),scope)
h=scope['ship'](S,['docs/product_backlog.json','docs/development_log.md','docs/CORE_ACCEPTANCE_CANDIDATE.md','docs/handoffs/core-acceptance-20261109','tools/qa/core_acceptance20261109/windows_meeting.py','tools/qa/core_acceptance20261109/run_ci.py'],'Preserve the same complete real meeting and matched Windows core '+a.phase)
print(json.dumps({'state':record['state'],'remoteCommit':h,'remoteReadbackVerified':True,'wholeProductQualified':False},ensure_ascii=False))
