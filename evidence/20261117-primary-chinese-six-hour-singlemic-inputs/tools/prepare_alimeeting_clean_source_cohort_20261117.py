"""Freeze original clean nonoverlap labels and one training source per recording venue."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict,Counter
import bisect,hashlib,json,shutil,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
O=E/'alimeeting-official-intake-r2';out=O/'clean-source-cohort-r1';out.mkdir()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
headers=read(O/'primary-wave-headers-r1/completed.json');split=read(O/'primary-train-eval-person-split.json')
annotation=read(O/'annotation-download-r1/completed.json');ann={Path(r['local']).stem:r for r in annotation['entries']}
pair=read(O/'original-pairing-r2/completed.json');paired={r['meeting']:r for r in pair['completed']}
assert headers['allOriginalHeadersMatchConvertedFrameCounts'] and len(headers['entries'])==209
assert not split['intersection'] and len(split['trainingGlobalSpeakerIds'])==452 and len(split['evaluationGlobalSpeakerIds'])==25
sources=[];rows=[];excluded=[]
for case in sorted(headers['entries'],key=lambda r:r['meeting']):
    meeting=case['meeting'];frames=case['header']['frames'];proof=ann[meeting]
    assert sha(proof['local'])==proof['sha256'] and paired[meeting]['officialNearFileSpeakerIdsMatch']
    if not case['singleMicCandidateSourceStructurallyAdmissible']:
        excluded.append({'meeting':meeting,'reason':'Original nonempty annotation extends beyond actual primaryWAV dataframes',
            'actualSourceFrames':frames,'outsideSpeechIntervals':case['speechIntervalsPastActualAudioEnd']});continue
    raw=read_reference_intervals(proof['local']);turns=[];events=defaultdict(list)
    for index,r in enumerate(raw):
        if not r['text'] or r['start']>=r['end']:continue
        speaker=r['speaker'].split('SPK')[-1];assert speaker in split['trainingGlobalSpeakerIds']
        a=round(r['start']*16000);b=round(r['end']*16000);assert 0<=a<b<=frames
        turn={'id':meeting+'-original-'+str(index).zfill(5),'meeting':meeting,'startFrame':a,'endFrame':b,
            'frames':b-a,'text':r['text'],'sourceSpeakerId':speaker,'sourceOriginalTier':r['speaker'],
            'sourceTextgridSha256':proof['sha256'],'sourceTextgrid':proof['local'],'role':'train-only','language':'Chinese'}
        turns.append(turn);events[a].append((speaker,1));events[b].append((speaker,-1))
    active=Counter();last=None;overlap=[]
    for at,changes in sorted(events.items()):
        if last is not None and last<at and len(active)>1:
            if overlap and overlap[-1][1]==last:overlap[-1]=(overlap[-1][0],at)
            else:overlap.append((last,at))
        for speaker,delta in changes:
            active[speaker]+=delta
            if active[speaker]==0:del active[speaker]
        assert all(n>0 for n in active.values());last=at
    assert not active;ends=[b for a,b in overlap];selected=[]
    for r in turns:
        if not 32000<=r['frames']<=480000:continue
        i=bisect.bisect_right(ends,r['startFrame'])
        if i<len(overlap) and overlap[i][0]<r['endFrame']:continue
        selected.append(r)
    # Complete source utterances only. No merge before overlap detection, no
    # text normalization, time clipping, speed perturbation, or padding.
    seconds=sum(r['frames'] for r in selected)/16000
    sources.append({**case,'venue':meeting.split('_')[0],'candidateUtterances':len(selected),
        'candidateSeconds':seconds,'candidateSpeakers':sorted({r['sourceSpeakerId'] for r in selected})})
    rows.extend(selected)
manifest=out/'original-clean-nonoverlap-candidates.jsonl'
with manifest.open('x',encoding='utf-8') as f:
    for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
venues=defaultdict(list)
for s in sources:
    if s['candidateUtterances']:venues[s['venue']].append(s)
assert len(venues)==12 and len(sources)==200 and len(excluded)==9
chosen=[]
for venue,cases in sorted(venues.items()):
    if venue=='R0003':selected=next(c for c in cases if c['meeting']=='R0003_M0046')
    else:selected=min(cases,key=lambda c:hashlib.sha256(('Companion-AliTrain-20261117/'+c['meeting']).encode()).hexdigest())
    chosen.append(selected)
first=read(O/'first-mic-source-r1/post-source-check-r2/completed.json')
assert first['state']=='COMPLETE_FIRST_MIC_RAW_SOURCE_AND_MONO_ALL_FRAMES_VERIFIED_COMMITTED'
assert sha(first['output'])==first['outputSha256']
for case in chosen:
    case['output']=str(out/'sources'/(case['meeting']+'.channel0.wav'))
    if case['meeting']=='R0003_M0046':
        assert case['etag'].lower()==first['sourceFullMd5'] and case['header']['frames']==first['comparedFrames']
        case.update(reusedVerifiedSource=str(O/'first-mic-source-r1/post-source-check-r2/completed.json'),
            output=first['output'],outputSha256=first['outputSha256'])
current=sum(p.stat().st_size for p in E.rglob('*') if p.is_file())
remaining_raw=sum(c['objectBytes'] for c in chosen if not c.get('reusedVerifiedSource'))
mono_bytes=sum(c['header']['frames']*2+44 for c in chosen if not c.get('reusedVerifiedSource'))
chosen_ids={c['meeting'] for c in chosen};candidate_bytes=sum(r['frames']*2+44 for r in rows if r['meeting'] in chosen_ids)
envelope=current+remaining_raw+mono_bytes+candidate_bytes
assert envelope<12*1024**3,'Conservative source/mono/clip envelope exceeds original12GiB budget'
assert shutil.disk_usage(out).free>50*1024**3+mono_bytes+candidate_bytes,'Original disk reserve'
protocol={'at':datetime.now().astimezone().isoformat(),'state':'FROZEN12_VENUE_PRIMARY_CHINESE_TRAIN_SOURCE_ACQUISITION_NO_TRAINING',
    'selectedSources':chosen,'candidateManifest':str(manifest),'candidateManifestSha256':sha(manifest),
    'allCleanSources':sources,'excludedWholeSources':excluded,'cleanSourceMeetings':200,'venues':12,
    'allOriginalCleanNonoverlapUtterances':len(rows),'allOriginalCleanCandidateSeconds':sum(r['frames'] for r in rows)/16000,
    'selectedNonoverlapUtterances':sum(c['candidateUtterances'] for c in chosen),
    'selectedNonoverlapSeconds':sum(c['candidateSeconds'] for c in chosen),
    'selection':'One source per all12published training venue IDs, fixedSHA256 order. Reuse the independently verified first source inR0003 to avoid another acquisition. Only training metadata/source-integrity criteria; no model quality outputs.',
    'segmentation':'Whole original utterance2-30s with no other-speaker overlap, no padding/merging/truncation/text edits.',
    'sourceChannel':0,'sourceChannels':8,'sampleRate':16000,'sourceBits':16,
    'cpuPercent':5,'privateMemoryBytes':256*1024**2,'minimumAvailableBytes':3414499000,
    'minimumDiskFreeBytes':50*1024**3,'maximumOwnedNewDataBytes':12*1024**3,
    'budget':{'currentOwnedBytes':current,'remainingWholeSourceIngressBytes':remaining_raw,
        'newMonoBytes':mono_bytes,'prospectiveClipsBytes':candidate_bytes,'conservativeCombinedEnvelopeBytes':envelope},
    'publishedTrainEvalParticipantIntersection':[],'participantProof':str(O/'primary-train-eval-person-split.json'),
    'originalAishellCrossCorpusPersonIsolationProven':False,'originalQualityGatesChanged':False,
    'newNeuralCalls':0,'parameterUpdates':0,'trainingAdmitted':False,'qualityQualified':False,
    'dependencies':[{'file':str(p),'sha256':sha(p)} for p in [O/'primary-wave-headers-r1/completed.json',
        O/'primary-train-eval-person-split.json',O/'annotation-download-r1/completed.json',
        O/'original-pairing-r2/completed.json',Path(__file__),Path(__file__).with_name('alimeeting_public_oss_20261117.py')]]}
atomic_json(out/'protocol.json',protocol)
print(json.dumps({k:protocol[k] for k in ['state','venues','cleanSourceMeetings','allOriginalCleanNonoverlapUtterances',
    'allOriginalCleanCandidateSeconds','selectedNonoverlapUtterances','selectedNonoverlapSeconds','budget']},ensure_ascii=False))
