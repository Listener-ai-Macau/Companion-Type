from pathlib import Path
from datetime import datetime
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'public-speaker-adaptation-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/public-speaker-adaptation-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
t=read(E/'train-r2/state.json');run=read(E/'train-r2/run.json');result=read(C/'candidate-decision.json')
assert t['optimizerUpdates']==8 and t['allFrozenParameterBytesUnchanged'] and result['validationKeepRulePassed']
at=datetime.now().astimezone().isoformat(timespec='seconds')
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115']
e.update(publicSpeakerTrainingStatus=t['state'],publicSpeakerTrainingResult=str(E/'train-r2/state.json'),
 publicSpeakerAdapterFile=t['adapterFile'],publicSpeakerAdapterSha256=t['adapterSha256'],
 publicSpeakerHeldValidation=str(C/'candidate-decision.json'),publicSpeakerHeldValidationKeepRulePassed=True,
 publicSpeakerAdapterAdoptedInProduct=False,publicSpeakerDefaultChanged=False)
v['newPublicSpeakerAdapterWeightsCreated']=True
v['next']='公开人物/重叠适配已完成且两完整会轻微改善，按冻结规则接原34分钟困难开发会议；复用已经验证的官方FP32整场baseline，只重新生成相同字节的特征后验证其hash，不重复原基准推理。候选原困难会DER仍须<=10，未过就拒绝本固定适配用于默认，不追加同参数/阈值变体；所有训练/失败/原音保留，Owner无需听审或录音。原D2原字质量仍未过、未采用进产品。'
v['logResult']+=' '+at+' 公开人物模型本轮实际固定训练完成：train-r2于15:29:54—15:31:57完成122.985秒，4epoch/2整会每轮/8次更新，1160core chunk前向含校准与回放，族私有峰1566101504B、原5%/2GiB/Windows低RAM保持；每会整梯度回放误差均0，所有冻结原参数逐字节保持，131072LoRA参数最终528024B SHA '+t['adapterSha256']+'，32张量保存/回读全等，8恢复用checkpoint保留、最终第8唯一候选。原中途5更新失败与两次准备失败不丢，不把重跑说成新参数变体。最终candidate-r1于15:32:12—15:32:42完整重测72分钟两会，禁用适配原前61秒logits全等、加载适配32张量回读通过，无真实人数/标注进推理。原连续时间/零collar/含重叠官方参考评分，L20200709 DER4.3344487%→4.3068447%，S20200805 7.9276158%→7.8540001%，合计6.1611492%→6.1101536%，总误差266.6676376→264.4604426说话人秒，仅少2.2072秒；属于轻微双会一致改善、不作显著性或普适/售卖证明。这两会只对本轮适配留出，原基础模型预训练包含公开AISHELL4且部分素材曾作其他诊断，不称基础模型从未见过。按原规则保留待原开发门，未进产品默认，原完整文字/逐人/纪要/设备等仍开放。下一步原困难34分钟；其原基准FP32特征/prob/严格分已经保护，准备逐字节复用，最终留出不打开。'
p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
readme=R/'model-research/README.md';text=readme.read_text(encoding='utf-8')
text+='\n\n'+at+' Owner要求公开会议训练由工程自主完成，撤销4片人工听审前置，旧blocked仅历史。已完成原99M Nemotron人物/重叠适配：2个7人公开会议65分钟训练、另6/5人72分钟验证，官方PIL/ATS/activity/phantom forward体原样，后8层q/v LoRA131072参数、4epoch8整会更新。初期CPU池/投影及跨两pass离散cache路线问题均保留；固定校准输入路径回放令整会梯度各次差0，8更新恢复checkpoint及最终528024B适配SHA'+t['adapterSha256']+'保留，原参数全等，约123秒/族峰1.566GB。完整留出两会DER4.33445→4.30684%、7.92762→7.85400%，合计6.16115→6.11015%，仅少2.2072说话人秒。满足本轮微小双会保留条件，仍非原D2/售卖通过，继续原34分钟困难开发门；无文字ASR/默认应用变化、不新增Owner动作、不用最终留出。\n'
readme.write_text(text,encoding='utf-8')
print(json.dumps({'trained':True,'updates':8,'aggregateDerBefore':result['baselineAggregateDer'],'aggregateDerAfter':result['aggregateDer'],'adoptedInProduct':False},ensure_ascii=False))
