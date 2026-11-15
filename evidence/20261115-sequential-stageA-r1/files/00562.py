from pathlib import Path
import hashlib,json
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'sequential-meeting-stageA-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
assert read(C/'protocol.json')['state']=='FROZEN_STAGE_A_BEFORE_MODEL_OUTPUTS'
audio=read(D/'context-matched-baseline-r3/audio-only.json')[0]
old=Path('E:/CodexData/Companion/product-d1d2-20261114/context-matched-baseline-r3/base-run-r1/baseline-state.json')
row=next(r for r in read(old)['completed'] if r['id']==audio['id'])
raw=read(row['rawResult'])
assert raw['request']['pcmSha256']==audio['pcmSha256'] and raw['inferenceBinding']['languagePolicy']=='Chinese'
write(C/'numeric-control.json',{'audio':audio,'expectedRawGeneratedIds':raw['result']['rawGeneratedIds'],
 'sourceRawResult':row['rawResult'],'sourceRawResultSha256':sha(row['rawResult']),
 'purpose':'Existing unchanged Chinese generation exact before and after shared resident bilingual sessions; no reference text.'})
helpers=['companion_local_qwen_worker_20261114.py','companion_local_pcm_session_20261114.py',
 'companion_local_decode_recovery_20261114.py','practical_qwen_bounded_decode_20261107.py',
 'practical_qwen_streamed_loader_20261107.py','companion_community1_adapter_20261115.py',
 'moss_windows_resource_limits_20261104.py','companion_windows_power_request_20261115.py','practical_io_20261107.py']
write(C/'worker-binding.json',{'workerSha256':sha(S/'sequential_meeting_asr_worker_20261115.py'),
 'protocolSha256':sha(C/'protocol.json'),'numericControlSha256':sha(C/'numeric-control.json'),
 'helpers':{str(S/name):sha(S/name) for name in helpers},'runnerSha256':sha(S/'run_sequential_meeting_asr_20261115.py')})
print('BOUND_FROZEN_STAGE_A_ASR_WITH_EXACT_BILINGUAL_RESIDENCY_CONTROLS')
