from pathlib import Path
from datetime import datetime
import hashlib,json,wave
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';H=R/'docs/handoffs/20261107-model-generation-recovery'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1';C=BASE/'cpu-native8-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/cpu-native8-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not C.exists() and not E.exists();C.mkdir();cpu=read(H/'native8-smoke-r1/protocol.json');f16=read(H/'native8-f16-smoke-r1/protocol.json')
P={**f16,**{k:cpu[k] for k in ['nativeLibrary','nativeLibrarySha256','nativeExe','nativeExeSha256','nativeFiles']}}
P.update(backend='cpu',probabilityCacheRoot=str(E/'probabilities'),interPushIdleSeconds=0.0,cpuPercent=25,privateCommitBytes=2147483648,
 frozenAt=datetime.now().astimezone().isoformat(),precision='Same published-checkpoint FP16 GGUF as the retained original full4 speaker baseline, CPU-only native binary. This is not the original FP32 Torch path and no bitwise cross-backend equivalence is assumed.',nativeComputeThreads=4)
for name,digest in P['nativeFiles'].items():assert sha(Path(P['nativeLibrary']).parent/name)==digest
assert sha(P['model'])==P['modelSha256']
control=read(H/'native8-f16-smoke-r1/audio-only.json')[0];assert control['audioSeconds']==61
short={**control,'meeting':'cpu-native8-control61'};cases=[short]+[{k:r[k] for k in ['meeting','audio','audioSha256','audioSeconds']} for r in read(BASE/'cpu-fixed-whole-r2/binding.json')['meetings']]
for case in cases:
 assert sha(case['audio'])==case['audioSha256']
 with wave.open(case['audio'],'rb') as w:assert w.getnframes()/16000==case['audioSeconds']
proof=[]
for path,blob in [('src-runtime-ggml-runtime.h','308985e0482ea2200b532f569c2a50697f669934'),('src-asr-diar-diarizer.cpp','610812c872a507b847f609906e65b0a5cab6ec33'),('src-runtime-ggml-session.cpp','deac3003efd5720d818f9eb51c30ef79b538d414')]:
 file=Path('work/upstream-nemo-cpu-v030')/path;raw=file.read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==blob
 proof.append({'file':str(file.resolve()),'sha256':sha(file),'upstreamGitBlobSha1':blob,'source':'https://github.com/NVIDIA/NeMo-Speech.cpp/blob/v0.3.0/'+path.replace('src-runtime-ggml-','src/runtime/ggml/').replace('src-asr-diar-','src/asr/diar/')})
B={'at':datetime.now().astimezone().isoformat(),'wrapperSha256':sha(S/'cpu25_nemotron_wrapper_20261116.py'),'runnerSha256':sha(S/'run_cpu25_nemotron_20261116.py'),
 'ownerCpuBudgetPermission':read(BASE/'cpu-fixed-whole-r2/binding.json')['ownerCpuBudgetPermission'],'workerPython':'E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',
 'neuralDeadline':'2026-11-16T15:40:00+08:00','reportDeadline':'2026-11-16T16:00:00+08:00','nativeComputeThreads':4,'threadDefaultSourceProof':proof,
 'helperSha256':{str(S/n):sha(S/n) for n in ['moss_windows_resource_limits_20261104.py','practical_nemotron_worker_20261107.py','practical_nemotron_cli_control_20261107.py']},
 'modelScope':'The same original native8 FP16 speaker backbone and geometry; explicit CPU-only binary/gpu=-1, no oracle speaker count or references.',
 'control':'Exact existing public61 waveform; CPU C ABI vs official CPU CLI at unchanged geometry/threshold and millisecond serialization tolerance before original4 whole recordings.',
 'runtimeOnly':True,'weightsChanged':False,'qualityQualified':False,'productDefaultChanged':False,'newWeightTraining':False,'noNeuralExecutionDuringPreparation':True}
for name,value in [('protocol.json',P),('audio-only.json',cases),('binding.json',B)]:
 (C/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'control':str(C),'run':str(E),'inputs':len(cases),'cpuOnlyBinary':P['nativeLibrary'],'modelSha256':P['modelSha256'],'sourceDefaultThreads':4}))
