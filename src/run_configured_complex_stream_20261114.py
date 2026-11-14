"""One public complete real meeting through the existing configured ASR resource.

Official long-meeting streaming endpoint/two-pass mode; no new account/service,
reference/hotwords/person count, retries, audio replay or product-default change.
Input/receive run concurrently at the original100ms pacing. All response deltas
and the authoritative post-EOS final are retained; no invented word alignment.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import asyncio,hashlib,json,sys,time,uuid,wave
import psutil

ROOT=Path('C:/Users/Billy/Desktop/Denzic/Companion')
HELPER=ROOT/'model-research/evidence/20261108-competitive-sale-standard'
sys.path.insert(0,str(HELPER))
from probe_existing_companion_asr_20261108 import existing_provider,NoRedirect,ProbeFailure,frame,parse
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
OUT=ROOT/'docs/handoffs/20261109-paired-real-meeting/sleep-continuation20261114/configured-full-complex'
AUDIO=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/L_R003S01C02-channel1.wav')
EXPECTED='768574317a1054afe52a098f8b2630185974a57eb42144ecdf249e929807fc1a'
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

async def main():
    if OUT.exists():
        assert not any(OUT.iterdir()),'Retain the existing request; no automatic replay/retry'
        write(OUT/'preparation-failures-before-upload.json',{'networkRequests':0,'audioFramesSent':0,
              'failures':['The clean scoring interpreter did not contain websockets; use the existing system Python11.0.3 websocket runtime.',
                          'The configured existing resource is ASR1.0, not the presumed2.0. Bind the actual resource and unchanged original1.0 framing/request; never upgrade the account/service.']})
    else:OUT.mkdir()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=128*1024**2)
    pressure=SystemRamPressure();started=time.perf_counter()
    assert sha(AUDIO)==EXPECTED
    with wave.open(str(AUDIO),'rb') as audio:
        assert (audio.getnchannels(),audio.getframerate(),audio.getsampwidth(),audio.getcomptype())==(1,16000,2,'NONE')
        total=audio.getnframes()
    app,access,resource=existing_provider()
    assert resource.lower().startswith(('volc.seedasr.sauc.','volc.bigasr.sauc.')),'Do not substitute another service/resource'
    seed=resource.lower().startswith('volc.seedasr.sauc.')
    endpoint='wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async'
    ident=str(uuid.uuid4())
    request={'model_name':'bigmodel','enable_itn':True,'enable_punc':True,'show_utterances':True,
             'enable_speaker_info':True,'result_type':'full','enable_nonstream':True}
    if seed:request.update(reqid=ident,sequence=1,additions={'with_speaker_info':'True'})
    else:request['ssd_version']='200'
    record={'at':now(),'state':'PREPARING_CONFIGURED_COMPLETE_COMPLEX_STREAM','pid':psutil.Process().pid,
            'meeting':'L_R003S01C02','audio':str(AUDIO),'audioSha256':EXPECTED,'audioSeconds':total/16000,
            'sourceScope':'Existing exposed public six-person real meeting; reference never enters this worker.',
            'endpoint':endpoint,'resourceId':resource,'wireRequestWithoutCredentials':request,
            'officialSources':['https://docs.volcengine.com/docs/doubao-voice/access-must-read-1-1?lang=zh',
                               'https://docs.volcengine.com/docs/doubao-voice/speaker-separation?lang=zh'],
            'differenceFromPriorShortCloudControls':('Same configured ASR2 hourly resource; documented long-meeting async/two-pass mode instead of sentence-oriented nostream.' if seed else 'Same actual configured ASR1.0 hourly resource, async/two-pass request and framing as the original six short cloud controls; now one complete continuous meeting.'),
            'notTheFixedLocalQwenComparison':True,
            'newServiceOrAccount':False,'referencePassedToProvider':False,'privateAudioUploaded':False,
            'originalAudioUnchanged':True,'retryCount':0,'productDefaultChanged':False,
            'sentFrames':0,'responsePackets':0,'neuralInferenceOnLocalComputer':False,
            'qualityQualified':False,'saleQualified':False,'actualWindowsLowRam':False}
    def save():
        record.update(elapsedSeconds=time.perf_counter()-started,limits=limits.query())
        write(OUT/'state.json',record)
    save();ended=asyncio.Event();last_result=None;last_delta={}
    audio_config={'format':'pcm','rate':16000,'bits':16,'channel':1}
    audio_config.update({'sample_rate':16000} if seed else {'codec':'raw'})
    config=json.dumps({'user':{'uid':ident},'audio':audio_config,'request':request},separators=(',',':')).encode()
    headers={'X-Api-App-Key':app,'X-Api-Access-Key':access,'X-Api-Resource-Id':resource,'X-Api-Connect-Id':ident}
    if seed:headers['X-Api-App-Id']=app
    try:
        if pressure.low():
            record['actualWindowsLowRam']=True;raise ProbeFailure('ACTUAL_WINDOWS_LOW_MEMORY_BEFORE_UPLOAD')
        async with NoRedirect(endpoint,extra_headers=headers,open_timeout=8,close_timeout=2,max_size=4*1024**2,max_queue=2,compression=None) as ws:
            await ws.send(frame(1,0 if seed else 1,1,config,None if seed else 1))
            record.update(state='RUNNING_CONFIGURED_COMPLETE_COMPLEX_STREAM',connectedAt=now());save()
            async def receive():
                nonlocal last_result,last_delta
                async for data in ws:
                    kind,final,value=parse(data)
                    if kind!=9:continue
                    record['responsePackets']+=1
                    result=value.get('result');result=result[0] if isinstance(result,list) and result else result
                    if not isinstance(result,dict):continue
                    last_result=value
                    # Persist changes, not thousands of repeated full prefixes.
                    utterances=result.get('utterances') or []
                    changed=[]
                    for index,row in enumerate(utterances):
                        encoded=json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':'))
                        fingerprint=hashlib.sha256(encoded.encode()).hexdigest()
                        if last_delta.get(index)!=fingerprint:
                            last_delta[index]=fingerprint;changed.append({'index':index,'utterance':row})
                    with (OUT/'response-deltas.jsonl').open('a',encoding='utf-8') as file:
                        file.write(json.dumps({'at':now(),'packet':record['responsePackets'],'rawPacketSha256':hashlib.sha256(data).hexdigest(),
                                               'final':final,'text':result.get('text'),'utteranceCount':len(utterances),'changed':changed},ensure_ascii=False)+'\n')
                    if final and ended.is_set():
                        write(OUT/'authoritative-final-response.json',value);return value
                raise ProbeFailure('NO_AUTHORITATIVE_POST_EOS_FINAL')
            receiving=asyncio.create_task(receive())
            try:
                with wave.open(str(AUDIO),'rb') as audio:
                    sent=0;last_saved=-1;sequence=2
                    while sent<total:
                        if pressure.low():
                            record['actualWindowsLowRam']=True;raise ProbeFailure('ACTUAL_WINDOWS_LOW_MEMORY_DURING_STREAM')
                        if receiving.done():
                            await receiving;raise ProbeFailure('PREMATURE_COMPLETION_BEFORE_ALL_AUDIO')
                        block=audio.readframes(min(1600,total-sent));assert block
                        sent+=len(block)//2;last=sent==total
                        if seed and last:ended.set()
                        await ws.send(frame(2,(2 if last else 0) if seed else 1,0,block,None if seed else sequence))
                        sequence+=1
                        record['sentFrames']=sent
                        if int(sent/16000)//10!=last_saved:
                            last_saved=int(sent/16000)//10;save()
                        await asyncio.sleep(.1)
                if not seed:
                    ended.set();await ws.send(frame(2,3,0,b'',-sequence))
                await asyncio.wait_for(receiving,60)
            finally:
                if not receiving.done():receiving.cancel();await asyncio.gather(receiving,return_exceptions=True)
        assert record['sentFrames']==total and sha(AUDIO)==EXPECTED
        record.update(state='COMPLETE_CONFIGURED_WHOLE_COMPLEX_RESPONSE_UNSCORED',finishedAt=now(),authoritativePostEosFinal=True)
    except BaseException as error:
        if last_result is not None:write(OUT/'last-partial-response.json',last_result)
        record.update(state='CONFIGURED_COMPLETE_COMPLEX_STREAM_STOPPED_RETAINED',finishedAt=now(),
                      failureType=type(error).__name__,reason=str(error) if isinstance(error,ProbeFailure) else 'See retained state; no automatic retry')
        raise
    finally:
        save();pressure.close()
        print(json.dumps({k:record.get(k) for k in ['state','sentFrames','audioSeconds','responsePackets','actualWindowsLowRam','failureType','reason']},ensure_ascii=False),flush=True)

if __name__=='__main__':
    asyncio.run(main())
