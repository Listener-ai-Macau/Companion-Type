"""Freeze one English adaptation and its independent score; do not execute GPU."""
from pathlib import Path
from datetime import datetime,timedelta
import argparse,hashlib,json,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
from model_thermal_guard_20261117 import inspect_thermal_policy
from tdt_domain_adaptation_20261116 import inspect
from meeting_acoustic_contract_20261116 import read,require,sha
from durable_model_state_20261117 import atomic_json
from tdt_adaptation_contract_20261117 import checkpoint_due
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
parser=argparse.ArgumentParser();parser.add_argument('--revision',default='r1');parser.add_argument('--enable-existing-gpu',action='store_true');parser.add_argument('--gpu-revision',type=int,default=1);args=parser.parse_args()
if args.enable_existing_gpu:
    source=J/'language-specific-adaptation-r1/prepared-r3/protocol.json';P=read(source)
    changes=[]
    for f in P['files']:
        current=sha(f['file'])
        if current!=f['sha256']:
            require(Path(f['file']).name in ('model_thermal_guard_20261117.py','tdt_domain_adaptation_20261116.py','run_owned_tdt_adaptation_20261117.py'),'Unexpected frozen input change: '+f['file'])
            changes.append({'file':f['file'],'before':f['sha256'],'after':current});f['sha256']=current
    P['thermal'].update(mode='observe-only',ownerAuthorizedObservationOnly=True,
        ownerQuote='这个为什么会有这个软件门栏呢？没有必要有这个东西啊。',maximumStartCelsius=None,stopCelsius=None)
    inspect_thermal_policy(P['thermal']);inspect(P)
    P.update(state='FROZEN_EXISTING_ENGLISH_ADAPTATION_GPU_WINDOW_NO_RECIPE_GRID',
        at=datetime.now().astimezone().isoformat(),stopAt=(datetime.now().astimezone()+timedelta(hours=4)).isoformat(),
        gpuExecutionEnabled=True,executionDisabledReasons=[],admissionSeconds=0,
        ownerComputeQuote='现在是插上显卡了',originalPreparedRecipe=str(source),controlledSourceChanges=changes,
        decisionBasis='Granite fixed113/709 does not qualify and its profile is ended. Existing publishedF32 Parakeet recipe1828train-only/participant-disjoint clips is retained unchanged. Measure real GPU loss/gradient/maximum-shape/roundtrip and cost before deciding whether one fixed epoch is feasible; no model/epoch/hyperparameter grid.')
    require(args.gpu_revision in (1,2),'Only the original run and diagnosed venv-supervisor fix are authorized profiles')
    target=J/('language-specific-adaptation-r1/prepared-gpu-evening20261117-r'+str(args.gpu_revision));target.mkdir(exist_ok=False)
    atomic_json(target/'protocol.json',P)
    old=read(J/'language-specific-adaptation-r1/prepared-r3/scoring-control.json')
    for key in list(old):
        if key.lower().startswith('protocol'):
            old[key]=sha(target/'protocol.json') if 'sha256' in key.lower() else str(target/'protocol.json')
    atomic_json(target/'scoring-control.json',old)
    print(json.dumps({'protocol':str(target/'protocol.json'),'state':P['state'],'examples':P['training']['examples'],
        'updates':P['training']['optimizerUpdates'],'stopAt':P['stopAt'],'controlledChanges':changes,'newTrainingUpdates':0}));raise SystemExit(0)
require(args.revision in ('r1','r2','r3'),'Explicit preserved preparation revision required')
out=J/('language-specific-adaptation-r1/prepared-'+args.revision);out.mkdir(exist_ok=False)
prior=read(J/'english-transducer-r1/protocol.json');old_score=read(J/'english-transducer-r1/scoring-control.json')
plan_path=J/('language-specific-adaptation-r1/expanded-data-r3/english-data-plan.json' if args.revision=='r3'
    else 'language-specific-adaptation-r1/english-data-plan.json');plan=read(plan_path)
examples=plan['examples'];updates=(examples+3)//4
checkpoint_every=32 if args.revision=='r3' else 8;checkpoint_first=args.revision=='r3'
if args.revision=='r3':
    assert examples==1828 and plan['independentIntegrityPassed']
    assert sha(plan['integrityReceipt'])==plan['integrityReceiptSha256']
validation=read(prior['audioOnly']);assert len(validation)==12
assert all(set(row)=={'id','audio','audioSha256','frames'} for row in validation)
audio=out/'validation-audio-only.json';audio.write_bytes(Path(prior['audioOnly']).read_bytes())
training=Path(plan['trainingManifest']);assert sha(training)==plan['trainingManifestSha256']
train_rows=[json.loads(line) for line in training.read_text(encoding='utf-8').splitlines() if line]
assert len(train_rows)==examples and len({r['id'] for r in train_rows})==examples
assert all(r['role']=='train-only' and r['language']=='English' for r in train_rows)
assert not ({r['id'] for r in train_rows}&{r['id'] for r in validation})
monitor=E/'system-restart-20261116-2315/laptop-thermal-r3'
thermal={'run':str(monitor),'sensorIdentifier':'/amdcpu/0/temperature/2',
    'maximumStartCelsius':85,'stopCelsius':95,'maximumSampleAgeSeconds':15,'cacheSeconds':1,
    'scope':'owned model worker only; no system power/fan/clock changes',
    'loggerSources':[{'file':str(monitor/n),'sha256':sha(monitor/n)}
        for n in ['monitor_thermal_20261117.py','read_laptop_thermal_stream_20261117.ps1']],
    'identifiedCpuTjmaxCelsius':100,'taskThresholdsAreNotHardwareLimitsOrRootCauseProof':True}
inspect_thermal_policy(thermal)
runtime_root=Path(prior['runtime']['python']).parents[1]/'Lib/site-packages'
paths=[Path(e['file']) for e in prior['files']]
paths+=[S/n for n in ['tdt_domain_adaptation_20261116.py','tdt_adaptation_checkpoint_20261116.py',
    'tdt_adaptation_contract_20261117.py','tdt_selected_loss_20261116.py','durable_model_state_20261117.py',
    'model_thermal_guard_20261117.py','run_owned_tdt_adaptation_20261117.py','companion_gpu_execution_20261116.py']]
paths += [audio,plan_path,training,runtime_root/'transformers/loss/loss_tdt.py',
    runtime_root/'torch/optim/adamw.py',runtime_root/'torch/utils/checkpoint.py']
paths += [Path(item['file']) for item in thermal['loggerSources']]
if args.revision=='r3':paths += [Path(plan['integrityReceipt'])]
files=[{'file':str(path),'sha256':sha(path),'bytes':path.stat().st_size} for path in dict.fromkeys(paths)]
protocol={'state':'FROZEN_OFFLINE_ENGLISH_ADAPTATION_PREPARATION_GPU_DISABLED_ORIGINAL_WINDOW_EXPIRED',
    'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'modelRoot':prior['modelRoot'],'weights':prior['weights'],'runtime':prior['runtime'],'blas':prior['blas'],
    'dataPlan':str(plan_path),'validationAudioOnly':str(audio),'neuralLock':prior['neuralLock'],
    'minimumAvailableBytes':prior['minimumAvailableBytes'],'minimumDiskFreeBytes':50*1024**3,
    'checkpointBudgetBytes':32*1024**3,'cpuPercent':25,'privateMemoryLimitBytes':2*1024**3,
    'stopAt':prior['stopAt'],'gpuExecutionEnabled':False,
    'executionDisabledReasons':['Original overnight window ended; no automatic extension',
        'Second system restart left sustained GPU compatibility unproven',
        'A new valid execution window and fresh owned CPU-temperature logger must be frozen before execution'],
    'thermal':thermal,'training':{'epochs':1,'learningRate':1e-5,'optimizer':'AdamW','betas':[.9,.999],
        'weightDecay':.01,'epsilon':1e-8,'gradientAccumulationExamples':4,'gradientClipNorm':1.,'seed':20261116,
        'examples':examples,'optimizerUpdates':updates,'checkpointEveryUpdates':checkpoint_every,
        'checkpointAtFirstUpdate':checkpoint_first,'noValidationCheckpointSelection':True},
    'sequence':['baseline12','native/scalar/selected/chunked GPU gradient proof',
        'largest real joint and longest real example with steady Adam storage; one disposable update',
        'GPU tensor/Adam/integer/RNG checkpoint destructive roundtrip',
        'fresh original factory initialization','one fixed training epoch or exact explicit checkpoint resume',
        'final'+str(updates)+'-update checkpoint validation12','independent original-reference paired score'],
    'gpuProfile':{'publishedFloat32':True,'cudnnDisabled':True,'allocatorFraction':.5,
        'leafOperatorSynchronization':True,'jointChunkFrames':16,'hardGpuPowerOrTemperatureCap':False,
        'longTermCompatibilityEstablished':False},
    'validationScope':'Same12 exposed nonoverlap English clips; not blind, not whole-meeting, not speaker identity',
    'chineseTrainingIncluded':False,'qualityQualified':False,'saleQualified':False,'files':files}
schedule=[u for u in range(1,updates+1) if checkpoint_due(u,updates,every=checkpoint_every,first=checkpoint_first)]
# Keep the original32GiB checkpoint budget. The expanded epoch stores an early
# recovery point, then every32updates and the final checkpoint; no old files are
# deleted, no budget increased, and no checkpoint is selected by validation.
from meeting_acoustic_contract_20261116 import tensor_header
header,_=tensor_header(Path(plan['modelRoot'])/protocol['weights']['file'] if not Path(protocol['weights']['file']).is_absolute() else protocol['weights']['file'])
import math
buffer_bytes=sum(math.prod(header[n]['shape'])*4 for n in plan['allowedMutableBufferNames'] if header[n]['dtype']=='F32')
payload_upper=plan['trainableParameters']*12+buffer_bytes+1024**2
require(len(schedule)*payload_upper<protocol['checkpointBudgetBytes'],'Fixed epoch exceeds original checkpoint budget')
protocol['checkpointStoragePlan']={'checkpointUpdates':schedule,'maximumCandidateFullCheckpoints':len(schedule),
    'payloadUpperBoundBytesIncluding1MiBMetadata':payload_upper,
    'candidateCheckpointBytesUpperBound':len(schedule)*payload_upper,
    'original32GiBBudgetRetained':True,'automaticDeletion':False,
    'preflightCheckpointIsSeparateDisposableRun':True}
protocol_path=out/'protocol.json';atomic_json(protocol_path,protocol)
inspect(protocol)
scorer=S/'score_tdt_adaptation_20261117.py'
score_files=[protocol_path,scorer,S/'score_sequential_meetings_20261115.py',
    S/'tdt_adaptation_contract_20261117.py',S/'tdt_adaptation_checkpoint_20261116.py',
    S/'meeting_acoustic_contract_20261116.py',S/'durable_model_state_20261117.py',
    Path(old_score['references']),Path(old_score['qwenBaseline']),Path(old_score['mossBaseline']),
    S/'tdt_domain_adaptation_20261116.py',plan_path]
control={'protocol':str(protocol_path),'worker':str(S/'tdt_domain_adaptation_20261116.py'),
    'references':old_score['references'],'qwenBaseline':old_score['qwenBaseline'],'mossBaseline':old_score['mossBaseline'],
    'admissionGate':{'referenceWords':709,'maximumEnglishErrors':99,
        'minimumRelativeErrorReductionVsSameProfileBaseline':.2,'eachMeetingAtMostSameProfileAndPriorMossErrors':True,
        'actionIfPass':'Complete-source validation only; no deployment, no product qualification',
        'actionIfFail':'Retain and reject; no learning-rate/epoch/checkpoint/model grid'},
    'files':[{'file':str(path),'sha256':sha(path)} for path in score_files]}
control_path=out/'scoring-control.json';atomic_json(control_path,control)
require('torch' not in sys.modules,'CPU preparation imported a neural runtime')
report={'state':'PASS_OFFLINE_TDT_RECIPE_AND_REFERENCE_SEPARATION_GPU_EXECUTION_DISABLED',
    'at':datetime.now().astimezone().isoformat(timespec='seconds'),'protocol':str(protocol_path),
    'protocolSha256':sha(protocol_path),'scoringControl':str(control_path),'scoringControlSha256':sha(control_path),
    'examples':examples,'plannedOptimizerUpdates':updates,'trainableParameters':118886022,'trainingUpdates':0,'newNeuralCalls':0,
    'validationAudioOnlyKeys':['id','audio','audioSha256','frames'],
    'scoringReferenceManifestIncludedInGpuFiles':any(Path(e['file'])==Path(control['references']) for e in protocol['files']),
    'originalWindowExtended':False,'gpuExecutionEnabled':False,'torchImported':False,
    'lossGradientLargestShapeAndGpuCheckpointProven':False,'qualityQualified':False,'saleQualified':False,
    'limits':limits.query()}
assert not report['scoringReferenceManifestIncludedInGpuFiles']
atomic_json(out/'intake.json',report);print(json.dumps(report,ensure_ascii=False))
