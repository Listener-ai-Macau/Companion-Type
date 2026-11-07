"""Fetch two pinned public official assets, no installers, inference or global setup."""
from pathlib import Path
from datetime import datetime
import concurrent.futures,hashlib,json,os,shutil,stat,subprocess,urllib.request,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/nemotron-speaker-20261107-prep';E=Path('E:/CodexData/Companion/.model-cache/nemotron-speaker-20261107');E.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
release=read(C/'release-metadata.json');meta=read(C/'model-metadata.json');assert release['tag_name']=='v0.3.0' and meta['gated'] is False and meta['private'] is False
runtime=next(x for x in release['assets'] if x['name']=='nemo-speech-0.3.0-windows-x86_64-cpu.zip');weight=next(x for x in meta['siblings'] if x['rfilename']=='Nemotron-3-Diarization.q8_0.gguf')
assets=[{'name':runtime['name'],'url':runtime['browser_download_url'],'bytes':runtime['size'],'sha256':runtime['digest'].removeprefix('sha256:')},{'name':weight['rfilename'],'url':'https://huggingface.co/nvidia/Nemotron-3-Diarization/resolve/'+meta['sha']+'/'+weight['rfilename'],'bytes':weight['lfs']['size'],'sha256':weight['lfs']['sha256']}]
sha=lambda p:hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def fetch(asset):
    dest=E/asset['name']
    if not dest.exists():
        partial=dest.with_suffix(dest.suffix+'.part');request=urllib.request.Request(asset['url'],headers={'User-Agent':'Companion-model-research-20261107'})
        with urllib.request.urlopen(request,timeout=45) as source,partial.open('wb') as target:
            shutil.copyfileobj(source,target,1024*1024);target.flush();os.fsync(target.fileno())
        assert partial.stat().st_size==asset['bytes'] and sha(partial)==asset['sha256'],'Published asset digest/size mismatch; refuse loading'
        os.replace(partial,dest)
    assert dest.stat().st_size==asset['bytes'] and sha(dest)==asset['sha256']
    return {**asset,'file':str(dest),'verified':True}
results=list(concurrent.futures.ThreadPoolExecutor(2).map(fetch,assets));out=E/'runtime-0.3.0-cpu';out.mkdir(exist_ok=True)
with zipfile.ZipFile(results[0]['file']) as archive:
    for member in archive.infolist():
        target=(out/member.filename).resolve();assert target.is_relative_to(out.resolve()) and not stat.S_ISLNK(member.external_attr>>16),'Archive path/symlink escaped independent runtime directory'
    archive.extractall(out)
exe=next(out.rglob('nemo-speech.exe'));probe=subprocess.run([str(exe),'diarize','--help'],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
(C/'diarize-help.txt').write_text(probe.stdout+'\n'+probe.stderr,encoding='utf8')
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'OFFICIAL_CPU_RUNTIME_AND_PUBLIC_8_SPEAKER_WEIGHTS_PREPARED_NO_INFERENCE','assets':results,'modelRepository':'nvidia/Nemotron-3-Diarization','modelRevision':meta['sha'],'accountRequiredForActualDownload':False,'runtime':str(exe),'runtimeSha256':sha(exe),'helpExitCode':probe.returncode,'cpuPackageOnly':True,'inferencePerformed':False,'defaultBackendChanged':False,'modelCandidateNotQualified':True,'routeReason':'Current full official complete-link result fragmented6 reference speakers into190 active groups, DER78.0445%. Test one pretrained8-channel end-to-end diarizer rather than per-meeting threshold fitting. Same full development meetings and original quality gates; not overlap-word separation or ASR<5%.'}
(C/'prepared.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False),flush=True)
