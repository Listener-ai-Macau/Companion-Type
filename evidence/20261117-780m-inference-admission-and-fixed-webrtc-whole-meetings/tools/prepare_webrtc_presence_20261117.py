"""Freeze the sole non-neural presence comparator before viewing its outputs."""
from pathlib import Path
from datetime import datetime,timedelta
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
C=J/'context-activity-r1/webrtc-presence-r1';run=E/'context-activity-r1/webrtc-presence-r1/run-mode0'
assert not C.exists() and not run.exists();C.mkdir()
old=read(J/'context-activity-r1/silero-presence-day-r2/protocol.json')
asset=Path('E:/CodexData/Companion/.model-cache/webrtcvad-wheels-20261117/asset-receipt.json')
files=[S/n for n in ['webrtc_presence_worker_20261117.py','compose_vad_presence_20261117.py',
    'fixed_presence_identity_core_20261117.py','moss_windows_resource_limits_20261104.py',
    'durable_model_state_20261117.py','meeting_acoustic_contract_20261116.py']]
files += [asset,Path(old['audioOnly']),Path(old['predictedBindings'])]
at=datetime.now().astimezone()
P={'state':'FROZEN_ONE_WEBRTC_DSP_MODE0_NO_NEURAL_COMPUTATION','at':at.isoformat(),
    'assetReceipt':str(asset),'sampleRate':16000,'frameSamples':160,'mode':0,
    'audioOnly':old['audioOnly'],'predictedBindings':old['predictedBindings'],'meetings':old['meetings'],
    'files':[{'file':str(p),'sha256':sha(p)} for p in files],
    'minimumAvailableBytes':3414499000,'cpuPercent':5,'privateCommitBytes':256*1024**2,
    'stopAt':(at+timedelta(minutes=15)).isoformat(),'extraPaddingOrSmoothing':False,
    'decisionBasis':'Native8 misses speech. One very small non-neural published DSP VAD provides a distinct CPU-only presence option after neural admission stopped. Same two complete original English recordings/unchanged Native8 identity fusion/zero-collar overlap-included scoring. Not another acoustic model or threshold grid.',
    'admissionGate':old['admissionGate'],'qualityQualified':False,'parameterUpdates':0,
    'newNeuralCalls':0,'fallbackChangesProductDefault':False,
    'referencesPassedToWorker':False,'originalWordsAndAcceptanceMetricsChanged':False}
(C/'protocol.json').write_text(json.dumps(P,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
score=read(J/'context-activity-r1/silero-presence-day-r2/scoring-control.json')
score['predictionProtocol']=str(C/'protocol.json');score['files'][0]={'file':str(C/'protocol.json'),'sha256':sha(C/'protocol.json')}
(C/'scoring-control.json').write_text(json.dumps(score,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'control':str(C),'run':str(run),'sourceCount':2,'newNeuralCalls':0}))
