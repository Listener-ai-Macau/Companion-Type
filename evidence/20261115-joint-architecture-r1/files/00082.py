from pathlib import Path
import hashlib,json,sys,wave
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
train=next(r for r in read(D/'public-speaker-adaptation-r1/audio-only.json') if r['meeting']=='20200708_L_R002S01C01')
ami=next(r for r in read(D/'sequential-meeting-stageA-r2/activity-cal-r1/sources.json') if r['meeting']=='IS1000a')
cases=[]
for source in [train,ami]:
 assert sha(source['audio'])==source['audioSha256']
 with wave.open(source['audio'],'rb') as wav:
  assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(1,2,16000);assert wav.getnframes()>=180*16000
  pcm=wav.readframes(180*16000)
 target=E/(source['meeting']+'-first180s.wav');assert not target.exists()
 with wave.open(str(target),'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(pcm)
 cases.append({'meeting':source['meeting'],'audio':str(target),'audioSha256':sha(target),'frames':180*16000,
  'purpose':'First180s of a public training recording; fixed order Chinese then English. Runtime/format proof only, not complete-meeting quality or architecture selection.'})
write(C/'pilot-audio-only.json',cases)
files=['moss_native_architecture_20261115.py','moss_streamed_weights_20261104.py','moss_windows_resource_limits_20261104.py',
 'companion_community1_adapter_20261115.py','practical_io_20261107.py']
runtime=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/transformers/models/moss_transcribe_diarize')
helpers={str(S/name):sha(S/name) for name in files}
helpers.update({str(runtime/name):sha(runtime/name) for name in ['configuration_moss_transcribe_diarize.py','modeling_moss_transcribe_diarize.py','processing_moss_transcribe_diarize.py','feature_extraction_moss_transcribe_diarize.py']})
write(C/'pilot-binding.json',{'workerSha256':sha(S/'moss_native_pilot_worker_20261115.py'),
 'runnerSha256':sha(S/'run_moss_native_architecture_20261115.py'),'audioManifestSha256':sha(C/'pilot-audio-only.json'),
 'helpers':helpers,'blas':'E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll',
 'blasSha256':'88f7631d9f7c49cfbf710551a7fa69bef2fd54052007532a518d7ba3699534c0'})
print('Native joint runtime proof inputs frozen; no transcript/person/count labels')
