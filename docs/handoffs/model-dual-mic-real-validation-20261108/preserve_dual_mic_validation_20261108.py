"""Save the single bounded real dual-input experiment in the existing backlog."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,shutil,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['checkpoint','complete'],required=True);args=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261108-dual-mic-real-meeting-validation';EV=M/'evidence/20261108-dual-mic-real-meeting-validation'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));optional=lambda p:read(p) if Path(p).exists() else None
EV.mkdir(exist_ok=True)
for file in C.rglob('*'):
    if file.is_file() and file.suffix in ['.json','.jsonl','.log','.txt']:
        target=EV/file.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
def git(root,*argv):
    deadline=time.monotonic()+45
    while True:
        q=subprocess.run(['git','-c','maintenance.auto=false','-c','pack.threads=1','-c','pack.windowMemory=32m',*argv],cwd=root,env=env,capture_output=True,text=True)
        if q.returncode and 'index.lock' in q.stderr and 'File exists' in q.stderr and time.monotonic()<deadline:time.sleep(1);continue
        if q.returncode:raise RuntimeError((q.stdout+q.stderr)[-4000:])
        return q.stdout.strip()
def ship(root,paths,message):
    git(root,'add','--',*paths)
    if git(root,'diff','--cached','--name-only','--',*paths):
        git(root,'-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*paths)
        git(root,'commit','--only','-m',message,'--',*paths)
    h=git(root,'rev-parse','HEAD');b=git(root,'branch','--show-current');git(root,'push','origin','HEAD:refs/heads/'+b)
    assert git(root,'ls-remote','origin','refs/heads/'+b).split()[0]==h;return h
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'phase':args.phase,
    'ownerOriginal':'那你看看验证一下咯  开始看看怎么继续推进吧',
    'ownerCompressionQuestion':'然后你看看是不是音频压缩了比较难分析要解压了好分析一点',
    'evidence':str(C),'protocol':optional(C/'protocol-summary.json'),'audioPreparation':optional(C/'audio-preparation.json'),
    'numericalProof':optional(C/'numpy-numerical-proof.json'),'run':optional(C/'run-r2.json'),'review':optional(C/'review.json'),'decision':optional(C/'decision.json'),
    'noHardGateControl':{'run':optional(C/'no-hard-gate/run-r2.json'),'review':optional(C/'no-hard-gate/review.json'),'preparation':optional(C/'no-hard-gate/preparation.json')},
    'productDefaultChanged':False,'newHardwareAccess':False,'newTrainingRuns':0,'qualityQualified':False}
point=record['decision'] or record['noHardGateControl']['review'] or record['noHardGateControl']['run'] or record['review'] or record['run'] or record['protocol'];record['state']=point['state']
record['next']=point.get('next','继续原RM-OVERLAP：固定同一原音/预测活动/ASR，对照单路活动分段、原始双路GSS和Opus解码双路GSS，全部逐人评分后决定保留或停止；不扫模型/窗口/码率、不占实板，原普通/严格<5%/纪要事实/双端实卡/售卖门保留。')
(EV/'observed-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
upstream=Path(read(C/'upstream-source.json')['sourceRoot'])
paths=['.gitattributes','README.md','evidence/20261108-dual-mic-real-meeting-validation',str(upstream.relative_to(M)).replace('\\','/')]
paths += [str(p.relative_to(M)).replace('\\','/') for p in (M/'src').glob('*gss*20261108.py')]
model_head=ship(M,paths,'Preserve real dual-input and codec validation '+args.phase);record.update(sourceAndEvidenceCommit=model_head,remoteReadbackConfirmed=True)
path=R/'docs/product_backlog.json'
for attempt in range(8):
    raw=path.read_bytes();d=json.loads(raw);node=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
    node['ownerDualMicRealMeetingValidation20261108']=record;node.update(status=record['state'],next=record['next'],ownerQuote=record['ownerOriginal']+'；'+record['ownerCompressionQuestion'])
    gate=next(g for g in d['quality_targets']['real_meeting_model_contract_20261103']['gates'] if g['id']=='RM-OVERLAP')
    gate['dualMicRealMeetingValidation20261108']={'state':record['state'],'sourceAndEvidenceCommit':model_head,'evidence':str(C),'qualified':False}
    if path.read_bytes()!=raw:continue
    temp=path.with_suffix('.dual-validation.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if path.read_bytes()!=raw:temp.unlink();continue
    try:os.replace(temp,path)
    except PermissionError as error:
        if getattr(error,'winerror',None) not in [5,32,33]:raise
        temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2));continue
    break
else:raise RuntimeError('Shared backlog changed repeatedly; source safe, retain external progress')
if args.phase=='complete':
    assert record['decision'];log=R/'docs/development_log.md';marker='原RM-OVERLAP真实双路与压缩对照20261108';assert marker not in log.read_text(encoding='utf8')
    with log.open('a',encoding='utf8') as stream:stream.write('\n\n## '+record['at']+'｜'+marker+'\n\n承接Owner“'+record['ownerOriginal']+'”及压缩/解码疑问“'+record['ownerCompressionQuestion']+'”。实际结果：'+json.dumps(record['decision'],ensure_ascii=False)+'。源码/公式来源/数值证明/全部原始生成及失败证据'+model_head+'已远端核验；原音仅本机，未占实板/手机或改产品默认，原全部<5%/事实/双端实卡/售卖门保留。下一步：'+record['next']+'\n')
dest=S/'docs/handoffs/model-dual-mic-real-validation-20261108';dest.mkdir(exist_ok=True)
for file in [path,R/'docs/development_log.md']:shutil.copyfile(file,S/'docs'/file.name)
(dest/(args.phase+'-result.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');shutil.copyfile(__file__,dest/Path(__file__).name)
main_head=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/model-dual-mic-real-validation-20261108'],'Record same-task dual-input validation '+args.phase)
print(json.dumps({'state':record['state'],'modelCommit':model_head,'mainCommit':main_head,'remoteReadbackConfirmed':True}),flush=True)
