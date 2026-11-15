"""Independent low-RAM NumPy check of the author's supported GPU log-mel math."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
import numpy as np
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-qwen-native-r1');E=Path('E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107/processor-control')
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);target=C/'processor-numeric-proof.json';assert not target.exists()
proof=json.loads((C/'processor-gpu-proof.json').read_text());assert proof['state']=='PASS_AUTHOR_GPU_PROCESSOR_NO_NEURAL_WEIGHTS_NUMERIC_CHECK_PENDING'
cfg=proof['featureConfig'];assert cfg=={'nFft':400,'hopLength':160,'nSamples':480000,'nWindow':50,'dither':0.}
# Tolerance is fixed before observing the comparison, for FP32 STFT/window/
# accumulation-order rounding. It never changes CER/DER or audio/reference.
tolerance=2e-4;mel=np.load(E/'official-mel-filters-f32.npy');rows=[]
for item in proof['results']:
    name=item['case'];wave=np.load(E/(name+'-waveform.npy'));actual=np.load(E/(name+'-features.npy'));mask=np.load(E/(name+'-mask.npy'))
    assert wave.ndim==1 and len(wave)==item['sampleCount'] and actual.shape[0]==1 and actual.shape[1]==128
    # torch.stft defaults: center=True, reflect padding, periodic Hann. Last
    # STFT frame is dropped by the unchanged official feature extractor.
    window=(.5-.5*np.cos(2*np.pi*np.arange(400)/400)).astype(np.float32)
    frames=np.lib.stride_tricks.sliding_window_view(np.pad(wave,(200,200),mode='reflect'),400)[::160]
    spectrum=np.fft.rfft(frames*window,axis=-1).astype(np.complex64)
    powers=(np.abs(spectrum[:-1])**2).T
    logs=np.log10(np.maximum(mel.T@powers,np.float32(1e-10)))
    expected=(np.maximum(logs,logs.max()-8)+4)/4
    pad=(-expected.shape[-1])%100
    if pad:expected=np.pad(expected,((0,0),(0,pad)))
    assert expected.shape==actual[0].shape
    difference=np.abs(expected-actual[0]);maximum=float(difference.max());mean=float(difference.mean())
    rows.append({'case':name,'maximumAbsoluteDifference':maximum,'meanAbsoluteDifference':mean,'tolerance':tolerance,'shape':list(actual.shape),'pass':maximum<=tolerance,'allOriginalSamplesIncluded':True,'maskValidFrames':int(mask.sum())})
assert all(row['pass'] for row in rows),'Do not relax numerical equivalence after observing a failure'
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PASS_SUPPORTED_GPU_FEATURES_INDEPENDENT_NUMPY_REFERENCE','results':rows,'sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'neuralInferenceAdded':0,'featureMathChanged':False,'referenceLabelsUsed':False,'qualityQualified':False,'limits':limits.query()}
atomic_json(target,result);print(json.dumps(result),flush=True)
