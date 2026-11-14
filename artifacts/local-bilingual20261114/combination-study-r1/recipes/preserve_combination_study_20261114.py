from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import zipfile
import psutil

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
MODEL = ROOT / 'model-research'
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/combination-study-r1'
CACHE = Path('E:/CodexData/Companion/.model-cache/ordinary-combination-study-20261114')
ARTIFACT = MODEL / 'artifacts/local-bilingual20261114/combination-study-r1'
WORK = Path(__file__).resolve().parent
OUT = WORK.parent / 'outputs'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))


def sha(p):
    with Path(p).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def copy(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    assert sha(source) == sha(dest)


assert read(CONTROL / 'remaining-run.json')['state'] == 'COMPLETE_FROZEN_COMBINATION_BATCH_REVIEW_PENDING'
result = read(CONTROL / 'result.json')
assert result['state'] == 'COMPLETE_TWO_FROZEN_COMBINATIONS_QUALITY_NOT_QUALIFIED'
assert not result['qualityQualified'] and not result['saleQualified']
assert not ARTIFACT.exists()
ARTIFACT.mkdir(parents=True)
(ARTIFACT / '.gitattributes').write_text('* -text -whitespace\n', encoding='utf-8')

# Preserve every attempt, raw node, resource log and result, without model weights
# or source PCM. Absolute source/cache paths remain recorded; path-map is explicit.
for file in sorted(CONTROL.rglob('*')):
    if file.is_file():
        assert file.suffix.lower() in {'.json', '.jsonl', '.log', '.txt', '.rttm', '.py'}, file
        copy(file, ARTIFACT / 'control' / file.relative_to(CONTROL))
for file in sorted((CACHE / 'qwen').rglob('*')):
    if file.is_file():
        assert file.suffix.lower() in {'.json', '.jsonl', '.log', '.txt'}, file
        copy(file, ARTIFACT / 'qwen-cache' / file.relative_to(CACHE / 'qwen'))
probability_dir = CACHE / 'native8-probabilities' / result['audio']['meeting']
for file in probability_dir.iterdir():
    if file.is_file():
        copy(file, ARTIFACT / 'native-posteriors' / file.name)
reference, = read(CONTROL / 'scoring-only.json')
copy(Path(reference['reference']), ARTIFACT / 'source-reference' / Path(reference['reference']).name)
for name in ['prepare_combination_study_20261114.py', 'prepare_combination_alignment_20261114.py',
             'join_combination_study_20261114.py', 'run_combination_remaining_20261114.py',
             'diagnose_combination_diarization_20261114.py', 'run_normal_turn_alignment_20261114.py',
             'preserve_combination_study_20261114.py', 'recover_combination_packaging_20261114.py']:
    copy(WORK / name, ARTIFACT / 'recipes' / name)
source_files = ['run_paraformer_matched_spans_20261114.py', 'practical_alignment_session_worker_20261114.py',
                'companion_local_speaker_document_20261114.py', 'companion_exclusive_journal_20261114.py',
                'practical_qwen_audio_boundaries_20261107.py', 'practical_qwen_boundaries_worker_20261107.py',
                'practical_nemotron_worker_20261107.py', 'run_bound_native_cases_20261114.py',
                'score_practical_transcript_20261107.py', 'score_practical_regions_20261107.py']
for name in source_files:
    copy(MODEL / 'src' / name, ARTIFACT / 'source-snapshot' / name)
write(ARTIFACT / 'path-map.json', {'originalControl': str(CONTROL), 'preservedControl': 'control/',
                                  'originalQwenCache': str(CACHE / 'qwen'), 'preservedQwenCache': 'qwen-cache/',
                                  'originalPosteriors': str(probability_dir), 'preservedPosteriors': 'native-posteriors/',
                                  'absoluteBindingsUnchanged': True, 'sourcePcmAndWeightsExcluded': True})

rows = []
for arm in result['arms']:
    quality = arm['views']['exclusive-frozen']
    raw = quality['rawCer']
    cp = quality['cpCer']
    rows.append({'arm': arm['arm'], 'referenceCharacters': arm['referenceCharacters'],
                 'rawCer': raw['cer'], 'rawEditCounts': raw['edits'],
                 'integratedCpCer': cp['characterErrorRate'], 'integratedEdits': cp['totalEdits'],
                 'unknownCharacters': quality['unknown']['characters'],
                 'unknownForcedUnmatchedCer': quality['unknownForcedUnmatched']['cer'],
                 'sourceTextPreserved': True,
                 'conservativeControlCpCer': arm['views']['conservative-control']['cpCer']['characterErrorRate'],
                 'paragraphs': quality['paragraphs']})
speaker = result['sharedRawSpeakerQuality']
report = {'at': datetime.now().astimezone().isoformat(timespec='seconds'),
          'state': result['state'], 'meeting': result['audio']['meeting'],
          'seconds': result['audio']['audioSeconds'], 'microphones': 1,
          'referencePeople': speaker['referenceSpeakers'],
          'referenceOverlapSeconds': result['sharedRawSpeakerRegions']['regions']['twoOrMore']['audioRegionSeconds'],
          'rows': rows, 'rawSpeakerDer': speaker['components']['diarization error rate'],
          'nonOverlapIncludingSilenceDer': result['sharedRawSpeakerRegions']['regions']['nonOverlapIncludingSilence']['derWithFrozenGlobalAssignment'],
          'overlapDer': result['sharedRawSpeakerRegions']['regions']['twoOrMore']['derWithFrozenGlobalAssignment'],
          'shortReferenceSpans': speaker['shortReferenceSpans'],
          'resourceAttempts': {'diarization': result['sharedDiarizationAttempt']['results'],
                               'qwen': result['qwenAttempt']['attempts'],
                               'paraformer': result['paraformerAttempt'],
                               'alignment': result['sharedAlignmentAttempt']['results']},
          'availableMemoryBytesAfter': psutil.virtual_memory().available,
          'trainedNewWeights': False, 'selectedPerWordBestOutputs': False,
          'ownerLatestConstraint': '现在主要还是不要太多瞎尝试',
          'furtherExperiments': 'No new models, training or threshold trials launched after this frozen comparison. Next intervention requires a concrete cause, one fixed change and success/stop criteria.',
          'sameFrozenAudioAndRootSpans': True, 'sameSharedSpeakerAlignerAndFusion': True,
          'dataScope': result['dataScope'], 'completeEnglishMeetingOrRealCardQualified': False,
          'qualityQualified': False, 'saleQualified': False}
write(ARTIFACT / 'delivery-result.json', report)
write(OUT / 'Companion-组合模型对比-结果-20261114.json', report)

note = ['Companion 组合模型对比｜2026-11-14', '',
        '方向：已有成熟模型分工，转写负责文字，分人负责匿名人物活动，对齐负责把原字定位到原音，固定融合负责说话人日志。尚未训练新权重。',
        '本批固定比较两套：Qwen3-ASR-1.7B 与现有 Paraformer int8；共同使用相同 Native8 FP16、Qwen ForcedAligner0.6B 和原 exclusive/60ms 起点归属规则。保守归属仅为共同控制，不能逐句择优。',
        f"新完整开发会 {report['meeting']}，{report['seconds']:.4f} 秒，4人、单麦，参考重叠 {report['referenceOverlapSeconds']:.4f} 秒；整场采样完整保留，两套68个原始切分一致。没有删重叠、静音或难段。",
        '该来源为官方Train分区，首次用于这套完整组合对比；不称预训练独立、最终留出或用户录音卡。原AISHELL4 CC-BY-SA-4.0来源与固定修订保留。', '']
for row in rows:
    note.append(f"{row['arm']}：原字CER {row['rawCer']:.4%}，逐人cpCER {row['integratedCpCer']:.4%}（{row['integratedEdits']}/{row['referenceCharacters']}），待确认 {row['unknownCharacters']} 字；待确认强制不匹配的独立诊断 {row['unknownForcedUnmatchedCer']:.4%}。")
note += ['', f"共同原始人物活动DER {report['rawSpeakerDer']:.4%}，非重叠含静音 {report['nonOverlapIncludingSilenceDer']:.4%}，重叠 {report['overlapDer']:.4%}，均固定整场人物映射、零容差。",
         f"短于2秒参考发言 {speaker['shortReferenceSpans']['count']} 条，其中 {speaker['shortReferenceSpans']['zeroCorrectSpans']} 条无正确人物归属。",
         '独立诊断确认：参考003-M独自讲话时约62.85秒被另一个人物004-M的声部覆盖。非重叠问题仍明显，不能把失败全部归于抢话。以上参考编号只用于评分，不输入推理，也不作真实身份。', '',
         '两套均保留每个模型原字、标点与换行；没有删除口头词、润色、补标准答案或按句选择更好模型。独立对齐的词时刻仍是预测值，不称真实字级时间验证。exclusive视图不能恢复重叠第二路文字；原多人日记和后验数组另存。',
         '资源：一次只跑一个神经模型，CPU5%、各模型族私有提交上限2GiB、Windows实际低内存停止保留。Paraformer走现有Python sherpa-onnx CPU，属于模型级对比；不冒充已安装产品实测，也不据CPU/GPU不同路径宣称通用速度胜负。',
         '结论边界：该新场人物DER未达10%，即使某一路文字较好也不能称整套复杂会议合格。继续按错误归属修对应模块并保住上一场；中英文长会、密集重叠、事实/数字/否定、跨房间留出、Windows/Android和实卡仍未验收。',
         'Owner最新约束：现在主要还是不要太多瞎尝试。本轮冻结两套比较已完成，此后不新增模型、训练、阈值或片段试跑；下一次干预先列明一个具体根因假设、固定改动和成功/停止标准。', '',
         '本包含完整匿名转写、逐字归属轨迹、全部原始模型节点与失败、评分/资源日志、后验数组、固定协议和源码快照；不含模型权重或源录音。']
(OUT / 'Companion-组合模型对比-说明-20261114.txt').write_text('\n'.join(note)+'\n', encoding='utf-8')
for arm in result['arms']:
    doc = read(arm['views']['exclusive-frozen']['outputFile'])
    name = 'Companion-'+arm['arm']+'-完整匿名会议-20261114'
    write(OUT / (name+'.json'), doc)
    lines = []
    for row in doc['utterances']:
        speaker_label = '待确认' if row['speaker'] is None else '说话人'+str(row['speaker']+1)
        def stamp(ms):
            seconds = ms/1000
            return f'{int(seconds//60):02d}:{seconds%60:06.3f}'
        lines.append('['+stamp(row['startMs'])+'—'+stamp(row['endMs'])+'] '+speaker_label+'\n'+row['text'])
    (OUT / (name+'.txt')).write_text('\n\n'.join(lines)+'\n', encoding='utf-8')
    assert doc['text'] == ''.join(row['text'] for row in doc['utterances'])

files = [{'path': str(p.relative_to(ARTIFACT)).replace('\\', '/'), 'bytes': p.stat().st_size,
          'sha256': sha(p)} for p in sorted(ARTIFACT.rglob('*')) if p.is_file()]
write(ARTIFACT / 'manifest.json', {'files': files, 'allFilesVerifiedAtCopy': True,
                                 'noPcmOrWeights': True, 'qualityQualified': False})
archive = OUT / 'Companion-组合模型对比-完整证据-20261114.zip'
assert not archive.exists()
with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
    for file in sorted(ARTIFACT.rglob('*')):
        if file.is_file():
            bundle.write(file, str(file.relative_to(ARTIFACT)))
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    for row in files:
        assert hashlib.sha256(bundle.read(row['path'])).hexdigest() == row['sha256']
receipt = {'at': report['at'], 'artifact': str(ARTIFACT), 'archive': str(archive),
           'bytes': archive.stat().st_size, 'sha256': sha(archive), 'verifiedFiles': len(files),
           'qualityQualified': False}
write(OUT / 'Companion-组合模型对比-交付校验-20261114.json', receipt)
print(json.dumps({'report': report, 'delivery': receipt}, ensure_ascii=False))
