"""Stream one pinned original8ch recording into exact first-mic PCM, without mixing."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,struct,sys,time,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from durable_model_state_20261117 import atomic_json
from alimeeting_public_oss_20261117 import PublicAliTrainingStore
import numpy as np,psutil
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
data_root=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
O=data_root/'alimeeting-official-intake-r2';out=O/'first-mic-source-r1';out.mkdir()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
head=read(O/'first-official-wave-object.json');control=read(O/'first-original-vs-converted.json')
assert control['rawTextAndTimeMissing']==control['rawTextAndTimeExtra']==0
assert control['allSourceFrameIntervalsMatch'] and control['allOriginalSpeakerIdsMatchOfficialNearFiles']
source_path='Train_Ali_far/audio_dir/R0003_M0046_MS002.wav';assert head['file']==source_path
expected_bytes=523745616;expected_frames=32734096;expected_data=expected_frames*16
assert head['bytes']==expected_bytes and expected_bytes==80+expected_data
header=(O/'first-official-wave-header.bin').read_bytes();assert len(header)==80
current_bytes=sum(p.stat().st_size for p in data_root.rglob('*') if p.is_file())
assert current_bytes+expected_bytes+expected_frames*2+44<12*1024**3,'Original new-data budget'
assert shutil.disk_usage(out).free>=50*1024**3+expected_frames*2+44,'Original free-space reserve'
target=out/'R0003_M0046.channel0.wav';partial=target.with_suffix('.wav.partial');assert not target.exists() and not partial.exists()
state={'at':datetime.now().astimezone().isoformat(),'state':'STREAMING_ORIGINAL_TRAIN_WAVE_TO_FIRST_MIC',
    'sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'helperSha256':hashlib.sha256(Path(__file__).with_name('alimeeting_public_oss_20261117.py').read_bytes()).hexdigest(),
    'sourceFile':source_path,'sourceObject':head,'selectedChannelIndex':0,'sourceChannels':8,
    'sampleRate':16000,'sourceFrames':expected_frames,'downloadedSourceBytes':0,'writtenMonoFrames':0,
    'currentOwnedDataBytes':current_bytes,'originalNewDataBudgetBytes':12*1024**3,'minimumFreeBytes':50*1024**3,
    'allOutputBytesIndependentlyComparedWithRawChannelBytePositions':False,
    'noResamplingOrGainOrChannelAverage':True,'neuralCalls':0,'parameterUpdates':0,
    'trainingAdmitted':False,'qualityQualified':False}
def save():
    state.update(observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
    atomic_json(out/'state.json',state,progress=True)
pressure=SystemRamPressure();began=time.monotonic();raw_sha=hashlib.sha256();raw_md5=hashlib.md5();pcm_sha=hashlib.sha256();save()
def stop():
    assert not pressure.low() and psutil.virtual_memory().available>=3414499000,'Original RAM guard'
    assert shutil.disk_usage(out).free>=50*1024**3,'Original disk reserve'
    assert time.monotonic()-began<600,'Bounded single-source transfer deadline'
    assert not(out/'stop.request').exists(),'Owned source transfer stop requested'
try:
    store=PublicAliTrainingStore(O/'Train_Ali_far.csv');stop()
    with store.open(source_path) as response,wave.open(str(partial),'wb') as mono:
        assert response.status==200 and int(response.headers['Content-Length'])==expected_bytes
        assert response.headers['ETag'].strip('"').lower()==head['etag'].lower(),'Pinned official audio object changed'
        def read_exact(count):
            parts=[];remaining=count
            while remaining:
                stop();value=response.read(remaining);assert value,'Truncated original audio response'
                parts.append(value);remaining-=len(value)
            value=b''.join(parts);raw_sha.update(value);raw_md5.update(value);state['downloadedSourceBytes']+=len(value)
            return value
        assert read_exact(80)==header,'Official audio header differs from pinned archive/object pair'
        mono.setnchannels(1);mono.setsampwidth(2);mono.setframerate(16000)
        remaining=expected_data;last_save=0
        while remaining:
            raw=read_exact(min(1024**2,remaining));assert len(raw)%16==0
            samples=np.frombuffer(raw,dtype='<i2').reshape(-1,8);selected=samples[:,0].tobytes()
            assert selected[0::2]==raw[0::16] and selected[1::2]==raw[1::16], 'EmittedPCM differs from selected raw channel'
            mono.writeframesraw(selected);pcm_sha.update(selected);state['writtenMonoFrames']+=len(selected)//2
            remaining-=len(raw)
            if state['downloadedSourceBytes']-last_save>=16*1024**2:save();last_save=state['downloadedSourceBytes']
        assert not response.read(1),'Original response has unexpected trailing bytes'
    assert state['downloadedSourceBytes']==expected_bytes and state['writtenMonoFrames']==expected_frames
    assert raw_md5.hexdigest()==head['etag'].lower(),'Full original eight-channel waveform MD5 differs'
    with wave.open(str(partial),'rb') as check:
        assert (check.getnchannels(),check.getsampwidth(),check.getframerate(),check.getnframes())==(1,2,16000,expected_frames)
        verification=hashlib.sha256()
        while chunk:=check.readframes(262144):verification.update(chunk)
        assert verification.hexdigest()==pcm_sha.hexdigest(),'Written monoPCM differs from streaming selection'
    with partial.open('rb') as stream:os.fsync(stream.fileno())
    os.replace(partial,target)
    with target.open('rb') as stream:full_sha=hashlib.file_digest(stream,'sha256').hexdigest()
    state.update(state='COMPLETE_ORIGINAL_PUBLIC_FIRST_MIC_ALL_FRAMES_BYTE_VERIFIED',output=str(target),
        outputBytes=target.stat().st_size,outputSha256=full_sha,monoPcmSha256=pcm_sha.hexdigest(),
        fullOriginalEightChannelWaveSha256=raw_sha.hexdigest(),fullOriginalEightChannelWaveMd5=raw_md5.hexdigest(),
        allOutputBytesIndependentlyComparedWithRawChannelBytePositions=True,
        fullOriginalAudioFramesRetained=True,audioSeconds=expected_frames/16000,
        originalEightChannelWavePersisted=False,elapsedSeconds=time.monotonic()-began)
    save();atomic_json(out/'completed.json',state)
except BaseException as error:state.update(state='FAILED_OFFICIAL_FIRST_MIC_ACQUISITION_PARTIAL_RETAINED',error=repr(error));save();raise
finally:pressure.close()
print(json.dumps(state,ensure_ascii=False))
