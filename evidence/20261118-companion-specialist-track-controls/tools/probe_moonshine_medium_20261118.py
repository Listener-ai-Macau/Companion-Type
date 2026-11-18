"""Run one publisher-native English CPU candidate on the unchanged comparison audio."""
from contextlib import ExitStack
from datetime import datetime, timezone, timedelta
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import threading
import time
import types
import wave

project = Path('C:/Users/Billy/Desktop/Denzic/Companion')
sys.path.insert(0, str(project / 'model-research/src'))
from companion_local_pcm_session_20261114 import exclusive_file, SessionConflict
from durable_model_state_20261117 import atomic_json
from moss_windows_resource_limits_20261104 import SystemRamPressure, WorkerLimits
from meeting_acoustic_worker_20261116 import own_limits

parser=argparse.ArgumentParser()
parser.add_argument('phase',choices=['prepare','execute','score'])
args=parser.parse_args()
limits=own_limits(25) if args.phase=='execute' else WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
asset=Path('E:/CodexData/Companion/.model-cache/moonshine-voice-0.1.6-reference20261118')
root=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
run=root/'moonshine-english-medium-reference-r2'
protocol=root/'moonshine-english-medium-reference-protocol-r2.json'
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

if args.phase=='prepare':
    prev=read(root/'selected-cpu-segmentation-protocol-r1.json')
    model=read(asset/'model-acquisition-completed.json')
    assert model['modelArch']==5 and len(model['files'])==8
    runtime=asset/'runtime/moonshine_voice'
    control=runtime/'assets/two_cities.wav'
    P=dict(state='FROZEN_PUBLISHER_NATIVE_ENGLISH_CPU_REFERENCE',at=now(),workerSha256=sha(__file__),
           modelPath=model['modelPath'],modelArch=5,modelFiles=model['files'],
           runtimeFiles=[dict(file=str(p),sha256=sha(p)) for p in sorted(runtime.iterdir()) if p.suffix in ('.py','.dll')],
           runtime='Moonshine Voice 0.1.6',modelRevision='quantized_26_11_02',
           cases=prev['cases'],originalReferences=prev['originalReferences'],publisherControl=str(control),publisherControlSha256=sha(control),
           maximumSeconds=360,maximumLeaseWaitSeconds=180,neuralLock=prev['neuralLock'],minimumAvailableBytes=prev['minimumAvailableBytes'],
           unchangedScreen=dict(maximumErrors=70,words=709,maximumPerMeeting={'ES2003b':46,'EN2001a':67}),
           scoreAfterInferenceOnly=True,trainingUpdates=0,qualityQualified=False,saleQualified=False)
    assert len(P['cases'])==12 and not protocol.exists()
    atomic_json(protocol,P)
    print(json.dumps({'state':P['state'],'cases':12,'modelRevision':P['modelRevision']}))
    raise SystemExit(0)

P=read(protocol)
assert sha(__file__)==P['workerSha256']
if args.phase=='score':
    from score_sequential_meetings_20261115 import measure
    complete=read(run/'completed.json')
    assert complete['state']=='PUBLISHER_NATIVE_CPU_REFERENCE_COMPLETE' and len(complete['completed'])==12
    refs={r['id']:r for r in read(P['originalReferences']) if r['role']=='validation' and r['language']=='English'}
    assert set(refs)=={c['id'] for c in P['cases']}
    rows=[]
    for entry in complete['completed']:
        assert sha(entry['file'])==entry['sha256']
        packet=read(entry['file']);ref=refs[packet['id']]
        assert packet['audioSha256']==ref['wavSha256'] and packet['frames']==ref['frames']
        assert packet['protocolSha256']==sha(protocol) and not packet['wordsPostEdited']
        result=measure(ref['rawReferenceText'],packet['text'],'English')
        rows.append(dict(id=packet['id'],meeting=ref['meeting'],emptyOutput=not packet['text'].strip(),seconds=packet['seconds'],audioSeconds=packet['frames']/16000,
                    **{k:result[k] for k in ['errors','referenceUnits','substitutions','deletions','insertions']}))
    words=sum(r['referenceUnits'] for r in rows);errors=sum(r['errors'] for r in rows)
    seconds=sum(r['seconds'] for r in rows);audio=sum(r['audioSeconds'] for r in rows)
    meetings={name:sum(r['errors'] for r in rows if r['meeting']==name) for name in {r['meeting'] for r in rows}}
    gate=P['unchangedScreen'];assert words==gate['words']
    passed=errors<=gate['maximumErrors'] and all(meetings[n]<=v for n,v in gate['maximumPerMeeting'].items())
    value=dict(state='ENGLISH_REFERENCE_SCREEN_PASS_INDEPENDENT_COMPLETE_MEETING_PENDING' if passed else 'ENGLISH_REFERENCE_SCREEN_FAILED_NO_VARIANT_GRID',
               at=now(),errors=errors,referenceWords=words,wer=errors/words,meetings=meetings,
               emptyOutputs=sum(r['emptyOutput'] for r in rows),inferenceSeconds=seconds,rtf=seconds/audio,
               privatePeakBytes=complete['limits']['jobPeakPrivateCommitBytes'],publisherControl=complete['publisherControl'],
               screenPassed=passed,trainingUpdates=0,qualityQualified=False,saleQualified=False,cases=rows)
    output=run/'score.json';assert not output.exists();atomic_json(output,value)
    print(json.dumps({k:v for k,v in value.items() if k!='cases'}));raise SystemExit(0)

run.mkdir(exist_ok=False)
state=dict(state='WAITING_FOR_SHARED_MODEL_LEASE',at=now(),pid=os.getpid(),completed=[],newInferenceCalls=0,trainingUpdates=0)
done=threading.Event();pressure=SystemRamPressure()

def save(**values):
    state.update(values,observedAt=now(),limits=limits.query())
    atomic_json(run/'state.json',state,progress=True)

def monitor(start):
    import psutil
    while not done.wait(.5):
        if pressure.low() or psutil.virtual_memory().available<P['minimumAvailableBytes'] or time.monotonic()-start>P['maximumSeconds']:
            save(state='PUBLISHER_CPU_REFERENCE_STOPPED_AT_RESOURCE_OR_TIME_BOUNDARY')
            atomic_json(run/'completed.json',state);os._exit(76)

try:
    save()
    with ExitStack() as stack:
        deadline=time.monotonic()+P['maximumLeaseWaitSeconds']
        while True:
            try:
                stack.enter_context(exclusive_file(Path(P['neuralLock'])))
                break
            except SessionConflict:
                if time.monotonic()>=deadline:raise
                time.sleep(2)
        start=time.monotonic();threading.Thread(target=monitor,args=(start,),daemon=True).start()
        save(state='LOADING_PUBLISHER_NATIVE_CPU_MODEL')
        os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='-1',HIP_VISIBLE_DEVICES='-1')
        for item in P['runtimeFiles']+P['modelFiles']:
            assert sha(item['file'])==item['sha256']
        # Load the publisher's file-only bindings without importing its microphone UI.
        pkg=types.ModuleType('moonshine_voice');pkg.__path__=[str(asset/'runtime/moonshine_voice')]
        sys.modules['moonshine_voice']=pkg
        from moonshine_voice.moonshine_api import ModelArch
        from moonshine_voice.transcriber import Transcriber
        from moonshine_voice.utils import load_wav_file
        import numpy as np
        with Transcriber(model_path=P['modelPath'],model_arch=ModelArch.MEDIUM_STREAMING) as engine:
            assert sha(P['publisherControl'])==P['publisherControlSha256']
            samples,rate=load_wav_file(P['publisherControl'])
            state['newInferenceCalls']+=1
            probe=engine.transcribe_without_streaming(samples,sample_rate=rate,flags=0)
            probe_text=' '.join(x.text for x in probe.lines)
            save(state='PUBLISHER_CONTROL_OUTPUT',publisherControl={'text':probe_text,'nonempty':bool(probe_text.strip()),'sha256':P['publisherControlSha256']})
            assert 'best of times' in probe_text.lower() and 'worst of times' in probe_text.lower()
            for row in P['cases']:
                assert sha(row['audio'])==row['audioSha256']
                with wave.open(row['audio'],'rb') as wav:
                    assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())==(1,2,16000,row['frames'])
                    pcm=wav.readframes(row['frames'])
                assert hashlib.sha256(pcm).hexdigest()==row['pcmSha256']
                audio=(np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768).tolist()
                tick=time.perf_counter();state['newInferenceCalls']+=1
                transcript=engine.transcribe_without_streaming(audio,sample_rate=16000,flags=0)
                text=' '.join(line.text for line in transcript.lines)
                packet=dict(id=row['id'],audioSha256=row['audioSha256'],frames=row['frames'],text=text,
                            lines=len(transcript.lines),seconds=time.perf_counter()-tick,protocolSha256=sha(protocol),wordsPostEdited=False)
                file=run/(row['id']+'.json');atomic_json(file,packet)
                state['completed'].append(dict(file=str(file),sha256=sha(file)));save(state='DECODING_ORIGINAL_ENGLISH_INPUTS',activeCase=row['id'])
        save(state='PUBLISHER_NATIVE_CPU_REFERENCE_COMPLETE',seconds=time.monotonic()-start)
        atomic_json(run/'completed.json',state)
        print(json.dumps(dict(state=state['state'],cases=len(state['completed']),seconds=state['seconds'])))
except BaseException as error:
    save(state='PUBLISHER_NATIVE_CPU_REFERENCE_FAILED_RETAINED',error=repr(error));atomic_json(run/'completed.json',state);raise
finally:
    done.set();pressure.close()
