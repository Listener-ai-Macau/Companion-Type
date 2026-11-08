"""Checkpoint/final result in the same model task and both protected remotes."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,shutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';C=R/'docs/handoffs/20261108-joint-neural-spatial';EV=M/'evidence/20261108-joint-neural-spatial'
sys.path.insert(0,str(M/'src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['checkpoint','complete'],required=True);a=parser.parse_args();read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));optional=lambda p:read(p) if Path(p).exists() else None
EV.mkdir(exist_ok=True)
for f in C.rglob('*'):
    if f.is_file() and f.suffix in ['.json','.jsonl','.log','.txt']:
        dest=EV/f.relative_to(C);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)
attr=M/'.gitattributes';text=attr.read_text(encoding='utf8')
for line in ['src/*joint_neural_spatial*20261108.py -text','evidence/20261108-joint-neural-spatial/** -text -whitespace']:
    if line not in text:text+='\n'+line+'\n'
attr.write_text(text,encoding='utf8')
purpose=read(C/'purpose.json');record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'phase':a.phase,'ownerOriginal':purpose['owner'],'evidence':str(C),'purpose':purpose,'protocol':optional(C/'protocol-r2.json'),'run':optional(C/'run-r2.json'),'review':optional(C/'review.json'),'decision':optional(C/'decision.json'),'newTrainingRuns':0,'productDefaultChanged':False,'qualityQualified':False,'saleQualified':False,'finalHoldoutOpened':False}
point=record['decision'] or record['review'] or record['run'] or purpose;record['state']=point['state'];record['next']=point.get('next','完成本次固定声纹条件神经掩码＋原始双路MVDR候选，与相同神经单路及缓存最强GSS逐人对照。全局已知人均计入，缺席输出计插入，不以活动门控／top1删除。过预定条件才扩剩余片段；失败即停该候选，不扫模型或掩码参数。原全部质量与售卖门保持未完成。')
(EV/'observed-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
def git(root,*argv):
    p=subprocess.run(['git','-c','maintenance.auto=false','-c','pack.threads=1','-c','pack.windowMemory=32m','-c','pack.deltaCacheSize=32m','-c','core.deltaBaseCacheLimit=32m',*argv],cwd=root,env=env,capture_output=True,text=True)
    if p.returncode:raise RuntimeError((p.stdout+p.stderr)[-3000:])
    return p.stdout.strip()
def ship(root,paths,message):
    git(root,'add','--',*paths)
    if git(root,'diff','--cached','--name-only','--',*paths):git(root,'-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*paths);git(root,'commit','--only','-m',message,'--',*paths)
    h=git(root,'rev-parse','HEAD');branch=git(root,'branch','--show-current');git(root,'push','origin','HEAD:refs/heads/'+branch);assert git(root,'ls-remote','origin','refs/heads/'+branch).split()[0]==h;return h
paths=['.gitattributes','evidence/20261108-joint-neural-spatial']+[str(f.relative_to(M)).replace('\\','/') for f in (M/'src').glob('*joint_neural_spatial*20261108.py')]
head=ship(M,paths,'Preserve one speaker-mask spatial candidate '+a.phase);record.update(sourceAndEvidenceCommit=head,remoteReadbackConfirmed=True)
path=R/'docs/product_backlog.json'
for attempt in range(8):
    raw=path.read_bytes();d=json.loads(raw);node=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104'];node['ownerJointNeuralSpatial20261108']=record;node.update(status=record['state'],next=record['next'])
    gate=next(g for g in d['quality_targets']['real_meeting_model_contract_20261103']['gates'] if g['id']=='RM-OVERLAP');gate['jointNeuralSpatialCandidate20261108']={'state':record['state'],'sourceAndEvidenceCommit':head,'evidence':str(C),'qualified':False}
    temp=path.with_suffix('.joint-mask.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if path.read_bytes()!=raw:temp.unlink();continue
    try:os.replace(temp,path)
    except PermissionError as error:
        if getattr(error,'winerror',None) not in [5,32,33]:raise
        temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2));continue
    break
else:raise RuntimeError('Canonical backlog busy, source preserved on remote')
if a.phase=='complete':
    assert record['decision'];log=R/'docs/development_log.md';marker='原RM-OVERLAP声纹神经掩码与双路空间候选20261108';assert marker not in log.read_text(encoding='utf8')
    with log.open('a',encoding='utf8') as f:f.write('\n\n## '+record['at']+'｜'+marker+'\n\n承接Owner“'+record['ownerOriginal']+'”。本轮实际结果：'+json.dumps(record['decision'],ensure_ascii=False)+'。来源/参数/原始输出/失败证据'+head+'已推送并核验；保留先前基线和失败，不将运行、文档或局部成绩当可售卖。下一项：'+record['next']+'\n')
dest=S/'docs/handoffs/model-joint-neural-spatial-20261108';dest.mkdir(exist_ok=True)
for f in [path,R/'docs/development_log.md']:shutil.copyfile(f,S/'docs'/f.name)
(dest/(a.phase+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');shutil.copyfile(__file__,dest/Path(__file__).name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-joint-neural-spatial-20261108'],'Record same-task speaker spatial candidate '+a.phase)
print(json.dumps({'state':record['state'],'modelCommit':head,'mainCommit':main,'remoteReadbackConfirmed':True}),flush=True)
