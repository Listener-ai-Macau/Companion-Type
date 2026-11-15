from pathlib import Path
from datetime import datetime
import hashlib,json,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
OLD=D/'public-speaker-adaptation-r1';T=D/'supervised-blind-separation-r1';C=T/'single-source-activity-guard-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/supervised-blind-separation-r1/single-source-activity-guard-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not C.exists();C.mkdir()
audio=[r for r in read(OLD/'audio-only.json') if r['role']=='validation'];assert len(audio)==2
write(C/'audio-only.json',audio)
bindings={}
for case in audio:
    folder=Path(read(OLD/'protocol.json')['baselineRun'])/'results'/case['meeting']
    meta=read(folder/'result.json');assert meta['audioSha256']==case['audioSha256']
    bindings[case['meeting']]=dict(file=str(folder/'probabilities.npy'),sha256=meta['probabilitySha256'])
write(C/'baseline-bindings.json',bindings)
P=read(OLD/'protocol.json');P.update(state='FROZEN_ORIGINAL_ACTIVITY_HEAD_SINGLE_SOURCE_PROTECTION_BEFORE_OUTPUTS',
    at=datetime.now().astimezone().isoformat(),audioOnlySha256=sha(C/'audio-only.json'),
    observationRun=str(E/'observation-r1'),newTraining=False,
    previousDecision=str(T/'continuous-overlap-composition-r1/routed-decision.json'),
    decisionEvidence='Previous same weights with precise originalNemo routing improve12natural context161to134 but20solo13to19. Four model-predicted overlap short replies cause6additional errors. Do not fit any new threshold/duration to those answers. Original frozen3class activity head exists but was not used in route.',
    candidateRule='Fixed original pretrained auxiliary head categories0silence/1single/2overlap, categorical argmax of unchanged original logits. Route separation only where original8speaker activities (original .5 ties unchanged) predict>=2 AND auxiliary argmax==2. Else retain original microphone. No duration, smoothing, temperature, confidence threshold, new weights or model variants.',
    primarySource='https://arxiv.org/html/2611.12246v1#S2.SS3',
    primarySourceBoundary='The paper establishes the training objective and pretrained head semantics, not that this inference gate improves accuracy. Treat this gate as one explicit experiment, never an upstream official pipeline claim.',
    numericalControl='Both complete72min existing source-held validation speaker posteriors must be bit-exact to previously protected original probabilities. All four restored original head tensors must equal checkpoint values. No labels/text/speaker count in forward.',
    sourceScoring='After inference independently report framewise 0/1/2confusion and overlap precision/recall/F1 on entire two meetings. Reference segment activity can overcount intra-turn silence; do not change gold, and do not claim independent pretraining qualification.',
    wordKeepRule='Same original32 full-used-word diagnostic: multi total<161, neither source worse than48/113, solo total<=13 and neither solo source worse than0/13, all outputs confirmed. Compare current134/19 separately; no checkpoint or rule selection from answers. Final full bilingual/person gates unchanged.',
    stop='One pretrained auxiliary-count agreement rule only. Reuse unchanged input/ASR outputs by SHA and digital-zero bypass. If original words/solo gates fail, retain failure, no threshold/duration/model variants. Advance independent speaker association work.',
    ownerParticipationRequired=False,qualityQualified=False,d2Complete=False,finalHoldoutOpened=False)
write(C/'protocol.json',P)
runner=S/'run_single_source_activity_guard_20261115.py'
text=(S/'run_public_nemotron_training_20261115.py').read_text(encoding='utf-8')
assert 'public_nemotron_training_worker_20261115.py' in text
text=text.replace('public_nemotron_training_worker_20261115.py','single_source_activity_guard_worker_20261115.py')
assert not runner.exists();compile(text,str(runner),'exec');runner.write_text(text,encoding='utf-8')
helpers=['public_nemotron_adaptation_20261115.py','public_nemotron_supervision_20261115.py',
    'moss_windows_resource_limits_20261104.py','companion_community1_adapter_20261115.py','companion_local_pcm_session_20261114.py']
binding={str(S/n):sha(S/n) for n in helpers};binding[str(C/'baseline-bindings.json')]=sha(C/'baseline-bindings.json')
write(C/'worker-binding.json',dict(workerSha256=sha(S/'single_source_activity_guard_worker_20261115.py'),
    runnerSha256=sha(runner),protocolSha256=sha(C/'protocol.json'),helpers=binding))
p=Path('work/bilingual_progress.json');v=read(p);e=v['d1d2Execution20261115'];e.update(singleSourceActivityGuard=str(C),singleSourceActivityGuardStatus=P['state'])
v['latestOwnerContinuation20261115']='看着比以前好很多了，那就继续呗。你看啊，再继续推进一下。然后的话，目前来看。还有多久可以搞完这个事情？医疗现在整体的进展是怎么样？现在我们走在这个正确的方向上面吗？'
v['next']='按固定原模型activity头验证单人保护：原8人概率完整两会议逐帧全等控制，补原三分类头并保留真实cache；原.5活动>=2且原预训练单/重叠头argmax2才分离，无新阈值/新模型/训练。独立整会活动诊断后仅转输入真正改变的路，按原32复杂/单人门验收；失败不盲调，继续人物绑定。'
v['logResult']+=' '+P['at']+' Owner继续推进并问整体方向/工期，沿原待办单人保护/人物绑定，不恢复清除Goal、不另建目标。复核R20基线多轮161→134、单人13→19/87尚未合格；完整人物/中英/独立会议仍开放。2–5工作日仅完整候选工程计划，非售卖日期。新证据为原checkpoint已有并逐张量恢复的3类activity头，作者论文明确训练静音/单人/重叠，当前路由未用；冻结唯一双头一致路由，先全2val原说话人后验逐帧全等控制，无新训练/模型/阈值，作者未声称该推理组合有效，实际词门决定。'
write(p,v);print(json.dumps(dict(control=str(C),run=str(E/'observation-r1'),rule=P['candidateRule']),ensure_ascii=False))
