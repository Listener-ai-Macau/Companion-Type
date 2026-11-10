"""Bounded read-only verification of an already uploaded private draft asset.

Authentication stays in memory at api.github.com; CDN range reads carry no
GitHub credential. Four small buffers, one immutable asset, final full SHA256.
"""
from pathlib import Path
import concurrent.futures,hashlib,json,re,subprocess,time,urllib.request,urllib.error,urllib.parse,socket,threading

def command(args):
 p=subprocess.run(args,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
 if p.returncode:raise RuntimeError('GitHub readback command failed')
 return p.stdout

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args):return None

def location(repo,asset,kind='release'):
 assert re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo) and str(asset).isdigit()
 assert kind in ['release','artifact'];endpoint='releases/assets/'+str(asset) if kind=='release' else 'actions/artifacts/'+str(asset)+'/zip'
 token=command(['gh','auth','token']).decode().strip()
 request=urllib.request.Request('https://api.github.com/repos/'+repo+'/'+endpoint,headers={'Authorization':'Bearer '+token,'Accept':'application/octet-stream' if kind=='release' else 'application/vnd.github+json','User-Agent':'Companion-candidate-readback'})
 try:
  with urllib.request.build_opener(NoRedirect()).open(request,timeout=30):return None
 except urllib.error.HTTPError as error:
  if error.code not in [301,302,303,307,308]:raise RuntimeError('GitHub asset redirect unavailable: HTTP '+str(error.code)) from None
  url=error.headers.get('Location');error.close()
 parsed=urllib.parse.urlsplit(url or '')
 allowed=parsed.hostname in ['release-assets.githubusercontent.com','objects.githubusercontent.com'] or kind=='artifact' and (parsed.hostname or '').endswith('.blob.core.windows.net')
 if parsed.scheme!='https' or not allowed:return None
 return url

def download(repo,asset,destination,expected_bytes,expected_sha,kind='release'):
 destination=Path(destination);assert expected_bytes>0 and re.fullmatch('[0-9a-f]{64}',expected_sha);destination.parent.mkdir(parents=True,exist_ok=True)
 def digest():
  with destination.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
 if destination.exists() and destination.stat().st_size==expected_bytes and digest()==expected_sha:return {'method':'reuse-already-readback-identical-bytes','bytes':expected_bytes,'sha256':expected_sha}
 started=time.monotonic();url=location(repo,asset,kind);supported=False
 if url:
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'Range':'bytes=0-0'}),timeout=30) as response:
    supported=response.status==206 and response.headers.get('Content-Range')=='bytes 0-0/'+str(expected_bytes) and len(response.read(2))==1
  except Exception:supported=False
 if supported:
  with destination.open('wb') as out:out.truncate(expected_bytes)
  size=4*1024*1024;sections=[(start,min(expected_bytes-1,start+size-1)) for start in range(0,expected_bytes,size)]
  failures=[];failure_lock=threading.Lock()
  def section(bounds):
   start,end=bounds
   for attempt in range(2):
    received=0
    try:
     request=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}'})
     with urllib.request.urlopen(request,timeout=45) as response,destination.open('r+b') as out:
      if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{expected_bytes}':raise RuntimeError('Range identity mismatch')
      out.seek(start);remaining=end-start+1
      while remaining:
       chunk=response.read(min(128*1024,remaining))
       if not chunk:raise RuntimeError('Incomplete range')
       out.write(chunk);remaining-=len(chunk);received+=len(chunk)
      if response.read(1):raise RuntimeError('Overlong range')
     return
    except Exception as error:
     status=getattr(error,'code',None);safe={'start':start,'end':end,'attempt':attempt+1,'received':received,'exceptionClass':type(error).__name__,'httpStatus':status,'reason':str(error) if isinstance(error,RuntimeError) else None}
     with failure_lock:failures.append(safe)
     retry=isinstance(error,(TimeoutError,socket.timeout,ConnectionError,urllib.error.URLError)) and (status is None or status in [429,500,502,503,504])
     if attempt==0 and retry:continue
     destination.with_suffix(destination.suffix+'.failure.json').write_text(json.dumps({'assetId':asset,'failures':failures},indent=2)+'\n')
     raise RuntimeError(f'Private asset range {start}-{end} failed ({safe["exceptionClass"]}, status={status}, bytes={received}); sanitized diagnostics retained') from None
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(section,sections))
  method='four-bounded-official-CDN-range-readers'
 else:
  endpoint='releases/assets/'+str(asset) if kind=='release' else 'actions/artifacts/'+str(asset)+'/zip'
  accept='application/octet-stream' if kind=='release' else 'application/vnd.github+json'
  with destination.open('wb') as out:p=subprocess.run(['gh','api','repos/'+repo+'/'+endpoint,'-H','Accept: '+accept],stdout=out,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
  if p.returncode:raise RuntimeError('Private asset sequential readback failed')
  sections=[];method='official-gh-sequential-fallback'
 if destination.stat().st_size!=expected_bytes or digest()!=expected_sha:raise RuntimeError('Full private asset readback SHA256 mismatch; retained for investigation')
 return {'method':method,'workers':4 if supported else 1,'sections':len(sections),'bufferBytesPerWorker':128*1024 if supported else None,'bytes':expected_bytes,'sha256':expected_sha,'seconds':time.monotonic()-started,'retainedTransientReads':failures if supported else [],'authSentOnlyToGitHubApi':True,'signedUrlOrTokenPersisted':False,'routingModified':False}
