from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--aligned',action='store_true');p.add_argument('--continuous',action='store_true');a=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';S=M/'src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
T=D/'supervised-blind-separation-r1';C=T/('continuous-overlap-composition-r1' if a.continuous else 'natural-window-unit-alignment-r1' if a.aligned else 'natural-composition-r1')
E=Path('E:/CodexData/Companion/product-d1d2-20261114/supervised-blind-separation-r1')/C.name
number=20 if a.continuous else 19 if a.aligned else 18
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
parent_receipt=D/('protection-r'+str(number-1)+'.json')
parent=read(parent_receipt)['modelCommit']
assert read(parent_receipt)['remoteVerified']
assert subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()==parent
assert not subprocess.check_output(['git','-C',str(M),'diff','--cached','--name-only'],text=True).strip()
assert read(E/'asr-r1/state.json')['state']=='COMPLETE_FIXED_SEPARATION_ASR_COMPOSITION_SCORING_PENDING'
assert (C/'decision.json').exists() and (C/'routed-decision.json').exists()
DEST=M/('evidence/20261115-continuous-overlap-composition-r1' if a.continuous else 'evidence/20261115-supervised-separation-window-unit-repair-r1' if a.aligned else 'evidence/20261115-supervised-separation-natural-result-r1')
assert not DEST.exists();(DEST/'files').mkdir(parents=True);items=[]
def take(f,logical):
    before=f.stat();digest=sha(f);assert before.st_size<32*1024**2,(f,before.st_size)
    target=DEST/'files'/(str(len(items)).zfill(5)+f.suffix)
    shutil.copyfile(f,target);assert sha(target)==sha(f)==digest and before.st_mtime_ns==f.stat().st_mtime_ns
    items.append(dict(source=str(f),logicalPath=logical,file=target.relative_to(DEST).as_posix(),bytes=before.st_size,sha256=digest))
for root in ([C,E/'routed-waveforms',E/'asr-r1'] if a.continuous else [C,E/'control-r1',E/'separate-r1',E/'asr-r1']):
    for directory,dirs,files in os.walk(root):
        dirs[:]=[n for n in dirs if n not in ['__pycache__','offline-hf-cache','matplotlib-cache']]
        for name in sorted(files):
            f=Path(directory)/name
            if f.name=='run.json':assert read(f).get('finishedAt')
            if f.suffix.lower() in {'.json','.jsonl','.log','.py','.txt','.npy'}:take(f,root.name+'/'+f.relative_to(root).as_posix())
for name in ['prepare_supervised_separator_natural_validation_20261115.py','score_supervised_separator_natural_router_20261115.py',
             'record_supervised_blind_separator_result_20261115.py','sync_supervised_separator_natural_waveforms_20261115.py',Path(__file__).name]:
    take(Path('work')/name,'continuation-tools/'+name)
if a.aligned:
    for name in ['align_separator_training_inference_units_20261115.py','score_window_aligned_separator_router_20261115.py',
                 'analyze_separator_window_unit_alignment_20261115.py','attribute_separator_natural_insertions_20261115.py']:
        take(Path('work')/name,'continuation-tools/'+name)
    take(T/'window-unit-repair.json','window-unit-repair.json')
    take(T/'natural-composition-r1/insertion-attribution.json','prior-failure-insertion-attribution.json')
    take(T/'continuous-routing-r1/routing-plan.json','continuous-routing-input-plan.json')
if a.continuous:
    for name in ['prepare_continuous_overlap_composition_20261115.py','score_continuous_overlap_composition_20261115.py','attribute_separator_natural_insertions_20261115.py']:
        take(Path('work')/name,'continuation-tools/'+name)
    take(T/'continuous-routing-r1/routing-plan.json','continuous-routing-input-plan.json')
take(Path('work/bilingual_progress.json'),'canonical-workpoint-snapshot.json')
take(Path('outputs/Companion-分离组合模型进度-20261115.txt'),'owner-separation-composition-note.txt')
manifest=dict(state='FINAL_SUPERVISED_SEPARATOR_ALL32_NATURAL_TWO_STREAMS_AND64_ASR_WORDS_PROTECTED',
    at=datetime.now().astimezone().isoformat(),entries=items,parentCommit=parent,
    priorFullTrainedWeightProtection=str(D/'protection-r17.json'),
    originalAudioOrBaseWeightsCopied=False,allDerivedWaveformsAndRawAsrRetained=True,
    qualityQualified=False,d2Complete=False,productDefaultChanged=False,ownerParticipationRequired=False)
if a.aligned:
    manifest.update(correctnessRepair='Identical per-window training/source-validation common-scale operation before CSS; previous whole-clip-order failure retained in parent.',
        trainingWeightsChanged=False,previousFailureProtection=str(D/'protection-r18.json'),
        sourceForwardEquivalenceSha256=sha(E/'control-r1/source-forward-equivalence.json'))
if a.continuous:
    manifest.update(continuousTimeAudioRoutingImplemented=True,originalNonoverlapPcmPreserved=True,
        newTraining=False,newSeparationNeuralCalls=0,separatedStreamSpeakerAssociationImplemented=False,
        originalCoarseFailureProtection=str(D/'protection-r19.json'))
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
sources=['continuous_meeting_audio_routing_20261115.py','continuous_overlap_composition_worker_20261115.py','run_continuous_overlap_composition_20261115.py'] if a.continuous else ['window_aligned_separator_worker_20261115.py','run_window_aligned_separator_20261115.py','compile_continuous_meeting_routing_20261115.py'] if a.aligned else ['supervised_separator_natural_worker_20261115.py','run_supervised_separator_natural_20261115.py']
attrs=M/'.gitattributes';body=attrs.read_bytes()
for rule in [DEST.relative_to(M).as_posix()+'/** -text -whitespace']+['src/'+n+' -text -whitespace' for n in sources]:
    if rule.encode() not in body:body+=b'\n'+rule.encode()+b'\n'
attrs.write_bytes(body)
decision=read(C/'routed-decision.json')
with (M/'README.md').open('a',encoding='utf-8') as f:
    f.write('\n\n'+manifest['at']+' 固定盲分离完整核80更新后：84独立源门通过，原自然32/完整64路原ASR及原Nemotron固定路由结果：'+decision['state']+'。所有实际使用路文字计分，未改参考/窗口/阈值；原整会中英文人物门与最终留出保持，不能据此称产品售卖合格。完整分离权重在父提交保护。\n')
paths=['.gitattributes','README.md']+['src/'+n for n in sources]+[p.relative_to(M).as_posix() for p in DEST.rglob('*') if p.is_file()]
subprocess.run(['git','-C',str(M),'add','--force','--pathspec-from-file=-','--pathspec-file-nul'],input=b'\0'.join(p.encode() for p in paths)+b'\0',check=True)
for name in paths:
    raw=(M/name).read_bytes();expected=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert subprocess.check_output(['git','-C',str(M),'rev-parse',':'+name],text=True).strip()==expected,name
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','-C',str(M),'commit','--quiet','-m','Record fixed trained separator complete natural meeting composition and word gate'],check=True)
head=subprocess.check_output(['git','-C',str(M),'rev-parse','HEAD'],text=True).strip()
receipt=dict(state=manifest['state'],modelCommit=head,exactByteStagedFiles=len(paths),evidenceFiles=len(items),
    evidenceBytes=sum(i['bytes'] for i in items),remoteVerified=False,d2Complete=False)
target=D/('protection-r'+str(number)+'.json');target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
ssh='ssh -o HostName=github.com -p22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'
base=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','core.sshCommand='+ssh,'-C',str(M)]
result=subprocess.run(base+['push','origin','research/moss-resume-20261105'],capture_output=True,text=True,timeout=600)
(D/('push-r'+str(number)+'-model.log')).write_text(result.stdout+result.stderr,encoding='utf-8');assert result.returncode==0
result=subprocess.run(base+['ls-remote','origin','refs/heads/research/moss-resume-20261105'],capture_output=True,text=True,timeout=60)
assert result.returncode==0 and result.stdout.split()[0]==head
receipt['remoteVerified']=True;target.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt))
