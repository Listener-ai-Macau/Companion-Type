"""Freeze the routed candidate on every predicted-overlap root of full L."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import ast,hashlib,json,shutil,wave
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery';old=B/'practical-conditioned-ps4-r1';C=B/'practical-conditioned-ps4-full-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert read(old/'verified-review.json')['componentRetentionRulePassed']
assert not C.exists();C.mkdir();limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/.model-cache/ps4-target-extraction-20261107/full-L-audio');E.mkdir(exist_ok=False)
for name in ['model-ready.json','audio-frontend-source.json','hip-inventory.json']:shutil.copyfile(old/name,C/name)
case=next(c for c in read(B/'practical-qwen-native17-r5/audio-only.json') if c['meeting']=='L_R003S01C02')
assert sha(case['audio'])==case['audioSha256']
journal_file=B/'native8-f16-full-r1/results'/case['meeting']/'speaker-journal.json';journal=read(journal_file)
events=defaultdict(list)
for r in journal['segments']:events[r['start']].append((r['speaker'],1));events[r['end']].append((r['speaker'],-1))
points=sorted(events);active=defaultdict(int);regions=[]
for i,start in enumerate(points[:-1]):
    for person,delta in events[start]:
        active[person]+=delta
        if not active[person]:del active[person]
    if points[i+1]>start and active:regions.append((start,points[i+1],tuple(sorted(active))))
anchors={a['speaker']:a for c in read(old/'audio-only.json') if c['meeting']==case['meeting'] for a in c['anchors']}
assert len(anchors)==6
selected=[];all_roots=[]
with wave.open(case['audio'],'rb') as stream:
    count=stream.getnframes();params=stream.getparams()
    for index,lo in enumerate(range(0,count,480000)):
        hi=min(count,lo+480000);people=set();overlap=triple=solo=0.
        for a,b,who in regions:
            d=max(0.,min(hi/16000,b)-max(lo/16000,a))
            if not d:continue
            people.update(who)
            if len(who)==1:solo+=d
            if len(who)>=2:overlap+=d
            if len(who)>=3:triple+=d
        row={'id':case['meeting']+'-root-%06d'%index,'meeting':case['meeting'],'kind':'full-predicted-overlap',
            'rootIndex':index,'startSample':lo,'endSample':hi,'predictedPeople':sorted(people),
            'predictedOverlapSeconds':overlap,'predictedTripleSeconds':triple,'predictedSoloSeconds':solo,
            'route':'verify_extracted_targets' if len(people)>=2 and overlap>0 else 'retain_original'}
        all_roots.append(row.copy())
        if row['route']=='retain_original':continue
        dest=E/(row['id']+'-mixture.wav');stream.setpos(lo);pcm=stream.readframes(hi-lo)
        with wave.open(str(dest),'wb') as output:output.setparams(params);output.writeframes(pcm)
        row.update(audio=str(dest),audioSha256=sha(dest),audioSeconds=(hi-lo)/16000,
            originalFullAudio=case['audio'],originalFullAudioSha256=case['audioSha256'],
            journal=str(journal_file),journalSha256=sha(journal_file),
            anchors=[anchors[p] for p in sorted(people) if p in anchors],
            peopleWithoutPredictedSoloAnchor=[p for p in sorted(people) if p not in anchors])
        selected.append(row)
atomic_json(C/'audio-only.json',selected)
atomic_json(C/'full-route-plan.json',{'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],'roots':all_roots,
    'originalAlignedDocument':str(B/'practical-alignment-r1/derived-onset/transcripts'/case['meeting']/'model-output.json'),
    'originalAttributionReview':str(B/'practical-alignment-r1/derived-onset/transcripts'/case['meeting']/'attribution-review.json'),
    'scope':'All full-L roots selected before new inference from frozen model activity only. Nonoverlap roots retain all original text/person assignments. No participant count/GT/text used to select inputs.'})
atomic_json(C/'global-anchors.json',[anchors[p] for p in sorted(anchors)])
seeds={};old_lanes=read(old/'asr-manifest-r2.json');identity={r['id']:r for r in read(old/'identity-state.json')['comparisons']}
for lane in read(old/'separation-manifest-r2.json'):
    match=next((c for c in selected if c['id']+'-speaker-'+str(lane['predictedSpeaker'])==lane['id']),None)
    if match is None:continue
    assert match['audioSha256']==lane['inputMixtureSha256']
    sf=old/'separation-outputs-r2'/(lane['id']+'.json');af=old/'asr-outputs-r2'/lane['id']/'completed.json'
    seeds[lane['id']]={'separationFile':str(sf),'separationFileSha256':sha(sf),'asrFile':str(af),'asrFileSha256':sha(af),'identity':identity[lane['id']],
        'sameWeightsSourceAudioNativeEncoderPrototypesAndAsrPolicy':True}
atomic_json(C/'seed-manifest.json',seeds)
src=Path(__file__).parent;worker=src/'practical_ps4_full_worker_20261107.py';assert not worker.exists()
s=(src/'practical_ps4_frontend_worker_20261107.py').read_text().replace('practical-conditioned-ps4-r1','practical-conditioned-ps4-full-r1')
needle="        folder=Path(P['derivedAudioRoot']);folder.mkdir(exist_ok=True);outputs=[]"
assert needle in s
addition="""
        from practical_target_voice_router_20261107 import admits_target
        seeds=read(C/'seed-manifest.json');prototypes={}
        def embedding(value):
            peak=float(np.max(np.abs(value)));assert peak>0
            signal=torch.from_numpy(value/peak).unsqueeze(0).to('cuda:0')
            with torch.inference_mode():
                features=model.preEmphasis(signal);features=model.spk_encoder(features)+1e-8
                features=features.log();features=features-features.mean(dim=-1,keepdim=True);features=features.permute(0,2,1)
                value=model.spk_model(features);value=value[-1] if isinstance(value,tuple) else value
                value=torch.nn.functional.normalize(value,dim=-1)
            state['newSpeakerEncoderCalls']=state.get('newSpeakerEncoderCalls',0)+1
            return value.detach().cpu()
        for anchor in read(C/'global-anchors.json'):
            assert sha(anchor['audio'])==anchor['audioSha256']
            prototypes[anchor['speaker']]=embedding(samples(anchor['audio']))
        def identity_for(result):
            value=embedding(samples(result['audio']))
            scores={p:float((value*prototype).sum()) for p,prototype in prototypes.items()}
            return {'sameMeetingCosines':scores,'targetIsTop1':admits_target(result['predictedSpeaker'],scores),'argmaxOnlyNoAbsoluteThreshold':True}
"""
s=s.replace(needle,needle+addition)
needle="                if receipt.exists():"
assert s.count(needle)==1
s=s.replace(needle,"""                if not receipt.exists() and identity in seeds:
                    seed=seeds[identity];assert sha(seed['separationFile'])==seed['separationFileSha256']
                    result=read(seed['separationFile']);assert result['inputMixtureSha256']==case['audioSha256'] and sha(result['audio'])==result['audioSha256']
                    result.update(binding=binding,seedSourceFile=seed['separationFile'],seedSourceSha256=seed['separationFileSha256'],
                        voiceIdentity={'sameMeetingCosines':seed['identity']['similarities'],'targetIsTop1':seed['identity']['targetIsTop1'],'argmaxOnlyNoAbsoluteThreshold':True})
                    atomic_json(receipt,result)
"""+needle)
needle="                    atomic_json(receipt,result);state['newNeuralCalls']+=1;"
assert needle in s;s=s.replace(needle,"                    result['voiceIdentity']=identity_for(result)\n"+needle)
needle="        outputs=[]\n        for case in read(C/'separation-manifest-r2.json'):"
assert needle in s
s=s.replace(needle,"        outputs=[];seeds=read(C/'seed-manifest.json')\n        for case in read(C/'separation-manifest-r2.json'):\n            if not case['voiceIdentity']['targetIsTop1']:continue")
needle="            def infer(lo,hi):"
assert needle in s
s=s.replace(needle,"""            if case['id'] in seeds:
                seed=seeds[case['id']];assert sha(seed['asrFile'])==seed['asrFileSha256']
                cached=read(seed['asrFile']);assert cached['audioSha256']==case['audioSha256']
                result={**case,'text':cached['text'],'acceptedLeaves':cached['acceptedLeaves'],
                    'seedAsrSourceSha256':seed['asrFileSha256'],'newAsrCallsForThisLane':0}
                atomic_json(folder/'completed.json',result);outputs.append(result);state['reusedOutputs']+=1;state['completedInputs']+=1;save();continue
"""+needle)
ast.parse(s);worker.write_text(s,encoding='utf8')
runner=src/'run_practical_ps4_full_20261107.py';assert not runner.exists()
s=(src/'run_practical_ps4_frontend_20261107.py').read_text().replace('practical-conditioned-ps4-r1','practical-conditioned-ps4-full-r1').replace('practical_ps4_frontend_worker_20261107.py','practical_ps4_full_worker_20261107.py')
ast.parse(s);runner.write_text(s,encoding='utf8')
P=read(old/'protocol-r2.json');P.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),
    state='FROZEN_FULL_COMPLEX_ROUTED_CANDIDATE_BEFORE_NEW_INFERENCE',workerSourceSha256=sha(worker),
    audioOnlySha256=sha(C/'audio-only.json'),modelReadySha256=sha(C/'model-ready.json'),audioFrontendManifestSha256=sha(C/'audio-frontend-source.json'),
    derivedAudioRoot='E:/CodexData/Companion/.model-cache/ps4-target-extraction-20261107/full-L-extracted',
    componentParentVerifiedReviewSha256=sha(old/'verified-review.json'),seedManifestSha256=sha(C/'seed-manifest.json'),
    globalAnchorsSha256=sha(C/'global-anchors.json'),fullRoutePlanSha256=sha(C/'full-route-plan.json'),
    fullRoute='Every predicted-overlap root, all predicted-active enrolled people, same native encoder top1 self-identity check against all6 frozen automatic anchors. All rejected raw lanes retained; no hard time-activity masking. If no lane admitted in a root, retain its full original transcript. Other roots retain original whole output. Same thresholds/model/ASR as routed component, no per-root winner selection.',
    fullRetentionRule='Report full-L fixed global DER mapping/unknown-unmatched and standard cpCER, all-person errors, short utterance and overlap-context categories separately. Any total regression rejects this whole candidate, no per-root model cherry-picking. Ordinary source route stays byte-identical. Short-person regression and absent/unregistered speakers remain explicit even if total improves; no formal5% or sale pass from this one development meeting.')
P['helperSources']['practical_target_voice_router_20261107.py']=sha(src/'practical_target_voice_router_20261107.py')
atomic_json(C/'protocol-r2.json',P)
print(json.dumps({'state':P['state'],'fullRoots':len(all_roots),'routedRoots':len(selected),'targetLanes':sum(len(c['anchors']) for c in selected),'sameCandidateSeedLanes':len(seeds),'newAudioSecondsRouted':sum(c['audioSeconds'] for c in selected),'qualityQualified':False}))
