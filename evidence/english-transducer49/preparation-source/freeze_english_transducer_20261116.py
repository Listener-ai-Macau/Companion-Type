"""One nativeF32 English role, admitted only after current comparisons."""
from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';J=D/'joint-architecture-r1'
C=J/'english-transducer-r1';read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
item=lambda p:{'file':str(p),'sha256':sha(p)}
asset=read(C/'asset-receipt.json');old=read(J/'microphone-diagnostic-r1/inference-protocol.json')
require_state='ONE_OFFICIAL_ENGLISH_TRANSDUCER_ASSETS_READY_NO_INFERENCE';assert asset['state']==require_state
root=Path(asset['nativeModelRoot']);weights=next(r for r in asset['completed'] if Path(r['file']).name=='model.safetensors')
rows=[r for r in read(D/'sequential-meeting-stageA-r2/scoring-only.json') if r['role']=='validation' and r['language']=='English']
audio=[{'id':r['id'],'audio':r['wav'],'audioSha256':r['wavSha256'],'frames':r['frames']} for r in rows]
assert len(audio)==12
audio_path=C/'audio-only.json';assert not audio_path.exists()
audio_path.write_text(json.dumps(audio,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
worker=S/'english_transducer_worker_20261116.py';scorer=S/'score_english_transducer_20261116.py'
for p in [worker,scorer]:
    tree=ast.parse(p.read_text(encoding='utf-8'))
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ['train','backward','step'] for n in ast.walk(tree))
files=[worker,audio_path,C/'asset-receipt.json']+[Path(x['file']) for x in asset['completed'] if Path(x['file']).suffix=='.json']
files += [S/n for n in ['meeting_acoustic_contract_20261116.py','meeting_acoustic_worker_20261116.py',
    'moss_windows_resource_limits_20261104.py','moss_streamed_weights_20261104.py','practical_io_20261107.py',
    'companion_community1_adapter_20261115.py','companion_local_pcm_session_20261114.py','companion_windows_power_request_20261115.py']]
runtime=Path(old['runtime']['python']).parent.parent/'Lib/site-packages/transformers/models/parakeet'
files += list(runtime.glob('*.py'))
P={'state':'FROZEN_ONE_NATIVE_F32_ENGLISH_TRANSDUCER_ROLE_NO_INFERENCE',
    'at':datetime.now().astimezone().isoformat(timespec='seconds'),'modelRoot':str(root),'weights':weights,
    'audioOnly':str(audio_path),'runtime':old['runtime'],'blas':old['blas'],
    'files':[item(p) for p in dict.fromkeys(files)],'trainingUpdates':0,
    'minimumAvailableBytes':old['minimumAvailableBytes'],
    'neuralLock':'E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock',
    'stopAt':'2026-11-17T07:25:00+08:00',
    'nativeRecipe':'Published float32 tensors and generation config, greedy TDT decoding with repeated lexical tokens retained, defaultCPU frontend and GPU neural model; eager attention and no torch.compile for bounded AMD compatibility. No external LM, prompt, normalization sweep or dtype conversion.',
    'executionAdmission':'After interpreting the active native-context180 whole-source and FRCRN+unchangedASR24clip comparisons. Not automatically launched by this preparation.',
    'scope':'Same12 exposed original English nonoverlap cases; not a blind cohort or a bilingual routing/whole-meeting acceptance result.',
    'qualityQualified':False,'saleQualified':False}
protocol=C/'protocol.json';assert not protocol.exists()
protocol.write_text(json.dumps(P,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
scoring={'protocol':str(protocol),'references':str(D/'sequential-meeting-stageA-r2/scoring-only.json'),
    'qwenBaseline':str(D/'sequential-meeting-stageA-r2/raw-text-baseline.json'),
    'mossBaseline':str(J/'stagea-cpu-composition-r2/score.json'),
    'admissionGate':{'maximumEnglishErrors':99,'referenceWords':709,'minimumRelativeErrorReductionVsPriorMoss124':.2,
        'eachMeetingAtMostPriorMossErrors':True,'actionIfPass':'Complete-source validation, not default promotion',
        'actionIfFail':'Retain and retire without a temperature/beam/model/dtype grid'},
    'files':[item(p) for p in [protocol,worker,scorer,D/'sequential-meeting-stageA-r2/scoring-only.json',
        D/'sequential-meeting-stageA-r2/raw-text-baseline.json',J/'stagea-cpu-composition-r2/score.json',
        S/'score_sequential_meetings_20261115.py']]}
(C/'scoring-control.json').write_text(json.dumps(scoring,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':P['state'],'cases':12,'dtypeConversion':False,'newNeuralCalls':0},ensure_ascii=False))
