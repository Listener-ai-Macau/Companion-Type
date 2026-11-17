"""Protect this closed model-review batch and its actual failed/successful runs."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
selected=['run_tdt_cpu_loss_proof_20261117.py','run_tdt_real_cpu_backward_20261117.py',
 'prepare_full_whisper_reference_20261117.py','run_full_whisper_reference_20261117.py',
 'score_full_whisper_reference_20261117.py','record_week_direction_review_20261117.py','prepare_week_checkpoint_20261117.py']
live=[]
for p in psutil.process_iter(['name','cmdline','create_time']):
 try:
  if (p.info['name'] or '').lower() not in ['python.exe','pythonw.exe']:continue
  scripts=[Path(a).name for a in p.info['cmdline'] or []]
  if p.pid!=__import__('os').getpid() and any(name in scripts for name in selected):live.append({'pid':p.pid,'createdAt':p.info['create_time']})
 except (psutil.NoSuchProcess,psutil.AccessDenied):pass
assert not live
run=E/'language-specific-adaptation-r1/real-cpu-backward-r2';state=read(run/'state.json')
assert state['state']=='BACKWARD_ONE_ORIGINAL_TRAINING_EXAMPLE_CPU' and not(run/'result.json').exists()
original=Path('E:/CodexData/Companion/.model-cache/english-transducer-official20261116/model.safetensors')
digest=sha(original);assert digest=='3a2026366188c8c68598edbbff92f8d11590a08e0ae2e6775544e7b07d6a5e11'
observer={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(),'state':'OBSERVED_TERMINAL_DURING_CPU_BACKWARD_NO_FINAL_RESULT',
 'unifiedExecSession':97133,'observedExitCode':1,'expectedOriginalPid':24532,'expectedCreatedAt':1794904250.7542365,
 'sameOriginalProcessLive':False,'lastStateSha256':sha(run/'state.json'),'lastPersistedState':state['state'],
 'backwardCompletionProven':False,'optimizerUpdates':0,'reason':'No final Python result; near2GiB lastcommit is a clue, not a proven exit cause.',
 'originalPublishedWeightsSha256AfterBothCpuAttempts':digest,'originalPublishedWeightFileUnchanged':True}
(run/'observed-terminal.json').write_text(json.dumps(observer,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
base=E/'english-full-base-r1';score=read(base/'cpu-execution-r3/score.json');assert score['aggregate']['errors']==227 and not score['advanceToWholeEnglish']
assert read(base/'cpu-execution-r3/run/completed.json')['limits']['jobPeakPrivateCommitBytes']<2147483648
files=[]
def take(p,name):
 p=Path(p);assert p.is_file() and p.stat().st_size<32*1024**2
 assert p.suffix.lower() not in ['.gguf','.safetensors','.bin','.wav','.ckpt','.nemo','.dll','.exe']
 files.append({'source':str(p),'name':name})
for name in selected:take(Path('work')/name,'tools/'+name)
take(J/'week-direction-review-20261117.json','week-direction-review.json')
take(Path('outputs/Companion-一周模型复盘与路线收敛-20261117.txt'),'owner-week-review.txt')
for name in ['cpu-loss-reference-r1','real-cpu-backward-r1','real-cpu-backward-r2']:
 for p in (E/'language-specific-adaptation-r1'/name).rglob('*'):
  if p.is_file() and p.suffix.lower() in ['.json','.py','.log']:take(p,'cpu-feasibility/'+name+'/'+p.name)
for p in base.rglob('*'):
 if p.is_file() and p.suffix.lower() in ['.json','.py','.log']:take(p,'full-whisper-reference/'+p.relative_to(base).as_posix())
config={'revision':71,'evidenceDirectory':'evidence/20261117-week-route-review-cpu-feasibility-and-full-base-rejection',
 'sources':[],'closedDirectories':[],'files':files,
 'commitMessage':'Review week-level convergence, verify CPU feasibility and reject fullWhisper reference on fixed original cohort',
 'claims':{'state':'WEEK_DIRECTION_REVIEW_AND_FULL_BASE_COMPARISON_COMPLETE_NO_QUALITY_GAIN',
  'fullWhisperEnglishErrors':227,'originalEnglishReferenceWords':709,'fullWhisperCandidateRejected':True,
  'cpuTinyLossGradientProofPassed':True,'realCpuForwardPassedBackwardNotCompleted':True,
  'trainedWeightUpdatesThisBatch':0,'cpuIgpuTrainingPermissionNowAllowed':True,
  'oldMetricsAndFailuresRetained':True,'allOwnedModelJobsTerminal':True,
  'rawAudioInputFeaturesModelWeightsOrCredentialsIncluded':False,'qualityQualified':False,'saleQualified':False}}
Path('work/checkpoint_week_review_r71.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'evidenceFiles':len(files),'allOwnedJobsTerminal':True,'publishedWeightFileUnchanged':True,'fullBaseRejected':True}))
