from pathlib import Path
from datetime import datetime
import hashlib,json,wave
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
BASE=D/'joint-architecture-r1';C=BASE/'cpu-fixed-whole-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/cpu-fixed-whole-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not C.exists() and not E.exists();C.mkdir()
old=BASE/'stagea-cpu-composition-r2';previous=read(old/'binding.json');result=read(old/'score.json')
for row in result['groups']:
 if row['role']=='validation':assert row['rawErrors']<row['baselineRawErrors'] and row['speakerAttributedErrors']<row['baselineSpeakerAttributedErrors']
original=read(BASE/'overnight-r5/whole-scoring-only.json');meetings=[{k:r[k] for k in ['meeting','audio','audioSha256','audioSeconds','frames','language']} for r in original['cases']]
assert len(meetings)==4 and all('L_R003S03C02' not in r['meeting'] for r in meetings)
cases=[]
for source in meetings:
 assert sha(source['audio'])==source['audioSha256']
 with wave.open(source['audio'],'rb') as wav:assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())==(1,2,16000,source['frames'])
 for i,first in enumerate(range(0,source['frames'],480000)):
  last=min(first+480000,source['frames'])
  cases.append({'id':source['meeting']+'-fixed30-'+str(i).zfill(4),'meeting':source['meeting'],'audio':source['audio'],'audioSha256':source['audioSha256'],
   'sourceStartFrame':first,'sourceEndFrame':last,'frames':last-first,'audioSeconds':(last-first)/16000})
B={k:previous[k] for k in ['workerPython','cppControl','neuralDeadline','reportDeadline','ownerCpuBudgetPermission','cpuPercent','computeThreads','privateBytes']}
B.update(at=datetime.now().astimezone().isoformat(),workerSha256=sha(S/'cpu_fixed_chunks_worker_20261116.py'),runnerSha256=sha(S/'run_cpu_fixed_chunks_20261116.py'),
 meetings=meetings,cases=cases,helpers={str(S/n):sha(S/n) for n in ['moss_windows_resource_limits_20261104.py','practical_io_20261107.py','cpu_window_joint_worker_20261116.py']},
 scope='The same4 original complete development recordings; every original16k mono PCM frame exactly once in fixed30s nonoverlap windows, final short tail retained. No annotation-assisted boundary or VAD omission.',
 outputPolicy='No automatic retries, repetition cleanup, filler deletion or numerical rewriting. Incomplete EOS packets are preserved and counted; continue other original windows, never silently discard failed windows.',
 compositionFrozenBeforeOutputs=previous['compositionFrozenBeforeOutputs'],fullSequenceSpeakerIdentityResetsForbidden=True,
 originalContinuousContextModelExperimentRetained6501Tokens=True,newTraining=False,qualityQualified=False,wholeMeetingAcceptance=False,productDefaultChanged=False)
(C/'binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(C/'scoring-binding.json').write_text(json.dumps({'sourceControl':str(BASE/'overnight-r5'),'sourceManifestSha256':sha(BASE/'overnight-r5/whole-scoring-only.json'),
 'originalScorerSha256':sha(S/'score_joint_whole_meetings_20261115.py'),'selectionBasedOnStageAValidation':str(old/'score.json'),'selectionResultSha256':sha(old/'score.json'),
 'referencesPassedToInference':False,'originalGatesChanged':False,'wholeInputs':4,'wholeAudioSeconds':sum(r['audioSeconds'] for r in meetings),'chunks':len(cases),
 'attributionPolicy':B['compositionFrozenBeforeOutputs']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=Path('work/bilingual_progress.json');d=read(p);o=d['ownerOvernightRun20261115'];d['state']='DAY_CPU_FIXED_FULL4_FROZEN_READY'
o.update(currentState=d['state'],currentCpuWholeControl=str(C),currentCpuWholeRun=str(E),activePid=None,noOwnNeuralProcessActive=True)
d['logResult']+='\n'+B['at']+' 32条固定验证两语raw/带人均降低后，同一CPU原生组合推进完整原4录音：共'+str(len(cases))+'段，30s时间固定连续不重叠，最后不足30s原样保留；每个原PCM样本恰好一次，不读标签/VAD/说话人数决定切分。继承25%/4线程、2GiB私有/低RAM停止；未自然EOS结果保留且不重试/不漏计，继续其余原输入。原整会长上下文模型6501前缀与缓存保留，非把短窗质量冒充原整会模型完成。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'control':str(C),'run':str(E),'wholeMeetings':4,'windows':len(cases),'audioSeconds':sum(r['audioSeconds'] for r in meetings)},ensure_ascii=False))
