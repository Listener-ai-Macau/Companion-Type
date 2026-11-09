"""Protect actual public audio/AI outcomes in the existing batch and remote."""
from pathlib import Path
from datetime import datetime
import ast,copy,hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261109-core-acceptance';D=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109')
at=datetime.now().astimezone().isoformat(timespec='seconds')
allowed={'.json','.jsonl','.log','.txt','.png','.md','.pdf','.docx','.py','.cjs','.ps1'}
def public_copy(source,dest):
 for p in source.rglob('*'):
  if not p.is_file() or p.suffix not in allowed or '.private' in p.name or '__pycache__' in p.parts:continue
  rel=p.relative_to(source)
  if 'public-audio-output' in rel.parts:continue
  q=dest/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
for prefix,run in [('audio',42587058258),('ui',42584662552)]:
 source=D/(prefix+'-ci-'+str(run));assert source.is_dir()
 public_copy(source,C/(prefix+'-ci-'+str(run)))
audio=json.loads(next((C/'audio-ci-42587058258').glob('*/result.json')).read_text(encoding='utf8'))
assert audio['state']=='WINDOWS_REAL_PUBLIC_AUDIO_IMPORT_PLAYBACK_DELIVERY_REOPEN_PASSED'
A=C/'ai-22512f1af147477eadece50329a12b93'
read=lambda n:json.loads((A/n).read_text(encoding='utf8'))
assert read('generation.json')['exitCode']==0
assert read('review-regeneration.json')['oldMinutesHistoryRetained']
assert read('ai-checklist-flow.json')['checkedItemPersisted']
freeze=json.loads((C/'candidate079/source-freeze.json').read_text(encoding='utf8'))
record={'at':at,'state':'PUBLIC_AUDIO_AND_REVIEWED_AI_WORKFLOW_PROVEN_GROUPED_WINDOWS079_BUILDING','versionUnderTest':'0.1.78','audio':audio,'ai':{name:read(name) for name in ['generation.json','review-regeneration.json','ai-checklist-flow.json','fact-review.json']},'groupedCandidateSource':freeze['sourceCommit'],'candidateVersion':'0.1.79','candidateBuildRun':42587844329,'candidateInstalled':False,'oldWinRtSystemShareStillOpen':True,'thirdPartyMessengerAttachmentStillOpen':True,'physicalListeningQualified':False,'wholeCoreCandidateQualified':False,'saleQualified':False,'localHeavyBuild':False,'localModelsRun':False,'phoneAccessed':False,'boardAccessed':False}
(C/'audio-ai-checkpoint.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=R/'docs/product_backlog.json';raw=p.read_bytes();d=json.loads(raw);quality=copy.deepcopy(d['quality_targets'])
f=d['owner_module_execution']['frontendWindowsMobile20261102'];b=f['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']
b['audioAiWorkflow20261109']={key:value for key,value in record.items() if key!='ai'}
b['audioAiWorkflow20261109']['ai']={'generationSeconds':record['ai']['generation.json']['nativeProcessFamilySeconds'],'regenerationSeconds':record['ai']['review-regeneration.json']['steps'][3]['seconds'],'manualSourceCorrectionNotAsrImprovement':True,'oldMinutesHistoryRetained':True,'staleMinutesNoticeAndActionExportGuardPassed':True,'checklistSaveReopenAndWordExportPassed':True,'factReviewScope':'One exposed public meeting, selected high-risk facts only; not exhaustive quality or customer acceptance','factsStillOpen':['跨段问题是否已解决','任务负责人/期限不能凭空补齐','原ASR错误需要修订，未提高模型评分'],'evidence':'docs/handoffs/core-acceptance-20261109/ai-22512f1af147477eadece50329a12b93'}
b['currentCheckpoint']['windowsRemaining']='Windows079正常远端构建/包内核对/受影响界面验收；原WinRT系统分享故障与聊天应用附件仍开放。原音/MP3实际保存、Shell粘贴、重导入播放和重开已过；实体实听、手机与板卡按原任务继续。'
b['groupedCandidate079'].update(sourceCommit=freeze['sourceCommit'],remoteReadbackConfirmed=True,buildRun=42587844329,state='GROUPED_WINDOWS079_REMOTE_BUILD_IN_PROGRESS')
assert d['quality_targets']==quality and p.read_bytes()==raw
temp=p.with_suffix('.core-ai-checkpoint.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,p)
log=R/'docs/development_log.md';marker='核心候选同批真实录音与AI整理闭环20261109'
with log.open('a' if marker not in log.read_text(encoding='utf8') else 'r',encoding='utf8') as out:
 if out.writable():
  out.write('\n\n## '+at+'｜'+marker+'\n\n承接Owner“继续集中推进”，沿11月9日原核心候选批次，不新建任务树。实际用户结果：公开S_R004S03C01的38分47秒WAV，经真实078原生导入、开头/中间/结尾媒体播放、系统另存原音与MP3、Windows标准Shell粘贴、MP3重导入/播放、新进程重开通过（run42587058258；验证源af03118156e59a17ad48bae3e54f573c690108be）。原音SHA82ac9f8b25e2c085b2e0434e444727af0577e373ed5e1f587d3f28881862fe2f不变；交付MP3 SHAab2afb6a8a2224eff4e74eb1ca3f8d03921fecdf2a7ba1c588f494bad5e1e39e，重新导入2327170ms。媒体运行时静音；定位探针为currentTime，不代替实体实听和原生拖动条。远端普通系统对话框有输入，Owner键鼠/前台未用；未自动发送。\n\n同一公开会议现有9196字转写，经原生078和已有AI服务完成全部2/2源段，30.817秒；这是转写文字到纪要的耗时，不是音频转写速度。对照公开人工标注发现工作日/零食区两处ASR错误会进入初版AI；明确人工修订单独保存后，旧纪要显示来源变化、旧待办导出拒绝、28.264秒重新整理、初版历史保留、新版导出通过。原ASR文字/说话段未覆盖，未改变模型评分。真实AI待办勾选/新进程重开/Word交付/撤销通过；未声称业务事项真正完成。金额、优惠条件等仅做选点事实审阅，不能据此报整体准确率或客户合格；任务负责人/日期未知继续为空，跨段问题是否已解决仍开放。\n\n同批修复：顶部导出分享定位到所选内容；顶部直达录音导出；无最终文字时不展示不可用AI工作区，明确先转文字；会中问题不擅自标作待解。受影响源码类型/交互检查过（run42584662552），目前仅源码，尚未安装。已冻结0.1.79源'+freeze['sourceCommit']+'并远端读回，正常优化构建run42587844329进行中。本机此前真实低内存仍按停止本机重构建处理，没有关闭Owner程序或改分页；本轮原生AI轻量进程作业5%CPU/128MiB上限，实际私有提交峰约7–9MiB。\n\n失败保留：草稿下载403、原生Open按钮歧义、另存路径未提交、初始库加载时序、对话框WaitForInputIdle未实现、隐藏分享按钮定位误判，均按具体原因修验收工具；Save As由独占远端对话框正常文件名输入完成后验证实际文件，不把这些当产品ASR/功能进展。旧源、旧安装078和每次失败保持，音频二进制留私有草稿/CI，公开文字/收据/截图入Git。没有手机、板卡、本地模型或新客户体验。原WinRT系统分享、聊天附件、模型/实体/整机售卖门保持开放。下一项仍是本批079包内核对与实际界面确认，随后双端/录音卡原待办。\n')
dest=S/'docs/handoffs/core-acceptance-20261109';mapping=json.loads((dest/'evidence-path-map.json').read_text(encoding='utf8'));rename={e['original']:e['mirror'] for e in mapping['entries']}
for p in C.rglob('*'):
 if not p.is_file() or p.suffix not in allowed or '.private' in p.name or '__pycache__' in p.parts:continue
 rel=p.relative_to(C).as_posix()
 if '/ci-artifact/' in '/'+rel or 'public-audio-output/' in rel:continue
 mirrored=rename.get(rel,rel)
 if rel.startswith(('audio-ci-','ui-ci-')):
  parts=mirrored.split('/')
  parts=['artifact' if item.startswith(('companion-core-audio-','companion-core-ui-')) else item for item in parts]
  for i,item in enumerate(parts):
   if i and parts[i-1]=='workflow-evidence' and len(item)==32:parts[i]='case-'+item[:8]
  mirrored='/'.join(parts)
 if mirrored!=rel and rel not in rename:
  entry={'original':rel,'mirror':mirrored,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()};mapping['entries'].append(entry);rename[rel]=mirrored
 q=dest/mirrored;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
(dest/'evidence-path-map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for p in [R/'docs/product_backlog.json',log]:shutil.copyfile(p,S/'docs'/p.name)
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'))
scope={'os':os,'subprocess':subprocess,'env':{**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'<approved-publisher>','exec'),scope)
head=scope['ship'](S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/core-acceptance-20261109'],'Preserve the real audio round trip and source-reviewed AI minutes within the core candidate batch')
print(json.dumps({'state':record['state'],'remoteEvidenceCommit':head,'remoteReadbackConfirmed':True,'wholeCoreCandidateQualified':False},ensure_ascii=False))
