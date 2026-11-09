from pathlib import Path
import os,sys,json,hashlib,shutil,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109';O=C/'ordinary-full-r1'
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);pressure=SystemRamPressure()
sys.path.append('C:/Users/Billy/AppData/Local/Programs/Python/Python311/Lib/site-packages')
sys.path.append('E:/CodexData/Companion/.model-cache/audio-tools')
import soundfile as sf
import numpy as np
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
source=next(r for r in read(R/'docs/handoffs/20261108-tse-source-supervision/sources.json') if r['meeting']=='20200805_S_R001S01C01')
assert sha(source['localFlac'])==source['expectedWholeFileLfsSha256'] and sha(source['reference'])==source['referenceSha256']
target=Path('E:/CodexData/Companion/.model-cache/competitive-sale-standard-20261108/two-lane-validation-20261109')/(source['meeting']+'-channel1.wav')
assert not target.exists();started=time.perf_counter();count=0;h=hashlib.sha256()
with sf.SoundFile(source['localFlac']) as f:
 assert f.samplerate==16000 and f.channels==8 and f.subtype=='PCM_16';frames=len(f)
 with sf.SoundFile(str(target),'w',samplerate=16000,channels=1,subtype='PCM_16',format='WAV') as out:
  for block in f.blocks(blocksize=16000*60,dtype='int16',always_2d=True):
   if pressure.low():raise RuntimeError('Actual Windows low memory; stop export')
   mono=np.ascontiguousarray(block[:,0]);out.write(mono);h.update(mono.astype('<i2',copy=False).tobytes());count+=len(mono)
assert count==frames
with sf.SoundFile(str(target)) as f:
 assert len(f)==frames and f.channels==1 and f.samplerate==16000
 check=hashlib.sha256()
 for block in f.blocks(blocksize=16000*60,dtype='int16'):check.update(block.astype('<i2',copy=False).tobytes())
assert check.hexdigest()==h.hexdigest()
case={'meeting':source['meeting'],'audio':str(target),'audioSha256':sha(target),'audioSeconds':frames/16000}
O.mkdir(exist_ok=False);(O/'full').mkdir()
base=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-native17-r5'
for name in ('native-protocol.json','model-ready.json'):shutil.copyfile(base/name,O/name)
protocol=read(base/'protocol.json');protocol.update(baseControl=str(base),modelParametersChanged=False,changedParameterScope='No model/generation changes; new full development audio only. References remain scoring-only.',earlyGateReusedFrom=str(base/'pilot'),qualityQualified=False)
write(O/'protocol.json',protocol);write(O/'seed-manifest.json',{'files':{}});write(O/'pilot-extra-audio-only.json',[]);write(O/'audio-only.json',[case]);write(O/'full/audio-only.json',[case]);write(O/'full/scoring-only.json',[{**case,'reference':source['reference'],'referenceSha256':source['referenceSha256'],'corpus':'AISHELL-4','referenceKind':'textgrid_lexical'}])
proof={'state':'READY_FROZEN_QWEN_WHOLE_MEETING_NOT_RUN_GPU_OFFLINE','case':case,'originalSource':source,'channelIndexZeroBased':0,'sourceFrames':frames,'exportedFrames':count,'allOriginalChannelSamplesBitExact':True,'pcmSha256':h.hexdigest(),'exportSeconds':time.perf_counter()-started,'limits':limits.query(),'denoisingOrTrimmingOrResampling':False,'sourcePreviouslyUsedForTseValidation':True,'finalHoldout':False,'noAsrOrAccuracyGainClaimed':True,'launchCommand':['E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe',str(M/'src/practical_qwen_checkpoint_worker_20261107.py'),'--control',str(O),'--phase','full','--index','0'],'scoringCommand':['E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',str(M/'src/score_practical_transcript_20261107.py'),'--control',str(O/'full'),'--meeting',source['meeting']],'license':'AISHELL4/OpenSLR111 CC-BY-SA4.0, original attribution retained in sources','saleQualified':False}
write(C/'ordinary-full-ready.json',proof);print(json.dumps({'state':proof['state'],'meeting':case['meeting'],'seconds':case['audioSeconds'],'allSamplesBitExact':True,'exportSeconds':proof['exportSeconds']},ensure_ascii=False))
