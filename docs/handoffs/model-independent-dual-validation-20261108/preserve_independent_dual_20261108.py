"""Preserve this continuation in the original task, timeline and both remotes."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,shutil,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['checkpoint','complete'],required=True);a=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';C=R/'docs/handoffs/20261108-dual-mic-independent-meetings';EV=M/'evidence/20261108-dual-mic-independent-meetings';EV.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));optional=lambda p:read(p) if Path(p).exists() else None
for file in C.rglob('*'):
    if file.is_file() and file.suffix in ['.json','.jsonl','.log','.txt','.rttm']:
        dest=EV/file.relative_to(C);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
attr=M/'.gitattributes';text=attr.read_text(encoding='utf8')
for line in ['src/*independent*20261108.py -text','evidence/20261108-dual-mic-independent-meetings/** -text -whitespace']:
    if line not in text:text+='\n'+line+'\n'
attr.write_text(text,encoding='utf8')
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
def git(root,*argv):
    q=subprocess.run(['git','-c','maintenance.auto=false','-c','pack.threads=1','-c','pack.windowMemory=32m',*argv],cwd=root,env=env,capture_output=True,text=True)
    if q.returncode:raise RuntimeError((q.stdout+q.stderr)[-3000:])
    return q.stdout.strip()
def ship(root,paths,message):
    git(root,'add','--',*paths)
    if git(root,'diff','--cached','--name-only','--',*paths):
        git(root,'-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*paths);git(root,'commit','--only','-m',message,'--',*paths)
    h=git(root,'rev-parse','HEAD');b=git(root,'branch','--show-current');git(root,'push','origin','HEAD:refs/heads/'+b);assert git(root,'ls-remote','origin','refs/heads/'+b).split()[0]==h;return h
direction=read(C/'direction.json');record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'phase':a.phase,'ownerOriginal':direction['owner'],'evidence':str(C),'direction':direction,'preparation':optional(C/'preparation.json'),'nativeRun':optional(C/'native-run.json'),'run':optional(C/'run-r2.json'),'review':optional(C/'review.json'),'decision':optional(C/'decision.json'),'newTrainingRuns':0,'productDefaultChanged':False,'qualityQualified':False,'finalHoldoutOpened':False}
point=record['decision'] or record['review'] or record['run'] or record['nativeRun'] or direction
record.update(state=point['state'],next=point.get('next',direction['next']));(EV/'observed-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
paths=['.gitattributes','evidence/20261108-dual-mic-independent-meetings']+[str(p.relative_to(M)).replace('\\','/') for p in (M/'src').glob('*independent*20261108.py')]
source=optional(C/'fusion-source.json')
if source:paths.append(str(Path(source['sourceRoot']).relative_to(M)).replace('\\','/'))
head=ship(M,paths,'Preserve independent dual-mic real-meeting '+a.phase);record.update(sourceAndEvidenceCommit=head,remoteReadbackConfirmed=True)
path=R/'docs/product_backlog.json'
for attempt in range(8):
    raw=path.read_bytes();d=json.loads(raw);node=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104'];node['ownerIndependentDualMicValidation20261108']=record;node.update(status=record['state'],next=record['next'])
    gate=next(g for g in d['quality_targets']['real_meeting_model_contract_20261103']['gates'] if g['id']=='RM-OVERLAP');gate['independentDualMicValidation20261108']={'state':record['state'],'sourceAndEvidenceCommit':head,'evidence':str(C),'qualified':False}
    temp=path.with_suffix('.independent-dual.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if path.read_bytes()!=raw:temp.unlink();continue
    try:os.replace(temp,path)
    except PermissionError as error:
        if getattr(error,'winerror',None) not in [5,32,33]:raise
        temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2));continue
    break
else:raise RuntimeError('Canonical backlog busy; source safely pushed, retain progress')
if a.phase=='complete':
    assert record['decision'];marker='原RM-OVERLAP跨会议原始双路验证20261108';log=R/'docs/development_log.md';assert marker not in log.read_text(encoding='utf8')
    with log.open('a',encoding='utf8') as f:f.write('\n\n## '+record['at']+'｜'+marker+'\n\nOwner要求“'+record['ownerOriginal']+'”。本轮实际结果：'+json.dumps(record['decision'],ensure_ascii=False)+'。源码与全部失败/生成证据已推送并核验 '+head+'；保留原任务、普通语音基线、最终留出集、双端实卡和售卖未完成门，不把片段改善算作验收。下一步：'+record['next']+'\n')
dest=S/'docs/handoffs/model-independent-dual-validation-20261108';dest.mkdir(exist_ok=True)
for file in [path,R/'docs/development_log.md']:shutil.copyfile(file,S/'docs'/file.name)
(dest/(a.phase+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');shutil.copyfile(__file__,dest/Path(__file__).name)
main=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-independent-dual-validation-20261108'],'Record independent dual-mic validation '+a.phase)
print(json.dumps({'state':record['state'],'modelCommit':head,'mainCommit':main,'remoteReadbackConfirmed':True}),flush=True)
