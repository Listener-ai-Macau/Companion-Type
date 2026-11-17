"""Read only allow-listed public AliMeeting train objects via its documented API.

Signing follows aliyun/aliyun-oss-python-sdk oss2/auth.py. Credentials remain
in memory, are never logged, and are never forwarded through redirects.
"""
from pathlib import Path,PurePosixPath
import base64,csv,email.utils,hashlib,hmac,json,re,urllib.request,urllib.error,xml.etree.ElementTree as ET

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
    def small(self,path,maximum):
        with self.open(path) as r:
            expected=int(r.headers['Content-Length']);assert 0<expected<=maximum
            raw=r.read(maximum+1);assert len(raw)==expected
            etag=r.headers.get('ETag','').strip('"')
        assert re.fullmatch(r'[0-9a-fA-F]{32}',etag),'Require a whole-object content MD5'
        assert hashlib.md5(raw).hexdigest()==etag.lower(),'Whole-object MD5 differs'
        return raw,{'bytes':len(raw),'etag':etag,'sha256':hashlib.sha256(raw).hexdigest(),'objectKey':self.ROOT+'/'+path}
