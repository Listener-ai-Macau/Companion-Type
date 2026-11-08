"""Protect this same-task adaptation batch without touching unrelated product code."""
from pathlib import Path
from datetime import datetime
import argparse,json,hashlib,os,shutil,subprocess,time
parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['checkpoint','complete'],required=True);args=parser.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055';C=R/'docs/handoffs/20261108-target-activity-adaptation';EV=M/'evidence/20261108-target-activity-adaptation';EV.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));optional=lambda p:read(p) if Path(p).exists() else None;now=datetime.now().astimezone().isoformat(timespec='seconds')
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
def git(root,*arguments):
    deadline=time.monotonic()+45
    while True:
        result=subprocess.run(['git','-c','maintenance.auto=false','-c','pack.threads=1','-c','pack.windowMemory=32m',*arguments],cwd=root,env=env,capture_output=True,text=True)
        if result.returncode and 'index.lock' in result.stderr and 'File exists' in result.stderr and time.monotonic()<deadline:time.sleep(1);continue
        if result.returncode:raise RuntimeError((result.stdout+result.stderr)[-4000:])
        return result.stdout.strip()
def ship(root,paths,message):
    git(root,'add','--',*paths)
    if git(root,'diff','--cached','--name-only','--',*paths):git(root,'-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*paths);git(root,'commit','--only','-m',message,'--',*paths)
    head=git(root,'rev-parse','HEAD');branch=git(root,'branch','--show-current');git(root,'push','origin','HEAD:refs/heads/'+branch);assert git(root,'ls-remote','origin','refs/heads/'+branch).split()[0]==head;return head
# Public transport cookies are irrelevant to reproducibility; never publish them.
transport=C/'official-train-archive-probe.json'
if transport.exists():
    metadata=read(transport)
    if any(k.lower() in ['set-cookie','cookie','authorization'] for k in metadata.get('headers',{})):
        metadata['headers']={k:v for k,v in metadata['headers'].items() if k.lower() not in ['set-cookie','cookie','authorization']};metadata['irrelevantTransportCookieRemoved']=True;transport.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for file in C.rglob('*'):
    if file.is_file() and file.suffix in ['.json','.jsonl','.txt','.log']:
        target=EV/file.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
record={'at':now,'ownerQuote':'需要你向着正确方向推进','precedingOwnerQuestion':'接下来什么才是正确的效率高得方式去做这个, 已经很久了这个项目 , 有希望做好吗','phase':args.phase,
    'state':(optional(C/'decision.json') or optional(C/'run.json') or optional(C/'audio-preparation-state.json') or {'state':'ACTIVITY_ADAPTATION_PREPARATION'})['state'],
    'evidence':str(C),'sourcePolicy':optional(C/'data-source-policy.json'),'dataSelection':optional(C/'data-selection.json'),'audioPreparation':optional(C/'audio-preparation-state.json'),'run':optional(C/'run.json'),
    'gradientProof':optional(C/'gradient-proof.json'),'trainingHistory':optional(C/'training-history.json'),'selectedCheckpoint':optional(C/'best-checkpoint.json'),'evaluation':optional(C/'evaluation/review.json'),'decision':optional(C/'decision.json'),
    'pairedControl':{'run':optional(C/'paired-control/run.json'),'preparation':optional(C/'paired-control/control-preparation.json'),'trainingHistory':optional(C/'paired-control/training-history.json'),'selectedCheckpoint':optional(C/'paired-control/best-checkpoint.json'),'evaluation':optional(C/'paired-control/evaluation/review.json'),'technicalRecovery':optional(C/'paired-control/explicit-directory-recovery.json')},
    'defaultProductChanged':False,'originalOrdinaryAsrChanged':False,'finalHoldoutOpened':False,'qualityQualified':False}
record['next']=(record['decision'] or {}).get('next','继续原RM-OVERLAP：完成独立真实训练与另房间验证数据，冻结原模型主干，只验证条件活动小模块的梯度/资源与跨会议效果；没有实际收益不扩整场，不替换产品默认。原普通<5%、复杂逐路文字/分离/纪要事实/双端实卡/售卖门保留。')
record['retainedUnqualifiedHeadArtifacts']=[]
if args.phase=='complete':
    for trial,best in [('initial',record['selectedCheckpoint']),('paired-control',record['pairedControl']['selectedCheckpoint'])]:
        if best and best.get('checkpoint'):
            assert hashlib.sha256(Path(best['checkpoint']).read_bytes()).hexdigest()==best['checkpointSha256'];artifact=EV/(trial+'-validation-selected-head.bin');shutil.copyfile(best['checkpoint'],artifact);record['retainedUnqualifiedHeadArtifacts'].append({'trial':trial,'file':str(artifact),'sha256':best['checkpointSha256'],'bytes':artifact.stat().st_size,'baseSourceCheckpointRequired':True,'qualified':False})
(EV/'observed-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
paths=['.gitattributes','evidence/20261108-target-activity-adaptation']+[str(p.relative_to(M)).replace('\\','/') for p in (M/'src').glob('*target_activity*20261108.py')]
if (M/'README.md').exists():paths.append('README.md')
model_head=ship(M,paths,'Preserve bounded real-meeting activity adaptation '+args.phase);record.update(sourceAndEvidenceCommit=model_head,remoteReadbackConfirmed=True)
backlog=R/'docs/product_backlog.json';raw=backlog.read_bytes();data=json.loads(raw);node=data['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104'];node['ownerTargetActivityAdaptation20261108']=record;node.update(status=record['state'],next=record['next'],ownerQuote=record['ownerQuote'])
contract=data['quality_targets']['real_meeting_model_contract_20261103'];gate=next(g for g in contract['gates'] if g['id']=='RM-OVERLAP');gate['targetActivityAdaptation20261108']={'state':record['state'],'evidence':str(C),'sourceAndEvidenceCommit':model_head,'newProductQualification':False,'currentOrdinaryAndAllOtherGatesRetained':True}
assert backlog.read_bytes()==raw,'Original shared backlog changed; re-read and merge before writing';temp=backlog.with_suffix('.activity.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,backlog)
if args.phase=='complete':
    assert record['decision'],'A completed batch needs an actual result/decision, not preparation counters'
    log=R/'docs/development_log.md';marker='原RM-OVERLAP定向适配20261108';assert marker not in log.read_text(encoding='utf8')
    with log.open('a',encoding='utf8') as stream:stream.write('\n\n## '+now+'｜'+marker+'\n\n承接Owner“需要你向着正确方向推进”及可行性/效率询问。实际结果、收益与未解决范围：'+json.dumps(record['decision'],ensure_ascii=False)+'。源码/公开证据及所选小模块权重（若有）提交'+model_head+'已远端核验。原普通模型/原字/原音与全部<5%/跨域/事实/双端实卡/售卖门保持；不以梯度或训练loss下降冒称交付准确率提升。下一步：'+record['next']+'\n')
dest=S/'docs/handoffs/model-target-activity-adaptation-20261108';dest.mkdir(exist_ok=True)
for file in [backlog,R/'docs/development_log.md']:shutil.copyfile(file,S/'docs'/file.name)
(dest/(args.phase+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');shutil.copyfile(__file__,dest/Path(__file__).name)
main_head=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-target-activity-adaptation-20261108'],'Record same-task activity adaptation '+args.phase)
print(json.dumps({'state':record['state'],'modelCommit':model_head,'mainCommit':main_head,'remoteReadbackConfirmed':True}),flush=True)
