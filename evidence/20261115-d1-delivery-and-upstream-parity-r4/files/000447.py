"""Exact additive two-channel components and untouched natural validation queries."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib,json,math,os,random,sys,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages');sys.path.append('E:/CodexData/Companion/.model-cache/audio-tools')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_source_data_20261108 import read,sha,pcm_write,pcm_read,overlap,truth_rows,profile_interval
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-tse-source-supervision';E=Path('E:/CodexData/Companion/.model-cache/tse-source-supervision-20261108');P=read(C/'data-protocol-r1.json');limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2);tick=time.perf_counter();assert not (C/'audio-ready.json').exists();assert read(C/'source-fetch.json')['state']=='COMPLETE_ALL_FOUR_LOSSLESS_SOURCE_HASHES_VERIFIED';assert sha(C/'sources.json')==P['sourceListSha256']
import numpy as np
import soundfile as sf
state={'state':'PREPARING_EXACT_COMPONENT_AND_NEW_NATURAL_INPUTS','startedAt':datetime.now().astimezone().isoformat(),'completedSources':0,'newModelCalls':0,'newTrainingUpdates':0};atomic_json(C/'audio-preparation.json',state)
profiles=[];components=[];natural=[];warnings=[]
for source in read(C/'sources.json'):
    assert sha(source['localFlac'])==source['expectedWholeFileLfsSha256'] and sha(source['reference'])==source['referenceSha256'];truth=truth_rows(source['reference']);people=sorted({x['speaker'] for x in truth});meeting=source['meeting'];role=source['role']
    with sf.SoundFile(source['localFlac']) as audio:
        assert audio.channels==8 and audio.samplerate==16000 and audio.subtype=='PCM_16';duration=len(audio)/16000
        def samples(lo,hi):audio.seek(lo);v=audio.read(hi-lo,dtype='int16',always_2d=True)[:,:2];assert len(v)==hi-lo;return v
        for person in people:
            lo,hi=profile_interval(truth,person,duration);identity=meeting+'--'+person;packet=pcm_write(E/'profiles'/(identity+'.wav'),samples(lo,hi)[:,:1]);profile={**packet,'id':identity,'meeting':meeting,'personForTrainingOrScoringOnly':person,'role':role,'sourceStartSample':lo,'sourceEndSample':hi,'sourceFlacSha256':source['expectedWholeFileLfsSha256'],'otherAnnotatedSpeechOverlaps':False};profiles.append(profile)
            choices=[]
            for interval in truth:
                a,b=interval['start'],interval['end'];start,end=math.floor(a*16000),math.ceil(b*16000)
                if interval['speaker']!=person or not P['componentMinimumSeconds']<=b-a<=P['componentMaximumSeconds']:continue
                if overlap(start,end,lo,hi)>0 or any(y['speaker']!=person and overlap(start/16000,end/16000,y['start'],y['end'])>0 for y in truth):continue
                choices.append((start,end,interval))
            random.Random(P['seed']+int(hashlib.sha256(identity.encode()).hexdigest()[:8],16)).shuffle(choices);choices=choices[:P['maximumComponentsPerTrainingPerson'] if role=='train' else 16];assert choices,'No independent component for '+identity
            for index,(a,b,interval) in enumerate(choices):
                name=identity+'--component-%03d'%index;packet=pcm_write(E/'components'/(name+'.wav'),samples(a,b));components.append({**packet,'id':name,'role':role,'meeting':meeting,'personForTrainingOrScoringOnly':person,'profileId':identity,'sourceStartSample':a,'sourceEndSample':b,'sourceFlacSha256':source['expectedWholeFileLfsSha256'],'referenceTextForTrainingOrScoringOnly':interval['text'],'sourceUtterance':interval,'profileAndComponentDisjoint':True,'componentMeaning':'Observed raw far-field utterance with no other annotated lexical speaker; room/background remain. Not a studio-clean reference.'})
            if role!='validation':continue
            candidates={k:[] for k in ['present_solo','present_overlap','absent_other_speech']};seen=set()
            for seed in truth:
                a=max(0.,seed['start']-.25);b=min(duration,seed['end']+.25)
                for _ in range(20):
                    touched=[x for x in truth if x['speaker']==person and overlap(a,b,x['start'],x['end'])>0]
                    aa=min([a]+[x['start'] for x in touched]);bb=max([b]+[x['end'] for x in touched])
                    if (aa,bb)==(a,b):break
                    a,b=aa,bb
                start,end=math.floor(a*16000),math.ceil(b*16000)
                if end-start>int(P['naturalQueryMaximumSeconds']*16000) or overlap(start,end,lo,hi)>0 or (start,end) in seen:continue
                targets=[x for x in truth if x['speaker']==person and overlap(start/16000,end/16000,x['start'],x['end'])>0];others=[x for x in truth if x['speaker']!=person and overlap(start/16000,end/16000,x['start'],x['end'])>0]
                if any(x['start']<start/16000 or x['end']>end/16000 for x in targets):continue
                if not targets:
                    if not others:continue
                    category='absent_other_speech'
                else:category='present_overlap' if any(overlap(x['start'],x['end'],y['start'],y['end'])>0 for x in targets for y in others) else 'present_solo'
                seen.add((start,end));candidates[category].append((start,end,targets))
            for category,values in candidates.items():
                random.Random(P['seed']+int(hashlib.sha256((identity+category).encode()).hexdigest()[:8],16)).shuffle(values)
                if len(values)<P['maximumNaturalQueriesPerPersonPerCategory']:warnings.append({'meeting':meeting,'person':person,'category':category,'available':len(values)})
                for index,(a,b,targets) in enumerate(values[:P['maximumNaturalQueriesPerPersonPerCategory']]):
                    name=identity+'--'+category+'--'+str(index);packet=pcm_write(E/'natural'/(name+'.wav'),samples(a,b));natural.append({**packet,'id':name,'kind':'natural_real_meeting','role':'natural_validation','meeting':meeting,'personForScoringOnly':person,'profileId':identity,'category':category,'sourceStartSample':a,'sourceEndSample':b,'sourceFlacSha256':source['expectedWholeFileLfsSha256'],'targetUtterancesForScoringOnly':targets,'referenceForScoringOnly':''.join(x['text'] for x in sorted(targets,key=lambda x:(x['start'],x['end']))),'profileAndQueryDisjoint':True,'naturalOverlapCleanTargetAvailable':False})
    state['completedSources']+=1;atomic_json(C/'audio-preparation.json',state,progress=True);print(json.dumps({'meeting':meeting,'people':len(people),'components':sum(x['meeting']==meeting for x in components),'naturalQueries':sum(x['meeting']==meeting for x in natural)}),flush=True)
profile_byid={x['id']:x for x in profiles};units=[];mixed=[]
for role,pairs,negatives,solos in [('train',P['trainingMixedPairs'],P['absentTargetTrainingQueries'],P['singleTargetTrainingQueries']),('validation',P['syntheticValidationMixedPairs'],8,8)]:
    pool=[x for x in components if x['role']==role];meetings=sorted({x['meeting'] for x in pool});people_bymeeting={m:sorted({x['personForTrainingOrScoringOnly'] for x in pool if x['meeting']==m}) for m in meetings};pools={(m,p):[x for x in pool if x['meeting']==m and x['personForTrainingOrScoringOnly']==p] for m in meetings for p in people_bymeeting[m]};rng=random.Random(P['seed']+(0 if role=='train' else 1))
    for index in range(pairs):
        meeting=meetings[index%len(meetings)];people=people_bymeeting[meeting];a_person=people[(index//len(meetings))%len(people)];b_person=people[(people.index(a_person)+1+(index//(len(people)*len(meetings))))%len(people)]
        if b_person==a_person:b_person=people[(people.index(a_person)+1)%len(people)]
        a=rng.choice(pools[meeting,a_person]);b=rng.choice(pools[meeting,b_person]);left=pcm_read(a['audio'],2).astype(np.float64);right=pcm_read(b['audio'],2).astype(np.float64);assert np.mean(left[:,0]**2)>0 and np.mean(right[:,0]**2)>0
        snr=P['snrScheduleDb'][index%len(P['snrScheduleDb'])];gain=float(np.sqrt(np.mean(left[:,0]**2)/np.mean(right[:,0]**2))*10**(-snr/20));right*=gain;offset=int(min(len(left),len(right))*P['interfererOffsetScheduleFractions'][(index//len(P['snrScheduleDb']))%len(P['interfererOffsetScheduleFractions'])]);length=max(len(left),len(right)+offset);aa=np.zeros((length,2));bb=np.zeros((length,2));aa[:len(left)]=left;bb[offset:offset+len(right)]=right;common=.90*32767/max(float(np.max(np.abs(aa))),float(np.max(np.abs(bb))),float(np.max(np.abs(aa+bb))));aa=np.rint(aa*common).astype('<i2');bb=np.rint(bb*common).astype('<i2');integer_mix=aa.astype(np.int32)+bb.astype(np.int32);assert np.max(np.abs(integer_mix))<=32767
        name=role+'--mixed-%03d'%index;folder=E/'mixed'/name;mix=pcm_write(folder/'mixture.wav',integer_mix.astype('<i2'));ta=pcm_write(folder/'component-a.wav',aa);tb=pcm_write(folder/'component-b.wav',bb);item={'id':name,'kind':'known_additive_mixture','role':role,'meeting':meeting,'mixture':mix,'targets':[{'component':ta,'profileId':a['profileId'],'originalComponentId':a['id'],'referenceForScoringOnly':a['referenceTextForTrainingOrScoringOnly']},{'component':tb,'profileId':b['profileId'],'originalComponentId':b['id'],'referenceForScoringOnly':b['referenceTextForTrainingOrScoringOnly']}],'sourceGainB':gain,'commonPcmGain':common,'interfererOffsetSamples':offset,'snrBeforeQuantizationDb':snr,'physicalChannels':[0,1],'componentSumBitIdenticalToMixture':True,'notNaturalOverlap':True};units.append(item);mixed.append(item)
        if index<negatives:
            remaining_people=[p for p in people if p not in [a_person,b_person]];person=remaining_people[(index//len(meetings))%len(remaining_people)];units.append({'id':role+'--absent-%03d'%index,'kind':'absent_known_identity','role':role,'meeting':meeting,'mixture':mix,'profileId':meeting+'--'+person,'targetIsExactZero':True,'mixedSourceId':name,'notNaturalOverlap':True})
    for index in range(solos):
        keys=sorted(pools);component=rng.choice(pools[keys[index%len(keys)]]);units.append({'id':role+'--solo-%03d'%index,'kind':'single_target_preservation','role':role,'meeting':component['meeting'],'mixture':{k:component[k] for k in ['audio','audioSha256','audioSeconds','channels']},'targets':[{'component':{k:component[k] for k in ['audio','audioSha256','audioSeconds','channels']},'profileId':component['profileId'],'originalComponentId':component['id'],'referenceForScoringOnly':component['referenceTextForTrainingOrScoringOnly']}],'notNaturalOverlap':True})
train=[x for x in units if x['role']=='train'];validation=[x for x in units if x['role']=='validation'];random.Random(P['seed']).shuffle(train)
for name,values in [('profiles.json',profiles),('components.json',components),('training-units.json',train),('synthetic-validation-units.json',validation),('natural-validation-queries.json',natural)]:atomic_json(C/name,values)
summary={'state':'COMPLETE_KNOWN_COMPONENT_AND_NEW_NATURAL_AUDIO_PREPARATION','trainingUnits':len(train),'trainingTargetQueries':sum(2 if x['kind']=='known_additive_mixture' else 1 for x in train),'syntheticValidationUnits':len(validation),'naturalValidationQueries':len(natural),'counts':dict(Counter(x['role']+'/'+x['kind'] for x in units)),'naturalCounts':dict(Counter(x['meeting']+'/'+x['category'] for x in natural)),'componentPool':len(components),'profiles':len(profiles),'sourceHashChecks':True,'componentSumExactByConstruction':True,'coverageWarnings':warnings,'physicalSpeakerSplitIndependenceUnknown':True,'oldExposed48NotUsed':True,'finalHoldoutOpened':False,'newModelCalls':0,'qualityQualified':False};atomic_json(C/'audio-ready.json',summary);state.update(**summary,finishedAt=datetime.now().astimezone().isoformat(),wholeSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(C/'audio-preparation.json',state);print(json.dumps(summary,ensure_ascii=False),flush=True)
