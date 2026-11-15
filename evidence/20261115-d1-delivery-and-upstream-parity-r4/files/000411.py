"""One causal ablation for a demonstrated interior sentence erased by the gate."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,wave
import numpy as np
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
B=R/'docs/handoffs/20261108-dual-mic-real-meeting-validation';C=B/'no-hard-gate'
E=Path('E:/CodexData/Companion/.model-cache/dual-mic-real-meeting-20261108/no-hard-gate')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
assert not C.exists();C.mkdir();E.mkdir();audit=read(B/'codec-and-gate-audit.json')
assert any(r['fullyContainedCompletelyRemovedCharacters']>0 for r in audit['predictedGateCoverage'] if not r['ordinaryBypassDoesNotApplyThisGate'])
prepared=[]
for row in read(B/'separation-manifest-r2.json'):
    if row['arm']!='dual_pcm' or row['ordinaryBypass']:continue
    source=Path(row['ungatedDerivedAudio']);data=np.load(source,allow_pickle=False)
    assert data.shape==(480000,) and np.isfinite(data).all() and float(np.max(np.abs(data)))<1 and row['pcmExportDivisor']==1
    output=E/(row['id']+'-no-hard-gate.wav');assert not output.exists()
    pcm=np.rint(data*32768).clip(-32768,32767).astype('<i2')
    with wave.open(str(output),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm.tobytes())
    prepared.append({**row,'id':row['id']+'-no-hard-gate','arm':'dual_pcm_no_gate','audio':str(output),'audioSha256':sha(output),
        'sourceUngatedFloatSha256':sha(source),'originalGatedAudioSha256':row['audioSha256'],
        'predictedActivityGateApplied':False,'predictedActivityStillUsedInsideGss':True,
        'sourceSpatialProtocolSha256':sha(B/'protocol-r2.json'),'newSeparationCalls':0,
        'sameExportGainAndTimeline':True,'noReferenceWordsOrActivityUsedForAudio':True})
assert len(prepared)==6
for name in ['audio-only.json','separation-manifest-r2.json']:atomic_json(C/name,prepared)
for name in ['model-ready.json','hip-inventory.json']:(C/name).write_bytes((B/name).read_bytes())
atomic_json(C/'seed-manifest.json',{})
atomic_json(C/'separation-state-r2.json',{'state':'REUSED_FROZEN_GSS_FLOAT_OUTPUTS_WITHOUT_AUDIO_GATE','sourceProtocolSha256':sha(B/'protocol-r2.json'),'newSeparationCalls':0,'newModelCalls':0,'derivedRows':6,'qualityQualified':False})
P=read(B/'protocol-r2.json');source=S/'dual_mic_gss_asr_worker_20261108.py';assert sha(source)==P['asrWorkerSourceSha256']
text=source.read_text(encoding='utf8').replace(str(B).replace('\\','/'),str(C).replace('\\','/')).replace('COMPLETE_GUIDED_DUAL_MIC_SEPARATION_NOT_PRODUCT','REUSED_FROZEN_GSS_FLOAT_OUTPUTS_WITHOUT_AUDIO_GATE')
def inference_ast(value):return ast.dump(next(n for n in ast.walk(ast.parse(value)) if isinstance(n,ast.FunctionDef) and n.name=='infer'),include_attributes=False)
assert inference_ast(text)==inference_ast(source.read_text(encoding='utf8'))
worker=S/'dual_mic_gss_no_gate_asr_worker_20261108.py';assert not worker.exists();worker.write_text(text,encoding='utf8')
controller=(S/'run_dual_mic_gss_validation_20261108.py').read_text(encoding='utf8').replace(str(B).replace('\\','/'),str(C).replace('\\','/'))
needle="stages=[('separation','dual_mic_gss_worker_20261108.py',[],C/'separation-state-r2.json','COMPLETE_GUIDED_DUAL_MIC_SEPARATION_NOT_PRODUCT'),\n    ('inventory'"
assert needle in controller;controller=controller.replace(needle,"stages=[('inventory'").replace('dual_mic_gss_asr_worker_20261108.py','dual_mic_gss_no_gate_asr_worker_20261108.py')
launcher=S/'run_dual_mic_gss_no_gate_20261108.py';assert not launcher.exists();ast.parse(controller);launcher.write_text(controller,encoding='utf8')
P.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='ONE_CAUSAL_REMOVE_POST_GSS_HARD_GATE_CONTROL_FROZEN',
    asrWorkerSourceSha256=sha(worker),audioOnlySha256=sha(C/'audio-only.json'),
    causalChange='Remove only final predicted waveform zeroing from all6existing rawdual target outputs. Reuse identical GSS float arrays; same PCM gain,sample grid,ASR generation. No new separation/activity/training, no selected-person winner.',
    triggerEvidence={'file':str(B/'codec-and-gate-audit.json'),'sha256':sha(B/'codec-and-gate-audit.json')},
    scope='Exposed local causal ablation only. Reference audit identified hard gate loss, but no reference time or word changes the new audio. Report all6people and additions/deletions, retaining the first21row comparison unchanged.',
    stop='One causal removal test only. Do not mix gated/ungated text per person or tune voice/cutoff/codec. If restored content brings unacceptable extra words, stop this branch and retain both failures.')
atomic_json(C/'protocol-r2.json',P)
atomic_json(C/'preparation.json',{'state':P['state'],'sourceBaseProtocolSha256':sha(B/'protocol-r2.json'),'derivedRows':6,'newGssCalls':0,'newModelFamilies':0,'sameInferenceAst':True,'sameOriginalFloatOutputAndGain':True,'qualityQualified':False})
print(json.dumps(read(C/'preparation.json')),flush=True)
