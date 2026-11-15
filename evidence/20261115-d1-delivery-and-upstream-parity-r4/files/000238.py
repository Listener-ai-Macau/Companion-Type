"""Exact author-function/streamed-WAV boundary controls; no neural inference."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,typing,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
import numpy as np
from practical_qwen_audio_boundaries_20261107 import quiet_wav_spans
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery';C=B/'practical-qwen-native17-r5'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
up=B/'practical-qwen-native-r1/upstream-input-review';source=up/'qwen_asr__inference__utils.py.txt'
manifest=next(row for row in read(up/'manifest.json') if row['name']=='qwen_asr/inference/utils.py')
assert sha(source)==manifest['sha256']
source_bytes=source.read_bytes();assert hashlib.sha1(b'blob '+str(len(source_bytes)).encode()+b'\0'+source_bytes).hexdigest()==manifest['gitBlob']
parsed=ast.parse(source_bytes.decode());function=next(node for node in parsed.body if isinstance(node,ast.FunctionDef) and node.name=='split_audio_into_chunks')
namespace={'np':np,'List':typing.List,'Tuple':typing.Tuple,'MIN_ASR_INPUT_SECONDS':.5}
exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),namespace)
original=namespace['split_audio_into_chunks'];assets=Path('E:/CodexData/Companion/.model-cache/qwen-native17-asr-20261107/boundary-math-controls');assets.mkdir(exist_ok=False)
assert not (C/'author-boundary-preparation.json').exists();controls=[]
def check(label,pcm):
    audio=assets/(label+'.wav')
    with wave.open(str(audio),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm.tobytes())
    values=pcm.astype(np.float32);values/=32768
    expected=original(values,16000,30.,search_expand_sec=5.,min_window_ms=100.)
    actual=quiet_wav_spans(audio)
    assert len(expected)==len(actual)
    for (chunk,offset),row in zip(expected,actual):
        assert round(offset*16000)==row['startSample']
        raw=values[row['startSample']:row['endSample']]
        padded=np.pad(raw,(0,row['paddingSamples'])) if row['paddingSamples'] else raw
        assert np.array_equal(chunk,padded),'Port changed a cut sample or upstream tail padding'
    controls.append({'label':label,'samples':len(pcm),'spanCount':len(actual),'allSpanSamplesAndPaddingEqualToExactAuthorFunction':True})
rng=np.random.default_rng(20261107)
pcm=rng.integers(-16000,16001,16000*93,dtype=np.int16)
pcm[26*16000:27*16000]=0;pcm[59*16000:60*16000]=0
check('synthetic-pcm-boundary-math-not-speech-quality',pcm)
check('short-upstream-early-return-no-padding',np.ones(4000,dtype=np.int16))
case=read(C/'audio-only.json')[0];assert sha(case['audio'])==case['audioSha256']
with wave.open(case['audio'],'rb') as stream:pcm=np.frombuffer(stream.readframes(16000*120),dtype='<i2')
check('public-original120s-boundary-math-not-asr-quality',pcm)
del pcm
rows=[]
for case in read(C/'audio-only.json'):
    assert sha(case['audio'])==case['audioSha256']
    spans=quiet_wav_spans(case['audio']);rows.append({**case,'spans':spans})
atomic_json(C/'author-boundaries-audio-only.json',rows)
proof={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PASS_BOUNDED_WAV_AUTHOR_BOUNDARY_MATH_ONLY_NO_ASR_QUALITY_RESULT',
  'upstreamRevision':manifest['revision'],'upstreamSourceSha256':manifest['sha256'],
  'portSourceSha256':sha(Path(__file__).with_name('practical_qwen_audio_boundaries_20261107.py')),
  'controls':controls,'localTargetSeconds':30.,'authorDefaultAsrTargetSeconds':1200.,'searchExpandSeconds':5.,'energyWindowMilliseconds':100.,
  'sameBoundaryRuleDifferentMemoryBudget':True,'allOriginalSamplesCoveredOnce':True,'noiseOrSpeechRemoved':False,
  'fullPublicSpans':[{'meeting':row['meeting'],'spans':len(row['spans']),'minSeconds':min((s['endSample']-s['startSample'])/16000 for s in row['spans']),
    'maxSeconds':max((s['endSample']-s['startSample'])/16000 for s in row['spans']),'paddingSamples':sum(s['paddingSamples'] for s in row['spans'])} for row in rows],
  'modelInferenceAdded':0,'activeNative17NeuralProtocolChanged':False,'referencesOpened':False,'qualityQualified':False,'limits':limits.query(),
  'scope':'Exact mathematical boundary equality on public120s and synthetic non-speech controls. Full real-meeting manifests prepared without neural scoring. No evidence yet of lower CER; not the authors1200s end-to-end configuration or a completed new quality experiment.'}
atomic_json(C/'author-boundary-preparation.json',proof)
print(json.dumps({k:proof[k] for k in ['state','fullPublicSpans','modelInferenceAdded','qualityQualified']}))
