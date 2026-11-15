"""Freeze real same-meeting two-channel and codec controls before inference."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,wave,urllib.request
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_gss_numpy_backend_20261108 import prepare_backend
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery'
C=R/'docs/handoffs/20261108-dual-mic-real-meeting-validation';E=Path('E:/CodexData/Companion/.model-cache/dual-mic-real-meeting-20261108')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
E.mkdir(parents=True,exist_ok=True);assert not (C/'audio-preparation.json').exists()
sys.path.append('E:/CodexData/Companion/.model-cache/audio-tools');import soundfile as sf
import numpy as np
revision='aada72727856313b19d4a030383c426364931dbf'
url='https://huggingface.co/api/datasets/AISHELL/AISHELL-4/tree/'+revision+'/test/wav'
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-bounded-dual-mic-data-check'}),timeout=20) as f:tree=json.load(f)
sources=[]
for meeting in ['L_R003S01C02','S_R004S03C01']:
    file=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031')/(meeting+'.flac')
    remote=next(r for r in tree if r['path']=='test/wav/'+file.name)
    assert file.stat().st_size==remote['size'] and sha(file)==remote['lfs']['oid']
    sources.append({'meeting':meeting,'losslessSource':str(file),'losslessSourceSha256':sha(file),
        'sourceWholePayloadMatchesPinnedLfs':True,'revision':revision,'microphoneChannelsUsed':[0,1],
        'sourceCollection':'AISHELL-4 original8channel shared recording; exactly2channels used in this screen.',
        'geometry':'Original adjacent channel indices0/1; exact port positions/order are not established by the loaded file. No claim this matches the recorder31.8mmestimate.'})

def write(file,array):
    assert not file.exists();array=np.ascontiguousarray(array,dtype='<i2')
    with wave.open(str(file),'wb') as f:
        f.setnchannels(array.shape[1] if array.ndim==2 else 1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(array.tobytes())
def load(file):
    with wave.open(str(file),'rb') as f:
        assert f.getframerate()==16000 and f.getsampwidth()==2
        return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,f.getnchannels())
ffmpeg=subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[:3]
clips=[]
for meeting,index,kind in [('L_R003S01C02',12,'previous-exposed-two'),('L_R003S01C02',27,'disclosed-reference-curated-triple'),('S_R004S03C01',1,'ordinary-regression')]:
    source=next(r for r in sources if r['meeting']==meeting);lo=max(0,index*480000-240000);hi=(index+1)*480000+240000
    key=meeting+'-root-%06d'%index;original=E/(key+'-raw-pair-context.wav')
    with sf.SoundFile(source['losslessSource']) as f:
        assert f.channels==8 and f.samplerate==16000 and f.subtype=='PCM_16'
        f.seek(lo);audio=f.read(hi-lo,dtype='int16',always_2d=True);assert audio.shape==(hi-lo,8)
    write(original,audio[:,:2]);assert np.array_equal(load(original),audio[:,:2])
    oldcase=next(r for r in read(B/'practical-target-activity-r1/audio-only.json') if r['meeting']==meeting and r['id'].endswith('%06d'%index)) if index!=27 else next(r for r in read(B/'practical-conditioned-ps4-full-r1/audio-only.json') if r['rootIndex']==27)
    offset=index*480000-lo;root=audio[offset:offset+480000,0]
    assert np.array_equal(load(oldcase['audio'])[:,0],root),'First-channel PCM differs from the fixed previous raw control'
    encoded=E/(key+'-stereo32k.opus');decoded=E/(key+'-stereo32k-decoded.wav')
    command=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n','-threads','1','-i',str(original),'-map_metadata','-1','-c:a','libopus','-application','lowdelay','-frame_duration','20','-compression_level','0','-b:a','32000','-vbr','off',str(encoded)]
    subprocess.run(command,check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n','-threads','1','-i',str(encoded),'-map_metadata','-1','-ar','16000','-ac','2','-c:a','pcm_s16le',str(decoded)],check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    lossy=load(decoded);assert lossy.shape==audio[:,:2].shape,'Decoded delay/sample count mismatch; no manual padding or time shift'
    # Author-supplied FLAC is lossless; verify a local roundtrip explicitly.
    lossless=E/(key+'-roundtrip.flac');sf.write(lossless,audio[:,:2],16000,format='FLAC',subtype='PCM_16')
    roundtrip,rate=sf.read(lossless,dtype='int16',always_2d=True);assert rate==16000 and np.array_equal(roundtrip,audio[:,:2])
    journal=B/('native8-f16-full-r1/results/'+meeting+'/speaker-journal.json');segments=read(journal)['segments']
    people=sorted({r['speaker'] for r in segments if r['end']>index*30 and r['start']<(index+1)*30})
    row={'id':key,'meeting':meeting,'rootIndex':index,'kind':kind,'audio':str(original),'audioSha256':sha(original),
        'compressedFile':str(encoded),'compressedSha256':sha(encoded),'compressedDecodedAudio':str(decoded),'compressedDecodedSha256':sha(decoded),
        'contextStartSample':lo,'contextEndSample':hi,'rootStartSample':index*480000,'rootEndSample':(index+1)*480000,
        'rootOffsetWithinContext':offset,'contextSeconds':(hi-lo)/16000,'previousMonoRootAudio':oldcase['audio'],'previousMonoRootSha256':oldcase['audioSha256'],
        'firstChannelPcmExactlyPreviousRoot':True,'flacPcmRoundtripExactlyEqual':True,
        'journal':str(journal),'journalSha256':sha(journal),'predictedRootPeople':people,
        'codecPcmNotBitIdentical':not np.array_equal(lossy,audio[:,:2]),
        'codecDifferenceRmsPerChannel':np.sqrt(np.mean((lossy.astype(np.float64)-audio[:,:2])**2,axis=0)).tolist(),
        'encodedCommand':command,'codecScope':'Host libopus32kbps stereo20msCBR lowdelay,complexity0; Ogg pre-skip/resampling handled by FFmpeg. This is a disclosed stereo compression control, not the current board mono CELT binary.'}
    clips.append(row)
atomic_json(C/'audio-only.json',clips)
backend=prepare_backend(C/'upstream-source.json',E/'numpy-reference');atomic_json(C/'numpy-backend.json',backend)
atomic_json(C/'audio-preparation.json',{'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'REAL_DUAL_PCM_AND_CODEC_INPUTS_FROZEN_NO_MODEL', 'sources':sources,'clips':len(clips),
    'uniqueOriginalRootSeconds':90,'newAudioDownloaded':False,'ffmpegVersion':ffmpeg,
    'sameRootChannel0PcmAsPriorTests':True,'losslessFlacPcmRoundtripVerified':True,
    'referenceGeometryNotMatchedToDevice':True,'newModels':0,'finalHoldoutOpened':False,'qualityQualified':False,'limits':limits.query()})
print(json.dumps({'state':'REAL_DUAL_PCM_AND_CODEC_INPUTS_FROZEN_NO_MODEL','clips':len(clips),'channelsUsed':2,'firstChannelExactlyPrevious':True,'flacBitIdentical':True,'opusIsLossy':True,'newAudioDownloaded':False}),flush=True)
