"""Freeze a single optional speaker-component comparison before model access."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
R=S.parent.parent;C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114'
D=C/'d1d2-execution';P=D/'community1-preflight-r1';OUT=D/'community1-comparison-r1';OUT.mkdir()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert read(P/'pyannote-import-control.json')['state']=='PASS_ISOLATED_PYANNOTE_IMPORT_AND_OFFICIAL_IN_MEMORY_PCM_EXACT'
assert read(P/'isolated-additions-install-state.json')['baseDistributionsExactBeforeAfter']
sites=[Path('E:/CodexData/Companion/.model-cache/community1-preflight-20261115/isolated-pyannote-r1'),
 Path('E:/CodexData/Companion/.model-cache/community1-preflight-20261115/isolated-torchaudio-r1')]
runtime_files=[]
for site in sites:
 for f in sorted(site.rglob('*')):
  if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':
   runtime_files.append({'file':str(f),'bytes':f.stat().st_size,'sha256':sha(f)})
write(OUT/'runtime-source-binding.json',{'at':datetime.now().astimezone().isoformat(),'additionalSites':[str(p) for p in sites],
 'files':runtime_files,'frozenBaseDistributions':str(P/'frozen-existing-runtime.json'),
 'frozenBaseDistributionsSha256':sha(P/'frozen-existing-runtime.json'),'limits':limits.query()})
case=read(D/'cached-global-identity-r1/scoring-only.json')[0]
assert case['meeting']=='20200623_S_R001S07C01' and sha(case['audio'])==case['audioSha256']
assert sha(case['reference'])==case['referenceSha256']
write(OUT/'audio-only.json',{k:case[k] for k in ['meeting','audio','audioSha256','audioSeconds']})
write(OUT/'scoring-case.json',case)
original=C/'combination-study-r1/native8/results/20200623_S_R001S07C01'
baseline=read(original/'review.json')
assert baseline['rttmSha256']==sha(original/'predicted.rttm')
write(OUT/'baseline-binding.json',{'rttm':str(original/'predicted.rttm'),'rttmSha256':sha(original/'predicted.rttm'),
 'originalScore':str(original/'review.json'),'originalScoreSha256':sha(original/'review.json'),
 'originalComponents':baseline['components']})
native=read(D/'official-native-parity-r1/protocol.json')
protocol={'state':'FROZEN_SINGLE_OFFICIAL_COMMUNITY1_SPEAKER_ONLY_COMPARISON_AWAITING_ACCESS',
 'at':datetime.now().astimezone().isoformat(),'repository':'pyannote/speaker-diarization-community-1',
 'officialCard':'https://huggingface.co/pyannote/speaker-diarization-community-1',
 'reason':'Same-checkpoint upstream parity reproduces native returning-speaker confusion and neutral cache tracing rules out total cache eviction. An unchanged official VBx/WeSpeaker pipeline is materially different from the failed ERes complete-link port or cached regrouping.',
 'modelRoot':'E:/CodexData/Companion/.model-cache/community1-comparison-20261115/model',
 'modelAccess':'Owner account-information agreement and a pinned official local snapshot must be completed before model-binding.json and any full NN phase. No token is accepted in control files or logs.',
 'pythonExe':'E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe',
 'additionalSites':[str(p) for p in sites],'runtimeManifest':str(OUT/'runtime-source-binding.json'),
 'runtimeManifestSha256':sha(OUT/'runtime-source-binding.json'),
 'rocmBlasLibrary':native['rocmBlasLibrary'],'rocmBlasLibrarySha256':native['rocmBlasLibrarySha256'],
 'featureProof':'E:/CodexData/Companion/product-d1d2-20261114/community1-comparison-r1/features-r1/state.json',
 'audioOnlySha256':sha(OUT/'audio-only.json'),
 'pipelineSettings':'Unmodified official pretrained defaults, FP32/default upstream dtype, no AMP, no speaker-count hints, no segmentation/clustering/threshold/batch-size sweep, seed20261115.',
 'localInput':'Exact original mono16k PCM16/32768, no enhancement, no separation, no amplitude change, no resampling. Official preloaded waveform input; all samples retained.',
 'scoring':'Original full continuous-time DER, zero collar, overlap included, full audio UEM and original reference/parser. Score regular output only; keep raw float times and9decimal RTTM. Save exclusive separately; never use it as a replacement score.',
 'scorer':str(S/'score_cross_corpus_diarization_20261103.py'),'scorerSha256':sha(S/'score_cross_corpus_diarization_20261103.py'),
 'acceptance':'One fixed full new ordinary development meeting. Only if DER<=10% and returning-voice attribution improves, run the protected old whole meeting before considering a product candidate. Inspect per-person regressions; ASR/per-person words/minutes/original whole-product gates remain independently required. No automatic adoption.',
 'stop':'If new complete original DER fails10%, reject this fixed comparison for default use; no speaker-count hint, cutoff/duration tweak, model version shopping or easier reference.',
 'originalBenchmarkProtocolSha256':sha(R/'docs/handoffs/20261108-competitive-sale-standard/benchmark-protocol.json'),
 'oldProtectedMeeting':'S_R004S03C01','finalHoldoutOpened':False,'newTraining':False,'qualityQualified':False,
 'ownerAccessAnswerReceived':False,'cpuPercentMaximum':5,'privateLimitBytes':2*1024**3,'actualWindowsLowRamStop':True,
 'featureToleranceBeforeOutputs':{'maximumAbsolute':.003,'meanAbsolute':.0001,'scope':'Technical CPU/GPU FP32 public feature check, not speech recognition or model quality.'}}
assert protocol['originalBenchmarkProtocolSha256']=='2a82b5b36b231dd4ba77c670c347bb573aa7a13f225271eb9c5750e309e99623'
write(OUT/'protocol.json',protocol)
sources=['community1_comparison_worker_20261115.py','run_community1_comparison_20261115.py',
 'companion_community1_adapter_20261115.py']
for name in sources:ast.parse((S/name).read_text(encoding='utf-8'))
write(OUT/'worker-binding.json',{'workerSha256':sha(S/sources[0]),'runnerSha256':sha(S/sources[1]),
 'protocolSha256':sha(OUT/'protocol.json'),'helpers':{str(S/name):sha(S/name) for name in [sources[2],
 'moss_windows_resource_limits_20261104.py','companion_local_pcm_session_20261114.py','companion_windows_power_request_20261115.py','practical_io_20261107.py']}})
print(json.dumps({'state':protocol['state'],'runtimeFiles':len(runtime_files),'runtimeBytes':sum(r['bytes'] for r in runtime_files),
 'originalBaselineDer':baseline['components']['diarization error rate'],'newNeuralCalls':0,'gateAccessed':False},ensure_ascii=False))
