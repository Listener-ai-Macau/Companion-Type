"""Resume the owned public download in four verified non-overlapping ranges."""
from pathlib import Path
from datetime import datetime
import concurrent.futures,hashlib,json,os,psutil,urllib.request
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-native-r1';E=Path('E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107/model').resolve()
target=C/'download-range-receipt.json';assert not target.exists()
script=Path(__file__).with_name('prepare_practical_qwen_native_20261107.py').resolve()
owned=[]
for p in psutil.process_iter(['cmdline']):
    try:
        cmd=p.info['cmdline'] or []
        if len(cmd)>1 and Path(cmd[1]).resolve()==script:owned.append(p)
    except (psutil.Error,OSError,ValueError):pass
assert len(owned)==1,'Need the uniquely identified original owned preparer, not an arbitrary PID'
owned[0].terminate();owned[0].wait(timeout=5)
part=E/'model.safetensors.part';dest=E/'model.safetensors';assert part.is_file() and not dest.exists()
model='Qwen/Qwen3-ASR-0.6B-hf';rev='7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c'
data=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+model+'/revision/'+rev+'?blobs=true',timeout=30));assert data['sha']==rev
row=next(r for r in data['siblings'] if r['rfilename']=='model.safetensors');size=row['size'];digest=row['lfs']['sha256'];prefix=part.stat().st_size;assert 0<prefix<size
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
record={'at':now(),'state':'RESUMING_OWNED_PUBLIC_DOWNLOAD_VERIFIED_RANGES','terminatedOwnPreparerPid':owned[0].pid,'reason':'Reuse the existing prefix; four bounded network streams after a successful206range probe, no proxy/routing changes. This is download preparation, not a model failure or inference.','revision':rev,'prefixBytesPreserved':prefix,'prefixSha256':sha(part),'expectedBytes':size,'expectedSha256':digest,'inferenceStarted':False}
atomic_json(target,record)
url='https://huggingface.co/'+model+'/resolve/'+rev+'/model.safetensors?download=true'
width=(size-prefix+3)//4
def fetch(index):
    start=prefix+index*width;end=min(size,start+width)-1;path=E/('qwen-model-range-%d.part'%index);assert not path.exists()
    headers={'Range':f'bytes={start}-{end}','User-Agent':'Companion-public-native-model-control'}
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=45) as response:
        assert response.status==206 and response.headers['Content-Range']==f'bytes {start}-{end}/{size}','Server did not honor the exact independent range'
        remaining=end-start+1
        with path.open('xb') as stream:
            while remaining:
                chunk=response.read(min(1024*1024,remaining));assert chunk,'Incomplete range response';stream.write(chunk);remaining-=len(chunk)
            stream.flush();os.fsync(stream.fileno())
    return {'index':index,'start':start,'end':end,'bytes':path.stat().st_size,'sha256':sha(path),'path':str(path)}
try:
    pieces=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(fetch,i) for i in range(4)]
        for future in concurrent.futures.as_completed(futures):
            pieces.append(future.result());record['completedRanges']=pieces;atomic_json(target,record)
    pieces.sort(key=lambda p:p['start']);assert pieces[0]['start']==prefix and pieces[-1]['end']==size-1 and all(a['end']+1==b['start'] for a,b in zip(pieces,pieces[1:]))
    assembled=E/'model.safetensors.assembled.part';assert not assembled.exists()
    with assembled.open('xb') as stream:
        for p in [part]+[Path(piece['path']) for piece in pieces]:
            with p.open('rb') as source:
                while True:
                    chunk=source.read(1024*1024)
                    if not chunk:break
                    stream.write(chunk)
        stream.flush();os.fsync(stream.fileno())
    assert assembled.stat().st_size==size and sha(assembled)==digest
    assert not dest.exists();os.replace(assembled,dest)
    # Delete only redundant verified public transfer fragments, never model
    # evidence/user data/unknown directories. Complete weights remain intact.
    for p in [part]+[Path(piece['path']) for piece in pieces]:
        assert p.resolve().parent==E and p.suffix=='.part';p.unlink()
    record.update(state='COMPLETE_PINNED_PUBLIC_WEIGHTS_SHA256_VERIFIED',finishedAt=now(),finalFile=str(dest),finalSha256=digest,redundantVerifiedFragmentsRemoved=True)
except BaseException as error:
    record.update(state='PUBLIC_RANGE_PREPARATION_FAILED_FRAGMENTS_RETAINED',error=repr(error),finishedAt=now());raise
finally:
    atomic_json(target,record);print(json.dumps(record),flush=True)
