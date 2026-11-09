"""Preserve the owner-clicked acceptance entry and consume existing firmware evidence."""
from pathlib import Path
import ast, copy, hashlib, json, os, shutil, subprocess
from datetime import datetime

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
S = R / 'companion-device-closure055'
C = R / 'docs/handoffs/20261109-core-acceptance'
DEST = S / 'docs/handoffs/core-acceptance-20261109'
now = datetime.now().astimezone().isoformat(timespec='seconds')
bp = R / 'docs/product_backlog.json'
original = bp.read_bytes()
d = json.loads(original)
quality = copy.deepcopy(d['quality_targets'])
f = d['owner_module_execution']['frontendWindowsMobile20261102']
b = f['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']
rp = R / 'docs/handoffs/20261106-companion-device-management/full-media66762/core771-device-chain-acceptance.json'
receipt_bytes = rp.read_bytes()
short = json.loads(receipt_bytes)
assert short['firmware'] == 66771 and short['runtime']['timing']['encodePeakUpperUs'] == 6510
observed = {
    'observedAt': now, 'receiptAt': short['at'], 'firmware': short['firmware'],
    'sourceCommit': short['sourceCommit'], 'receipt': str(rp),
    'receiptSha256': hashlib.sha256(receipt_bytes).hexdigest(),
    'shortGates': short['shortGates'], 'liveGates': short['liveGates'],
    'timing': short['runtime']['timing'],
    'twoHourCurrentFirmwareQualified': False, 'saleQualified': False,
    'scope': 'Consumed existing peer receipt only; no board operation, no new recording or audio upload.',
    'nextFromOriginalFirmwareTask': d['owner_module_execution']['embedded']['next'],
}
entry = {
    'at': now, 'script': str(C / 'open_public_meeting.py'),
    'scriptSha256': hashlib.sha256((C / 'open_public_meeting.py').read_bytes()).hexdigest(),
    'shortcut': 'C:/Users/Billy/Desktop/Companion - 公开会议验收.lnk',
    'sameSessionId': 'import-00817de5e4dc4f55b9119da5a170fcaa',
    'publicProfileOnly': True, 'checkOnlyPassed': True, 'appStartedByThisWork': False,
    'qualification': 'Owner-clicked review of existing actual public meeting; not a customer or physical-board acceptance.',
}
b['wholeCandidateCurrent']['ownerReviewEntry'] = entry
b['wholeCandidateCurrent']['latestFirmwareScopedResult'] = observed
b['latestFirmwareScopedResult'] = observed
facts = ('769已保存2小时3分原音、录中同步与完整音频；771短录全部门通过，'
         '183.45秒录中同步的PDM峰2.832ms<3ms、零采集故障通过，编码峰6.510ms>6ms仍失败。'
         '原嵌软任务继续定位准入/中断路径，当前固件两小时与异常恢复未合格，不继承旧长录。')
for gaps in [b['remainingSaleBlocks'], b['wholeCandidateCurrent']['saleGaps']]:
    for gap in gaps:
        if gap['block'] == '长录/连接/异常恢复可靠性':
            gap['facts'] = facts
b['wholeWindowsCoreIntegration']['state'] = 'MATCHED_WINDOWS080_SOURCE_BUILT_INSTALLED_WHOLE_PUBLIC_MEETING_PROVEN'
b['wholeCandidateCurrent']['integratedWindowsCore']['state'] = b['wholeWindowsCoreIntegration']['state']
assert d['quality_targets'] == quality and bp.read_bytes() == original
bp.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
(C / 'whole-candidate-result.json').write_text(json.dumps(b['wholeCandidateCurrent'], ensure_ascii=False, indent=2) + '\n', encoding='utf8')
(C / 'owner-review-entry.json').write_text(json.dumps(entry, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
(C / 'latest-firmware-scoped-result.json').write_text(json.dumps(observed, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
guide = R / 'docs/CORE_ACCEPTANCE_CANDIDATE.md'
text = guide.read_text(encoding='utf8').replace('两项长期峰值、复杂多人', '当前固件长录及编码峰、复杂多人')
assert '## 实际体验入口' not in text
text += '''\n## 实际体验入口\n\n桌面“Companion - 公开会议验收”打开已经完成真实转写和AI整理的同一场公开会议；使用独立资料库，不需要重新推理。入口已只读检查，未由本轮自动打开窗口。此入口供Owner验收，尚无新客户体验结论。\n\n[Windows 0.1.80 安装包](C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-core-acceptance/candidate080/Companion-Windows-0.1.80-candidate.msi) · [Android 0.1.110 候选安装包](C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-core-acceptance/android110/Companion-Android-0.1.110-core-candidate.apk)\n\n实卡结果范围：769的2小时3分原音、录中同步和完整性通过；后续771的短录PDM峰改善至2.832ms，编码峰6.510ms仍超6ms，不能写成当前长录或整机合格。后续观察固件由原嵌软任务接续，不在本入口操作板卡。\n'''
guide.write_text(text, encoding='utf8')
log = R / 'docs/development_log.md'
with log.open('a', encoding='utf8') as out:
    out.write('\n\n' + now + ' · 同一完整候选收尾：桌面公开会议验收入口只读检查通过，未自动打开窗口；Windows080及Android110安装包、来源和恢复证据均已远端回读。消费原771收据：短录全过，183.45秒录中同步PDM峰2832us通过、编码峰6510us失败，当前固件2h仍未合格；不重录、不碰原嵌软控制。公开38m47s软件链和实卡长录为不同录音，不合并宣称实卡转写/AI全链条。模型<5%、真机、分享附件及既有售卖依赖保留。下一项沿原待办：手机在线后使用110验证同场保存/恢复/回听/AI及升级保留；固件编码峰由原任务修源头，模型不因功能链通过而降低标准。\n')
paths = []
for name in ['product_backlog.json', 'development_log.md', 'CORE_ACCEPTANCE_CANDIDATE.md']:
    target = S / 'docs' / name
    shutil.copyfile(R / 'docs' / name, target)
    paths.append(str(target.relative_to(S)).replace('\\', '/'))
for name in ['open_public_meeting.py', 'finalize_owner_entry.py', 'owner-review-entry.json', 'latest-firmware-scoped-result.json', 'whole-candidate-result.json']:
    target = DEST / name
    shutil.copyfile(C / name, target)
    paths.append(str(target.relative_to(S)).replace('\\', '/'))
publisher = S / 'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py'
source = publisher.read_text(encoding='utf8')
tree = ast.parse(source)
env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_SSH_COMMAND': 'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
scope = {'subprocess': subprocess, 'env': env}
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in ['git', 'ship']:
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(publisher), 'exec'), scope)
commit = scope['ship'](S, paths, 'Preserve complete candidate review entry and scoped firmware result')
result = {'at': now, 'remoteCommit': commit, 'remoteReadbackVerified': True, 'sourceAndCandidatePackagesAlreadyProtected': True, 'entryCheckOnlyPassed': True, 'appStarted': False, 'saleQualified': False}
(C / 'owner-entry-preservation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps(result, ensure_ascii=False))
