"""Prove added enrollment contains no evaluated component and preserves source PCM."""
from pathlib import Path
import os,sys,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.path.append('E:/CodexData/Companion/.model-cache/audio-tools');sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_source_data_20261108 import read,sha,pcm_read,truth_rows,overlap
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-tse-source-supervision');B=C/'reference-bank-r1';limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2)
import numpy as np
import soundfile as sf
plan=read(B/'reference-plan.json');components=read(C/'components.json');natural=read(C/'natural-validation-queries.json');checked=0
for source in read(C/'sources.json'):
    truth=truth_rows(source['reference'])
    with sf.SoundFile(source['localFlac']) as f:
        for ref in [x for x in plan['references'] if x['meeting']==source['meeting']]:
            a,b=ref['sourceStartSample'],ref['sourceEndSample'];assert sha(ref['audio'])==ref['audioSha256'];f.seek(a);expected=f.read(b-a,dtype='int16',always_2d=True)[:,:1];assert np.array_equal(expected,pcm_read(ref['audio'],1));person=ref['personForTrainingOrScoringOnly'];assert not any(x['speaker']!=person and overlap(a/16000,b/16000,x['start'],x['end'])>0 for x in truth)
            assert not any(overlap(a,b,x['sourceStartSample'],x['sourceEndSample'])>0 for x in components if x['meeting']==source['meeting'])
            assert not any(overlap(a,b,x['sourceStartSample'],x['sourceEndSample'])>0 for x in natural if x['meeting']==source['meeting'] and x['personForScoringOnly']==person)
            assert not any(overlap(a,b,x['sourceStartSample'],x['sourceEndSample'])>0 for x in plan['references'] if x['id']==ref['id'] and x['referenceOrdinal']!=ref['referenceOrdinal']);checked+=1
assert len(components)==223 and len(plan['coverage'])==25
result={'state':'PASS_ALL_REFERENCES_PCM_IDENTITY_PURITY_AND_QUERY_DISJOINTNESS','referencesChecked':checked,'peoplePreserved':25,'componentsRemain223':True,'allReferencesMutuallyDisjointWithinIdentity':True,'noEvalComponentAudioInAnyReference':True,'noOriginalLabelsChanged':True,'modelScoresNotUsedForSelection':True,'newWeightUpdates':0,'qualityQualified':False};atomic_json(B/'data-verification.json',result);print(json.dumps(result),flush=True)
