from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1';C=BASE/'cpu-pcm-candidate-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=Path('work/bilingual_progress.json');d=read(p);o=d['ownerOvernightRun20261115'];at=datetime.now().astimezone().isoformat()
d['jointArchitecture20261115']['cpuNoDiscreteProductCandidate20261116']={'at':at,'state':'CPU_ONLY_PCM_CANDIDATE_PREPARED_ACTUAL_NEURAL_INTEGRATION_PENDING',
 'control':str(C),'bindingSha256':sha(C/'binding.json'),'runtimeCpuBytes':12586370,'modelSha256':read(C/'binding.json')['model']['sha256'],
 'parsedReal32OutputsExactly':str(C/'parser-control.json'),'durableSourceAndSchedulingControl':str(C/'scheduler-control.json'),
 'actualBilingualDualRouteProtocol':str(C/'dualroute-protocol.json'),'actualBilingualDualRouteScript':'work/run_cpu_pcm_dualroute_20261116.py',
 'actualNeuralIntegrationExecuted':False,'cpuOnlyOptionalVulkanPluginOmitted':True,'sourceAudioUploaded':False,'productDefaultChanged':False,'qualityQualified':False,
 'next':'After the current single-family full4 ASR and original whole scoring, run CPU-only native8 control/full4, then the fixed75.25s English/Chinese real paced ingress vs offline CPU integration. Keep facts/card/Android/sale gates open.'}
o.update(currentCpuSpeakerControl=str(BASE/'cpu-native8-r1'),currentCpuSpeakerRun='E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/cpu-native8-r1',
 cpuSpeakerRuntimeState='PREPARED_NOT_EXECUTED_WAITING_SINGLE_NEURAL_FAMILY')
d['next']='16:00截止/15:40神经截止保持。CPU25%/4线程、2GiB私有/真实低RAM保护内，原4完整录音固定30s分块已完成前两场输入，继续第二英文/复杂中文，不重跑39条恢复前结果。顺序完成全会组合/原门评分→同原native8 FP16显式CPU-only 61s C ABI/官方CLI控制与4整会→同75.25s中英公开原音真实定速增量/离线接口。CPU接口独立候选已去可选Vulkan插件且保留CPU原字节，不改现有安装包；技术parser/接收调度核对不冒充识别质量，声纹/事实/售卖仍待门槛。原长上下文6501IDs/缓存保留，未完成不报通过。'
d['jointArchitecture20261115']['nextExecutableGate']=d['next']
d['logResult']+='\n'+at+' 原4完整CPU固定输入已过半：ES2003b71/71与S_R004S03C01 78/78输入完成，仍待整会组合评分。当前NN运行同时仅做非NN准备：CPU产品消费者沿现有PcmSession持久接收/最终合并，显式CPU、同MOSS BF16/f16 KV、无Torch；独立目录省略可选Vulkan插件，16份原CPU/许可证字节保留共12586370B。parser与冻结评分器在32实际输出完全一致；真实公开PCM无NN调度控制核空草稿进展/最终优先/重放与离线最终区间字节同一，技术空结果accepted=false且非识别成绩。为避免开场静音抢走唯一草稿，先最终请求、每块一次被接受且非空草稿；空/失败草稿只推进到不同最新原PCM前缀，绝不重试同请求/漏原音。75.25s中英各双路径实际NN协议和原整会前两30s输出控制已冻结，尚未执行，等单模型家族空闲再做。原安装/默认/权重/参考与门不改。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'state':d['state'],'cpuCandidatePrepared':str(C),'actualCpuIntegrationExecuted':False}))
