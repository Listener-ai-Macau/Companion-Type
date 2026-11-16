"""Freeze a single official frontend setting and the unchanged ASR recipe."""
from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json
import zipfile

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1';C=J/'frcrn-front-end-r1'
E=Path('E:/CodexData/Companion/.model-cache/frcrn-se16k-official20261116')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
item=lambda p:{'file':str(p),'sha256':sha(p)}
asset=read(C/'asset-receipt.json');assert asset['newNeuralCalls']==0 and sha(asset['file'])==asset['sha256']
assert zipfile.is_zipfile(asset['file']),'Inspect legacy checkpoint format before model loading'
author=ast.parse((E/'upstream/official_functions.py').read_text(encoding='utf-8'))
for filename,name in [('decoder-upstream.py','decode_one_audio_frcrn_se_16k'),('dataloader-upstream.py','audio_norm')]:
    old=ast.parse((E/'upstream'/filename).read_text(encoding='utf-8'))
    left=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name)
    right=next(n for n in author.body if isinstance(n,ast.FunctionDef) and n.name==name)
    assert ast.dump(left)==ast.dump(right),'Numerical upstream function changed'
worker=S/'frontend_component_compare_20261116.py'
tree=ast.parse(worker.read_text(encoding='utf-8'))
assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ['train','backward','step'] for n in ast.walk(tree))
rows=[r for r in read(D/'sequential-meeting-stageA-r2/scoring-only.json') if r['role']=='validation']
assert len(rows)==24 and all(not r['overlapPresentByReference'] for r in rows)
audio=[{'id':r['id'],'language':r['language'],'audio':r['wav'],'audioSha256':r['wavSha256'],'frames':r['frames']} for r in rows]
audio_path=C/'audio-only.json';assert not audio_path.exists()
audio_path.write_text(json.dumps(audio,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
old=read(J/'microphone-diagnostic-r1/inference-protocol.json')
control=read(J/'microphone-diagnostic-r1/pairing.json')['control']
first=next(r for r in audio if r['id']==control['caseId'])
files=[worker,audio_path,C/'asset-receipt.json',E/'upstream/official_functions.py']
files += [Path(r['file']) for r in asset['sourceFiles']]
files += [Path(r['file']) for r in old['files'] if not any(x in r['file'] for x in [
    'native_microphone_diagnostic_20261116.py','inference-audio-only.json','pairing.json','timebase-review.json'])]
files += [S/'companion_windows_power_request_20261115.py']
P={'state':'FROZEN_ONE_OFFICIAL_FRCRN_FRONTEND_BEFORE_UNCHANGED_QWEN',
    'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'audioOnly':str(audio_path),'upstreamRoot':str(E/'upstream'),
    'enhancer':{k:asset[k] for k in ['file','sha256','revision','bytes']},
    'asr':{k:old[k] for k in ['modelRoot','modelSha256']},
    'asrControl':dict(first,id='native-unchanged-asr-control'),
    'asrControlIds':old['expectedControlIds'],'runtime':old['runtime'],'blas':old['blas'],
    'files':[item(p) for p in dict.fromkeys(files)],
    'minimumAvailableBytes':old['minimumAvailableBytes'],
    'neuralLock':'E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock',
    'stopAt':'2026-11-17T07:25:00+08:00','trainingUpdates':0,
    'frontendSetting':'Exact author FRCRN16k full-strength mask, official normalization and decode padding; original gain restored. Preserve original sample count with official final-tail cropping, no time shift/resample/VAD. Float32 output avoids clipping/extra quantization.',
    'gpuPhaseOrder':'Complete current native-context180 source run first, then enhance, then unchanged ASR in separate exclusive GPU workers.',
    'retentionGate':{'englishRelativeErrorReductionAtLeast':.2,'englishEachMeetingNoRegression':True,
        'chineseAggregateAndEachMeetingNoRegression':True,'all24CasesAndNativeAsrControlComplete':True},
    'scope':'Same24 exposed nonoverlap Chinese/English validation clips. This is not a blind whole-meeting acceptance test. No alpha/gamma/gain/model/temperature grid.',
    'qualityQualified':False,'saleQualified':False}
protocol=C/'protocol.json';assert not protocol.exists()
protocol.write_text(json.dumps(P,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
score={'protocol':str(protocol),'references':str(D/'sequential-meeting-stageA-r2/scoring-only.json'),
    'baseline':str(D/'sequential-meeting-stageA-r2/raw-text-baseline.json'),
    'files':[item(p) for p in [protocol,S/'score_frontend_component_20261116.py',
        D/'sequential-meeting-stageA-r2/scoring-only.json',D/'sequential-meeting-stageA-r2/raw-text-baseline.json',
        S/'score_sequential_meetings_20261115.py']]}
(C/'scoring-control.json').write_text(json.dumps(score,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':P['state'],'inputs':len(audio),'upstreamFunctionAstsExact':True,'newNeuralCalls':0},ensure_ascii=False))
