"""Freeze one raw-preserving recovery rule before any new neural result."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil
from practical_io_20261107 import atomic_json
from practical_qwen_bounded_decode_20261107 import accepted
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery'
C=B/'practical-qwen-bounded-r4';base=B/'practical-qwen-signal-r3'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not C.exists();old=read(base/'review.json')
assert old['state']=='NATIVE_QWEN_ORDINARY_COMPLETE_COMPLEX_DECODE_LOOP_FAILED_SALE_OPEN'
C.mkdir();src=Path(__file__).parent
files={};counts={}
for case in read(base/'full/audio-only.json'):
    good=bad=0
    for file in sorted((base/'full/transcripts'/case['meeting']/'windows').glob('*.raw.json')):
        files[case['meeting']+'/'+file.name]=sha(file)
        if accepted(read(file)['raw']):good+=1
        else:bad+=1
    counts[case['meeting']]={'acceptedRoots':good,'failedRoots':bad}
assert counts['S_R004S03C01']=={'acceptedRoots':78,'failedRoots':0}
assert counts['L_R003S01C02']=={'acceptedRoots':34,'failedRoots':1}
shutil.copyfile(base/'full/audio-only.json',C/'audio-only.json')
atomic_json(C/'seed-manifest.json',{'baseControl':str(base),'files':files,'rootCounts':counts,'originalFilesRemainImmutable':True})
protocol={'declaredAt':datetime.now().astimezone().isoformat(timespec='seconds'),'baseControl':str(base),'baseProtocolSha256':sha(base/'protocol.json'),
  'baseWorkerSourceSha256':sha(src/'practical_qwen_full_worker_20261107.py'),
  'workerSourceSha256':sha(src/'practical_qwen_bounded_worker_20261107.py'),
  'recoverySourceSha256':sha(src/'practical_qwen_bounded_decode_20261107.py'),
  'maximumSplitDepth':2,'minimumLeafSamples':120000,'repeatCopies':20,'maximumRepeatBlockTokens':8,
  'rule':'On missing natural EOS or the existing short-gate20-copy token loop, retain the failed raw node, bisect the entire original input and decode both children. At most2levels; no child shorter than7.5s. Exhaustion is a failure. Early loop stop changes no generated prefix. No word deletion, VAD trimming, token-budget increase, model/prompt/weight change, reference or participant count.',
  'normalOutputPolicy':'Keep every accepted original raw ID/text exactly; same frozen policy across both whole meetings.',
  'modelParametersChanged':False,'rawFailedParentReplacedByClaimedEos':False,'qualityQualified':False,
  'pilotCases':'One ordinary original first30s fresh generation must exactly match R3; real failed root34 retains its old failed parent and must recover all samples via accepted children. Pilot is exposed development, not independent qualification.',
  'originalFailedReview':str(base/'review.json')}
atomic_json(C/'protocol.json',protocol)
(C/'full').mkdir();shutil.copyfile(C/'audio-only.json',C/'full/audio-only.json');shutil.copyfile(base/'full/scoring-only.json',C/'full/scoring-only.json')
atomic_json(C/'prepared.json',{'state':'FROZEN_BOUNDED_NATIVE_RECOVERY_BEFORE_PILOT_NO_NEW_INFERENCE','protocolSha256':sha(C/'protocol.json'),'rootCounts':counts,'referenceOpened':False,'newModelsDownloaded':False,'qualityQualified':False})
print(json.dumps({'control':str(C),'rootCounts':counts,'state':'PREPARED_ONLY'}))
