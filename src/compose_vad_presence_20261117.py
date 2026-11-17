"""Official VAD presence, retained native8 identity, unchanged fixed fusion."""
from pathlib import Path
from datetime import datetime
import argparse,json,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from meeting_acoustic_contract_20261116 import read,sha,require
from score_joint_whole_meetings_20261115 import rttm
from fixed_presence_identity_core_20261117 import compose
from durable_model_state_20261117 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--meeting',required=True)
    parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);P=read(a.protocol)
    for item in P['files']:require(sha(item['file'])==item['sha256'],'Frozen VAD composition dependency changed')
    require(a.meeting in P['meetings'],'English-only detector experiment')
    case=next(r for r in read(P['audioOnly']) if r['meeting']==a.meeting)
    state=read(a.run/'completed.json');require(state['state']=='COMPLETE_TWO_CPU_VAD_FULL_SOURCES_PENDING_COMPOSITION'
        and len(state['completed'])==2 and state['binding']['protocolSha256']==sha(a.protocol),
        'Full detector run incomplete/different')
    item=next(r for r in state['completed'] if r['meeting']==a.meeting)
    require(sha(item['file'])==item['sha256'],'Closed VAD result changed');packet=read(item['file'])
    require(packet['binding']==state['binding'] and packet['frames']==case['frames']
        and packet['audioSha256']==case['audioSha256'] and packet['allOriginalFramesCovered'],'VAD source pairing differs')
    source=read(P['predictedBindings'])['sources'][a.meeting]
    for name in ['probabilities','sourceJournal','producer','probabilityManifest']:
        require(sha(source[name])==source[name+'Sha256'],'Original native8 prediction changed')
    require(source['audioSha256']==case['audioSha256'],'Original source differs')
    base=Path(source['sourceJournal']).with_name('predicted.rttm')
    require(sha(base)==read(source['producer'])['rttmSha256'],'Original RTTM changed')
    activity=[{'start':r['start']/16000,'end':r['end']/16000} for r in packet['segmentsInOriginalSamples']]
    data=np.load(source['probabilities'],mmap_mode='r',allow_pickle=False)
    result=compose(activity,rttm(base),data,source,case,a.output,a.meeting)
    result.update(state='PREDICTION_ONLY_PRESENCE_IDENTITY_COMPLETE_PENDING_SCORING',
        at=datetime.now().astimezone().isoformat(),meeting=a.meeting,audioSha256=case['audioSha256'],
        frames=case['frames'],audioSeconds=case['audioSeconds'],protocolSha256=sha(a.protocol),
        sourceRttm=str(base),sourceRttmSha256=sha(base),presenceResultSha256=sha(item['file']),
        invalidNativeTimeSegments=[],referencesRead=False,wordsChanged=False,mossLocalSpeakerIdsUsed=False,
        originalActiveIdentitiesPreserved=True,newNeuralCalls=0,trainingUpdates=0,
        scope='Official default CPU VAD presence only; original continuous native8 identities and active intervals retained.',
        qualityQualified=False,saleQualified=False,limits=limits.query())
    atomic_json(a.output/'prediction.json',result)
    print(json.dumps({k:result[k] for k in ['meeting','assignedSupplementSeconds','unknownIdentitySeconds','newNeuralCalls']}))

if __name__=='__main__':main()
