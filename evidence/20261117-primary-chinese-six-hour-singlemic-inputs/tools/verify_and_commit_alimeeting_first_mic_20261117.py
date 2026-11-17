"""Independently compare every existing mono byte with a pinned original source."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,sys,time,wave
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from durable_model_state_20261117 import atomic_json
from alimeeting_public_oss_20261117 import PublicAliTrainingStore
import psutil
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
O=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1/alimeeting-official-intake-r2')
root=O/'first-mic-source-r1';out=root/'post-source-check-r2';out.mkdir()
partial=root/'R0003_M0046.channel0.wav.partial';target=root/'R0003_M0046.channel0.wav'
assert partial.is_file() and not target.exists() and partial.resolve().parent==target.resolve().parent==root.resolve()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
prior=read(root/'state.json');head=read(O/'first-official-wave-object.json');header=(O/'first-official-wave-header.bin').read_bytes()
assert prior['downloadedSourceBytes']==523745616 and prior['writtenMonoFrames']==32734096 and 'Bad file descriptor' in prior['error']
state={'at':datetime.now().astimezone().isoformat(),'state':'VERIFYING_EXISTING_MONO_AGAINST_ORIGINAL_ALL_CHANNEL_SOURCE',
    'sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'sourceFile':head['file'],
    'sourceExpectedBytes':head['bytes'],'sourceExpectedMd5':head['etag'].lower(),'comparedFrames':0,'sourceBytesRead':0,
    'conversionRepeated':False,'neuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'trainingAdmitted':False}
def save():
    state.update(observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
    atomic_json(out/'state.json',state,progress=True)
pressure=SystemRamPressure();began=time.monotonic();source_sha=hashlib.sha256();source_md5=hashlib.md5();mono_sha=hashlib.sha256();save()
def stop():
    assert not pressure.low() and psutil.virtual_memory().available>=3414499000,'Original RAM floor'
    assert shutil.disk_usage(out).free>=50*1024**3,'Original free-space reserve'
    assert time.monotonic()-began<600 and not(out/'stop.request').exists(),'Bounded verification cutoff'
try:
    store=PublicAliTrainingStore(O/'Train_Ali_far.csv')
    with store.open(head['file']) as response,wave.open(str(partial),'rb') as mono:
        assert response.status==200 and int(response.headers['Content-Length'])==head['bytes']
        assert response.headers['ETag'].strip('"').lower()==head['etag'].lower(),'Pinned source object changed'
        assert (mono.getnchannels(),mono.getsampwidth(),mono.getframerate(),mono.getnframes())==(1,2,16000,32734096)
        def read_exact(count):
            chunks=[];remaining=count
            while remaining:
                stop();raw=response.read(remaining);assert raw,'Truncated verification source'
                chunks.append(raw);remaining-=len(raw)
            raw=b''.join(chunks);source_sha.update(raw);source_md5.update(raw);state['sourceBytesRead']+=len(raw);return raw
        assert read_exact(80)==header
        remaining=head['bytes']-80;last_save=0
        while remaining:
            raw=read_exact(min(1024**2,remaining));assert len(raw)%16==0;frames=len(raw)//16
            actual=mono.readframes(frames);assert len(actual)==frames*2
            assert actual[0::2]==raw[0::16] and actual[1::2]==raw[1::16],'Existing mono file differs from exact first-source channel'
            mono_sha.update(actual);state['comparedFrames']+=frames;remaining-=len(raw)
            if state['sourceBytesRead']-last_save>=16*1024**2:save();last_save=state['sourceBytesRead']
        assert not mono.readframes(1) and not response.read(1)
    assert state['comparedFrames']==32734096 and state['sourceBytesRead']==head['bytes']
    assert source_md5.hexdigest()==head['etag'].lower(),'Full official waveform content MD5 differs'
    state.update(sourceFullSha256=source_sha.hexdigest(),sourceFullMd5=source_md5.hexdigest(),monoPcmSha256=mono_sha.hexdigest(),
        everyMonoByteComparedWithRawSourceChannel=True,state='VERIFIED_SOURCE_AND_EXISTING_MONO_LOCAL_COMMIT_PENDING');save()
    with partial.open('r+b') as stream:stream.flush();os.fsync(stream.fileno())
    os.replace(partial,target)
    with target.open('rb') as stream:output_sha=hashlib.file_digest(stream,'sha256').hexdigest()
    state.update(state='COMPLETE_FIRST_MIC_RAW_SOURCE_AND_MONO_ALL_FRAMES_VERIFIED_COMMITTED',output=str(target),
        outputSha256=output_sha,outputBytes=target.stat().st_size,audioSeconds=32734096/16000,
        selectedChannel=0,sourceChannels=8,sampleRate=16000,sourceBits=16,
        noResamplingGainChannelAverageOrTailDeletion=True,elapsedSeconds=time.monotonic()-began,
        originalFailureAndConverterRetained=True,fullSourceDigestCapturedByIndependentVerifier=True)
    save();atomic_json(out/'completed.json',state)
except BaseException as error:state.update(state='FAILED_EXISTING_MONO_VERIFICATION_RETAINED',error=repr(error));save();raise
finally:pressure.close()
print(json.dumps(state,ensure_ascii=False))
