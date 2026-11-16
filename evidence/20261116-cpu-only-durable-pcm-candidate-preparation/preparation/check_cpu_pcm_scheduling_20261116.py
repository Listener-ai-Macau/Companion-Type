"""Real PCM intake / scheduler contract only; no speech output is fabricated as accepted."""
from pathlib import Path
import hashlib,json,sys,uuid,wave
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from companion_local_pcm_session_20261114 import PcmSession
from companion_local_moss_cpu_worker_20261116 import scheduled_jobs
R=S.parent.parent;BASE=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';C=BASE/'cpu-pcm-candidate-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/cpu-pcm-candidate-r1/scheduler-control-r1');assert not E.exists();E.mkdir()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
source=json.loads((BASE/'cpu-fixed-whole-r2/binding.json').read_text())['meetings'][0];assert sha(source['audio'])==source['audioSha256']
with wave.open(source['audio'],'rb') as w:pcm=w.readframes(75*16000+4000)
stream=PcmSession.create(E/'incremental',recording_id=str(uuid.uuid4()));bind={'technicalSchedulerControlOnly':True,'neuralInferencePerformed':False}
stream.append(0,pcm[:5*32000]);first=scheduled_jobs(stream)[0];assert first['endFrame']==80000 and not first['blockFinal']
stream.save_result(first,{'text':'','rawGeneratedIds':[],'accepted':False,'reviewRequired':True,'technicalSchedulerControlOnly':True},inference_binding=bind)
stream.append(5*16000,pcm[5*32000:15*32000]);second=scheduled_jobs(stream)[0];assert second['endFrame']==15*16000 and not second['blockFinal']
stream.append(15*16000,pcm[15*32000:30*32000]);third=scheduled_jobs(stream)[0];assert third['blockFinal'] and third['startFrame']==0 and third['endFrame']==30*16000
# A completed final request always takes precedence over all growing drafts.
for start in range(30*16000,len(pcm)//2,5*16000):stream.append(start,pcm[start*2:min(start+5*16000,len(pcm)//2)*2])
stream.seal(len(pcm)//2);assert stream.audio.read_bytes()==pcm
offline=PcmSession.create(E/'offline',recording_id=str(uuid.uuid4()))
for start in range(0,len(pcm),960000):offline.append(start//2,pcm[start:start+960000])
offline.seal(len(pcm)//2)
finals=lambda s:sorted((json.loads(p.read_text()) for p in (s.root/'requests').glob('*.json') if json.loads(p.read_text())['blockFinal']),key=lambda r:r['startFrame'])
a,b=finals(stream),finals(offline);assert [(x['startFrame'],x['endFrame'],x['pcmSha256']) for x in a]==[(x['startFrame'],x['endFrame'],x['pcmSha256']) for x in b]
cursor=0
for job in a:assert job['startFrame']==cursor;cursor=job['endFrame'];assert stream.read_request_pcm(job)==offline.read_request_pcm(next(x for x in b if x['startFrame']==job['startFrame']))
assert cursor==len(pcm)//2
receipt={'state':'PASS_REAL_PCM_EMPTY_DRAFT_ADVANCE_FINAL_PRIORITY_AND_OFFLINE_IDENTICAL_FINAL_INTERVALS','sourceSha256':source['audioSha256'],'frames':cursor,
 'finalIntervals':[{k:r[k] for k in ['startFrame','endFrame','pcmSha256']} for r in a],'neuralCalls':0,'technicalEmptyRejectedResultOnly':True,'qualityQualified':False}
(C/'scheduler-control.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
B=json.loads((C/'binding.json').read_text(encoding='utf-8'));assert B['workerSha256']==sha(C/'worker-before-empty-draft-scheduling.py')
B['workerSha256']=sha(S/'companion_local_moss_cpu_worker_20261116.py');B['scheduler']='Final30s blocks first; one accepted nonempty draft per open block. Empty/failed draft results remain preserved and may advance to the newest different source prefix; no replay of the same frozen request.'
B['schedulerReason']='Do not let initial room silence consume the only draft opportunity. Keep bounded final-priority scheduling without adding VAD, reference times or energy thresholds.'
(C/'binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
