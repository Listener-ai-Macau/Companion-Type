"""Reuse the original FP32 complete baseline for the retained speaker adapter."""
from pathlib import Path
from datetime import datetime
import gc,hashlib,importlib.util,json,os,sys,tarfile,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
from companion_community1_adapter_20261115 import pin_rocm_blas
import numpy as np,torch,yaml
torch.set_num_threads(1);torch.set_num_interop_threads(1)
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'public-speaker-adaptation-r1';OUT=D/'public-speaker-development-r1';OUT.mkdir()
cache=Path('E:/CodexData/Companion/.model-cache/public-speaker-adaptation-20261115/original-development-r1');cache.mkdir()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert read(C/'candidate-decision.json')['validationKeepRulePassed'] is True
P=read(C/'protocol.json');pin_rocm_blas(P['rocmBlasLibrary'],P['rocmBlasLibrarySha256'])
case=read(D/'cached-global-identity-r1/scoring-only.json')[0];assert case['meeting']=='20200623_S_R001S07C01'
assert sha(case['audio'])==case['audioSha256']
spec=importlib.util.spec_from_file_location('pinned_original_diar_converter',P['converter']);up=importlib.util.module_from_spec(spec);spec.loader.exec_module(up)
with tarfile.open(P['checkpoint']) as archive:config=yaml.safe_load(archive.extractfile('model_config.yaml').read())
extractor=up.build_feature_extractor(config)
from bounded_nemotron_frontend_20261115 import install_bounded_frontend
install_bounded_frontend(extractor)
processor=up.Nemotron3DiarizationProcessor(feature_extractor=extractor,subsampling_factor=8)
with wave.open(case['audio'],'rb') as stream:
 assert (stream.getnchannels(),stream.getsampwidth(),stream.getframerate())==(1,2,16000)
 samples=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float32);samples/=32768
with torch.inference_mode():inputs=processor(samples,sampling_rate=16000,return_tensors='pt')
feature=inputs['input_features'][0].contiguous()
reference_root=Path('E:/CodexData/Companion/product-d1d2-20261114/official-native-parity-r1/new-ordinary-run-r2/result')
original_features=read(reference_root/'feature-binding.json')
raw_digest=hashlib.sha256(feature.numpy().tobytes()).hexdigest()
assert raw_digest==original_features['sha256'],'Original full feature bytes differ; do not reuse old neural baseline'
feature_file=cache/'features.npy';np.save(feature_file,feature.numpy(),allow_pickle=False)
item={**{k:case[k] for k in ['meeting','audio','audioSha256','audioSeconds']},'role':'validation',
 'frames':len(feature),'validSupervisedFrames':int(case['audioSeconds']*100),
 'features':str(feature_file),'featuresSha256':sha(feature_file)}
prefix=read(C/'audio-only.json')[0];assert prefix['role']=='train'
write(OUT/'audio-only.json',[prefix,item])
write(OUT/'validation-scoring-only.json',[{**item,**{k:case[k] for k in ['reference','referenceSha256','referenceKind','corpus']}}])
old_score=read(reference_root/'strict-score.json')
assert old_score['audioSha256']==case['audioSha256'] and old_score['referenceSha256']==case['referenceSha256']
error=sum(old_score['components'][k] for k in ['false alarm','missed detection','confusion'])
write(OUT/'baseline-decision.json',{'state':'REUSE_ORIGINAL_COMPLETE_FP32_REFERENCE_NO_NEW_BASELINE_NEURAL_CALLS',
 'reports':[old_score],'aggregateDer':old_score['components']['diarization error rate'],
 'totalErrorSeconds':error,'totalReferenceSpeakerSeconds':old_score['components']['total'],
 'originalFeatureRawBytesExact':True,'originalFeatureSha256':raw_digest,
 'originalProbability':str(reference_root/'probabilities.npy'),'originalProbabilitySha256':sha(reference_root/'probabilities.npy'),
 'qualityQualified':False})
P.update(state='FROZEN_ORIGINAL_DIFFICULT_DEVELOPMENT_MEETING_AFTER_HELD_VALIDATION_KEEP_RULE',
 at=datetime.now().astimezone().isoformat(),audioOnlySha256=sha(OUT/'audio-only.json'),
 validationScoringSha256=sha(OUT/'validation-scoring-only.json'),baselineDecision=str(OUT/'baseline-decision.json'),
 evaluationRole='Original complete development meeting, not new independent validation or training. Same unchanged ASR and original reference.')
write(OUT/'protocol.json',P)
B=read(C/'worker-binding.json');B['protocolSha256']=sha(OUT/'protocol.json');write(OUT/'worker-binding.json',B)
write(OUT/'preparation-receipt.json',{'state':'PASS_ORIGINAL_FULL_FEATURE_BYTES_EXACT_BASELINE_REUSED',
 'at':datetime.now().astimezone().isoformat(),'originalFeatureRawSha256':raw_digest,
 'originalBaselineDer':old_score['components']['diarization error rate'],'newNeuralCalls':0,
 'trainingOnDevelopment':False,'finalHoldoutOpened':False,'limits':limits.query()})
print(json.dumps({'state':'PASS_ORIGINAL_FULL_FEATURE_BYTES_EXACT_BASELINE_REUSED','originalDer':old_score['components']['diarization error rate'],'frames':len(feature),'newNeuralCalls':0},ensure_ascii=False))
