"""Pin and inspect upstream training entry without importing or executing it."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,sys,urllib.request
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2)
C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/meeting-domain-data-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1/training-source-audit');assert not E.exists();E.mkdir()
def fetch(url):
 request=urllib.request.Request(url,headers={'User-Agent':'Companion-research-source-audit','Accept':'application/vnd.github+json'})
 with urllib.request.urlopen(request,timeout=30) as response:return response.read()
api='https://api.github.com/repos/QwenLM/Qwen3-ASR/commits?path=finetuning/qwen3_asr_sft.py&per_page=1';raw=fetch(api);commits=json.loads(raw);commit=commits[0]['sha']
url='https://raw.githubusercontent.com/QwenLM/Qwen3-ASR/'+commit+'/finetuning/qwen3_asr_sft.py';body=fetch(url);text=body.decode();ast.parse(text);(E/'qwen3_asr_sft.py').write_bytes(body)
old=(S/'public_acoustic_context_worker_20261115.py').read_text(encoding='utf-8')
receipt={'state':'PINNED_UPSTREAM_TRAINING_ENTRY_STATIC_AUDIT_ONLY_NO_IMPORT_OR_TRAINING','at':datetime.now().astimezone().isoformat(),'upstreamCommit':commit,'url':url,
 'sha256':hashlib.sha256(body).hexdigest(),'license':'Apache-2.0, original header retained','sourceFile':str(E/'qwen3_asr_sft.py'),
 'observedPrefixMaskAbsoluteFromColumnZero':'labels[i, :pl] = -100' in text,'observedPatchedForwardAcceptsKwargs':'**kwargs' in text.split('def patch_outer_forward',1)[1].split('_CKPT_RE',1)[0],
 'communityIssue':'https://github.com/QwenLM/Qwen3-ASR/issues/216','communityReportedLossAndPaddingBugsLocallyReproduced':False,
 'doNotAttributePriorAdapterFailureToThisIssue':True,'priorCustomAcousticWorker':str(S/'public_acoustic_context_worker_20261115.py'),
 'priorCustomWorkerUsesSingleExampleExplicitPrefixMask':'labels[:, :prefix_size] = -100' in old,'priorCustomWorkerDividesManualAccumulationByActualGroupSize':'(output.loss/group_size).backward()' in old,
 'futureTrainingPreflight':['Verify target-only labels on actual unequal-length left/right-padded processor batches.','Verify one-batch versus accumulated-gradient equivalence under the selected token/example loss normalization.','Verify real acoustic encoder and bridge parameter coverage; preserve the earlier rejected adapters.','Verify complete checkpoint save/reload logits and CPU deployment conversion on unchanged controls before full acceptance.'],
 'architectureEvidence':{'url':'https://arxiv.org/abs/2607.08208v2','scope':'A modular diarization+Qwen adaptation study on two-speaker conversations, not proof for our multi-person single-mic product. It motivates supervised domain adaptation; no result transfers automatically.'},
 'trainingLaunchReady':False,'remaining':['Actual usable training device/runtime is unavailable after owner disconnected the6800XT.','Chinese real cross-meeting participant isolation remains unverified.','Current exports cover2.81h selected nonoverlap speech, not all13.1h of source audio or a proven sufficient training scale.'],
 'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'training-source-audit.json',receipt);print(json.dumps(receipt,ensure_ascii=False))
