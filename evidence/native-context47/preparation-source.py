"""Freeze one already-local native context recipe; no new model or audio."""
from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1';C=J/'native-context180-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
item=lambda p:{'file':str(p),'sha256':sha(p)}
C.mkdir(exist_ok=False)
worker=S/'moss_native_context180_worker_20261116.py'
tree=ast.parse(worker.read_text(encoding='utf-8'))
assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ['train','backward','step'] for n in ast.walk(tree))
old=read(J/'night-acoustic-pilot-r1/packet.json');assets=read(J/'preparation.json');proof=read(J/'tensor-reuse-proof.json')
pilot=read(J/'pilot-audio-only.json')[0];previous=E/'native-runtime-r1'/(pilot['meeting']+'-raw.json')
raw=read(previous);assert raw['naturalEos'] and raw['audioSha256']==pilot['audioSha256']
audio=J/'full-audio-only.json'
files=[worker,audio,J/'preparation.json',J/'tensor-reuse-proof.json',previous]
files += [Path(k) for k in read(J/'pilot-binding.json')['helpers']]
files += [S/n for n in ['meeting_acoustic_contract_20261116.py','meeting_acoustic_worker_20261116.py',
    'companion_local_pcm_session_20261114.py','companion_windows_power_request_20261115.py']]
files += [Path(k['file']) for k in assets['files']]
P={'state':'FROZEN_NATIVE_PRETRAINED_CONTEXT180_COMPLETE_SOURCE_COMPARISON',
   'at':datetime.now().astimezone().isoformat(timespec='seconds'),
   'runtime':old['runtime'],'blas':old['blas'],'modelRoot':assets['nativeModelRoot'],
   'nativeControl':str(J),'nativeCheckpointSha256':proof['nativeCheckpointSha256'],
   'authorCheckpointSha256':proof['authorCheckpointSha256'],
   'audioOnly':str(audio),'control':{k:pilot[k] for k in ['meeting','audio','audioSha256','frames']},
   'expectedControlIds':raw['generatedIds'],'contextFrames':2880000,'maxNewTokens':4096,
   'files':[item(p) for p in dict.fromkeys(files)],'trainingUpdates':0,
   'minimumAvailableBytes':old['resources']['minimumAvailableBytes'],
   'neuralLock':'E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock',
   'latestDecodeStart':'2026-11-17T07:10:00+08:00','stopAt':'2026-11-17T07:25:00+08:00',
   'maximumDecodeSeconds':900,
   'initialSources':['ES2003b','S_R004S03C01'],
   'extensionSources':['EN2002a','20200623_S_R001S07C01'],
   'selectionBasis':'Old fixed30s CPU port regressed Chinese; full native35minute input failed in compiler/prefill allocation, not a quality result. Published exact BF16 tensors already completed two180s GPU controls. This recipe changes deployment/context, not weights. It is not a pure context-only or precision-only ablation.',
   'stopRules':'Exact retained native180s token control must pass. Any EOS/resource failure stops without changed-window retries. Score complete initial EN/ZH sources before extending; retain originalChinese baseline if regressed. No promotion from a shorter prefix or local block speaker IDs.',
   'wholeMeetingAnonymousIdentityQualified':False,'qualityQualified':False,'saleQualified':False}
(C/'protocol.json').write_text(json.dumps(P,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
scoring={'wholeReferences':str(J/'cpu-fixed-whole-r2/whole-scoring-only.json'),
    'protocol':str(C/'protocol.json'),'files':[item(p) for p in [C/'protocol.json',J/'cpu-fixed-whole-r2/whole-scoring-only.json',
      S/'score_joint_whole_meetings_20261115.py',S/'score_ami_bilingual_20261115.py',S/'reference_textgrid_20261104.py']]}
(C/'scoring-control.json').write_text(json.dumps(scoring,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'protocol':str(C/'protocol.json'),'initialSources':P['initialSources'],'trainingUpdates':0},ensure_ascii=False))
