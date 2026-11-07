"""Pin one public native forced-aligner; bounded transfer is not inference."""
from pathlib import Path
from datetime import datetime
import argparse,concurrent.futures,hashlib,json,os,shutil,threading,urllib.request
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure

parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');args=parser.parse_args()
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery'
C=B/'practical-alignment-r1'; E=Path('E:/CodexData/Companion/.model-cache/qwen-native-aligner-20261107/model').resolve()
model='Qwen/Qwen3-ForcedAligner-0.6B-hf';revision='c07281df297b9905d24a508279258cccf987a064'
C.mkdir(exist_ok=True);E.mkdir(parents=True,exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2);pressure=SystemRamPressure()
target=C/'preparation.json';assert args.resume==target.exists()
if target.exists():
    assert read(target)['state']!='PINNED_NATIVE_ALIGNER_READY_NO_INFERENCE'
    archive=C/('preparation-prior-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    archive.write_bytes(target.read_bytes())
state={'at':now(),'state':'PREPARING_PINNED_PUBLIC_ALIGNER_NO_INFERENCE','modelId':model,'revision':revision,'inferenceStarted':False,'qualityQualified':False,'ranges':[]}
atomic_json(target,state);lock=threading.Lock()
try:
    assert not pressure.low(),'Actual low-memory signal: defer transfer, retain files'
    api='https://huggingface.co/api/models/'+model+'/revision/'+revision+'?blobs=true'
    data=json.load(urllib.request.urlopen(api,timeout=30));assert data['sha']==revision
    atomic_json(C/'checkpoint-source.json',data)
    files=[]
    for item in data['siblings']:
        name=item['rfilename']
        if name=='.gitattributes':continue
        assert name in ['README.md','chat_template.jinja','config.json','model.safetensors','processor_config.json','tokenizer.json','tokenizer_config.json']
        dest=E/name;size=item['size'];expected=item.get('lfs',{}).get('sha256')
        if name=='model.safetensors':
            files.append({'file':str(dest),'bytes':size,'sha256':expected});continue
        if not dest.exists():
            previous=Path('E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107/model')/name
            if expected and previous.exists() and sha(previous)==expected:shutil.copyfile(previous,dest)
            else:
                url='https://huggingface.co/'+model+'/resolve/'+revision+'/'+name+'?download=true'
                part=dest.with_suffix(dest.suffix+'.part');assert not part.exists(),'Retain partial metadata rather than overwrite'
                with urllib.request.urlopen(url,timeout=30) as response,part.open('xb') as stream:
                    while chunk:=response.read(1024*1024):stream.write(chunk)
                os.replace(part,dest)
        assert dest.stat().st_size==size
        if expected:assert sha(dest)==expected
        else:assert hashlib.sha1(b'blob '+str(size).encode()+b'\0'+dest.read_bytes()).hexdigest()==item['blobId']
        files.append({'file':str(dest),'bytes':size,'sha256':sha(dest)})
    row=next(f for f in files if Path(f['file']).name=='model.safetensors')
    size=row['bytes'];dest=Path(row['file']);width=(size+3)//4
    assert shutil.disk_usage(E).free>=size*2+256*1024**2
    def fetch(index):
        lo=index*width;hi=min(size,lo+width)-1;file=E/('aligner-range-%d.part'%index)
        prefix=file.stat().st_size if file.exists() else 0;assert 0<=prefix<=hi-lo+1
        assert not prefix or args.resume
        if prefix<hi-lo+1:
            start=lo+prefix
            url='https://huggingface.co/'+model+'/resolve/'+revision+'/model.safetensors?download=true&companion_range='+str(index)+'-'+str(start)
            request=urllib.request.Request(url,headers={'Range':f'bytes={start}-{hi}','User-Agent':'Companion-public-forced-alignment-control'})
            with urllib.request.urlopen(request,timeout=45) as response:
                assert response.status==206 and response.headers['Content-Range']==f'bytes {start}-{hi}/{size}'
                remaining=hi-start+1
                with file.open('ab' if prefix else 'xb') as stream:
                    while remaining:
                        assert not pressure.low(),'Actual low-memory signal: retain partial transfer'
                        chunk=response.read(min(1024*1024,remaining));assert chunk
                        stream.write(chunk);remaining-=len(chunk)
                    stream.flush();os.fsync(stream.fileno())
        assert file.stat().st_size==hi-lo+1
        result={'index':index,'start':lo,'end':hi,'bytes':file.stat().st_size,'resumedPrefixBytes':prefix,'sha256':sha(file),'path':str(file)}
        with lock:state['ranges'].append(result);atomic_json(target,state)
        return result
    if not dest.exists():
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:pieces=list(pool.map(fetch,range(4)))
        pieces.sort(key=lambda r:r['start'])
        assert pieces[0]['start']==0 and pieces[-1]['end']==size-1 and all(a['end']+1==b['start'] for a,b in zip(pieces,pieces[1:]))
        assembled=E/'aligner-assembled.part';assert not assembled.exists()
        with assembled.open('xb') as output:
            for piece in pieces:
                with Path(piece['path']).open('rb') as stream:
                    while chunk:=stream.read(1024*1024):output.write(chunk)
            output.flush();os.fsync(output.fileno())
        assert assembled.stat().st_size==size and sha(assembled)==row['sha256']
        os.replace(assembled,dest)
        for piece in pieces:
            file=Path(piece['path']);assert file.resolve().parent==E and file.suffix=='.part';file.unlink()
    for file in files:assert Path(file['file']).stat().st_size==file['bytes'] and sha(file['file'])==file['sha256']
    config=read(E/'config.json')
    assert config['architectures']==['Qwen3ASRForTokenClassification'] and config['model_type']=='qwen3_asr'
    atomic_json(C/'model-source.json',{'modelId':model,'revision':revision,'modelRoot':str(E),'files':files,'architecture':config['architectures'],'commercialLicense':'Apache-2.0','sourceCardUrl':'https://huggingface.co/'+model,'referenceNeverPassed':True,'qualityQualified':False})
    state.update(state='PINNED_NATIVE_ALIGNER_READY_NO_INFERENCE',finishedAt=now(),weightBytes=size,weightSha256=row['sha256'],limits=limits.query(),sourceSha256=sha(__file__),scope='Download and source verification only. No true word timestamps, person attribution, overlap separation or lower CER established.')
except BaseException as error:
    state.update(state='ALIGNER_PREPARATION_FAILED_FILES_RETAINED',error=repr(error),finishedAt=now());raise
finally:
    pressure.close();atomic_json(target,state);print(json.dumps(state),flush=True)
