"""Record the grouped Windows outcome without closing other platform gates."""
from pathlib import Path
from datetime import datetime
import argparse,ast,copy,hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261109-core-acceptance';O=C/'candidate079';D=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/candidate079')
parser=argparse.ArgumentParser();parser.add_argument('--run',type=int,required=True);args=parser.parse_args()
runtime=json.loads((O/'runtime-result.json').read_text(encoding='utf8'))
assert runtime['state']=='WINDOWS079_GROUPED_AUDIO_REVIEWED_AI_AND_DELIVERY_RUNTIME_PASSED'
v=json.loads((O/'windows-verification.json').read_text(encoding='utf8'))
assert runtime['appSourceCommit']==v['sourceCommit'] and runtime['appVersion']=='0.1.79'
backup=json.loads((O/'remote-candidate-backup.json').read_text(encoding='utf8'));assert backup['readbackByteIdentical']
install=json.loads((O/'installation.json').read_text(encoding='utf8')) if (O/'installation.json').exists() else None
installed=bool(install and install['state']=='WINDOWS079_INSTALLED_EXISTING_DATA_IDENTICAL')
at=datetime.now().astimezone().isoformat(timespec='seconds')
allowed={'.json','.jsonl','.log','.txt','.png','.md','.pdf','.docx','.py','.cjs','.ps1'}
source=D/('runtime-ci-'+str(args.run));assert source.is_dir()
for p in source.rglob('*'):
 if not p.is_file() or p.suffix not in allowed or '.private' in p.name or 'public-audio-output' in p.parts:continue
 q=O/('runtime-ci-'+str(args.run))/p.relative_to(source);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
record={'at':at,'state':'WINDOWS079_GROUPED_CANDIDATE_INSTALLED_DATA_PRESERVED' if installed else 'WINDOWS079_GROUPED_CANDIDATE_PROTECTED_RUNTIME_PASSED_INSTALL_PENDING','version':'0.1.79','sourceCommit':v['sourceCommit'],'runtimeTestSourceCommit':runtime['testSourceCommit'],'buildRun':v['ciRunId'],'runtimeRun':args.run,'runtimeUrl':'https://github.com/Listener-ai-Macau/Companion-Type/actions/runs/'+str(args.run),'installed':installed,'installation':install,'remoteDraft':backup,'msiSha256':v['msiSha256'],'completedOutcome':['真实公开38分47秒原音系统导入、媒体播放探针、原音/MP3系统保存和Windows标准Shell粘贴、MP3重导入解码、重开','无文字时转文字/导出录音可见，未显示不可用AI工作区；有最终文字时可进入会议AI助手','实际AI纪要的会中问题、完整两段处理状态、校对后摘要、顶部直达所选内容导出、Word实际落盘','实际AI材料阅读/导出后原始转写、修订及纪要内容不变'],'limits':['回听探针为实际媒体解码与运行时静音，不代替扬声器实听和全部原生拖动条操作','本批复用实际既有ASR和AI结果；30.817秒是转写文字到纪要，人工校对不等于ASR准确率提升','Windows标准Shell文件收件已过；聊天应用附件及旧WinRT系统分享仍未合格','Android、板卡、复杂多人/重叠、完整事实质量和新客户实际体验沿原待办开放'],'localHeavyBuild':False,'localModelsRun':False,'phoneAccessed':False,'boardAccessed':False,'wholeCoreCandidateQualified':False,'saleQualified':False}
(O/'delivery-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
guide=R/'docs/CORE_ACCEPTANCE_CANDIDATE.md'
guide.write_text('# Companion 核心候选验收入口\n\n更新：'+at+'。当前这份是Windows侧集中候选0.1.79，'+('已后台升级，原有应用资料逐文件校验一致。' if installed else '已完成原生运行验收和安装包保护，尚未确认本机升级。')+'整体核心候选仍在推进，不能作为正式开售合格证明。\n\n[Windows 0.1.79 候选安装包]('+v['msi'].replace('\\','/')+') · [私有草稿备份]('+backup['url']+')\n\n验收时围绕一场会议完成下面这个目的，不需要逐页点所有按钮：\n\n1. 在“设备与同步”导入一份公开测试录音，再到“我的记录”打开它。应能找到“转文字”“回听”和顶部“导出录音”；尚无文字时，先按提示转文字。\n2. 回听确认内容与时长。通过顶部“导出录音”保存原音，或另存MP3副本。原音保留；复制录音文件后，由自己选择粘贴位置。\n3. 在已有转写和纪要的会议里核对摘要、讨论结论、待办与原文。原文字可单独修订；修订后旧整理应提示来源已变化，需要重新整理，初版应保留。\n4. 通过顶部“导出分享”选择整理结果、录音文字或补充，预览后保存Word/PDF等文件；复制文件后可到Windows文件夹粘贴，核对内容和格式。复制与保存不会自动发送。\n5. 关闭后重新打开，核对记录、修订、整理结果和待办状态是否还在。\n\n这轮工程已经实际跑过：公开38分47秒WAV与导出MP3的保存、文件粘贴、重新导入解码和重开；实际AI整理、人工校对后的重新整理与历史、Word交付，以及新版对应界面。播放检查是静音媒体探针，仍需要实际听音。没有把公开样例自动写进你的日用资料库。\n\n仍需继续：旧Windows系统分享面板、聊天应用附件收件、Android和录音卡同场联调、复杂多人/重叠模型与完整纪要事实质量、客户真实使用。没有用本轮界面或安装结果替代这些资格。\n\n唯一待办仍是[原任务书](C:/Users/Billy/Desktop/Denzic/Companion/docs/product_backlog.json)，完整记录仍是[开发时间线](C:/Users/Billy/Desktop/Denzic/Companion/docs/development_log.md)。\n',encoding='utf8')
p=R/'docs/product_backlog.json';raw=p.read_bytes();d=json.loads(raw);quality=copy.deepcopy(d['quality_targets']);f=d['owner_module_execution']['frontendWindowsMobile20261102'];b=f['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']
if b.get('lastOutcome') and b['lastOutcome'].get('version')!='0.1.79':b.setdefault('previousBatchOutcomes',[]).append(b['lastOutcome'])
b['lastOutcome']=record
b.update(state='CORE_ACCEPTANCE_BATCH_IN_PROGRESS_WINDOWS079_GROUPED_RUNTIME_PROVEN',lastWindowsGroupedOutcome=record)
b['groupedCandidate079'].update(state=record['state'],sourceCommit=v['sourceCommit'],runtimeRun=args.run,installed=installed,normalReleaseBuildPassed=True,msiPayloadAndUpgradeVerified=True,actualRuntimePassed=True,remoteDraftProtected=True)
b['groupedMeetingUiSource20261109'].update(state='GROUPED_UI_PACKAGED_AND_ACTUAL_RUNTIME_PASSED',nativePackaged=True,candidateVersion='0.1.79',runtimeRun=args.run,installed=installed)
if installed:
 closure=f['ownerDevicePhoneClosure055'];previous=closure.get('latestWindowsInstalled')
 if previous and previous.get('version')!='0.1.79':closure.setdefault('previousWindowsInstalledObservations',[]).append(previous)
 closure['latestWindowsInstalled']={'version':'0.1.79','receipt':str(O/'installation.json'),'existingFilesByteIdentical':install['existingDataFiles'],'source':v['sourceCommit'],'exeSha256':install['installedExeSha256'],'dllSha256':install['installedDllSha256'],'actualGroupedRuntimeRun':args.run,'wholeProductQualified':False}
b['currentCheckpoint']['windows']='0.1.79 '+('installed; existing data hashes unchanged' if installed else 'inspected protected candidate; installation pending')+'; source '+v['sourceCommit']+'; normal release MSI and grouped runtime passed'
b['currentCheckpoint']['windowsRemaining']='旧WinRT系统分享与聊天应用附件、实体实听保留；下一批Windows阻断/双端/录音卡按原任务集中完成，不能写只剩模型。'
b['next']='先处理Windows旧系统分享和聊天附件交付的剩余实际阻断；结合当前可用条件承接Android/录音卡同场流程，沿原分工不抢板卡。模型独立，原质量门保持；完整核心候选到齐后集中交Owner和新客户体验。'
f['next']=b['next'];b['latestOwnerContinuation']={'quote':'继续集中推进','at':at,'decision':'完成同一Windows会议交付链及079集中候选，承接原1–2周工程预算，不拆新任务树。','next':b['next']}
assert d['quality_targets']==quality and p.read_bytes()==raw
temp=p.with_suffix('.core079-final.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,p)
log=R/'docs/development_log.md';marker='Windows079集中会议候选实际运行与交付20261109'
with log.open('a' if marker not in log.read_text(encoding='utf8') else 'r',encoding='utf8') as out:
 if out.writable():
  out.write('\n\n## '+at+'｜'+marker+'\n\n同一核心候选批次的Windows侧收敛结果：'+json.dumps(record,ensure_ascii=False)+'\n\n原078及失败保留；079正常优化仅远端构建，源和共享平台固定、包内EXE/DLL/许可证/同升级身份独立核对，私有草稿下载回读核SHA。原音与实际AI资料受影响的普通UI路径使用新包内同字节原生对验证，不用浏览器演示、假AI回答或旧版改标签。原质量目标结构不变；这不是整机、客户或售卖验收。下一项：'+b['next']+'\n')
text=log.read_text(encoding='utf8');start='<!-- frontend-windows078-current -->';end='<!-- /frontend-windows078-current -->'
if start in text and end in text:
 a=text.index(start);z=text.index(end,a)+len(end);text=text[:a]+start+'\nWindows当前（'+at+'）：0.1.79集中候选'+('已安装，原资料hash一致' if installed else '已保护，安装待完成')+'；真实公开原音/MP3及校对后AI文档的受影响原生界面和Shell实际交付通过。旧系统分享/聊天附件/双端板卡/模型/售卖门仍开放。沿原核心批次ownerCoreAcceptanceCandidate20261109继续。\n'+end+text[z:];log.write_text(text,encoding='utf8')
dest=S/'docs/handoffs/core-acceptance-20261109';mapping=json.loads((dest/'evidence-path-map.json').read_text(encoding='utf8'));rename={e['original']:e['mirror'] for e in mapping['entries']}
for p in C.rglob('*'):
 if not p.is_file() or p.suffix not in allowed or '.private' in p.name or '__pycache__' in p.parts:continue
 rel=p.relative_to(C).as_posix()
 if 'public-audio-output/' in rel or '/ci-artifact/' in '/'+rel:continue
 mirrored=rename.get(rel,rel)
 if len(str(dest/mirrored))>240:
  parts=mirrored.split('/')
  parts=['artifact' if item.startswith(('companion-core-audio-','companion-core-ui-')) else item for item in parts]
  for i,item in enumerate(parts):
   if i and parts[i-1]=='workflow-evidence' and len(item)==32:parts[i]='case-'+item[:8]
  mirrored='/'.join(parts)
 if mirrored!=rel and rel not in rename:
  mapping['entries'].append({'original':rel,'mirror':mirrored,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()});rename[rel]=mirrored
 q=dest/mirrored;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
(dest/'evidence-path-map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for p in [R/'docs/product_backlog.json',log,guide]:shutil.copyfile(p,S/'docs'/p.name)
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'os':os,'subprocess':subprocess,'env':{**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'<approved-publisher>','exec'),scope)
head=scope['ship'](S,['docs/product_backlog.json','docs/development_log.md','docs/CORE_ACCEPTANCE_CANDIDATE.md','docs/handoffs/core-acceptance-20261109'],'Preserve grouped Windows079 runtime delivery and continue the same core acceptance batch')
print(json.dumps({'state':record['state'],'installed':installed,'remoteDeliveryCommit':head,'remoteReadbackConfirmed':True,'wholeCoreCandidateQualified':False},ensure_ascii=False))
