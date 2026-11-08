"""Preserve a demonstrated provider contract repair without promoting model quality."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,shutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';C=R/'docs/handoffs/20261108-competitive-sale-standard';B=C/'async-speaker-contract-r2';EV=M/'evidence/20261108-competitive-sale-standard';DEST=S/'docs/handoffs/model-competitive-sale-standard-20261108';W=Path(__file__).parent
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
publisher=S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py';functions=[n for n in ast.parse(publisher.read_text(encoding='utf8')).body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']];exec(compile(ast.Module(body=functions,type_ignores=[]),str(publisher),'exec'),globals())
source='apps/windows/src-tauri/src/backend/volcengine.rs'
assert not git(M,'status','--porcelain')
assert git(S,'diff','--name-only').splitlines()==[source]
before=read(C/'prefix-quality-review.json');after=read(B/'prefix-quality-review.json');p1=read(C/'prefix-protocol.json');p2=read(B/'prefix-protocol.json');native=read(B/'native-module-check.json');run=read(B/'prefix-run.json')
assert p1['audioSha256']==p2['audioSha256'] and sha(S/source)==native['sourceSha256']==p2['productSourceSha256']
assert native['state']=='ACTUAL_PROVIDER_MODULE_CHECK_PASSED' and run['state']=='COMPLETE_PUBLIC_PREFIX_REFERENCE_ASR_REVIEW_REQUIRED'
assert run['wireRequestWithoutCredentials']['enable_nonstream'] is True and run['wireRequestWithoutCredentials']['ssd_version']=='200'
assert before['cpCer']['predictedTextStreams']==1 and after['cpCer']['predictedTextStreams']==7
assert not after['saleQualified'] and not after['strictWindowCerBelow5']
source_commit=ship(S,[source],'Fix async ASR speaker contract and bind corrected request to cache')
at=datetime.now().astimezone().isoformat(timespec='seconds')
fix={'at':at,'state':'ASYNC_SPEAKER_CONTRACT_FIXED_REAL_MULTILABEL_GAIN_MODEL_QUALITY_OPEN','officialContract':'https://docs.volcengine.com/docs/doubao-voice/large-model-streaming-automatic-speech-recognition-api-1?lang=en','rootCause':'Existing bigmodel_async request asked for speaker info but explicitly disabled the required second pass and omitted ssd_version200. Fix both documented prerequisites together, not a threshold search.','sourceCommit':source_commit,'sourceSha256':sha(S/source),'productSourceCheckout':str(S),'primaryEditableSourceMerged':False,'primaryMergeReason':'Primary recovered-software050 has a separate in-progress Cargo.toml edit; retain isolated source repair and verified remote commit for integration rather than overwrite its branch.','controlledChange':p2['controlledChange'],'audioSha256':p2['audioSha256'],'audioSeconds':p2['audioSeconds'],'referencePeople':6,'referenceOverlapFraction':after['referenceOverlapFraction'],'predictedGroupsBefore':1,'predictedGroupsAfter':7,'cpCerBefore':before['cpCer']['characterErrorRate'],'cpCerAfter':after['cpCer']['characterErrorRate'],'cpCerLimits':'Anonymous minimum permutation diagnostic on one deliberately difficult development window; includes missed and wrongly grouped words, not ordinary ASR accuracy, not known real identity or pure-overlap wordCER. Before exceeds100% because all other person streams are unmatched.','afterEdits':after['cpCer']['edits'],'perPerson':after['perReferencePerson'],'timingBefore':before['timing'],'timingAfter':after['timing'],'sameAudioSameAccountResourceEndpoint':True,'originalSeedNostreamRequestUnchanged':True,'cacheIdentityIncludesNewRequest':True,'actualModuleCheck':native,'fullAppTestBuild':read(B/'native-test.json'),'fullAppBuildPassed':False,'buildFailureScope':'Full-app test rustc allocation failed at bounded2GiB. Source module itself compiled and executed assertions successfully in an exact byte-copy of its normal module layout; first absolute-path harness failed module lookup and is retained.','localModelWeightsOrBaselineChanged':False,'privateAudioUploaded':False,'installed':False,'qualityQualified':False,'saleQualified':False,'finalHoldoutOpened':False,'next':'保留已实测修正的async请求与缓存身份，作为已找到的接入缺口；当前6人分7组且逐人联合CER36.31%，不扩大近实时整会或盲调。下一步用现有原音/响应按时间拆分003-F和007-M短发言的漏词、串人及识别错误，先分清身份错误与声音内容丢失；原20200707_L_R001S08C01中002/003/007参考身份复核工作保留。只在明确根因变化后验证新候选，原普通<5%、分人<=10%、重叠逐人<5%、事实、双端实卡和售卖门不变。Windows完整构建/主源码合入和日用安装仍待，不以本模块检查代替交付。'}
write(B/'repair-result.json',fix)
assessment=read(C/'assessment.json');assessment['asyncSpeakerContractRepair20261108']=fix;assessment['state']=fix['state'];assessment['next']=fix['next'];assessment['actualSourceRepairProven']=True;assessment['capabilityImprovementProven']=False;write(C/'assessment.json',assessment)
metric=read(C/'metric-review.json');metric['actualSourceRepair20261108']={'sourceCommit':source_commit,'result':str(B/'repair-result.json'),'saleQualified':False};write(C/'metric-review.json',metric)
protocol=read(C/'benchmark-protocol.json');protocol['metricInterpretation']=metric;protocol['executionEvidence20261108']['asyncContractRepair']=str(B/'repair-result.json');write(C/'benchmark-protocol.json',protocol)
old_initial=read(C/'prefix-protocol-initial-not-inferred.json');archived=Path(old_initial['audio']).with_name('initial-ordinary-not-inferred.wav');assert sha(archived)==old_initial['audioSha256'];write(C/'initial-not-inferred-audio-archive.json',{'audio':str(archived),'sha256':sha(archived),'notInferred':True})
for file in C.rglob('*'):
 if file.is_file():
  dest=EV/file.relative_to(C);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
scripts=['probe_existing_companion_asr_20261108.py','prepare_companion_commercial_prefix_20261108.py','run_companion_commercial_prefix_20261108.py','score_companion_commercial_prefix_20261108.py','check_companion_async_contract_native_20261108.py','check_companion_async_module_20261108.py','preserve_companion_async_repair_20261108.py']
for name in scripts:shutil.copyfile(W/name,EV/name)
attr=M/'.gitattributes';content=attr.read_text(encoding='utf8');line='evidence/20261108-competitive-sale-standard/** -text -whitespace'
if line not in content:attr.write_text(content+'\n'+line+'\n',encoding='utf8')
model_commit=ship(M,['.gitattributes','evidence/20261108-competitive-sale-standard'],'Preserve same-audio repair of missing async diarization prerequisites')
assessment['sourceAndEvidenceCommit']=model_commit;assessment['remoteReadbackConfirmed']=True;write(C/'assessment.json',assessment)
path=R/'docs/product_backlog.json';d=read(path);quality=d['quality_targets'];oldlog=(R/'docs/development_log.md').read_bytes()
def task(d):return d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
for attempt in range(8):
 raw=path.read_bytes();d=json.loads(raw);n=task(d);assert n['ownerCompetitiveSaleStandard20261108']['sourceAndEvidenceCommit']=='92b4e0ce7b769012b9042561d3c51d2736570dc6';n['ownerCompetitiveSaleStandard20261108']=assessment;n.update(status=fix['state'],next=fix['next']);temp=path.with_suffix('.async-repair.tmp');write(temp,d)
 if path.read_bytes()!=raw:temp.unlink();continue
 try:os.replace(temp,path);break
 except PermissionError:temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2))
else:raise RuntimeError('Original backlog busy; code and evidence already preserved')
assert read(path)['quality_targets']==quality
marker='原模型任务async多人请求源头修正20261108';log=R/'docs/development_log.md';assert marker.encode('utf8') not in log.read_bytes()
entry='\n\n## '+at+'｜'+marker+'\n\n续作同一指标复核发现：官方async多人契约要求enable_nonstream=true及ssd_version200，原请求缺失；修正Windows候选源码，缓存身份随有效请求改变，原Seed nostream路径保留。同账号/资源/端点/完全相同302.05秒真实音频重跑一次：原37句全部人物0，修正后7组/6参考；逐人联合cpCER115.8362%→36.3140%（含身份塌缩与未匹配流错误，不是普通ASR率），仍未达5%。实际发送+服务耗时328.4898→331.5005秒，100ms近实时发送，不作极速批处理/停录等待成绩；进程私有内存峰23,445,504→23,842,816B，无本地模型训练/GPU任务。完整Windows测试编译在2GiB限制内rustc内存分配失败保留；复用确切生产模块字节、正常目录布局做独立编译/执行，请求及缓存/Seed路径断言通过；首次独立绝对路径harness找子模块失败同样保留，不增加内存反复编整应用。未合入另有Cargo修改的主编辑分支、未安装日用版、全构建/双端实卡及售卖门仍开放。源码'+source_commit+'、证据'+model_commit+'均已远端核验。下一项：'+fix['next']+'\n'
with log.open('ab') as f:f.write(entry.encode('utf8'))
assert log.read_bytes().startswith(oldlog)
for file in [path,log]:shutil.copyfile(file,S/'docs'/file.name)
for file in C.rglob('*'):
 if file.is_file():
  dest=DEST/file.relative_to(C);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
for name in scripts:shutil.copyfile(W/name,DEST/name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-competitive-sale-standard-20261108'],'Record real async speaker repair and remaining complex meeting errors')
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':fix['state'],'sourceCommit':source_commit,'modelCommit':model_commit,'mainCommit':main,'remoteReadbackConfirmed':True,'originalQualityTargetsUnchanged':read(path)['quality_targets']==quality,'timelinePrefixPreserved':log.read_bytes().startswith(oldlog),'workingTreesClean':all(not git(repo,'status','--porcelain') for repo in [M,S]),'next':task(read(path))['next'],'sourceRepairProven':True,'modelSaleQualified':False,'installed':False}
write(B/'preservation-result.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
