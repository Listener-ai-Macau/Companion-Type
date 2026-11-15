from pathlib import Path
from datetime import datetime
import ast,hashlib,json,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/official-native-parity-r1')
control=D/'nemotron-cache-trace-r1';assert not control.exists()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
parent=S/'official_nemotron_reference_worker_20261115.py'
assert sha(parent)=='953f1a3c8e9741f596401855ed3cae92a320166fa3b6e5a951b9463f0127fdb3'
source=parent.read_text(encoding='utf-8')
needle='  hook=model.model.register_forward_hook(progress)'
insert='''  from trace_nemotron_cache_20261115 import install_cache_trace
  assert sha(Path(__file__).with_name('trace_nemotron_cache_20261115.py'))==P['cacheTraceHelperSha256']
  restore_trace=install_cache_trace(out/'cache-trace',expected_source_sha256=P['upstreamCacheSourceSha256'],audio_seconds=case['audioSeconds'])
'''+needle
assert source.count(needle)==1;source=source.replace(needle,insert)
needle2="  np.save(out/'probabilities.npy',probability,allow_pickle=False)"
insert2=needle2+'''
  restore_trace()
  assert sha(out/'probabilities.npy')==P['originalFullProbabilitySha256'], 'Observational trace changed original full model output; retain evidence, no retry/tolerance variant'
  atomic_json(out/'observational-control.json',{'exactOriginalFullProbabilityBytes':True,'baselineSha256':P['originalFullProbabilitySha256'],
    'allOriginalFramesAndChannelsIdentical':True,'newSelectionPolicy':False,'qualityQualified':False})
'''
assert source.count(needle2)==1;source=source.replace(needle2,insert2)
worker=S/'nemotron_cache_trace_worker_20261115.py';assert not worker.exists();ast.parse(source)
worker.write_text(source,encoding='utf-8',newline='')
runner=S/'run_nemotron_cache_trace_20261115.py';assert not runner.exists()
body=(S/'run_official_nemotron_reference_20261115.py').read_text(encoding='utf-8').replace(parent.name,worker.name)
ast.parse(body);runner.write_text(body,encoding='utf-8',newline='')
control.mkdir()
for name in ['audio-only.json','scoring-only.json']:shutil.copyfile(D/'official-native-parity-r1'/name,control/name)
P=read(D/'official-native-parity-r1/protocol.json')
source_file=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/transformers/models/nemotron3_diarization/modeling_nemotron3_diarization.py')
P.update(at=datetime.now().astimezone().isoformat(),state='FIXED_OBSERVATIONAL_CACHE_CAUSE_AUDIT_NOT_MODEL_CANDIDATE',
 workerSha256=sha(worker),parentWorkerSha256=sha(parent),cacheTraceHelperSha256=sha(S/'trace_nemotron_cache_20261115.py'),
 upstreamCacheSourceSha256=sha(source_file),
 originalFullProbabilitySha256=sha(E/'new-ordinary-run-r2/result/probabilities.npy'),
 purpose='Determine whether cache activity evidence for a previously observed anonymous channel disappears before the returning-voice failure. Same weights/geometry/math; only detached cache snapshots. Require full probability file bit-identical to saved uninstrumented run.',
 runOrder=['After active ASR family exits, one same34min observation only; no parameter changes or alternate checkpoint.'],
 automaticVariants=False,newCacheSelectionPolicy=False,newTraining=False,
 interpretation='Zero retained activity evidence would support eviction as a cause; retained evidence would argue against simple cache eviction. No reference labels enter inference; conclusions require actual trace and exact-output control.')
(control/'protocol.json').write_text(json.dumps(P,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(control/'preparation.json').write_text(json.dumps({'state':'PREPARED_ONLY_WAITING_FOR_CURRENT_ASR_FAMILY',
 'workerSha256':sha(worker),'newNeuralCalls':0,'newTraining':False,'qualityQualified':False,
 'newModelCandidate':False,'originalQualityGateChanged':False,'noInputOrModelMathChanged':True},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'control':str(control),'workerSha256':sha(worker),'newNeuralCalls':0}))
