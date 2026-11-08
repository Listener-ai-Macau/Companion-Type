"""Protect source, frozen trial, gradient evidence and final trainable parameters."""
from pathlib import Path
from datetime import datetime
import argparse,ast,hashlib,json,os,shutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';C=R/'docs/handoffs/20261108-tse-supervised-adaptation';EV=M/'evidence/20261108-tse-supervised-adaptation';sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3);p=argparse.ArgumentParser();p.add_argument('--phase',choices=['checkpoint','complete'],required=True);a=p.parse_args()
def read(path):
    for i in range(8):
        try:return json.loads(Path(path).read_text(encoding='utf8'))
        except OSError as e:
            if getattr(e,'winerror',None) not in (5,32,33) or i==7:raise
            time.sleep(min(.01*2**i,.2))
optional=lambda p:read(p) if Path(p).exists() else None
EV.mkdir(exist_ok=True)
for file in C.rglob('*'):
    if file.is_file() and file.suffix in ['.json','.jsonl','.log','.txt']:
        dest=EV/file.relative_to(C);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
attr=M/'.gitattributes';content=attr.read_text(encoding='utf8')
for line in ['src/companion_tse_*20261108.py -text','src/*tse_supervised*20261108.py -text','src/configure_tse_*20261108.py -text','evidence/20261108-tse-supervised-adaptation/** -text -whitespace','trained/20261108-tse-supervised-adaptation/*.safetensors -text -diff']:
    if line not in content:content+='\n'+line+'\n'
attr.write_text(content,encoding='utf8')
runs=sorted(C.glob('train-*-controller.json'),key=lambda p:p.stat().st_mtime_ns);purpose=read(C/'purpose.json');latest_run=optional(runs[-1]) if runs else None
protocols=list(C.glob('training-protocol-r*.json'));matching=[p for p in protocols if latest_run and hashlib.sha256(p.read_bytes()).hexdigest()==latest_run['protocolSha256']];assert len(matching)<=1
protocol=read(matching[0]) if matching else optional(C/'training-protocol-r1.json')
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'phase':a.phase,'ownerOriginal':purpose['owner'],'evidence':str(C),'purpose':purpose,'gradientProof':optional(C/'gradient-r2/state.json'),'activationMemoryProof':optional(C/'activation-proof-r1/state.json'),'retainedZeroUpdateMemoryStops':optional(C/'training-memory-failure-r1.json'),'trainingProtocol':protocol,'latestTrainingRun':latest_run,'trainingReview':optional(C/'training-review.json'),'decision':optional(C/'decision.json'),'latestTrainingCheckpoint':optional(C/'latest-training-checkpoint.json'),'productDefaultChanged':False,'qualityQualified':False,'saleQualified':False,'finalHoldoutOpened':False}
point=record['decision'] or record['trainingReview'] or record['latestTrainingRun'] or purpose;record['state']=point['state'];record['next']=point.get('next','完成固定166组单遍训练及48组分开会议验证；全骨干＋空间分支训练，声纹编码器和识别器冻结。仅在预定验证非回退条件通过后做无参考自由转写，不能以训练损失或梯度通过冒充可用；原完整会议<5%、事实、双端实卡和售卖门保留。')
paths=['.gitattributes','evidence/20261108-tse-supervised-adaptation']
sources={p for pattern in ['companion_tse_*20261108.py','*tse_supervised*20261108.py','configure_tse_*20261108.py'] for p in (M/'src').glob(pattern)};paths += [str(p.relative_to(M)).replace('\\','/') for p in sorted(sources)]
weights=[]
if a.phase=='complete' and record['latestTrainingCheckpoint'] and record['latestTrainingCheckpoint']['completedSteps']>0:
    checkpoint=record['latestTrainingCheckpoint'];source=Path(checkpoint['trainableWeights']);assert hashlib.sha256(source.read_bytes()).hexdigest()==checkpoint['trainableWeightsSha256'] and source.stat().st_size<100*1024**2
    folder=M/'trained/20261108-tse-supervised-adaptation';folder.mkdir(parents=True,exist_ok=True);target=folder/'trainable.safetensors';shutil.copyfile(source,target);metadata={k:v for k,v in checkpoint.items() if k not in ['optimizerState','optimizerStateSha256']};metadata.update(baseReference=record['trainingProtocol']['extractorReady'],optimizerCachedOnlyNotDeploymentRequired=True,qualityQualified=False);(folder/'manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf8');paths.append('trained/20261108-tse-supervised-adaptation');weights=[str(target.relative_to(M)).replace('\\','/')];record['preservedTrainableWeightSha256']=checkpoint['trainableWeightsSha256']
(EV/'observed-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
# Reuse the preserved publication implementation, without running its old task.
publisher=S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py';tree=ast.parse(publisher.read_text(encoding='utf8'));functions=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ['git','ship']];assert len(functions)==2;exec(compile(ast.Module(body=functions,type_ignores=[]),str(publisher),'exec'),globals())
if weights:git(M,'add','--force','--',*weights)
head=ship(M,paths,'Preserve real TSE supervised trial '+a.phase);record.update(sourceAndEvidenceCommit=head,remoteReadbackConfirmed=True)
path=R/'docs/product_backlog.json'
for attempt in range(8):
    raw=path.read_bytes();d=json.loads(raw);node=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104'];node['ownerTseSupervisedAdaptation20261108']=record;node.update(status=record['state'],next=record['next'])
    gate=next(g for g in d['quality_targets']['real_meeting_model_contract_20261103']['gates'] if g['id']=='RM-OVERLAP');gate['realTseTraining20261108']={'state':record['state'],'evidence':str(C),'sourceAndEvidenceCommit':head,'qualified':False}
    temp=path.with_suffix('.real-tse.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if path.read_bytes()!=raw:temp.unlink();continue
    try:os.replace(temp,path)
    except PermissionError as e:
        if getattr(e,'winerror',None) not in [5,32,33]:raise
        temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2));continue
    break
else:raise RuntimeError('Shared backlog busy; source safely preserved')
if a.phase=='complete':
    assert record['decision'];marker='原RM-OVERLAP真实目标声音提取监督训练20261108';log=R/'docs/development_log.md';assert marker not in log.read_text(encoding='utf8')
    with log.open('a',encoding='utf8') as f:f.write('\n\n## '+record['at']+'｜'+marker+'\n\n承接Owner“'+record['ownerOriginal']+'”。实际结果：'+json.dumps(record['decision'],ensure_ascii=False)+'。源码、训练/验证和准备失败证据及训练后参数'+head+'已推送核验；保留原基线、未通过结果和全部质量门，不把梯度/损失/训练成功当可用模型。下一项：'+record['next']+'\n')
dest=S/'docs/handoffs/model-tse-supervised-adaptation-20261108';dest.mkdir(exist_ok=True)
for f in [path,R/'docs/development_log.md']:shutil.copyfile(f,S/'docs'/f.name)
(dest/(a.phase+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');shutil.copyfile(__file__,dest/Path(__file__).name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-tse-supervised-adaptation-20261108'],'Record same-task real TSE training '+a.phase);print(json.dumps({'state':record['state'],'modelCommit':head,'mainCommit':main,'remoteReadbackConfirmed':True}),flush=True)
