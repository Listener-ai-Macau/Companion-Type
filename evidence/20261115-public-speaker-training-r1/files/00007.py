"""Prepare complete public meetings and official frame labels, no owner input."""
from pathlib import Path
from datetime import datetime
import gc,hashlib,importlib.util,json,os,re,sys,tarfile,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure()
sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from reference_textgrid_20261104 import read_reference_intervals
import numpy as np,soundfile as sf,torch,yaml
torch.set_num_threads(1);torch.set_num_interop_threads(1)
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
OUT=D/'public-speaker-adaptation-r1'
audio=Path('E:/CodexData/Companion/.model-cache/public-speaker-adaptation-20261115/data-r1');audio.mkdir(parents=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
P=read(D/'official-native-parity-r1/protocol.json')
assert sha(P['converter'])==P['converterSha256'] and sha(P['checkpoint'])==P['checkpointSha256']
spec=importlib.util.spec_from_file_location('pinned_diar_converter',P['converter']);up=importlib.util.module_from_spec(spec);spec.loader.exec_module(up)
with tarfile.open(P['checkpoint']) as archive:config=yaml.safe_load(archive.extractfile('model_config.yaml').read())
extractor=up.build_feature_extractor(config)
from bounded_nemotron_frontend_20261115 import install_bounded_frontend
assert sha(S/'bounded_nemotron_frontend_20261115.py')==P['boundedFrontendSha256'];install_bounded_frontend(extractor)
processor=up.Nemotron3DiarizationProcessor(feature_extractor=extractor,subsampling_factor=8)
sources=read(R/'docs/handoffs/20261108-tse-source-supervision/sources.json')
assert len(sources)==4 and {s['role'] for s in sources}=={'train','validation'}
excluded={'S_R004S03C01','20200623_S_R001S07C01','L_R003S01C02','L_R003S03C02'}
assert not excluded&{s['meeting'] for s in sources}
manifests=[];score=[]
for source in sources:
 assert not pressure.low(),'Actual Windows low RAM; retain prepared files, no automatic variant'
 assert sha(source['localFlac'])==source['expectedWholeFileLfsSha256'] and sha(source['reference'])==source['referenceSha256']
 meeting=source['meeting'];directory=audio/meeting;directory.mkdir()
 info=sf.info(source['localFlac']);assert (info.samplerate,info.channels,info.subtype)==(16000,8,'PCM_16')
 wav=directory/'microphone0.wav'
 with sf.SoundFile(source['localFlac']) as stream,wave.open(str(wav),'wb') as out:
  out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000)
  while True:
   block=stream.read(64000,dtype='int16',always_2d=True)
   if not len(block):break
   out.writeframesraw(block[:,0].astype('<i2',copy=False).tobytes())
 with wave.open(str(wav),'rb') as stream:
  assert stream.getnframes()==info.frames
  pcm=stream.readframes(info.frames)
 samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32);samples/=32768;del pcm,block
 with torch.inference_mode():features=processor(samples,sampling_rate=16000,return_tensors='pt')
 assert not torch.cuda.is_initialized() and features['input_features'].shape[0]==1
 feature=features['input_features'][0].contiguous();assert feature.shape[1]==128
 frames=feature.shape[0];valid=min(frames,int(info.frames/16000*100))
 np.save(directory/'features.npy',feature.numpy(),allow_pickle=False)
 rows=[r for r in read_reference_intervals(source['reference']) if re.sub(r'<[^>]*>','',r['text']).strip()]
 speakers=sorted({r['speaker'] for r in rows});assert 1<len(speakers)<=8
 labels=np.zeros((frames,8),dtype=np.uint8)
 for row in rows:
  first=max(0,int(row['start']*100));last=min(valid,int(row['end']*100))
  if last>first:labels[first:last,speakers.index(row['speaker'])]=1
 np.save(directory/'labels.npy',labels,allow_pickle=False)
 item={'meeting':meeting,'role':source['role'],'audio':str(wav),'audioSha256':sha(wav),
  'audioSeconds':info.frames/16000,'frames':frames,'validSupervisedFrames':valid,
  'features':str(directory/'features.npy'),'featuresSha256':sha(directory/'features.npy')}
 manifests.append(item)
 score.append({**item,'labels':str(directory/'labels.npy'),'labelsSha256':sha(directory/'labels.npy'),
  'reference':source['reference'],'referenceSha256':source['referenceSha256'],'referenceKind':'textgrid_lexical',
  'corpus':'AISHELL4-Train-source-held-session-adaptation','officialSourceFlacSha256':source['expectedWholeFileLfsSha256'],
  'targetSpeakersForTrainingAndScoringOnly':speakers,'annotatedOverlapSecondsAt10ms':float((labels[:valid].sum(axis=1)>1).sum()/100)})
 write(OUT/'preparation-state.json',{'state':'PREPARING_COMPLETE_PUBLIC_MEETINGS','completed':[r['meeting'] for r in manifests],
  'limits':limits.query(),'newNeuralCalls':0})
 del samples,features,feature,labels,rows;gc.collect()
write(OUT/'audio-only.json',manifests)
write(OUT/'train-supervision.json',[r for r in score if r['role']=='train'])
write(OUT/'validation-scoring-only.json',[r for r in score if r['role']=='validation'])
write(OUT/'preparation-state.json',{'state':'COMPLETE_OFFICIAL_PUBLIC_TRAIN_VALIDATION_DATA_NO_NEURAL_CALLS',
 'at':datetime.now().astimezone().isoformat(),'sources':score,'newNeuralCalls':0,'newParameterUpdates':0,
 'targetRaster':'Original NeMo10ms int(start*100):int(end*100), max8 speakers; target-valid length floor(duration*100). Extra frontend tail remains in inference/scoring, only not supervised.',
 'features':'Same pinned upstream FP32 frontend and validated bounded FFT, all original mono samples. No audio enhancement/resampling.',
 'license':'AISHELL4 CC-BY-SA-4.0 https://www.openslr.org/111/; original metadata retained.',
 'physicalSpeakerOrRoomIndependenceNotProved':True,'developmentAndFinalMeetingsExcluded':sorted(excluded),
 'qualityQualified':False,'limits':limits.query()})
pressure.close()
print(json.dumps({'state':'COMPLETE_OFFICIAL_PUBLIC_TRAIN_VALIDATION_DATA_NO_NEURAL_CALLS',
 'sources':[{k:r[k] for k in ['meeting','role','audioSeconds','annotatedOverlapSecondsAt10ms']} for r in score],
 'limits':limits.query()},ensure_ascii=False))
