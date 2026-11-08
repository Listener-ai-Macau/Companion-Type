"""Reference-assisted audio-gate diagnostic, never a product accuracy candidate."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,math,wave
import numpy as np
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals
from full_meeting_transcript_metrics_20261103 import normalize

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
B=R/'docs/handoffs/20261107-model-generation-recovery'
C=R/'docs/handoffs/20261108-target-activity-adaptation/oracle-activity-diagnostic'
E=Path('E:/CodexData/Companion/.model-cache/target-activity-adaptation-20261108/oracle-activity-diagnostic')
F=B/'practical-conditioned-ps4-full-r1';read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
assert not C.exists();C.mkdir();E.mkdir(parents=True,exist_ok=False)
assert read(C.parent/'decision.json')['state']=='BOUNDED_REAL_MEETING_HEAD_ADAPTATION_REJECTED_BASELINE_RETAINED'
oldP=read(F/'protocol-r2.json');source=S/'practical_ps4_full_worker_20261107.py';assert sha(source)==oldP['workerSourceSha256']
case=next(r for r in read(B/'practical-target-activity-r1/scoring-only.json') if r['meeting']=='L_R003S01C02')
assert sha(case['reference'])==case['referenceSha256']
reference=[r for r in read_reference_intervals(case['reference']) if normalize(r['text'])]
mapping={int(v['matchedAnonymousGroup'].removeprefix('speaker_')):person for person,v in read(case['fixedMappingReview'])['perReferenceSpeakerForEvaluationOnly'].items()}
cases={r['rootIndex']:r for r in read(F/'audio-only.json')}
lanes=read(F/'separation-manifest-r2.json');original_asr={r['id']:r for r in read(F/'asr-manifest-r2.json')}
selected=[r for r in lanes if r['rootIndex'] in [12,27]]
assert len(selected)==6 and all(r['voiceIdentity']['targetIsTop1'] for r in selected)
prepared=[];scoring=[];roots=[];seeds={}

def load(file):
    with wave.open(str(file),'rb') as f:
        assert f.getframerate()==16000 and f.getnchannels()==1 and f.getsampwidth()==2
        return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').copy()
def write(file,samples):
    assert not file.exists()
    with wave.open(str(file),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(samples.tobytes())

for index in [12,27]:
    clip=cases[index];lo=clip['startSample']/16000;hi=clip['endSample']/16000
    # Fixed roots: the previously exposed true-two control and independently
    # disclosed true-triple supplement, without looking at this trial's text.
    rows=[r for r in reference if r['end']>lo and r['start']<hi]
    points=sorted({lo,hi}|{max(lo,r['start']) for r in rows}|{min(hi,r['end']) for r in rows})
    triple=sum(b-a for a,b in zip(points,points[1:]) if len({r['speaker'] for r in rows if r['start']<(a+b)/2<r['end']})>=3)
    roots.append({'rootIndex':index,'referenceTripleSeconds':triple,
        'availableSeparatedPeople':[mapping[r['predictedSpeaker']] for r in selected if r['rootIndex']==index],
        'actualReferencePeople':sorted({r['speaker'] for r in rows}),
        'rootBoundaryStraddlingReferenceRows':sum(r['start']<lo or r['end']>hi for r in rows)})
    assert sha(clip['audio'])==clip['audioSha256'];mixture=load(clip['audio'])
    for lane in [r for r in selected if r['rootIndex']==index]:
        person=mapping[lane['predictedSpeaker']];assert sha(lane['audio'])==lane['audioSha256']
        voice=load(lane['audio']);assert len(voice)==len(mixture)==clip['endSample']-clip['startSample']
        mask=np.zeros(len(voice),dtype=bool)
        for row in rows:
            if row['speaker']!=person:continue
            a=max(0,math.floor((row['start']-lo)*16000));b=min(len(mask),math.ceil((row['end']-lo)*16000));mask[a:b]=True
        # Keep the original timeline and every target-active PCM value. Never
        # choose generated words from the reference or shorten time with concat.
        for mode,samples in [('separated',voice),('mixture',mixture)]:
            identity=lane['id']+'-oracle-'+mode;output=E/(identity+'.wav');gated=np.where(mask,samples,0).astype('<i2');write(output,gated)
            roundtrip=load(output);assert np.array_equal(roundtrip[mask],samples[mask]) and not np.any(roundtrip[~mask])
            prepared.append({**lane,'id':identity,'audio':str(output),'audioSha256':sha(output),
                'diagnosticMode':mode,'sourceSeparatedLane':lane['id'],'sourceAudio':lane['audio'] if mode=='separated' else clip['audio'],
                'sourceAudioSha256':lane['audioSha256'] if mode=='separated' else clip['audioSha256'],
                'referenceActivityUsedOnWaveform':True,'noReferenceInputOrOutputFiltering':False,
                'allTargetActivePcmSamplesUnchanged':True,'originalSampleCountAndTimelineUnchanged':True,
                'maskActiveSamples':int(mask.sum()),'referenceWordsNeverProvidedToAsr':True})
            if mode=='separated' and sha(output)==lane['audioSha256']:
                af=F/'asr-outputs-r2'/lane['id']/'completed.json';assert af.exists()
                seeds[identity]={'asrFile':str(af),'asrFileSha256':sha(af),'unchangedInputReuseOnly':True}
        scoring.append({'laneId':lane['id'],'rootIndex':index,'referencePerson':person,
            'referenceText':''.join(r['text'] for r in sorted(rows,key=lambda x:(x['start'],x['end'])) if r['speaker']==person and lo<=(r['start']+r['end'])/2<hi),
            'referenceRowsCrossingClipBoundary':[{k:r[k] for k in ['start','end','text']} for r in rows if r['speaker']==person and (r['start']<lo or r['end']>hi)],
            'cachedUngatedText':original_asr[lane['id']]['text'],
            'cachedUngatedFile':str(F/'asr-outputs-r2'/lane['id']/'completed.json'),
            'cachedUngatedFileSha256':sha(F/'asr-outputs-r2'/lane['id']/'completed.json')})
assert roots[1]['referenceTripleSeconds']>1
atomic_json(C/'audio-only.json',prepared);atomic_json(C/'separation-manifest-r2.json',prepared)
atomic_json(C/'seed-manifest.json',seeds);atomic_json(C/'scoring-only.json',scoring)
(C/'model-ready.json').write_bytes((F/'model-ready.json').read_bytes())
atomic_json(C/'audio-gate-preparation.json',{'state':'COMPLETE_REFERENCE_ACTIVITY_WAVEFORM_GATE_NOT_PRODUCT',
    'rootSelection':[12,27],'roots':roots,'lanes':6,'waveformConditions':12,
    'noReferenceWordsInAudioOnlyManifest':all('referenceText' not in r for r in prepared),
    'gate':'Zero samples outside lexical target reference intervals; floor/ceil sample coverage, no context extension, original timeline. Both original mixture and already extracted voice use the exact same mask.',
    'limitations':'Human utterance boundaries can clip phonetic context; existing predicted target inventory can miss a real person. This isolates this downstream gate on six existing lanes, not an absolute separation upper bound or a speaker-conditioned separation network. No clean per-person waveform reference is available.',
    'originalInputsAndSourceAsrUnchanged':True,'separationCalls':0,'newNeuralCalls':0,'qualityQualified':False,'limits':limits.query()})

text=source.read_text(encoding='utf8').replace(str(F).replace('\\','/'),str(C).replace('\\','/'))
text=text.replace("choices=['separation','asr']","choices=['asr']")
begin=text.index("    if args.stage=='separation':")
end=text.index("    else:\n        assert read(C/'separation-state-r2.json')",begin)
text=text[:begin]+"    if args.stage=='asr':\n"+text[end+len('    else:\n'):]
text=text.replace("assert read(C/'separation-state-r2.json')['state']=='COMPLETE_PS4_SEPARATION_UNQUALIFIED'","assert read(C/'audio-gate-preparation.json')['state']=='COMPLETE_REFERENCE_ACTIVITY_WAVEFORM_GATE_NOT_PRODUCT'")
text=text.replace("'referencePassedToWorker':False","'referencePassedToWorker':True,'referenceDerivedWaveformDiagnostic':True,'noReferenceWordsInPrompt':True")
text=text.replace("result={**case,'text':","result={**case,'binding':binding,'text':")
text=text.replace("'COMPLETE_PS4_'+args.stage.upper()+'_UNQUALIFIED'","'COMPLETE_ORACLE_ACTIVITY_ASR_DIAGNOSTIC_NOT_PRODUCT'")
text=text.replace('Sequential target extraction / unchanged native ASR. No references enter here.','Annotation-assisted waveform gate / unchanged native ASR. Never a product result.')
def infer_ast(value):
    return ast.dump(next(n for n in ast.walk(ast.parse(value)) if isinstance(n,ast.FunctionDef) and n.name=='infer'),include_attributes=False)
assert infer_ast(text)==infer_ast(source.read_text(encoding='utf8'))
worker=S/'target_activity_oracle_asr_worker_20261108.py';assert not worker.exists();worker.write_text(text,encoding='utf8')
launcher_source=(S/'run_practical_ps4_full_20261107.py').read_text(encoding='utf8')
launcher=launcher_source.replace(str(F).replace('\\','/'),str(C).replace('\\','/')).replace("    ('separation','practical_ps4_full_worker_20261107.py',['--stage','separation'],C/'separation-state-r2.json','COMPLETE_PS4_SEPARATION_UNQUALIFIED'),\n",'')
launcher=launcher.replace('practical_ps4_full_worker_20261107.py','target_activity_oracle_asr_worker_20261108.py')
launcher=launcher.replace("'moss_night_gpu_worker_20261104.py'","'moss_night_gpu_worker_20261104.py','target_activity_paired_worker_20261108.py','target_activity_adaptation_worker_20261108.py'")
launcher=launcher.replace('COMPLETE_PS4_ASR_UNQUALIFIED','COMPLETE_ORACLE_ACTIVITY_ASR_DIAGNOSTIC_NOT_PRODUCT').replace('COMPLETE_TARGET_SEPARATION_AND_ASR_REVIEW_REQUIRED','COMPLETE_ORACLE_ACTIVITY_DIAGNOSTIC_REVIEW_REQUIRED')
launcher_file=S/'run_target_activity_oracle_diagnostic_20261108.py';assert not launcher_file.exists();ast.parse(launcher);launcher_file.write_text(launcher,encoding='utf8')
P={**oldP,'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'FROZEN_REFERENCE_WAVEFORM_GATE_CAUSAL_DIAGNOSTIC_NOT_PRODUCT',
    'workerSourceSha256':sha(worker),'audioOnlySha256':sha(C/'audio-only.json'),
    'modelReadySha256':sha(C/'model-ready.json'),'seedManifestSha256':sha(C/'seed-manifest.json'),
    'referenceActivityUsedOnWaveform':True,'asrGenerationFunctionAstUnchanged':True,
    'inferenceFunctionAstSha256':hashlib.sha256(infer_ast(text).encode()).hexdigest(),
    'scope':'One known two-speaker root12 and disclosed true-triple root27, six existing extracted lanes. Compare cached raw separated ASR vs original mixture and extracted voice with identical perfect-reference activity gate. No new separation, no new checkpoint/threshold/window choice, no product or holdout claim.',
    'scoring':'Same per-person midpoint-in-root lexical reference and fixed whole-meeting anonymous mapping across all conditions. Report every lane, boundary-straddling utterances, missed people outside available lanes, edits/misses/insertions; no transcript filtering or winner selection.',
    'decisionRule':'If gated separation remains worse than gated mixture or retains many errors, perfect downstream activity gating alone is insufficient. Do not claim this isolates ASR versus waveform distortion without clean-source targets or proves a different internally conditioned network cannot work.',
    'qualityQualified':False}
atomic_json(C/'protocol-r2.json',P)
atomic_json(C/'preparation.json',{'at':P['at'],'state':P['state'],'protocolSha256':sha(C/'protocol-r2.json'),
    'sourceOriginalFullWorkerSha256':sha(source),'generatedWorkerSha256':sha(worker),
    'workerInferAstMatchesOriginal':True,'roots':roots,'conditions':12,'newModels':0,'finalHoldoutOpened':False,
    'next':'运行固定六路的双音频门控诊断，原生成函数不变；逐人比较全部文字，不作产品成绩。'})
print(json.dumps({'state':P['state'],'waveformConditions':len(prepared),'newSeparationCalls':0,'newModelFamilies':0,'roots':roots},ensure_ascii=False),flush=True)
