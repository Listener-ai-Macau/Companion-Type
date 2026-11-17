"""Record one requested source-backed survey in the existing model work item."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, json

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
D = R / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J = D / 'joint-architecture-r1'
E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

gap_path = J / 'language-gap-diagnosis.json'
gap = read(gap_path)
raw_path = D / 'sequential-meeting-stageA-r2/raw-text-baseline.json'
assert sha(raw_path) == gap['rawScoreSha256']
cn, en = gap['groups']['Chinese'], gap['groups']['English']
assert (cn['sameUnitCharacterErrors'], en['sameUnitCharacterErrors']) == (73, 328)
energy_path = J / 'english-acoustic-omission-summary20261116.json'
energy = read(energy_path)
assert energy['baselineErrors'] == 141 and energy['referenceWords'] == 709
whole_path = J / 'cpu-fixed-whole-r2/full-score.json'
hard = next(v for v in read(whole_path)['meetings'] if v['meeting'] == '20200623_S_R001S07C01')
ref_root = E / 'language-specific-adaptation-r1/english-accuracy-reference-20261117'
source_dir = ref_root / 'research-sources'
assert len(list(source_dir.iterdir())) == 6
assert 'ami_cleaned test' in (source_dir / 'OpenASR-MOSS-submit_jobs.sh').read_text(encoding='utf-8')
assert 'ami_cleaned test' in (source_dir / 'OpenASR-Parakeet-submit_jobs.sh').read_text(encoding='utf-8')

report = {
    'at': at,
    'state': 'REQUESTED_OPEN_SOURCE_SURVEY_COMPLETE_NO_NEW_MODEL_EXPERIMENT',
    'ownerQuote': '对啊，那你看一下有没有什么开源的东西可以做这个事情的，然后的话。然后你先调研一下方案吧，我感觉为什么中文跟英文会差这么远？',
    'researchScope': 'Official repositories, model cards and research papers for single-channel local incremental/offline meeting ASR; prioritize ordinary nonoverlap, distinguish speaker timing from audio separation.',
    'languageGap': {
        'measurementUnit': {
            'originalQwenChineseCER': {'errors': 73, 'units': 1258, 'rate': 73/1258},
            'originalQwenEnglishWER': {'errors': 141, 'units': 709, 'rate': 141/709},
            'existingDiagnosticEnglishCharacterRate': {'errors': 328, 'units': 2794, 'rate': 328/2794},
            'existingDiagnosticChineseCharacterRate': {'errors': 73, 'units': 1258, 'rate': 73/1258},
            'interpretation': 'Part of the apparent gap is CER/WER; a real descriptive gap remains in this old Qwen cohort under the same character convention. Not a new Parakeet score, not a controlled cross-language causal experiment, and not a changed acceptance metric.',
            'source': str(gap_path), 'sourceSha256': sha(gap_path),
        },
        'recordingAndCohort': {
            'chineseNotGenerallyQualified': True,
            'harderChineseExistingQwenBaseline': {'meeting': hard['meeting'], 'errors': hard['baselineRawText']['errors'],
                'referenceCharacters': hard['baselineRawText']['referenceUnits'], 'CER': hard['baselineRawText']['errorRate']},
            'sameModelPublishedEnglishExample': {'repository': 'Qwen/Qwen3-ASR-1.7B', 'LibriSpeechCleanWER': 1.63, 'GigaSpeechWER': 8.45, 'CommonVoiceEnglishWER': 7.39},
            'samePublishedGraniteNARModelConditions': {'AMI_IHM_WER': 7.91, 'AMI_SDM_WER': 19.59},
            'interpretation': 'Recording setup, colloquial speech, speakers and reference conventions are confounded with language in our recordings. Published figures illustrate condition sensitivity; they do not reproduce our test or quantify the causal share of each condition.',
        },
        'acousticAssociationAlreadyMeasured': {
            'source': str(energy_path), 'sourceSha256': sha(energy_path),
            'olderQwenLowerEnergyQuartileDeletionRate': energy['lowerEnergyQuartile']['deletionRate'],
            'olderQwenOtherWordsDeletionRate': energy['remainingEnergyWords']['deletionRate'],
            'interpretation': 'RMS association supports investigating weak/remote speech. Room/background RMS is not target-speaker SNR or intelligibility; no causal attribution and no new gain/VAD/denoise experiment.',
        },
        'trainingBias': 'A language/domain imbalance is a hypothesis; there is no controlled evidence here to assign the observed gap to Chinese model origin or to require separately trained networks for every language.',
        'implementation': 'The previous fixed Parakeet audit verified published F32 roundtrip, PCM, frontend lengths and encoder exhaustion. Full-model independent backend equivalence is not thereby proven. Treat native reference quality separately from fast deployment backends.',
        'benchmarkProtocol': 'Current official Open-ASR submission scripts for MOSS and Parakeet select ami_cleaned. Historical model-card AMI figures, current cleaned leaderboard figures and our original raw far-field multi-turn recordings cannot be interchanged. The exact historical benchmark snapshot behind each old figure is not established by current scripts.',
    },
    'openSourceOptions': [
        {'name': 'Qwen3-ASR and MOSS-Transcribe-Diarize', 'kind': 'Pretrained recognition / joint transcription models',
         'sources': ['https://huggingface.co/Qwen/Qwen3-ASR-1.7B', 'https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize'],
         'licenseIdentifiers': ['Apache-2.0'],
         'capability': 'Qwen multilingual ASR; MOSS joint long-form transcription with recording-local anonymous speakers/timestamps.',
         'decision': 'Retain existing same-source evidence and Chinese baselines. Already tried here, so not a new discovery or permission to repeat their unchanged configurations. Multilingual support alone does not qualify natural code-switching.'},
        {'name': 'IBM Granite Speech4.1 2B AR', 'kind': 'One pending accuracy-first English final reference',
         'sources': ['https://huggingface.co/ibm-granite/granite-speech-4.1-2b', 'https://huggingface.co/ibm-granite/granite-speech-4.1-2b-nar'],
         'licenseIdentifiers': ['Apache-2.0'],
         'capability': 'Acoustically conditioned transcription, keyword biasing; official Transformers and llama.cpp examples.',
         'decision': 'Keep the one pinned AR candidate from the prior audit. The cited7.91/19.59 figures belong to its NAR sibling, not this AR candidate. Do not count those as our accuracy or our performance on AMD. No extra base roster, quantization, or custom engine port.'},
        {'name': 'FunASR', 'kind': 'Deployment and component toolkit',
         'sources': ['https://github.com/modelscope/FunASR', 'https://github.com/modelscope/FunASR/blob/main/docs/deployment_matrix.md'],
         'licenseIdentifiers': ['Toolkit MIT; pretrained checkpoints separately licensed'],
         'capability': 'File and streaming ASR, VAD, punctuation, speaker pipelines, CPU and ONNX/C++ deployment paths depending on the selected model.',
         'decision': 'Useful engineering reference. Switching toolkit is not evidence of lower WER, and offline/streaming checkpoints are not interchangeable. Preserve current authorized incremental/offline chain.'},
        {'name': 'WhisperX', 'kind': 'Transcription / alignment / speaker pipeline',
         'sources': ['https://github.com/m-bain/whisperX', 'https://github.com/m-bain/whisperX/blob/main/LICENSE'],
         'licenseIdentifiers': ['Toolkit BSD-2-Clause; components separately licensed'],
         'capability': 'faster-whisper transcription, word alignment and diarization. Documented CPU path; documented GPU acceleration uses CUDA.',
         'decision': 'Reference for integration, not a promised accuracy replacement. Upstream documents overlap and diarization limitations. Our rejected fullWhisper native profile is not a controlled WhisperX benchmark; do not generalize either way or assume AMD is CUDA-compatible.'},
        {'name': 'Nemotron3 Diarization / pyannote Community1', 'kind': 'Who-spoke-when components',
         'sources': ['https://huggingface.co/nvidia/Nemotron-3-Diarization', 'https://huggingface.co/pyannote/speaker-diarization-community-1'],
         'licenseIdentifiers': ['Nemotron3 OpenMDW-1.1', 'Community1 CC-BY-4.0 plus download access conditions'],
         'capability': 'Nemotron3 online/offline up to8speakers; Community1 mono16kHz offline diarization. These output speaker timing/anonymous identities, not separated audio tracks or intrinsically corrected words.',
         'decision': 'Retain the already-tested Nemotron component; no new diarizer grid. Community1 offline integration was already explored in this project and is a reference, not a fresh candidate. Do not accept upstream download account conditions for the owner.'},
    ],
    'researchOnly': [
        {'name': 'DM-ASR', 'source': 'https://arxiv.org/html/2604.22467v3',
         'idea': 'Use speaker-time conditions plus mixed acoustic context for structured multi-speaker decoding.',
         'reportedExample': {'decoderSizeB': 1.7, 'AMI_SDM_cpWER': 21.26, 'metric': 'speaker-attributed cpWER including complex conversational speech, not ordinary raw WER'},
         'limits': 'Inspected paper does not establish a complete permissively licensed local ready-to-run release. Paper training recipe uses8A6000 48GB GPUs and hundreds/thousands of hours, not evidence that our4hour recipe will reach5%.',
         'decision': 'Later overlap/structured-ASR architectural reference only; no implementation or training branch.'},
    ],
    'recommendedExecution': {
        'architecture': 'Original single-mic PCM feeds existing provisional incremental text, one accuracy-first offline final ASR, and existing speaker timeline. Align final words to anonymous speaker timing. File import uses the final path. Diarization does not first delete/crop audio merely to suppress unknown speakers.',
        'languagePolicy': 'Score Chinese CER, English WER and natural mixed-language separately; native reference metrics stay fixed. Choose a language-specific model only after same-source gains. Separate networks or training-from-scratch per language are not prerequisites.',
        'next': 'Complete only the already-pinned English accuracy reference feasibility/admission, then unchanged709word quality comparison and original complete-meeting/person/facts/final checks. No new training until this requested route research is reconciled; no additional model launches in this research batch.',
        'intermediateGate': {'maxErrors': 70, 'referenceWords': 709, 'eachMeetingNoRegression': True, 'saleQualified': False},
        'unchangedFinalTarget': {'perLanguageFloorErrorRate': 0.05, 'perLanguageTargetErrorRate': 0.02, 'wholeMeetingPersonFactsRequired': True},
        'furtherTraining': 'If a single base is substantially stronger, one meeting-domain adaptation with disjoint meetings/participants; then distillation/quantization after quality. Finish ordinary nonoverlap before overlap/separation.',
        'certainty': 'Off-the-shelf open components can implement the workflow. No reviewed source proves that this complete local product meets a universal5%far-field meeting word-error floor.',
    },
    'sourceSnapshots': [{'file': str(p), 'sha256': sha(p)} for p in sorted(source_dir.iterdir())],
    'originalEvidence': [{'file': str(p), 'sha256': sha(p)} for p in [gap_path, raw_path, energy_path, whole_path, J/'english-route-audit-20261117.json']],
    'newInferenceOrScoring': False, 'newNeuralCalls': 0, 'newTrainingUpdates': 0,
    'finalHoldoutOpened': False, 'qualityQualified': False, 'saleQualified': False,
}
dest = J / 'open-source-route-research-20261117.json'
assert not dest.exists(), 'Preserve completed survey'
dest.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

progress_path = Path('work/bilingual_progress.json')
x = read(progress_path)
j = x['jointArchitecture20261115']
pointer = {'file': str(dest), 'sha256': sha(dest), 'state': report['state'], 'at': at,
           'nextActionSource': 'jointArchitecture20261115.overnightExecution20261116.englishAccuracyReference20261117',
           'newModelCandidatesAdded': 0, 'newNeuralCalls': 0, 'newTrainingUpdates': 0,
           'qualityQualified': False, 'saleQualified': False}
j['weekDirectionReview20261117']['openSourceResearch20261117'] = pointer
j.setdefault('trainingGateBeforeOpenSourceResearch20261117', j['trainingGate'])
j['trainingGate'] = ('Current compute authority is ownerRuntimePolicy20261117: CPU/integratedGPU training allowed; temperature observation-only. '
                    'Current quality order follows overnightExecution20261116.englishAccuracyReference20261117. '
                    'Older noCPU-training text and old conditional candidates do not override that order or owner policy.')
j['nextExecutableGate'] = 'Follow overnightExecution20261116.englishAccuracyReference20261117; source survey in weekDirectionReview20261117.openSourceResearch20261117.'
j['candidate'].setdefault('previousStateBeforeResearch20261117', j['candidate']['state'])
j['candidate']['state'] = 'PRESERVED_OLD_CONDITIONAL_CANDIDATE_NOT_CURRENT_ACCURACY_REFERENCE'
j['candidate']['activeReferenceSource'] = pointer['nextActionSource']
x['state'] = 'OPEN_SOURCE_ROUTE_RESEARCH_COMPLETE_ONE_ENGLISH_REFERENCE_RETAINED'
x['ownerLatestOpenSourceResearchQuote20261117'] = report['ownerQuote']
marker = 'OPEN_SOURCE_RESEARCH_20261117'
assert marker not in x['logResult']
x['logResult'] += (
    f'\n\n{at}｜{marker}｜Owner要求先调研开源方案与中英差距，本轮未启动模型。'
    '核对官方Qwen/MOSS/Granite、FunASR/WhisperX与Nemotron/pyannote及DM-ASR论文。'
    '复用既有Qwen同字符诊断：中文73/1258=5.80%、英文328/2794=11.74%，原英文141/709词门未改；'
    '这是旧Qwen已暴露样本，不是Parakeet新成绩或同声学条件的语言因果实验。'
    '原低能量四分位漏词16.29%/其余8.10%只作既有RMS相关证据，不冒充SNR或重跑前端；'
    '另一场中文原Qwen1037/7153=14.50%，普通中文单场5.14%不代表普遍合格。'
    '官方Qwen英文朗读1.63%、Giga8.45%，Granite同NAR的IHM7.91/SDM19.59用于说明场景依赖；'
    'NAR数据不冒充所选AR候选。另查到当前官方OpenASR的MOSS/Parakeet提交脚本均选ami_cleaned，'
    '旧模型卡分数/当前榜单/我方原始远场轮流会议不得混排，也不能由当前脚本推定历史快照。'
    'FunASR MIT与WhisperX BSD2仅属工具代码，权重单独许可；WhisperX默认GPU路径CUDA，不视为AMD即装支持；'
    '人物日志输出时间/匿名ID不等于分出多路音频或修好词错。现有Nemotron组件保留，未新增人物/模型网格；'
    'DM-ASR仅论文参考，未核实完整可直接部署开源发行，不立新训练支线。'
    '执行仍仅原固定Granite英文AR参考，先普通非重叠、逐语独立原门、终稿词准后训练/压缩。'
    '同时保留顶层旧trainingGate和旧Qwen944候选状态，将活入口改指现行参考及OwnerCPU/核显允许/温度观察政策，避免旧禁令再导错续作。'
    f'0新神经/0更新/0评分/0最终集读取，调研收据{dest}。'
)
progress_path.write_text(json.dumps(x, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
files = [{'source': str(dest), 'name': 'open-source-route-research.json'},
         {'source': 'work/record_open_source_research_20261117.py', 'name': 'tools/record_open_source_research_20261117.py'}]
files += [{'source': str(p), 'name': 'sources/'+p.name} for p in sorted(source_dir.iterdir())]
config = {'revision': 73, 'evidenceDirectory': 'evidence/20261117-open-source-route-survey-and-language-gap',
          'sources': [], 'closedDirectories': [], 'files': files,
          'commitMessage': 'Survey official meeting-ASR routes and reconcile bilingual evidence without new model trials',
          'claims': {'state': x['state'], 'newNeuralCalls': 0, 'newTrainingUpdates': 0,
                     'newModelCandidatesAdded': 0, 'originalReferencesAndMetricsUnchanged': True,
                     'rawAudioInputFeaturesModelWeightsOrCredentialsIncluded': False,
                     'qualityQualified': False, 'saleQualified': False}}
Path('work/checkpoint_open_source_research_r73.json').write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'state': x['state'], 'report': str(dest),
                  'sameCharacterEnglishRateFromOldQwen': 328/2794,
                  'sameCharacterChineseRateFromOldQwen': 73/1258,
                  'newModelCandidatesAdded': 0, 'newNeuralCalls': 0}, ensure_ascii=False))
