"""Close the pinned ASR feasibility audit; keep existing model evidence distinct."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib,json,struct

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
A=E/'language-specific-adaptation-r1/native-vulkan-port-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,o):
    Path(p).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

refs=read(Path(__file__).with_name('native_vulkan_primary_refs_20261117.json'))
tree=read(A/'nemo-v030-tree.json')
assert tree['sha']=='20999cc921d2b14aa58708f61756a8b2e787ba20' and not tree['truncated']
submodule=next(x for x in tree['tree'] if x['path']=='vendor/llama.cpp') if any(x['path']=='vendor/llama.cpp' for x in tree['tree']) else next(x for x in tree['tree'] if x['type']=='commit' and 'llama' in x['path'])
assert submodule['sha']=='bd4f514db14d87fded667787a7a963bfbaa98e89'
weights=Path('E:/CodexData/Companion/.model-cache/english-transducer-official20261116/model.safetensors')
with weights.open('rb') as f:
    length=struct.unpack('<Q',f.read(8))[0]
    header=json.loads(f.read(length))
counts=dict(Counter(v['dtype'] for k,v in header.items() if k!='__metadata__'))
assert counts=={'F32':699,'I64':24} and weights.stat().st_size==2508311120
converter=Path('E:/CodexData/Companion/.model-cache/nemotron-speaker-20261107/conversion-source/conversion/asr.py')
incident=read(E/'system-restart-20261116-2315/incident.json')
at=datetime.now().astimezone().isoformat(timespec='seconds')
report={
 'at':at,'state':'PINNED_NATIVE_ENGLISH_FP32_PORT_REQUIRES_ENGINE_CHANGES_DEFERRED_BEFORE_QUALITY_ADMISSION',
 'model':{'repository':'nvidia/parakeet-tdt-0.6b-v3','revision':'541d1f99c6b0c3cd0b11a95167540bb8edefd82b',
    'localWeightBytes':weights.stat().st_size,'headerTensorDtypes':counts,
    'localHeaderSha256':hashlib.sha256(json.dumps(header,sort_keys=True).encode()).hexdigest(),
    'selectedFrozenProfile':'Original published FP32; no dtype conversion admitted by the original asset contract.',
    'existingFixedTwelveEnglishErrors':123,'existingFixedTwelveEnglishReferenceWords':709,
    'existingDirectQualityAdmissionPassed':False,'roleRetained':'One supervised adaptation base; not promoted to a qualified product model.'},
 'nativeRuntime':{'repository':'NVIDIA/NeMo-Speech.cpp','ref':'v0.3.0','treeSha':tree['sha'],
    'llamaSubmoduleRevision':submodule['sha'],'cachedConverterSha256':sha(converter),'primaryReferences':refs,
    'findings':[
       'Cached official converter forces convolution and embedding tensors to F16 even when general weight_type is f32.',
       'Native Conv1D declarations use F16 for depthwise and non-pointwise kernels; Session::load_weight converts F32 disk tensors to F16 memory tensors for these declarations.',
       'The pinned GGML depthwise1D/2D convolution graphs request F16 im2col for F32 kernels; a custom all-F32 export alone would not preserve the original execution profile.',
       'A native FP32 port would require converter mapping, runtime tensor declarations and convolution graph/backend verification, plus tokenizer/frontend equivalence. Stock runtime support for model family is not evidence of this exact profile.'
    ],
    'decision':'Defer a substantial native-engine FP32 port until the selected English model has accuracy-bearing adaptation evidence. Do not silently substitute Q8/FP16, launch a precision grid or treat file export as accuracy improvement.',
    'buildStarted':False,'convertedWeightsWritten':False,'asrNeuralCalls':0,'cpuOrIntegratedGpuTraining':False},
 'rebootReview':{'existingIncident':str(E/'system-restart-20261116-2315/incident.json'),
    'existingIncidentSha256':sha(E/'system-restart-20261116-2315/incident.json'),
    'lastIncidentWasInferenceNotTraining':incident['trainingParameterUpdates']==0 and not incident['english119MTrainingStarted'],
    'observedReservedPeakGiB':incident['observedGpuReservedPeakGiB'],
    'lastObservedDriverFreeGiB':incident['lastObservedDriverFreeGiB'],
    'lastObservedSystemAvailableGiB':incident['lastObservedSystemAvailableGiB'],
    'samplesAreNotCrashInstant':True,'rootCauseIdentified':False,
    'priority':'Compute runtime/driver/USB4 externalGPU path. Games or graphics benchmarks passing do not qualify the separate compute workload.',
    'cpuThermalCauseExcluded':False,'cpuTemperatureTaskPolicy':'observe-only; no 85/95 software admission or abort threshold',
    'systemThermalDriverTdrPowerBiosSettingsChanged':False,
    'repeatUnchangedFailingOvernightBatch':False,
    'nextExternalGpuComparison':'Use one frozen short input and model, durable stage/operator/device/memory journal, and one changed execution condition. The already prepared graphics-driver comparison is separate and not yet installation-authorized.'},
 'metadataEvidence':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in A.glob('*.json')},
 'qualityQualified':False,'saleQualified':False,'newWeightTraining':False,
 'finalHoldoutOpened':False,'productDefaultChanged':False,
 'next':'Return to the accuracy-bearing non-overlap bilingual path: one frozen English specialist adaptation and independent paired/whole-source validation; reject it if the predeclared improvement and no-regression gates fail. DedicatedGPU training is separate from daytime780M inference. Keep proven780M speaker inference available for justified component work, but do not substitute app integration, native-engine porting, genericVAD or parameter grids for word/speaker accuracy. CPU temperature remains observation-only.'}
target=J/'language-specific-adaptation-r1/native-vulkan-source-audit-20261117.json'
assert not target.exists()
write(target,report)
progress=Path('work/bilingual_progress.json');x=read(progress);o=x['jointArchitecture20261115']['overnightExecution20261116']
o['nativeEnglishVulkanFeasibility20261117']={'state':report['state'],'receipt':str(target),'exactStockFp32PathProven':False,
   'engineBuildDeferredBeforeQualityEvidence':True,'newAsrNeuralCalls':0,'newParameterUpdates':0}
dep=o['requiredModelExecutionDependency20261117']
dep.setdefault('historicalExternalConditionBeforeOwnerCpuPolicy',dep['externalCondition'])
dep['externalCondition']='Last owner-confirmed daytime discreteGPU state is undocked.780M Vulkan speaker inference is actually proven. CPU temperature is observation-only by current owner policy. CPU/integratedGPU training remains prohibited; no whole-task dependency on discreteGPU.'
dep['resumeFrom']='Use proven780M for inference/integration. DedicatedGPU training requires a fresh bounded execution window with original RAM/private-memory/CPU/time guards; CPU temperature stays observation-only. No automatic graphics-driver installation or unchanged failing long run.'
o['currentOwnedNeuralWorker']=None
o['currentWorkerState']='NO_OWNED_NEURAL_DATA_TEMPERATURE_OR_BUILD_WORKER'
x['at']=at;x['next']=report['next']
x['logResult']+='\n\n'+at+'｜固定英语底座原生Vulkan可行性审视结束：本机Parakeet原权重699F32+24I64/2508311120B，沿已固定官方修订。v0.3.0官方转换器的f32选项仍把卷积/embedding改F16；原生Conv1D声明及Session加载也会将F32卷积降F16；其固定GGML子模块的F32卷积仍选F16 im2col。因此不是简单改格式就保留原FP32配方，需转换/声明/算子多层修复与前端验证。未构建引擎/写新权重/作ASR神经调用，不再把此高成本部署移植置于英语模型质量证据之前；不偷换Q8/FP16或重开量化网格。核显已证明的说话人组件保留可执行；Owner问是否正常方向承接为回到非重叠中英文质量主线：既有一次固定英语专用底座适配及独立整会/逐人复核，不把部署接线、底层移植、报告或VAD网格当准确率改善。适配未实际完成，不承诺能达到95/98。重启旧现场复核为推理且0训练更新，显存预留峰3.7559GiB/最后驱动空闲11.9805GiB/系统可用9.9514GiB；不是死机瞬间，既不证明OOM也不排除驱动/USB4/供电/热原因。CPU85/95门槛沿Owner最新仅观察，同时更正旧依赖字段里尚残留的历史温控恢复描述；不动系统温控/驱动/TDR。游戏压测稳定支持优先查不同计算路径，不能认定具体显卡服务或驱动已定位。收据'+str(target)+'。'
write(progress,x)
print(json.dumps({'receipt':str(target),'newAsrNeuralCalls':0,'newParameterUpdates':0,'engineBuildStarted':False,'cpuTemperaturePolicy':'observe-only','sourceCommitUnchanged':True},ensure_ascii=False))
