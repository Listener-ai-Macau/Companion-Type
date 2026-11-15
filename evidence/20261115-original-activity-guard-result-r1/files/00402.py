from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=M/'src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
G=D/'supervised-blind-separation-r1/single-source-activity-guard-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/supervised-blind-separation-r1/single-source-activity-guard-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
parent=read(D/'protection-r20.json')['modelCommit'];assert read(D/'protection-r20.json')['remoteVerified']
assert subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()==parent
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
assert read(G/'composition-r1/routed-decision.json')['state']=='REJECT_FIXED_ROUTED_THREE_MODEL_COMPOSITION'
DEST=M/'evidence/20261115-original-activity-guard-result-r1';assert not DEST.exists();(DEST/'files').mkdir(parents=True)
items=[]
def take(f,logical):
    before=f.stat();digest=sha(f);assert before.st_size<32*1024**2,(f,before.st_size)
    target=DEST/'files'/(str(len(items)).zfill(5)+f.suffix);shutil.copyfile(f,target)
    assert sha(target)==sha(f)==digest and before.st_mtime_ns==f.stat().st_mtime_ns
    items.append(dict(source=str(f),logicalPath=logical,file=target.relative_to(DEST).as_posix(),sha256=digest,bytes=before.st_size))
for root in [G,E/'observation-r1',E/'composition-r1']:
    for directory,dirs,files in os.walk(root):
        dirs[:]=[n for n in dirs if n not in ['__pycache__','offline-hf-cache','matplotlib-cache']]
        for name in sorted(files):
            f=Path(directory)/name
            if f.name=='run.json':assert read(f).get('finishedAt')
            if f.suffix.lower() in {'.json','.jsonl','.log','.py','.txt','.npy'}:take(f,root.name+'/'+f.relative_to(root).as_posix())
for name in ['freeze_single_source_activity_guard_20261115.py','prepare_activity_guard_composition_20261115.py',Path(__file__).name]:
    take(Path('work')/name,'continuation-tools/'+name)
take(Path('work/bilingual_progress.json'),'canonical-workpoint-snapshot.json')
manifest=dict(state='REJECTED_ORIGINAL_ACTIVITY_GUARD_WITH_EXACT_ORIGINAL_POSTERIORS_PROTECTED',
    at=datetime.now().astimezone().isoformat(),entries=items,parentCommit=parent,
    rawOriginalAudioOrWeightsCopied=False,publicOriginalSpeakerCacheRoutesCopied=True,
    optimizerUpdates=0,qualityQualified=False,d2Complete=False,productDefaultChanged=False)
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
sources=['single_source_activity_guard_worker_20261115.py','run_single_source_activity_guard_20261115.py','score_single_source_activity_guard_20261115.py']
attrs=M/'.gitattributes';body=attrs.read_bytes()
for rule in [DEST.relative_to(M).as_posix()+'/** -text -whitespace']+['src/'+n+' -text -whitespace' for n in sources]:
    if rule.encode() not in body:body+=b'\n'+rule.encode()+b'\n'
attrs.write_bytes(body)
with (M/'README.md').open('a',encoding='utf-8') as f:
    f.write('\n\n'+manifest['at']+' 原预训练3类activity头双头一致路由已拒绝：完整2val原说话人概率逐帧全等，补原头160块无训练；原32多轮161→140（旧候选134）、单人13→18（旧候选19），一会议48→51。保留旧较好候选及原默认，不追加阈值/时长/模型变体；真实原AOSC缓存已保存以推进独立人物关联。D2与售卖仍未完成。\n')
paths=['.gitattributes','README.md']+['src/'+n for n in sources]+[p.relative_to(M).as_posix() for p in DEST.rglob('*') if p.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(p.encode() for p in paths)+b'\0',check=True)
for name in paths:
    raw=(M/name).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+name],text=True).strip()==expected,name
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m','Reject frozen original activity-head guard and preserve exact whole-meeting cache evidence'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt=dict(state=manifest['state'],modelCommit=head,exactByteStagedFiles=len(paths),evidenceFiles=len(items),evidenceBytes=sum(x['bytes'] for x in items),remoteVerified=False,d2Complete=False)
target=D/'protection-r21.json';target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
result=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=600)
(D/'push-r21-model.log').write_text(result.stdout+result.stderr,encoding='utf-8');assert result.returncode==0
result=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=60)
assert result.returncode==0 and result.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
