"""Reference-time acoustic associations for frozen English errors, no models.

Energy contains room/background sound; this cannot establish intelligibility,
true SNR, or the cause of a model error. All original WER edits are retained.
"""
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib
import json
import os
import sys
import wave

os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
sys.path.insert(0,str(ROOT/'model-research/src'))
import numpy as np
from rapidfuzz.distance import Levenshtein
from score_sequential_meetings_20261115 import tokens
from moss_windows_resource_limits_20261104 import WorkerLimits, SystemRamPressure

D = ROOT/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C = D/'sequential-meeting-stageA-r2'
OUT = D/'joint-architecture-r1/english-acoustic-omission-review20261116.json'
read = lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()
limits = WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
pressure = SystemRamPressure()
assert not pressure.low()
cases = [r for r in read(C/'scoring-only.json') if r['language']=='English' and r['role']=='validation']
base = {r['id']:r for r in read(C/'raw-text-baseline.json')['cases']}
words, turns, clips = [], [], []
for case in cases:
    assert not pressure.low() and not case['overlapPresentByReference']
    assert sha(case['wav']) == case['wavSha256']
    with wave.open(case['wav'],'rb') as f:
        assert (f.getnchannels(),f.getframerate(),f.getsampwidth(),f.getnframes()) == (1,16000,2,case['frames'])
        pcm = np.frombuffer(f.readframes(f.getnframes()),dtype='<i2')
    x = pcm.astype(np.float64)/32768
    start = case['sourceStartFrame']/16000
    reference = tokens(case['rawReferenceText'],'English')
    hypothesis = tokens(base[case['id']]['hypothesis'],'English')
    edits = Levenshtein.editops(reference,hypothesis)
    assert len(edits) == base[case['id']]['errors']
    statuses = {op.src_pos:op.tag for op in edits if op.tag!='insert'}
    atoms, local_turns = [], []
    for event in case['referenceEvents']:
        values = tokens(event['text'],'English')
        if not values:
            continue
        assert event['annotationElement']=='w'
        if not local_turns or local_turns[-1]['speaker']!=event['speaker']:
            local_turns.append({'id':case['id'],'speaker':event['speaker'],'start':event['start'],
                                'end':event['end'],'tokens':[],'deleted':0})
        turn = local_turns[-1]; turn['end']=max(turn['end'],event['end'])
        lo=max(0,min(len(x),round((event['start']-start)*16000)))
        hi=max(lo,min(len(x),round((event['end']-start)*16000)))
        segment=x[lo:hi]
        rms=float(np.sqrt(max(0.,float(np.mean(segment*segment)-np.mean(segment)**2)))) if hi>lo else None
        for token in values:
            index=len(atoms)
            status=statuses.get(index,'equal')
            row={'id':case['id'],'meeting':case['meeting'],'speaker':event['speaker'],
                 'referenceIndex':index,'token':token,'edit':status,
                 'samples':hi-lo,'rms':rms,'validEnergyInterval':hi-lo>=80,
                 'shortTurnIndex':len(local_turns)-1}
            atoms.append(row); turn['tokens'].append(token)
            turn['deleted']+=int(status=='delete')
    assert [r['token'] for r in atoms]==reference
    nonzero=[r['rms'] for r in atoms if r['validEnergyInterval'] and r['rms']>0]
    median=float(np.median(nonzero))
    assert median>0
    for row in atoms:
        row['relativeToClipMedianRms']=row['rms']/median if row['validEnergyInterval'] else None
    for turn in local_turns:
        lo=max(0,round((turn['start']-start)*16000)); hi=min(len(x),round((turn['end']-start)*16000))
        segment=x[lo:hi]
        turn.update(duration=turn['end']-turn['start'],referenceUnits=len(turn['tokens']),
                    fullyDeleted=turn['deleted']==len(turn['tokens']),
                    relativeToClipMedianRms=float(np.std(segment))/median if len(segment) else None)
    words.extend(atoms); turns.extend(local_turns)
    clips.append({'id':case['id'],'sourceWavSha256':case['wavSha256'],'frames':len(x),
                  'nearFullScaleSamples':int(np.count_nonzero(np.abs(pcm.astype(np.int32))>=32760)),
                  'absolutePeak':float(np.max(np.abs(x))),'wordMedianRms':median,
                  'deletions':sum(r['edit']=='delete' for r in atoms),
                  'invalidOrVeryShortWordIntervals':sum(not r['validEnergyInterval'] for r in atoms)})
valid=[r for r in words if r['relativeToClipMedianRms'] is not None]
threshold=float(np.quantile([r['relativeToClipMedianRms'] for r in valid],.25))
low=[r for r in valid if r['relativeToClipMedianRms']<=threshold]
other=[r for r in valid if r['relativeToClipMedianRms']>threshold]
def summary(items):
    counts=Counter(r['edit'] for r in items)
    return {'referenceUnits':len(items),'deleted':counts['delete'],'substituted':counts['replace'],
            'deletionRate':counts['delete']/len(items) if items else None,
            'medianRelativeRms':float(np.median([r['relativeToClipMedianRms'] for r in items])) if items else None}
short=[t for t in turns if t['duration']<=2]
assert len(words)==709 and sum(r['edit']=='delete' for r in words)==72 and len(short)==14
result={'state':'COMPLETE_FROZEN_ENGLISH_ACOUSTIC_ASSOCIATION_AUDIT_NO_INFERENCE',
        'at':datetime.now().astimezone().isoformat(timespec='seconds'),
        'referenceWords':709,'baselineErrors':141,'baselineDeletions':72,
        'wordEnergyCoverage':len(valid),'unreliableEnergyIntervals':len(words)-len(valid),
        'lowerQuartileThresholdRelativeRms':threshold,
        'lowerEnergyQuartile':summary(low),'remainingEnergyWords':summary(other),
        'byEdit':{key:summary([r for r in valid if r['edit']==key]) for key in ['equal','replace','delete']},
        'shortTurns':short,'clips':clips,'wordInspection':words,
        'inputs':[{'file':str(p),'sha256':sha(p)} for p in [C/'scoring-only.json',C/'raw-text-baseline.json']],
        'sourceSha256':sha(__file__),
        'method':'Original AMI word times clipped to unchanged16kHz PCM. DC-removed RMS,normalized by per-clip median nonzero word RMS. Fixed lower quartile chosen from all word energies without error labels; intervals<5ms excluded from energy associations only, never from WER.',
        'limitsOfInference':['Room/background energy is not target-speaker SNR or intelligibility.','Levenshtein allocation can be ambiguous for repeated words.','Association on12 exposed English clips cannot establish causality or generalization.','No waveform gain/denoise/VAD/word/reference/score changed.'],
        'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'saleQualified':False,
        'limits':limits.query()}
assert 'torch' not in sys.modules and not OUT.exists()
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
pressure.close()
print(json.dumps({k:result[k] for k in ['state','wordEnergyCoverage','unreliableEnergyIntervals',
                 'lowerEnergyQuartile','remainingEnergyWords','byEdit','newNeuralCalls']},ensure_ascii=False))
