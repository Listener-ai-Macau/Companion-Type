"""Bounded-memory byte-range recovery. Final full published hash is mandatory."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
import requests,json,hashlib,time,psutil,threading,shutil,os
root=Path('C:/Users/Billy/Desktop/Denzic/Companion');proof=root/'docs/handoffs/20261105-model-resume'
cache=Path('E:/CodexData/Companion/asr-accuracy-latency-20261103/multispeaker-ai/joint-moss-architecture-20261104/model')
target=cache/'model-00000-of-00001.safetensors';prefix=target.with_suffix('.part');parts=cache/'weight-ranges-20261105';parts.mkdir(exist_ok=True)
total=1817113576;expected='9a0ceb4ab7330357db3ff583dba8d83625d5b733b00e1d55d6970e11b07026c4'
url='https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize/resolve/10304d926740cf5a5cee05a268086e3265197910/'+target.name
receipt=proof/'weights-range-restore.json';assert not receipt.exists() and not target.exists()
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);allowed=psutil.Process().cpu_affinity();psutil.Process().cpu_affinity(allowed[-2:])
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
start=prefix.stat().st_size if prefix.exists() else 0
state={'at':now(),'state':'RESUMING_PINNED_WEIGHTS_BY_EXACT_RANGES','pid':os.getpid(),'expectedBytes':total,'reusedPrefixBytes':start,'downloadedBytes':start,'completedRanges':0,
    'downloadWorkers':6,'bufferBytesPerWorker':1024**2,'modelLoaded':False,'systemMemoryStart':psutil.virtual_memory().available,'failures':[]}
def save():
    tmp=receipt.with_suffix('.tmp');tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8');tmp.replace(receipt)
save();begin=time.perf_counter()
def one(span):
    a,b=span;dest=parts/f'{a:012d}-{b:012d}.part';length=b-a+1
    if dest.exists() and dest.stat().st_size==length:return a,b,dest,True
    existing=dest.stat().st_size if dest.exists() else 0;assert existing<length
    session=requests.Session();session.trust_env=False
    for attempt in range(3):
        offset=dest.stat().st_size if dest.exists() else 0
        if offset==length:return a,b,dest,True
        try:
            with session.get(url,headers={'Range':f'bytes={a+offset}-{b}'},stream=True,timeout=(20,60)) as response:
                response.raise_for_status();assert response.status_code==206
                assert response.headers.get('Content-Range')==f'bytes {a+offset}-{b}/{total}'
                with dest.open('ab' if offset else 'wb') as out:
                    for block in response.iter_content(1024**2):
                        if block:out.write(block)
            assert dest.stat().st_size==length;return a,b,dest,False
        except Exception:
            if attempt==2:raise
    raise RuntimeError('Range failed')
try:
    spans=[(a,min(total-1,a+8*1024**2-1)) for a in range(start,total,8*1024**2)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(one,span):span for span in spans}
        for future in as_completed(futures):
            try:
                a,b,_,reused=future.result();state['completedRanges']+=1;state['downloadedBytes']+=b-a+1
                state.update(state='DOWNLOADING_HASH_GUARDED_PUBLIC_WEIGHT_RANGES',availableSystemMemory=psutil.virtual_memory().available);save()
            except BaseException as error:
                state['failures'].append({'range':futures[future],'error':repr(error)});save();raise
    state.update(state='ASSEMBLING_AND_VERIFYING_FULL_PUBLISHED_SHA256');save()
    assembled=target.with_suffix('.assembled');assert not assembled.exists()
    digest=hashlib.sha256();count=0
    with assembled.open('xb') as output:
        sources=([prefix] if start else [])+[parts/f'{a:012d}-{b:012d}.part' for a,b in spans]
        for source in sources:
            with source.open('rb') as inp:
                while block:=inp.read(1024**2):output.write(block);digest.update(block);count+=len(block)
        output.flush();os.fsync(output.fileno())
    assert count==total and digest.hexdigest()==expected
    assembled.replace(target)
    state.update(state='PUBLISHED_PINNED_WEIGHTS_RESTORED_FULL_SHA_VERIFIED',sha256=expected,bytes=total,modelLoaded=False)
except BaseException as error:
    state.update(state='RANGE_WEIGHT_RECOVERY_FAILURE_RETAINED',error=repr(error));raise
finally:
    state.update(finishedAt=now(),wallSeconds=round(time.perf_counter()-begin,3),systemMemoryEnd=psutil.virtual_memory().available);save();print(json.dumps(state,ensure_ascii=False),flush=True)
