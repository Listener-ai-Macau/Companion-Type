"""Preserve actual two-lane results in existing model task and sole timeline."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast,hashlib,json,os,shutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';W=Path(__file__).parent
C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109';EV=M/'evidence/20261108-competitive-sale-standard/two-lane-validation-20261109';DEST=S/'docs/handoffs/model-competitive-sale-standard-20261108/two-lane-validation-20261109'
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
publisher=S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py';functions=[n for n in ast.parse(publisher.read_text(encoding='utf8')).body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']];exec(compile(ast.Module(body=functions,type_ignores=[]),str(publisher),'exec'),globals())
assert not git(S,'status','--porcelain')
sources=[M/'src'/name for name in ['automatic_speaker_cpu_worker_20261109.py','automatic_speaker_extraction_cpu_20261109.py','companion_meeting_route_plan_20261109.py','test_companion_meeting_route_plan_20261109.py']]
assert set(git(M,'status','--porcelain').splitlines())=={'?? '+str(p.relative_to(M)).replace('\\','/') for p in sources},'Preserve other work before publishing; unexpected dirty paths'
scripts=[W/name for name in ['prepare_companion_two_lanes_20261109.py','score_companion_automatic_profiles_20261109.py','prepare_companion_ordinary_full_20261109.py','prepare_companion_overlap_cpu_20261109.py','run_companion_separation_asr_20261109.py','probe_existing_companion_asr_20261108.py','review_companion_two_lanes_20261109.py','preserve_companion_two_lanes_20261109.py']]
result=read(C/'result.json');assert result['pairedAsr']['requests']==6 and not result['saleQualified']
assert read(C/'paired-content-review.json')['cases'][1]['recognition']['overlap-01-native-2']['wordOnlySentenceFallbackUsed']
write(C/'failure-notes.json',{'amdRuntimeCpuAttempt':{'state':'FAILED_DURING_NUMERICAL_IMPORT_BEFORE_FIRST_NEURAL_CALL','symptom':'OpenBLAS allocation failed after10retries under2GiB worker-private cap; initial result preserved as encoder-result-amd-runtime-failed-r1.json. No model inference/training performed on this attempt.','resolution':'Use existing native CPU torch2.12.0+cpu for a CPU-only task; same2GiB cap, pinnedcheckpoint and inputs. No new package, raised limit, or other-app change.'},'scoringRuntimeAttempt':{'state':'PY_PRAATIO_MISSING','resolution':'Use existing clean scoring runtime and same maintained parser. No parser/reference or test-input changes.'},'initialPowerShellPipeline':{'state':'BUILTIN_UTILITY_MODULE_UNAVAILABLE','resolution':'Pass Python code directly or run an exact script file; do not reinstall/change host shell.'},'productQualified':False})
source_manifest=[{'file':str(p),'sha256':sha(p)} for p in sources+scripts+[M/'src/companion_tse_reference_bank_20261108.py',M/'src/companion_word_journal_join_20261109.py']]
write(C/'reproducibility-sources.json',{'files':source_manifest,'nativeCpuTorch':'2.12.0+cpu','audioOnlyInputsAndReferenceScoringSeparate':True,'schemaTests':'4route preservation tests passed; this is safety evidence, not modelaccuracy progress.'})
for p in C.rglob('*'):
 if p.is_file():target=EV/p.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
for p in scripts:shutil.copyfile(p,EV/p.name)
# Keep small public derived audio remotely, not only in a disposable cache.
audio=[];base=read(C/'audio-only.json')
for kind in ('profiles','queries','calibration'):
 for row in base[kind]:audio.append((kind+'/'+row['id']+'.wav',Path(row['audio'])))
for row in read(C/'overlap-audio-only.json')['cases']:audio.append(('mixtures/'+row['id']+'.wav',Path(row['audio'])))
for row in read(C/'extraction-result.json')['outputs']:
 for key in ('rawFloatAudio','pcmAudio'):audio.append(('extracted/'+Path(row[key]).name,Path(row[key])))
index=[]
for relative,source in audio:
 target=EV/'public-audio'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);assert sha(target)==sha(source);index.append({'originalPath':str(source),'archivedRelativePath':'public-audio/'+relative,'bytes':source.stat().st_size,'sha256':sha(source)})
write(EV/'archived-audio-index.json',{'license':'Derived fromAISHELL4/OpenSLR111, CC-BY-SA4.0; originalcorpus authors/attribution/source descriptions retained. PS4author originalcheckpoint Apache2.0 modelcard withupstreamcomponent licenses. Publicdevelopment audio only, no private content.','source':'https://www.openslr.org/111/','derivation':'Original PCM channel1 crops and originalPS4 speaker-conditioned float/PCM outputs. Exact sample bounds, sourceSHA and modelSHA in manifests. Reference/transcripts are not inference input.','files':index,'totalBytes':sum(r['bytes'] for r in index)})
attrs=M/'.gitattributes';with_attrs=attrs.read_text(encoding='utf8');newattrs='\n# Preserve byte-bound CPU speaker and two-lane routing sources (2026-11-09).\nsrc/automatic_speaker_*20261109.py -text\nsrc/*companion_meeting_route_plan_20261109.py -text\n'
if 'src/automatic_speaker_*20261109.py -text' not in with_attrs:attrs.write_text(with_attrs+newattrs,encoding='utf8')
model=ship(M,['.gitattributes']+[str(p.relative_to(M)).replace('\\','/') for p in sources]+[str(EV.relative_to(M)).replace('\\','/')],'Validate automatic speaker references and reject unsafe separation with real paired audio')
for p in sources:
 blob=subprocess.run(['git','show',model+':'+str(p.relative_to(M)).replace('\\','/')],cwd=M,capture_output=True,env=env,check=True).stdout
 assert hashlib.sha256(blob).hexdigest()==sha(p),'Remote source byte binding must remain reproducible'
path=R/'docs/product_backlog.json';log=R/'docs/development_log.md';old=read(path);quality=old['quality_targets'];prefix=log.read_bytes();at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
def task(d):return d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
record={'at':at,'ownerQuote':'普通会议和复杂多人分开处理，继续推进；目前进度太慢、完全不满意。','state':result['state'],'modelEvidenceCommit':model,'remoteReadbackConfirmed':True,'previousWorkpoint':task(old)['next'],'currentDevice':'OnlyconnectedAMD780M; external6800XT absent inPnP. No wholeQwenCPU fallback.','ordinary':{'bestRetainedStrictCer':461/8325,'newFullMeeting':result['ordinaryMeeting'],'wholeRunStarted':False,'sourcePreviouslyUsedForTseValidation':True,'finalHoldout':False,'allOriginalChannelSamplesBitExact':True,'sameFrozenModelAndParameters':True,'newAccuracyGainClaimed':False},'complex':{'automaticProfiles':17,'nativePeople':6,'disjointAutomaticQueryClips':22,'agreesWithJournal':19,'matchesDominantReference':19,'referencePureAt95Percent':20,'referenceAndJournalNotAlwaysCorrect':'q000iswronglyjournaled0butreference006M; encoderalsofailed. q006encoderfixedajournalgroupbutq021ispredictedsoloandactuallyoverlap; allretained. Sameexposedmeeting,notDER/independentgeneralization.','cpuEncoderSeconds':result['encoder']['elapsedSeconds'],'cpuEncoderPeakPrivateBytes':result['encoder']['limits']['jobPeakPrivateCommitBytes'],'cpuVsPriorGpuCalibrationCosine':result['encoder']['calibration']['cpuVsPreviousGpuCosine'],'targetedSeparationOutputs':4,'selectedSourceWindowSeconds':16,'targetStreamSeconds':32,'cpuSeparationSeconds':result['extraction']['elapsedSeconds'],'cpuSeparationPeakPrivateBytes':result['extraction']['limits']['jobPeakPrivateCommitBytes'],'authorDirectEmbeddingBranchWaveformDifference':0,'clippedPcmSamples':0,'sameExistingCloudAsrCalls':6,'publicUploadedSeconds':48,'sameExistingCloudAsrWallSeconds':result['pairedAsr']['wallSeconds'],'decision':'Do not promote. Paired realaudio shows lexicalcorruption/crosstalk, e.g whollycontained挺普遍的→交通便利 in targetstream. Another对有的就是一些 remainsincorrect. Word-only output这就是本校区呗 retained by existingfallback; no falseempty. Need samefrozenQwen comparison beforepositiveclaim.','formalPureOverlapCerMeasured':False,'reasonNoFormalCer':'8scontext crosses referenceutterances andother peopleoutsidecentralpair. No goldwordtimes, no fabricatedpartialreference.'},'routePlan':{'sourceFramesCoveredExactlyOnce':True,'sourceSecondsByRoute':result['routesSeconds'],'ordinaryBypassesSeparation':True,'noActivityAudioRetained':True,'overlapRawRetainedAndCandidateNotPromoted':True,'researchBackendImplemented':True,'integratedProductDefault':False},'failuresRetained':['AMDCPUruntimeOpenBLASimportallocationfailurebeforefirstmodelcall→existingCPUtorch/samecap','PYmissingPraatIO→existingcleanSC/scorerunchanged','separationcontentregressionsinbothselectedoverlapcases'],'resources':'SingleCPUmodel at a time,5%WindowsCPU jobhardcap,2GiBmodelprivatecap; actualLOWRAMstop. No training/newweights/GPUjob/otherapptermination/pagefilechange. Existingauthorizedservice/publicaudio only, no newpaidservice.','publishedPublicAudioBytes':sum(r['bytes'] for r in index),'qualityTargetsUnchanged':True,'weightsChanged':False,'installedOrProductDefaultChanged':False,'saleQualified':False,'next':result['next']}
write(C/'preservation-result.json',record)
for attempt in range(8):
 raw=path.read_bytes();d=json.loads(raw);node=task(d);node['ownerCompetitiveSaleStandard20261108']['twoLaneValidation20261109']=record;node['next']=record['next'];node['ownerCompetitiveSaleStandard20261108']['next']=record['next'];temp=path.with_suffix('.two-lanes.tmp');write(temp,d)
 if path.read_bytes()!=raw:temp.unlink();continue
 try:os.replace(temp,path);break
 except PermissionError:temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2))
else:raise RuntimeError('Original backlogbusy; source/evidencealreadyremote')
assert read(path)['quality_targets']==quality
marker='原模型普通与复杂分线真实CPU和同音对照20261109';assert marker.encode('utf8') not in prefix
entry='\n\n## '+at+'｜'+marker+'\n\nOwner要求普通会议与复杂多人分开、加快实际推进。研究后端实现按预测活动分路，39m23s原会议全部样本恰一次覆盖：普通原音1903.3499375s、未标语音仍保留280.9750625s、预测重叠候选178.62s；普通不经过分离，候选始终留原音、不默认替换。原17段自动参考实跑原PS4声纹：22段不重复自动查询中19同日志、19同原标注主说话人，20段>=95%纯语音；每段保留，q021原预测单人实有重叠，不能把86.36%叫整会准确率或DER。CPU共11.613s/私有峰645308416B，旧GPU同音编码cos0.999999999992、最大差3.54e-6。再用预测而非答案选两段8s真实重叠，自动参考驱动四路输出共32s，CPU65.449s/私有峰935010304B，原作者直接向量分支同音波形差0、float回读逐点一致、PCM无削波。用同一现有服务做六次8s原音/分离对照共63.635s，发现挺普遍的→交通便利等串音/内容失真，拒绝候选默认启用；另一路仅words无text仍恢复这就是本校区呗，未丢弃。8s窗跨完整标注边界且含其它人物，无词级真值，未编造纯重叠CER、未宣称字错率提升。当前仅780M无6800XT，不跑整会QwenCPU。36m35.362s真实五人整会完整通道无损导出逐样本一致，原标注重叠135.431s(6.17%音频)；此会以前用于TSE验证，非未见最终集，已固定Qwen1.7B配置/命令但未推理。六段同Qwen短对照已排在整会之前，先快速复核内容保护再扩大，不扫阈值或训练。首次AMD运行库CPU导入触2GiB内OpenBLAS分配失败(零神经调用)及PY缺PraatIO失败保留，改现有纯CPU/清洁评分运行库，同预算不扩内存。4条路由样本安全测试过，属于保护证据，不计模型能力。普通最佳5.53754%未变，原严格<5%/说话人/关键事实/整会/双端实卡/售卖门全保留；无安装、无默认变更。源码/输入/原始响应/失败和'+str(sum(r['bytes'] for r in index))+'B公开小音频'+model+'已远端核验；大整会WAV为可重建缓存，不提交新权重。下一项：'+record['next']+'\n'
with log.open('ab') as f:f.write(entry.encode('utf8'))
for file in [path,log]:shutil.copyfile(file,S/'docs'/file.name)
for file in C.rglob('*'):
 if file.is_file():target=DEST/file.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
for file in scripts:shutil.copyfile(file,DEST/file.name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md',str(DEST.relative_to(S)).replace('\\','/')],'Record ordinary and complex model lanes with actual paired failures and preserved source')
assert not git(M,'status','--porcelain') and not git(S,'status','--porcelain')
print(json.dumps({'modelCommit':model,'mainCommit':main,'remoteReadbackConfirmed':True,'timelinePrefixPreserved':log.read_bytes().startswith(prefix),'qualityTargetsUnchanged':read(path)['quality_targets']==quality,'publicAudioBytesPreserved':record['publishedPublicAudioBytes'],'sourceClean':True,'next':task(read(path))['next'],'saleQualified':False},ensure_ascii=False),flush=True)
