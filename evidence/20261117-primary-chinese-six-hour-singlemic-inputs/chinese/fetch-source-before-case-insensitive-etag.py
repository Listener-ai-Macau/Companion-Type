"""Fetch one published train annotation through ModelScope's public dataset API.

Temporary public-read credentials exist only in this process; never print or
persist them. OSS V1 header signing follows the provider's Python SDK.
"""
from pathlib import Path,PurePosixPath
from datetime import datetime
import base64,csv,email.utils,hashlib,hmac,json,sys,urllib.request,urllib.error,xml.etree.ElementTree as ET
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/meeting-domain-data-r1/alimeeting-official-intake-r2')
rows=list(csv.DictReader((E/'Train_Ali_far.csv').open(encoding='utf-8-sig')))
assert rows[0]['Text:FILE']=='Train_Ali_far/textgrid_dir/R0003_M0046.TextGrid'
file=rows[0]['Text:FILE'];assert '..' not in PurePosixPath(file).parts
out=E/'original-textgrids';out.mkdir(exist_ok=True);target=out/PurePosixPath(file).name;assert not target.exists()
state={'at':datetime.now().astimezone().isoformat(),'state':'PUBLIC_OFFICIAL_TRAIN_TEXTGRID_FETCH',
    'sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'file':file,
    'maximumBytes':1024**2,'attempts':[],'evalOrTestPayloadRead':False,'credentialsPersistedOrPrinted':False,
    'newNeuralCalls':0,'parameterUpdates':0,'trainingAdmitted':False}
def save():atomic_json(E/'first-original-textgrid-fetch-legacy-root-r2.json',state,progress=True)
def request(cfg,key,method):
    date=email.utils.formatdate(usegmt=True);token=cfg['SecurityToken']
    resource='/'+cfg['Bucket']+'/'+key
    message=method+'\n\n\n'+date+'\nx-oss-security-token:'+token+'\n'+resource
    signature=base64.b64encode(hmac.new(cfg['AccessSecret'].encode(),message.encode(),hashlib.sha1).digest()).decode()
    url='https://'+cfg['Bucket']+'.'+cfg['Region']+'.aliyuncs.com/'+urllib.parse.quote(key,safe='/')
    headers={'Date':date,'x-oss-security-token':token,'Authorization':'OSS '+cfg['AccessId']+':'+signature,
        'User-Agent':'Companion-public-training-intake/1.0'}
    return urllib.request.urlopen(urllib.request.Request(url,headers=headers,method=method),timeout=20)
save()
try:
    url='https://www.modelscope.cn/api/v1/datasets/modelscope/AliMeeting/ststoken?Revision=master'
    with urllib.request.urlopen(url,timeout=20) as r:envelope=json.loads(r.read(256*1024))
    assert envelope['Code']==200;cfg=envelope['Data']
    state['publicLocation']={k:cfg[k] for k in ['Bucket','Region','Dir','BackupDir']};save()
    state['legacyRootEvidence']='https://github.com/modelscope/modelscope_hub/blob/5810c09aa0c8b5f8348a5c53bdc831099228d9ad/src/modelscope_hub/compat/hub_api.py#L1368'
    for root in ['public-unzipped/modelscope_AliMeeting_Train_Ali_far']:
        key=root.rstrip('/')+'/'+file;item={'objectKey':key,'method':'HEAD'};state['attempts'].append(item)
        try:
            with request(cfg,key,'HEAD') as r:
                size=int(r.headers['Content-Length']);item.update(status=r.status,bytes=size,etag=r.headers.get('ETag'))
            assert 0<size<=state['maximumBytes'],'Unexpected training annotation size'
            with request(cfg,key,'GET') as r:
                raw=r.read(state['maximumBytes']+1);assert len(raw)==size
                etag=r.headers.get('ETag','').strip('"')
            if len(etag)==32:assert hashlib.md5(raw).hexdigest()==etag,'OSS annotation content checksum differs'
            assert b'TextGrid' in raw[:200] or 'TextGrid' in raw.decode('utf-8-sig')[:200]
            target.write_bytes(raw)
            state.update(state='COMPLETE_ORIGINAL_PUBLIC_TRAIN_TEXTGRID_DOWNLOADED',fileLocal=str(target),bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),etag=etag,objectKey=key)
            break
        except urllib.error.HTTPError as error:
            item['status']=error.code
            # Error XML may echo signed headers; retain only its public Code.
            body=error.read(64*1024)
            try:item['ossErrorCode']=ET.fromstring(body).findtext('Code')
            except ET.ParseError:item['ossErrorCode']='unparsed'
            save()
            if error.code!=404:raise RuntimeError('Public train object request denied/failed; see sanitized status') from None
    else:raise FileNotFoundError('Published train object absent from both provider-declared prefixes')
except BaseException as error:state.update(state='FAILED_OFFICIAL_TRAIN_TEXTGRID_FETCH_RETAINED_NO_RETRY',error=repr(error));save();raise
save();print(json.dumps(state,ensure_ascii=False))
