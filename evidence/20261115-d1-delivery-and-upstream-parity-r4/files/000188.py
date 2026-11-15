"""Check whether two requested identities actually produce different extracted voices."""
from pathlib import Path
import os,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_source_data_20261108 import read,pcm_read
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-tse-source-supervision');limits=WorkerLimits(cpu_percent=10,memory_bytes=512*1024**2)
import numpy as np
rows=[];summary={}
for arm in ['baseline','adapted']:
    data=read(C/(arm+'-validation.json'))['synthetic'];identities=sorted({x['unitId'] for x in data if x['kind']=='known_additive_mixture'});current=[]
    for identity in identities:
        pair=sorted([x for x in data if x['unitId']==identity],key=lambda x:x['id']);assert len(pair)==2 and pair[0]['profileId']!=pair[1]['profileId'];a,b=[pcm_read(x['audio'],1)[:,0].astype(np.float64)*x['pcmExportDivisor'] for x in pair];a-=a.mean();b-=b.mean();aa=float(a@a);bb=float(b@b);corr=float(a@b)/max((aa*bb)**.5,1e-20);relative=float(np.mean(np.abs(a-b))/max(float(np.mean(np.abs(a))+np.mean(np.abs(b)))/2,1e-10));row={'unitId':identity,'condition':arm,'meeting':pair[0]['meeting'],'requestedProfiles':[x['profileId'] for x in pair],'twoOutputSignedCorrelation':corr,'twoOutputRelativeAbsoluteDifference':relative};rows.append(row);current.append(row)
    summary[arm]={'pairs':len(current),'meanTwoOutputCorrelation':float(np.mean([x['twoOutputSignedCorrelation'] for x in current])),'medianTwoOutputCorrelation':float(np.median([x['twoOutputSignedCorrelation'] for x in current])),'pairsWithCorrelationAbovePoint9':sum(x['twoOutputSignedCorrelation']>.9 for x in current),'meanRelativeAbsoluteDifference':float(np.mean([x['twoOutputRelativeAbsoluteDifference'] for x in current]))}
result={'state':'POST_REJECTION_DIFFERENT_PROFILE_OUTPUT_IDENTITY_DIAGNOSTIC','summary':summary,'perPair':rows,'highCorrelationIsDiagnosticNotAutomaticProofOfIgnoredSpeaker':True,'noNewModelCalls':True,'candidateStillRejected':True};assert not (C/'identity-output-diagnostic.json').exists();atomic_json(C/'identity-output-diagnostic.json',result);print(json.dumps(result['summary']),flush=True)
