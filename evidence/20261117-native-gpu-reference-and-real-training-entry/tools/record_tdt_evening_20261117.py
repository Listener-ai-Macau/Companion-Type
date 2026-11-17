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
at=datetime.now().astimezone().isoformat(timespec='seconds')
proof=state.get('maximumShapeProofs',[])
execution=dict(phase=args.phase,state=state['state'],observedAt=state['observedAt'],aliveWhenObserved=alive,
 workerIdentity=identity,stateFile=str(file),run=str(run),parameterUpdates=state['parameterUpdates'],
 candidateOptimizerUpdates=state['candidateOptimizerUpdates'],completedTrainingExamples=state['completedTrainingExamples'],
 maximumShapeProofs=proof,checkpointExactRoundtrip=state.get('checkpointExactRoundtrip'),
 supervisorResult=read(run/('supervisor-'+args.phase)/'completed.json') if (run/('supervisor-'+args.phase)/'completed.json').exists() else None)
batch=j['runtimeOptimization20261117'];batch.update(at=at,graniteErrorAttribution=str(C/'granite-error-attribution.json'),
 graniteDecision='Retired fixed113/709 profile: only4of71deletions are explicit fillers;67other deletions. At9.33x the prior Parakeet inference time,10fewer errors do not qualify this candidate. No prompt/dtype/decoder grid.',
 existingEnglishAdaptation=execution,
 supervisorSourceFix='Windows venv redirector PID differs from actualPython child. Bind only exact-script/argument descendant plus creation time and executable; outside tree rejection and real child completion verified.',
 supervisorLiveRegression=str(C/'venv-supervisor-regression-r1/result.json'))
a=o['languageSpecificAdaptation20261116'];a['eveningGpuExecution20261117']=execution
a['trainingStarted']=state['candidateOptimizerUpdates']>0;a['trainingUpdates']=state['candidateOptimizerUpdates']
a['state']=state['state']
o['currentOwnedNeuralWorker']=dict(pid=identity['pid'],createdAt=identity['createdAt'],stateFile=str(file)) if alive else None
x['state']='EXISTING_ENGLISH_ADAPTATION_'+args.phase.upper()+('_RUNNING' if alive else '_TERMINAL_RETAINED')
x['next']='Follow this fixed existing1828clip one-epoch recipe only after real GPU gradient/maximum-shape/checkpoint proof and measured cost. Keep the final5/2percent gates, original references and independent final assessment. No further Granite candidate variations.'
marker='EXISTING_ENGLISH_TRAINING_GPU_20261117'
text=f'\n\n{at}｜{marker}｜Granite完整原12条113/709=15.9379%WER；较Parakeet123少10错，但其164.893秒较17.667秒慢9.33倍，未过中间门，结束该候选固定配方。错误分解34替换/71漏/8增；明确语气词漏4、其它漏67，不能靠补语气词达到5%。转回此前已备好且从未完成ASR更新的原Parakeet会议适配：1828条4.18h、人物/来源与验证隔离、119M可训参数、固定1轮457更新不改。r1启动监督器错误地要求Windows虚拟环境启动器PID等于真实工作PID，实际19612→3400，0模型前向/更新即父作业退出；现场与旧源码保留。源头修为创建时间+精确参数+已启动进程树内真实Python身份，实际虚拟环境子进程完成和外树拒绝验证通过。r2完整12条同配方未训基线已实际完成，现{args.phase}状态{state["state"]}，参数更新{state["parameterUpdates"]}/候选更新{state["candidateOptimizerUpdates"]}/训练样本{state["completedTrainingExamples"]}，真实活性{alive}；最大实样本及梯度/恢复结果见原收据。原2GiB私有/25%CPU/低内存保护保持，原85/95任务温度门依Owner已取消只观察；当前有效窗口至2026-11-18约00:12，不使用已过期07:25门。预检更新是一次丢弃副本，不作为候选训练或质量提高。没有把原最终留出集打开或改原评分。'
if marker in x['logResult']:
 start=x['logResult'].rfind('\n\n',0,x['logResult'].index(marker));x['logResult']=x['logResult'][:start]+text
else:x['logResult']+=text
xfile.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':x['state'],'worker':state['state'],'alive':alive,'parameterUpdates':state['parameterUpdates'],'candidateOptimizerUpdates':state['candidateOptimizerUpdates'],'completedTrainingExamples':state['completedTrainingExamples']},ensure_ascii=False))
