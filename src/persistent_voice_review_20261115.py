"""One fixed acoustic review of complete-meeting native speaker identities.

Only clean predicted single-speaker activity supplies voice profiles. Existing
ERes2Net weights, bounded clips and saved vectors prevent lost work or global
quadratic clustering. No transcript/reference/person count enters inference.
"""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import argparse,hashlib,json,os,time,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from companion_local_pcm_session_20261114 import atomic_json,exclusive_file
from companion_windows_power_request_20261115 import PowerLease

read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def clean_runs(rows):
    events=defaultdict(list)
    for i,row in enumerate(rows):
        events[row['start']].append((i,True));events[row['end']].append((i,False))
    active=set();last=0.;runs=[]
    for t,updates in sorted(events.items()):
        if t>last and len(active)==1:
            spk=rows[next(iter(active))]['speaker']
            if runs and runs[-1]['end']==last and runs[-1]['speaker']==spk:runs[-1]['end']=t
            else:runs.append({'start':last,'end':t,'speaker':spk})
        for i,start in updates:
            if start:active.add(i)
            else:active.remove(i)
        last=t
    return runs

POLICY={
 'minimumCleanQuerySeconds':2.,'minimumCleanProfileSeconds':3.,'maximumClipSeconds':10.,
 'profileReferences':3,'profileSelection':'First three chronological predicted clean intervals per native ID; keep these enrollment intervals unchanged',
 'profileVector':'Mean of unit-normalized vectors, normalized again; frozen for the complete meeting with no eviction',
 'reassignment':'Original profile cosine distance >=0.5 AND exactly one other profile cosine distance <0.5; otherwise retain original anonymous ID',
 'distanceThreshold':.5,'shortOrAmbiguousIntervals':'Retain original native labels; do not infer missing speech or second overlapping voice',
 'unchanged':'All original audio, text, original activity boundaries and speaker activity multiplicity; no time or threshold sweep',
 'stopRule':'One fixed complete development run; retain failure without automatic variants. Promote only after full new+old ordinary DER<=10% and per-person regression checks',
 'scope':'Research identity review only; existing fixed original diarizer and evidence remain available; not a trained diarization model'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    control=a.control;protocol=read(control/'protocol.json');assert protocol['policy']==POLICY
    assert protocol['workerSha256']==sha(__file__)
    cases=read(control/'audio-only.json');limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
    pressure=SystemRamPressure()
    import numpy as np
    import sherpa_onnx
    assert sherpa_onnx.__version__=='1.13.4'
    with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')),PowerLease():
        assert sha(protocol['embeddingModel'])==protocol['embeddingSha256']
        config=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=protocol['embeddingModel'],num_threads=1,provider='cpu')
        assert config.validate();extractor=sherpa_onnx.SpeakerEmbeddingExtractor(config)
        for case in cases:
            assert not any('reference' in k.lower() for k in case)
            assert sha(case['audio'])==case['audioSha256'] and sha(case['journal'])==case['journalSha256']
            source=read(case['journal']);assert source['audioSha256']==case['audioSha256']
            out=control/'results'/case['meeting'];out.mkdir(parents=True,exist_ok=True)
            assert a.resume or not (out/'state.json').exists(),'Explicit resume required; retain prior state'
            cache=out/'vectors';cache.mkdir(exist_ok=True)
            journal=source['segments'];runs=[x for x in clean_runs(journal) if x['end']-x['start']>=2.]
            profiles=defaultdict(list)
            for i,run in enumerate(runs):
                if run['end']-run['start']>=3. and len(profiles[run['speaker']])<3:profiles[run['speaker']].append(i)
            enroll={i for values in profiles.values() for i in values}
            plan={'sourceJournalSha256':case['journalSha256'],'policy':POLICY,'runs':runs,'profileIndices':dict(profiles)}
            if (out/'input-plan.json').exists():assert read(out/'input-plan.json')==json.loads(json.dumps(plan))
            else:atomic_json(out/'input-plan.json',plan)
            state={'state':'RUNNING_PERSISTENT_VOICE_REVIEW','startedAt':datetime.now().astimezone().isoformat(),
                'meeting':case['meeting'],'newNeuralCalls':0,'reusedVectors':0,'plannedVectors':len(runs),
                'referencePassedToInference':False,'expectedSpeakerCountUsed':False,'qualityQualified':False}
            def save():state['limits']=limits.query();atomic_json(out/'state.json',state)
            save();vectors=[];started=time.perf_counter()
            try:
                with wave.open(case['audio'],'rb') as audio:
                    assert (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())==(1,2,16000)
                    for i,run in enumerate(runs):
                        assert not pressure.low(),'Actual Windows low-memory signal'
                        assert not (control/'stop.request').exists(),'Owned stop requested'
                        lo=round(run['start']*16000);hi=round(run['end']*16000)
                        if hi-lo>160000:lo=(lo+hi-160000)//2;hi=lo+160000
                        audio.setpos(lo);pcm=audio.readframes(hi-lo);assert len(pcm)==(hi-lo)*2
                        binding={'inputPlanSha256':sha(out/'input-plan.json'),'embeddingSha256':protocol['embeddingSha256'],
                            'runtimeVersion':sherpa_onnx.__version__,'startSample':lo,'endSample':hi,
                            'pcmSha256':hashlib.sha256(pcm).hexdigest()}
                        path=cache/(str(i).zfill(6)+'.json')
                        if path.exists():
                            row=read(path);assert row['binding']==binding;vector=np.asarray(row['vector'],dtype=np.float32);state['reusedVectors']+=1
                        else:
                            stream=extractor.create_stream();stream.accept_waveform(16000,np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768.)
                            stream.input_finished();assert extractor.is_ready(stream),'Predicted clean clip produced no ready voice vector'
                            vector=np.asarray(extractor.compute(stream),dtype=np.float32)
                            assert vector.ndim==1 and np.isfinite(vector).all() and np.linalg.norm(vector)>0
                            atomic_json(path,{'binding':binding,'vector':vector.tolist()});state['newNeuralCalls']+=1
                        vector=vector/np.linalg.norm(vector);vectors.append(vector);state['completedVectors']=i+1;save()
                prototypes={}
                for spk,indices in profiles.items():
                    v=np.mean(np.stack([vectors[i] for i in indices]),axis=0);prototypes[spk]=v/np.linalg.norm(v)
                changes=[];decisions=[]
                for i,(run,vector) in enumerate(zip(runs,vectors)):
                    distances={spk:float(1-np.dot(vector,profile)) for spk,profile in prototypes.items()}
                    original=run['speaker'];passing=[s for s,d in distances.items() if s!=original and d<.5]
                    revised=original
                    if i not in enroll and original in distances and distances[original]>=.5 and len(passing)==1:revised=passing[0]
                    decisions.append({'run':i,'sourceSpeaker':original,'speaker':revised,'cosineDistances':distances,'enrollmentUnchanged':i in enroll})
                    if revised!=original:changes.append({**run,'speaker':revised,'sourceSpeaker':original})
                revised=[]
                for row in journal:
                    cuts=[c for c in changes if c['sourceSpeaker']==row['speaker'] and c['end']>row['start'] and c['start']<row['end']]
                    at=row['start']
                    for cut in cuts:
                        lo=max(row['start'],cut['start']);hi=min(row['end'],cut['end'])
                        if lo>at:revised.append({**row,'start':at,'end':lo})
                        revised.append({**row,'start':lo,'end':hi,'speaker':cut['speaker']});at=hi
                    if at<row['end']:revised.append({**row,'start':at})
                revised.sort(key=lambda r:(r['start'],r['end'],r['speaker']))
                assert abs(sum(x['end']-x['start'] for x in journal)-sum(x['end']-x['start'] for x in revised))<1e-7
                atomic_json(out/'decisions.json',{'decisions':decisions,'changes':changes,'originalAudioAndTextUnchanged':True})
                atomic_json(out/'speaker-journal.json',{**source,'segments':revised,'identityReviewPolicy':POLICY})
                (out/'predicted.rttm').write_text(''.join(f"SPEAKER {case['meeting']} 1 {r['start']:.9f} {r['end']-r['start']:.9f} <NA> <NA> speaker_{r['speaker']} <NA> <NA>\n" for r in revised),encoding='utf-8')
                state.update(state='COMPLETE_FIXED_PERSISTENT_VOICE_REVIEW_NOT_QUALITY_QUALIFIED',changedIntervals=len(changes),
                    changedSpeakerSeconds=sum(x['end']-x['start'] for x in changes),newIdentityCount=len({r['speaker'] for r in revised}),
                    elapsedSeconds=time.perf_counter()-started,outputSha256=sha(out/'speaker-journal.json'))
            except BaseException as error:state.update(state='INCOMPLETE_VECTORS_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error));raise
            finally:save()
            print(json.dumps(state,ensure_ascii=False),flush=True)
    pressure.close()

if __name__=='__main__':main()
