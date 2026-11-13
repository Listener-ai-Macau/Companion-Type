from pathlib import Path
from datetime import datetime
import json,os,sys,time,subprocess,shutil,hashlib,wave,array,math,argparse
from pycaw.pycaw import AudioUtilities
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113')
task=json.loads((R/'docs/product_backlog.json').read_bytes())['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110']['ownerProductClosure20261112']['ownerUiUsabilityRework20261112']['completeProductRework20261113']
assert task.get('soundOutputPolicy',{}).get('allowed')is True,'Owner meeting sound pause: explicit permission required before any speaker output; silent work can continue.'
parser=argparse.ArgumentParser();parser.add_argument('--folder',default='public-level-control-resumed20261113');parser.add_argument('--duration',type=int,default=180);parser.add_argument('--source-offset',type=float,default=1620);parser.add_argument('--profile',choices=['comparison','headroom'],default='comparison');args=parser.parse_args();assert args.folder.startswith('public-level-control-')and '/'not in args.folder and '\\'not in args.folder
assert 10<=args.duration<=1800 and args.source_offset>=0 and args.source_offset+args.duration<=1800
P=O/args.folder;P.mkdir(exist_ok=False)
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(5,2*1024**3)
sys.path.insert(0,str(R.parent/'ai-collaboration-workflow/scripts'));from development_storage import preflight
storage=preflight(O.parents[1],reserve_gib=1)
identity_path=O/'current-board-identity-resumed.json';identity=json.loads(identity_path.read_bytes());assert identity['deviceUid']=='120011000d50335754363720'and identity['crv2CrcValid']and time.time()-identity_path.stat().st_mtime<900
firmware=identity['firmware']
proof=R/'docs/handoffs/20261112-product-closure/windows126/windows-verification.json';source=json.loads((O/'public-source.json').read_bytes());start=source['sourceStartSeconds']+args.source_offset;duration=args.duration
speakers=AudioUtilities.GetSpeakers();volume=speakers.EndpointVolume;assert not volume.GetMute()and volume.GetMasterVolumeLevelScalar()>.4
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='PREPARING_PUBLIC_LEVEL_CONTROL',controllerPid=os.getpid(),source=source['source'],sourceSha256=source['sourceSha256'],sourceStartSeconds=start,durationSeconds=duration,systemVolume=volume.GetMasterVolumeLevelScalar(),globalVolumeChanged=False,outputDevice=speakers.FriendlyName,comparisons=[],physicalOwnerAction=False,cloud=False,privateOldAudioRead=False,actualFirmware=firmware,identityProof=str(identity_path),resourceLimits=limits.receipt,storage=storage,priorInterrupted01a3Excluded=True)
def save():(P/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
save();original=Path(source['source']);assert hashlib.sha256(original.read_bytes()).hexdigest()==source['sourceSha256']
runner=P/'run-current-capture.py';code=(O/'run-current-public-capture.py').read_text(encoding='utf8');assert code.count('wire.FIRMWARE=66830')==1;code=code.replace('wire.FIRMWARE=66830',f'wire.FIRMWARE={firmware}').replace("'firmware':66830",f"'firmware':{firmware}");runner.write_text(code,encoding='utf8')
levels=[('current-minus16',-16,-1.5),('higher-minus10',-10,-1.5)]if args.profile=='comparison'else [('headroom-minus13',-13,-3.0)]
for label,lufs,true_peak in levels:
 assert not(P/'cancel-request.json').exists(),'Owner cancelled this owned control'
 wav=P/(label+'.wav');prepare=subprocess.run([shutil.which('ffmpeg'),'-hide_banner','-loglevel','warning','-threads','1','-ss',str(start),'-t',str(duration),'-i',str(original),'-af',f'pan=mono|c0=c0,loudnorm=I={lufs}:TP={true_peak}:LRA=7','-ar','16000','-ac','1','-c:a','pcm_s16le',str(wav)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);assert prepare.returncode==0,prepare.stderr.decode(errors='replace')
 with wave.open(str(wav),'rb')as prepared:
  assert prepared.getnchannels()==1 and prepared.getsampwidth()==2 and prepared.getframerate()==16000 and prepared.getnframes()==duration*16000
  samples=array.array('h',prepared.readframes(prepared.getnframes()));rms=math.sqrt(sum(x*x for x in samples)/len(samples))/32768;peak=max(abs(x)for x in samples)/32768
 assert not volume.GetMute()and abs(volume.GetMasterVolumeLevelScalar()-record['systemVolume'])<.001,'Owner playback condition changed; preserve prior control, do not alter global setting'
 assert not(P/'cancel-request.json').exists(),'Owner cancelled before capture start'
 status=json.loads(subprocess.check_output(['python',str(R/'tools/board_turn.py'),'status'],cwd=R,text=True,encoding='utf8'));assert status['holder']is None,'Board occupied; do not claim or wait while holding a connection'
 out=P/label;item=f'前端中文真实会议播放电平对照 {label}，普通126/FW{firmware}，仅本轮新原音，无Owner弹窗'
 capture=player=None;step=dict(label=label,loudnessTargetLufs=lufs,truePeakLimitDb=true_peak,playback=str(wav),playbackSha256=hashlib.sha256(wav.read_bytes()).hexdigest(),playbackRms=rms,playbackPeak=peak,captureOutput=str(out),state='CONNECTING');record['comparisons'].append(step);record.update(state='RUNNING_'+label,activeCondition=label);save()
 try:
  with(P/(label+'-capture.log')).open('xb')as log:
   capture=subprocess.Popen([sys.executable,str(runner),'--output',str(out),'--stages','short','--short-seconds',str(duration+8),'--board-item',item,'--native-proof',str(proof)],cwd=runner.parent,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
   step['capturePid']=capture.pid;save()
   ready=out/'short/capture-started.json';deadline=time.monotonic()+120
   while not ready.exists():
    assert capture.poll()is None,'Preflight failed before speaker playback';assert time.monotonic()<deadline;time.sleep(.2)
   step.update(state='CAPTURING_PUBLIC_PASSAGE',captureObserved=json.loads(ready.read_bytes()),playbackStartUnixNs=time.time_ns());save()
   assert not(P/'cancel-request.json').exists(),'Owner cancelled before speaker playback'
   with(P/(label+'-speaker.log')).open('xb')as log2:
    player=subprocess.Popen([shutil.which('ffplay'),'-hide_banner','-loglevel','warning','-threads','1','-nodisp','-autoexit','-vn','-volume','100',str(wav)],stdout=log2,stderr=log2,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    step['playerPid']=player.pid;save()
    print(json.dumps(dict(state=step['state'],label=label,seconds=duration,systemVolume=record['systemVolume'])),flush=True)
    while player.poll()is None:
     assert capture.poll()is None,'Capture ended before playback';assert not(P/'cancel-request.json').exists();time.sleep(.5)
    assert player.returncode==0
   capture.wait(timeout=300);assert capture.returncode==0
   result=json.loads((out/'result.json').read_bytes());assert result['ownHandlesClosed']and result['release']['result']=='TURN_RELEASED';step.update(state='LEVEL_CONTROL_CAPTURE_COMPLETE',captureReceipt=str(out/'result.json'),durationMs=result['stages'][0]['audioDurationMs']);save()
 except BaseException as error:
  step.update(state='CONTROL_FAILED_RETAINED',error=repr(error));save()
  if player and player.poll()is None:player.terminate();player.wait(timeout=10)
  if capture and capture.poll()is None:
   out.mkdir(parents=True,exist_ok=True);(out/'cancel-request.json').write_text(json.dumps(dict(reason='Stop only owned new public control')));capture.wait(timeout=180)
  raise
record.update(state='BOTH_PUBLIC_LEVEL_CONTROLS_CAPTURED_ASR_COMPARISON_PENDING',finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'));save();print(json.dumps(record,ensure_ascii=False),flush=True)
