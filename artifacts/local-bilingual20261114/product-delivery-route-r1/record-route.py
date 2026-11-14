from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import shutil
import subprocess

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
MODEL = ROOT / 'model-research'
WORK = Path(__file__).resolve().parent
OUT = WORK.parent / 'outputs'
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
now = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
progress = read(WORK / 'bilingual_progress.json')
contract = ROOT / 'docs/handoffs/20261108-competitive-sale-standard/benchmark-protocol.json'
delivery = ROOT / 'docs/handoffs/20261113-ui-foundation/reader-clarity/ui148164-delivery.json'
cpu_failure = ROOT / 'docs/handoffs/20261107-model-generation-recovery/practical-cpu-r2/results/L_R003S01C02/completed-state.json'
comparison = CONTROL / 'combination-study-r1/result.json'
assert read(cpu_failure)['error'] == "MemoryError('bad allocation')"
assert read(comparison)['state'] == 'COMPLETE_TWO_FROZEN_COMBINATIONS_QUALITY_NOT_QUALIFIED'
installed = read(delivery)['manifest']
base = ROOT / 'docs/handoffs/20261107-model-generation-recovery'
development = []
for p in [base/'practical-qwen-author-boundaries-r6/audio-only.json',
          CONTROL/'combination-study-r1/audio-only.json', base/'native8-ami-r1/audio-only.json']:
    for case in read(p):
        development.append({k: case[k] for k in ['meeting', 'audio', 'audioSha256', 'audioSeconds']})

route = {
    'at': now,
    'state': 'ACTIVE_WHOLE_PRODUCT_DELIVERY_CONVERGENCE_ROUTE',
    'ownerQuote': '不要这样子，你需要把整个东西给收敛好了，然后尽快交付出可以达到合格层次，可以达到售卖标准的产品。你看下怎么样搞个合适的这个路径去把这个东西一步步推进完。',
    'correction': 'Convergence means completing the original sellable user outcome. A speaker-only issue is one work item; rejecting a candidate does not stop product delivery. Avoid blind trials without freezing all engineering work.',
    'userOutcome': 'Record a real Chinese/English meeting with the card; see incremental text while receiving; finish or import offline audio; obtain reliable speaker-attributed text and evidence-linked minutes; replay, correct, save, reopen and export on the intended Windows/Android path.',
    'architecture': {
        'capture': 'One durable original audio/session timeline and recoverable transfer; never replace or consume unsafely acknowledged source audio.',
        'live': 'Existing bounded local incremental ASR as revisable draft; local automatic Chinese/English route must replace the fixed-Chinese research-only assumption before bilingual qualification.',
        'closed': 'One finalization stage over the complete original timeline, reusing valid bound ASR results rather than blindly retranscribing the entire meeting. Whole-recording speaker identity reconciliation and alignment may revise draft identities.',
        'text': 'Current Qwen1.7 is a candidate baseline, not a guaranteed final model. Keep recognized words unchanged through attribution. Repair source omissions and segmentation/recovery defects before training.',
        'speakers': 'Retain current Native8 as a measured baseline. Evaluate an implementable bounded-memory whole-recording identity solution against the returning-speaker failure; old all-in-memory global pipeline is rejected for unchanged rerun.',
        'minutes': 'Use the existing product generation path with source time references. Check against original audio, including decisions, owners, dates, amounts and negation; uncertain source content remains unresolved.',
        'runtime': 'One explicit candidate model/runtime bundle with draft/refining/final/incomplete states, cancellation, resume, errors and versions. PC, phone and actual card capabilities measured separately.',
        'privacy': 'Local-first. No silent cloud fallback or private-recording upload. Any existing explicitly selected network enhancement is separately qualified and cannot stand in for offline quality.'
    },
    'milestones': [
        {'id': 'D1', 'deliverable': 'One executable meeting-processing candidate backend',
         'scope': 'Unify incremental PCM and offline-file jobs, Chinese/English selection, revision/finalization states and preserved source output. Bind current ASR, independent alignment and replaceable speaker interface.',
         'acceptance': 'Actual local audio reaches final structured transcript through one supported entry, survives cancel/restart without audio/text loss, and remains compatible with current app data contracts. Internal candidate only; no sale claim.',
         'current': 'Pieces already exist and have separate tests; no single installed complete bilingual/speaker chain has passed.'},
        {'id': 'D2', 'deliverable': 'One ordinary-meeting Chinese/English quality candidate',
         'scope': 'Resolve source word omissions and whole-meeting speaker identity/short responses together. Reuse existing weights first; memory-bound any global processing. Full English meeting and natural code switching are separate checks.',
         'acceptance': 'Original text and speaker gates, per-person deletions/identity/short turns reported on fixed complete development cases. Earlier ordinary results protected. One new intervention must have a concrete reason and measurable benefit.',
         'current': 'Ordinary Chinese raw CER5.54% on one case but14.50% on another; new-case DER15.84%. English full ASR and long natural switching are unqualified.'},
        {'id': 'D3', 'deliverable': 'Complex-meeting text, speaker and faithful-minutes candidate',
         'scope': 'Natural two-/three-person overlap, missed speakers, code switching and source facts. Run content separation/recovery only when the measured omission requires it; preserve both voices and all failed outputs.',
         'acceptance': 'Original overlap/per-person text gates remain. Facts>=95%; critical decisions/ownership/deadlines/amounts/negation correct, no unsupported critical conclusions. Uncertainty marking is useful behavior but not a substitute for the quality gates.',
         'current': 'Complex raw and attributed text still fail; no qualification by ordinary-case improvement.'},
        {'id': 'D4', 'deliverable': 'One installed Windows/Android/card product candidate',
         'scope': 'Integrate the candidate model package into the existing normal app path. Record/transfer/transcribe/minutes/replay/edit/save/reopen/export, interruption and resume, offline operation, model installation and resource behavior.',
         'acceptance': 'Actual intended devices and source versions tested; data preserved; responsibilities follow existing frontend/model/firmware ownership. Batch related changes before packaging. No extrapolation from developer6800XT to all customer PCs or phones.',
         'current': 'Installed148/164 UI delivery exists, but its receipt explicitly does not qualify the new model chain or phone AI generation.'},
        {'id': 'D5', 'deliverable': 'Frozen sales candidate and complete delivery bundle',
         'scope': 'Freeze models/code/rules, then run untouched qualification meetings and actual end-to-end device tests. Include installers, model distribution/attribution, settings, failure recovery, realistic supported devices and measured waiting/cost.',
         'acceptance': 'All original sales gates pass with exact candidate sources; >=3 complete>=30min meetings, >=2 rooms, at least one unseen meeting, >=4people and real overlap per original contract. A failed gate returns to the relevant implementation work; it is not relabeled passed.',
         'current': 'Not qualified. Final holdout not opened by this planning action.'}
    ],
    'qualityGatesSource': str(contract), 'qualityGatesSha256': sha(contract),
    'unchangedNumericGates': {'ordinaryAndPerPersonChineseCerExclusiveMax': .05,
                             'formalDerMax': .10, 'overlapPerPersonChineseCerExclusiveMax': .05,
                             'factsCoverageMin': .95, 'criticalFactErrorsMax': 0,
                             'qualificationFullMeetingsMin': 3, 'qualificationMinutesPerMeetingMin': 30,
                             'qualificationRoomsMin': 2, 'qualificationUnseenMeetingsMin': 1},
    'englishMetricHandling': 'Report English WER and critical bilingual facts separately; freeze the English acceptance definition in the quality implementation before qualification. Do not silently reuse Chinese CER as English WER or use4-second switching as full-meeting acceptance.',
    'performanceHandling': 'InitialRTF<=1 remains a development gate. Final product waiting targets must be frozen for the actual supported PC/phone and measured for cold load, live lag and post-stop finalization; no invented P95 from fewer than20 valid samples.',
    'executionRules': ['One product batch is a complete usable user result; scripts, commits and documents are evidence, not delivered functionality.',
                       'Reuse immutable completed inference and unaffected product evidence. No same-condition failed long reruns.',
                       'Use mature fixed components first. Training is conditional on a reproducible residual and clean training/validation separation; never required just to demonstrate activity.',
                       'A rejected candidate ends that candidate only. Continue other authorized work toward the original product outcome without waiting for repeated continue requests.',
                       'A second independent method is justified only to resolve a defined quality or resource gap; no growing model roster or threshold search.',
                       'Keep one neural inference family at a time, originalCPU5%/private2GiB/actual Windows low-RAM guards for present local work. No other-app termination or system protection changes.',
                       'Actual device participation uses the original shared operator prompt only when human action is necessary; prepare background work first.'],
    'nextBatch': {'userVisibleGoal': 'One supported meeting job can progress from incoming audio or an offline file to a recoverable final transcript and source-linked minutes through the existing product contract.',
                  'modelWork': 'First unify candidate backend lifecycle and bilingual input/output; reuse completed Qwen/alignment inputs for integration. In the same batch address speaker finalization memory failure/identity persistence and source-word losses with bounded implementation checks.',
                  'frontendDependency': 'Existing frontend task integrates/reviews the versioned candidate via shared backlog; no unsolicited messages, parallel product task tree or takeover of its working files.',
                  'noPrematureShipping': 'Do not change the installed default to an unqualified research candidate. Internal executable checkpoint and sellable release have separate states.'},
    'currentInstalledEvidence': {'receipt': str(delivery), 'sha256': sha(delivery),
                                 'versions': installed['versions'], 'saleQualified': False},
    'directFailureEvidence': {str(p): sha(p) for p in [comparison, cpu_failure]},
    'developmentAudioOnlyCases': development,
    'developmentCasesAreNotFinalQualification': True,
    'missingQualificationEvidence': ['Unseen multi-room whole-meeting results after freeze',
                                     'Full English and long natural Chinese/English switching quality',
                                     'Actual card and both installed clients with this exact model candidate',
                                     'Critical-fact audit and supported-device finalization latency'],
    'technicalReferences': ['https://github.com/QwenLM/Qwen3-ASR',
                             'https://huggingface.co/pyannote/speaker-diarization-community-1',
                             'https://k2-fsa.github.io/sherpa/onnx/speaker-diarization/index.html'],
    'schedule': 'Dependency-driven checkpoints, not an unsupported sales date. First executable end-to-end candidate determines the remaining measured quality and device work; product outcome remains open until all original gates pass.',
    'newModelInferenceThisAction': 0, 'newWeightUpdatesThisAction': 0,
    'installedDefaultChangedThisAction': False, 'qualityQualified': False, 'saleQualified': False
}
folder = CONTROL / 'product-delivery-route-r1'
assert not folder.exists()
folder.mkdir()
(folder / 'route.json').write_text(json.dumps(route, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
out_json = OUT / 'Companion-整套产品收敛交付路线-20261114.json'
out_json.write_bytes((folder / 'route.json').read_bytes())
text = '''Companion 整套产品收敛及交付路线｜2026-11-14

Owner要求：把整个东西收敛到合格、可售卖产品，尽快按合适路径逐步推进。此前仅保留一个分人问题的执行范围过窄，本路线恢复完整原目标，不降低原质量合同。

目标用户结果：录音卡录下一场中英文会议，边接收边看可修订文字，停录或离线导入后得到人物稳定的完整原文和有原话依据的纪要；可回听、修改、保存、重开和导出。

处理架构：原音与逻辑会话可靠保存 → 录音中增量草稿 → 封口后全会文字/人物复核 → 独立时间对齐 → 有原话依据的纪要 → 双端保存/导出。有效缓存按音频/模型/规则哈希复用，不因会后复核无条件再转写一遍。实时人物可以修订，会后人物要利用整会信息复核。

第1批：统一可执行候选后端。接好现有增量PCM和离线文件、自动中英识别、修订/封口、取消/恢复及产品输出契约；先形成一场完整会议能走完的内部候选。现有零散组件和JSON证据不能代替这个结果。

第2批：中英文普通会议达到原质量门。Qwen为当前较好转写候选；文字漏错和人物身份同时是交付阻断。旧全会分人已在提取完3327份特征后bad allocation，不能原样重跑；先实现有界内存和可复用中间数据，再验证整会人物身份。中文、英文及自然混说分开，保护此前普通会，不靠删词或标准答案修分。

第3批：复杂会议和事实合格。自然双人/三人重叠、短回应、长间隔回归和漏整人要分别计错；必要分离只针对已经测清的漏词。纪要对原音核事实、决定、负责人、期限、金额和否定，有原话定位，未知不补。标待确认是必要产品行为，但不能抵消未通过准确率。

第4批：一整套真实产品候选。接入已有Windows/Android正常主链，集中核录音卡边录边传、离线转写、断链续传、取消恢复、回听编辑、纪要、保存重开和导出。实际版本以148/164收据和之后新交付为准；开发6800XT成功不外推为客户电脑或手机成功。模型安装、离线首次使用和资源等待也属于产品。

第5批：冻结后验收并交付可售卖版本。按原合同至少3场各>=30分钟、>=2房间、含独立未用于选型的会议、至少4人和真实重叠条件验证；保留最终留出，方案冻结后才用。真实双端/实卡和关键事实门全过，才交付匹配安装包、模型包、版本来源、使用及恢复说明。未过哪项就回到对应实现，不把阶段候选改名叫合格版。

原门槛保持：中文原字及逐人CER<5%，自动分人DER<=10%（零容差、含重叠），重叠逐人文字仍按原门，事实覆盖>=95%，关键事实错误0。英文WER另列并在资格验收前固定定义；不混用中英口径。初始RTF<=1仅研发门，售卖等待时间需按真实支持的电脑/手机固定并实测。

执行约束：成熟模型组合优先，不从零训练；一项改动须有具体差距和保留条件。失败结束该候选，不结束整个产品任务；同条件无改善不重复。按完整用户收益集中源码联动和打包，复用未受影响证据，不把报告/测试数当进展。本机现有CPU5%/私有2GiB/真实低RAM停止继续；不关其它软件、不静默上传私人录音。

当前事实：普通会最好原字5.54%，新会14.50%/逐人27.07%/DER15.84%，复杂会仍未达标；Windows148/Android164已有UI交付，但本模型链及手机AI生成未因此通过。本路线是实际推进顺序，不声称已经改好，也不承诺无依据的几天售卖日期。
'''
(OUT / 'Companion-整套产品收敛交付路线-20261114.txt').write_text(text, encoding='utf-8')
progress['state'] = route['state']
progress['ownerWholeProductDelivery20261114'] = route['ownerQuote']
progress['productDeliveryConvergence20261114'] = route
progress['previousSpeakerOnlyPrioritySupersededForScope'] = True
progress['next'] = ('按Owner最新要求推进完整合格及售卖产品，分人只是其中一项。当前交付批次先把增量PCM/离线输入、中英识别、封口全会复核、人物/时间和原话纪要接成一份可执行候选后端，'
                    '同时处理已测文字漏错及全会分人内存/身份阻断；复用已有模型和结果，不等待单一cache研究完才集成。随后按原门完成普通/中英→复杂重叠及事实→真实Windows/Android/实卡整链→冻结跨房间留出及售卖包。'
                    '无改善只淘汰该候选，不停止原产品；不原样重复旧全会OOM、不扩模型清单，不把阶段文档当功能交付。前端沿既有任务/共享记录对接，不抢在途源码或默认装入不合格研究候选。')
progress['logResult'] += (f' {now} Owner纠正仅收一个人物问题的范围，要求整套尽快达到合格及售卖并给逐步路径；已恢复完整原目标，先前一个候选失败即停不再解释为停产品。'
                          '核原售卖协议保留CER<5%、DER<=10%、事实>=95%/关键错0、>=3完整30分钟/跨房间/独立留出及双端实卡；核148/164实际UI交付明确不含新模型或手机AI生成资格。'
                          '核旧全会sherpa已完成3327/3327embedding后bad allocation、私有峰约2GiB，没有质量成绩，不原样复跑也不把全局聚类说成已成功。'
                          '路线收为同一原音/会话→增量草稿→封口全会文字人物复核→对齐→原话事实纪要→双端保存导出；成熟组件优先、训练有条件，原音/隐私/资源门不改。'
                          '五个交付检查点已写原待办：可执行整链候选、普通中英质量、复杂事实、实际双端实卡候选、冻结正式资格及售卖包。此动作0新推理/0训练/0构建/0安装，是路线与接续纠偏，不冒充新产品能力。')
(WORK / 'bilingual_progress.json').write_text(json.dumps(progress, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
artifact = MODEL / 'artifacts/local-bilingual20261114/product-delivery-route-r1'
assert not artifact.exists()
artifact.mkdir()
(artifact / '.gitattributes').write_text('* -text -whitespace\n', encoding='utf-8')
shutil.copy2(folder / 'route.json', artifact / 'route.json')
shutil.copy2(Path(__file__), artifact / 'record-route.py')
shutil.copy2(OUT / 'Companion-整套产品收敛交付路线-20261114.txt', artifact / 'route.txt')
gitbase = ['git', '-c', 'maintenance.auto=false', '-c', 'gc.auto=0']
git = lambda *args: subprocess.check_output([*gitbase, *args], cwd=MODEL)
assert not git('diff', '--cached', '--name-only').strip()
relative = str(artifact.relative_to(MODEL)).replace('\\', '/')
git('add', '--', relative)
paths = [p for p in git('diff', '--cached', '--name-only', '-z').decode().split('\0') if p]
assert len(paths) == 4 and all(p.startswith(relative+'/') for p in paths)
for p in paths:
    raw = (MODEL/p).read_bytes()
    assert git('rev-parse', ':'+p).decode().strip() == hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
git('commit', '-m', 'Restore whole-product qualification and delivery convergence route')
print(json.dumps({'state': route['state'], 'commit': git('rev-parse', 'HEAD').decode().strip(),
                  'milestones': [m['id'] for m in route['milestones']], 'newInference': 0}, ensure_ascii=False))
