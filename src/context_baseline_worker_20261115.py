"""One frozen context-matched base-model diagnostic, with no label access."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,uuid,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_local_pcm_session_20261114 import PcmSession,atomic_json,exclusive_file
from companion_local_qwen_worker_20261114 import NativeDecoder
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 p=argparse.ArgumentParser()
 for flag in ['control','inventory','run']:p.add_argument('--'+flag,type=Path,required=True)
 a=p.parse_args();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
 binding=read(a.control/'worker-binding.json');protocol=read(a.control/'protocol.json')
 assert binding['workerSha256']==sha(__file__) and binding['protocolSha256']==sha(a.control/'protocol.json')
 for path,expected in binding['helpers'].items():assert sha(path)==expected
 assert protocol['newTraining'] is False and protocol['cases']==32
 assert sha(a.control/'audio-only.json')==protocol['audioOnlyManifestSha256']
 assert sha(protocol['nativeProtocol'])==protocol['nativeProtocolSha256']
 cases=read(a.control/'audio-only.json')
 allowed={'id','condition','meeting','wav','wavSha256','pcmSha256','frames','audioSeconds','language'}
 assert len(cases)==32 and all(set(c)==allowed and c['language']=='Chinese' for c in cases)
 state={'state':'STARTING_FROZEN_CONTEXT_BASELINE','startedAt':datetime.now().astimezone().isoformat(),
  'completed':[],'newTraining':False,'parameterUpdates':0,'validationReferenceRead':False,
  'qualityQualified':False,'automaticRetries':0,'workerSourceSha256':sha(__file__)}
 def save():
  state.update(limits=limits.query(),observedAt=datetime.now().astimezone().isoformat())
  atomic_json(a.run/'baseline-state.json',state)
 decoder=None;began=time.perf_counter();save()
 try:
  for case in cases:
   if (a.run/'stop.request').exists():raise InterruptedError('Owned stop; retain all sources and raw nodes')
   assert sha(case['wav'])==case['wavSha256']
   with wave.open(case['wav'],'rb') as wav:
    assert wav.getnchannels()==1 and wav.getsampwidth()==2 and wav.getframerate()==16000
    assert wav.getnframes()==case['frames'] and 0<case['frames']<=480000
    pcm=wav.readframes(case['frames'])
   assert hashlib.sha256(pcm).hexdigest()==case['pcmSha256']
   session=PcmSession.create(a.run/'sessions'/case['id'],recording_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'companion-context-baseline-r1/'+case['id'])),language='Chinese')
   session.append(0,pcm);session.seal(case['frames']);jobs=session.pending()
   assert len(jobs)==1 and jobs[0]['blockFinal'] and jobs[0]['startFrame']==0 and jobs[0]['endFrame']==case['frames']
   if decoder is None:decoder=NativeDecoder(protocol['nativeProtocol'],a.inventory,session,a.run)
   else:
    assert session.state()['config']['language']==decoder.language
    decoder.session=session
   state.update(state='RUNNING_FROZEN_CONTEXT_BASELINE',activeCase=case['id']);save()
   with exclusive_file(session.root/'inference.lock'):decoder.transcribe(jobs[0])
   document=session.document();assert document['isFinal'] and document['confirmedAudioFrames']==case['frames']
   atomic_json(session.root/'document.json',document)
   state['completed'].append({'id':case['id'],'document':str(session.root/'document.json'),
    'documentSha256':sha(session.root/'document.json'),'pcmSha256':sha(session.audio),
    'rawResult':str(session.root/'results'/(jobs[0]['jobId']+'.json')),'reviewRequired':document['reviewRequired']})
   assert state['completed'][-1]['pcmSha256']==case['pcmSha256'];save()
  state.update(state='COMPLETE_FROZEN_CONTEXT_BASELINE_UNQUALIFIED',neuralCalls=decoder.state['neuralCalls'],
   inferenceSeconds=decoder.state['freshInferenceSeconds'],modelLoadSeconds=decoder.state['modelLoadSeconds'])
 except BaseException as error:
  state.update(state='INCOMPLETE_FROZEN_CONTEXT_BASELINE_RETAINED_NO_RETRY',error=repr(error));raise
 finally:
  state.update(seconds=time.perf_counter()-began,finishedAt=datetime.now().astimezone().isoformat());state.pop('activeCase',None);save()
 print(json.dumps(state,ensure_ascii=False))

if __name__=='__main__':main()
