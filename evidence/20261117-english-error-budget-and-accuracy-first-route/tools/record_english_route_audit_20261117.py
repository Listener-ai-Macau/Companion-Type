"""Reconcile the owner's route question into the one existing work point."""
from pathlib import Path
from datetime import datetime
import hashlib, json, psutil

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
D = R / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J = D / 'joint-architecture-r1'
E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

audit_path = J / 'english-route-audit-20261117.json'
metadata_root = E / 'language-specific-adaptation-r1/english-accuracy-reference-20261117'
meta_path = metadata_root / 'metadata-receipt.json'
audit, meta = read(audit_path), read(meta_path)
assert audit['wholeClipOracleSelection']['fourExistingModelsErrors'] == 101
assert audit['parakeetErrorBudget']['errorsToRemoveForFivePercent'] == 88
assert not audit['qualityQualified'] and not meta['largeWeightsDownloaded']
at = datetime.now().astimezone().isoformat(timespec='seconds')
snapshot = {
    'at': at, 'audit': str(audit_path), 'auditSha256': sha(audit_path),
    'referenceMetadata': str(meta_path), 'referenceMetadataSha256': sha(meta_path),
    'state': 'ACCURACY_FIRST_OFFLINE_ENGLISH_REFERENCE_SELECTED_NOT_EXECUTED',
    'decisionBasis': 'Fixed English123/709 requires88 fewer errors to reach5%; even reference-assisted whole-clip switching among4existing models yields101/709. ExactF32/PCM/frontend lengths and encoder exhaustion agree with receipts. No evidence that more routing, filler cleanup or119M CPU memory work will close the71.5%relative gap.',
    'previousWorkPointPreserved': 'Original one-epoch1828-clip meeting adaptation remains prepared and untrained; suspend next mapped-state CPU workaround pending a substantially stronger quality reference. Do not call that recipe a trained failure.',
    'next': 'One pinned official GraniteSpeech4.1-2B accuracy reference, publishedBF16, original709words/no reference in inference. Inspect compatibility and resource feasibility before large assets/model load; no custom engine port or parameter/model roster. Add the stricter70errors/no-meeting-regression intermediate gate to the original99gate; then original whole-source/person/facts/final gates. 70/709 is not sale qualification.',
    'repository': meta['repository'], 'revision': meta['revision'],
    'availableRamBytesAtInspection': psutil.virtual_memory().available,
    'checkpointTensorBytes': meta['totalCheckpointTensorBytes'],
    'privateLimitBytes': 2147483648, 'minimumAvailableRamBytes': 3414499000,
    'resourceCaveat': '4.626GB checkpoint resident in host RAM plus current realRAM floor needs more than the present availableRAM even before runtime/activation overhead. This is a conservative placement estimate, not a measured OOM. CPU or integratedGPU training remain authorized; they are not mandatory for this next inference reference.',
    'newNeuralCalls': 0, 'newTrainingUpdates': 0,
    'finalHoldoutOpened': False, 'qualityQualified': False, 'saleQualified': False,
}
assert snapshot['availableRamBytesAtInspection'] < snapshot['checkpointTensorBytes'] + snapshot['minimumAvailableRamBytes']
point = Path('work/bilingual_progress.json')
x = read(point)
j = x['jointArchitecture20261115']
o = j['overnightExecution20261116']
j['weekDirectionReview20261117']['englishRouteReassessment20261117'] = snapshot
o['englishAccuracyReference20261117'] = snapshot
x['ownerLatestEnglishRouteQuestion20261117'] = audit['ownerQuotes']
x['state'] = 'ENGLISH_ROUTE_REASSESSED_ACCURACY_REFERENCE_PINNED_NOT_EXECUTED'
x['next'] = snapshot['next']
x['nativeInferencePerformedThisBatch'] = False
x['qualityQualified'] = x['saleQualified'] = False
marker = 'ENGLISH_ROUTE_REASSESSMENT_20261117'
assert marker not in x['logResult'], 'Do not duplicate one batch in the canonical timeline'
x['logResult'] += (
    f'\n\n{at}｜{marker}｜承接Owner关于英文差距/5%与新路线的两条原话。'
    '只复用原2场12段/709词，核对原F32设备往返、每条原PCM/WAV哈希、输入特征长度与encoder确实走完；'
    '不是独立NeMo全模型等价证明，也不把走完输入当每个词已识别。Parakeet123错由56替换/46删除/21插入构成；'
    '要到5%最多35错，需少88错/71.54%相对降低。即使零新增地修完全部46删除仍77/709=10.86%；'
    '原对齐中明确uh/um等填充词删除为0，不以删口头词或改标准参考冲95。'
    '用参考挑每段完整输出的诊断oracle：MOSS/Parakeet103/709，含Qwen和完整Whisper四者101/709=14.25%；'
    '仅排除当前完整输出级选择可达5%，未声称词级融合或所有组合架构不可能。'
    '官方Parakeet表AMI11.31/朗读1.93、IBM同NAR模型IHM7.91/SDM19.59说明录音/协议影响；'
    '均为异协议发布成绩，不与本批直接排名、不当物理极限。中文CER/英文WER和不同会议不直接比较。'
    '决定改为先证明英文离线终稿强底座，再会议域适配/蒸馏/轻量化；原增量链与专用人物组件保留，重叠后置。'
    '暂停新的119M文件映射CPU反向系统，原4.18小时/1828例适配仍0更新，不称训练失败。'
    f'仅固定一个GraniteSpeech4.1-2B原生参考{meta["revision"]}，官方BF16权重元数据4626414392B，'
    '已核小配置和现有Transformers源码存在，未下载大权重/执行模型/新增准确率。当前RAM不足以同时满足全部驻留权重和原真实RAM余量，'
    '不放松资源、不自写引擎；CPU/核显依旧允许，温度仅观察。新增70错且每场不回退的中间门，比原99门更严，'
    '不降低最终5%底线/2%目标及逐人事实门，不把两场已暴露片段当跨会议合格。'
    f'本轮无新神经/更新/最终集读取，收据{audit_path}；原待办下一项已据此改向。'
)
point.write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

files = [
    {'source': str(Path('work') / name), 'name': 'tools/' + name}
    for name in ('audit_english_route_20261117.py', 'inspect_english_accuracy_reference_20261117.py',
                 'record_english_route_audit_20261117.py', 'english_accuracy_reference_api_20261117.json')
]
files.append({'source': str(audit_path), 'name': 'english-route-audit.json'})
for p in sorted(metadata_root.iterdir()):
    assert p.is_file() and p.stat().st_size < 2 * 1024**2
    files.append({'source': str(p), 'name': 'reference-metadata/' + p.name})
config = {
    'revision': 72, 'evidenceDirectory': 'evidence/20261117-english-error-budget-and-accuracy-first-route',
    'sources': [], 'closedDirectories': [], 'files': files,
    'commitMessage': 'Audit fixed English error budget and oracle routing; pin one accuracy-first offline reference',
    'claims': {'state': x['state'], 'newNeuralCalls': 0, 'newTrainingUpdates': 0,
               'oracleSelectionIsDeployable': False, 'newReferenceQualityProven': False,
               'originalScoresAndGatesPreserved': True,
               'rawAudioInputFeaturesModelWeightsOrCredentialsIncluded': False,
               'qualityQualified': False, 'saleQualified': False},
}
Path('work/checkpoint_english_route_r72.json').write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'state': x['state'], 'oracleWholeClipErrors': 101,
                  'reference': meta['repository'], 'revision': meta['revision'],
                  'largeWeightsDownloaded': False, 'sourceFilesForProtection': len(files)}, ensure_ascii=False))
