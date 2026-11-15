"""Freeze a fresh resource-controlled compatibility profile, not a quality claim."""
from pathlib import Path
import json,hashlib,shutil,ast,psutil
from datetime import datetime
from zoneinfo import ZoneInfo
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');m=r/'docs/handoffs/20261105-model-resume';research=r/'model-research'
probe=json.loads((m/'native-amd-probe-worker-r3.json').read_text(encoding='utf8'))
assert probe['state']=='NATIVE_RX6800XT_FP32_BF16_TINY_GPU_OPERATORS_PASSED_MODEL_UNTESTED'
assert (m/'frontend-install-report-r4.json').is_file()
assert json.loads((m/'weights-range-restore.json').read_text(encoding='utf8'))['sha256']=='9a0ceb4ab7330357db3ff583dba8d83625d5b733b00e1d55d6970e11b07026c4'
control=m/'compatibility-run';control.mkdir(exist_ok=False)
inputs=json.loads((m/'compatibility-audio-only.json').read_text(encoding='utf8'));assert len(inputs)==1 and inputs[0]['audioSeconds']==30 and inputs[0]['smokeOnly']
assert not any('reference' in k.lower() for k in inputs[0])
worker=research/'src/moss_night_gpu_worker_20261104.py';source=worker.read_text(encoding='utf8')
anchor="    state['directGpuWeightLoading']=bool(load_options)";assert source.count(anchor)==1
source=source.replace(anchor,"""    # Record the actual projection width; never assume a long prefix emits
    # only last-token logits when investigating WDDM/system-memory pressure.
    def observe_projection(module, values):
        width=int(values[0].shape[-2])
        if 'firstProjectionTokenCount' not in state:
            state['firstProjectionTokenCount']=width
        state['maximumProjectionTokenCount']=max(width,state.get('maximumProjectionTokenCount',0))
    model.lm_head.register_forward_pre_hook(observe_projection)
"""+anchor)
ast.parse(source);worker.write_text(source,encoding='utf8')
runtime='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Scripts/python.exe'
allowed=psutil.Process().cpu_affinity()
protocol={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
    'model':'OpenMOSS-Team/MOSS-Transcribe-Diarize','modelRevision':'10304d926740cf5a5cee05a268086e3265197910','officialSourceCommit':'79c675f0670cc2f824bcbcdd98263704f40f1f7e',
    'weightSha256':'9a0ceb4ab7330357db3ff583dba8d83625d5b733b00e1d55d6970e11b07026c4',
    'runtime':{'python':runtime,'torch':'2.11.0+rocm10.0.0','transformers':'5.22.1','gpuIndex':probe['chosen']['index'],'dtype':'bfloat16',
        'boundedMathAttention':True,'queryBlock':128,'keyBlock':256,'encoderBatch':1,
        'streamedWeightLoading':True,'directGpuWeightLoading':True,'nativePcm16RamLoading':True,
        'releaseUnusedModelAllocations':True,'systemPrivateMemoryBudgetBytes':2*1024**3,'workerCpuHardCapPercent':5,
        'workerGpuScheduling':'IDLE','cooperativeGpuDuty':.25,'affinity':allowed[-2:],'threads':2,
        'maxLength':131072,'maxNewTokensSmoke':2048,'maxNewTokensFull':65536,'doSample':False,'seed':0},
    'scope':'Fresh post-cleanup environment compatibility only. Recovered exact original S audio, same published model/source pins; Python/transitive dependencies reconstructed, execution tile sizes explicitly fixed before running. No full-meeting qualification or R15-result equivalence claim.'}
(control/'frozen-protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf8')
(control/'audio-only.json').write_text(json.dumps(inputs,indent=2)+'\n',encoding='utf8')
print(json.dumps({'state':'COMPATIBILITY_PROFILE_FROZEN_REFERENCE_FREE','control':str(control),'workerObservationAdded':'LM-head projection width only; no model math change'}))
