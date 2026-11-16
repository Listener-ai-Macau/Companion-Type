"""Prepare the13-decode native inference diagnostic and independent scoring."""
from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion'); S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1/microphone-diagnostic-r1'
C=D/'sequential-meeting-stageA-r2'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/microphone-diagnostic-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def item(p):return {'file':str(p),'sha256':sha(p)}
pairing=read(J/'pairing.json'); old=read(D/'joint-architecture-r1/night-acoustic-pilot-r1/packet.json')
assert pairing['inspection']['pairs']==12 and pairing['inspection']['sources']==2
assert pairing['inspection']['largestAbsoluteEnvelopeLagMs']<=100,'Investigate source timebase before inference'
timebase=read(J/'timebase-review.json')
assert timebase['allPairsPass'] and timebase['pairingSha256']==sha(J/'pairing.json')
assert len(timebase['rows'])==12 and all(r['withinOriginal100MsTimingBound'] for r in timebase['rows'])
assert not any(r['audioOrReferenceShiftApplied'] for r in timebase['rows'])
# The original amplitude check failed and is preserved. Official shared-clock
# acquisition and independent raw-PCM peak lags establish gross timebase
# consistency; do not lower a correlation threshold or modify source audio.
assert not (J/'inference-protocol.json').exists()
control=pairing['control']; first=next(r for r in pairing['pairs'] if r['id']==control['caseId'])
audio=[{'id':'native-distant-control','caseId':first['id'],'kind':'native-distant-control',
        'audio':control['audio'],'audioSha256':control['audioSha256'],'frames':first['frames']}]
for pair in pairing['pairs']:
    audio.append({'id':pair['id']+'-headset-mix','caseId':pair['id'],'kind':'official-headset-mix',
                  'audio':pair['headsetMix']['audio'],'audioSha256':pair['headsetMix']['audioSha256'],
                  'frames':pair['frames']})
audio_file=J/'inference-audio-only.json'
audio_file.write_text(json.dumps(audio,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
worker=S/'native_microphone_diagnostic_20261116.py'; scorer=S/'score_microphone_diagnostic_20261116.py'
tree=ast.parse(worker.read_text(encoding='utf-8'))
assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
               and n.func.attr in ['backward','step','train'] for n in ast.walk(tree)), 'Inference-only worker acquired a training call'
ast.parse(scorer.read_text(encoding='utf-8'))
bindings=[worker,audio_file,J/'pairing.json',J/'timebase-review.json']
bindings += [Path(p['file']) for p in old['files'] if p['file'].endswith((
    'meeting_acoustic_contract_20261116.py','meeting_acoustic_worker_20261116.py',
    'moss_windows_resource_limits_20261104.py','practical_io_20261107.py',
    'practical_qwen_streamed_loader_20261107.py','moss_streamed_weights_20261104.py',
    'companion_community1_adapter_20261115.py','companion_local_pcm_session_20261114.py',
    'config.json','tokenizer.json','tokenizer_config.json','chat_template.jinja',
    'modeling_qwen3_asr.py','processing_qwen3_asr.py','feature_extraction_qwen3_asr.py',
    'processor-numeric-proof.json','streamed-loader-proof-r2.json'))]
protocol={'state':'FROZEN_PRETRAINED_INFERENCE_ONLY_MICROPHONE_CAUSE_DIAGNOSTIC',
    'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'modelRoot':old['modelRoot'],'modelSha256':old['modelSha256'],
    'runtime':old['runtime'],'blas':old['blas'],'minimumAvailableBytes':old['resources']['minimumAvailableBytes'],
    'audioOnly':str(audio_file),'expectedControlIds':control['expectedGeneratedIds'],
    'timebaseReview':str(J/'timebase-review.json'),'timebaseWithinOriginal100MsBound':True,
    'files':[item(p) for p in dict.fromkeys(bindings)],
    'trainingUpdates':0,'freshRunMaximumNewGpuDecodes':13,
    'noDenoiseGainResamplingOrVADChange':True,'noReferenceWordsPassedToInference':True,
    'scope':'Diagnostic only: same12 exposed original-English intervals, official source recorded views. Headset-mix scores never count as product mono-mic acceptance.',
    'nightPriority':'Unchanged-native control then12 headset inferences and original-reference comparison. Do not run the preserved broad training batch before interpreting this result.',
    'gpuRun':str(E/'gpu-run'),'qualityQualified':False,'saleQualified':False}
protocol_file=J/'inference-protocol.json'
protocol_file.write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
scoring={'protocol':str(protocol_file),'worker':str(worker),
         'references':str(C/'scoring-only.json'),'baseline':str(C/'raw-text-baseline.json'),
         'files':[item(p) for p in [protocol_file,scorer,worker,audio_file,C/'scoring-only.json',
                                   C/'raw-text-baseline.json',S/'score_sequential_meetings_20261115.py']],
         'noChangeToOriginalReferencesOrScoring':True,'productQualificationAllowed':False}
(J/'scoring-control.json').write_text(json.dumps(scoring,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['Companion：先判方向，暂不以训练为默认下一步',
       '目标98%，底线95%，最终仍按原单麦产品范围验收。',
       '当前只准备一项控制变量诊断：同一12条无重叠英文会议片段，远场原输入与官方头戴混音，使用同一个未改权重的原生Qwen。',
       '官方头戴混音只用于判断声学条件影响，不能作为单麦产品更好成绩。',
       '白天已完成：709词原音能量关联检查，12对输入的原时轴/样本数/波形来源检查；无新模型推理。',
       '夜间：先1条原远场控制，生成token必须与原结果完全一致；随后12条头戴输入推理，交独立评分器比较141/709原远场错误。总计最多13次新解码，无参数更新。',
       '若近讲明显更好：优先定位远场/实际收音、声学鲁棒性或前处理；不直接认定硬件损坏。',
       '若近讲也差：优先复核基础识别能力/口语转录任务与推理条件，再决定一个成熟现成组件对照。',
       '若文字够准而人物差：修活动漏检、连续身份和时间对齐。每种结果都仍可能有多种成因。',
       '原r45声学训练入口与证据保留为有条件备选；不因接入GPU自动运行训练，不跑CPU或核显训练，不启动模型网格。',
       '当前实际GPU执行、13条新输出和新WER都不存在；不能称方向已由该对照证实。',
       '',
       'GPU推理入口：',old['runtime']['python']+' '+str(worker)+' --protocol '+str(protocol_file)+' --execute --run '+str(E/'gpu-run'),
       '独立评分入口：',old['scoringPython']+' '+str(scorer)+' --control '+str(J/'scoring-control.json')+' --run '+str(E/'gpu-run')+' --output '+str(J/'diagnostic-score.json')]
(J/'说明.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'protocol':str(protocol_file),'inputs':len(audio),'pairingInspection':pairing['inspection'],
                  'newNeuralCalls':0,'trainingUpdates':0},ensure_ascii=False))
