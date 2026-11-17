"""Presence-only replay of cached Q8/fixed30 outputs; identities stay native8."""
from pathlib import Path
from datetime import datetime
import argparse,math,os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from meeting_acoustic_contract_20261116 import read,sha,require
from score_joint_whole_meetings_20261115 import parse_native,rttm
from fixed_presence_identity_core_20261117 import compose
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--meeting',required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);P=read(a.protocol)
    for item in P['files']:require(sha(item['file'])==item['sha256'],'Frozen cached presence dependency changed')
    require(a.meeting in P['admittedEnglishSources'],'This candidate is English-only')
    case=next(r for r in read(P['audioOnly']) if r['meeting']==a.meeting)
    source=read(P['predictedBindings'])['sources'][a.meeting]
    for name in ['probabilities','sourceJournal','producer','probabilityManifest']:
        require(sha(source[name])==source[name+'Sha256'],'Original native8 prediction changed')
    require(source['audioSha256']==case['audioSha256'],'Original input mismatch')
    base_file=Path(source['sourceJournal']).with_name('predicted.rttm')
    require(sha(base_file)==read(source['producer'])['rttmSha256'],'Original RTTM changed')
    binding=read(P['cachedInferenceBinding']);state_file=Path(P['cachedInferenceRun'])/'inference-state.json'
    state=read(state_file);require(state['state']=='COMPLETE_CPU_FIXED_CHUNKS_COMPOSITION_AND_SCORING_PENDING'
        and len(state['completed'])==290,'Original full cached inference is not complete')
    completed={r['id']:r for r in state['completed']};activity=[];invalid=[];cursor=0;count=0;input_receipts=[]
    for chunk in [r for r in binding['cases'] if r['meeting']==a.meeting]:
        entry=completed[chunk['id']];require(sha(entry['file'])==entry['sha256'],'Cached block changed')
        packet=read(entry['file']);require(packet['case']==chunk and packet['naturalEos'] and not packet['wasTruncated']
            and packet['semanticError'] is None and packet['originalChunkInputComplete']
            and packet['modelSha256']==P['originalInferenceModelSha256']
            and packet['referenceRead'] is False and packet['wordsRewritten'] is False,'Invalid cached source block')
        require(chunk['sourceStartFrame']==cursor,'Original block coverage gap')
        cursor=chunk['sourceEndFrame'];count+=1;offset=chunk['sourceStartFrame']/16000
        parsed,_,_=parse_native(packet['rawDecoded'])
        for index,row in enumerate(parsed):
            if not math.isfinite(row['start']) or not math.isfinite(row['end']) or not 0<=row['start']<row['end']<=chunk['audioSeconds']:
                invalid.append({'block':chunk['id'],'index':index,'start':row['start'],'end':row['end']});continue
            activity.append({'start':offset+row['start'],'end':offset+row['end']})
        input_receipts.append({'id':chunk['id'],'file':entry['file'],'sha256':entry['sha256']})
    require(cursor==case['frames'],'Original source tail missing')
    data=np.load(source['probabilities'],mmap_mode='r',allow_pickle=False)
    result=compose(activity,rttm(base_file),data,source,case,a.output,a.meeting)
    result.update(state='PREDICTION_ONLY_PRESENCE_IDENTITY_COMPLETE_PENDING_SCORING',
        at=datetime.now().astimezone().isoformat(timespec='seconds'),meeting=a.meeting,
        audioSha256=case['audioSha256'],frames=cursor,audioSeconds=case['audioSeconds'],
        protocolSha256=sha(a.protocol),sourceRttm=str(base_file),sourceRttmSha256=sha(base_file),
        cachedInferenceStateSha256=sha(state_file),cachedBlocks=count,cachedInputReceipts=input_receipts,
        invalidNativeTimeSegments=invalid,originalActiveIdentitiesPreserved=True,mossLocalSpeakerIdsUsed=False,
        referencesRead=False,wordsChanged=False,newNeuralCalls=0,trainingUpdates=0,
        scope=P['purpose'],qualityQualified=False,saleQualified=False,limits=limits.query())
    atomic_json(a.output/'prediction.json',result)
    print(__import__('json').dumps({k:result[k] for k in ['meeting','cachedBlocks','assignedSupplementSeconds','unknownIdentitySeconds','invalidNativeTimeSegments','newNeuralCalls']}))

if __name__=='__main__':main()
