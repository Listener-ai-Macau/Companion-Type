"""Pinned public corpus I/O and exact microphone0 export, no neural runtime."""
from pathlib import Path
from datetime import datetime
import ctypes,hashlib,json,os,sys,time,urllib.request,wave
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
from practical_io_20261107 import atomic_json
import psutil,numpy as np,soundfile as sf
C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/meeting-domain-data-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1')
plan=json.loads((C/'plan.json').read_text(encoding='utf-8'));deadline=datetime.fromisoformat(plan['preparationDeadline'])
limits=WorkerLimits(cpu_percent=1,memory_bytes=plan['privateBytes']);rate=CpuRate(5,50)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
state={'state':'PREPARING_BROAD_PUBLIC_FARFIELD_DATA_NO_TRAINING','startedAt':datetime.now().astimezone().isoformat(),'completed':[],'failures':[],
 'downloadedBytes':0,'canonicalAudioBytes':0,'newNeuralCalls':0,'parameterUpdates':0,'trainingStarted':False,'qualityQualified':False,'soundfileVersion':sf.__version__,'libsndfileVersion':sf.__libsndfile_version__}
assert not (E/'run.json').exists()
def check():
 assert datetime.now().astimezone()<deadline,'Public data preparation deadline'
 assert psutil.disk_usage('E:/').free>plan['minimumDiskFreeBytes'],'Original data-storage free-space reserve'
 assert state['downloadedBytes']+state['canonicalAudioBytes']<plan['maximumNewDataBytes'],'Frozen data budget reached'
def save():state['limits']=limits.query();atomic_json(E/'run.json',state)
def fetch(url,target,expected=None):
 check();assert not target.exists();partial=target.with_suffix(target.suffix+'.partial');assert not partial.exists()
 tick=time.monotonic();last=0;digest=hashlib.sha256();count=0;headers={}
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-public-meeting-corpus/1.0'}),timeout=30) as response,partial.open('xb',buffering=65536) as output:
  headers={k:response.headers.get(k) for k in ['Content-Length','ETag','Last-Modified']}
  while True:
   check()
   if time.monotonic()-tick>240:raise TimeoutError('One bounded corpus transfer; partial bytes retained, no automatic retry')
   block=response.read(256*1024)
   if not block:break
   output.write(block);digest.update(block);count+=len(block);state['downloadedBytes']+=len(block)
   if expected:assert count<=expected['size']
   if time.monotonic()-last>10:save();last=time.monotonic()
  output.flush();os.fsync(output.fileno())
 if expected:
  assert count==expected['size']
  if expected.get('lfs'):assert digest.hexdigest()==expected['lfs']['sha256']
  else:
   h=hashlib.sha1();h.update(b'blob '+str(count).encode()+b'\0')
   with partial.open('rb') as f:
    while data:=f.read(65536):h.update(data)
   assert h.hexdigest()==expected['blobId']
 if headers['Content-Length']:assert count==int(headers['Content-Length'])
 partial.replace(target);return {'file':str(target),'sha256':digest.hexdigest(),'bytes':count,'url':url,'headers':headers,'publisherHashVerified':bool(expected),'seconds':time.monotonic()-tick}
save()
try:
 for entry in plan['sources']:
  check();folder=E/entry['meeting'];folder.mkdir();state['activeMeeting']=entry['meeting'];save()
  try:
   if entry['corpus']=='AISHELL-4':
    prefix='https://huggingface.co/datasets/AISHELL/AISHELL-4/resolve/'+entry['revision']+'/'
    reference=fetch(prefix+entry['referenceSource']['rfilename'],folder/'reference.TextGrid',entry['referenceSource'])
    original=fetch(prefix+entry['audioSource']['rfilename'],folder/'source.flac',entry['audioSource']);audio=folder/'microphone0.wav';pending=folder/'microphone0.pending.wav';frames=0;pcm_digest=hashlib.sha256()
    with sf.SoundFile(original['file']) as source,wave.open(str(pending),'wb') as output:
     assert source.samplerate==16000 and source.channels==8 and source.subtype=='PCM_16'
     expected_frames=len(source);output.setparams((1,2,16000,0,'NONE','not compressed'))
     while True:
      check();block=source.read(65536,dtype='int16',always_2d=True)
      if len(block)==0:break
      pcm=block[:,0].astype('<i2',copy=True).tobytes();output.writeframesraw(pcm);pcm_digest.update(pcm);frames+=len(block)
     assert frames==expected_frames
    pending.replace(audio);state['canonicalAudioBytes']+=audio.stat().st_size
   else:
    original=fetch(entry['url'],folder/'microphone0.wav');audio=Path(original['file']);reference={'archive':entry['annotationArchive'],'archiveSha256':entry['annotationArchiveSha256']}
    with wave.open(str(audio),'rb') as source:
     assert (source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getcomptype())==(1,2,16000,'NONE')
     frames=source.getnframes();pcm_digest=hashlib.sha256()
     while pcm:=source.readframes(32000):pcm_digest.update(pcm)
   item={'meeting':entry['meeting'],'language':entry['language'],'corpus':entry['corpus'],'role':entry['role'],'source':original,'reference':reference,
    'audio':str(audio),'audioSha256':sha(audio),'pcmSha256':pcm_digest.hexdigest(),'frames':frames,'audioSeconds':frames/16000,
    'selectedMicrophoneZeroBased':0,'sourceChannels':8 if entry['corpus']=='AISHELL-4' else 1,'resampled':False,'denoised':False,'vadDroppedAudio':False,
    'referenceTranscriptModified':False,'trainingStarted':False,'newNeuralCalls':0,'qualityQualified':False}
   atomic_json(folder/'receipt.json',item);state['completed'].append(item);save();print(json.dumps({'meeting':item['meeting'],'audioSeconds':item['audioSeconds'],'sourcesCompleted':len(state['completed'])}),flush=True)
  except BaseException as error:
   failure={'meeting':entry['meeting'],'error':repr(error),'at':datetime.now().astimezone().isoformat(),'automaticRetry':False};state['failures'].append(failure);atomic_json(folder/'failure.json',failure);save()
 state.update(state='PUBLIC_TRAINING_SOURCE_DATA_PREPARED_WITH_RETAINED_FAILURES' if state['failures'] else 'COMPLETE_PUBLIC_TRAINING_SOURCE_DATA_NO_TRAINING')
except BaseException as error:state.update(state='INCOMPLETE_PUBLIC_TRAINING_DATA_RETAINED_NO_TRAINING',error=repr(error));raise
finally:state['finishedAt']=datetime.now().astimezone().isoformat();state.pop('activeMeeting',None);save();atomic_json(C/'data-preparation.json',state)
print(json.dumps({'state':state['state'],'completed':len(state['completed']),'failures':state['failures'],'audioHours':sum(r['audioSeconds'] for r in state['completed'])/3600,'trainingStarted':False}))
