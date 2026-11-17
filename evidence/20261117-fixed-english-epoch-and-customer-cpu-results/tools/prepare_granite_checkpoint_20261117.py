"""Select closed, small model evidence without weights, audio or runtime caches."""
from pathlib import Path
from datetime import datetime
import argparse,gzip,hashlib,json,sys
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/ai-collaboration-workflow/tools/handbook')
import docstore

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
ap=argparse.ArgumentParser();ap.add_argument('--revision',type=int,default=74);args=ap.parse_args();assert args.revision in (74,75,76)
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
key='Companion/docs/development_log.md'
timeline=docstore.read_bytes(key)
assert b'MODEL_REFERENCE_AND_PORTAL_BATCH_20261117' in timeline
receipt=dict(at=datetime.now().astimezone().isoformat(),timelineQueryKey=key,timelineUrl=docstore.url(key),
    timelineSha256=docstore.sha(timeline),timelineBytes=len(timeline),
    physicalMarkdownRestored=False,canonicalBacklogSha256=hashlib.sha256((R/'docs/product_backlog.json').read_bytes()).hexdigest())
(C/'canonical-record-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
items=[]
def add(p,name):
    p=Path(p)
    assert p.is_file()
    if p.stat().st_size>=32*1024**2:
        assert p.name=='gpu-operators.jsonl' and p.parent.name=='train'
        archive=C/'closed-training-operators.jsonl.gz'
        if not archive.exists():
            with p.open('rb') as source,archive.open('xb') as target:
                with gzip.GzipFile(filename='',fileobj=target,mode='wb',mtime=0) as compressed:
                    while block:=source.read(1024**2):compressed.write(block)
        with p.open('rb') as source:digest=hashlib.file_digest(source,'sha256').hexdigest()
        with gzip.open(archive,'rb') as restored:assert hashlib.file_digest(restored,'sha256').hexdigest()==digest
        receipt=C/'closed-training-operators-receipt.json'
        receipt.write_text(json.dumps(dict(original=str(p),bytes=p.stat().st_size,sha256=digest,
            archive=str(archive),gzipExactDecompressionVerified=True,originalDeleted=False),indent=2)+'\n',encoding='utf-8')
        assert archive.stat().st_size<32*1024**2
        items.append(dict(source=str(archive),name=name+'.gz'))
        items.append(dict(source=str(receipt),name=name+'.gzip-receipt.json'))
        return
    items.append(dict(source=str(p.resolve()),name=name))
for p in C.glob('*.json'):add(p,'reference/'+p.name)
if args.revision>=75:
 for p in C.glob('*.py'):add(p,'reference/'+p.name)
for run in sorted(C.glob('native-cpu-r*')):
    for p in run.iterdir():
        if p.is_file() and p.suffix in ('.json','.py','.previous'):add(p,'reference/'+run.name+'/'+p.name)
if args.revision>=75:
 for folder in [C/'native-gpu-r1',C/'prepared-native-inputs-r1',C/'venv-supervisor-regression-r1']:
  for p in folder.rglob('*'):
   if p.is_file() and p.suffix in ('.json','.py','.txt','.log','.previous'):
    add(p,'reference/'+folder.name+'/'+p.relative_to(folder).as_posix())
 E=C.parent
 for folder in [E/'gpu-owned-evening20261117-r1',E/'gpu-owned-evening20261117-r2/baseline',E/'gpu-owned-evening20261117-r2/supervisor-baseline',E/'gpu-owned-evening20261117-r2/preflight',E/'gpu-owned-evening20261117-r2/supervisor-preflight']:
  for p in folder.rglob('*'):
   if p.is_file() and p.suffix in ('.json','.log','.previous'):
    add(p,'adaptation/'+folder.parent.name+'/'+folder.name+'/'+p.relative_to(folder).as_posix())
 J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/language-specific-adaptation-r1'
 for folder in [J/'prepared-gpu-evening20261117-r1',J/'prepared-gpu-evening20261117-r2']:
  for p in folder.glob('*.json'):add(p,'adaptation/'+folder.name+'/'+p.name)
for p in (C/'asset-acquisition-r1').glob('*.json'):add(p,'reference/asset-acquisition-r1/'+p.name)
for p in (C/'portal-browser-r5').iterdir():
    if p.is_file():add(p,'portal-browser-r5/'+p.name)
for name in ['acquire_granite_reference_20261117.py','prepare_granite_execution_20261117.py',
 'score_granite_reference_20261117.py','record_granite_and_portal_20261117.py',
 'record_bilingual_progress.py','check_model_portal_20261117.py',
 'checkpoint_model_portal_20261117.py','complete_cpu_wheel_payload_20261117.py',
 'prepare_granite_checkpoint_20261117.py']:
    add(Path('work')/name,'tools/'+name)
add('work/bilingual_progress.json','workpoint-snapshot.json')
if args.revision>=75:
 for name in ['audit_granite_errors_20261117.py','prepare_tdt_adaptation_20261117.py','verify_live_venv_supervisor_20261117.py','record_tdt_evening_20261117.py']:
  add(Path('work')/name,'tools/'+name)
if args.revision==76:
 for name in ['finish_fixed_tdt_evaluation_20261117.py','finish_resumed_tdt_evaluation_20261117.py','finish_tdt_after_shared_lease_20261117.py','record_customer_cpu_deployment_20261117.py','probe_customer_cpu_bilingual_20261117.py','record_customer_cpu_probe_20261117.py','acquire_parakeet_cpu_export_20261117.py','close_model_direction_review_20261117.py']:
  add(Path('work')/name,'tools/'+name)
 add(R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/customer-cpu-bilingual-deployment-20261117.json','customer-cpu-deployment-research.json')
 add(R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/week-direction-review-20261117.json','latest-week-direction-review.json')
 E=C.parent
 for folder in [E/'gpu-owned-evening20261117-r2/train',E/'gpu-owned-evening20261117-r2/supervisor-train',
  E/'gpu-owned-evening20261117-r2/validate',E/'gpu-owned-evening20261117-r2/supervisor-validate',
  E/'gpu-owned-evening20261117-r2/finish-evaluation-r1',E/'gpu-owned-evening20261117-r2/finish-evaluation-resume-r1',
  E/'gpu-owned-evening20261117-r2/finish-evaluation-shared-lease-r1',E/'gpu-owned-evening20261117-r2/supervisor-validate-lock-admission-failed-r1',E/'gpu-owned-evening20261117-r2/validate-lock-admission-failed-r1',
  E/'gpu-owned-evening20261117-r2/resume-1',E/'gpu-owned-evening20261117-r2/supervisor-resume-1',
  E/'gpu-owned-evening20261117-r2/checkpoints',C/'customer-cpu-probe-r1',C/'parakeet-cpu-export-acquisition-r1',C/'portal-cpu-requirement-r1',C/'portal-final-epoch-cpu-r1']:
  for p in folder.rglob('*'):
   if p.is_file() and p.suffix in ('.json','.jsonl','.log','.txt','.py','.png','.previous'):
    add(p,'final/'+folder.parent.name+'/'+folder.name+'/'+p.relative_to(folder).as_posix())
 for name in ['training-completed.json','paired-score.json']:
  add(E/'gpu-owned-evening20261117-r2'/name,'final/'+name)
assert len({x['name'] for x in items})==len(items)
config=dict(revision=args.revision,evidenceDirectory='evidence/20261117-granite-reference-resource-boundary-and-model-webpage' if args.revision==74 else 'evidence/20261117-native-gpu-reference-and-real-training-entry',
    sources=['src/granite_reference_worker_20261117.py']+(['src/readonly_cpu_offload_20261117.py','src/granite_reference_gpu_worker_20261117.py','src/tdt_domain_adaptation_20261116.py','src/run_owned_tdt_adaptation_20261117.py'] if args.revision==75 else []),closedDirectories=[],files=items,
    commitMessage='Preserve native Granite reference execution boundary and measured model-webpage delivery',
    claims=dict(state='GRANITE_REFERENCE_PARTIAL_CPU_BOUNDARY_RETAINED_AND_MODEL_PAGE_DELIVERED',
        completedOriginalAudioOutputs=1,attemptedOriginalAudioCases=2,originalCaseCount=12,
        newTrainingUpdates=0,fullFixedReferenceScoreExists=False,
        cpuDiskOffloadProfileEndedWithoutAutomaticRetry=True,
        candidateQualityRejected=False,qualityQualified=False,saleQualified=False,
        originalReferencesAndMetricsUnchanged=True,
        rawAudioInputFeaturesModelWeightsRuntimeWheelsOrCredentialsIncluded=False,
        webpageLocalSourceCommit=json.loads((C/'portal-source-checkpoint.json').read_text())['commit']))
if args.revision>=75:
 config['commitMessage']='Complete original Granite GPU reference, attribute errors and repair real Windows training supervision'
 config['claims'].update(state='GRANITE_ORIGINAL113_OF709_REJECTED_EXISTING_TRAINING_PREFLIGHT_ACTIVE',
  completedOriginalAudioOutputs=12,attemptedOriginalAudioCases=12,fullFixedReferenceScoreExists=True,
  candidateQualityRejected=True,trainingCandidateOptimizerUpdates=0,
  newTrainingUpdates=1,preflightOnlyParameterUpdates=1,existingTrainingGpuPreflightPassed=True)
if args.revision==76:
 score=json.loads((C.parent/'gpu-owned-evening20261117-r2/paired-score.json').read_text())
 train=json.loads((C.parent/'gpu-owned-evening20261117-r2/train/state.json').read_text())
 recovery=json.loads((C.parent/'gpu-owned-evening20261117-r2/resume-1/completed.json').read_text())
 assert recovery['candidateOptimizerUpdates']==457
 config['evidenceDirectory']='evidence/20261117-fixed-english-epoch-and-customer-cpu-results'
 config['sources']=[]
 config['commitMessage']='Record complete fixed English adaptation and CPU bilingual deployment evidence'
 config['claims'].update(state='FIXED_ENGLISH_EPOCH_SCORED_CUSTOMER_CPU_EVIDENCE_RETAINED',
  trainingCandidateOptimizerUpdates=457,newTrainingUpdates=train['parameterUpdates']+recovery['parameterUpdates']+1,
  discardedUncommittedTrainingUpdates=17,explicitCheckpointRecoveryFromUpdate=416,preflightOnlyParameterUpdates=1,
  pairedBaselineErrors=score['baselineErrors'],pairedCandidateErrors=score['candidateErrors'],
  pairedAdmissionPassed=score['advanceToCompleteSources'],original709WordsRetained=True,
  finalHoldoutOpened=False,productDefaultModelChanged=False,
  customerCpuProbeCompleted=(C/'customer-cpu-probe-r1/score.json').exists(),
  ownerRequestedWorkingModeReviewRecorded=True,newCpuExportInferencePerformed=False,
  qualityQualified=False,saleQualified=False)
 config['claims'].pop('candidateQualityRejected',None)
out=Path('work/checkpoint_granite_and_portal_r'+str(args.revision)+'.json')
out.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(configuration=str(out),files=len(items),bytes=sum(Path(i['source']).stat().st_size for i in items),canonicalRecord=receipt)))
