from pathlib import Path
import hashlib,json
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'sequential-meeting-stageA-r1';A=C/'speaker-r1';A.mkdir()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
inventory=read(C/'source-inventory.json')
sources=[{'meeting':r['meeting'],'audio':r['audio'],'audioSha256':r['audioSha256']} for r in inventory['sources'] if r['language']=='English']
write(A/'audio-only.json',sources)
P=read(D/'public-speaker-adaptation-r1/protocol.json')
P={k:v for k,v in P.items() if k in ['checkpoint','checkpointSha256','extractedCheckpoint','extractedCheckpointSha256','converter','converterSha256']}
P.update(audioOnlySha256=sha(A/'audio-only.json'),
 blas='E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll',
 blasSha256='88f7631d9f7c49cfbf710551a7fa69bef2fd54052007532a518d7ba3699534c0',
 newTraining=False,speakerCountHintProvided=False,qualityQualified=False,frontendRule='Direct upstream bitwise control before whole-meeting inference, original preemphasis/global padding/mask/no-CMVN, disk-backed blocks3000frames.',
 inference='Original FP32 whole-meeting AOSC340/right40/FIFO40/cache264/update300/8 native slots, no reset at selected clips.')
write(A/'protocol.json',P)
helpers=['disk_nemotron_frontend_20261115.py','public_nemotron_adaptation_20261115.py',
 'public_nemotron_supervision_20261115.py','companion_community1_adapter_20261115.py',
 'moss_windows_resource_limits_20261104.py','companion_local_pcm_session_20261114.py']
write(A/'worker-binding.json',{'workerSha256':sha(S/'sequential_meeting_speaker_worker_20261115.py'),
 'runnerSha256':sha(S/'run_sequential_meeting_speaker_20261115.py'),'protocolSha256':sha(A/'protocol.json'),
 'helpers':{str(S/name):sha(S/name) for name in helpers}})
print('FROZEN_ORIGINAL_ENGLISH_WHOLE_MEETING_SPEAKER_PLAN')
