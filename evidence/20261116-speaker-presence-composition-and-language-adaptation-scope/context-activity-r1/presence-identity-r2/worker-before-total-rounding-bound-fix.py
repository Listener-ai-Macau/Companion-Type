"""Separate speech presence and stable identity without retraining either model.

Retain every original active speaker interval. Only where the original raw
journal is empty, use MOSS speech presence and the continuous native8 posterior
winner. MOSS local IDs never determine identity; ties remain explicit unknowns.
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
from meeting_acoustic_contract_20261116 import read,sha,require
from score_joint_whole_meetings_20261115 import parse_native,union,rttm
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json


def intersections(left,right):
    i=j=0;out=[]
    while i<len(left) and j<len(right):
        low=max(left[i]['start'],right[j]['start']);high=min(left[i]['end'],right[j]['end'])
        if high>low:out.append({'start':low,'end':high})
        if left[i]['end']<right[j]['end']:i+=1
        else:j+=1
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--meeting',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);P=read(a.protocol)
    for item in P['files']:require(sha(item['file'])==item['sha256'],'Frozen presence/identity source changed')
    require(a.meeting in P['admittedEnglishSources'],'This fixed candidate is English-only')
    case=next(r for r in read(P['audioOnly']) if r['meeting']==a.meeting)
    source=read(P['predictedBindings'])['sources'][a.meeting]
    for name in ['probabilities','sourceJournal','producer','probabilityManifest']:
        require(sha(source[name])==source[name+'Sha256'],'Continuous native8 prediction changed')
    require(source['audioSha256']==case['audioSha256'],'Original audio/speaker state mismatch')
    base_file=Path(source['sourceJournal']).with_name('predicted.rttm')
    require(sha(base_file)==read(source['producer'])['rttmSha256'],'Original RTTM changed')
    base=rttm(base_file);data=np.load(source['probabilities'],mmap_mode='r',allow_pickle=False)
    done=read(a.run/(a.meeting+'-completed.json'));state=read(a.run/'state.json')
    require(state['nativeControlExact'] and done['binding']==state['binding'] and done['naturalEos']
        and done['audioSha256']==case['audioSha256'] and done['frames']==case['frames']
        and done['binding']['protocolSha256']==sha(P['nativeProtocol'])
        and done['binding']['workerSha256']==sha(P['nativeWorker']),'Different/incomplete MOSS source')
    activity=[];invalid=[];cursor=0
    for block in done['blocks']:
        require(sha(block['file'])==block['sha256'] and block['startFrame']==cursor,'Native block gap/change')
        out=read(block['file']);require(out['binding']==done['binding'] and out['naturalEos'],'Invalid native block')
        cursor=block['endFrame'];offset=block['startFrame']/16000
        parsed,all_rows,residual=parse_native(out['rawDecoded'])
        for index,row in enumerate(parsed):
            if not math.isfinite(row['start']) or not math.isfinite(row['end']) or not 0<=row['start']<row['end']<=out['audioSeconds']:
                invalid.append({'block':block['id'],'index':index,'start':row['start'],'end':row['end']});continue
            activity.append({'start':offset+row['start'],'end':offset+row['end']})
    require(cursor==case['frames'],'Original source tail missing')
    duration=case['audioSeconds'];occupied=union([{'start':max(0,r['start']),'end':min(duration,r['end'])}
        for r in base if r['end']>0 and r['start']<duration])
    gaps=[];end=0.
    for interval in occupied:
        if interval['start']>end:gaps.append({'start':end,'end':interval['start']})
        end=max(end,interval['end'])
    if end<duration:gaps.append({'start':end,'end':duration})
    support=intersections(union(activity),gaps);supplement=[];unknown=[];cadence=source['cadence']
    minimum_margin=1.;minimum_posterior=1.;assigned_seconds=unknown_seconds=0.
    for index,interval in enumerate(support):
        for g in range(math.floor(interval['start']/cadence),math.ceil(interval['end']/cadence)):
            low=max(interval['start'],g*cadence);high=min(interval['end'],(g+1)*cadence)
            if high<=low:continue
            require(0<=g<source['frames'],'Missing native8 posterior frame')
            values=np.asarray(data[g]);require(values.shape==(8,) and np.isfinite(values).all(),'Invalid native8 posteriors')
            winner=int(values.argmax());best=float(values[winner]);unique=int(np.count_nonzero(values==values[winner]))==1
            if unique:
                label='speaker_'+str(winner);assigned_seconds+=high-low
                minimum_posterior=min(minimum_posterior,best)
                minimum_margin=min(minimum_margin,best-float(np.partition(values,-2)[-2]))
            else:
                label='unknown_identity_'+str(index);unknown_seconds+=high-low
            row={'start':low,'end':high,'speaker':label};supplement.append(row)
            if not unique:unknown.append(row)
    a.output.mkdir(parents=True,exist_ok=False)
    def write(name,rows):
        groups=defaultdict(list)
        rounded_zero=0;rounded_zero_seconds=0.
        for row in rows:
            # Match the retained RTTM's six-decimal format before merging.
            # Native cadence is a float; intersections at the same serialized
            # boundary can otherwise produce positive1e-14s phantom cells.
            low=round(row['start']*1000000);high=round(row['end']*1000000)
            require(high>=low,'Time serialization reversed an interval')
            if high==low:
                require(0<=row['end']-row['start']<.5e-6,'A real interval vanished in time serialization')
                rounded_zero+=1;rounded_zero_seconds+=row['end']-row['start'];continue
            groups[row['speaker']].append(dict(row,start=low/1000000,end=high/1000000))
        require(rounded_zero_seconds<1e-8,'Unexpected total sub-microsecond timing loss')
        rows=[dict(r,speaker=s) for s,items in groups.items() for r in union(items)]
        rows.sort(key=lambda r:(r['start'],r['end'],r['speaker']))
        path=a.output/name
        path.write_text(''.join(f"SPEAKER {a.meeting} 1 {r['start']:.6f} {r['end']-r['start']:.6f} <NA> <NA> {r['speaker']} <NA> <NA>\n" for r in rows),encoding='utf-8')
        return {'file':str(path),'sha256':sha(path),'segments':len(rows),
            'zeroDurationFloatIntersectionCellsNotSerialized':rounded_zero,
            'totalFloatPhantomSeconds':rounded_zero_seconds,'timeResolutionSeconds':1e-6}
    supplemental=write('presence-identity-supplement.rttm',supplement)
    combined=write('combined.rttm',base+supplement)
    result={'state':'PREDICTION_ONLY_PRESENCE_IDENTITY_COMPLETE_PENDING_SCORING',
        'at':datetime.now().astimezone().isoformat(timespec='seconds'),'meeting':a.meeting,
        'audioSha256':case['audioSha256'],'frames':cursor,'audioSeconds':duration,
        'protocolSha256':sha(a.protocol),'nativeCompletedSha256':sha(a.run/(a.meeting+'-completed.json')),
        'sourceRttm':str(base_file),'sourceRttmSha256':sha(base_file),
        'mossMapped':supplemental,'combined':combined,'invalidNativeTimeSegments':invalid,
        'unmatchedLocalSpeakerSegments':unknown,'unknownIdentitySeconds':unknown_seconds,
        'assignedSupplementSeconds':assigned_seconds,'minimumAssignedPosterior':minimum_posterior,
        'minimumAssignedTopTwoMargin':minimum_margin,
        'originalActiveIdentitiesPreserved':True,'mossLocalSpeakerIdsUsed':False,
        'referencesRead':False,'wordsChanged':False,'newNeuralCalls':0,'trainingUpdates':0,
        'recipe':'MOSS supplies speech presence only. Fill original raw-journal empty regions only, with the unique maximum of original continuous native8 posteriors. Retain exact ties as unknowns, retain every original multi-voice active interval. No probability, gain, collar, padding, or fusion-weight grid.',
        'scope':'English turn-taking activity supplement; it does not recover additional overlapping voices while the original journal is already active. Unknown identities remain explicit. Chinese default unchanged.',
        'qualityQualified':False,'saleQualified':False,'limits':limits.query()}
    atomic_json(a.output/'prediction.json',result)
    print(json.dumps({'state':result['state'],'meeting':a.meeting,'additionalSpeakerSeconds':assigned_seconds,
        'unknownIdentitySeconds':unknown_seconds,'invalidTimes':len(invalid),'newNeuralCalls':0},ensure_ascii=False))


if __name__=='__main__':main()
