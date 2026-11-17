"""Close the bounded metadata audit in the existing model workpoint."""
from pathlib import Path
from datetime import datetime
import json

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
D = R / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J = D / 'joint-architecture-r1'
E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))
receipt = J / 'meeting-domain-data-r1/chinese-global-speaker-audit-20261117.json'
audit = read(receipt)
assert audit['selectedTrainMeetings'] == 12
assert audit['selectedTrainingTierInstances'] == 63
assert audit['decision']['chineseGlobalSpeakerDisjointnessVerified'] is False
assert audit['decision']['chineseAdaptationLaunchAllowed'] is False
assert audit['reservedFinalAudioLabelsOrEmbeddingsOpened'] is False
assert len(audit['boundedExistingPrefixInspection']['selectedReferenceComparisons']) == 3
assert all(r['lfNormalizedBytesEqual'] for r in audit['boundedExistingPrefixInspection']['selectedReferenceComparisons'])
p = Path('work/bilingual_progress.json')
x = read(p)
at = datetime.now().astimezone().isoformat(timespec='seconds')
x['at'] = at
j = x['jointArchitecture20261115']
j['meetingDomainTrainingPreparation20261116']['chineseGlobalSpeakerAudit20261117'] = {
    'receipt': str(receipt), 'state': audit['state'],
    'trainingMeetingsChecked': 12, 'meetingLocalSpeakerTiers': 63,
    'globalPeopleCountOrIsolationNotInferredFromLocalLabels': True,
    'publishedTrainEvalOneSpeakerOverlap': True,
    'globalMappingLocated': False, 'reservedFinalHoldoutOpened': False,
    'chineseAdaptationLaunchAllowed': False,
    'existingChineseEvaluationScoreChanged': False}
own = j['overnightExecution20261116']
own['state'] = 'GPU_UNDOCKED_ENGLISH_ADAPTATION_PREPARED_CHINESE_PERSON_SPLIT_UNPROVEN'
own['chineseGlobalSpeakerAudit20261117'] = {'receipt': str(receipt), 'state': audit['state']}
x['state'] = own['state']
x['next'] = '中文12场/63会议内身份元数据审计已收束：跨会全局身份仍未证实，中文适配保持未就绪，不再重复查同一缺失表或下载7GB全包；既有中文基座/原分数不变，英文475片/119更新配方人员划分不受影响。下一模型执行为英文固定预检与真实GPU梯度/稳态最大形状/检查点往返，当前6800XT已拔且计算栈长稳未建立，禁止CPU/核显训练或重跑旧失败长批次；先沿compute-only-trigger-review定位兼容栈单变量条件。95/98/整源/逐人/事实/最终盲测均开放。'
entry = (at + '｜继续原模型任务的中文全局人员隔离审计：只读已选12场训练TextGrid的63个会议内身份名、官方论文/说明/基线，未读最终L_R003原音/标签/嵌入。官方明确训练36人、评测25人且重合1人，不能把官方划分称零人员交叉。已缓存505文件镜像索引无全局表；官方基线树无spk_info/xlsx，两个按说明目录构造的DOC/spk_info.xlsx路径HEAD均404，仅否定这两个路径、不证明全网无表。复用之前超时28留下的524288B压缩前缀，成功读取首30训练包头；其中3场已选训练标注与缓存只差CRLF/LF，内容核对一致，原文件/训练及验收文本均未改。第一次审计脚本误取E盘元数据路径FileNotFound已保留源和失败收据，修正为原冻结计划目录并核原SHA后通过；这是准备路径失败，不是模型失败。结论仍是中文跨会人员隔离未证实/不准启动适配，英文已有独立人员划分不受影响；本批0神经调用0更新、没有准确率改善，不借数据检查关闭95/98或人物/事实/盲测。结果' + str(receipt) + '。')
x['logResult'] += '\n\n' + entry + '\n'
p.write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'state': x['state'], 'receipt': str(receipt), 'next': x['next']}, ensure_ascii=False))
