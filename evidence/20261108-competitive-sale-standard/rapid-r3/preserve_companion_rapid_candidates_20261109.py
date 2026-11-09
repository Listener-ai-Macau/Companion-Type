"""Publish the bounded experiments and next executable pilot, preserving failures."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast,hashlib,json,os,shutil,subprocess,sys,time,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';W=Path(__file__).parent;H=R/'docs/handoffs';C=H/'20261109-sedicow-r1';F=H/'20261109-firered2-cpu-r1';P=H/'20261109-overlap-marginal-r1';EV=M/'evidence/20261108-competitive-sale-standard/rapid-r3';DEST=S/'docs/handoffs/model-rapid-r3-20261109'
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
publisher=S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py';functions=[n for n in ast.parse(publisher.read_text(encoding='utf8')).body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']];exec(compile(ast.Module(body=functions,type_ignores=[]),str(publisher),'exec'),globals())
assert not git(S,'status','--porcelain')
sources=[M/'src'/name for name in ['companion_local_overlap_regions_20261109.py','test_companion_overlap_posterior_20261109.py','companion_firered2_cpu_worker_20261109.py','companion_sedicow_checkpoint_20261109.py','companion_sedicow_conditioning_20261109.py','companion_sedicow_decode_trace_20261109.py','companion_sedicow_gpu_worker_20261109.py','test_companion_sedicow_conditioning_20261109.py']]
upstream=Path(read(C/'source.json')['sourceRoot']);expected={'M src/companion_local_overlap_regions_20261109.py'}|{'?? '+str(p.relative_to(M)).replace('\\','/') for p in sources if p.name!='companion_local_overlap_regions_20261109.py'}|{'?? '+str(upstream.relative_to(M)).replace('\\','/')+'/'}
assert {line.strip() for line in git(M,'status','--porcelain').splitlines()}==expected
scripts=[W/name for name in ['companion_overlap_marginal_trial_20261109.py','prepare_companion_firered2_20261109.py','run_companion_firered2_cpu_20261109.py','run_companion_firered2_isolated_20261109.py','prepare_companion_sedicow_20261109.py','download_companion_sedicow_weights_20261109.py','prepare_companion_sedicow_inputs_20261109.py','probe_companion_sedicow_runtime_20261109.py','probe_companion_sedicow_checkpoint_20261109.py','check_companion_sedicow_runtime_dependencies_20261109.py','run_companion_sedicow_pilot_20261109.py','finalize_companion_rapid_candidates_20261109.py','preserve_companion_rapid_candidates_20261109.py']]
decision=read(C/'decision.json');probe=read(C/'checkpoint-probe.json');test=read(C/'safety-tests.json');assert probe['state']=='PASS_EXACT_TINY_LOAD_GENERATION_AND_FULL_META_HEADER' and probe['tinyParameterCount']==1687409 and test['successful'] and test['tests']==13
assert read(C/'pilot-controller.json')['state']=='DEFERRED_NO_CONNECTED_6800XT_NO_MODEL_IMPORTED'
protocol=read(C/'gpu-protocol.json');assert sha(protocol['worker'])==protocol['workerSha256'] and sha(protocol['controller'])==protocol['controllerSha256']
for row in protocol['supportSources']:assert sha(row['file'])==row['sha256']
for p in sources+scripts:compile(p.read_text('utf8'),str(p),'exec')
for name,folder in [('marginal',P),('firered2',F),('sedicow',C)]:
 for p in folder.rglob('*'):
  if p.is_file():target=EV/name/p.relative_to(folder);target.parent.mkdir(parents=True,exist_ok=True);assert len(str(target))<250;shutil.copyfile(p,target)
for p in scripts:shutil.copyfile(p,EV/p.name)
# Public audio and exact model-ready arrays are small and survive routine cache cleanup.
seen=set();items=[]
for row in read(C/'audio-only-inputs.json'):
 for key in ['originalAudio','enrollmentAudio','modelInputs']:
  file=Path(row[key]);digest=sha(file);assert digest==row[key+'Sha256']
  if digest in seen:continue
  seen.add(digest);items.append({'originalPath':str(file),'member':file.name,'sha256':digest,'bytes':file.stat().st_size})
archive=EV/'public-inputs.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for row in items:z.write(row['originalPath'],row['member'])
with zipfile.ZipFile(archive) as z:
 for row in items:assert hashlib.sha256(z.read(row['member'])).hexdigest()==row['sha256']
write(EV/'public-inputs-index.json',{'files':items,'archiveSha256':sha(archive),'archiveBytes':archive.stat().st_size,'source':'AISHELL4/OpenSLR111 https://www.openslr.org/111/ CC-BY-SA4.0; originalauthors/corpus attribution retained. Only publicdevelopmentaudio, no privatecontent.','derivedFeatures':'ExactpinnedWhisperprocessor; originalmain30s andsixautomaticenrollment30s plusfloat32features/STNO arrays. No referencewords/IDs in inference.','noWeightsInGit':True,'weightRecovery':'Official pinned URLs, bytecounts andSHA256 in source.json/model-ready.json; >GBweights remainrecoverableEcache, not claimedGitbackup.'})
write(EV/'reproducibility-index.json',{'sources':[{'file':str(p),'sha256':sha(p)} for p in sources+scripts],'originalGenerationNotChanged':True,'decodeTraceObserver':'Originalsampler called withidenticalargs; rawresult copiedwithoutlogitsretention. Authorreturned timestamprebuilttokens recordedseparately.','tinyLoadFix':'Firstpassingprobe showedassign=TruelostsharedParameteridentity thoughbytes/forwardequal. Restoredauthor tie_weights, rerunverifiedexactparams/logits/parametercount1687409. Beforefixresult andactualLOWRAM stop retained. Full957tensorheader(+onealias) checkedonmeta, norealCPUweightload.','safetyTests':test,'gpuPreflight':read(C/'pilot-controller.json'),'finalHoldoutOpened':False,'newProductDelivery':False,'saleQualified':False})
attrs=M/'.gitattributes';text=attrs.read_text('utf8')
for rule in ['src/*sedicow*20261109.py -text','src/companion_firered2_cpu_worker_20261109.py -text','src/test_companion_overlap_posterior_20261109.py -text']:
 if rule not in text:text+='\n'+rule+'\n'
attrs.write_text(text,encoding='utf8')
model=ship(M,['.gitattributes']+[str(p.relative_to(M)).replace('\\','/') for p in sources]+[str(upstream.relative_to(M)).replace('\\','/'),str(EV.relative_to(M)).replace('\\','/')],'Validate overlap alternatives and stage exact self-enrolled target ASR pilot')
for p in sources+list(upstream.iterdir()):
 if not p.is_file():continue
 blob=subprocess.run(['git','show',model+':'+str(p.relative_to(M)).replace('\\','/')],cwd=M,capture_output=True,check=True,env=env).stdout;assert hashlib.sha256(blob).hexdigest()==sha(p)
at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds');path=R/'docs/product_backlog.json';log=R/'docs/development_log.md';initial=read(path);quality=initial['quality_targets'];prefix=log.read_bytes()
def task(d):return d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
record={'at':at,'ownerQuote':'那看着好像有一点进展, 那接下来要怎么搞, 我想你看看研究, 快点搞好这个事情, 速速尝试可能成功的方向','state':decision['state'],'previousStatus':task(initial)['status'],'previousWorkpoint':task(initial)['next'],'modelEvidenceCommit':model,'remoteReadbackConfirmed':True,'source':str(C),'marginalProbabilityTrial':read(P/'result.json'),'restoredFireRed2':read(F/'paired-review.json'),'newCandidateSource':{'model':read(C/'source.json')['model'],'revision':read(C/'source.json')['revision'],'license':'apache-2.0','noAccountGate':True,'pretrainedInferenceRun':False,'inputReady':read(C/'input-ready.json'),'checkpointProbe':probe,'runtimeDependencies':read(C/'runtime-dependencies.json'),'gpuPreflight':read(C/'pilot-controller.json')},'decision':decision,'ordinaryBestStrictCerUnchanged':461/8325,'newProductInstalled':False,'formalQualityTargetsChanged':False,'finalHoldoutOpened':False,'saleQualified':False,'next':decision['next']};write(C/'preservation-result.json',record)
for attempt in range(8):
 raw=path.read_bytes();d=json.loads(raw);n=task(d);n['ownerCompetitiveSaleStandard20261108']['rapidArchitectureCandidates20261109']=record;n.update(status=decision['state'],next=record['next']);n['ownerCompetitiveSaleStandard20261108']['next']=record['next'];temp=path.with_suffix('.rapid-r3.tmp');write(temp,d)
 if path.read_bytes()!=raw:temp.unlink();continue
 try:os.replace(temp,path);break
 except PermissionError:temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2))
else:raise RuntimeError('Originalbacklogbusy; modelsourceandevidencealreadyremote')
assert read(path)['quality_targets']==quality
marker='原模型快速架构候选与内容回归复验20261109';assert marker.encode('utf8') not in prefix
entry='\n\n## '+at+'｜'+marker+'\n\n承接Owner要求加快尝试可能成功方向。无外置6800XT，串行CPU/缓存做有判别力的小验证，未把整会Qwen/native人物压CPU。三真实开发会议固定powerset双人后验求和、同窗均值/0.5决策一次对照：复杂L与native并集误报109.041→101.740s、召回82.9594→82.9921%，第三场独立召回38.9270→34.6378%，不推广、不扫阈值。恢复官方FireRed2 AED int8同旧20260226权重，最初误认旧v1已在新推理前查源码纠正且向Owner明说，不记为新模型。30s在2GiB任务内存限额ScatterND80MiB申请失败；改同固定六8s，第一段成功、连续第二段Concat16MiB申请失败；保留失败，继承首段、剩余5段各新进程完成(93.171s含各次加载、采样私有峰约2.140..2.144GB接近2GiB)，诊断可跑不代表生产快。原音挺普遍、分离native1仍读交通便的，native3仍对或者就是那些，与旧另一ASR相似内容回归，支持优先绕开波形重建查逐人ASR，不冒充同Qwen严字错提升或听感定论；原同Qwen六段控制保留未做。选一个真正不同公开候选：官方推荐SE-DiCoW(连字符版，旧下划线版明确弃用)，Apache2免账号，470fce9ffff844dd53a27751cdf6c6df9efecb39固定源码与4.407GB原F32权重SHA核验下载，不使用捆绑非商用DiariZen。复用原native全部8头软活动得到S/T/N/O，作者公式实值最大差5.96e-8；原真实1560..1590s30秒、6人物各自动最大单人活动30秒参考(避开原query区)，主音不分离、不读答案/参考人物数，先人物1/2/3小对照。现有普通Qwen5.53754%未变。独立transformers4.55依赖不改全局，补齐AMD环境缺的pandas；tiny随机模型精确权重16MiB流式往返/逐权重/forward完全一致，修assign后共享Parameter身份、最终1687409参数；生成小样本强制token只验API不记识别成绩，原始greedyIDs单独捕获与作者重建时间戳输出分开核EOS/死循环，省略仅labels训练才使用的平滑矩阵。真模型957张量+1共享alias只读113112B头/全meta结构核对，0真实预训练tensor载CPU。中间实际WindowsLOWRAM在加载前停(当时全机可用约325MB)，未动用户程序，信号自然解除后最终tiny复验18.726s/任务私有峰416133120B通过；失败和修前结果均保留。控制器实测只780M时不导入模型，单模型5%CPU/2GiB任务、实际LOWRAM/子家族退出、按型号选6800XT、无CPU/集显回退，未承诺GPU利用率硬限额。13条相关输入/源帧保留/人物不编造安全检查过，均非新模型准确率。源码/小公开输入压缩/模型恢复hash/原始结果/失败和决定'+model+'已远端核验，GB权重在E缓存可按固定源恢复、不冒充Git备份。没有新预训练模型真实识别、没有安装/日用默认变化、没有最终留出、没有新售卖门关闭。下一项：'+record['next']+'\n'
with log.open('ab') as f:f.write(entry.encode('utf8'))
for p in [path,log]:shutil.copyfile(p,S/'docs'/p.name)
# Mirror complete evidence after modelcommit exists, with sourcecommit receipt.
for p in EV.rglob('*'):
 if p.is_file():target=DEST/p.relative_to(EV);target.parent.mkdir(parents=True,exist_ok=True);assert len(str(target))<250;shutil.copyfile(p,target)
shutil.copyfile(C/'preservation-result.json',DEST/'preservation-result.json')
attrs=S/'.gitattributes';text=attrs.read_text('utf8');rule='docs/handoffs/model-rapid-r3-20261109/** -text -whitespace'
if rule not in text:attrs.write_text(text+'\n'+rule+'\n',encoding='utf8')
main=ship(S,['.gitattributes','docs/product_backlog.json','docs/development_log.md',str(DEST.relative_to(S)).replace('\\','/')],'Record rejected overlap shortcut and ready self-enrolled ASR pilot without accuracy claim')
assert not git(M,'status','--porcelain') and not git(S,'status','--porcelain')
print(json.dumps({'modelCommit':model,'mainCommit':main,'remoteReadbackConfirmed':True,'qualityTargetsUnchanged':read(path)['quality_targets']==quality,'timelinePrefixPreserved':log.read_bytes().startswith(prefix),'next':task(read(path))['next'],'modelSourceClean':True,'saleQualified':False},ensure_ascii=False),flush=True)
