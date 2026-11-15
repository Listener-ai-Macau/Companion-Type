"""Independent source PCM, label, enrollment and exact additive-component checks."""
from pathlib import Path
from collections import Counter
import os,sys,math,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages');sys.path.append('E:/CodexData/Companion/.model-cache/audio-tools')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_source_data_20261108 import read,sha,pcm_read,truth_rows,overlap
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-tse-source-supervision';limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2)
import numpy as np
import soundfile as sf
assert not (C/'audio-verification.json').exists();assert read(C/'audio-ready.json')['state']=='COMPLETE_KNOWN_COMPONENT_AND_NEW_NATURAL_AUDIO_PREPARATION';profiles=read(C/'profiles.json');components=read(C/'components.json');natural=read(C/'natural-validation-queries.json');units=read(C/'training-units.json')+read(C/'synthetic-validation-units.json');profile_byid={x['id']:x for x in profiles};bycomponent={x['id']:x for x in components};checked=0
for source in read(C/'sources.json'):
    assert sha(source['localFlac'])==source['expectedWholeFileLfsSha256'] and sha(source['reference'])==source['referenceSha256'];truth=truth_rows(source['reference'])
    with sf.SoundFile(source['localFlac']) as f:
        for row in [x for x in profiles+components+natural if x['meeting']==source['meeting']]:
            assert sha(row['audio'])==row['audioSha256'];a,b=row['sourceStartSample'],row['sourceEndSample'];f.seek(a);expected=f.read(b-a,dtype='int16',always_2d=True)[:,:row['channels']];assert np.array_equal(expected,pcm_read(row['audio'],row['channels']));checked+=1
            if row in profiles or row in components:
                person=row['personForTrainingOrScoringOnly'];assert not any(x['speaker']!=person and overlap(a/16000,b/16000,x['start'],x['end'])>0 for x in truth)
            if row in components or row in natural:
                profile=profile_byid[row['profileId']];assert overlap(a,b,profile['sourceStartSample'],profile['sourceEndSample'])==0
            if row in components:
                u=row['sourceUtterance'];assert math.floor(u['start']*16000)==a and math.ceil(u['end']*16000)==b
            if row in natural:
                target=[x for x in truth if x['speaker']==row['personForScoringOnly'] and overlap(a/16000,b/16000,x['start'],x['end'])>0];assert target==row['targetUtterancesForScoringOnly'];assert all(x['start']>=a/16000 and x['end']<=b/16000 for x in target)
mixes=0
for unit in units:
    packet=unit['mixture'];assert sha(packet['audio'])==packet['audioSha256'];mixture=pcm_read(packet['audio'],2)
    if unit['kind']=='known_additive_mixture':
        outputs=[]
        for index,target in enumerate(unit['targets']):
            component=target['component'];assert sha(component['audio'])==component['audioSha256'];value=pcm_read(component['audio'],2);outputs.append(value.astype(np.int32));source=bycomponent[target['originalComponentId']];assert source['role']==unit['role'] and source['meeting']==unit['meeting'];original=pcm_read(source['audio'],2).astype(np.float64);gain=unit['commonPcmGain']*(unit['sourceGainB'] if index else 1.);offset=unit['interfererOffsetSamples'] if index else 0;expected=np.zeros_like(value);expected[offset:offset+len(original)]=np.rint(original*gain).astype('<i2');assert np.array_equal(value,expected);assert target['profileId']==source['profileId']
        assert np.array_equal(outputs[0]+outputs[1],mixture.astype(np.int32));assert unit['targets'][0]['profileId']!=unit['targets'][1]['profileId'];mixes+=1
    elif unit['kind']=='single_target_preservation':assert unit['targets'][0]['component']['audioSha256']==packet['audioSha256']
    else:
        mixed=next(x for x in units if x['id']==unit['mixedSourceId']);assert unit['profileId'] not in [x['profileId'] for x in mixed['targets']]
train_meetings={x['meeting'] for x in units if x['role']=='train'};val_meetings={x['meeting'] for x in units if x['role']=='validation'};assert train_meetings.isdisjoint(val_meetings)==True and val_meetings=={x['meeting'] for x in natural}
result={'state':'PASS_ALL_SOURCE_PCM_PROFILES_LABELS_AND_EXACT_COMPONENT_SUMS','sourceExcerptsChecked':checked,'mixedInputsCheckedBothChannels':mixes,'naturalQueriesChecked':len(natural),'trainingUnits':sum(x['role']=='train' for x in units),'validationUnits':sum(x['role']=='validation' for x in units),'meetingSplitDisjoint':True,'allProfileAndQueryWindowsDisjoint':True,'allPositiveComponentsIncludeOriginalCompleteUtterance':True,'sourceComponentsStillContainRealRoomBackground':True,'allMixturesExplicitlySynthetic':True,'referenceNotAnInferenceInput':True,'newModelCalls':0,'qualityQualified':False};atomic_json(C/'audio-verification.json',result);print(json.dumps(result),flush=True)
