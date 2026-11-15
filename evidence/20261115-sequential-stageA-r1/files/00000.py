"""Existing bilingual decoder on frozen sequential meeting audio; no gold access."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,uuid,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_local_pcm_session_20261114 import PcmSession,atomic_json,exclusive_file
from companion_local_qwen_worker_20261114 import NativeDecoder
from companion_community1_adapter_20261115 import pin_rocm_blas
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
 assert protocol['newTraining'] is False and protocol['state']=='FROZEN_STAGE_A_BEFORE_MODEL_OUTPUTS'
 assert sha(a.control/'audio-only.json')==protocol['audioOnlyManifestSha256']
 assert sha(protocol['nativeProtocol'])==protocol['nativeProtocolSha256']
 assert sha(a.control/'numeric-control.json')==binding['numericControlSha256']
 cases=read(a.control/'audio-only.json');control=read(a.control/'numeric-control.json')
 assert len(cases)==protocol['cases']
 allowed={'id','condition','meeting','wav','wavSha256','pcmSha256','frames','audioSeconds','language'}
 assert all(set(c)==allowed and c['language'] in ('Chinese','English') for c in cases)
 assert control['audio']['language']=='Chinese'
 blas=pin_rocm_blas(Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll'),
  '88f7631d9f7c49cfbf710551a7fa69bef2fd54052007532a518d7ba3699534c0')
 state={'state':'STARTING_STAGE_A_ASR','startedAt':datetime.now().astimezone().isoformat(),
  'completed':[],'controls':[],'newTraining':False,'parameterUpdates':0,'validationReferenceRead':False,
  'qualityQualified':False,'automaticRetries':0,'workerSourceSha256':sha(__file__),'blas':blas,
  'neuralCalls':0,'inferenceSeconds':0.,'modelLoads':0}
 def save():
  state.update(limits=limits.query(),observedAt=datetime.now().astimezone().isoformat())
  atomic_json(a.run/'baseline-state.json',state)
 resident=None;began=time.perf_counter();save()
 try:
  sequence=[('control-before',control['audio'])]+[(None,c) for c in cases]+[('control-after-english',control['audio'])]
  for control_id,case in sequence:
   if (a.run/'stop.request').exists():raise InterruptedError('Owned stop; retain audio and raw nodes')
   assert sha(case['wav'])==case['wavSha256']
   with wave.open(case['wav'],'rb') as wav:
    assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(1,2,16000)
    assert wav.getnframes()==case['frames'] and 0<case['frames']<=480000
    pcm=wav.readframes(case['frames'])
   assert hashlib.sha256(pcm).hexdigest()==case['pcmSha256']
   case_id=control_id or case['id'];session=PcmSession.create(a.run/'sessions'/case_id,
    recording_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'companion-sequential-stageA-r1/'+case_id)),language=case['language'])
   session.append(0,pcm);session.seal(case['frames']);jobs=session.pending()
   assert len(jobs)==1 and jobs[0]['blockFinal'] and jobs[0]['startFrame']==0 and jobs[0]['endFrame']==case['frames']
   # A fresh adapter binds each session/language. Share only immutable model,
   # processor and torch pointers; never carry decoder context or raw nodes.
   decoder=NativeDecoder(protocol['nativeProtocol'],a.inventory,session,a.run/'decoders'/case_id)
   if resident is not None:
    decoder.model,decoder.processor,decoder.torch=resident
    decoder.state.update(modelLoaded=True,modelLoadSeconds=0.,sharedResidentWeights=True)
   state.update(state='RUNNING_STAGE_A_ASR',activeCase=case_id,language=case['language']);save()
   with exclusive_file(session.root/'inference.lock'):result=decoder.transcribe(jobs[0])
   if resident is None:
    resident=(decoder.model,decoder.processor,decoder.torch);state['modelLoads']+=1
    state['modelLoadSeconds']=decoder.state['modelLoadSeconds']
   document=session.document();assert document['isFinal'] and document['confirmedAudioFrames']==case['frames']
   atomic_json(session.root/'document.json',document)
   row={'id':case_id,'language':case['language'],'document':str(session.root/'document.json'),
    'documentSha256':sha(session.root/'document.json'),'pcmSha256':sha(session.audio),
    'rawResult':str(session.root/'results'/(jobs[0]['jobId']+'.json')),'reviewRequired':document['reviewRequired'],
    'neuralCalls':decoder.state['neuralCalls'],'inferenceSeconds':decoder.state['freshInferenceSeconds']}
   assert row['pcmSha256']==case['pcmSha256']
   if control_id:
    assert result['rawGeneratedIds']==control['expectedRawGeneratedIds'],'Existing numeric control changed'
    row['generatedIdsExact']=True;state['controls'].append(row)
   else:state['completed'].append(row)
   state['neuralCalls']+=decoder.state['neuralCalls'];state['inferenceSeconds']+=decoder.state['freshInferenceSeconds'];save()
  assert len(state['controls'])==2 and state['modelLoads']==1
  state.update(state='COMPLETE_STAGE_A_RAW_ASR_UNQUALIFIED')
 except BaseException as error:
  state.update(state='INCOMPLETE_STAGE_A_ASR_RETAINED_NO_RETRY',error=repr(error));raise
 finally:
  state.update(seconds=time.perf_counter()-began,finishedAt=datetime.now().astimezone().isoformat());state.pop('activeCase',None);save()
 print(json.dumps({k:v for k,v in state.items() if k not in ('completed','controls')},ensure_ascii=False))
if __name__=='__main__':main()
