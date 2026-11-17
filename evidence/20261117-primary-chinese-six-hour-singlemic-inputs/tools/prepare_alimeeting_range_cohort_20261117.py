"""Freeze six hours of complete original utterances for bounded range acquisition."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import hashlib,json,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
O=E/'alimeeting-official-intake-r2';old=O/'clean-source-cohort-r1/protocol.json'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
P=read(old);manifest=Path(P['candidateManifest']);assert sha(manifest)==P['candidateManifestSha256']
cases=defaultdict(list)
for line in manifest.read_text(encoding='utf-8').splitlines():
    r=json.loads(line);cases[r['meeting']].append(r)
for meeting in cases:cases[meeting].sort(key=lambda r:hashlib.sha256(('Ali-range-sixhours-20261117/'+r['id']).encode()).hexdigest())
selected=[];duration=0;round_index=0
while duration<6*3600*16000:
    added=0
    for meeting in sorted(cases):
        if round_index>=len(cases[meeting]):continue
        r=cases[meeting][round_index];selected.append(r);duration+=r['frames'];added+=1
        if duration>=6*3600*16000:break
    assert added,'Insufficient original nonoverlap material';round_index+=1
out=O/'range-training-cohort-r2';out.mkdir()
source={c['meeting']:c for c in P['allCleanSources']}
first=read(O/'first-mic-source-r1/post-source-check-r2/completed.json')
assert sha(first['output'])==first['outputSha256']
raw_bytes=sum(r['frames']*16 for r in selected if r['meeting']!='R0003_M0046')
clip_bytes=sum(r['frames']*2+44 for r in selected)
owned=sum(p.stat().st_size for p in E.rglob('*') if p.is_file())
extra_ingress=2*first['sourceExpectedBytes']
envelope=owned+extra_ingress+raw_bytes+clip_bytes
assert envelope<12*1024**3,'Original12GiB conservative envelope'
path=out/'selected-original-utterances.jsonl'
with path.open('x',encoding='utf-8') as f:
    for r in selected:f.write(json.dumps(r,ensure_ascii=False)+'\n')
plan={'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_ORIGINAL_SIX_HOUR_NONOVERLAP_CHINESE_RANGE_INPUT_NO_TRAINING',
    'selectedManifest':str(path),'selectedManifestSha256':sha(path),'sourceCatalog':source,
    'sourceCatalogProof':str(O/'primary-wave-headers-r1/completed.json'),
    'participantProof':str(O/'primary-train-eval-person-split.json'),
    'examples':len(selected),'frames':duration,'audioSeconds':duration/16000,
    'meetings':len({r['meeting'] for r in selected}),'venues':len({r['meeting'].split('_')[0] for r in selected}),
    'speakers':len({r['sourceSpeakerId'] for r in selected}),
    'selection':'FixedSHA256 utterance order within each clean source; round-robin over all clean meetings until at least6h. Keep the final complete utterance. No candidate outputs/validation labels; every original text and full interval is unchanged.',
    'sourceQualityExclusion':P['excludedWholeSources'],'paddingSeconds':0,'targetTextsRewritten':False,
    'acquisition':'ExactHTTP byte range for each original complete utterance from8channelPCM; retain channel0 byte-for-byte. Reuse independently verified full mono where available.',
    'existingVerifiedFirstMono':first,'cpuPercent':5,'ioThreads':4,'privateMemoryBytes':256*1024**2,
    'minimumAvailableBytes':3414499000,'minimumDiskFreeBytes':50*1024**3,'maximumOwnedNewDataBytes':12*1024**3,
    'budget':{'currentOwnedBytes':owned,'alreadySpentFullSourceTransferAndVerificationBytes':extra_ingress,
        'plannedNewRawRangeBytes':raw_bytes,'plannedNewClipBytes':clip_bytes,'conservativeCombinedEnvelopeBytes':envelope},
    'publishedAliTrainEvalGlobalSpeakerIntersection':[],'originalAishellCrossCorpusIsolationProven':False,
    'originalQualityAndFinalHoldoutGatesChanged':False,'newNeuralCalls':0,'parameterUpdates':0,'trainingAdmitted':False,
    'dependencies':[{'file':str(p),'sha256':sha(p)} for p in [manifest,old,O/'primary-wave-headers-r1/completed.json',
        O/'primary-train-eval-person-split.json',Path(__file__),Path(__file__).with_name('alimeeting_public_oss_20261117.py')]]}
atomic_json(out/'protocol.json',plan)
print(json.dumps({k:plan[k] for k in ['state','examples','audioSeconds','meetings','venues','speakers','budget']},ensure_ascii=False))
