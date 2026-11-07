"""Freeze cross-meeting short controls from existing predicted activity, no GT."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import json,hashlib,math,wave
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery';C=B/'practical-target-activity-r1';E=Path('E:/CodexData/Companion/.model-cache/target-activity-controls-20261107');E.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
assert not (C/'audio-only.json').exists();limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
source=read(B/'native8-f16-full-r1/audio-only.json')+read(B/'native8-ami-r1/audio-only.json');plan=[];prototypes=[];summary=[];scoring=[]
for item in source:
    name=item['meeting'];origin=B/('native8-ami-r1' if name=='EN2002a' else 'native8-f16-full-r1');journalfile=origin/'results'/name/'speaker-journal.json';journal=read(journalfile)
    assert sha(item['audio'])==item['audioSha256']==journal['audioSha256']
    events=defaultdict(list)
    for row in journal['segments']:events[row['start']].append((row['speaker'],1));events[row['end']].append((row['speaker'],-1))
    points=sorted(events);active=defaultdict(int);regions=[]
    for i,lo in enumerate(points[:-1]):
        for person,delta in events[lo]:
            active[person]+=delta
            if not active[person]:del active[person]
        hi=points[i+1];people=tuple(sorted(active))
        if hi>lo and people:
            if regions and regions[-1]['end']==lo and regions[-1]['people']==people:regions[-1]['end']=hi
            else:regions.append({'start':lo,'end':hi,'people':people})
    allpeople=sorted({row['speaker'] for row in journal['segments']});roots=[]
    for index in range(math.floor(item['audioSeconds']/30)):
        lo=index*30.;hi=lo+30.;parts=[(r,max(0.,min(hi,r['end'])-max(lo,r['start']))) for r in regions];parts=[(r,d) for r,d in parts if d>0]
        total={p:sum(d for r,d in parts if p in r['people']) for p in allpeople}
        roots.append({'rootIndex':index,'startSample':round(lo*16000),'endSample':round(hi*16000),'predictedPeople':[p for p,d in total.items() if d>0],
            'predictedPersonSeconds':total,'predictedSoloSeconds':sum(d for r,d in parts if len(r['people'])==1),
            'predictedOverlapSeconds':sum(d for r,d in parts if len(r['people'])>=2),'predictedTripleSeconds':sum(d for r,d in parts if len(r['people'])>=3),
            'predictedShortTurns':sum(.25<=r['end']-r['start']<2 and r['end']>lo and r['start']<hi for r in journal['segments'])})
    chosen=[];used=set();missing=[]
    rules=[('ordinary',lambda r:len(r['predictedPeople'])==1 and r['predictedSoloSeconds']>=20 and r['predictedOverlapSeconds']==0),
        ('two-speaker-overlap',lambda r:r['predictedOverlapSeconds']>=2 and r['predictedTripleSeconds']<.1),
        ('three-plus-overlap',lambda r:r['predictedTripleSeconds']>=.5),
        ('short-turn',lambda r:len(r['predictedPeople'])>=2 and r['predictedShortTurns']>0)]
    for kind,rule in rules:
        root=next((r for r in roots if r['rootIndex'] not in used and rule(r)),None)
        if root is None:missing.append(kind);continue
        chosen.append((kind,root));used.add(root['rootIndex'])
    covered={p for _,root in chosen for p,d in root['predictedPersonSeconds'].items() if d>=3}
    for person in allpeople:
        if person in covered:continue
        root=next((r for r in roots if r['rootIndex'] not in used and r['predictedPersonSeconds'][person]>=3),None)
        if root is None:missing.append('predicted-positive-coverage-'+str(person));continue
        chosen.append(('predicted-person-coverage',root));used.add(root['rootIndex']);covered.update(p for p,d in root['predictedPersonSeconds'].items() if d>=3)
    excluded=[(r['startSample']/16000,r['endSample']/16000) for _,r in chosen];anchors=[]
    with wave.open(item['audio'],'rb') as stream:
        assert stream.getframerate()==16000 and stream.getnchannels()==1 and stream.getsampwidth()==2;params=stream.getparams()
        def copy(lo,hi,dest):
            assert not dest.exists();stream.setpos(lo);pcm=stream.readframes(hi-lo);assert len(pcm)==2*(hi-lo)
            with wave.open(str(dest),'wb') as out:out.setparams(params);out.writeframes(pcm)
            return {'audio':str(dest),'audioSha256':sha(dest),'audioSeconds':(hi-lo)/16000}
        for person in allpeople:
            candidates=[]
            for region in regions:
                if region['people']!=(person,):continue
                spans=[(region['start'],region['end'])]
                for left,right in excluded:
                    spans=[part for lo,hi in spans for part in [(lo,min(hi,left)),(max(lo,right),hi)] if part[1]>part[0]]
                candidates.extend((lo,hi) for lo,hi in spans if hi-lo>=3.12)
            assert candidates,(name,person,'No automatic disjoint enrollment; do not use GT to recover')
            lo,hi=max(candidates,key=lambda v:(v[1]-v[0],-v[0]));length=min(10.,hi-lo-.12);center=(lo+hi)/2;a=round((center-length/2)*16000);z=a+round(length*16000)
            anchors.append({'meeting':name,'speaker':person,'startSample':a,'endSample':z,'sourceSoloRegion':[lo,hi],**copy(a,z,E/(name+'-anchor-'+str(person)+'.wav'))})
        prototypes.extend(anchors)
        for kind,root in chosen:
            key=name+'-root-%06d'%root['rootIndex'];plan.append({'id':key,'meeting':name,'kind':kind,**root,**copy(root['startSample'],root['endSample'],E/(key+'.wav')),
                'allAnonymousTargets':allpeople,'originalFullAudio':item['audio'],'originalFullAudioSha256':item['audioSha256']})
    score=next(s for s in read(B/('native8-ami-r1/scoring-only.json' if name=='EN2002a' else 'practical-qwen-native17-r5/full/scoring-only.json')) if s['meeting']==name)
    scoring.append({**score,'journal':str(journalfile),'journalSha256':sha(journalfile),'fixedMappingReview':str(origin/'results'/name/'review.json')})
    summary.append({'meeting':name,'predictedPeople':len(allpeople),'cases':[{'kind':k,'rootIndex':v['rootIndex'],'predictedPeople':v['predictedPeople']} for k,v in chosen],
        'missingPredictedCategories':missing,'automaticAnchorsUnder10Seconds':[{'speaker':a['speaker'],'seconds':a['audioSeconds']} for a in anchors if a['audioSeconds']<10.],'anchorsDisjointFromEveryTestClip':True})
atomic_json(C/'audio-only.json',plan);atomic_json(C/'automatic-enrollments.json',prototypes);atomic_json(C/'scoring-only.json',scoring)
atomic_json(C/'control-selection.json',{'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'CROSS_MEETING_RAW_MIXTURE_CONTROLS_FROZEN_BEFORE_NEW_NEURAL_INFERENCE',
    'selectionRule':'From prior frozen predicted activity, first distinct full30s roots for>=20s one-person/no-overlap,>=2s overlap/<0.1s triple,>=0.5s triple,>=1 predicted0.25-2s turn with>=2 people. Add first distinct roots with>=3s predicted speech to cover missing predicted profiles. All same-meeting automatic profiles are queried on every clip, including absent ones. Enrollment is central<=10s of longest predicted solo outside every selected clip,>=3s after60ms guards; no GT enrollment or profile reselection.',
    'meetings':summary,'cases':len(plan),'totalOriginalAudioSeconds':sum(p['audioSeconds'] for p in plan),'targetQueries':sum(len(p['allAnonymousTargets']) for p in plan),'referencesOpenedDuringSelection':False,
    'scope':'Exposed real development meetings,2corpora. Short controls are not complete-meeting qualification or an unseen test. Reference names/count/activity do not enter worker input. Actual category coverage must be audited separately; a predicted category is not declared ground truth.',
    'baseline':'Same frozen native FP16 anonymous activity, same fixed whole-meeting reference mapping, compared only posthoc on identical clips.',
    'candidatePolicy':'One learned target-presence candidate on original mixtures only. No ASR/separation rerun and no word filtering. A failed short gate prevents full-meeting candidate expansion. No threshold/window sweep.',
    'finalHoldoutOpened':False,'qualityQualified':False,'limits':limits.query()})
print(json.dumps({'state':'CONTROLS_FROZEN','cases':len(plan),'targetQueries':sum(len(p['allAnonymousTargets']) for p in plan),'meetings':summary},ensure_ascii=False),flush=True)
