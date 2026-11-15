from pathlib import Path
from datetime import datetime
import hashlib,json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
import numpy as np
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'independent-voice-return-probe-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/independent-voice-return-probe-r1/probe-r1')
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
target=C/'decision.json';assert not target.exists()
state=read(E/'state.json');protocol=read(C/'protocol.json')
assert state['state']=='COMPLETE_PUBLIC_INDEPENDENT_VOICE_EXTRACTOR_DIAGNOSIS_SCORE_PENDING'
assert state['parameterUpdates']==0 and state['referenceRead'] is False
assert hashlib.sha256((C/'scoring-only.json').read_bytes()).hexdigest()==protocol['scoringOnlySha256']
values=np.load(E/'embeddings.npy',allow_pickle=False)
assert hashlib.sha256((E/'embeddings.npy').read_bytes()).hexdigest()==state['embeddingsSha256']
values=values/np.linalg.norm(values,axis=1,keepdims=True)
cases=read(C/'scoring-only.json');assert state['clipIds']==[r['id'] for r in cases]
profiles=[i for i,r in enumerate(cases) if r['role']=='profile'];queries=[i for i,r in enumerate(cases) if r['role']=='query']
assert len(profiles)==4 and len(queries)==3
rows=[]
for i in queries:
    similarity=values[profiles]@values[i];order=np.argsort(similarity)[::-1]
    predicted=cases[profiles[order[0]]]['referenceSpeaker'];truth=cases[i]['referenceSpeaker']
    rows.append(dict(id=cases[i]['id'],referenceSpeaker=truth,highestProfileSpeaker=predicted,
                     correct=predicted==truth,margin=float(similarity[order[0]]-similarity[order[1]]),
                     cosineByReferenceProfileForDiagnosisOnly={cases[j]['referenceSpeaker']:float(v) for j,v in zip(profiles,similarity)}))
passed=all(r['correct'] for r in rows)
result=dict(state='PASS_REFERENCE_ASSISTED_LONG_RETURN_VOICE_DIAGNOSIS_ONLY' if passed else 'REJECT_FIXED_INDEPENDENT_VOICE_RETURN_PROBE',
            at=datetime.now().astimezone().isoformat(),rows=rows,allThreeCorrect=passed,
            numericalControl=dict(maximumFeatureDifference=state['maximumFeatureDifference'],
                                  meanFeatureDifference=state['meanFeatureDifference'],
                                  embeddingCpuGpuCosine=state['embeddingCpuGpuCosine']),
            originalWholeMeetingDiarizationTested=False,unsupervisedSpeakerCountTested=False,
            referenceAssistedCutsAndProfiles=True,originalScoresChanged=False,
            newNeuralCalls=0,newTrainingUpdates=0,ownerParticipationRequired=False,
            qualityQualified=False,d2Complete=False,saleQualified=False,
            next='Design one full original-development combination using predicted segmentation only, after checking whether relabel-only segmentation can mathematically reach the original gate. No reference identities/counts/profiles in full inference.' if passed else 'Stop this fixed probe. Do not change reference profiles/window lengths/query selection or similarity thresholds.',
            limits=limits.query())
target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='limits'},ensure_ascii=False))
