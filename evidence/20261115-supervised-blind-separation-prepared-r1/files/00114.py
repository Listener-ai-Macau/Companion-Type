from pathlib import Path
from datetime import datetime
import argparse, hashlib, json, os, shutil, subprocess

p=argparse.ArgumentParser();p.add_argument('--stage',choices=['prepared','result'],required=True);a=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=M/'src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'supervised-blind-separation-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/supervised-blind-separation-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
prepared=a.stage=='prepared';number=16 if prepared else 17
parent=read(D/('protection-r'+str(number-1)+'.json'))['modelCommit']
DEST=M/('evidence/20261115-supervised-blind-separation-'+a.stage+'-r1')
assert not DEST.exists()
assert subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()==parent
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
assert read(E/'baseline-r1/state.json')['state']=='COMPLETE_FROZEN_SYNTHETIC_SOURCE_PREDICTIONS_SCORE_PENDING'
if not prepared:
    assert (C/'source-decision.json').exists()
    assert read(E/'train-r1/state.json')['state']=='COMPLETE_ONE_FIXED_BLIND_SEPARATOR_TRAINING_PASS'
(DEST/'files').mkdir(parents=True);items=[]
def take(f,logical):
    before=f.stat();digest=sha(f);assert before.st_size<32*1024**2,(f,before.st_size)
    target=DEST/'files'/(str(len(items)).zfill(5)+f.suffix)
    shutil.copyfile(f,target);assert sha(target)==sha(f)==digest and before.st_mtime_ns==f.stat().st_mtime_ns
    items.append(dict(source=str(f),logicalPath=logical,file=target.relative_to(DEST).as_posix(),bytes=before.st_size,sha256=digest))
roots=[C,E/'control-r1',E/'baseline-r1'] if prepared else [C,E/'candidate-r1']
for root in roots:
    for directory,dirs,files in os.walk(root):
        dirs[:]=[n for n in dirs if n not in ['__pycache__','offline-hf-cache','matplotlib-cache']]
        for name in sorted(files):
            f=Path(directory)/name
            if f.name=='run.json':assert 'finishedAt' in read(f)
            if f.suffix.lower() in {'.json','.jsonl','.log','.py','.txt','.npy'}:take(f,root.name+'/'+f.relative_to(root).as_posix())
if not prepared:
    for name in ['state.json','run.json','worker.log','history.jsonl','latest-checkpoint.json']:
        f=E/'train-r1'/name
        if f.exists():take(f,'train-r1/'+name)
    final=read(E/'train-r1/latest-checkpoint.json')
    for shard in final['modelShards']:take(Path(shard['file']),'final-trained-model/'+Path(shard['file']).name)
    take(Path(final['modelShards'][0]['file']).parent/'checkpoint.json','final-trained-model/checkpoint.json')
tools=['prepare_blind_separator_supervision_20261115.py','split_blind_separator_validation_inputs_20261115.py',
       'freeze_supervised_blind_separator_20261115.py',Path(__file__).name]
for name in tools:take(Path('work')/name,'continuation-tools/'+name)
take(Path('work/bilingual_progress.json'),'canonical-workpoint-snapshot.json')
take(Path('outputs/Companion-分离组合模型进度-20261115.txt'),'owner-separation-composition-note.txt')
manifest=dict(state='SUPERVISED_BLIND_SEPARATOR_SOURCE_CONTROL_AND_BASELINE_PROTECTED' if prepared else 'FINAL_SUPERVISED_BLIND_SEPARATOR_AND_FIXED_SOURCE_GATE_PROTECTED',
    at=datetime.now().astimezone().isoformat(),entries=items,parentCommit=parent,
    originalAudioOrBaseWeightsCopied=False,optimizerCopied=False,
    fullFinalSeparatorWeightsCopied=not prepared,qualityQualified=False,d2Complete=False,
    productDefaultChanged=False,ownerParticipationRequired=False)
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
sources=['blind_separator_supervision_20261115.py','blind_separator_training_worker_20261115.py',
         'run_supervised_blind_separator_20261115.py','score_supervised_blind_separator_20261115.py']
attrs=M/'.gitattributes';body=attrs.read_bytes()
for rule in [DEST.relative_to(M).as_posix()+'/** -text -whitespace']+['src/'+n+' -text -whitespace' for n in sources]:
    if rule.encode() not in body:body+=b'\n'+rule.encode()+b'\n'
attrs.write_bytes(body)
with (M/'README.md').open('a',encoding='utf-8') as f:
    f.write('\n\n'+manifest['at']+' '+manifest['state']+'：同一55.7M盲分离核公开会议已知一/双源PIT源聚合SDR监督，固定1pass/319窗/80更新；原ASR与人物模型保持。原自然词评分和完整中英文人物门不变。'+('源控制和84原模型源基线完成，训练进行中。' if prepared else '最终完整权重逐分片归档，优化器/RNG保留E盘恢复；合成源门结论见source-decision，不代表自然会议或售卖达标。')+'\n')
paths=['.gitattributes','README.md']+['src/'+n for n in sources]+[p.relative_to(M).as_posix() for p in DEST.rglob('*') if p.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(p.encode() for p in paths)+b'\0',check=True)
for name in paths:
    raw=(M/name).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+name],text=True).strip()==expected,name
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m',
    'Preserve fixed blind separator training source controls and independent baseline' if prepared else 'Protect final blind separator training weights and fixed source validation'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt=dict(state=manifest['state'],modelCommit=head,exactByteStagedFiles=len(paths),evidenceFiles=len(items),
             evidenceBytes=sum(i['bytes'] for i in items),remoteVerified=False,d2Complete=False)
target=D/('protection-r'+str(number)+'.json');target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
result=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=120)
(D/('push-r'+str(number)+'-model.log')).write_text(result.stdout+result.stderr,encoding='utf-8');assert result.returncode==0
result=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=60)
assert result.returncode==0 and result.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt))
