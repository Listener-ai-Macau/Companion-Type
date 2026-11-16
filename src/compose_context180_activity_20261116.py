"""Prediction-only meeting activity composition; no words or gold labels read.

Use nativeMOSS local speaker groups to supplement the retained continuous
Nemotron journal. One fixed union, no threshold/padding/fusion-weight search.
"""
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import argparse
import json
import math
import os

os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from scipy.optimize import linear_sum_assignment
from meeting_acoustic_contract_20261116 import read,sha,require
from companion_exclusive_journal_20261114 import exclusive_journal
from score_sequential_speakers_20261115 import overlap_seconds
from score_joint_whole_meetings_20261115 import parse_native,union,rttm
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--meeting',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
    P=read(a.protocol)
    for item in P['files']:require(sha(item['file'])==item['sha256'],'Activity composition source changed')
    case=next(r for r in read(P['audioOnly']) if r['meeting']==a.meeting)
    source=read(P['predictedBindings'])['sources'][a.meeting]
    for name in ['probabilities','sourceJournal','producer','probabilityManifest']:
        require(sha(source[name])==source[name+'Sha256'],'Original continuous speaker prediction changed')
    require(source['audioSha256']==case['audioSha256'],'Speaker/audio identity mismatch')
    original_rttm=Path(source['sourceJournal']).with_name('predicted.rttm')
    require(sha(original_rttm)==read(source['producer'])['rttmSha256'],'Original RTTM changed')
    base_rows=rttm(original_rttm)
    done=read(a.run/(a.meeting+'-completed.json'));state=read(a.run/'state.json')
    require(state['nativeControlExact'] and done['binding']==state['binding'] and done['naturalEos']
        and done['audioSha256']==case['audioSha256'] and done['frames']==case['frames']
        and done['binding']['protocolSha256']==sha(P['nativeProtocol'])
        and done['binding']['workerSha256']==sha(P['nativeWorker']),'Incomplete/different nativeMOSS source')
    probabilities=np.load(source['probabilities'],mmap_mode='r',allow_pickle=False)
    primary,exclusive_receipt=exclusive_journal(probabilities,frames=source['frames'],
        seconds_per_frame=source['cadence'],source_journal=read(source['sourceJournal']))
    global_ids=sorted({r['speaker'] for r in primary['segments']})
    supplemental=[];invalid=[];unknown=[];trace=[];cursor=0
    for block in done['blocks']:
        require(sha(block['file'])==block['sha256'] and block['startFrame']==cursor,'Native block identity/continuity changed')
        out=read(block['file']);require(out['binding']==done['binding'] and out['naturalEos'],'Invalid native output')
        cursor=block['endFrame'];offset=block['startFrame']/16000
        parsed,all_rows,residual=parse_native(out['rawDecoded'])
        def valid(r):
            return math.isfinite(r['start']) and math.isfinite(r['end']) and 0<=r['start']<r['end']<=out['audioSeconds']
        local=sorted({r['speaker'] for r in parsed if valid(r)})
        matrix=np.zeros((len(local),len(global_ids)))
        for i,speaker in enumerate(local):
            intervals=union([dict(r,start=offset+r['start'],end=offset+r['end']) for r in parsed if valid(r) and r['speaker']==speaker])
            for j,person in enumerate(global_ids):
                matrix[i,j]=overlap_seconds(intervals,[r for r in primary['segments'] if r['speaker']==person])
        rr,cc=linear_sum_assignment(-matrix)
        mapping={local[i]:global_ids[j] for i,j in zip(rr,cc) if matrix[i,j]>0}
        for index,row in enumerate(parsed):
            if not valid(row):
                invalid.append({'block':block['id'],'index':index,'start':row['start'],'end':row['end']});continue
            person=mapping.get(row['speaker'])
            label='speaker_'+str(person) if person is not None else 'unmatched_'+block['id']+'_'+row['speaker']
            item={'start':offset+row['start'],'end':offset+row['end'],'speaker':label}
            if person is None:unknown.append(dict(item,localSpeaker=row['speaker']))
            supplemental.append(item)
        trace.append({'block':block['id'],'localOrder':local,'globalOrder':global_ids,
            'localToGlobal':mapping,'overlapSecondsMatrix':matrix.tolist(),
            'lexicalResidualCountNotRewrittenOrUsedAsActivity':len(residual)})
    require(cursor==case['frames'],'Whole source original tail missing')
    a.output.mkdir(parents=True,exist_ok=False)
    def write_journal(name,rows):
        groups=defaultdict(list)
        for row in rows:groups[row['speaker']].append(row)
        merged=[dict(r,speaker=s) for s,items in groups.items() for r in union(items)]
        merged.sort(key=lambda r:(r['start'],r['end'],r['speaker']))
        path=a.output/name
        path.write_text(''.join(f"SPEAKER {a.meeting} 1 {r['start']:.6f} {r['end']-r['start']:.6f} <NA> <NA> {r['speaker']} <NA> <NA>\n" for r in merged),encoding='utf-8')
        return {'file':str(path),'sha256':sha(path),'segments':len(merged)}
    moss=write_journal('moss-mapped.rttm',supplemental)
    combined=write_journal('combined.rttm',base_rows+supplemental)
    result={'state':'PREDICTION_ONLY_CONTEXT_ACTIVITY_UNION_COMPLETE_PENDING_SCORING',
        'at':datetime.now().astimezone().isoformat(timespec='seconds'),'meeting':a.meeting,
        'audioSha256':case['audioSha256'],'frames':cursor,'audioSeconds':case['audioSeconds'],
        'protocolSha256':sha(a.protocol),'nativeCompletedSha256':sha(a.run/(a.meeting+'-completed.json')),
        'sourceRttm':str(original_rttm),'sourceRttmSha256':sha(original_rttm),
        'mossMapped':moss,'combined':combined,'invalidNativeTimeSegments':invalid,
        'unmatchedLocalSpeakerSegments':unknown,'trace':trace,'exclusiveAssociationReceipt':exclusive_receipt,
        'referencesRead':False,'wordsChanged':False,'newNeuralCalls':0,'trainingUpdates':0,
        'recipe':'Retain original raw multi-voice journal and union independently predicted MOSS word-segment activity after prediction-only Hungarian local/global association. No frame threshold, collar, padding, or reference-dependent selection changed.',
        'scope':'A candidate activity journal, not acceptance of new words, real names, whole-product identity or CPU execution. Unknown speakers and invalid times remain explicit.',
        'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
    atomic_json(a.output/'prediction.json',result)
    print(json.dumps({'state':result['state'],'meeting':a.meeting,'supplementalSegments':moss['segments'],
        'combinedSegments':combined['segments'],'invalidTimes':len(invalid),'unmatched':len(unknown),'newNeuralCalls':0},ensure_ascii=False))


if __name__=='__main__':main()
