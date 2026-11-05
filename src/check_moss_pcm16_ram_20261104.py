from pathlib import Path
import hashlib,json,sys
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5)
import numpy as np
root=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104')
assets=Path('E:/CodexData/Companion/asr-accuracy-latency-20261103/multispeaker-ai/joint-moss-architecture-20261104')
sys.path.insert(0,str(assets/'official-source'))
from moss_transcribe_diarize import inference_utils
from moss_pcm16_ram_20261104 import install_pcm16_loader
cases=json.loads((root/'compatibility-audio-only.json').read_text(encoding='utf8'))+json.loads((root/'screening-audio-only-r4.json').read_text(encoding='utf8'))
original=inference_utils.load_audio_item
stats=install_pcm16_loader(inference_utils);checks=[]
for case in cases:
    old=original(case['audio'],sampling_rate=16000)
    new=inference_utils.load_audio_item(case['audio'],sampling_rate=16000)
    assert old.dtype==new.dtype==np.float32 and old.shape==new.shape and np.array_equal(old,new)
    checks.append({'meeting':case['meeting'],'samples':len(new),'allFloat32SamplesBitwiseIdentical':True,
      'sampleBytesSha256':hashlib.sha256(new.tobytes()).hexdigest()})
    del old,new
target=root/'pcm16-input-equivalence-r10.json';assert not target.exists()
report={'state':'PASS_NATIVE_PCM16_FLOAT32_INPUT_EQUIVALENCE','cases':checks,'loader':stats,
 'modelLoaded':False,'modelInferenceRepeated':False,'otherFormatsStillUseOriginalLoader':True}
target.write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
