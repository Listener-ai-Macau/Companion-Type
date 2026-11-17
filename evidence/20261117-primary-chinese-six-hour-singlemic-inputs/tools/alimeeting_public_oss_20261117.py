"""Read only allow-listed public AliMeeting train objects via its documented API.

Signing follows aliyun/aliyun-oss-python-sdk oss2/auth.py. Credentials remain
in memory, are never logged, and are never forwarded through redirects.
"""
from pathlib import Path,PurePosixPath
import base64,csv,email.utils,hashlib,hmac,json,re,threading,urllib.request,urllib.error,xml.etree.ElementTree as ET

class PublicObjectError(RuntimeError):
    def __init__(self,status,code):
        self.status=status;self.code=code
        super().__init__('Public training object HTTP '+str(status)+' '+str(code))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

class PublicAliTrainingStore:
    ROOT='public-unzipped/modelscope_AliMeeting_Train_Ali_far'
    API='https://www.modelscope.cn/api/v1/datasets/modelscope/AliMeeting/ststoken?Revision=master'
    def __init__(self,csv_file):
        p=Path(csv_file)
        assert hashlib.sha256(p.read_bytes()).hexdigest()=='c03b65362f703f14aa1adae94cb025f558dc3ce80119a5877ab9d0e317f5a38c'
        self.rows=list(csv.DictReader(p.open(encoding='utf-8-sig')))
        assert len(self.rows)==209
        self.allowed={v for r in self.rows for v in r.values()}
        with urllib.request.urlopen(self.API,timeout=20) as r:envelope=json.loads(r.read(256*1024))
        assert envelope['Code']==200;self._cfg=envelope['Data']
        assert self._cfg['Bucket']=='dataset-hub' and self._cfg['Region']=='oss-cn-hangzhou'
        self._local=threading.local()
    def open(self,path,*,method='GET',byte_range=None):
        assert path in self.allowed and '..' not in PurePosixPath(path).parts
        assert method in ('GET','HEAD');cfg=self._cfg;key=self.ROOT+'/'+path
        date=email.utils.formatdate(usegmt=True)
        message=method+'\n\n\n'+date+'\nx-oss-security-token:'+cfg['SecurityToken']+'\n/'+cfg['Bucket']+'/'+key
        signature=base64.b64encode(hmac.new(cfg['AccessSecret'].encode(),message.encode(),hashlib.sha1).digest()).decode()
        url='https://'+cfg['Bucket']+'.'+cfg['Region']+'.aliyuncs.com/'+urllib.parse.quote(key,safe='/')
        request=urllib.request.Request(url,headers={'Date':date,'User-Agent':'Companion-public-training-intake/1.0'},method=method)
        request.add_unredirected_header('x-oss-security-token',cfg['SecurityToken'])
        request.add_unredirected_header('Authorization','OSS '+cfg['AccessId']+':'+signature)
        if byte_range is not None:
            first,last=byte_range;assert 0<=first<=last;request.add_header('Range',f'bytes={first}-{last}')
        try:return urllib.request.build_opener(NoRedirect()).open(request,timeout=20)
        except urllib.error.HTTPError as error:
            try:code=ET.fromstring(error.read(64*1024)).findtext('Code')
            except ET.ParseError:code='unparsed'
            raise PublicObjectError(error.code,code) from None
    def head(self,path):
        with self.open(path,method='HEAD') as r:
            return {'bytes':int(r.headers['Content-Length']),'etag':r.headers.get('ETag','').strip('"'),
                'lastModified':r.headers.get('Last-Modified'),'objectKey':self.ROOT+'/'+path}
    def range_bytes(self,path,first,last,object_bytes,etag):
        """Reuse one HTTPS connection per IO thread; no retries or redirects."""
        assert path in self.allowed and 0<=first<=last<object_bytes and last-first+1<=30*16000*16
        if not hasattr(self._local,'session'):
            # Reuse the installed pure-Python HTTP client; no Torch import or
            # shared-runtime installation. Existing clean packages stay first.
            import sys
            site=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages')
            sys.path.append(str(site));import requests
            session=requests.Session()
            session.mount('https://',requests.adapters.HTTPAdapter(pool_connections=1,pool_maxsize=1,max_retries=0,pool_block=True))
            self._local.session=session
        cfg=self._cfg;key=self.ROOT+'/'+path;date=email.utils.formatdate(usegmt=True)
        message='GET\n\n\n'+date+'\nx-oss-security-token:'+cfg['SecurityToken']+'\n/'+cfg['Bucket']+'/'+key
        signature=base64.b64encode(hmac.new(cfg['AccessSecret'].encode(),message.encode(),hashlib.sha1).digest()).decode()
        url='https://'+cfg['Bucket']+'.'+cfg['Region']+'.aliyuncs.com/'+urllib.parse.quote(key,safe='/')
        headers={'Date':date,'x-oss-security-token':cfg['SecurityToken'],'Authorization':'OSS '+cfg['AccessId']+':'+signature,
            'Range':f'bytes={first}-{last}','If-Match':'"'+etag+'"','Accept-Encoding':'identity',
            'User-Agent':'Companion-public-training-intake/1.0'}
        with self._local.session.get(url,headers=headers,stream=True,allow_redirects=False,timeout=(10,20)) as response:
            if response.status_code!=206:
                try:code=ET.fromstring(response.raw.read(64*1024)).findtext('Code')
                except ET.ParseError:code='unparsed'
                raise PublicObjectError(response.status_code,code)
            assert response.headers.get('Content-Encoding') in (None,'identity')
            assert response.headers['Content-Range']==f'bytes {first}-{last}/{object_bytes}'
            assert response.headers['ETag'].strip('"').lower()==etag.lower(),'Pinned original source object changed'
            expected=last-first+1;assert int(response.headers['Content-Length'])==expected
            raw=response.raw.read(expected+1,decode_content=False);assert len(raw)==expected,'Truncated original PCM range'
            return raw
    def small(self,path,maximum):
        with self.open(path) as r:
            expected=int(r.headers['Content-Length']);assert 0<expected<=maximum
            raw=r.read(maximum+1);assert len(raw)==expected
            etag=r.headers.get('ETag','').strip('"')
        assert re.fullmatch(r'[0-9a-fA-F]{32}',etag),'Require a whole-object content MD5'
        assert hashlib.md5(raw).hexdigest()==etag.lower(),'Whole-object MD5 differs'
        return raw,{'bytes':len(raw),'etag':etag,'sha256':hashlib.sha256(raw).hexdigest(),'objectKey':self.ROOT+'/'+path}
