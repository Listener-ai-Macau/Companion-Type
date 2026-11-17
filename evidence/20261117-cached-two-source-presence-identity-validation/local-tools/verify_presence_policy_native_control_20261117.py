"""Require exact retained native180 RTTMs before applying factored policy."""
from pathlib import Path
from datetime import datetime
import json,math,os,sys
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
import numpy as np
from meeting_acoustic_contract_20261116 import read,require,sha
from score_joint_whole_meetings_20261115 import parse_native,rttm
from fixed_presence_identity_core_20261117 import compose
from durable_model_state_20261117 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
P=read(J/'context-activity-r1/quantized30-presence-r1/protocol.json')
out=E/'context-activity-r1/quantized30-presence-r1/native180-control'
case=next(r for r in read(P['audioOnly']) if r['meeting']=='ES2003b')
source=read(P['predictedBindings'])['sources']['ES2003b']
original=read(P['retainedNative180Prediction'])
done_file=Path(P['retainedNative180Run'])/'ES2003b-completed.json';done=read(done_file)
require(done['naturalEos'] and done['audioSha256']==case['audioSha256'] and done['frames']==case['frames'],'Native control incomplete')
activity=[];cursor=0
for block in done['blocks']:
    require(sha(block['file'])==block['sha256'] and block['startFrame']==cursor,'Native control block changed')
    packet=read(block['file']);require(packet['binding']==done['binding'] and packet['naturalEos'],'Invalid native control')
    cursor=block['endFrame'];offset=block['startFrame']/16000
    parsed,_,_=parse_native(packet['rawDecoded'])
    for row in parsed:
        if math.isfinite(row['start']) and math.isfinite(row['end']) and 0<=row['start']<row['end']<=packet['audioSeconds']:
            activity.append({'start':offset+row['start'],'end':offset+row['end']})
require(cursor==case['frames'],'Native source tail missing')
data=np.load(source['probabilities'],mmap_mode='r',allow_pickle=False)
result=compose(activity,rttm(original['sourceRttm']),data,source,case,out,'ES2003b')
for name in ['mossMapped','combined']:
    require(sha(original[name]['file'])==original[name]['sha256'],'Retained RTTM changed')
    require(Path(result[name]['file']).read_bytes()==Path(original[name]['file']).read_bytes(),
        'Factoring changed original '+name+' RTTM bytes')
require(result['unknownIdentitySeconds']==original['unknownIdentitySeconds'],'Identity uncertainty changed')
report={'state':'PASS_EXACT_ORIGINAL_NATIVE180_SUPPLEMENT_AND_COMBINED_RTTM_CONTROL',
    'at':datetime.now().astimezone().isoformat(),'meeting':'ES2003b','sourceCompletedSha256':sha(done_file),
    'originalPredictionSha256':sha(P['retainedNative180Prediction']),
    'factoredPolicySha256':sha(S/'fixed_presence_identity_core_20261117.py'),
    'combinedSha256':result['combined']['sha256'],'supplementSha256':result['mossMapped']['sha256'],
    'newNeuralCalls':0,'trainingUpdates':0,'referencesRead':False,'limits':limits.query()}
atomic_json(out/'result.json',report);print(json.dumps(report))
