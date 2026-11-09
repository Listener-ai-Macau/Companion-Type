"""Publish this complete model work batch without promoting unqualified candidates."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast,hashlib,json,os,shutil,subprocess,sys,time,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';W=Path(__file__).parent;ROOT=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109';C=ROOT/'automatic-cross-meeting-r2';O=C/'independent-overlap-candidate-r1';EV=M/'evidence/20261108-competitive-sale-standard/overlap-route-r2';DEST=S/'docs/handoffs/model-competitive-sale-standard-20261108/overlap-route-r2'
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
sources=[M/'src'/name for name in ['companion_meeting_route_plan_20261109.py','test_companion_meeting_route_plan_20261109.py','companion_local_overlap_regions_20261109.py']]
expected={'M src/companion_meeting_route_plan_20261109.py','M src/test_companion_meeting_route_plan_20261109.py','?? src/companion_local_overlap_regions_20261109.py'};assert {line.strip() for line in git(M,'status','--porcelain').splitlines()}==expected
scripts=[W/name for name in ['prepare_companion_speaker_cross_meeting_20261109.py','score_companion_speaker_cross_meeting_20261109.py','audit_companion_overlap_routes_20261109.py','audit_companion_cached_overlap_probabilities_20261109.py','run_companion_cached_overlap_candidate_20261109.py','evaluate_companion_overlap_candidate_20261109.py','check_companion_overlap_count_recipe_20261109.py','run_companion_third_meeting_overlap_20261109.py','preserve_companion_overlap_route_r2_20261109.py']]
bulk=read(C/'result.json');candidate=read(O/'result.json');third=read(O/'third-meeting-r1/review.json');assert bulk['overall']['queries']==148 and third['inferenceRun']['completedFreshNeuralCacheFrames']==2187 and third['inferenceRun']['newNeuralItems']==0
assert read(O/'author-count-recipe-proof.json')['state']=='PASS_SAME_LOCAL_SPEAKER_COUNT_AND_COORDINATES'
native=next(r for r in candidate['cases'] if r['meeting']=='L_R003S01C02');ordinary=next(r for r in candidate['cases'] if r['meeting']=='S_R004S03C01')
at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
decision={'at':at,'state':'ORDINARY_RETAINED_OVERLAP_ROUTING_CANDIDATE_NOT_GENERALIZED_OR_CONTENT_QUALIFIED','decision':'Retain nativejournal as primary activity/identity baseline. Do not replace identity labels with PS4encoder nearestprototype or use two-modelagreement as proof of nooverlap. Retain independent localcount union only as researchcandidate: Lrecall improves66.114→82.959%, but precision69.719→58.899%; ordinaryextra falseoverlap0.894s. Thirddevelopment meeting standalone localcount recall38.927% prevents generalization/promotionclaim; its native8/union still unmeasured. ExistingPS4contentregressions and sameQwenpending remain blockers. No threshold fitting or retraining from these recordings.','ordinaryAsrBestCerUnchanged':461/8325,'speakerQueryScope':'148newclips from2previouslyexposed fullmeetings, not wholeDER or CER. L newclips cover4/6 nativepeople; old22cliptest covers rarepeople but not reused in these counts. All32profiles had>=95% exclusive reference coverage on posthoc audit; this does not mean every future profile is safe.','agreementDiagnostic':'Agreement-dominant mismatches occur in genuine mixtures where more than one voice is present; do not call all3 arbitrary dominant-tie choices wrong realidentity. The 95%-pure subset and coverage costs remain separately reported.','referenceScopeCorrection':'Initial audit included source angle-tag-only intervals; preserved initialJSON, then aligned to canonical original lexical policy (remove source angle tags, nonempty remainder). Original fulloverlap reference seconds188.359388 reproduced exactly; ordinaryS has0 lexicaloverlap. No reference/data/model selection change, no worddeletion to improve CER.','executionFailuresRetained':['Initial nested5percent controller/worker jobs caused excessive throttling; stopped only ownfamily and kept same neuralcache. Corrected to worker-only5percent/2GiB cap plus actualLOWRAMmonitor.','Freshthird2187window neuralcache completed; final statepublication failed because nested control path made .tmp filename exceed Windows260character bound. Samefolder8.3 alias restored finalstate from verified completecache in1.017s, zero new neuralcalls; no repeat full inference. Firstfreshworker wall167.162s includes neuralwork/publicationfailure, not claimed isolated inference time.'],'newProductDelivery':False,'installedOrDefaultChanged':False,'finalHoldoutOpened':False,'saleQualified':False,'next':'独显恢复后先跑已固定六段8s原音/分离同Qwen1.7B对照，判定内容保护；接着用原native8 FP16同配方完成第三场36m35s人物活动，核新独立重叠候选的组合召回/误报，不把第三场单检38.9%或首场组合83%冒充跨会合格。通过内容与跨会门才扩大分离；不通过就拒绝该分离/检测候选、不扫阈值训练。普通线继续新36m35s整会冻结Qwen基线，严格字错率<5%、人物/事实/双端实卡与售卖门不变。无独显不将整场Qwen或已测很慢的native8压到CPU，不再无变化重复缓存审计。'}
write(C/'decision.json',decision)
# Preserve the completed new cache binding, not just its disposable E-drive path.
cache=Path('E:/CodexData/Companion/.model-cache/competitive-sale-standard-20261108/third-meeting-overlap-r1/20200805_S_R001S01C01');shutil.copyfile(cache/'segment.json',O/'third-meeting-r1/fresh-segmentation-manifest.json')
write(C/'reproducibility-sources.json',{'sourceFiles':[{'file':str(p),'sha256':sha(p)} for p in sources+scripts+[M/'src/automatic_speaker_cpu_worker_20261109.py',M/'src/bounded_speaker_20261107.py',M/'src/companion_tse_reference_bank_20261108.py']],'modelThresholdsAndWeightsChanged':False,'actualRouteSafetyTestsPassed':6,'newPublicAudioUploads':0})
for p in C.rglob('*'):
 if p.is_file():target=EV/p.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
for p in scripts:shutil.copyfile(p,EV/p.name)
# Archive the new public clips, avoiding previously preserved identical audio.
oldindex=read(M/'evidence/20261108-competitive-sale-standard/two-lane-validation-20261109/archived-audio-index.json');oldsha={r['sha256'] for r in oldindex['files']};seen=set();audio=[]
for row in read(C/'predeclared-selection.json')['cases']:
 I=read(Path(row['control'])/'audio-only.json')
 for kind in ('profiles','queries'):
  for packet in I[kind]:
   digest=packet['audioSha256']
   if digest in seen or digest in oldsha:continue
   seen.add(digest);source=Path(packet['audio']);assert sha(source)==digest;audio.append({'originalPath':str(source),'member':row['meeting']+'/'+kind+'/'+packet['id']+'.wav','sha256':digest,'bytes':source.stat().st_size})
with zipfile.ZipFile(EV/'new-public-clips.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for row in audio:z.write(row['originalPath'],row['member'])
with zipfile.ZipFile(EV/'new-public-clips.zip') as z:
 for row in audio:assert hashlib.sha256(z.read(row['member'])).hexdigest()==row['sha256']
write(EV/'public-audio-archive-index.json',{'license':'AISHELL4/OpenSLR111 CC-BY-SA4.0; publicdevelopment speech only, originalauthors and corpus attribution/source retained.','source':'https://www.openslr.org/111/','files':audio,'uncompressedBytes':sum(r['bytes'] for r in audio),'archiveSha256':sha(EV/'new-public-clips.zip'),'archiveBytes':(EV/'new-public-clips.zip').stat().st_size,'priorDuplicateAudioPreservedAtModelCommit':'5be8d7a3b8dac7a1375b6b3fff5e3f810234d651'})
# Preserve sufficient native neural evidence and exact powerset decisions compactly.
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
for name in ['S_R004S03C01','L_R003S01C02']:
 parent=Path('E:/CodexData/Companion/.model-cache/nemotron-speaker-20261107/precision-r1/full-probabilities')/name;manifest=read(parent/'probabilities.json');a=np.load(parent/'probabilities.npy',mmap_mode='r',allow_pickle=False);np.savez_compressed(EV/(name+'-native-probabilities.npz'),probabilities=np.asarray(a[:manifest['committedFrames']]));del a
local=[]
for name in ['S_R004S03C01','L_R003S01C02','20200805_S_R001S01C01']:
 parent=(Path('E:/CodexData/Companion/.model-cache/bounded-speaker-20261107-full-r1')/name if name!='20200805_S_R001S01C01' else cache);manifest=read(parent/'segment.json');a=np.load(parent/'segment.npy',mmap_mode='r',allow_pickle=False);classes=np.argmax(a,axis=-1).astype(np.uint8);np.savez_compressed(EV/(name+'-powerset-classes.npz'),classes=classes);local.append({'meeting':name,'classesSha256':hashlib.sha256(classes.tobytes()).hexdigest(),'rawNeuralPrefixSha256':manifest['committedPrefixSha256'],'shape':list(classes.shape),'scope':'Exact argmaxclasses preserve all neuralinformation used by localcount method; not a fullrawlogit archive.'});del a,classes
write(EV/'neural-archive-index.json',{'powerset':local,'native':'Fullcommitted originalfloat32 probabilities for2exposedmeetings compressed losslessly, exactsource prefixSHA in cached audit. No private content or modelweights.','newNativeInference':False})
attrs=M/'.gitattributes';content=attrs.read_text(encoding='utf8');rule='src/companion_local_overlap_regions_20261109.py -text'
if rule not in content:attrs.write_text(content+'\n'+rule+'\n',encoding='utf8')
model=ship(M,['.gitattributes']+[str(p.relative_to(M)).replace('\\','/') for p in sources]+[str(EV.relative_to(M)).replace('\\','/')],'Add identity-pending overlap route and validate its tradeoffs across real meetings')
for p in sources:
 blob=subprocess.run(['git','show',model+':'+str(p.relative_to(M)).replace('\\','/')],cwd=M,capture_output=True,check=True,env=env).stdout;assert hashlib.sha256(blob).hexdigest()==sha(p)
path=R/'docs/product_backlog.json';log=R/'docs/development_log.md';d=read(path);quality=d['quality_targets'];prefix=log.read_bytes()
def task(d):return d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
record={'at':at,'ownerQuote':'那继续吧','state':decision['state'],'previousStatus':task(d)['status'],'previousWorkpoint':task(d)['next'],'modelEvidenceCommit':model,'remoteReadbackConfirmed':True,'source':str(C),'newSpeakerChecks':bulk['overall'],'ordinarySpeakerQueryMatches':'67/67 new selectedclips; sameexposedordinarymeeting, notASRaccuracy or wholeDER','complexSpeakerQueryMatches':'72/81dominantmatches, nativejournal75/81; includesmixtures, rarepeople0/3have no neweligibleclips underfrozenpolicy. Not replacementfor6personcoveragegate.','overlapRouting':{'complexNative':native['metrics']['native'],'complexIndependent':native['metrics']['independent'],'complexUnion':native['metrics']['union'],'changedRegions':native['changedRegions'],'ordinaryExtraFalsePositiveSeconds':ordinary['changedRegions']['newFalsePositiveSeconds'],'routeUnknownSecondPersonDoesNotInventIdentity':True,'allSourceFramesPreserved':True,'defaultNotPromoted':True},'thirdMeeting':{'meeting':third['meeting'],'audioSeconds':third['audioSeconds'],'freshNeuralCacheFrames':2187,'metrics':third['metrics'],'freshWorkerWallIncludingOutputFailureSeconds':third['inferenceRun']['priorFullNeuralAttempt']['wallSeconds'],'freshWorkerPolledPrivatePeakBytes':third['inferenceRun']['priorFullNeuralAttempt']['polledPrivatePeakBytes'],'cacheOnlyOutputRecoverySeconds':third['inferenceRun']['wallSeconds'],'cacheOnlyRecoveryNewNeuralItems':0,'nativeOrUnionThirdNotMeasured':True,'notFinalHeldout':True},'decision':decision,'ordinaryAsrBestUnchanged':461/8325,'noAsrAccuracyGainClaimed':True,'newProductInstalled':False,'weightsOrFormalTargetsChanged':False,'saleQualified':False,'next':decision['next']};write(C/'preservation-result.json',record)
for attempt in range(8):
 raw=path.read_bytes();d=json.loads(raw);n=task(d);n['ownerCompetitiveSaleStandard20261108']['crossMeetingOverlapRouting20261109']=record;n.update(status=decision['state'],next=record['next']);n['ownerCompetitiveSaleStandard20261108']['next']=record['next'];temp=path.with_suffix('.overlap-route-r2.tmp');write(temp,d)
 if path.read_bytes()!=raw:temp.unlink();continue
 try:os.replace(temp,path);break
 except PermissionError:temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2))
else:raise RuntimeError('Originalbacklogbusy; sourceandevidencealreadyremote')
assert read(path)['quality_targets']==quality
marker='原模型跨会人物与独立重叠路由候选20261109';assert marker.encode('utf8') not in prefix
entry='\n\n## '+at+'｜'+marker+'\n\n承接Owner继续。当前仅780M无外置6800XT，原六段同Qwen/新整会ASR保留未跑，不把GPU模型压到CPU。串行CPU按原PS4编码器/32自动参考核148新片段：S67/67同主说话人，L72/81(原native75/81)，L稀少人物0/3本批无合格新片段不补编；纯参考子集与所有混合片段分别保留，两个模型一致也不代表无重叠。原32参考事后均>=95%纯，不能把声纹近邻替换人物日志。复用原native概率精确重建656段(源和缓存SHA一致)，复杂全会按原去源标签的词法参考188.359s重叠，检出124.532s/漏63.827s，漏处真声概率中位0.254，不是日志拼装缺失。首次审计包含<$>类非词法标注的初始JSON保留，评分范围已对齐原口径，非删词降CER。新增研究后端独立局部人数检测/人物待确认路由：只用已有powerset缓存argmax及原作者取整均值，原单人/无人物与另一路重叠冲突时不编第二人，所有源样本仍恰一次保留、不替换原ASR。与原人数聚合及坐标逐段一致，6条样本/未知人物安全测试过。复杂native与独立候选取并集：召回66.114%→82.959%，多检31.730s真实重叠，同时新增54.953s误报、精确率69.719%→58.899%；普通S原词法无重叠、额外误报0.894s。不是新字错率、不是可售通过。再在已备36m35s五人第三开发会真实CPU跑2187神经窗，同配方无新阈值/模型/训练：独立检测召回38.927%、精确率79.251%，真重叠131.069s仅检51.021s，证明单独不能泛化；第三native/并集尚待GPU，不拿首会83%推广。新CPU神经主作业167.162s含最终状态写失败、采样私有峰222969856B，初始父/子双5%限制过慢由工程停自身家族后改仅模型限额；完整新缓存已耐久，C深层路径临时文件超260字符导致最终状态失败，改同目录8.3别名从完整缓存1.017s恢复、0新推理，不重跑整场。实际LOWRAM监控/模型5%CPU及2GiB私有上限保留；原模型/阈值未改，不关闭用户程序。源码/选样/原始结果/失败、小公开音频压缩及两会原始概率/三会局部类别证据'+model+'已远端核验。普通5.53754%未变，未安装、未改变日用默认、未开最终留出，原人物/字错/事实/双端实卡/售卖门全保留。下一项：'+record['next']+'\n'
with log.open('ab') as f:f.write(entry.encode('utf8'))
for p in [path,log]:shutil.copyfile(p,S/'docs'/p.name)
for p in C.rglob('*'):
 if p.is_file():target=DEST/p.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
for p in scripts:shutil.copyfile(p,DEST/p.name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md',str(DEST.relative_to(S)).replace('\\','/')],'Record cross-meeting overlap routing gain, false positives and third-meeting limits')
assert not git(M,'status','--porcelain') and not git(S,'status','--porcelain')
print(json.dumps({'modelCommit':model,'mainCommit':main,'remoteReadbackConfirmed':True,'qualityTargetsUnchanged':read(path)['quality_targets']==quality,'timelinePrefixPreserved':log.read_bytes().startswith(prefix),'modelSourceClean':True,'newProductDelivery':False,'next':task(read(path))['next']},ensure_ascii=False),flush=True)
