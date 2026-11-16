"""Whole-source extension of the existing source-separated validation cohort, no NN."""
from pathlib import Path
from datetime import datetime
import ctypes,hashlib,json,os,sys,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate,SystemRamPressure
from practical_io_20261107 import atomic_json
limits=WorkerLimits(cpu_percent=1,memory_bytes=512*1024**2);rate=CpuRate(5,50)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
assert limits.query()['cpuRate']==50
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1'
C=BASE/'cpu-extended-validation-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/cpu-extended-validation-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not C.exists() and not E.exists();C.mkdir();E.mkdir();(E/'audio').mkdir()
old=D/'sequential-meeting-stageA-r2';inventory=read(old/'source-inventory.json');windows=read(old/'scoring-only.json')
selected=[r for r in inventory['sources'] if r['role']=='validation' and r['meeting']!='ES2003b']
selected.sort(key=lambda r:(r['language']!='English',r['meeting']));assert len(selected)==3
state={'state':'PREPARING_FIXED_EXTENDED_WHOLE_SOURCE_VALIDATION_NO_NEURAL_CALLS','at':datetime.now().astimezone().isoformat(),'completed':[],
 'order':[r['meeting'] for r in selected],'selection':'All prior validation sources beyond the original4, English first then source ID. No new full scores used to choose or reorder sources.',
 'sourceControls':str(old),'newNeuralCalls':0,'qualityQualified':False,'blindFinalHoldoutOpened':False,'cpuPercentDuringPreparation':.5}
atomic_json(E/'preparation.json',state);pressure=SystemRamPressure()
try:
 import soundfile as sf
 import numpy as np
 for source in selected:
  assert not pressure.low() and sha(source['audio'])==source['audioSha256'];info=sf.info(source['audio']);assert info.samplerate==16000 and info.subtype=='PCM_16'
  target=E/'audio'/(source['meeting']+'-mic0.wav');digest=hashlib.sha256();count=0
  with sf.SoundFile(source['audio']) as src,wave.open(str(target),'wb') as dst:
   dst.setparams((1,2,16000,0,'NONE','not compressed'))
   while True:
    if pressure.low():raise InterruptedError('Actual Windows low RAM; conversion partial retained, no inference started')
    data=src.read(480000,dtype='int16',always_2d=True)
    if not len(data):break
    pcm=np.ascontiguousarray(data[:,0],dtype='<i2').tobytes();dst.writeframesraw(pcm);digest.update(pcm);count+=len(data)
  assert count==info.frames
  controls=[]
  with wave.open(str(target),'rb') as wav:
   for row in [r for r in windows if r['meeting']==source['meeting']]:
    wav.setpos(row['sourceStartFrame']);pcm=wav.readframes(row['sourceEndFrame']-row['sourceStartFrame'])
    assert hashlib.sha256(pcm).hexdigest()==row['pcmSha256']
    controls.append(row['id'])
  case={'meeting':source['meeting'],'language':source['language'],'role':'validation','audio':str(target),'audioSha256':sha(target),
   'pcmSha256':digest.hexdigest(),'frames':count,'audioSeconds':count/16000,'sourceAudio':source['audio'],'sourceAudioSha256':source['audioSha256'],
   'sourceChannels':info.channels,'selectedChannelZeroBased':0,'sameExistingWindowPcmControls':controls,'addedNoise':False,'resampled':False,
   'scope':'Complete original single-mic timeline, includes natural overlap/noise; prior short validation windows are already seen and this is not blind final acceptance.'}
  state['completed'].append(case);atomic_json(E/'preparation.json',state)
 state['state']='PREPARED_COMPLETE_ADDITIONAL3_PUBLIC_VALIDATION_SOURCES_NO_NEURAL_CALLS';state['limits']=limits.query();atomic_json(E/'preparation.json',state)
 audio=[{k:r[k] for k in ['meeting','audio','audioSha256','frames','audioSeconds']} for r in state['completed']]
 atomic_json(C/'audio-only.json',audio)
 scoring=[{**r,'originalSourceEntry':next(s for s in selected if s['meeting']==r['meeting'])} for r in state['completed']]
 atomic_json(C/'scoring-only.json',scoring)
 atomic_json(C/'protocol.json',{'at':datetime.now().astimezone().isoformat(),'state':state['state'],'sourceInventorySha256':sha(old/'source-inventory.json'),
  'audioManifestSha256':sha(C/'audio-only.json'),'scoringManifestSha256':sha(C/'scoring-only.json'),'sameModelCombinationAnd30sPolicy':True,
  'order':state['order'],'selection':state['selection'],'totalAudioSeconds':sum(r['audioSeconds'] for r in state['completed']),
  'neuralDeadline':'2026-11-16T15:40:00+08:00','reportDeadline':'2026-11-16T16:00:00+08:00','newModelsOrThresholdTuning':False,
  'sameOldWindowPcmControlsMatched':sum(len(r['sameExistingWindowPcmControls']) for r in state['completed']),
  'qualification':'Original raw/per-person/DER/facts gates unchanged; no complete old ASR baseline exists for these sources, report absolute full-source metrics without claiming full-source improvement. Missing/unrun sources stay explicit.',
  'sourceRoles':'Existing validation sources used for short-window selection, not a blind final cohort. The original final Chinese holdout remains closed.',
  'newNeuralCallsDuringPreparation':0,'qualityQualified':False})
 print(json.dumps({'state':state['state'],'sources':[(r['meeting'],r['audioSeconds']) for r in state['completed']],'control':str(C),'newNeuralCalls':0},ensure_ascii=False))
except BaseException as error:
 state.update(state='INCOMPLETE_ADDITIONAL_SOURCE_PREPARATION_RETAINED_NO_NEURAL_CALLS',error=repr(error));atomic_json(E/'preparation.json',state);raise
finally:pressure.close()
