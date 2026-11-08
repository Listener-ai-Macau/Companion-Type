"""Preserve this continuation in the original backlog and unique project timeline."""
from pathlib import Path
from datetime import datetime
import argparse,ast,hashlib,json,os,shutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';C=R/'docs/handoffs/20261108-tse-source-supervision';EV=M/'evidence/20261108-tse-source-supervision';sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3);parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['checkpoint','complete','reference-bank'],required=True);args=parser.parse_args()
def read(p):
    for i in range(8):
        try:return json.loads(Path(p).read_text(encoding='utf8'))
        except OSError as e:
            if getattr(e,'winerror',None) not in [5,32,33] or i==7:raise
            time.sleep(min(.01*2**i,.2))
optional=lambda p:read(p) if Path(p).exists() else None
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
EV.mkdir(exist_ok=True)
for file in C.rglob('*'):
    if file.is_file() and file.suffix in ['.json','.jsonl','.log','.txt','.TextGrid']:
        dest=EV/file.relative_to(C);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
attr=M/'.gitattributes';content=attr.read_text(encoding='utf8')
for line in ['src/*tse_source_supervision*20261108.py -text','evidence/20261108-tse-source-supervision/** -text -whitespace','trained/20261108-tse-source-supervision/*.safetensors -text -diff']:
    if line not in content:content+='\n'+line+'\n'
attr.write_text(content,encoding='utf8');sources=sorted({p for pattern in ['*tse_source_supervision*20261108.py','companion_tse_source*20261108.py','companion_tse_reference*20261108.py'] for p in (M/'src').glob(pattern)});paths=['.gitattributes','evidence/20261108-tse-source-supervision',*[str(p.relative_to(M)).replace('\\','/') for p in sources]]
attempt_files=sorted(C.glob('source-train-*-controller.json'),key=lambda p:p.stat().st_mtime_ns);attempt=read(attempt_files[-1]) if attempt_files else None;progress=optional(C/attempt['runId']/'state.json') if attempt else None
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'phase':args.phase,'ownerOriginal':'好的,开始吧','evidence':str(C),'purpose':read(C/'purpose.json'),'data':optional(C/'audio-ready.json'),'dataVerification':optional(C/'audio-verification.json'),'objectiveProof':optional(C/'source-proof-r1/state.json'),'trainingProtocol':optional(C/'training-protocol-r1.json'),'trainingProgress':progress,'trainingController':attempt,'retainedTrainingAttempts':[read(p) for p in attempt_files],'trainingReview':optional(C/'training-review.json'),'decision':optional(C/'decision.json'),'latestTrainingCheckpoint':optional(C/'latest-training-checkpoint.json'),'productDefaultChanged':False,'qualityQualified':False,'saleQualified':False,'finalHoldoutOpened':False}
actual_progress=(progress or attempt) if attempt and attempt['state'] in ['RUNNING_TSE_STAGE','PREPARING_TSE_STAGE','COMPLETE_TSE_STAGE_REVIEW_REQUIRED'] else attempt
point=record['decision'] or record['trainingReview'] or actual_progress or record['objectiveProof'] or record['purpose'];record['state']=point['state'];record['next']=point.get('next','完成固定128单元原声监督训练、新会议分量验证和66段自然会议前后验证；先确认不压掉目标声音，再用相同识别器核对实际转写，全部原质量门保留。')
asr_files=sorted(C.glob('source-asr-*-controller.json'),key=lambda p:p.stat().st_mtime_ns);asr=read(asr_files[-1]) if asr_files else None;record['diagnosticAsrPlan']=optional(C/'post-rejection-asr-plan.json');record['asrController']=asr;record['asrProgress']=optional(C/asr['runId']/'state.json') if asr else None;record['alignmentDiagnostic']=optional(C/'alignment-diagnostic.json');record['identityOutputDiagnostic']=optional(C/'identity-output-diagnostic.json')
if not record['decision'] and record['diagnosticAsrPlan'] and asr and asr['state']=='RUNNING_TSE_STAGE':record['state']='REJECTED_CANDIDATE_FIXED_NATURAL_ASR_DIAGNOSTIC_RUNNING';record['next']='完成冻结的156份自然会议/原音对照转写与原声纹编码器223段独立发言核对；本轮声音保真不合格结论保留，不追加训练或据诊断结果直接进入产品。'
record['referenceBankResult']=optional(C/'reference-bank-r1/result.json')
if record['referenceBankResult']:record['state']=record['referenceBankResult']['state'];record['next']=record['referenceBankResult']['next']
weights=[]
if record['latestTrainingCheckpoint'] and record['latestTrainingCheckpoint']['completedSteps']>0:
    checkpoint=record['latestTrainingCheckpoint'];source=Path(checkpoint['trainableWeights']);assert sha(source)==checkpoint['trainableWeightsSha256'] and source.stat().st_size<100*1024**2;folder=M/'trained/20261108-tse-source-supervision';folder.mkdir(parents=True,exist_ok=True);target=folder/'trainable.safetensors';shutil.copyfile(source,target);metadata={k:v for k,v in checkpoint.items() if k not in ['optimizerState','optimizerStateSha256','optimizerStateSchema','optimizerParamGroups']};metadata.update(frozenBaseRequired=record['trainingProtocol']['extractorReady'],optimizerCachedOnlyNotDeploymentRequired=True,qualityQualified=False);(folder/'manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf8');paths.append('trained/20261108-tse-source-supervision');weights=[str(target.relative_to(M)).replace('\\','/')]
(EV/'observed-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2');publisher=S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py';tree=ast.parse(publisher.read_text(encoding='utf8'));functions=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ['git','ship']];assert len(functions)==2;exec(compile(ast.Module(body=functions,type_ignores=[]),str(publisher),'exec'),globals())
if weights:git(M,'add','--force','--',*weights)
head=ship(M,paths,'Preserve positive-source TSE supervision '+args.phase);record.update(sourceAndEvidenceCommit=head,remoteReadbackConfirmed=True)
path=R/'docs/product_backlog.json'
for attempt in range(8):
    raw=path.read_bytes();d=json.loads(raw);node=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104'];node['ownerSourceSupervision20261108']=record;node.update(status=record['state'],next=record['next']);gate=next(x for x in d['quality_targets']['real_meeting_model_contract_20261103']['gates'] if x['id']=='RM-OVERLAP');gate['positiveSourceSupervision20261108']={'state':record['state'],'sourceAndEvidenceCommit':head,'evidence':str(C),'qualified':False};temp=path.with_suffix('.source-tse.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if path.read_bytes()!=raw:temp.unlink();continue
    try:os.replace(temp,path)
    except PermissionError as e:
        if getattr(e,'winerror',None) not in [5,32,33]:raise
        temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2));continue
    break
else:raise RuntimeError('Original backlog busy; source already preserved')
if args.phase=='complete':
    decision=record['decision'];assert decision;marker='原RM-OVERLAP目标原声监督20261108';log=R/'docs/development_log.md';assert marker not in log.read_text(encoding='utf8');brief={k:v for k,v in decision.items() if k in ['state','completedWeightUpdates','trainingTargetQueries','naturalValidationQueriesEachCondition','retainedForNextStageOnly','newQualityQualification','wordSafetyFindings','speakerReferencePriorityEvidence','trainingFamilySeconds','trainingPeakPrivateBytes','naturalAsrFamilySecondsIncludingRecovery','next']}
    with log.open('a',encoding='utf8') as f:f.write('\n\n## '+record['at']+'｜'+marker+'\n\n承接Owner“好的,开始吧”。'+json.dumps(brief,ensure_ascii=False)+'。原声分量与新自然会议、目标、完整训练/自由转写结果及失败见'+str(C/'decision.json')+'；模型源码/参数/证据提交'+head+'已远端核验。上一轮静音退化及所有原门保留，合成混音不冒充自然会议，未达标不进入产品。\n')
if args.phase=='reference-bank':
    bank=record['referenceBankResult'];assert bank;marker='原RM-OVERLAP多段声纹参考20261108';log=R/'docs/development_log.md';assert marker not in log.read_text(encoding='utf8');brief={k:bank[k] for k in ['state','knownProfileAccuracySingle','knownProfileAccuracyMultiple','hardestMeetingAccuracy','singleReferenceInferenceBitIdentical','originalWeightsUnchanged','equalWeightDualFusionRetained','wordAccuracyImprovementFromReferenceBankProven','qualityQualified','next']};brief['perMeeting']=bank['voiceReferenceReview']['perMeeting'];brief['dualTotals']=bank['dualInformationDiagnostic']['totals']
    with log.open('a',encoding='utf8') as f:f.write('\n\n## '+record['at']+'｜'+marker+'\n\n承接同一原任务，在完整训练候选拒绝并核验远端后，按原待办继续修参考身份条件。'+json.dumps(brief,ensure_ascii=False)+'。69段参考逐个原音/纯度/时间不重叠核验；已知身份223段诊断、单参考原输出逐位相同及原参数不变，代码和证据提交'+head+'已远端核验。双麦信息检查的缺失CFFI准备失败保留，复用现有依赖后同一冻结规则完成；真值分组的留一诊断只作定位、不作独立验收。实际执行时间沿source-reference-r1收据，当前时刻为保存时间，不将中间中断时段计作计算或人工工时；原重叠转写、自动身份和售卖门未通过。\n')
dest=S/'docs/handoffs/model-tse-source-supervision-20261108';dest.mkdir(exist_ok=True)
for file in [path,R/'docs/development_log.md']:shutil.copyfile(file,S/'docs'/file.name)
(dest/(args.phase+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');shutil.copyfile(__file__,dest/Path(__file__).name);main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-tse-source-supervision-20261108'],'Record same-task positive-source TSE '+args.phase);print(json.dumps({'state':record['state'],'modelCommit':head,'mainCommit':main,'remoteReadbackConfirmed':True}),flush=True)
