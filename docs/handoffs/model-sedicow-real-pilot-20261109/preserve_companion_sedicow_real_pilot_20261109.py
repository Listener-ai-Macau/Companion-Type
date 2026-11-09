"""Publish actual Chinese target-ASR failure and preserve the unchanged baseline."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast,hashlib,json,os,shutil,subprocess,sys,time,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';H=R/'docs/handoffs';C=H/'20261109-sedicow-r1';W=Path(__file__).parent;EV=M/'evidence/20261108-competitive-sale-standard/sedicow-real-pilot';DEST=S/'docs/handoffs/model-sedicow-real-pilot-20261109'
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
publisher=S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py';functions=[n for n in ast.parse(publisher.read_text('utf8')).body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']];exec(compile(ast.Module(body=functions,type_ignores=[]),str(publisher),'exec'),globals())
assert not git(S,'status','--porcelain')
sources=[M/'src/companion_sedicow_cpu_stream_20261109.py',M/'src/companion_sedicow_cpu_worker_20261109.py']
assert {line.strip() for line in git(M,'status','--porcelain').splitlines()}=={'?? '+str(p.relative_to(M)).replace('\\','/') for p in sources}
scripts=[W/name for name in ['probe_companion_sedicow_cpu_stream_20261109.py','run_companion_sedicow_cpu_20261109.py','score_companion_sedicow_pilot_20261109.py','audit_companion_sedicow_enrollment_20261109.py','prepare_companion_sedicow_author_mask_20261109.py','preserve_companion_sedicow_real_pilot_20261109.py']]
for p in sources+scripts:compile(p.read_text('utf8'),str(p),'exec')
folders=[H/('20261109-sedicow-cpu-r'+str(i)) for i in range(1,6)]+[H/'20261109-sedicow-cpu-r6-author']
results=[]
for i in [2,3,4,5]:
 folder=folders[i];control=read(folder/'controller.json');state=read(folder/'state.json');raw=read(folder/'raw.json');review=read(folder/'review.json');assert control['state']=='COMPLETE' and control['exitCode']==0 and state['state']=='COMPLETE_REAL_CPU_TARGET_ASR_NOT_QUALIFIED';assert raw['naturalEos'] and not raw['loop'] and review['rawSha256']==sha(folder/'raw.json')
 assert raw['checkpoint']['checkpointSha256']==read(C/'source.json')['weight']['sha256'] and not raw['dtypeConversion']
 results.append({'attempt':folder.name,'nativePerson':read(folder/'audio-only.json')['nativePerson'],'conditioning':'author-binary-journal' if i==5 else 'soft-native-posterior','text':raw['text'],'rawSha256':sha(folder/'raw.json'),'recognitionWallSeconds':raw['seconds'],'workerWallIncludingSourceValidationSeconds':state['wallSeconds'],'controllerWallIncludingStartupSeconds':control['wallSeconds'],'polledPrivatePeakBytes':control['privatePeakBytes'],'jobPeakPrivateCommitBytes':state['limits']['jobPeakPrivateCommitBytes'],'strictTargetCer':review['strictTargetCer'],'strictCerOmittedForCrossingUtterance':review['strictCerOmittedForCrossingUtterance'],'naturalEos':raw['naturalEos'],'loop':raw['loop'],'notWholeMeeting':True})
probe=read(C/'cpu-stream-probe.json');assert probe['state']=='PASS_TINY_STREAMED_EAGER_EXACT_SDPA_TOLERANCE' and probe['results'][0]['bitExact']
assert results[1]['strictTargetCer']['totalEdits']==115 and results[1]['strictTargetCer']['referenceCharacters']==30
assert results[2]['strictTargetCer']['totalEdits']==19 and results[2]['strictTargetCer']['referenceCharacters']==23
assert results[3]['strictTargetCer']['totalEdits']==78 and results[3]['strictTargetCer']['referenceCharacters']==30
at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
next_action='本轮最后新增公开候选SE-DiCoW已实跑且未过中文小样本门：不扩整会、不训练、不因独显恢复原样重复。保留原先分离再转写/同Qwen六段对照与普通线<5%任务；独显可用时先执行原已固定六8s同Qwen内容保护对照及第三真实整会普通基线，不再新增模型清单。复杂多人字错/人物/事实仍未合格、不关闭任务、不自行缩减产品范围。后续若继续此类目标人物ASR研究，先解决自动参考混杂和匹配中文数据/训练验证边界，不能假定微调就能修好；原5%及跨会/留出/双端实卡门不改。'
decision={'at':at,'state':'SE_DICOW_REAL_CHINESE_PILOT_FAILED_NO_EXPANSION_OR_TRAINING','ownerQuote':'可以啊，那你看下这个新方案，先试一下呗。然后的话，如果。新方案可以的话，可以自己尝试优化一下他们的模型，看看能不能达到更好的效果。先试一下吧，但是我感觉也是能力有限。诶，这方向不对，再试最后一个吧，这应该是最有方向的吧，希望的方向了吧。','scope':'One previouslyexposed genuineAISHELL4complexmeeting, onefixed30swindow1560..1590, threepredeclaredanonymouspeopleplusoneformatablation. Fourcompleted targetcalls, notfourindependentmeetings, notfullmeetingquality.','model':'BUT-FIT/SE-DiCoW@470fce9ffff844dd53a27751cdf6c6df9efecb39','checkpointSha256':read(C/'source.json')['weight']['sha256'],'results':results,'qualityJudgment':'Do notadoptthischeckpoint/currentautomaticconditioning asChineseproductionbaseline. Native1clearlexicalerrors(挺普遍的→相同间的,门禁卡→门金卡). Native2Chinese→English despiteexplicitzh/transcribe andposthoctarget-onlyenrollment; native3only4/23referencecharsdecoded. Singleauthorbinarymaskcontrolnative2stillEnglish, so merelyreplacingsoftwithhardtimestampmaskdoesnotresolveit. DoesnotprovealltargetspeakerASRarchitecturesorChineseadaptationimpossible; doesnotisolatefullcausewithoutfurthercontrols.','ownerConditionalOptimization':'Ownerallowedoptimizationifnewrouteuseful. Currentpilotdidnotestablishusefulness; doNOTlaunchLoRA/fulltraining orspendlargecomputebudget ontheassumptionitwillfixthis. Treatthisasthelastnewmodelcandidateinthisbatch.','referenceCorrection':'Previouspreparationtextcallednative0/4/5absent; scoringreferenceactuallyhasnative4/5speech, only0absent. Correctedbeforequalityjudgment, inputsunaltered. Native1hasoneutterancecrossing1590s, soformalCERisnullinsteadofassigningpartialwords. Native2/3allreferenceutterancescontained, strict30sper-targetscoresvalidbuttiny/notwholemeeting.','referencePurity':'Automatic30sreferenceaudit: native1targetexclusivespeech/anyspeech94.3177%, native2=100%, native3=32.4436%; native3failuremustretainreferencecontaminationconfound. Nooracleclipsorreferencewordsturnedintomodelinputs.','memoryExecution':'Only780Mconnected. No fullmodelCPUstate/noquantization, exactF32tensorhashes. Oneencoderblockatime; decoderloadedonceonlywhenneeded; CTC-onlymodulesguarded/unallocatedbecauseauthorsgenerationctc_weight0. CPU5%/2GiBprivatejob, actualWindowsLOWRAMmonitor, workerfamilystoponly. SDPAbackendchangesfloatingpointroundoff(tinymax5.96e-8); streamed eagerbitexacttinyforward. FulltrainedCPUvsGPU/eagernumericalequivalenceNOTclaimed.','failureAndRecovery':'r1stoppedactualLOWRAMbeforemodelimport(3.048s,136552448Bpolledprivate). r2loadedoriginalweightsandranthroughencoderlayer19, stoppedactualLOWRAM(69.266s,1622515712Bpolledprivate); originalsourcehashsnapshotsretained. Afterdeferringidledecoderandnaturallychangingglobalmemory,r3..r6completed. CannotattributeabsenceofLOWRAMsolelytolazydecoder; r3overallprivatepeakstill1.619GB. No otherappsclosed/OSpagefilechanged.','ordinaryBestStrictCerUnchanged':461/8325,'complexWholeMeetingMetricReplaced':False,'finalHoldoutOpened':False,'trainingOrWeightChanges':False,'modelDefaultOrInstalledProductChanged':False,'candidateAdopted':False,'saleQualified':False,'next':next_action}
write(C/'real-pilot-result.json',decision)
# Preserve preparation snapshots as history and the current actual result separately.
for p in C.iterdir():
 if p.is_file():target=EV/'context'/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
for index,folder in enumerate(folders,1):
 for p in folder.rglob('*'):
  if p.is_file():target=EV/('attempt-'+str(index))/p.relative_to(folder);target.parent.mkdir(parents=True,exist_ok=True);assert len(str(target))<250;shutil.copyfile(p,target)
for p in scripts:shutil.copyfile(p,EV/p.name)
shutil.copyfile(C/'real-pilot-result.json',EV/'result.json')
# Only newinferredauthor-maskfeatures; ordinarysoftinputs alreadyremoteat9efd7e1.
job=read(folders[5]/'audio-only.json');features=Path(job['modelInputs']);assert sha(features)==job['modelInputsSha256']
archive=EV/'new-author-mask-input.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:z.write(features,features.name)
with zipfile.ZipFile(archive) as z:assert hashlib.sha256(z.read(features.name)).hexdigest()==job['modelInputsSha256']
reference=Path(read(C/'scoring-only.json')['reference']);shutil.copyfile(reference,EV/'scoring-only-public-reference.TextGrid');assert sha(EV/'scoring-only-public-reference.TextGrid')==read(C/'scoring-only.json')['referenceSha256']
write(EV/'reproduction-index.json',{'sources':[{'file':str(p),'sha256':sha(p)} for p in sources+scripts],'priorFrozenOriginalAudioAndFeaturesCommit':'9efd7e195af425450fe4680321c13fc9417ca336','newArchiveSha256':sha(archive),'newArchiveBytes':archive.stat().st_size,'newArchiveMember':features.name,'newFeatureFileSha256':sha(features),'publicReferenceLicense':'AISHELL4/OpenSLR111 https://www.openslr.org/111/ CC-BY-SA4.0; authors/corpus attribution retained. Referenceonlyforscoring, neverinference.','largeWeightsOrRuntimeInGit':False,'failedSourceSnapshots':'attempt-2/source-before-lazy-decoder; alloldcontrollerbytesretainedforsha-boundoriginalprotocols.','noProductOrModelPromotion':True})
model=ship(M,[str(p.relative_to(M)).replace('\\','/') for p in sources]+[str(EV.relative_to(M)).replace('\\','/')],'Run bounded real Chinese SE-DiCoW pilot and reject incorrect-language and missing-speech outputs')
for p in sources:
 blob=subprocess.run(['git','show',model+':'+str(p.relative_to(M)).replace('\\','/')],cwd=M,capture_output=True,check=True,env=env).stdout;assert hashlib.sha256(blob).hexdigest()==sha(p)
path=R/'docs/product_backlog.json';log=R/'docs/development_log.md';initial=read(path);quality=initial['quality_targets'];prefix=log.read_bytes()
def task(d):return d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
record={'at':at,'ownerQuote':decision['ownerQuote'],'state':decision['state'],'previousStatus':task(initial)['status'],'previousWorkpoint':task(initial)['next'],'modelEvidenceCommit':model,'remoteReadbackConfirmed':True,'source':str(C/'real-pilot-result.json'),'decision':decision,'newCompletedTargetAsrCalls':4,'newIndependentMeetings':0,'newTraining':False,'ordinaryBestStrictCerUnchanged':461/8325,'formalQualityTargetsChanged':False,'finalHoldoutOpened':False,'saleQualified':False,'next':next_action};write(C/'real-pilot-preservation.json',record)
for attempt in range(8):
 raw=path.read_bytes();d=json.loads(raw);n=task(d);n['ownerCompetitiveSaleStandard20261108']['seDicowRealChinesePilot20261109']=record;n.update(status=decision['state'],next=next_action);n['ownerCompetitiveSaleStandard20261108']['next']=next_action;temp=path.with_suffix('.sedicow-real.tmp');write(temp,d)
 if path.read_bytes()!=raw:temp.unlink();continue
 try:os.replace(temp,path);break
 except PermissionError:temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2))
else:raise RuntimeError('Originalbacklogbusy; modelsourceandevidencealreadyremote')
assert read(path)['quality_targets']==quality
marker='原模型SE-DiCoW真实中文逐人转写验证20261109';assert marker.encode('utf8') not in prefix
entry='\n\n## '+at+'｜'+marker+'\n\nOwner要求先试新方案，有用才优化，并将其作为本轮最后新增候选。当前仍无6800XT只有780M。为拿到实值而非继续准备，新增受限CPU分层读取原F32权重：逐tensor与固定4.407GB文件SHA匹配，编码块用完释放、文字decoder首次调用才载一次、作者generation.ctc_weight0的CTC专用层不载且加误调用guard；没有量化、改权重、训练、答案提示或改原音。先tiny验证eager分层与完整加载forward逐位一致，SDPA最大数值差5.96e-8，实际受限CPU用SDPA；不声称完整模型CPU/GPU/eager逐位等同。r1全机实际LOWRAM在导入前停(3.048s/私有采样136552448B)，r2到第19编码层再因实际LOWRAM停(69.266s/私有采样1622515712B)，修前源字节和协议保留。改闲置decoder延迟加载且全机内存自然变化后，原固定1560..1590s30秒、三人物1/2/3顺序实跑完成，所有原始greedy及作者时间戳重建输出/EOS/失败耐久保留。第一人识别118.451s/含校验启动140.163s/私有采样峰1619476480B，挺普遍的→相同间的、门禁卡→门金卡，尾标注跨1590s所以不编局部CER；第二人识别58.198s/全80.089s/1358499840B，中文强制zh仍输出英文，30参考字115编辑/383.333%局部CER(错误插入可超100%，非整会CER)；第三人识别55.242s/全84.097s/1339375616B，仅对对就是，23参考字漏19、82.609%局部CER。事后参考审计1号目标独占讲话/有声94.318%、2号100%、3号32.444%，第三人明显参考混杂留作混杂因素不一概归模型。又以作者原流程二值时间标记做一次固定格式反事实：只改主音/参考STNO，原音/同参考/特征/模型/zh/greedy全同，原自动nativejournal50Hz取整、不读人工标签/人数/文字、不扫阈值；第二人仍英文，识别57.322s/全78.095s/1359364096B，30字78编辑/260%局部CER。四次完整target生成均自然EOS/无20重复死循环不代表内容正确，均来自同一开发会同一30s，不是4独立会议，不做整会质量或速度外推。原准备曾猜0/4/5无声，经评分真值仅0无声、4/5有短句，已在质量判断前纠正、输入未动。最终拒绝此checkpoint与当前自动人物输入作为中文生产基线，不扩整会/其它人物、不启动LoRA/全训练，不以换硬时间标记仍失败断言整个目标人物ASR架构不可能。保持单模型5%CPU/2GiB私有上限/IDLE/实际LOWRAM只停自身，无其它应用/页文件/硬件操作；r3总体私有峰仍1.619GB，不能声称全程减半或把成功仅归代码优化。原普通最佳5.53754%、复杂整会旧指标和全部质量门未变，没开最终留出、没动日用默认/安装、没售卖通过。源/真实raw/标注评分/修前失败/新公开输入证据'+model+'已远端核验；CPU没有独显也拿到真实结果但未证明能力改善。下一项：'+next_action+'\n'
with log.open('ab') as f:f.write(entry.encode('utf8'))
for p in [path,log]:shutil.copyfile(p,S/'docs'/p.name)
for p in EV.rglob('*'):
 if p.is_file():target=DEST/p.relative_to(EV);target.parent.mkdir(parents=True,exist_ok=True);assert len(str(target))<250;shutil.copyfile(p,target)
shutil.copyfile(C/'real-pilot-preservation.json',DEST/'preservation-result.json')
attrs=S/'.gitattributes';text=attrs.read_text('utf8');rule='docs/handoffs/model-sedicow-real-pilot-20261109/** -text -whitespace'
if rule not in text:attrs.write_text(text+'\n'+rule+'\n',encoding='utf8')
main=ship(S,['.gitattributes','docs/product_backlog.json','docs/development_log.md',str(DEST.relative_to(S)).replace('\\','/')],'Record actual SE-DiCoW Chinese pilot rejection, resource limits and unchanged delivery gates')
assert not git(M,'status','--porcelain') and not git(S,'status','--porcelain')
print(json.dumps({'modelCommit':model,'mainCommit':main,'remoteReadbackConfirmed':True,'qualityTargetsUnchanged':read(path)['quality_targets']==quality,'timelinePrefixPreserved':log.read_bytes().startswith(prefix),'completedTargetCalls':4,'saleQualified':False,'next':task(read(path))['next']},ensure_ascii=False),flush=True)
