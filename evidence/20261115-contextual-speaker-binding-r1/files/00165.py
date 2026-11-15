from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=M/'src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'supervised-blind-separation-r1/contextual-speaker-binding-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/supervised-blind-separation-r1/contextual-speaker-binding-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
parent=read(D/'protection-r21.json')['modelCommit'];assert read(D/'protection-r21.json')['remoteVerified']
assert subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()==parent
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
assert read(C/'association-validation.json')['state']=='PASS_AUDIO_INTERVAL_COVERAGE_AND_ORIGINAL_MODEL_ID_CONTRACT_ONLY'
DEST=M/'evidence/20261115-contextual-speaker-binding-r1';assert not DEST.exists();(DEST/'files').mkdir(parents=True);items=[]
def take(f,logical):
    before=f.stat();digest=sha(f);assert before.st_size<32*1024**2,(f,before.st_size)
    target=DEST/'files'/(str(len(items)).zfill(5)+f.suffix);shutil.copyfile(f,target)
    assert sha(target)==sha(f)==digest and before.st_mtime_ns==f.stat().st_mtime_ns
    items.append(dict(source=str(f),logicalPath=logical,file=target.relative_to(DEST).as_posix(),sha256=digest,bytes=before.st_size))
for root in [C,D/'ctx-scope-r1',E/'control-r1',E/'association-r1',E/'association-r2',E/'association-r3']:
    for directory,dirs,files in os.walk(root):
        dirs[:]=[n for n in dirs if n not in ['__pycache__','offline-hf-cache','matplotlib-cache']]
        for name in sorted(files):
            f=Path(directory)/name
            if f.name=='run.json':assert read(f).get('finishedAt')
            if f.suffix.lower() in {'.json','.jsonl','.log','.py','.txt','.npy'}:take(f,root.name+'/'+f.relative_to(root).as_posix())
for name in ['freeze_contextual_speaker_binding_20261115.py','fix_contextual_binding_inference_scope_20261115.py',
    'validate_contextual_speaker_binding_20261115.py',Path(__file__).name]:take(Path('work')/name,'continuation-tools/'+name)
take(Path('work/bilingual_progress.json'),'canonical-workpoint-snapshot.json')
take(Path('outputs/Companion-语音推进与交付评估-20261115.txt'),'owner-progress-and-delivery-estimate.txt')
manifest=dict(state='CONTEXTUAL_AUDIO_SPEAKER_ASSOCIATION_CANDIDATE_AND_FAILURES_PROTECTED',
    at=datetime.now().astimezone().isoformat(),entries=items,parentCommit=parent,
    originalAudioOrWeightsCopied=False,newTraining=False,previousOriginalCacheProtection=str(D/'protection-r21.json'),
    humanSpeakerIdentityVerified=False,wordSpeakerAlignmentImplemented=False,qualityQualified=False,d2Complete=False,productDefaultChanged=False)
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
sources=['contextual_speaker_binding_20261115.py','contextual_speaker_binding_worker_20261115.py','run_contextual_speaker_binding_20261115.py']
attrs=M/'.gitattributes';body=attrs.read_bytes()
for rule in [DEST.relative_to(M).as_posix()+'/** -text -whitespace']+['src/'+n+' -text -whitespace' for n in sources]:
    if rule.encode() not in body:body+=b'\n'+rule.encode()+b'\n'
attrs.write_bytes(body)
with (M/'README.md').open('a',encoding='utf-8') as f:
    f.write('\n\n'+manifest['at']+' 新增只读原长会AOSC上下文的分离音频人物编号关联候选。两会原音/声学块/全长嵌入/原分类后验全等控制通过；32段/28路反事实查询完成，20.124375s原预测重叠中6.95s满足模型一致条件，13.174375s保留未确认。这不是实人身份准确率，未做词人物对齐。原音和64原ASR不变，未改默认。推理张量作用域错误及MAX_PATH准备失败/误启未修版本均保留，0分离query两次失败后同公式修复，原word/DER门及售卖仍开放。\n')
paths=['.gitattributes','README.md']+['src/'+n for n in sources]+[p.relative_to(M).as_posix() for p in DEST.rglob('*') if p.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(p.encode() for p in paths)+b'\0',check=True)
for name in paths:
    raw=(M/name).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+name],text=True).strip()==expected,name
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m','Implement original-cache contextual speaker binding with explicit unconfirmed regions'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt=dict(state=manifest['state'],modelCommit=head,exactByteStagedFiles=len(paths),evidenceFiles=len(items),evidenceBytes=sum(x['bytes'] for x in items),remoteVerified=False,d2Complete=False)
target=D/'protection-r22.json';target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
result=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=600)
(D/'push-r22-model.log').write_text(result.stdout+result.stderr,encoding='utf-8');assert result.returncode==0
result=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=60)
assert result.returncode==0 and result.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
