"""Resume two known public development recordings with full hash checks."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
import requests,psutil,json,time,hashlib,shutil,sys,wave,os,subprocess
root=Path('C:/Users/Billy/Desktop/Denzic/Companion');proof=root/'docs/handoffs/20261105-model-resume';out=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031')
receipt=proof/'public-audio-restore-r5.json';assert not receipt.exists()
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);psutil.Process().cpu_affinity(psutil.Process().cpu_affinity()[-2:])
sys.path.insert(0,'E:/CodexData/Companion/.model-cache/audio-tools');import soundfile as sf
revision='aada72727856313b19d4a030383c426364931dbf';s=requests.Session();s.trust_env=False
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
state={'at':now(),'state':'RECOVERING_KNOWN_PUBLIC_AUDIO_BY_RANGES','pid':os.getpid(),'cases':[],'finalHoldoutPayloadExtracted':False,'modelLoaded':False,'workers':4}
def save():
 t=receipt.with_suffix('.tmp');t.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8');t.replace(receipt)
def sha(p):
 with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
save();begin=time.perf_counter()
try:
 tree=s.get(f'https://huggingface.co/api/datasets/AISHELL/AISHELL-4/tree/{revision}/test/wav',timeout=30);tree.raise_for_status();tree=tree.json()
 for meeting,old_sha,ref_sha in [('S_R004S03C01','82ac9f8b25e2c085b2e0434e444727af0577e373ed5e1f587d3f28881862fe2f','ca515d60e370362aebbf481c465dadc0b8f0f0dc6eeb125845edd09f17cee3d3'),('L_R003S01C02','768574317a1054afe52a098f8b2630185974a57eb42144ecdf249e929807fc1a','a7e060c87f76f6ad51ca1bcd6ae7243942757f25bdcbfc9a628c552d03dcbc4c')]:
  item=next(x for x in tree if x['path']==f'test/wav/{meeting}.flac');total=item['size'];url=f'https://huggingface.co/datasets/AISHELL/AISHELL-4/resolve/{revision}/{item["path"]}'
  encoded=out/(meeting+'.flac');prefix=out/(meeting+'.part');start=prefix.stat().st_size if prefix.exists() else 0;assert start<total
  parts=out/(meeting+'-ranges');parts.mkdir(exist_ok=True)
  state.update(state='RESUMING_PUBLIC_AUDIO',activeMeeting=meeting,expectedBytes=total,reusedPrefixBytes=start,downloadedBytes=start);save()
  def one(span):
   a,b=span;target=parts/f'{a}-{b}.part';size=b-a+1;session=requests.Session();session.trust_env=False
   for attempt in range(3):
    offset=target.stat().st_size if target.exists() else 0
    if offset==size:return target
    assert offset<size
    try:
     with session.get(url,headers={'Range':f'bytes={a+offset}-{b}'},stream=True,timeout=(20,60)) as response:
      response.raise_for_status();assert response.status_code==206 and response.headers.get('Content-Range')==f'bytes {a+offset}-{b}/{total}'
      with target.open('ab' if offset else 'wb') as stream:
       for block in response.iter_content(1024**2):
        if block:stream.write(block)
     assert target.stat().st_size==size;return target
    except Exception:
     if attempt==2:raise
  spans=[(a,min(total-1,a+8*1024**2-1)) for a in range(start,total,8*1024**2)]
  if not encoded.exists():
   with ThreadPoolExecutor(max_workers=4) as pool:
    futures={pool.submit(one,x):x for x in spans}
    for f in as_completed(futures):f.result();a,b=futures[f];state['downloadedBytes']+=b-a+1;save()
   with encoded.open('xb') as stream:
    for source in ([prefix] if start else [])+[parts/f'{a}-{b}.part' for a,b in spans]:
     with source.open('rb') as inp:shutil.copyfileobj(inp,stream,1024**2)
  assert encoded.stat().st_size==total and sha(encoded)==item['lfs']['oid']
  state.update(state='DECODING_ORIGINAL_CHANNEL1');save()
  mono=out/(('meeting' if meeting.startswith('S_') else meeting)+'-channel1.wav')
  if mono.exists() and sha(mono)!=old_sha:
   retained=mono.with_name(mono.stem+'-soundfile-before-ffmpeg.wav');assert not retained.exists();mono.rename(retained)
  if not mono.exists():
   prior=out/'meeting-channel1-ffmpeg-restored.wav'
   if meeting.startswith('S_') and prior.exists() and sha(prior)==old_sha:shutil.copyfile(prior,mono)
   else:
    # Exact original archived 2026-10-31 command: first channel, no mix/resample
    # change. FFmpeg's WAV metadata bytes are part of the old whole-file SHA.
    run=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-i',str(encoded),'-af','pan=mono|c0=c0','-ar','16000','-c:a','pcm_s16le',str(mono)],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    assert run.returncode==0,run.stderr
  with wave.open(str(mono),'rb') as inp:
   assert (inp.getnchannels(),inp.getframerate(),inp.getsampwidth())==(1,16000,2);frames=inp.getnframes()
  assert sha(mono)==old_sha,'Recovered mono is not byte-identical to pre-cleanup audio'
  reference=out/(meeting+'.TextGrid');assert sha(reference)==ref_sha
  case={'meeting':meeting,'audio':str(mono),'audioSha256':old_sha,'audioSeconds':frames/16000,'reference':str(reference),'referenceSha256':ref_sha}
  state['cases'].append(case);save()
  if meeting.startswith('S_'):
   smoke=out/'engine-smoke30s-restored.wav';assert not smoke.exists()
   with wave.open(str(mono),'rb') as inp:params=inp.getparams();pcm=inp.readframes(30*16000)
   with wave.open(str(smoke),'wb') as dst:dst.setparams(params);dst.writeframes(pcm)
   manifest=[{'meeting':'engine-smoke30s-restored-20261105','audio':str(smoke),'audioSha256':sha(smoke),'audioSeconds':30.,'smokeOnly':True}]
   (proof/'compatibility-audio-only.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
 state.update(state='TWO_PUBLIC_MEETINGS_AUDIO_AND_REFERENCE_IDENTICAL_TO_PRE_CLEANUP',activeMeeting=None)
except BaseException as error:state.update(state='AUDIO_RANGE_RESTORE_FAILURE_RETAINED',error=repr(error));raise
finally:state.update(finishedAt=now(),wallSeconds=round(time.perf_counter()-begin,3));save();print(json.dumps(state),flush=True)
