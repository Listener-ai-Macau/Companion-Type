"""Verify exact-zero refusal preserves both signs of the quietest PCM16 signal."""
from pathlib import Path
from datetime import datetime
import hashlib,json,numpy as np
from practical_qwen_input_20261107 import is_exact_digital_silence
assert is_exact_digital_silence(np.zeros(48000,dtype=np.int16))
assert is_exact_digital_silence(np.zeros(48000,dtype=np.float32))
for value in [1,-1]:
    samples=np.zeros(48000,dtype=np.int16);samples[23999]=value
    assert not is_exact_digital_silence(samples)
    assert not is_exact_digital_silence(samples.astype(np.float32)/32768)
for invalid in [np.array([],dtype=np.int16),np.zeros((2,16)),np.array([float('nan')]),np.array([float('inf')])]:
    try:is_exact_digital_silence(invalid)
    except ValueError:pass
    else:raise AssertionError('Invalid input cannot be called quiet')
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PASS_EXACT_ZERO_GUARD_NONZERO_ONE_LSB_PRESERVED','sourceSha256':hashlib.sha256(Path(__file__).with_name('practical_qwen_input_20261107.py').read_bytes()).hexdigest(),'energyThresholdUsed':False,'neuralInferenceAdded':0,'noisySilenceSolved':False,'qualityQualified':False}
out=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-qwen-native-r1/exact-zero-guard-proof.json');assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
