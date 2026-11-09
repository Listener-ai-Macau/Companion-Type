"""Pin one maintained complete AED2 CPU challenger, never confuse it with CTC/v1."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,sys,time,urllib.request,tarfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261109-firered2-cpu-r1';CACHE=Path('E:/CodexData/Companion/.model-cache/firered2-aed-20261109');C.mkdir(exist_ok=False);CACHE.mkdir(exist_ok=False);sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2);pressure=SystemRamPressure()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def request(url):return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-public-model-validation','Accept':'application/vnd.github+json'}),timeout=30)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
name='sherpa-onnx-fire-red-asr2-zh_en-int8-2026-02-26.tar.bz2';at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds');start=time.perf_counter();state={'state':'RESOLVING_OFFICIAL_RELEASE_ASSET','startedAt':at,'bytes':0,'saleQualified':False};write(C/'download-state.json',state)
try:
 with request('https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/tags/asr-models') as f:release=json.load(f)
 asset=next(a for a in release['assets'] if a['name']==name)
 write(C/'source.json',{'at':at,'model':'FireRedASR2-AED','variant':'Full AED encoder+attention decoder, maintained int8ONNX conversion; not CTC-only, not original2025FireRedAED. No bit-exact nativefloatcheckpoint claim.','upstream':'https://github.com/FireRedTeam/FireRedASR2S','upstreamModel':'https://huggingface.co/FireRedTeam/FireRedASR2-AED','conversionDocs':'https://k2-fsa.github.io/sherpa/onnx/FireRedAsr/pretrained.html','asset':{k:asset.get(k) for k in ['id','name','size','digest','browser_download_url','created_at','updated_at']},'releaseId':release['id'],'releaseTag':release['tag_name'],'benchmarkEvidence':'OfficialFireRedASR2 report WenetSpeechmeeting AED4.53% versus Qwen1.7B5.88%; author benchmark notour strictmeeting result orint8equivalence. This justifies one candidate, not replacement.','officialBenchmarkUrl':'https://raw.githubusercontent.com/FireRedTeam/FireRedASR2S/main/README.md','decision':'ExistingQwenbaseline retained. Test resource/load andsameaudio only; no prompts/answerhotwords/thresholds/training. No bulkmodelsearch.','resourcePolicy':'SingleCPUmodel5percent/private2GiB, singleORTthread, actualLOWRAMstop; no otherapps modified.','saleQualified':False})
 path=CACHE/name;temporary=path.with_suffix('.part');state['state']='DOWNLOADING_PINNED_PUBLIC_ASSET';write(C/'download-state.json',state)
 with request(asset['browser_download_url']) as response,temporary.open('xb') as f:
  for b in iter(lambda:response.read(1024*1024),b''):
   if pressure.low():raise RuntimeError('ActualWindowsLOWRAM; preservepartialdownload')
   f.write(b);state['bytes']+=len(b)
   if state['bytes']%(16*1024**2)==0:state['seconds']=time.perf_counter()-start;write(C/'download-state.json',state)
 assert state['bytes']==asset['size'];digest=sha(temporary)
 if asset.get('digest'):assert asset['digest']=='sha256:'+digest,'OfficialGitHubassetdigestdiffers'
 temporary.rename(path);state.update(state='EXTRACTING_VERIFIED_ASSET',sha256=digest,publisherDigestVerified=bool(asset.get('digest')));write(C/'download-state.json',state)
 files=[]
 with tarfile.open(path,'r:bz2') as archive:
  for member in archive:
   assert member.isfile() or member.isdir(),'No symlink orspecialarchiveentries'
   relative=Path(member.name);assert not relative.is_absolute() and '..' not in relative.parts
   target=(CACHE/relative).resolve();assert target.is_relative_to(CACHE.resolve())
   if member.isdir():target.mkdir(parents=True,exist_ok=True);continue
   target.parent.mkdir(parents=True,exist_ok=True)
   with archive.extractfile(member) as src,target.open('xb') as dst:
    for b in iter(lambda:src.read(1024*1024),b''):dst.write(b)
   files.append({'file':str(target),'bytes':target.stat().st_size,'sha256':sha(target)})
 model=CACHE/name.removesuffix('.tar.bz2');assert all((model/n).exists() for n in ['encoder.int8.onnx','decoder.int8.onnx','tokens.txt'])
 write(C/'model-ready.json',{'state':'PINNED_COMPLETE_FIRERED2_AED_INT8_READY_NOT_INFERRED','modelRoot':str(model),'archiveSha256':digest,'assetId':asset['id'],'assetPublisherDigestVerified':bool(asset.get('digest')),'files':files,'weightsModified':False,'saleQualified':False});state.update(state='COMPLETE_PINNED_FIRERED2_AED_READY',modelRoot=str(model))
except BaseException as exc:
 state.update(state='FAILED',failureType=type(exc).__name__,reason=str(exc));raise
finally:state['seconds']=time.perf_counter()-start;state['limits']=limits.query();write(C/'download-state.json',state);print(json.dumps(state,ensure_ascii=False),flush=True)
