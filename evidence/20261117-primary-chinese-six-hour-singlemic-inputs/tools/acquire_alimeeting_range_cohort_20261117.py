"""Acquire the frozen6h original train utterances as exact first-mic PCM clips."""
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import hashlib,json,os,shutil,sys,time,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from durable_model_state_20261117 import atomic_json
from alimeeting_public_oss_20261117 import PublicAliTrainingStore
import numpy as np,psutil
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
O=E/'alimeeting-official-intake-r2';C=O/'range-training-cohort-r2';P=json.loads((C/'protocol.json').read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for item in P['dependencies']:assert sha(item['file'])==item['sha256'],'Frozen data acquisition dependency changed'
assert sha(P['selectedManifest'])==P['selectedManifestSha256']
rows=[json.loads(l) for l in Path(P['selectedManifest']).read_text(encoding='utf-8').splitlines()]
assert len(rows)==P['examples']==5027 and sum(r['frames'] for r in rows)==P['frames']
split=json.loads(Path(P['participantProof']).read_text(encoding='utf-8'))
assert not split['intersection']
assert all(r['role']=='train-only' and r['language']=='Chinese' and r['sourceSpeakerId'] in split['trainingGlobalSpeakerIds'] for r in rows)
first=P['existingVerifiedFirstMono'];assert sha(first['output'])==first['outputSha256']
out=C/'acquisition-r1';out.mkdir();(out/'clips').mkdir();(out/'receipts').mkdir()
state={'at':datetime.now().astimezone().isoformat(),'state':'ACQUIRING_FROZEN5027_ORIGINAL_CHINESE_TRAIN_CLIPS',
    'sourceSha256':sha(__file__),'protocolSha256':sha(C/'protocol.json'),'completedExamples':0,
    'completedAudioFrames':0,'downloadedRawRangeBytes':0,'writtenClipBytes':0,'reusedVerifiedMonoExamples':0,
    'ioThreads':4,'automaticRetries':0,'credentialsPrintedOrPersisted':False,
    'newNeuralCalls':0,'parameterUpdates':0,'trainingAdmitted':False,'qualityQualified':False}
pressure=SystemRamPressure();began=time.monotonic();last_save=0.;last_print=0
def save():
    state.update(observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
    atomic_json(out/'state.json',state,progress=True)
def stop():
    assert not pressure.low() and psutil.virtual_memory().available>=P['minimumAvailableBytes'],'Original RAM floor'
    assert shutil.disk_usage(out).free>=P['minimumDiskFreeBytes'],'Original disk reserve'
    assert time.monotonic()-began<3600 and not(out/'stop.request').exists(),'Bounded source acquisition cutoff'
save()
try:
    store=PublicAliTrainingStore(O/'Train_Ali_far.csv')
    def acquire(row):
        stop();source=P['sourceCatalog'][row['meeting']];header=source['header'];frames=row['frames']
        assert 32000<=frames<=480000 and row['endFrame']-row['startFrame']==frames
        assert 0<=row['startFrame']<row['endFrame']<=header['frames'] and header['channels']==8 and header['bits']==16
        if row['meeting']=='R0003_M0046':
            with wave.open(first['output'],'rb') as stream:
                stream.setpos(row['startFrame']);pcm=stream.readframes(frames)
            raw_bytes=0;raw_hash=None;byte_range=None;provenance='Previously independently byte-verified full original first-mic source'
        else:
            start=header['dataOffset']+row['startFrame']*16;end=start+frames*16-1
            raw=store.range_bytes(source['file'],start,end,source['objectBytes'],source['etag'])
            samples=np.frombuffer(raw,dtype='<i2').reshape(-1,8);pcm=samples[:,0].tobytes()
            assert pcm[0::2]==raw[0::16] and pcm[1::2]==raw[1::16],'Wrong channel, byteorder, or modified PCM'
            raw_bytes=len(raw);raw_hash=hashlib.sha256(raw).hexdigest();byte_range=[start,end]
            provenance='Exact original public object range, conditionalETag andContentRange checked; every emitted byte checked against channel0'
        assert len(pcm)==frames*2
        folder=out/'clips'/row['meeting'];folder.mkdir(exist_ok=True)
        target=folder/(row['id']+'.wav');partial=target.with_suffix('.wav.partial')
        assert not target.exists() and not partial.exists()
        assert partial.resolve().parent==target.resolve().parent==folder.resolve()
        with wave.open(str(partial),'wb') as stream:
            stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(16000);stream.writeframes(pcm)
        pcm_hash=hashlib.sha256(pcm).hexdigest()
        with wave.open(str(partial),'rb') as stream:
            assert (stream.getnchannels(),stream.getsampwidth(),stream.getframerate(),stream.getnframes())==(1,2,16000,frames)
            assert hashlib.sha256(stream.readframes(frames)).hexdigest()==pcm_hash,'Written clip PCM changed'
        with partial.open('r+b') as stream:stream.flush();os.fsync(stream.fileno())
        os.replace(partial,target)
        receipt={'id':row['id'],'meeting':row['meeting'],'role':'train-only','language':'Chinese',
            'audio':str(target),'audioSha256':sha(target),'pcmSha256':pcm_hash,'frames':frames,
            'sourceStartFrame':row['startFrame'],'sourceEndFrame':row['endFrame'],'sourceSpeakerId':row['sourceSpeakerId'],
            'sourceOriginalTextgridSha256':row['sourceTextgridSha256'],'sourceTextSha256':hashlib.sha256(row['text'].encode()).hexdigest(),
            'sourceFile':source['file'],'sourceObjectEtag':source['etag'],'sourceObjectBytes':source['objectBytes'],
            'sourceRawByteRange':byte_range,'sourceRawRangeSha256':raw_hash,'rawBytesFetched':raw_bytes,
            'outputBytes':target.stat().st_size,'selectedChannel':0,'sampleRate':16000,'sampleWidth':2,
            'provenance':provenance,'allOriginalUtteranceFramesRetained':True,'textOrTimeEdited':False,
            'newNeuralCalls':0,'parameterUpdates':0}
        atomic_json(out/'receipts'/(row['id']+'.json'),receipt);return receipt
    todo=iter(rows);pending={};completed={}
    with ThreadPoolExecutor(max_workers=4) as executor:
        def submit():
            row=next(todo,None)
            if row is not None:pending[executor.submit(acquire,row)]=row['id']
        for _ in range(4):submit()
        while pending:
            stop();finished,_=wait(pending,timeout=1,return_when=FIRST_COMPLETED)
            for future in finished:
                uid=pending.pop(future);receipt=future.result();completed[uid]=receipt
                state['completedExamples']+=1;state['completedAudioFrames']+=receipt['frames']
                state['downloadedRawRangeBytes']+=receipt['rawBytesFetched'];state['writtenClipBytes']+=receipt['outputBytes']
                state['reusedVerifiedMonoExamples']+=int(receipt['rawBytesFetched']==0)
                assert state['downloadedRawRangeBytes']<=P['budget']['plannedNewRawRangeBytes']
                if time.monotonic()-last_save>=2:save();last_save=time.monotonic()
                if state['completedExamples']-last_print>=256:
                    print(json.dumps({k:state[k] for k in ['completedExamples','completedAudioFrames','downloadedRawRangeBytes']}) ,flush=True)
                    last_print=state['completedExamples']
                submit()
    assert len(completed)==P['examples'] and state['completedAudioFrames']==P['frames']
    assert state['downloadedRawRangeBytes']==P['budget']['plannedNewRawRangeBytes']
    manifest=out/'chinese-train-original-nonoverlap.jsonl'
    with manifest.open('x',encoding='utf-8') as stream:
        for row in rows:
            receipt=completed[row['id']]
            stream.write(json.dumps({**row,'audio':receipt['audio'],'audioSha256':receipt['audioSha256'],
                'pcmSha256':receipt['pcmSha256'],'acquisitionReceipt':str(out/'receipts'/(row['id']+'.json'))},ensure_ascii=False)+'\n')
        stream.flush();os.fsync(stream.fileno())
    assert 'torch' not in sys.modules,'Data acquisition imported a neural runtime'
    owned=sum(p.stat().st_size for p in E.rglob('*') if p.is_file());assert owned<=P['maximumOwnedNewDataBytes']
    state.update(state='COMPLETE5027_ORIGINAL_SINGLE_MIC_CHINESE_TRAIN_INPUTS_PENDING_INDEPENDENT_INTEGRITY',
        manifest=str(manifest),manifestSha256=sha(manifest),audioSeconds=P['frames']/16000,
        actualOwnedDataBytes=owned,elapsedSeconds=time.monotonic()-began,modelInstances=0)
    save();atomic_json(out/'completed.json',state)
except BaseException as error:state.update(state='FAILED_ORIGINAL_CHINESE_RANGE_ACQUISITION_RETAINED_NO_RETRY',error=repr(error));save();raise
finally:pressure.close()
print(json.dumps(state,ensure_ascii=False))
