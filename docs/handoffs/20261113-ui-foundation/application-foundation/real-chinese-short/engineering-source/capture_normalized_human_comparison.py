"""One bounded comparison of the same public human source at a documented playback level."""
from pathlib import Path
from datetime import datetime
import json,os,subprocess,sys,time,hashlib,shutil
from pycaw.pycaw import AudioUtilities
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/notebook-foundation20261113/real-chinese019f118-r3/volume-reference')
source=O/'public-human-meeting-playback-normalized.wav';assert hashlib.sha256(source.read_bytes()).hexdigest()=='3ab5f1900ca6765082d5eef4c35939507d95d460f04efe4d3db91110b02f2eda'
out=O/'capture-normalized-r1';assert not out.exists()
status=json.loads(subprocess.check_output([sys.executable,str(R/'tools/board_turn.py'),'status'],text=True,encoding='utf8'));assert status['holder']is None and status['mayClaim']['codex']
speakers=AudioUtilities.GetSpeakers();volume=speakers.EndpointVolume;assert not volume.GetMute();before=volume.GetMasterVolumeLevelScalar();assert before>.95,'Comparison keeps the existing system volume; no system setting is changed'
controller=Path('C:/Users/Billy/Documents/Codex/2026-11-03/companion-firmware-66662-luna/recovery-work/run_shared829_background.py')
record=dict(at=datetime.now().astimezone().isoformat(timespec='milliseconds'),state='WAITING_SAME_ORIGINAL_CAPTURE',source=str(source),sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),requestedPlaybackSeconds=110,playerVolumePercent=100,sourceNormalization='loudnorm I=-16 TP=-1.5 LRA=7',systemMasterVolumeBefore=before,outputDevice=speakers.FriendlyName,syntheticSpeech=False,audioInjected=False,preexistingAudioSelected=False,asrRequested=False,cloudRequested=False)
receipt=O/'normalized-comparison-run.json';assert not receipt.exists()
def save():receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
player=None;capture=None
try:
 save()
 with(O/'comparison-capture-runner.log').open('xb')as log:
  capture=subprocess.Popen([sys.executable,str(controller),'--output',str(out),'--stages','short','--short-seconds','120','--board-item','前端同真人音源播放电平短对照，仅新录音，正常118接收保存','--native-proof',str(R/'docs/handoffs/20261112-product-closure/windows118/windows-verification.json')],cwd=controller.parent,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
  started=out/'short/capture-started.json';deadline=time.monotonic()+120
  while not started.exists():
   assert capture.poll()is None,'Capture stopped before START; inspect preserved controller result'
   assert time.monotonic()<deadline,'No normal capture start within two minutes'
   time.sleep(.2)
  start=json.loads(started.read_bytes());assert start['recordingKey']['sessionId']!='000000000000019f'
  record.update(state='PLAYING_PUBLIC_NORMALIZED_SOURCE',capturePid=capture.pid,recordingKey=start['recordingKey'],sessionId=start['sessionId'],captureObservedUnixNs=start['captureObservedUnixNs'],launchUnixNs=time.time_ns());save()
  with(O/'normalized-speaker-player.log').open('xb')as soundlog:
   player=subprocess.Popen([shutil.which('ffplay'),'-hide_banner','-loglevel','warning','-stats','-nodisp','-autoexit','-vn','-volume','100','-t','110',str(source)],stdin=subprocess.DEVNULL,stdout=soundlog,stderr=soundlog,creationflags=subprocess.CREATE_NO_WINDOW)
   record['playerPid']=player.pid;save();print(json.dumps(record,ensure_ascii=False),flush=True)
   player.wait(timeout=135);assert player.returncode==0;record.update(state='PUBLIC_PLAYBACK_FINISHED_WAITING_NORMAL_RECEIVE',playbackFinishedUnixNs=time.time_ns());save()
  capture.wait(timeout=600);assert capture.returncode==0
  final=json.loads((out/'result.json').read_bytes());assert final['ownHandlesClosed']and final['release']['result']=='TURN_RELEASED'
  record.update(state='ONE_NORMALIZED_PUBLIC_SPEAKER_TO_MIC_CAPTURE_RECEIVED',captureResult=str(out/'result.json'),captureExitCode=capture.returncode,physicalAudibilityOwnerAccepted=False,recognitionQualityQualified=False)
except BaseException as error:
 record.update(state='NORMALIZED_COMPARISON_STOPPED_EVIDENCE_RETAINED',error=repr(error))
 if out.exists()and capture and capture.poll()is None:
  (out/'cancel-request.json').write_text(json.dumps(dict(reason='Frontend comparison runner stopped; original controller must stop only its own new capture')),encoding='utf8')
  capture.wait(timeout=180)
 raise
finally:
 if player and player.poll()is None:player.terminate();player.wait(timeout=10)
 record.update(finishedAt=datetime.now().astimezone().isoformat(timespec='milliseconds'),systemMasterVolumeAfter=volume.GetMasterVolumeLevelScalar());save();print(json.dumps(record,ensure_ascii=False),flush=True)
