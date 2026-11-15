from pathlib import Path
from datetime import datetime
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'blind-separation-composition-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/blind-separation-composition-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
always=read(C/'decision.json');routed=read(C/'routed-decision.json');run=read(E/'asr-r3/run.json');state=read(E/'asr-r3/state.json')
assert not always['keepForOriginalWholeMeetingTesting'] and not routed['keepForOriginalWholeMeetingTesting']
assert len(state['results'])==64 and state['explicitNeuralCalls']==64
at=datetime.now().astimezone().isoformat(timespec='seconds')
summary=('公开盲分离组合本批已完整执行：55.735M MossFormer2原权重/核+本地2s/1.5s CSS全部32段239前向，双路完整float输出保留、核心CPU/GPUmax5.245e-6；修ASR重复interop设置前0识别失败，复用原分离结果。波形单位诊断发现SI-SNR输出尺度约40–50倍，asr-r2在22份未评分转写时按核实自有PID停止，未当有效比较；对所有32输入采用一个两路共用RMS(sum)还原系数、保持两路相对幅度，无参考文字或评分选择，原64路raw保留；准备str/Path错误与空目录预检失败0NN保留。asr-r3完成64/64路独立原Qwen识别，64新前向/327.672秒、族私有峰1248256000B，原输入/native逐token控制已过并按hash复用，无权重训练。全部输出已确认、无静音路文字筛选。始终分离的多轮ORC式诊断161→419/1476、单人13→51/87，拒绝。评分前固定的三模型路由只读原Nemotron0.5预测重叠，原PCM对位全等，10/12多轮和4/20单人走双路，其余保留原ASR；仍161→360/1476（10.9079%→24.3902%）、13→19/87，拒绝默认。L会议48→271/740（6.4865%→36.6216%），S会议113→89/736（15.3533%→12.0924%），显示一来源有词语恢复但跨会严重插入/替换；路由多轮插入42→173，删除86→80，不能只报告漏词减少。路由在64输出已生成后、任何合成成绩/输出词检查前固定，明确不是训练前留出或完全独立新房间证据。原逐字/人物/整会质量门未变，无产品默认/日用应用修改，不把诊断ORC替代原分。下一步固定同一分离器的单/双源会议式监督，优先多余路压制与两路保真，停止此未适配组合的模型/阈值/窗口/音量变体。公开训练数据两原声音成分可验证，不需人物样音或Owner听审；原0/1/2声源中的全数字静音已有0输出旁路，训练非全静音的一/双源，所有源监督都明确合成、保留背景，不能叫真实纯净重叠。')
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115'];e.update(
    blindSeparationCompositionStatus=routed['state'],blindSeparationAlwaysOnDecision=str(C/'decision.json'),
    blindSeparationRoutedDecision=str(C/'routed-decision.json'),blindSeparationAsrRun=str(E/'asr-r3'),
    blindSeparationCompositionProductDefaultChanged=False,blindSeparationNewTrainingUpdates=0)
v['next']='预训练分离+ASR及原检测路由组合已完成且跨来源失败，保护完整负例、原64路/校正64路、64有效转写和准备失败；不追加模型/阈值/窗口/音量变体。沿Owner新重点继续同一盲分离器训练：核对公开已知分量混音与单源监督、去除旧“缺席目标=0”但实际双人输入的条件标签，固定联合两源PIT/会议式SA-SDR保真与静音路目标，先证明源和损失不奖励整体静音，再一份固定训练及原多轮/单人/中英文整会验证。最终留出不打开，Owner无需参与，D2仍未过。'
v['logResult']+=' '+at+' '+summary
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (R/'model-research/README.md').open('a',encoding='utf-8') as f:f.write('\n\n'+at+' '+summary+'\n')
note=Path('outputs/Companion-分离组合模型进度-20261115.txt')
note.write_text('Companion 分离组合模型实际结果\n'+at+'\n\n单麦原音→原重叠检测→普通讲话保留原识别；检测到重叠时→双路盲分离→现有Qwen分别识别。\n\n已经完成：原12段多轮重叠+20段单人短回应全部双路分离和64路识别。原分离输出、共同幅度单位校正、全部转写和准备返工均保留，原人声/文字标注不改，无人物样音/真实人数/答案进入模型。\n\n同一预先固定诊断（全部使用路的词都计入，越低越好）：\n始终分离：多轮161→419/1476，单人13→51/87，拒绝。\n原检测模型路由组合：多轮161→360/1476（10.908%→24.390%），单人13→19/87，拒绝。\n两会议分开看：L会议多轮48→271/740（6.486%→36.622%）；S会议113→89/736（15.353%→12.092%）。后一场有改善，另一场明显变差，不能称复杂会议已合格。多余重复/串音是主要剩余。\n\n这些是有标注辅助截取的片段诊断；三模型路由在转写产出后、文字评分前固定。不是独立完整会议、人物身份或售卖验收分，原5%/10%门和最终留出保持。\n\n下一步：仍用同一分离器，转到公开已知两源成分和单源保真的训练，目标是单人输入保住原话并压住另一条、多人大声小声都保留；不继续换模型或在这些片段调阈值/窗口/音量。训练监督明确区分合成混音与真实会议，不把未知真实重叠的目标波形写成零。\n\n本批没有可交付的整体质量提升，未替换默认或日用版；D1原内测流程可用，D2和售卖仍未完成。模型CPU5%/私有2GiB及Windows低内存停止保持。Owner无需听审、标注、账号或录音。\n',encoding='utf-8')
print(json.dumps({'state':routed['state'],'routedMultiTurn':routed['byCondition']['multi-turn-context'],'d2Complete':False},ensure_ascii=False))
