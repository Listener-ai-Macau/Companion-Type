"""Reconcile the existing English adaptation phase into the original workpoint."""
from pathlib import Path
from datetime import datetime
import argparse,json,sys,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from durable_model_state_20261117 import read_snapshot
ap=argparse.ArgumentParser();ap.add_argument('--phase',required=True);args=ap.parse_args()
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1')
run=E/'gpu-owned-evening20261117-r2';C=E/'english-accuracy-reference-20261117'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
file=run/args.phase/'state.json';state,selection=read_snapshot(file)
identity=read(run/('supervisor-'+args.phase)/'worker-identity.json')
alive=psutil.pid_exists(identity['pid']) and abs(psutil.Process(identity['pid']).create_time()-identity['createdAt'])<.01
xfile=Path('work/bilingual_progress.json');x=read(xfile);j=x['jointArchitecture20261115'];o=j['overnightExecution20261116']
policy=x['ownerRuntimePolicy20261117']
if 'dedicatedGpuTrainingMemory20261117' not in policy:
 policy['dedicatedGpuTrainingMemory20261117']=dict(ownerQuotes=['训练的时候显存可以多用点, 最多用16g','仅限有独显的时候'],
  maximumDedicatedVramBytes=16*1024**3,requiresActualDedicatedGpuSelected=True,
  integratedGpuSharedMemoryLimitChanged=False,cpuPrivateMemoryLimitChanged=False,
  currentFixedEpochAllocationPolicyRetained=True,
  reason='Current fixed epoch uses about4.6GB and has not hit its8GiB allocator cap. Apply the newly authorized ceiling to later dedicatedGPU recipes; it does not enlarge integratedGPU shared RAM or CPU private commit.')
at=datetime.now().astimezone().isoformat(timespec='seconds')
proof=state.get('maximumShapeProofs',[])
trained_examples=state['completedTrainingExamples']
if args.phase=='validate' and (run/'training-completed.json').exists():
 trained_examples=read(run/'training-completed.json')['completedTrainingExamples']
execution=dict(phase=args.phase,state=state['state'],observedAt=state['observedAt'],aliveWhenObserved=alive,
 workerIdentity=identity,stateFile=str(file),run=str(run),parameterUpdates=state['parameterUpdates'],
 candidateOptimizerUpdates=state['candidateOptimizerUpdates'],completedTrainingExamples=trained_examples,
 maximumShapeProofs=proof,checkpointExactRoundtrip=state.get('checkpointExactRoundtrip'),
 supervisorResult=read(run/('supervisor-'+args.phase)/'completed.json') if (run/('supervisor-'+args.phase)/'completed.json').exists() else None)
if (run/'resume-1/state.json').exists():
 failed=read(run/'train/state.json');resumed=read(run/'resume-1/state.json')
 execution['checkpointRecovery']=dict(originalFailureFile=str(run/'train/state.json'),
  originalFailure=failed.get('error'),originalObservedUpdates=failed['parameterUpdates'],
  restoredCommittedUpdates=416,restoredCommittedExamples=1664,
  uncommittedUpdatesDiscarded=failed['parameterUpdates']-416,
  recoveryStateFile=str(run/'resume-1/state.json'),recoveryState=resumed['state'],
  recoveryUpdatesThisProcess=resumed['parameterUpdates'],
  actualObservedTrainingUpdateAttempts=failed['parameterUpdates']+resumed['parameterUpdates'],
  recipeDataOrderOptimizerAndRngUnchanged=True,automaticRetry=False)
batch=j['runtimeOptimization20261117'];batch.update(at=at,graniteErrorAttribution=str(C/'granite-error-attribution.json'),
 graniteDecision='Retired fixed113/709 profile: only4of71deletions are explicit fillers;67other deletions. At9.33x the prior Parakeet inference time,10fewer errors do not qualify this candidate. No prompt/dtype/decoder grid.',
 existingEnglishAdaptation=execution,
 supervisorSourceFix='Windows venv redirector PID differs from actualPython child. Bind only exact-script/argument descendant plus creation time and executable; outside tree rejection and real child completion verified.',
 supervisorLiveRegression=str(C/'venv-supervisor-regression-r1/result.json'))
a=o['languageSpecificAdaptation20261116'];a['eveningGpuExecution20261117']=execution
a['trainingStarted']=state['candidateOptimizerUpdates']>0;a['trainingUpdates']=state['candidateOptimizerUpdates']
a['state']=state['state']
x['modelWeightsChanged']=state['candidateOptimizerUpdates']>0
x['modelWeightsChangedScope']='Isolated experimental selected-parameter checkpoint only; published base files and installed product defaults are unchanged.'
x['baseModelWeightsChanged']=False;x['shippedDefaultWeightsChanged']=False
x['newOptionalAdapterWeightsCreated']=(run/'checkpoints/latest-checkpoint.json').exists()
x['optionalAdapterAdoptedInProduct']=False
o['currentOwnedNeuralWorker']=dict(pid=identity['pid'],createdAt=identity['createdAt'],stateFile=str(file)) if alive else None
x['state']='EXISTING_ENGLISH_ADAPTATION_'+args.phase.upper()+('_RUNNING' if alive else '_TERMINAL_RETAINED')
x['next']='Follow this fixed existing1828clip one-epoch recipe only after real GPU gradient/maximum-shape/checkpoint proof and measured cost. Keep the final5/2percent gates, original references and independent final assessment. No further Granite candidate variations.'
if args.phase=='train' or args.phase.startswith('resume-'):
 x['next']='Complete the fixed1828sample/457update epoch, then let the prepared followup validate only its exact final checkpoint and independently score the original12/709words. After shared GPU work finishes, execute the preparedCPU-only bilingual existing-model probe. No intermediate-checkpoint selection or changed-parameter retry.'
scorefile=run/'paired-score.json'
waiting=run/'finish-evaluation-shared-lease-r1/state.json'
if waiting.exists():
 queue=read(waiting)
 batch['sharedEvaluationAdmission']=dict(file=str(waiting),**queue)
if waiting.exists() and not scorefile.exists():
 x['state']='FIXED_ENGLISH457_COMPLETE_WAITING_SHARED_RESOURCE_EVALUATION'
 x['next']='Final457 checkpoint is durable. Identified minutes-model job owns the shared neural lease; wait for it to finish, preserve zero-inference validation admission failure, then evaluate the same final checkpoint and execute the preparedCPU probe. Do not kill or alter the other job.'
if scorefile.exists():
 score=read(scorefile)
 assert score['candidateOptimizerUpdates']==457 and score['trainingExamples']==1828
 a['eveningGpuScore20261117']=dict(file=str(scorefile),state=score['state'],baselineErrors=score['baselineErrors'],
  candidateErrors=score['candidateErrors'],referenceWords=709,candidateWer=score['candidateWer'],
  advanceToCompleteSources=score['advanceToCompleteSources'],relativeErrorReduction=score['relativeErrorReductionVsSameProfileBaseline'],
  wholeSourceQualified=False,speakerQualified=False,qualityQualified=False,saleQualified=False)
 batch['pairedEnglishAdaptationResult']=a['eveningGpuScore20261117']
 x['state']='FIXED_ENGLISH_ONE_EPOCH_SCORED_WHOLE_VALIDATION_PENDING' if score['advanceToCompleteSources'] else 'FIXED_ENGLISH_ONE_EPOCH_REJECTED_PAIRED_ADMISSION_RETAINED'
 x['next']='Run original complete English source and CPU/export validation of this exact final checkpoint; do not promote or claim5percent/2percent/whole-person qualification.' if score['advanceToCompleteSources'] else 'Retain and end this fixed one-epoch recipe, without another learning-rate/epoch/checkpoint grid. Complete the prepared existingCPU bilingual probe and use the measured error/cost gap to choose the next substantive route.'
marker='EXISTING_ENGLISH_TRAINING_GPU_20261117'
text=f'\n\n{at}｜{marker}｜Granite完整原12条113/709=15.9379%WER；较Parakeet123少10错，但其164.893秒较17.667秒慢9.33倍，未过中间门，结束该候选固定配方。错误分解34替换/71漏/8增；明确语气词漏4、其它漏67，不能靠补语气词达到5%。转回此前已备好且从未完成ASR更新的原Parakeet会议适配：1828条4.18h、人物/来源与验证隔离、119M可训参数、固定1轮457更新不改。r1启动监督器错误地要求Windows虚拟环境启动器PID等于真实工作PID，实际19612→3400，0模型前向/更新即父作业退出；现场与旧源码保留。源头修为创建时间+精确参数+已启动进程树内真实Python身份，实际虚拟环境子进程完成和外树拒绝验证通过。r2完整12条同配方未训基线已实际完成，现{args.phase}状态{state["state"]}，参数更新{state["parameterUpdates"]}/候选更新{state["candidateOptimizerUpdates"]}/训练样本{trained_examples}，真实活性{alive}；最大实样本及梯度/恢复结果见原收据。原2GiB私有/25%CPU/低内存保护保持，原85/95任务温度门依Owner已取消只观察；当前有效窗口至2026-11-18约00:12，不使用已过期07:25门。预检更新是一次丢弃副本，不作为候选训练或质量提高。没有把原最终留出集打开或改原评分。'
if scorefile.exists():
 text+=f' 一轮457正式更新与最终检查点12条验证均完整；独立原评分{score["baselineErrors"]}→{score["candidateErrors"]}/709错，候选WER{score["candidateWer"]*100:.4f}%，配对中间门通过{score["advanceToCompleteSources"]}。原5/2percent、整会/逐人/事实与客户CPU交付门不变，未改当前默认模型。'
if execution.get('checkpointRecovery'):
 recovery=execution['checkpointRecovery']
 text+=f' 21:41原训练因整机RAM保护停止于433更新，原失败保留；内存恢复后明确从已提交416更新/1664样本连同Adam/随机状态恢复，未提交17步重算，不改数据/学习率/轮数/终点。恢复过程实际更新{recovery["recoveryUpdatesThisProcess"]}，累计可观察训练更新尝试{recovery["actualObservedTrainingUpdateAttempts"]}，与最终候选有效更新数分开。'
if (run/'finish-evaluation-shared-lease-r1/admission-recovery.json').exists():
 text+=' 最终验证初次在导入Torch/加载权重之前因另一纪要作业持有共享模型锁而退出，0神经调用/更新；原空结果目录、监督器错误及进程身份均移入原run的lock-admission-failed-r1目录保留。等待该已识别作业实际退出/锁释放后，仅重做同一最终457检查点评估准入，不改原协议/权重/参考。'
if marker in x['logResult']:
 pos=x['logResult'].index(marker);start=x['logResult'].rfind('\n\n',0,pos);end=x['logResult'].find('\n\n',pos)
 x['logResult']=x['logResult'][:start]+text+(x['logResult'][end:] if end>=0 else '')
else:x['logResult']+=text
if 'OWNER_DEDICATED_VRAM_BUDGET_20261117' not in x['logResult']:
 x['logResult']+='\n\n'+at+'｜OWNER_DEDICATED_VRAM_BUDGET_20261117｜Owner“训练的时候显存可以多用点, 最多用16g”“仅限有独显的时候”：最高16GiB仅限实际选中独显的训练，CPU私有内存/核显共享内存预算不随之扩大。当前固定一轮实用约4.6GB，原8GiB分配上限未触发，本轮保持固定配方；后续需要更多显存的独显配方可按新上限准备。'
xfile.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':x['state'],'worker':state['state'],'alive':alive,'parameterUpdates':state['parameterUpdates'],'candidateOptimizerUpdates':state['candidateOptimizerUpdates'],'completedTrainingExamples':state['completedTrainingExamples']},ensure_ascii=False))
