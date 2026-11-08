"""Oracle leave-one-out voice prototypes to distinguish reference mismatch, not qualify."""
from pathlib import Path
import os,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_source_data_20261108 import read
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-tse-source-supervision');B=C/'reference-bank-r1';limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2)
import numpy as np
cache=read(B/'embedding-vectors.json')['vectors'];queries=[x for x in cache if x['kind']=='query'];original={x['profileId']:np.asarray(x['vector'],dtype=np.float64) for x in cache if x['kind']=='reference' and x['id'].endswith('--reference-0')};components={x['id']:x for x in read(C/'components.json')};rows=[]
def unit(x):return x/max(float(np.linalg.norm(x)),1e-12)
for query in queries:
    source=components[query['id']];meeting=source['meeting'];ids=sorted(p for p in original if p.startswith(meeting+'--'));scores={};fallback=[]
    for identity in ids:
        eligible=[x for x in queries if x['profileId']==identity and x['id']!=query['id']]
        if eligible:prototype=np.mean([x['vector'] for x in eligible],axis=0)
        else:prototype=original[identity];fallback.append(identity)
        scores[identity]=float(unit(np.asarray(query['vector']))@unit(prototype))
    predicted=max(scores,key=scores.get);rows.append({'componentId':query['id'],'meeting':meeting,'correctProfileId':query['profileId'],'predictedProfileId':predicted,'correct':predicted==query['profileId'],'originalProfileFallbacks':fallback})
summary={m:{'examples':len(g),'correct':sum(x['correct'] for x in g),'accuracy':sum(x['correct'] for x in g)/len(g)} for m in sorted({r['meeting'] for r in rows}) if (g:=[r for r in rows if r['meeting']==m])}
result={'state':'ORACLE_LABELED_OTHER_QUERY_PROTOTYPE_CAUSAL_DIAGNOSTIC_ONLY','perMeeting':summary,'perComponent':rows,'queryExcludedFromOwnPrototype':True,'otherQueriesGroundTruthLabelsUsedForPrototype':True,'notIndependentEnrollmentValidation':True,'notDeployableAutomaticSpeakerInference':True,'noLabelCorrectionsMade':True,'newModelCalls':0,'newWeightUpdates':0,'qualityQualified':False};assert not (B/'oracle-component-prototype-diagnostic.json').exists();atomic_json(B/'oracle-component-prototype-diagnostic.json',result);print(json.dumps(summary),flush=True)
