"""Fetch only all209 published train TextGrids, preserving original bytes."""
from pathlib import Path,PurePosixPath
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import hashlib,json,shutil,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from durable_model_state_20261117 import atomic_json
from alimeeting_public_oss_20261117 import PublicAliTrainingStore
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1/alimeeting-official-intake-r2')
out=E/'annotation-download-r1';out.mkdir();dest=E/'original-textgrids';assert dest.is_dir()
state={'at':datetime.now().astimezone().isoformat(),'state':'FETCHING_ORIGINAL209_TRAIN_ANNOTATIONS',
    'entries':[],'maximumMetadataBytes':64*1024**2,'maximumObjectBytes':1024**2,
    'downloadedBytes':0,'parallelRequests':2,'neuralCalls':0,'parameterUpdates':0,
    'evalOrTestFilesRequested':False,'credentialsPersistedOrPrinted':False,'automaticRetries':0}
def save():
    state.update(observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
    atomic_json(out/'state.json',state,progress=True)
pressure=SystemRamPressure();began=time.monotonic();save()
try:
    store=PublicAliTrainingStore(E/'Train_Ali_far.csv');paths=[r['Text:FILE'] for r in store.rows]
    first=json.loads((E/'first-original-textgrid-fetch-r3.json').read_text(encoding='utf-8'))
    old=Path(first['fileLocal']);assert old.exists() and hashlib.sha256(old.read_bytes()).hexdigest()==first['sha256']
    state['entries'].append({'file':first['file'],'local':str(old),'bytes':first['bytes'],'sha256':first['sha256'],
        'etag':first['etag'],'objectKey':first['objectKey'],'reusedVerifiedFirstObject':True})
    paths.remove(first['file']);todo=iter(paths)
    def fetch(path):
        raw,receipt=store.small(path,state['maximumObjectBytes'])
        assert b'TextGrid' in raw[:200] and raw.decode('utf-8-sig')
        target=dest/PurePosixPath(path).name;assert not target.exists()
        with target.open('xb') as stream:stream.write(raw)
        return {'file':path,'local':str(target),**receipt}
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending={}
        def submit():
            assert state['downloadedBytes']+(len(pending)+1)*state['maximumObjectBytes']<=state['maximumMetadataBytes'],'Metadata budget'
            path=next(todo,None)
            if path is not None:pending[executor.submit(fetch,path)]=path
        submit();submit()
        while pending:
            assert time.monotonic()-began<600,'Bounded public annotation collection deadline'
            assert not pressure.low() and shutil.disk_usage(E).free>=50*1024**3,'Original RAM/disk reserve'
            assert not(out/'stop.request').exists(),'Owned collection stop requested'
            finished,_=wait(pending,timeout=1,return_when=FIRST_COMPLETED)
            for future in finished:
                path=pending.pop(future);entry=future.result();state['entries'].append(entry)
                state['downloadedBytes']+=entry['bytes'];save();submit()
    assert len(state['entries'])==209 and {e['file'] for e in state['entries']}=={r['Text:FILE'] for r in store.rows}
    state['state']='COMPLETE_ALL209_ORIGINAL_PUBLIC_TRAIN_ANNOTATIONS_PENDING_PAIRING'
    state['elapsedSeconds']=time.monotonic()-began;save();atomic_json(out/'completed.json',state)
except BaseException as error:
    state.update(state='FAILED_ORIGINAL_TRAIN_ANNOTATION_COLLECTION_RETAINED',error=repr(error));save();raise
finally:pressure.close()
print(json.dumps({k:v for k,v in state.items() if k!='entries'},ensure_ascii=False))
