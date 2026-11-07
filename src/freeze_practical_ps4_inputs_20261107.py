"""Audio/activity-only rooted screen; references remain outside model inputs."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import hashlib,json,math,wave
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery'
C=B/'practical-conditioned-ps4-r1';A=B/'practical-qwen-native17-r5';J=B/'native8-f16-full-r1'
E=Path('E:/CodexData/Companion/.model-cache/ps4-target-extraction-20261107/audio');E.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
assert not (C/'audio-only.json').exists();cases=[];diagnostics=[]
for case in read(A/'audio-only.json'):
    name=case['meeting'];file=J/'results'/name/'speaker-journal.json';journal=read(file)
    assert journal['audioSha256']==case['audioSha256'] and sha(case['audio'])==case['audioSha256']
    events=defaultdict(list)
    for row in journal['segments']:
        events[row['start']].append((row['speaker'],1));events[row['end']].append((row['speaker'],-1))
    points=sorted(events);active=defaultdict(int);regions=[]
    for i,start in enumerate(points[:-1]):
        for person,delta in events[start]:
            active[person]+=delta
            if not active[person]:del active[person]
        end=points[i+1];people=tuple(sorted(active))
        if end>start and people:
            if regions and regions[-1]['end']==start and regions[-1]['people']==people:regions[-1]['end']=end
            else:regions.append({'start':start,'end':end,'people':people})
    anchors={}
    for person in sorted({r['speaker'] for r in journal['segments']}):
        solo=[r for r in regions if r['people']==(person,) and r['end']-r['start']>=3.12]
        if not solo:continue
        longest=max(solo,key=lambda r:(r['end']-r['start'],-r['start']))
        length=min(8.,longest['end']-longest['start']-.12)
        center=(longest['start']+longest['end'])/2;lo=round((center-length/2)*16000);hi=lo+round(length*16000)
        anchors[person]={'speaker':person,'startSample':lo,'endSample':hi,'sourceSoloRegion':longest}
    roots=[]
    for index in range(math.ceil(case['audioSeconds']/30)):
        lo=index*30.;hi=min(case['audioSeconds'],lo+30);pairs=triples=solo_seconds=0.;people=set()
        for region in regions:
            duration=max(0.,min(hi,region['end'])-max(lo,region['start']))
            if not duration:continue
            people.update(region['people'])
            if len(region['people'])==1:solo_seconds+=duration
            if len(region['people'])>=2:pairs+=duration
            if len(region['people'])>=3:triples+=duration
        roots.append({'rootIndex':index,'startSample':round(lo*16000),'endSample':round(hi*16000),
            'predictedOverlapSeconds':pairs,'predictedTripleSeconds':triples,'predictedSoloSeconds':solo_seconds,'predictedPeople':sorted(people)})
    if name.startswith('L_'):
        pair=next(r for r in roots if r['predictedOverlapSeconds']>=5. and r['predictedTripleSeconds']<1. and r['endSample']-r['startSample']==480000)
        triple=next(r for r in roots if r['predictedTripleSeconds']>=1. and r['rootIndex']!=pair['rootIndex'] and r['endSample']-r['startSample']==480000)
        selected=[('predicted-two-person-overlap',pair),('predicted-three-plus-overlap',triple)]
    else:
        root=next(r for r in roots if len(r['predictedPeople'])==1 and r['predictedSoloSeconds']>=20. and r['predictedOverlapSeconds']==0 and r['endSample']-r['startSample']==480000)
        selected=[('ordinary-single-person-forced-extraction-control',root)]
    with wave.open(case['audio'],'rb') as stream:
        params=stream.getparams()
        def copy(lo,hi,dest):
            assert not dest.exists();stream.setpos(lo);pcm=stream.readframes(hi-lo);assert len(pcm)==(hi-lo)*2
            with wave.open(str(dest),'wb') as output:output.setparams(params);output.writeframes(pcm)
            return {'audio':str(dest),'audioSha256':sha(dest),'audioSeconds':(hi-lo)/16000}
        for person,anchor in anchors.items():
            dest=E/(name+'-anchor-'+str(person)+'.wav')
            anchor.update(copy(anchor['startSample'],anchor['endSample'],dest))
        for kind,root in selected:
            key=name+'-root-%06d'%root['rootIndex'];dest=E/(key+'-mixture.wav')
            actual=copy(root['startSample'],root['endSample'],dest)
            cases.append({'id':key,'meeting':name,'kind':kind,**root,**actual,
                'originalFullAudio':case['audio'],'originalFullAudioSha256':case['audioSha256'],
                'journal':str(file),'journalSha256':sha(file),
                'anchors':[anchors[p] for p in root['predictedPeople'] if p in anchors],
                'peopleWithoutPredictedSoloAnchor':[p for p in root['predictedPeople'] if p not in anchors],
                'originalRootRawFile':str(A/'full/transcripts'/name/'nodes'/('%06d-root.json'%root['rootIndex']))})
    diagnostics.append({'meeting':name,'estimatedPeople':len({r['speaker'] for r in journal['segments']}),
        'availableAnchors':[{k:a[k] for k in ['speaker','startSample','endSample','audioSeconds']} for a in anchors.values()],
        'selectionUsesOnlyFrozenPredictedActivity':True})
atomic_json(C/'audio-only.json',cases)
atomic_json(C/'input-selection.json',{'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'AUDIO_AND_PREDICTED_ACTIVITY_ONLY_SELECTION_FROZEN_BEFORE_NEW_INFERENCE',
    'rule':'First complete30s native-ASR root with>=5s predicted overlap and<1s predicted triple; first distinct complete root with>=1s predicted triple. First ordinary complete root with one predicted person,>=20s solo activity and no overlap. Enrollment is central<=8s of each persons longest predicted solo region,>=3s after60ms boundary guards. No GT, words, names, source count or new-output selection.',
    'meetings':diagnostics,'allActivePredictedPeopleExtractedWhenAnAnchorExists':True,'noAnchorRemainsExplicit':True,
    'qualityQualified':False,'limits':limits.query()})
print(json.dumps({'state':'INPUTS_FROZEN','cases':[{k:c[k] for k in ['id','kind','predictedOverlapSeconds','predictedTripleSeconds','predictedPeople','peopleWithoutPredictedSoloAnchor']} for c in cases]},ensure_ascii=False))
