from pathlib import Path
from datetime import datetime
import json,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
P=D/'community1-preflight-r1';C=D/'community1-comparison-r1'
RUN=Path('E:/CodexData/Companion/product-d1d2-20261114/community1-comparison-r1/features-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
run=read(RUN/'run.json');feature=read(RUN/'state.json')
assert run['exitCode']==0 and feature['noWeightsLoaded'] and feature['newNeuralCalls']==0
if psutil.pid_exists(run['pid']):assert abs(psutil.Process(run['pid']).create_time()-run['pidCreatedAt'])>=.01
assert not (C/'model-binding.json').exists(),'No model access or full quality run was performed in this preparation'
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115']
e.update(community1PublicRuntimeStatus='ISOLATED_IMPORT_PCM_GPU_DEFAULT_FEATURE_PATH_READY_NO_WEIGHTS_OR_QUALITY_RUN',
 community1FixedComparison=str(C/'protocol.json'),community1FeatureProof=str(RUN/'state.json'),
 community1OutputContract=str(C/'output-contract-proof.json'),community1BaselineReproduced=str(C/'baseline-reproduced-score-receipt.json'),
 community1ModelAccess='Original asynchronous access question remains unanswered. No gated downloads/credentials read/whole pipeline applications. Existing runtime and ASR/product default unchanged.',
 asrOriginalAudioAdjudication=str(D/'asr-audio-adjudication-r1/packet.json'),
 asrOriginalAudioAdjudicationStatus='4KNOWN_CLEAN_SHORT_ERRORS_PREPARED_WITH_UNCHANGED_INPUT_AND_CONTEXT_NOT_LISTENED_OR_RELABELED')
v['next']='原D1/D2继续：先保护Community1隔离依赖/真实PCM入口/GPU默认特征控制/固定整场对照源码及ASR4条原音复核材料，更新同一本机HTML。Community1模型下载与整场人物对照等原账号条款授权，未再询问或绕过；ASR需基于原音区分实际漏听/标签歧义/边界，4条材料已备、尚无人听审，不自行改标签或追加旧失败训练。原D2文字和人物门仍未过。'
at=datetime.now().astimezone().isoformat(timespec='seconds')
v['logResult']+=' '+at+' Community1仅人物组件对照准备形成可执行入口：官方PyPI两包SHA核，TA2.11.1+cpu隔离导入/同率与零信号重采样精确通过；原安装全部包版本固定，55个新增wheel按各自SHA/no-deps装独立target，原包列表和torch init字节前后全等。完整pyannote导入及官方内存PCM全段/裁剪逐值全等，峰610893824B，telemetry进程级关闭、torchcodec可用、0GPU初始化/0模型加载。新接口保留常规含重叠输出的原float与9位小数RTTM，exclusive单存不替代原门，传输控制通过；构造的区间只验传输不算识别。原评分器在候选输出前复现34分钟DER0.1584147453575932和所有分量<1e-9差，原标注/全UEM/零collar含重叠不变。14:15:50—14:16:07新鲜HIP inventory实际ordinal1，官方WeSpeaker默认fbank函数无网络/权重/骨干构造地CPU对GPU计算，1x98x80，最大差0.00012826919555664062/均值1.679269644228043e-6，低于预定0.003/0.0001，job峰1076359168B（族采样1060982784B），原5%/2GiB/低RAM与lease保持，owned族已退出。此仅证明默认特征路径和接口，不证明门控检查点其余参数/整场加载/质量。整场worker/runner保留官方默认无人数提示/无阈值扫选，冻结同一34分钟输入，原DER未达10即拒绝固定方案；通过后还需原旧会和文字/纪要/产品门，绝不自动采用。实际权重/条款授权未收到，未读凭据、未下载/未调用pipeline。入整场分支后的NN计数改unknown避免失败误报0；仅该分支加音频绑定及计数修复，已过特征路径4605字符逐字相同，旧source/binding保留，不重跑无关GPU控制；准备器原任意>5000字符断言失败为工具错误留证后用唯一分支/完整末尾/逐字相等核。另4条已知短句错误的原输入逐字复制和前后2秒单麦原音共8WAV已备，只供事后原音审定，不作新训练/质量样本；0新NN/无播放/无麦克风/无人听审，原87字13错和全部原门保持。'
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
note=Path('outputs/Companion-社区可行性与实际进度-20261115.txt');text=note.read_text(encoding='utf-8')
text=text.replace('该对照能否改善、能否满足2GiB和AMD环境都尚未证明，不把它当成必胜替换。',
 '已在独立目录实际验证依赖导入、原PCM入口和AMD上的默认特征函数；门控模型的整场加载、2GiB内存和人物质量仍未验证，不把它当成必胜替换。')
text+='\n\n'+at+' 后台续作更新\nCommunity1隔离依赖、原音输入、含重叠原始日志与原评分入口已接好，未改现用ASR/模型包/应用。原完整会15.8414745%及误差分量复现一致；无权重的默认WeSpeaker CPU/GPU数值控制通过，峰约1.076GB，0新模型/训练。官方账号条款授权未收到，尚无Community1整场质量结果。4条短句错误的原音与前后文已整理到同目录Companion-ASR原音复核-20261115，尚未听审，没有播放或改标签。D1范围仍仅内测候选，D2仍失败。\n'
note.write_text(text,encoding='utf-8')
readme=R/'model-research/README.md';body=readme.read_text(encoding='utf-8')
body+='\n\n'+at+' Community1固定人物组件准备：原AMD环境包版本/torch字节不变，TA2.11.1+cpu与55个SHA固定公开wheel在独立target导入成功；pyannote4.0.7官方内存PCM全段/裁剪精确，0NN/CPU峰610893824B。实际默认WeSpeaker特征CPU/GPU无骨干/无权重控制通过（max0.0001282692,mean1.67927e-6，job峰1076359168B），非门控检查点/整场质量证明。常规重叠与全精度输出单独保存、exclusive不替代原门，传输及原完整DER各分量复现通过。固定新34分钟/官方默认/无真实人数提示/先原DER<=10再旧会及其余门；原访问问题待答，0门控下载/0整场pipeline/0训练，原D2未过。原ASR4条错误原音及前后文已备，无听审/改标签；不再据短控制直接训。源与证据保护见evidence/20261115-community1-isolated-preparation-r1。\n'
readme.write_text(body,encoding='utf-8')
print(json.dumps({'community1Prepared':True,'modelLoaded':False,'wholeQualityEvaluated':False,'asrErrorPacketReady':True,'d2Complete':False},ensure_ascii=False))
