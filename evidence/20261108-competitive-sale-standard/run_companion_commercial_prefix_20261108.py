"""One fixed public prefix through the existing provider; never reads scoring answers."""
from pathlib import Path
from datetime import datetime
import asyncio,hashlib,json,sys,time,wave
import psutil
from websockets.exceptions import InvalidStatusCode
from probe_existing_companion_asr_20261108 import existing_provider,NoRedirect,ProbeFailure,frame,parse
import uuid
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-competitive-sale-standard'
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
P=json.loads((C/'prefix-protocol.json').read_text(encoding='utf8'))
assert hashlib.sha256(Path(P['audio']).read_bytes()).hexdigest()==P['audioSha256']
assert P['state']=='FROZEN_PUBLIC_REAL_MEETING_PREFIX_DIAGNOSTIC' and P['referencePassedToProvider'] is False and not P['hotwords']
assert not (C/'prefix-final-response.json').exists()
started=time.perf_counter();process=psutil.Process();state={'startedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'pid':process.pid,'state':'RUNNING_PUBLIC_PREFIX_COMPARISON','protocolSha256':hashlib.sha256((C/'prefix-protocol.json').read_bytes()).hexdigest(),'audioSeconds':P['audioSeconds'],'sentAudioSeconds':0,'responsePackets':0,'privatePeakBytes':0,'privateAudioUploaded':False,'saleQualified':False,'retryCount':0}
def save():
 state['wallSeconds']=time.perf_counter()-started
 state['privatePeakBytes']=max(state['privatePeakBytes'],process.memory_info().private)
 temp=C/'prefix-run.tmp';temp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8');temp.replace(C/'prefix-run.json')
def result_object(value):
 result=value.get('result')
 return result[0] if isinstance(result,list) and result else result
async def run():
 app,access,resource=existing_provider();seed=resource.lower().startswith('volc.seedasr.sauc.')
 endpoint='wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_'+('nostream' if seed else 'async');ident=str(uuid.uuid4())
 state.update(providerGeneration='seed-asr-v2' if seed else 'bigmodel',endpoint=endpoint)
 headers={'X-Api-App-Key':app,'X-Api-Access-Key':access,'X-Api-Resource-Id':resource,'X-Api-Connect-Id':ident}
 if seed:headers['X-Api-App-Id']=app
 request={'model_name':'bigmodel','enable_itn':True,'enable_punc':True,'show_utterances':True,'enable_speaker_info':True,'result_type':'full'}
 if seed:request.update(reqid=ident,sequence=1,additions={'with_speaker_info':'True'})
 else:request['enable_nonstream']=False
 audio={'format':'pcm','rate':16000,'bits':16,'channel':1};audio.update({'sample_rate':16000} if seed else {'codec':'raw'})
 config=json.dumps({'user':{'uid':ident},'audio':audio,'request':request},separators=(',',':')).encode();ended=asyncio.Event()
 async with NoRedirect(endpoint,extra_headers=headers,open_timeout=8,close_timeout=2,max_size=4*1024**2,compression=None) as ws:
  await ws.send(frame(1,0 if seed else 1,1,config,None if seed else 1))
  async def receive():
   async for data in ws:
    kind,final,value=parse(data)
    if kind!=9:continue
    state['responsePackets']+=1
    result=result_object(value)
    if not isinstance(result,dict):continue
    text=result.get('text')
    if final and ended.is_set() and isinstance(text,str) and text.strip():
     (C/'prefix-final-response.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
     return
   raise ProbeFailure('NO_AUTHORITATIVE_POST_EOS_FINAL')
  receiving=asyncio.create_task(receive())
  try:
   with wave.open(P['audio'],'rb') as wav:
    assert (wav.getnchannels(),wav.getframerate(),wav.getsampwidth())==(1,16000,2)
    total=wav.getnframes();sent=0;seq=2
    while sent<total:
     if receiving.done():await receiving;raise ProbeFailure('PREMATURE_COMPLETION')
     block=wav.readframes(1600);sent+=len(block)//2;last=sent==total
     if seed and last:ended.set()
     await ws.send(frame(2,(2 if last else 0) if seed else 1,0,block,None if seed else seq));seq+=1
     state['sentAudioSeconds']=sent/16000
     if seq%100==0:save()
     await asyncio.sleep(.1)
   if not seed:
    ended.set();await ws.send(frame(2,3,0,b'',-seq))
   await asyncio.wait_for(receiving,timeout=30)
  finally:
   if not receiving.done():receiving.cancel();await asyncio.gather(receiving,return_exceptions=True)
 state['state']='COMPLETE_PUBLIC_PREFIX_REFERENCE_ASR_REVIEW_REQUIRED'
if __name__=='__main__':
 save()
 try:asyncio.run(asyncio.wait_for(run(),timeout=P['audioSeconds']*1.3+60))
 except InvalidStatusCode as e:state.update(state='PUBLIC_PREFIX_HANDSHAKE_REJECTED',httpStatus=int(e.status_code))
 except ProbeFailure as e:state.update(state='PUBLIC_PREFIX_FAILED',reason=str(e))
 except asyncio.TimeoutError:state.update(state='PUBLIC_PREFIX_TIMEOUT')
 except Exception as e:state.update(state='PUBLIC_PREFIX_FAILED',failureType=type(e).__name__)
 state['finishedAt']=datetime.now().astimezone().isoformat(timespec='seconds');save();print(json.dumps(state,ensure_ascii=False),flush=True)
