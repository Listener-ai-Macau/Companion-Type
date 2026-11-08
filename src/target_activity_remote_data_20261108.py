"""Bounded immutable HTTP byte-range reader for public lossless meeting files."""
from pathlib import Path
import io,hashlib,json,urllib.request,time

class PublicRangeFile(io.RawIOBase):
    def __init__(self,url,size,cache,*,block_bytes=262144,max_download_bytes=64*1024**2):
        self.url=url;self.size=size;self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True);self.position=0;self.block_bytes=block_bytes;self.max_download_bytes=max_download_bytes;self.downloaded=0;self.receipts=[]
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        position=offset if whence==0 else self.position+offset if whence==1 else self.size+offset
        if position<0:raise ValueError('Negative source seek')
        self.position=position;return position
    def read(self,size=-1):
        if size<0:size=self.size-self.position
        size=max(0,min(size,self.size-self.position));out=[]
        while size:
            index=self.position//self.block_bytes;lo=index*self.block_bytes;hi=min(self.size,lo+self.block_bytes)-1;path=self.cache/('%012d.bin'%lo)
            if path.exists():raw=path.read_bytes()
            else:
                assert self.downloaded+hi-lo+1<=self.max_download_bytes,'Bounded public source download budget reached; no full-archive fallback'
                req=urllib.request.Request(self.url,headers={'Range':'bytes=%d-%d'%(lo,hi),'User-Agent':'Companion-bounded-real-meeting-preparation'})
                started=time.perf_counter()
                with urllib.request.urlopen(req,timeout=20) as response:
                    assert response.status==206 and response.headers.get('Content-Range','').startswith('bytes %d-%d/'%(lo,hi)),'Require exact immutable source byte range'
                    raw=response.read(hi-lo+2);assert len(raw)==hi-lo+1
                path.write_bytes(raw);self.downloaded+=len(raw);self.receipts.append({'start':lo,'endInclusive':hi,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'seconds':time.perf_counter()-started})
            assert len(raw)==hi-lo+1
            start=self.position-lo;piece=raw[start:start+size];assert piece;out.append(piece);self.position+=len(piece);size-=len(piece)
        return b''.join(out)
    def readinto(self,buffer):
        raw=self.read(len(buffer));buffer[:len(raw)]=raw;return len(raw)

def public_json(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-public-data-provenance'}),timeout=20) as response:return json.load(response)
