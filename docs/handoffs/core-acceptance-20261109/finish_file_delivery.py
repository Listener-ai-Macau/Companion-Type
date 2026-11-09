"""Close one delivered file-handoff batch in the original backlog and timeline."""
from pathlib import Path
from datetime import datetime
import ast,copy,json,os,re,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261109-core-acceptance';O=C/'candidate081'
D=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109')
run=42616003162;artifact=D/f'attachments081-ci{run}'
load=lambda p:json.loads(p.read_text(encoding='utf8'))
v=load(O/'windows-verification.json');runtime=load(O/'runtime-result.json');installed=load(O/'installation.json');backup=load(O/'remote-candidate-backup.json')
case=next((artifact/'workflow-evidence').iterdir());native=load(case/'result.json')
assert runtime['state']=='WINDOWS_SAME_REAL_AUDIO_PRODUCT_ASR_AI_DOCUMENT_BACKUP_REOPEN_PASSED'
assert installed['state']=='WINDOWS081_INSTALLED_EXISTING_DATA_IDENTICAL' and installed['dataManifestIdentical']
assert v['sourceCommit']==runtime['appSourceCommit']==installed['sourceCommit']==backup['sourceCommit']
assert v['msiSha256']==backup['msiSha256'] and backup['readbackByteIdentical']
assert native['standardBrowserAttachmentsReceivedByteIdentical'] and len(native['receivedFiles'])==5
assert {Path(row['fileName']).suffix for row in native['receivedFiles']}=={'.docx','.txt','.pdf','.wav','.mp3'}
assert all(row['browserAttachment']['trustedNativePaste'] and row['sha256']==row['browserAttachment']['sha256'] for row in native['receivedFiles'])
assert load(case/'plan.json')['desktopPrimaryFileCopy']
proof=O/'runtime-proof';proof.mkdir(exist_ok=True)
for name in ['result.json','plan.json','ui-result.json','actual-received-pdf-extracted.txt','reviewed-ai-workbench-and-export.png','browser-attachments-received.png']:
 shutil.copyfile(case/name,proof/name)
for pattern in ['browser-reply-*.json','handoff-reply-*.json','received-attachment-*']:
 for p in case.glob(pattern):assert p.stat().st_size<5*1024**2;shutil.copyfile(p,proof/p.name)
failure=D/'attachments081-failure42615341299';failure_case=next((failure/'workflow-evidence').iterdir())
for source,name in [(failure/'result.json','failure-pdf-excerpt-result.json'),(failure_case/'result.json','failure-pdf-excerpt-native.json'),(failure_case/'browser-reply-2.json','failure-pdf-received.json')]:shutil.copyfile(source,O/name)
at=datetime.now().astimezone().isoformat(timespec='seconds')
record={'at':at,'state':'WINDOWS081_INSTALLED_COMPLETE_MEETING_DOCUMENT_AND_AUDIO_FILE_HANDOFF_PASSED',
 'purpose':'同一场实际公开会议的纪要、正文和原音/MP3从主入口复制为完整文件，实际粘贴为附件及文件落盘，备份恢复后继续使用。',
 'version':'0.1.81','sourceCommit':v['sourceCommit'],'buildRun':42612798269,'runtimeRun':run,
 'runtimeTestSource':'3db64f0c65c41e5a2b092269b234a9ab71abcf81','installed':True,
 'msiSha256':v['msiSha256'],'installation':str(O/'installation.json'),'runtimeReceipt':str(O/'runtime-result.json'),
 'receivedFiles':native['receivedFiles'],'standardBrowserAttachmentPasteQualified':True,'ordinaryShellFilePasteQualified':True,
 'sameOriginalWavByteIdentical':True,'sameAsrAiAndAudioBackupRestorePassed':True,
 'desktopPrimaryFileAndAudioCopyVisibleWithoutExtraMenu':True,'existingDataFilesByteIdentical':installed['existingDataFiles'],
 'remoteMsiReadbackVerified':True,'oldWinRTSharePickerFixed':False,'thirdPartyMessengerOrSendQualified':False,
 'ownerForegroundUsed':False,'newAsrOrAiCalls':0,'boardOrPhoneAccessed':False,'newCustomerAcceptance':False,'saleQualified':False,
 'verificationPreparationFailure':'PDF exact-string check encountered layout newlines; preserved native receipt and same-MSI headless diagnosis, then normalized whitespace only. No product source, source wording, model or installer was changed for this retry.'}
(O/'delivery-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
bp=R/'docs/product_backlog.json';raw=bp.read_bytes();d=json.loads(raw);quality=copy.deepcopy(d['quality_targets'])
f=d['owner_module_execution']['frontendWindowsMobile20261102'];b=f['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']
b['activeFileDelivery']=record
current=b['wholeCandidateCurrent'];current.update(updatedAt=at,installedVersion='0.1.81',installedSource=v['sourceCommit'],newProductBuildRun=42612798269,integratedRuntimeRun=run,wholeDeliveryRun=run,installation=installed,package=v,remoteDraft=backup,windowsFileDelivery=record)
current['integratedWindowsCore']['continuedCandidateVersion']='0.1.81'
current['integratedWindowsCore']['continuedSourceCommit']=v['sourceCommit']
for gaps in [b['remainingSaleBlocks'],current['saleGaps']]:
 for gap in gaps:
  if gap['block']=='双端与实卡同一候选':gap['facts']='Windows081同场实际ASR/AI结果、Word/TXT/PDF/WAV/MP3直接复制、标准浏览器真实附件粘贴及Shell实际落盘、原音备份恢复已过并安装；Android110签名包已远端保护，授权手机最近观察离线，真机/实卡匹配全链待续。旧WinRT面板及具体聊天客户端不由标准浏览器收件继承通过。'
f['state']='WINDOWS081_COMPLETE_MEETING_FILE_DELIVERY_INSTALLED_ANDROID110_PHONE_ACCEPTANCE_PENDING'
closure=f['ownerDevicePhoneClosure055'];previous=closure['latestWindowsInstalled']
if previous['version']!='0.1.81':closure.setdefault('previousWindowsInstalledObservations',[]).append(previous)
closure['latestWindowsInstalled']={'version':'0.1.81','receipt':str(O/'installation.json'),'source':v['sourceCommit'],'existingFilesByteIdentical':installed['existingDataFiles'],'exeSha256':v['embeddedExeSha256'],'dllSha256':v['dllSha256'],'wholeProductQualified':False}
closure.setdefault('phone100AggregateBeforeUnified110',{'state':closure['state'],'next':closure['next']})
closure['state']='ANDROID110_UNIFIED_CANDIDATE_READY_PHONE_OFFLINE_WINDOWS081_INSTALLED'
closure['next']='沿ownerCoreDeliveryPriority20261104.ownerCoreAcceptanceCandidate20261109.next续作；当前安卓候选110，连接后先读实际版本，不安装旧100或降级。'
f['ownerWindowsContentExports051']['latestContinuation']='ownerCoreDeliveryPriority20261104.ownerCoreAcceptanceCandidate20261109.activeFileDelivery'
assert d['quality_targets']==quality and bp.read_bytes()==raw and not d['release_boundary']['product_accepted']
bp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
(C/'whole-candidate-result.json').write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
guide=R/'docs/CORE_ACCEPTANCE_CANDIDATE.md';text=guide.read_text(encoding='utf8').replace('0.1.80','0.1.81').replace('candidate080/','candidate081/')
text=re.sub(r'2026-11-09T\d\d:\d\d:\d\d\+08:00',at,text,count=1)
text=text.replace('旧系统分享和聊天附件仍待补，Word已实际通过文件夹粘贴交付。','标准浏览器的真实附件粘贴已通过；旧系统分享和具体聊天客户端仍按原范围保留。')
text+='\n本批文件交付已安装：Windows081的“复制所选文件”和“复制录音文件”直接可见。同一场实际会议的Word、TXT、PDF、74,467,886字节原WAV和37,149,710字节MP3，在真实Edge可信粘贴事件后，经标准FormData在本机收件器落盘，并与Shell实际收件逐字节核对；这不是向联系人发送。原音、解码音频、原始转写和已有实际AI内容经备份恢复、重开保持一致。原245份应用资料升级前后hash相同。未重跑模型或云AI，未操作手机/板卡或Owner前台。\n'
guide.write_text(text,encoding='utf8')
log=R/'docs/development_log.md';log_raw=log.read_bytes();text=log_raw.decode('utf8').replace('\r\n','\n');marker='Windows文件附件交付20261109'
assert marker not in text
text=re.sub(r'<!-- frontend-windows078-current -->.*?<!-- /frontend-windows078-current -->','<!-- frontend-windows078-current -->\nWindows当前（'+at+'）：0.1.81已安装，原245份资料hash不变；同一实际公开会议的Word/TXT/PDF/原WAV/MP3主入口复制、真实浏览器附件和Shell落盘、带原音备份恢复通过。源码62b702d7，实际包验证与收件run42616003162，私有草稿备份回读一致。Android110沿原同批候选待真机；模型与硬件原门未因本批通过而降低。\n<!-- /frontend-windows078-current -->',text,count=1,flags=re.S)
text+='\n\n## '+at+' · '+marker+'\n\n承接Owner“直接把它做了”，完成同一会议文件交付整块：Windows主按钮直接复制完整内容文件及原音/MP3；移动端保留系统分享。源62b702d78b1258a4462d8a1fb7e49b7c0d42c9c9，正常构建42612798269；先在原080证明Edge实际接收45411B Word，随后在准确MSI081验证Word/TXT/PDF/原WAV/MP3五份实际附件与Shell收件，源码/包内/升级身份、原音及解码音频备份恢复和重开通过。20:23:01安装完成，245份原应用文件内容不变，MSI私有草稿上传并下载回读一致。全部网页与文件为原公开38m47s样本，无新ASR/AI、手机/板卡或Owner前台操作。\n\n真实返工：run42615341299在PDF逐字连续片段核对停止，Word/TXT内容及PDF文件实际接收字节已过；保留失败与同MSI后台导出诊断，证明PDF排版换行拆开片段。仅检查器忽略布局空白、保留原字词，增加实际收到PDF和提取文本留存；同一MSI复验run42616003162全过，没有重编或改会议事实。原WinRT面板未修、具体聊天客户端及真人购买不继承通过；当前模型CER目标、安卓真机与实卡售卖门继续沿原任务。修正055聚合中旧100下一步，统一指向110候选，防止后续降级。下一项读取原核心候选next，手机在线后用110做同场流程，固件原工作由对应任务接续。\n'
assert log.read_bytes()==log_raw;log.write_text(text,encoding='utf8')
paths=[]
for name in ['product_backlog.json','development_log.md','CORE_ACCEPTANCE_CANDIDATE.md']:
 target=S/'docs'/name;shutil.copyfile(R/'docs'/name,target);paths.append(target.relative_to(S).as_posix())
target=S/'docs/handoffs/core-acceptance-20261109/whole-candidate-result.json';shutil.copyfile(C/'whole-candidate-result.json',target);paths.append(target.relative_to(S).as_posix())
for p in O.rglob('*'):
 if p.is_file() and p.suffix.lower() in {'.py','.json','.txt','.png','.pdf','.docx'}:
  assert p.stat().st_size<5*1024**2
  target=S/'docs/handoffs/core-acceptance-20261109/candidate081'/p.relative_to(O);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);paths.append(target.relative_to(S).as_posix())
for name in ['continue_file_delivery.py','finish_file_delivery.py']:
 target=S/'docs/handoffs/core-acceptance-20261109'/name;shutil.copyfile(C/name,target);paths.append(target.relative_to(S).as_posix())
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'))
scope={'subprocess':subprocess,'env':{**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'<existing-publisher>','exec'),scope)
commit=scope['ship'](S,paths,'Deliver installed Windows081 complete meeting document and audio attachment workflow')
result={'at':at,'state':record['state'],'remoteCommit':commit,'remoteReadbackVerified':True,'installedVersion':'0.1.81','wholeProductQualified':False}
(O/'preservation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
