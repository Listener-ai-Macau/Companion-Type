"""Preserve the restored real pairing and update the original model workpoint."""
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
C = R / 'docs/handoffs/20261109-paired-real-meeting'
EV = M / 'evidence/20261108-competitive-sale-standard/paired-real-meeting-20261109'
DEST = S / 'docs/handoffs/model-paired-real-meeting-20261109'
STATE = 'PAIRED_REAL_SOURCE_RESTORED_AND_AUDITED_FIXED_ASR_PENDING_EXTERNAL_GPU'
KEY = 'ownerPairedRealMeetingSource20261109'
MARKER = '原模型真实中文近远场配对恢复与声学核验20261109'
now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
read_json = lambda p: json.loads(Path(p).read_bytes())
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')

env = os.environ.copy()
env.update(GIT_TERMINAL_PROMPT='0', GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
helper = S / 'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py'
tree = ast.parse(helper.read_text(encoding='utf8'))
ns = dict(subprocess=subprocess, env=env)
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ['git', 'ship']], type_ignores=[]), str(helper), 'exec'), ns)
git, ship = ns['git'], ns['ship']
for repo in [M, S]:
    assert not git(repo, 'diff', '--cached', '--name-only'), 'Do not consume another task staged changes'

audit = read_json(C / 'pair-audit-result.json')
acquisition = read_json(C / 'download-result.json')
extraction = read_json(C / 'pair-extraction-result.json')
prepared = read_json(C / 'fixed-asr-preparation.json')
old = read_json(R / 'docs/product_backlog.json')['owner_module_execution']['frontendWindowsMobile20261102']['ownerAsrAccuracyLatencyAndMeetingUse20261103']['ownerComplexPublicMeeting20261103']['boundedCssTrial20261104']['preparedNextEvidence']
assert audit['newModelCalls'] == 0 and audit['newTrainingRuns'] == 0 and extraction['gzipCrcVerified']
assert len(audit['pairedPeople']) == 4 and all(p['referenceExactlyMatchesFarTier'] for p in audit['pairedPeople'])
NEXT = ('已恢复并核验原暴露AliMeeting R8001_M8004一场四路近讲/远场及604段对应参考。'
        '下一项执行已冻结五输入同Qwen1.7B识别对照：四人完整近讲＋一路共同覆盖1551.82s原混音，先量近讲识别上限，'
        '再决定是否修识别器或当前分离内容保留；混音全文与逐人CER不能直接混比。当前仅780M、无外置6800XT，'
        '本轮零模型调用，GPU恢复时先重新枚举HIP并绑定私有运行包，不能用旧ordinal；单任务5%CPU/2GiB私有内存、保留raw与断点。'
        '近讲仍有串音，局部延迟/相关性不稳定，不作为样本精确干净声源训练或SDR真值；Eval不训练。'
        '普通最佳5.53754%及第三整会/跨会/最终留出/人物/纪要事实/双端实卡待办和售卖门均保持开放，不新增模型清单。')
record = {'at': now(), 'ownerQuote': '那继续按照这个推进咯', 'state': STATE,
          'historicalCorrection': {'priorAvailabilityOnlyStatementTooBroad': True,
              'actualEarlierState': old,
              'meaning': 'November4 already prepared2 exposed meetings/8headsets, reference consistency and coarse clocks; referenced cache and archive had been cleaned. This batch restores1 of those meetings and adds explicit source/raw verification, target-only core acoustic delays and leakage measurements, not a newly discovered dataset or new independent test.'},
          'source': {'official': 'https://www.openslr.org/119/', 'archiveBytes': acquisition['bytes'],
                     'archiveSha256': acquisition['sha256'], 'gzipCrcVerified': True,
                     'session': audit['session'], 'farSeconds': audit['farWave']['seconds'],
                     'nearSeconds': [p['wave']['seconds'] for p in audit['pairedPeople']],
                     'people': 4, 'referenceUtterances': audit['referenceUtterances'],
                     'annotatedOverlapSeconds': audit['annotatedOverlapSeconds'],
                     'split': 'Eval, exposed diagnostic only, not training or final holdout'},
          'actualFindings': [{'speaker': p['speaker'], 'referenceUtterances': p['referenceUtterances'],
                             'exactReferenceMatch': p['referenceExactlyMatchesFarTier'],
                             'ownVsOtherSoloMedianRmsDb': p['relativeLeakage']['ownVsOtherMedianDb'],
                             'fineDelay': p['fineDelaySummary']} for p in audit['pairedPeople']],
          'decision': 'Matched source microphones are useful for measuring recognition ceilings; they are NOT automatically clean or sample-aligned waveform training targets. Keep source/audio clocks intact. Measured local acoustic offsets are not the22.03s file-length difference and include room propagation; weak/variable peaks do not justify global resampling.',
          'preparation': prepared,
          'repairsAndFailures': [
              'Python3.11 wave rejected official far WAVE_FORMAT_EXTENSIBLE65534. Added bounded PCM16 RIFF/GUID reader; first/middle/last frames on all5 sources bit-exact against scipy mmap. No transcoding or lossy decode introduced.',
              'First extractor selected underscore-prefixed filenames and missed exact session.TextGrid; retained original incomplete manifest, fixed selection and asserted far reference presence.',
              'Whole-utterance isolation yielded no clock window for8015 despite213.66s target-only frames. R1 retained; R2 measures interior exclusive cores in each meeting third, never uses cut phrases for CER.',
              'R6 optional model-pack metadata was not yet exported; source pilot and model binding were already passed. Exported its existing opt-in pack, not new weights/model/installation. Actual ASR deferred due absent external GPU.',
          ],
          'resourceAndTime': {'acquisitionSeconds': acquisition['wallSeconds'],
              'archiveReuseVerifiedSeconds': read_json(C / 'download-reuse-result.json')['wallSeconds'],
              'secondExtractionSeconds': extraction['wallSeconds'],
              'auditWorkerSeconds': audit['wholeWorkerSeconds'],
              'auditPeakJobPrivateBytes': audit['limits']['jobPeakPrivateCommitBytes'],
              'inferenceSeconds': None, 'inferenceNotPerformed': True,
              'cpuMaximumPercent': 5, 'otherApplicationsClosed': False, 'pagefileChanged': False},
          'ordinaryBestStrictCerUnchanged': 461/8325, 'newModelCalls': 0,
          'newTrainingRuns': 0, 'newIndependentMeetings': 0, 'newAccuracyGain': False,
          'productSourceChanged': False, 'installedProductChanged': False,
          'phoneOrBoardAccessed': False, 'finalHoldoutOpened': False,
          'formalQualityTargetsChanged': False, 'saleQualified': False, 'next': NEXT}
dump(C / 'decision.json', record)
dump(C / 'preparation-failures.json', {'recordedAt': now(), 'preparationOnly': True,
     'failures': record['repairsAndFailures'], 'noModelInferencePerformed': True})
EV.mkdir(parents=True, exist_ok=True)
for file in C.iterdir():
    if file.is_file() and file.suffix in ['.json', '.py', '.txt']:
        shutil.copyfile(file, EV / file.name)
for file in extraction['files']:
    if file['name'].endswith('.TextGrid'):
        target = EV / 'references' / file['side'] / Path(file['path']).name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file['path'], target)
        assert digest(target) == file['sha256']
pack_path = Path(prepared['modelPack'])
pack = read_json(pack_path)
for rel in pack['pinnedFiles']:
    target = EV / 'bound-asr-source-control' / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(pack['sourceControl']) / rel, target)
    assert digest(target) == pack['pinnedFiles'][rel]
shutil.copyfile(pack_path, EV / 'bound-asr-source-control/model-pack.json')
(EV / 'SOURCE_ATTRIBUTION.txt').write_text('AliMeeting, Alibaba Group. Official source: https://www.openslr.org/119/\nLicense published by provider: CC BY-SA 4.0, https://creativecommons.org/licenses/by-sa/4.0/\nReferences are unchanged provider TextGrid files. Archive/audio hashes and acquisition URLs are recorded. Public large audio remains in reconstructible E cache, not Git.\nThis is an exposed development diagnostic, not independent final evaluation.\n', encoding='utf8')
names = ['acquire_alimeeting_paired_eval_20261109.py', 'extract_alimeeting_paired_session_20261109.py',
         'paired_meeting_pcm16_20261109.py', 'audit_alimeeting_paired_session_20261109.py',
         'prepare_alimeeting_fixed_asr_20261109.py']
attr = M / '.gitattributes'
attr_text = attr.read_text(encoding='utf8')
for name in names:
    rule = 'src/' + name + ' -text'
    if rule not in attr_text:
        attr_text += '\n' + rule + '\n'
attr.write_text(attr_text, encoding='utf8')
model_head = ship(M, ['.gitattributes', str(EV.relative_to(M)).replace('\\','/')] + ['src/'+name for name in names], 'Restore real paired Mandarin meeting and audit source leakage without new models')
record.update(modelEvidenceCommit=model_head, remoteModelReadbackConfirmed=True)

path = R / 'docs/product_backlog.json'
for attempt in range(8):
    original = path.read_bytes()
    d = json.loads(original)
    quality = json.dumps(d['quality_targets'], sort_keys=True, ensure_ascii=False)
    node = d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
    if KEY not in node:
        record.update(previousStatus=node.get('status'), previousWorkpoint=node.get('next'))
    else:
        record.update(previousStatus=node[KEY].get('previousStatus'), previousWorkpoint=node[KEY].get('previousWorkpoint'))
    node[KEY] = record
    node.update(status=STATE, next=NEXT)
    assert quality == json.dumps(d['quality_targets'], sort_keys=True, ensure_ascii=False)
    tmp = path.with_suffix('.paired-real.tmp')
    dump(tmp, d)
    if path.read_bytes() != original:
        tmp.unlink()
        continue
    try:
        os.replace(tmp, path)
    except PermissionError:
        tmp.unlink(missing_ok=True)
        time.sleep(min(.05*2**attempt, 2))
        continue
    break
else:
    raise RuntimeError('Canonical backlog busy; model evidence already remote')
log = R / 'docs/development_log.md'
before = log.read_bytes()
if MARKER not in before.decode('utf8'):
    entry = ('\n\n## '+record['at']+'｜'+MARKER+'\n\n'
        '承接Owner“那继续按照这个推进咯”。检索旧源码和原待办确认11月4日曾准备2场8耳麦及粗时钟/标注一致性，原E缓存已清；纠正上一轮“仅来源说明”的过宽表述。'
        '本轮从官方恢复原暴露R8001_M8004一场：archive3673718355B/SHA256 '+acquisition['sha256']+'，完整gzip CRC；远场1573.85s/8ch、四近讲各1551.82s、604段人物文字与时间逐条一致、参考区重叠456.28s。'
        '扩展PCM16头读取失败、精确session参考漏选、整句孤立条件造成8015时钟无覆盖均保留证据后修源；所有5源首中尾PCM与SciPy逐样本一致。'
        '四人本人口述/他人单独讲话的中位RMS差25.40/30.75/30.45/31.59dB，仅相对串音证据；每人三个时段共12声学延迟窗口仍有弱相关/变化，不声称精确干净source、不用22.03s时长差偏移，不启动波形监督训练。'
        '固定四近讲完整输入与一路共同1551.82s原混音到已验短控制的现有Qwen1.7B边界方案，原始单路样本位精确，人物参考不入推理。R6可选包元数据原缺失已按原导出器生成；当前PnP仅780M无6800XT，真实识别待外置GPU及新HIP身份绑定，不能假称取得新CER。'
        '下载292.006s/私有峰24256512B；R2数据审计2.904s/私有峰530784256B，全部后台5%CPU；时长为具体进程墙钟非人工工时，零新模型/训练/准确率增益、无手机/板卡/日用安装/留出操作。'
        '普通461/8325=5.53754%及原全部售卖门不变。代码、参考、哈希、失败、固定输入和可恢复来源'+model_head+'已远端核验；大音频在E可按固定来源/hash恢复，不冒充Git内含GB音频。下一项：'+NEXT+'\n')
    with log.open('ab') as handle:
        handle.write(entry.encode('utf8'))
    assert log.read_bytes().startswith(before)
DEST.mkdir(parents=True, exist_ok=True)
for src in [path, log]:
    shutil.copyfile(src, S / 'docs' / src.name)
dump(DEST / 'decision.json', record)
for name in ['pair-audit-result.json', 'fixed-asr-preparation.json', 'download-result.json']:
    shutil.copyfile(C / name, DEST / name)
shutil.copyfile(__file__, DEST / Path(__file__).name)
attr = S / '.gitattributes'
text = attr.read_text(encoding='utf8')
rule = 'docs/handoffs/model-paired-real-meeting-20261109/** -text -whitespace'
if rule not in text:
    attr.write_text(text+'\n'+rule+'\n', encoding='utf8')
main_head = ship(S, ['.gitattributes', 'docs/product_backlog.json', 'docs/development_log.md', str(DEST.relative_to(S)).replace('\\','/')], 'Record restored real source diagnostic and pending fixed ASR comparison')
node = read_json(path)['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerNightGpuModelPriority20261104']
assert node['status'] == STATE and node['next'] == NEXT
print(json.dumps({'state': STATE, 'modelCommit': model_head, 'deliveryCommit': main_head,
                  'bothRemoteHeadsVerified': True, 'modelWorkingTree': git(M, 'status', '--short'),
                  'deliveryWorkingTree': git(S, 'status', '--short'), 'newModelCalls': 0,
                  'newAccuracyGain': False, 'nextReadback': node['next']}, ensure_ascii=False), flush=True)
