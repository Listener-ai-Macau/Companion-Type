"""Record a competitive sale decision in the original model task, without training."""
from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
M = R / 'model-research'
S = R / 'companion-device-closure055'
C = R / 'docs/handoffs/20261108-competitive-sale-standard'
EV = M / 'evidence/20261108-competitive-sale-standard'
DEST = S / 'docs/handoffs/model-competitive-sale-standard-20261108'
SOURCE = R / 'docs/handoffs/20261108-tse-source-supervision'
sys.path.insert(0, str(M / 'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits

limits = WorkerLimits(cpu_percent=5, memory_bytes=1024**3)
at = datetime.now().astimezone().isoformat(timespec='seconds')
env = os.environ.copy()
env.update(GIT_TERMINAL_PROMPT='0', GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
publisher = S / 'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py'
functions = [n for n in ast.parse(publisher.read_text(encoding='utf8')).body if isinstance(n, ast.FunctionDef) and n.name in ['git', 'ship']]
assert len(functions) == 2
exec(compile(ast.Module(body=functions, type_ignores=[]), str(publisher), 'exec'), globals())
for repo in [M, S]:
    assert not git(repo, 'status', '--porcelain'), f'Unrelated uncommitted work in {repo}'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def node(data):
    return data['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']

backlog_path = R / 'docs/product_backlog.json'
log_path = R / 'docs/development_log.md'
before = read(backlog_path)
old_log = log_path.read_bytes()
old_node = node(before)
bank = read(SOURCE / 'reference-bank-r1/result.json')
words = read(SOURCE / 'free-asr-review.json')
decision = read(SOURCE / 'decision.json')
contract = before['quality_targets']['real_meeting_model_contract_20261103']
assert not bank['saleQualified'] and not words['saleQualified']
assert decision['completedWeightUpdates'] == 128
assert words['allExpectedOutputsScored'] == 156

sources = [
    {'url': 'https://www.granola.ai/security', 'claim': 'Granola公开列出第三方转写和摘要服务。这支持成熟组件集成的产品路线，不证明其中文或重叠识别准确率。'},
    {'url': 'https://help.otter.ai/hc/en-us/articles/4403627500951-Troubleshoot-audio-recording-problems', 'claim': 'Otter排障文档提醒音频抑制可能丢掉其他人声音，并建议避免同时讲话。不能把竞品存在多人标签理解为任意重叠均可正确还原。'},
    {'url': 'https://support.notta.ai/hc/en-us/articles/4403163792027-Does-Notta-support-speaker-identification', 'claim': 'Notta文件上传可启用分人，支持所有转写语言、至多10人；会议Bot依赖参会账号识别。账号区分不能作为单卡声学分人的同条件结果。'},
    {'url': 'https://support.plaud.ai/hc/en-us/articles/63429907861657-Auto-speaker-labeling-for-v4-0-x-or-later', 'claim': 'Plaud有自动说话人标签和可选声纹档案，建议档案录制至少30秒；不能据此推断延长我们的档案就能修好最难会议。'},
    {'url': 'https://support.plaud.ai/hc/en-us/articles/55624401842841-How-to-Generate-a-Summary-and-Mindmap', 'claim': 'Plaud在转写后生成摘要与思维导图，提供自动选择模板、模型、语言的入口，也保留自定义。适合作为少量清晰入口的流程参考。'},
]

protocol = {
    'version': 'companion.competitive-sale-comparison.v1', 'frozenAt': at,
    'status': 'PROTOCOL_ONLY_NO_LIVE_COMPETITOR_BENCHMARK',
    'originalContract': 'quality_targets.real_meeting_model_contract_20261103',
    'acceptanceThresholdsUnchanged': True,
    'qualification': contract['qualification'],
    'systems': [
        {'id': 'local_original', 'purpose': '冻结现有未训练原模型与普通转写基线，保留音频/版本/每步结果。'},
        {'id': 'local_reference_bank', 'purpose': '固定多段参考库加原模型，先独立身份/逐人文字验证；已知档案和自动发现的结果分开，不能将带真值身份的实验当自动分人。'},
        {'id': 'commercial_reference', 'purpose': '优先核实项目既有火山ASR可用性；兼容接口不等于任何服务已验证。仅公开测试音频，凭据在本机使用且不输出，不自动开通付费账户或新服务。', 'actualConfiguredServiceVerified': False},
        {'id': 'competitor_product', 'purpose': 'Plaud为录音卡产品主对照；Notta中文文件上传分人作次对照。需要实际可用账户/版本/导出结果，目前未运行。Granola作为体验流程参考，不假定支持相同文件导入。', 'actualAccountOrResultsVerified': False},
    ],
    'inputFairness': [
        '同条件声学比较使用同一完整公开会议、同一音频文件SHA256/时长/声道，记录所有实际前处理；不以会议账号/独立参会轨道对比单卡混音后宣称模型胜负。',
        '原始双通道额外路线另列，保存原音，不把阵列麦0/1结果外推到紧邻双麦录音卡。',
        '先在已暴露完整开发会议比较候选能力和失败原因；不足30分钟的开发片不得进入正式>=30分钟资格集。',
        '最终至少3场>=30分钟、>=2房间、>=1独立未用于选型的会议，含>=4人、真实重叠>=5%、短回应/快速切换。原最终留出L_R003S03C02保持未打开；候选和处理规则冻结后才验收。',
        '参考转写/标注/人数仅供评分，不能进入识别器、分离器或摘要提示；看过结果用于改方案的会议成为开发集。',
    ],
    'measurements': [
        {'id': 'QM04', 'target': '普通及全会逐人严格中文CER<5%，关键人名/数字/日期/否定0错误；按原合同逐场报告。', 'report': '替换/删除/插入原始计数、参考字符数、分人和普通/重叠分项；不删除语气词来优化评分。'},
        {'id': 'QM05', 'target': '自动分人正式DER<=10%；15%仅阶段目标。', 'report': '零宽容且含重叠，整会固定匿名映射，人数、逐人正确覆盖、短回应/重叠漏检与混淆。已知声纹匹配率不是DER。'},
        {'id': 'RM-OVERLAP', 'target': '原逐人真实重叠严格CER<5%保留，双人/三人分别报告。', 'report': '逐人漏字/串人/重复/虚构，漏掉整路必须计错。最佳排列只作诊断；不得用总CER降低掩盖真实讲话消失。'},
        {'id': 'QM06', 'target': '原事实覆盖>=95%；决定、归属、期限、金额及否定100%正确，无根据关键结论0。', 'report': '同时对原会与转写核对；所有关键结论带原音时间依据；建议不自动升级为决定，未知负责人/时间保持未知。'},
        {'id': 'QM07-LONG', 'target': '准确优先，沿原初始长会RTF<=1.0目标，不能将这个阶段目标当竞品速度或售卖性能证明。', 'report': 'Windows/Android分别测传输、解码、加载、分人、分离、转写、纪要、总墙钟及停录后等待；记录资源/中断恢复。可比合格样本不足20个不报P95。'},
        {'id': 'QM09', 'target': '真实Windows/Android和实卡完整主链按原门验收。', 'report': '原文/人物/时间回听/修改/纪要/保存恢复/导出分享、断链续传与取消恢复。脚本成功不当成已安装产品通过。'},
        {'id': 'commercial_viability', 'target': '联网路线成本、网络/失败恢复和用户知情选择可交付；具体价格/模式在有实测后确认。', 'report': '计费音频量、实际费用、延迟、上传范围及失败状态；云端分数不抵消本地不合格，无同音竞品结果不得宣传达到竞品。'},
    ],
    'promotionRule': '所有原门保留；本地/联网分别出资格结论。任何单人讲话回退、重叠漏词增多、整位说话人消失或关键事实错误均不能仅凭平均分晋级。联网使用只能由明确选择触发；私人录音不在本轮上传。',
    'productPresentation': '默认清晰的生成纪要入口，先展示摘要/决定/待办和人物原文，再提供带依据的问答、思维导图、翻译和模板；未实现功能继续留原竞品待办，不用更多开关冒充能力。',
    'noNewInferenceOrTraining': True, 'finalHoldoutOpened': False,
}

record = {
    'at': at, 'ownerQuote': '你觉得像我们这种水平的模型能达到竞品的那种感觉吗？能可以达到这种公开售卖的这个标准。',
    'state': 'COMPETITIVE_SALE_STANDARD_REVIEWED_CURRENT_MODELS_NOT_QUALIFIED',
    'judgment': '目前不能按复杂多人/重叠会议能力公开售卖。达到有竞争力产品有可行路径，但尚无同音实测证据证明已达到竞品；不承诺现有本地候选能独自解决所有复杂场景。',
    'route': '以最终原文、逐人内容和纪要事实为产品主线，使用可替换成熟组件；保留本地普通语音基线，复杂多人先建立成熟方案同音对照，再决定最小差距的适配。原本地重叠目标保持独立未完成；可选联网增强先验证质量/成本/知情选择，不改成静默默认上传。',
    'rejectedRoutes': [
        '不以自研基础模型、扩大同一训练或不断换模型作为必经路线；先证实差距在采音、身份、分离、识别还是纪要。',
        '拒绝以总CER改善掩盖漏掉更多真实讲话的候选；本轮128步训练继续拒绝，不进产品。',
        '不拿已知档案223段匹配、短片/合成混音或历史拼接开发样本代替完整自然会议验收。',
        '简单增加参考或等权双麦融合不能解决最难场，不据此继续扫参数或按预测改标签。',
    ],
    'observedEvidence': {
        'sourceDecisionSha256': digest(SOURCE / 'decision.json'),
        'wordsReviewSha256': digest(SOURCE / 'free-asr-review.json'),
        'referenceResultSha256': digest(SOURCE / 'reference-bank-r1/result.json'),
        'fixedNaturalTargetQueriesPerCondition': 66,
        'words': decision['wordSafetyFindings'],
        'knownProfileSingleAccuracy': bank['knownProfileAccuracySingle'],
        'knownProfileMultiAccuracy': bank['knownProfileAccuracyMultiple'],
        'hardestKnownProfileMeetingAccuracy': bank['hardestMeetingAccuracy'],
        'knownProfileAccuracyIsNotAutomaticDiarizationOrFullMeetingCer': True,
        'historical3612PercentScope': '原QM04验收记录将61分钟3.6120%列为拼接开发结果，不可宣称独立完整复杂会议已经通过。',
        'currentApplicationAdapters': 'Windows源码已有本地Paraformer、显式选择的火山ASR和兼容ASR接口；双端有AI纪要接口。这是代码能力检查，不是已配置服务可用性/质量或云端复杂重叠通过证明。',
        'privateCredentialsReadOrPrinted': False,
        'liveCompetitorComparisonRun': False,
    },
    'officialSources': sources,
    'protocol': str(C / 'benchmark-protocol.json'),
    'unchangedResearchWorkpoint': old_node['next'],
    'next': '先核实既有成熟ASR服务的可用性并做同一完整公开开发会议的固定对照，分开定位分人、漏词、转写与纪要事实差距；无现成服务/竞品账户时保留未测，继续原最难会议002/003/007参考身份复核，不等账户、不扩大训练。成熟方案只有同音实测达原门才作为候选；离线/可选联网分开验收。固定多段参考库保留、128步训练候选拒绝，原<5%、自动分人、真实重叠、事实、双端实卡和售卖门全部保留。',
    'qualityQualified': False, 'saleQualified': False,
    'newModelTrainingOrInference': False, 'productDefaultChanged': False,
    'privateRecordingsUploaded': False, 'finalHoldoutOpened': False,
    'thisBatchIsDecisionAndProtocolNotCapabilityImprovement': True,
    'preparationFailureRetained': '首次保存脚本读取原合同误用qualificationSet键，KeyError后在任何原待办/日志/远端写入前退出；核对实际qualification键后修正，未影响模型或质量门。',
}
C.mkdir(parents=True, exist_ok=True)
write(C / 'assessment.json', record)
write(C / 'benchmark-protocol.json', protocol)
for file in C.iterdir():
    if file.is_file():
        EV.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, EV / file.name)
model_head = ship(M, ['evidence/20261108-competitive-sale-standard'], 'Record competitor-aligned sale criteria without promoting failed models')
record['sourceAndEvidenceCommit'] = model_head
record['remoteReadbackConfirmed'] = True
write(C / 'assessment.json', record)

for attempt in range(8):
    raw = backlog_path.read_bytes()
    data = json.loads(raw)
    previous_quality = json.dumps(data['quality_targets'], ensure_ascii=False, sort_keys=True)
    n = node(data)
    assert 'ownerCompetitiveSaleStandard20261108' not in n
    old_n = json.loads(json.dumps(n))
    n['ownerCompetitiveSaleStandard20261108'] = record
    n.update(status=record['state'], next=record['next'])
    assert json.dumps(data['quality_targets'], ensure_ascii=False, sort_keys=True) == previous_quality
    for k, v in old_n.items():
        if k not in ['status', 'next']:
            assert n[k] == v
    temp = backlog_path.with_suffix('.competitive-sale.tmp')
    write(temp, data)
    if backlog_path.read_bytes() != raw:
        temp.unlink()
        continue
    try:
        os.replace(temp, backlog_path)
    except PermissionError:
        temp.unlink(missing_ok=True)
        time.sleep(min(.05 * 2**attempt, 2))
        continue
    break
else:
    raise RuntimeError('Original backlog busy; model evidence already preserved')

marker = '原模型任务竞品售卖标准复核20261108'
assert marker.encode('utf8') not in log_path.read_bytes()
entry = f'\n\n## {at}｜{marker}\n\nOwner询问当前模型能否达到竞品与公开售卖标准。结论：当前不合格；本轮只完成方向和同音对照标准复核，没有新增模型能力或真实竞品成绩。官方资料支持成熟转写/摘要组件集成、声纹档案和清晰自动生成流程；账号分人与单卡声学分人不混比。保留本地优先及全部原质量门，复杂多人先做成熟方案同音对照，可选联网不替代离线资格、不静默上传。上一轮普通CER13.1621%→15.0883%、真实重叠删除10→86的训练候选继续拒绝；已知档案203/223不当自动分人/整会通过。标准与官方链接见{C}/assessment.json、benchmark-protocol.json；研究证据{model_head}已推送核验。此前最难会议身份复核工作点、原候选/失败及留出集完整保留。下一项：{record["next"]}\n'
with log_path.open('ab') as f:
    f.write(entry.encode('utf8'))
assert log_path.read_bytes().startswith(old_log)
assert read(backlog_path)['quality_targets'] == before['quality_targets']
DEST.mkdir(parents=True, exist_ok=True)
for file in [backlog_path, log_path]:
    shutil.copyfile(file, S / 'docs' / file.name)
for file in C.iterdir():
    if file.is_file():
        shutil.copyfile(file, DEST / file.name)
shutil.copyfile(__file__, DEST / Path(__file__).name)
main_head = ship(S, ['docs/product_backlog.json', 'docs/development_log.md', 'docs/handoffs/model-competitive-sale-standard-20261108'], 'Record competitive sale review in original model backlog')
result = {
    'at': datetime.now().astimezone().isoformat(timespec='seconds'),
    'state': record['state'], 'modelCommit': model_head, 'mainCommit': main_head,
    'remoteReadbackConfirmed': True,
    'originalQualityTargetsUnchanged': read(backlog_path)['quality_targets'] == before['quality_targets'],
    'oldTimelinePrefixPreserved': log_path.read_bytes().startswith(old_log),
    'modelWorktreeClean': not git(M, 'status', '--porcelain'),
    'mainWorktreeClean': not git(S, 'status', '--porcelain'),
    'next': node(read(backlog_path))['next'],
    'saleQualified': False, 'newModelCapabilityClaimed': False,
}
write(C / 'preservation-result.json', result)
print(json.dumps(result, ensure_ascii=False), flush=True)
