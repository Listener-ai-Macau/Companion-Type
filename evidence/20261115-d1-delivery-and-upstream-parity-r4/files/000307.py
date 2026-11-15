"""Four bounded public transfer ranges; preserve and resume partial fragments."""
from pathlib import Path
from datetime import datetime
import argparse,concurrent.futures,hashlib,json,os,threading,time,urllib.request
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');a=p.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-native17-r5'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));N=read(C/'native-protocol.json')
E=Path(N['modelRoot']).resolve();row=next(f for f in N['files'] if Path(f['file']).name=='model.safetensors')
size=row['bytes'];expected=row['sha256'];dest=E/'model.safetensors';assert not dest.exists()
target=C/'download-range-receipt.json';assert a.resume==target.exists()
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
prior=read(target) if target.exists() else None
if prior:atomic_json(C/('download-prior-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json'),prior)
state={'state':'DOWNLOADING_PINNED_NATIVE17_PUBLIC_WEIGHTS','at':now(),'pid':os.getpid(),'revision':N['revision'],
  'expectedBytes':size,'expectedSha256':expected,'inferenceStarted':False,'modelWeightsReady':False,'ranges':[]}
lock=threading.Lock();width=(size+3)//4
atomic_json(target,state)
def fetch(index):
    lo=index*width;hi=min(size,lo+width)-1;file=E/('native17-range-%d.part'%index)
    assert file.resolve().parent==E
    prefix=file.stat().st_size if file.exists() else 0;assert 0<=prefix<=hi-lo+1
    if prefix and not a.resume:raise RuntimeError('Existing public fragment requires explicit resume')
    if prefix<hi-lo+1:
        start=lo+prefix;url='https://huggingface.co/'+N['modelId']+'/resolve/'+N['revision']+'/model.safetensors?download=true&companion_range='+str(index)+'-'+str(start)
        request=urllib.request.Request(url,headers={'Range':f'bytes={start}-{hi}','User-Agent':'Companion-public-native-checkpoint-control'})
        with urllib.request.urlopen(request,timeout=45) as response:
            assert response.status==206 and response.headers['Content-Range']==f'bytes {start}-{hi}/{size}'
            remaining=hi-start+1
            with file.open('ab' if prefix else 'xb') as stream:
                while remaining:
                    chunk=response.read(min(1024*1024,remaining));assert chunk
                    stream.write(chunk);remaining-=len(chunk)
                stream.flush();os.fsync(stream.fileno())
    assert file.stat().st_size==hi-lo+1
    result={'index':index,'start':lo,'end':hi,'bytes':file.stat().st_size,'resumedPrefixBytes':prefix,'sha256':sha(file),'path':str(file)}
    with lock:state['ranges'].append(result);atomic_json(target,state)
    return result
try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:pieces=list(pool.map(fetch,range(4)))
    pieces.sort(key=lambda p:p['start']);assert pieces[0]['start']==0 and pieces[-1]['end']==size-1 and all(a['end']+1==b['start'] for a,b in zip(pieces,pieces[1:]))
    assembled=E/'native17-assembled.part';assert not assembled.exists()
    state['state']='VERIFYING_ASSEMBLED_NATIVE17_WEIGHTS';atomic_json(target,state)
    with assembled.open('xb') as output:
        for piece in pieces:
            with Path(piece['path']).open('rb') as stream:
                while True:
                    chunk=stream.read(1024*1024)
                    if not chunk:break
                    output.write(chunk)
        output.flush();os.fsync(output.fileno())
    assert assembled.stat().st_size==size and sha(assembled)==expected
    os.replace(assembled,dest)
    for piece in pieces:
        file=Path(piece['path']);assert file.resolve().parent==E and file.suffix=='.part';file.unlink()
    for file in N['files']:assert Path(file['file']).stat().st_size==file['bytes'] and sha(file['file'])==file['sha256']
    state.update(state='COMPLETE_PINNED_PUBLIC_WEIGHTS_SHA256_VERIFIED',modelWeightsReady=True,finishedAt=now(),limits=limits.query(),redundantVerifiedFragmentsRemoved=True)
    atomic_json(C/'model-ready.json',{'state':'PINNED_NATIVE17_ALL_FILES_VERIFIED_NO_INFERENCE','at':now(),'nativeProtocolSha256':sha(C/'native-protocol.json'),'weightSha256':expected,'inferenceStarted':False,'qualityQualified':False})
except BaseException as error:
    state.update(state='PUBLIC_RANGE_DOWNLOAD_FAILED_FRAGMENTS_RETAINED',error=repr(error),finishedAt=now());raise
finally:atomic_json(target,state);print(json.dumps(state),flush=True)
