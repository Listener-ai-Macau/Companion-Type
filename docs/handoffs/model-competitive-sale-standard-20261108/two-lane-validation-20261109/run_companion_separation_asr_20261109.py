"""Same existing service on mixture and target streams, fixed inputs, no retries."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio,hashlib,json,sys,time,uuid,wave
import psutil
from probe_existing_companion_asr_20261108 import existing_provider,NoRedirect,ProbeFailure,frame,parse
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109'
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);pressure=SystemRamPressure()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
extraction=read(C/'extraction-result.json');assert extraction['state']=='COMPLETE_TARGETED_SEPARATION_NOT_ASR_QUALIFIED'
cases=read(C/'overlap-audio-only.json')['cases'];packets=[]
for case in cases:
 packets.append({'id':case['id']+'-mixture','case':case['id'],'condition':'mixture','audio':case['audio'],'audioSha256':case['audioSha256'],'sourceStartSample':case['sourceStartSample'],'sourceEndSample':case['sourceEndSample']})
 for row in extraction['outputs']:
  if row['case']==case['id']:packets.append({'id':case['id']+'-native-'+row['nativePerson'],'case':case['id'],'condition':'extracted','nativePerson':row['nativePerson'],'audio':row['pcmAudio'],'audioSha256':row['pcmSha256'],'sourceStartSample':row['sourceStartSample'],'sourceEndSample':row['sourceEndSample']})
assert len(packets)==6
target=C/'asr-paired-r1';target.mkdir(exist_ok=False)
protocol={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'inputs':packets,'workerSha256':sha(__file__),'serviceHelperSha256':sha(Path(__file__).with_name('probe_existing_companion_asr_20261108.py')),'extractionResultSha256':sha(C/'extraction-result.json'),'policy':'Six fixed8s clips,2mixtures then corresponding2targetstreams each, one configuredaccount/resource/endpoint/request, no retries, hotwords or reference answers. Alloutputs retained including empty/failures. PublicAISHELL4 only. Streaming packets100ms; timing is not optimized batch latency. This is cloud ASR after local separation, not the frozen localQwen model or whole-meeting qualification.','privateAudioUploaded':False,'referencePassedToProvider':False,'serviceChanged':False,'newPaidService':False,'saleQualified':False}
write(target/'protocol.json',protocol)

async def recognize(packet):
 assert sha(packet['audio'])==packet['audioSha256']
 app,access,resource=existing_provider();seed=resource.lower().startswith('volc.seedasr.sauc.');endpoint='wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_'+('nostream' if seed else 'async');ident=str(uuid.uuid4())
 headers={'X-Api-App-Key':app,'X-Api-Access-Key':access,'X-Api-Resource-Id':resource,'X-Api-Connect-Id':ident}
 if seed:headers['X-Api-App-Id']=app
 request={'model_name':'bigmodel','enable_itn':True,'enable_punc':True,'show_utterances':True,'enable_speaker_info':True,'result_type':'full'}
 if seed:request.update(reqid=ident,sequence=1,additions={'with_speaker_info':'True'})
 else:request.update(enable_nonstream=True,ssd_version='200')
 audio={'format':'pcm','rate':16000,'bits':16,'channel':1};audio.update({'sample_rate':16000} if seed else {'codec':'raw'});ended=asyncio.Event()
 config=json.dumps({'user':{'uid':ident},'audio':audio,'request':request},separators=(',',':')).encode()
 async with NoRedirect(endpoint,extra_headers=headers,open_timeout=8,close_timeout=2,max_size=4*1024**2,compression=None) as ws:
  await ws.send(frame(1,0 if seed else 1,1,config,None if seed else 1))
  async def receive():
   async for data in ws:
    kind,final,value=parse(data)
    if kind==9 and final and ended.is_set():
     result=value.get('result');result=result[0] if isinstance(result,list) and result else result
     if isinstance(result,dict):return value
   raise ProbeFailure('NO_AUTHORITATIVE_POST_EOS_FINAL')
  receiving=asyncio.create_task(receive())
  try:
   with wave.open(packet['audio'],'rb') as f:
    assert (f.getnchannels(),f.getframerate(),f.getsampwidth(),f.getnframes())==(1,16000,2,128000);sent=0;seq=2
    while sent<128000:
     if pressure.low():raise ProbeFailure('ACTUAL_WINDOWS_LOW_MEMORY')
     if receiving.done():await receiving;raise ProbeFailure('PREMATURE_COMPLETION')
     block=f.readframes(1600);sent+=len(block)//2;last=sent==128000
     if seed and last:ended.set()
     await ws.send(frame(2,(2 if last else 0) if seed else 1,0,block,None if seed else seq));seq+=1;await asyncio.sleep(.1)
   if not seed:ended.set();await ws.send(frame(2,3,0,b'',-seq))
   response=await asyncio.wait_for(receiving,30)
   return response,{'providerGeneration':'seed-asr-v2' if seed else 'bigmodel','endpoint':endpoint,'wireRequestWithoutCredentials':request}
  finally:
   if not receiving.done():receiving.cancel();await asyncio.gather(receiving,return_exceptions=True)

async def main():
 rows=[];started=time.perf_counter()
 for packet in packets:
  tick=time.perf_counter();row={'id':packet['id'],'state':'RUNNING','retryCount':0}
  try:
   response,metadata=await asyncio.wait_for(recognize(packet),55);write(target/(packet['id']+'-response.json'),response);row.update(state='COMPLETE',**metadata)
  except ProbeFailure as e:row.update(state='FAILED',reason=str(e))
  except BaseException as e:row.update(state='FAILED',failureType=type(e).__name__)
  row.update(wallSeconds=time.perf_counter()-tick,privateBytes=psutil.Process().memory_info().private);rows.append(row);write(target/'run.json',{'state':'RUNNING' if len(rows)<len(packets) else 'COMPLETE' if all(x['state']=='COMPLETE' for x in rows) else 'COMPLETE_WITH_FAILURES','rows':rows,'wallSeconds':time.perf_counter()-started,'limits':limits.query(),'saleQualified':False});print(json.dumps(row,ensure_ascii=False),flush=True)
asyncio.run(main())
