"""Record the completed native input contract; keep training/quality unproven."""
from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
C=E/'language-specific-adaptation-r1/chinese-moss-contract-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
export=read(C/'export-r1/completed.json');native=read(C/'native-input-r1/completed.json')
assert export['examples']==5027 and export['all5027TargetTokenizationRoundtripsExact']
assert len(native['completed'])==2 and all(len(x['cases'])==4 for x in native['completed'])
assert native['modelInstances']==native['neuralCalls']==native['parameterUpdates']==0 and not native['gpuInitialized']
at=datetime.now().astimezone().isoformat(timespec='seconds')
report={'at':at,'state':'CHINESE_MOSS_5027_TARGETS_AND_ACTUAL_NATIVE_FRONTEND_LABELS_VERIFIED_NO_TRAINING',
    'officialTrainingGuide':'https://github.com/OpenMOSS/MOSS-Transcribe-Diarize/blob/main/FINETUNING.md',
    'officialTrainingSource':'https://github.com/OpenMOSS/MOSS-Transcribe-Diarize/blob/main/finetune.py',
    'sourceTrainingExamples':5027,'sourceAudioHours':6.00075,'sourceRawCharacters':export['sourceTextCharacters'],
    'conversationManifest':export['manifest'],'conversationManifestSha256':export['manifestSha256'],
    'conversationManifestBytes':export['manifestBytes'],'supervisedTargetTokensIncludingEos':export['supervisedTargetTokensIncludingEos'],
    'allOriginalRawTextAndExactFrameDurationsPreserved':True,'allOfficialDatasetRowsParsed':True,
    'allTokenizerRoundtripsAndTextPrefixBoundariesExact':True,
    'nativeFrontendReceipt':str(C/'native-input-r1/completed.json'),'nativeFrontendReceiptSha256':sha(C/'native-input-r1/completed.json'),
    'actualNativeFrontends':{'selectedOriginalTrainingClips':4,'paddingConventions':['left','right'],
        'originalSampleRange':[32000,267840],'answerTokenRangeIncludingEos':[18,83],
        'maximumLeftOrRightPaddingTokens':234,'expandedAudioPromptActuallyMeasured':True,
        'allPromptAudioPlaceholderAndPaddingLabelsMasked':True,'allTargetTokensAndExactlyOneEosSupervised':True,
        'sameInputFeatureSha256BothPaddingSides':native['completed'][0]['inputFeatureSha256']==native['completed'][1]['inputFeatureSha256']},
    'promptCompatibility':{
        'portableManifest':'Official three-message user/text, user/audio, assistant/text JSONL accepted by upstream dataset parser.',
        'nativeBatch':'Uses current native audio-only inference prompt, then unchanged target+EOS. The portable user prompt is not inserted into the native request.',
        'nativeAndPortablePromptInputsAreNotClaimedIdentical':True,
        'nativeTargetMask':'Actual expanded prefix plus raw target IDs is checked exactly; padding offset is obtained from attention mask, not assumed to start at column zero.'},
    'speakerScope':'S01 is anonymous and local to each isolated original utterance; source global ID remains provenance only. Not continuous speaker-identity or overlap training.',
    'resources':{'cpuPercent':5,'metadataPrivatePeakBytes':export['limits']['jobPeakPrivateCommitBytes'],
        'signalPrivatePeakBytes':native['limits']['jobPeakPrivateCommitBytes'],
        'metadataSeconds':export['elapsedSeconds'],'signalSeconds':native['elapsedSeconds'],
        'privateCommitCapBytes':2147483648,'modelInstances':0,'optimizerInstances':0,
        'newNeuralCalls':0,'parameterUpdates':0,'gpuInitialized':False,'cpuOrIntegratedGpuTraining':False},
    'remaining':['Actual nativeGPU training forward/backward/loss/gradient/memory/checkpoint proof and fixed training recipe.',
        'Original AISHELL cross-corpus person isolation is unproven; no original evaluation or final gate is changed.',
        'Independent Chinese/English whole meetings, per-person text, facts and original final qualification.'],
    'trainingAdmitted':False,'newWerCerOrDerMeasured':False,'qualityQualified':False,'saleQualified':False,
    'originalReferencesAudioAndResourceOrQualityGatesChanged':False,'productDefaultChanged':False,
    'exportReceipt':str(C/'export-r1/completed.json'),'exportReceiptSha256':sha(C/'export-r1/completed.json')}
target=J/'language-specific-adaptation-r1/chinese-native-input-contract-20261117.json'
target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');x=read(p);o=x['jointArchitecture20261115']['overnightExecution20261116']
o['chineseMossNativeInputContract20261117']={'state':report['state'],'receipt':str(target),
    'conversationManifest':export['manifest'],'conversationManifestSha256':export['manifestSha256'],
    'nativeFrontendReceipt':report['nativeFrontendReceipt'],'trainingAdmitted':False,
    'actualModelForwardBackwardProven':False,'newAccuracyMeasured':False}
o['ownerTimeValueReview20261117']['remaining'][1]='Chinese target serialization and actual native CPU signal/expanded-audio/target-only-label contract passed; actual GPU trainability and original AISHELL cross-corpus person qualification remain unresolved.'
o['currentWorkerState']='NO_OWNED_NEURAL_DATA_OR_TEMPERATURE_WORKER';x['at']=at
x['next']='中英训练输入与执行器的必要准备在此收口。中文5027原句已转官方MOSS对话目标，原字/精确帧时长/分词往返全过，四个实际原音×左右padding的原生信号/音频占位展开/目标专用labels已过；0模型0优化器0更新，非连续说话人/重叠训练，原AISHELL跨库人物资格未证。保存r68后，下一关键动作仍是独显恢复及原准入通过后的英文固定1828片457更新适配与独立验收；不扩库、重复审查/轮询或CPU/核显训练，不把输入合格当95/98达标。'
x['logResult']+='\n\n'+at+'｜补齐中文模型专用输入这一可独立执行的原缺口：按OpenMOSS官方FINETUNING/finetune.py的固定源blob核对，5027句6.00075h已导出合法三消息会话目标[0.00][S01]原文[精确帧时长]，原文121579字符不删改、相对时间用Decimal(frames)/16000不四舍五入，匿名S01仅限本单句，原全局人ID仅来源；159825答案token含EOS，全部官方Dataset._parse接收、分词解码原字相同、prefix/answer文本BPE边界相同。新增目标专用batch helper保留现有native音频单输入提示，实际音频展开后的prefix另测且全序列=prefix+原目标/EOS，按attention确定左右padding位置而非假定列0，提示/音频token/pad均-100。实际最短答案/最长答案/最长音频/首固定片4条×左右2方式均过，原32000–267840样本全送入公开处理器，两边音频特征SHA一致；答案18–83token含一个EOS、最大padding234token均正确。官方可移植JSONL提示与现有native音频单输入提示不声称相同，native helper有意沿现有推理提示，不把官方辅助prompt重复塞进native请求。CPU5%，元数据峰160915456B/41.875s；真实CPU信号及标签峰900685824B/41.687s<原2GiB，进程内原ROCm BLAS16→1复用既有固定DLL，无GPU初始化/模型/优化器/神经前反向/权重更新，不是CPU训练。原音不复制/不改，新增本机含原字JSONL11264835B不入Git。此为格式与预处理可用变化，不是新CER/WER/DER；真实GPU训练及原AISHELL跨库人物隔离、逐人/事实/最终门开放。收据'+str(target)+'。'
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
files=[]
def take(p,name):
    p=Path(p);assert p.is_file() and p.suffix not in ('.jsonl','.wav','.TextGrid')
    files.append({'source':str(p),'name':name})
for n in ['verify_chinese_moss_native_inputs_20261117.py','record_chinese_moss_input_contract_20261117.py','verify_tdt_supervisor_lifecycle_20261117.py']:
    take(Path('work')/n,'tools/'+n)
take(target,'chinese/contract-summary.json')
for n in ['export-r1/completed.json','native-input-r1/completed.json']:
    take(C/n,'chinese/'+n)
for p in (C/'upstream').iterdir():
    if p.is_file():take(p,'chinese/upstream/'+p.name)
L=E/'language-specific-adaptation-r1'
for name in ['supervisor-lifecycle-before-r1','supervisor-lifecycle-existing-guard-r2','supervisor-lifecycle-existing-guard-r3']:
    b=L/name
    for p in b.rglob('*'):
        if p.is_file():take(p,'supervisor/'+name+'/'+p.relative_to(b).as_posix())
config={'revision':68,'evidenceDirectory':'evidence/20261117-chinese-moss-target-native-inputs-and-existing-supervisor-guard',
    'sources':['src/prepare_chinese_moss_inputs_20261117.py','src/moss_target_only_batch_20261117.py'],
    'closedDirectories':[],'files':files,
    'commitMessage':'Prepare source-bound Chinese MOSS targets and verify actual native signal and masked labels',
    'claims':{'state':report['state'],'examples':5027,'actualNativeSignalClips':4,'paddingConventions':2,
        'trainingAdmitted':False,'newNeuralCalls':0,'parameterUpdates':0,'cpuOrIntegratedGpuTraining':False,
        'rawTrainingTextAudioWeightsOrCredentialsIncluded':False,'newQualityResultMeasured':False,
        'originalEvaluationOrResourceGatesChanged':False,'qualityQualified':False,'saleQualified':False}}
Path('work/checkpoint_chinese_native_inputs_r68.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'receipt':str(target),'selectedProtectionFiles':len(files),'examples':5027,'nativeSignalCases':8,'newNeuralCalls':0},ensure_ascii=False))
