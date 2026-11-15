from pathlib import Path
from datetime import datetime
import json,hashlib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';T=D/'supervised-blind-separation-r1'
G=T/'single-source-activity-guard-r1';OLD=T/'continuous-overlap-composition-r1';C=T/'contextual-speaker-binding-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not C.exists();C.mkdir()
original=read(G/'protocol.json');observation=read(Path(original['observationRun'])/'state.json')
assert observation['allOriginalSpeakerPredictionsBitExact']
oldP=read(OLD/'protocol.json');old_wave=read(read(OLD/'asr-execution.json')['separationManifest'])
wave_by_id={r['id']:r for r in old_wave['results']};routes=read(OLD/'routed-composition-protocol.json');locations={r['id']:r for r in routes['cases']}
cases=[]
for case in read(OLD/'audio-only.json'):
    loc=locations[case['id']]
    cases.append(dict(id=case['id'],meeting=case['meeting'],wav=case['wav'],wavSha256=case['wavSha256'],
        sourceStartFrame=loc['sourceStartFrame'],sourceEndFrame=loc['sourceEndFrame'],
        streams=wave_by_id[case['id']]['streams'],overlapRoute=loc['useBothSeparatedStreams']))
write(C/'cases-audio-only.json',cases)
baseline=read(G/'baseline-bindings.json');records={r['meeting']:r for r in observation['results']};meetings=[]
for case in read(G/'audio-only.json'):
    record=records[case['meeting']];file=Path(record['originalCacheRoutes'])
    meetings.append(dict(**case,probabilities=baseline[case['meeting']]['file'],probabilitiesSha256=baseline[case['meeting']]['sha256'],
        legacyOverlap=record['outputs']['legacy-overlap'],cacheRoutes=str(file),cacheRoutesSha256=sha(file)))
write(C/'meetings-audio-only.json',meetings)
E=Path(original['observationRun']).parent.parent/'contextual-speaker-binding-r1'
P={**original,'state':'FROZEN_ORIGINAL_CONTEXT_SPEAKER_BINDING_BEFORE_QUERY_FORWARD',
    'at':datetime.now().astimezone().isoformat(),'controlRun':str(E/'control-r1'),'associationRun':str(E/'association-r1'),
    'meetingInputSha256':sha(C/'meetings-audio-only.json'),'caseInputSha256':sha(C/'cases-audio-only.json'),
    'inputRoute':'Use prior preferred134/19 continuous routing, NOT rejected activity guard140/18. Same final80separator streams and original0.5Nemo activity. All model weights frozen.',
    'method':'Read-only original whole-meeting AOSC prefix for each original chunk. For each separated lane replace only predicted-overlap samples, preserve original context elsewhere, compute exact unnormalized upstream3000-frame frontend patches, project full original-length features, query original encoder/classifier with original cache. Never update cache from counterfactual or use reference/person profiles.',
    'control':'First frozen overlap case of EACH original meeting: source WAV clip/whole PCM exact; unchanged local frontend blocks bit-exact to original features; full-length original embedding chunk bit-exact to saved input query; original encoder query CPU sigmoid bit-exact to original protected speaker probabilities. Any discrepancy stops before association.',
    'association':'At each original10msframe, bind only if exactly2original predicted slots, each query independently has one unique top original slot, the two winners are distinct and equal original2slots, AND both original auxiliary-query categorical heads predict single speech. Otherwise leave both unconfirmed. Nonoverlap retains original single-slot ID or unknown. No threshold/duration/word smoothing, profile selection or forced bijection.',
    'scope':'Audio-interval -> existing predicted model speaker IDs only. Identity accuracy, ASR word timing/person alignment, whole-meeting DER/CER and new recordings remain unqualified. Unknown intervals and all original words/audio retained; unknown never excluded from later scoring.',
    'stop':'One fixed context-association implementation. Fail closed on numerical or input mismatch, preserve partial outputs; no label-conditioned assignment or tuning to the4short cases. No final holdout, no product-default change.',
    'qualityQualified':False,'d2Complete':False}
write(C/'protocol.json',P)
runner=S/'run_contextual_speaker_binding_20261115.py'
text=(S/'run_single_source_activity_guard_20261115.py').read_text(encoding='utf-8')
assert 'single_source_activity_guard_worker_20261115.py' in text
text=text.replace('single_source_activity_guard_worker_20261115.py','contextual_speaker_binding_worker_20261115.py')
assert not runner.exists();compile(text,str(runner),'exec');runner.write_text(text,encoding='utf-8')
helpers=['contextual_speaker_binding_20261115.py','public_nemotron_adaptation_20261115.py','public_nemotron_supervision_20261115.py',
    'moss_windows_resource_limits_20261104.py','companion_community1_adapter_20261115.py','companion_local_pcm_session_20261114.py']
write(C/'worker-binding.json',dict(workerSha256=sha(S/'contextual_speaker_binding_worker_20261115.py'),runnerSha256=sha(runner),
    protocolSha256=sha(C/'protocol.json'),helpers={str(S/n):sha(S/n) for n in helpers}))
print(json.dumps(dict(control=str(C),runRoot=str(E),cases=len(cases),overlapQueries=sum(r['overlapRoute'] for r in cases))))
