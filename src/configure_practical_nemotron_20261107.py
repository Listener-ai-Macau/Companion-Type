"""Freeze the native61s boundary control and unchanged two complete development meetings."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,wave
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');base=R/'docs/handoffs/20261107-model-generation-recovery';prep=base/'nemotron-speaker-20261107-prep'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()
P=read(prep/'prepared.json');assert P['helpExitCode']==0 and all(r['verified'] for r in P['assets']);exe=Path(P['runtime']);dll=exe.parent/'nemo_speech_asr_c.dll';E=Path(P['assets'][1]['file']).parent
protocol={'frozenAt':datetime.now().astimezone().isoformat(timespec='seconds'),'model':P['assets'][1]['file'],'modelSha256':P['assets'][1]['sha256'],'modelRepository':P['modelRepository'],'modelRevision':P['modelRevision'],'precision':'Official published Q8_0 GGUF; no claim of bitwise PyTorch/BF16 equivalence','runtimeRelease':'NVIDIA/NeMo-Speech.cpp v0.3.0','nativeLibrary':str(dll),'nativeLibrarySha256':sha(dll),'nativeExe':str(exe),'nativeExeSha256':P['runtimeSha256'],'nativeFiles':{p.name:sha(p) for p in sorted(exe.parent.glob('*.dll'))},'preset':'v3-offline','streamingGeometry':{'spkcache_len':264,'fifo_len':40,'chunk_len':340,'right_context':40,'update_period':300},'inputPushSamples':486400,'probabilityThreshold':.5,'postProcessing':'uniform_frame_threshold_no_pad_no_duration_filter','thresholdTie':'Native onset>0.5/offset<0.5; equality retains previous activity','scope':'Continuous AOSC state,8-channel10ms activity only; no real names, words, oracle count, threshold sweep or default product promotion','cpuPercent':5,'privateCommitBytes':2147483648,'sources':['https://huggingface.co/nvidia/Nemotron-3-Diarization','https://github.com/NVIDIA/NeMo-Speech.cpp/tree/v0.3.0','https://huggingface.co/nvidia/Nemotron-3-Diarization/blob/'+P['modelRevision']+'/diarization_evaluation.md'],'implementationReason':'Read raw retained probabilities before native20min compaction and apply the same frozen segmentation to the whole timeline; native CLI default short-turn filters belong to the earlier4-speaker checkpoint.'}
short=base/'native8-smoke-r1';full=base/'native8-full-r1'
for c,cache in [(short,'native61-r1'),(full,'full-r1')]:
    c.mkdir(exist_ok=False);(c/'protocol.json').write_text(json.dumps({**protocol,'probabilityCacheRoot':str(E/cache)},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
source=read(base/'bounded-speaker-full-r1/audio-only.json')[1];assert sha(source['audio'])==source['audioSha256'];audio=E/'public61-from-S.wav'
with wave.open(source['audio'],'rb') as src,wave.open(str(audio),'wb') as dest:
    dest.setparams(src.getparams());dest.writeframes(src.readframes(61*16000))
case={'meeting':'public61-native8-control','audio':str(audio),'audioSha256':sha(audio),'audioSeconds':61.}
(short/'audio-only.json').write_text(json.dumps([case],indent=2)+'\n',encoding='utf8')
for name in ['audio-only.json','scoring-only.json']:shutil.copyfile(base/'bounded-speaker-full-r1'/name,full/name)
(prep/'frozen-controls.json').write_text(json.dumps({'state':'PREPARED_NO_NATIVE_MODEL_INFERENCE_YET','shortControl':str(short),'fullControl':str(full),'shortSourceAudioSha256':source['audioSha256'],'shortIsOnlyExecutionBoundaryNotQualitySample':True,'fullInputsAndScoringUnchanged':True,'originalQualityGatesUnchanged':True},indent=2)+'\n',encoding='utf8')
print(json.dumps({'state':'FROZEN_NATIVE8_CONTROLS_READY','short':str(short),'full':str(full)},ensure_ascii=False),flush=True)
