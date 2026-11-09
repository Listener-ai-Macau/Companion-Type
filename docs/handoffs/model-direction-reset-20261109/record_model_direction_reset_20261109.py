"""Record an evidence-based direction reset in the original task; run no model."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import ast
import hashlib
import json
import os
import shutil
import subprocess
import time

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
M = R / 'model-research'
S = R / 'companion-device-closure055'
C = R / 'docs/handoffs/20261109-sedicow-r1'
EV = M / 'evidence/20261108-competitive-sale-standard/direction-reset-20261109'
DEST = S / 'docs/handoffs/model-direction-reset-20261109'
STATE = 'FIXED_STACK_MATCHED_REAL_SOURCE_DIAGNOSTICS_PRIORITY_NO_NEW_MODEL_SEARCH'
KEY = 'ownerBottleneckFirstDirection20261109'
MARKER = '原模型方向收敛与停止轮换模型20261109'
OWNER = '不停的尝试模型，这个方向是错的，对吧？接下来我们应该怎么做？还有什么新的方向或者正确的方向？'
NEXT = ('停止新增模型候选和重复旧失败实验。固定现有中文Qwen识别器、一个分离对照及解码版本，'
        '优先完成一场真实中文会议远场混音与逐人近讲录音的配对、身份/声道映射、时间对齐/漂移与串音验证；'
        '近讲不是默认干净真值。按同人同时间同文字参照隔离输入/识别、分离内容损失和人物归属，'
        '不能把混音对单人参照的错误当模型幻觉。复用已有正确活动时间和归人失败证据，不重跑当新进展。'
        '定位后只修一个可归因模块，有可靠匹配中文Train数据才考虑小范围适配，Eval仅诊断不训练。'
        '普通线5.53754%仍需降至<5%，第三真实整会/跨会/留出/纪要事实/双端实卡任务全部保留未完成；'
        '不默认大规模自研、不降低售卖门、不承诺任意单麦密集重叠逐人<5%。')

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

env = os.environ.copy()
env.update(GIT_TERMINAL_PROMPT='0', GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
helper = S / 'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py'
tree = ast.parse(helper.read_text(encoding='utf8'))
ns = dict(subprocess=subprocess, env=env)
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ['git', 'ship']], type_ignores=[]), str(helper), 'exec'), ns)
git, ship = ns['git'], ns['ship']
for repo in [M, S]:
    assert not git(repo, 'diff', '--cached', '--name-only'), 'Preserve unrelated staged changes'

record_path = C / 'direction-reset-20261109.json'
if record_path.exists():
    record = json.loads(record_path.read_bytes())
else:
    refs = [
        ('oracleActivity', M / 'evidence/20261108-target-activity-adaptation/oracle-activity-diagnostic/direction-decision.json'),
        ('dualMicIndependent', R / 'docs/handoffs/20261108-dual-mic-independent-meetings/decision.json'),
        ('targetSupervisedAdaptation', R / 'docs/handoffs/20261108-tse-supervised-adaptation/decision.json'),
        ('sourceSupervisedAdaptation', R / 'docs/handoffs/20261108-tse-source-supervision/decision.json'),
        ('wordIdentityAudit', M / 'evidence/20261108-competitive-sale-standard/word-identity-audit-20261109/result.json'),
        ('lastNewCandidate', C / 'real-pilot-result.json'),
    ]
    record = {
        'at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'ownerQuoteSummary': OWNER, 'state': STATE,
        'purpose': 'Stop serial model selection as the primary development loop; execute the previously identified missing paired-source diagnostic, then repair one measured bottleneck.',
        'priorEvidence': [{'name': name, 'path': str(path), 'sha256': digest(path)} for name, path in refs],
        'priorModelEvidenceCommit': git(M, 'rev-parse', 'HEAD'),
        'priorDeliveryRecordCommit': git(S, 'rev-parse', 'HEAD'),
        'findingsReusedWithoutRerun': [
            'Correct target timing has already been tested: 256 local reference characters, oracle-gated mixture88 edits vs separated113, fully-contained deletions9 vs28. Activity alone is insufficient; distortion vs recognizer sensitivity not uniquely isolated.',
            'Two independent dual-channel meeting diagnostics showed limited improvement, but 64 interior characters were removed before ASR by predicted activity. Public array microphones are not the actual close-spaced card geometry.',
            'Removing the activity gate recovered some speech but greatly increased other-speaker insertions; removing all filtering is not a solution.',
            'Two adaptation attempts failed content/ordinary-speech protection, including target energy collapse and overlap deletions increasing despite a lower aggregate error. Do not repeat generic epoch/lr/volume sweeps.',
            'Word-time reassignment already worsened cached cpCER, and latest target-conditioned ASR pilot failed real Chinese; neither becomes a new recommended model trial.',
        ],
        'executionCorrection': 'The November8 oracle decision already prescribed matched real near/far data. Subsequent execution returned to new model trials before completing that prerequisite. This reset resumes the missing work, not a newly discovered architecture.',
        'missingArtifact': 'One verified genuine Mandarin session with far-field mixture and each person\'s simultaneous close-talk waveform; identity/channel mapping, clock offset/drift, headset cross-talk and target transcript correspondence must be checked. Enrollment snippets are not the overlapping utterance source targets.',
        'sourceAvailabilityOnly': {
            'officialDescription': 'https://www.openslr.org/119/',
            'headCheck': json.loads((C / 'paired-source-head-check.json').read_bytes()),
            'audioDownloadedThisTurn': False,
            'pairedSessionVerified': False,
            'use': 'One Eval session for exposed diagnostics only, never training. Future adaptation must use the separate Train split and separate validation meetings/rooms/people as metadata allows.',
        },
        'frozenDiagnosticPlan': [
            'Freeze Qwen1.7B ordinary ASR and its decoder/normalization, one existing separation checkpoint and one input convention; do not add model candidates.',
            'Acquire and verify one paired meeting before inference: source hashes/license/split, session/person/channel identities, time offset/drift, cross-talk. Preserve raw recordings. Start with a single far-field channel; public8-channel data does not prove card dual-mic capability.',
            'Use simultaneous non-overlap near vs far with identical target transcripts to isolate the basic acoustic/recognition penalty. Use individual near sources during overlap as diagnostic recognition ceilings after verifying source/reference quality.',
            'Compare each separated far-field person output with the SAME person/time/reference and frozen recognizer as the paired near-source path. Record substitutions/deletions/insertions, extra words when person silent, speech preservation, identity errors, wall time and private memory. A reference-only crop is diagnostic and never a product score.',
            'Keep raw mixed chronological CER separate from per-person CER/cpCER; do not score mixed legitimate speakers against a single person reference or compare incompatible denominators. Global identity permutation only under a fixed documented rule.',
            'Use existing correct-activity controls and failed word reassignment evidence; do not rerun them as the next milestone.',
            'Only after localization, implement ONE module repair and verify on disjoint meetings, preserving ordinary speech. If adaptation is justified, use true matched source supervision and content/absence protection; no large training without a falsifiable bottleneck.',
        ],
        'repairDecisionRules': [
            {'finding': 'Validated per-person near-source ASR is already wrong', 'action': 'Audit reference/input/language recognition first; separation-only changes cannot explain or fix all errors.'},
            {'finding': 'Near-source ASR correct, matched separated far output loses/substitutes target words', 'action': 'Repair target content preservation in extraction/frontend; measure source fidelity and downstream text together.'},
            {'finding': 'Correct recognizable speech consistently assigned to the wrong person', 'action': 'Repair reference identity, clustering and stable mapping, rather than retraining the lexical recognizer.'},
            {'finding': 'No reliable module-level gain across disjoint real meetings', 'action': 'Stop that repair; retain failure and unfinished sale gates. Escalate a concrete hardware/service/scope decision separately instead of silently weakening the requirement.'},
        ],
        'primaryResearch': [
            {'url': 'https://www.merl.com/publications/TR2026-112', 'support': 'Real-TSE report builds on a baseline and emphasizes realistic data cleaning and processed close-talk targets; learned sound quality/similarity are not enough. Does not establish our product <5%.'},
            {'url': 'https://www.openslr.org/119/', 'support': 'Official AliMeeting provides same-session far-field array and each participant headset, with separate Train/Eval/Test. Headsets still require validation.'},
        ],
        'ordinaryBest': {'referenceCharacters': 8325, 'edits': 461, 'strictCer': 461 / 8325, 'unchanged': True, 'underFivePercentPassed': False},
        'newModelCalls': 0, 'newTrainingRuns': 0, 'newModelCandidates': 0,
        'newMeetingAudioPayloadDownloaded': False, 'newAccuracyGain': False,
        'productSourceChanged': False, 'installedProductChanged': False,
        'phoneOrBoardAccessed': False, 'formalQualityTargetsChanged': False,
        'finalHoldoutOpened': False, 'saleQualified': False,
        'next': NEXT,
    }
    dump(record_path, record)

EV.mkdir(parents=True, exist_ok=True)
shutil.copyfile(record_path, EV / 'decision.json')
shutil.copyfile(C / 'paired-source-head-check.json', EV / 'paired-source-head-check.json')
note = '''# 模型方向收敛：停止轮换候选，补齐真实配对诊断

现阶段停止把“换模型—失败—再换”当主线。早期选型有价值，但目前已知道活动漏检、分离内容损失、参考人物混杂和训练退化等不同问题；继续替换整套模型无法把改动归因。

11月8日正确活动时间诊断已经要求真实中文近讲/远场配对数据，随后执行又回到候选试跑。现在应完成那个未执行的前提，不将其包装成新架构或新准确率进展。

下一项的交付物是一场真实会议的可核查配对：同场桌面混音、每个人同步近讲录音、人物声道对应、对齐/漂移结果、串音评估和文字参照。近讲仅用于开发核对，不要求用户戴耳麦。AliMeeting官方提供此类来源，本轮仅HEAD确认下载入口，无音频下载、配对验证或新模型运行。

固定现有中文识别器和一个分离对照：先在非重叠同人片段比较近讲与远场，再在重叠时比较同人近讲与分离结果。混合音全文CER与逐人CER/cpCER分开；不能用混音对单人参照制造“串话”结论。重复利用已有正确时间、双麦和归人失败证据。

近讲也错，先查参照/输入/识别；近讲对、分离后错，先修目标语音保留；文字对、人物错，先修身份与映射。定位后只修一个模块，有匹配中文训练真值才做适配。Eval只用于诊断，不用于训练；跨会议检验后再扩大和验纪要、双端、录音卡。

普通完整会议最佳仍461/8325=5.53754%，复杂多人仍不达标；<5%、人物、跨会、留出、事实和双端实卡门均不改变。任意单麦远场密集重叠逐人<5%目前无法承诺。文档、准备和失败排除不算功能达标。

来源：[MERL真实目标语音提取报告](https://www.merl.com/publications/TR2026-112)、[AliMeeting官方数据说明](https://www.openslr.org/119/)。研究支持优先真实配对数据与内容指标，不保证我们的最终效果。
'''
(EV / 'direction.md').write_text(note, encoding='utf8')
model_head = ship(M, ['evidence/20261108-competitive-sale-standard/direction-reset-20261109'], 'Fix model strategy on matched real-source bottleneck diagnosis')
record.update(modelEvidenceCommit=model_head, remoteModelReadbackConfirmed=True)

backlog = R / 'docs/product_backlog.json'
for attempt in range(8):
    original = backlog.read_bytes()
    d = json.loads(original)
    quality_before = json.dumps(d['quality_targets'], sort_keys=True, ensure_ascii=False)
    node = d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
    if KEY not in node:
        record.update(previousStatus=node.get('status'), previousWorkpoint=node.get('next'))
    else:
        record.update(previousStatus=node[KEY].get('previousStatus'), previousWorkpoint=node[KEY].get('previousWorkpoint'))
    node[KEY] = record
    node.update(status=STATE, next=NEXT)
    assert quality_before == json.dumps(d['quality_targets'], sort_keys=True, ensure_ascii=False)
    tmp = backlog.with_suffix('.direction-reset.tmp')
    dump(tmp, d)
    if backlog.read_bytes() != original:
        tmp.unlink()
        continue
    try:
        os.replace(tmp, backlog)
    except PermissionError:
        tmp.unlink(missing_ok=True)
        time.sleep(min(.05 * 2**attempt, 2))
        continue
    break
else:
    raise RuntimeError('Canonical backlog busy; model direction evidence already preserved remotely')

log = R / 'docs/development_log.md'
before = log.read_bytes()
if MARKER not in before.decode('utf8'):
    entry = ('\n\n## ' + record['at'] + '｜' + MARKER + '\n\n'
             'Owner质疑持续尝试模型的方向。本轮审阅既有正确活动控制、双麦跨会、两次训练退化、归人回退和最新中文候选失败；'
             '确认11月8日已提出真实近讲/远场配对但尚无实际配对、对齐和串音验证，执行不应继续回到换模型。'
             '当前停止新增候选，固定中文识别器和一个分离对照，先补齐一场同会议逐人近讲与远场混音，按同人同时间同参照定位输入/分离/识别/身份瓶颈；'
             '混音全文和逐人指标不混算、Eval不训练、旧正确时间控制不重复当进展。AliMeeting官方入口HEAD200/3673718355字节仅来源确认，无音频下载。'
             '本轮零模型调用/零训练/零新准确率增益、无安装/手机/实卡/留出，普通461/8325=5.53754%和全部售卖门未变。'
             '没有把复杂能力移除或改低目标；任意单麦密集重叠逐人<5%不能承诺。证据提交' + model_head + '已推送并远端核验。下一项：' + NEXT + '\n')
    with log.open('ab') as handle:
        handle.write(entry.encode('utf8'))
    assert log.read_bytes().startswith(before)

DEST.mkdir(parents=True, exist_ok=True)
for source in [backlog, log]:
    shutil.copyfile(source, S / 'docs' / source.name)
dump(DEST / 'decision.json', record)
shutil.copyfile(EV / 'direction.md', DEST / 'direction.md')
shutil.copyfile(C / 'paired-source-head-check.json', DEST / 'paired-source-head-check.json')
shutil.copyfile(__file__, DEST / Path(__file__).name)
attr = S / '.gitattributes'
attr_text = attr.read_text(encoding='utf8')
rule = 'docs/handoffs/model-direction-reset-20261109/** -text -whitespace'
if rule not in attr_text:
    attr.write_text(attr_text + '\n' + rule + '\n', encoding='utf8')
main_head = ship(S, ['.gitattributes', 'docs/product_backlog.json', 'docs/development_log.md', 'docs/handoffs/model-direction-reset-20261109'], 'Record original model task direction reset and unchanged sale gates')
current = json.loads(backlog.read_bytes())['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
assert current['status'] == STATE and current['next'] == NEXT
print(json.dumps({'state': STATE, 'modelCommit': model_head, 'deliveryCommit': main_head, 'bothRemoteHeadsVerified': True, 'modelCalls': 0, 'trainingRuns': 0, 'ordinaryBestCerUnchanged': 461/8325, 'modelWorkingTree': git(M, 'status', '--short'), 'deliveryWorkingTree': git(S, 'status', '--short'), 'nextReadback': current['next']}, ensure_ascii=False), flush=True)
