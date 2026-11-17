"""Fresh bounded 780M inference; explicit owner CPU observation policy applies."""
from pathlib import Path
from datetime import datetime,timedelta
import argparse,hashlib,json,shutil,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
sys.path.insert(0,str(S))
from model_thermal_guard_20261117 import ThermalGuard
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--attempt',choices=['r2','r3'],default='r2');args=parser.parse_args()
C=J/('igpu-native8-'+args.attempt);run=E/C.name;assert not C.exists() and not run.exists();C.mkdir()
P=read(J/'igpu-native8-r1/protocol.json');B=read(J/'igpu-native8-r1/binding.json')
logger=E/'system-restart-20261116-2315'/('igpu-native8-owner-observe-thermal-r3' if args.attempt=='r3' else 'igpu-native8-owner-resume-thermal-r2')
thermal=P['thermal'];thermal['run']=str(logger);thermal['loggerSources']=[]
if args.attempt=='r3':
    thermal.update(mode='observe-only',maximumStartCelsius=None,stopCelsius=None,
        ownerAuthorizedObservationOnly=True,
        ownerQuote='这个为什么会有这个软件门栏呢？没有必要有这个东西啊。')
for name in ['monitor_thermal_20261117.py','read_laptop_thermal_stream_20261117.ps1']:
    p=Path('work')/name;q=logger/name;shutil.copyfile(p,q)
    thermal['loggerSources'].append({'file':str(q),'sha256':sha(q)})
at=datetime.now().astimezone();P.update(frozenAt=at.isoformat(),thermal=thermal,
    workerSourceSha256=sha(S/'native8_780m_inference_20261117.py'),
    helperSources=[{'file':x['file'],'sha256':sha(x['file'])} for x in P['helperSources']],
    probabilityCacheRoot=str(run/'probabilities'),stopAt=(at+timedelta(minutes=15)).isoformat(),
    ownerIntegratedGpuPermission={'quote':'你为什么一定要依赖独显可用呢？用的核显先呗。',
        'scope':'780M inference/correctness/composition. NoCPU/noIntegratedGPU training and original memory/CPU/time guards; owner explicitly changed CPU temperature to observation only for r3.'})
assert P['backend']=='vulkan-780m' and P['workerSourceSha256']==sha(S/'native8_780m_inference_20261117.py')
B.update(at=at.isoformat(),priorControl=str(J/'igpu-native8-r1'),
    ownerResumedExplicit780mInference=True,priorFailureWasPreModelThermalAdmissionNotBackendUnsupported=True,
    automaticRetry=False,originalAcceptanceMetricsChanged=False,
    failureSnapshotOnlySourceFix='Carry actual triggering CPU thermal observation through the exception; native model, weights, geometry and quality gates unchanged.',
    cpuTemperatureMode=thermal.get('mode','enforce'))
for name,value in [('protocol.json',P),('binding.json',B),('audio-only.json',read(J/'igpu-native8-r1/audio-only.json'))]:
    (C/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
guard=ThermalGuard(thermal)
try:observed=guard.check(starting=True);ready=True;error=None
except Exception as e:observed=getattr(e,'observation',None);ready=False;error=repr(e)
receipt={'at':at.isoformat(),'control':str(C),'run':str(run),'logger':str(logger),
    'readyForOriginal60SecondAdmission':ready,'cpuObservation':observed,'error':error,
    'newNeuralCalls':0,'parameterUpdates':0,'training':False,
    'cpuTemperatureMode':thermal.get('mode','enforce'),
    'originalMemoryCpuAndQualityGatesChanged':False}
(C/'preparation.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');x=read(p);o=x['jointArchitecture20261115']['overnightExecution20261116']
o['ownerResumedIntegratedGpu20261117']=receipt
o['requiredModelExecutionDependency20261117']['resumedAt']=at.isoformat()
o['requiredModelExecutionDependency20261117']['resumedBlockedAuditCount']=0
x['at']=at.isoformat();x['state']='OWNER_RESUMED_EXPLICIT_780M_INFERENCE_PREPARATION'
x['next']='Owner要求先用780M并移除本任务CPU温度85/95软件门槛、保留只读观测；先同已保留61秒原音/同FP16权重验证Vulkan推理，保留CPU/核显不训练及原2GiB/CPU5%/低RAM/60秒RAM准入/有界时限。过固定后验比较后才进入同模型固定原会组合验证；不将独显训练依赖扩大为所有模型工作受阻。'
x['logResult']+='\n\n'+at.isoformat()+'｜Owner恢复Goal并明确先用核显。780M推理/对比优先，原CPU/核显训练禁令保留；原blocked解除，阻塞审计重新计数。此前把下一训练步与全模型工作绑定过窄，本轮用已备Vulkan显式780M路径。原第一次尝试是在模型加载前温度准入停止，不能据此断言780M不支持。新只读传感与原61秒CPU控制/FP16权重/原后验容差重新冻结，15分钟有界；原内存/CPU预算、参考和严格6800选择器不改，不新增驱动/系统设置。当前CPU温度模式为'+thermal.get('mode','enforce')+'，r3按Owner最新指示移除本任务85/95温度中止门槛而保留观测，旧协议只作历史。'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False))
