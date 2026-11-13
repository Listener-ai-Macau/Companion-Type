from pathlib import Path
from datetime import datetime
import json,wave,hashlib,subprocess,numpy as np
C=Path('E:/CodexData/Companion/.build-cache/imu-pointer20261112/concentrated20261113/chinese-real-short');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/notebook-foundation20261113/real-chinese019f118-r3');R=O/'volume-reference';R.mkdir(exist_ok=False)
speaker=json.loads((C/'speaker-playback.json').read_bytes());row=json.loads((C/'capture/short/library/sessions.json').read_bytes())[0];raw=Path(row['audioPath']);source=Path(speaker['source']['wav']);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();before=sha(raw)
def samples(p):
 with wave.open(str(p),'rb')as w:assert w.getframerate()==16000 and w.getnchannels()==1 and w.getsampwidth()==2;return np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float64)
def bins(a):a=a[:len(a)//800*800].reshape(-1,800);return np.sqrt(np.mean(a*a,axis=1))
x=samples(raw);s=samples(source);a=bins(x);b=bins(s[:round(speaker['requestedSeconds']*16000)]);offset=(speaker['launchUnixNs']-json.loads((C/'capture/result.json').read_bytes())['stages'][0]['captureObservedUnixNs'])/1e9
fits=[]
for shift in range(round((offset-3)*20),round((offset+3)*20)+1):
 n=min(len(a)-shift,len(b));fits.append((float(np.corrcoef(a[shift:shift+n],b[:n])[0,1]),shift/20))
best=max(fits);start=round(best[1]*20);n=min(len(a)-start,len(b));pre=a[80:max(81,start-20)];during=a[start:start+n]
def info(v):
 return dict(rms=float(np.sqrt(np.mean(v*v))),rmsDbfs=float(20*np.log10(max(np.sqrt(np.mean(v*v)),1)/32768)),peak=float(np.max(np.abs(v))),clippedSamples=int(np.sum(np.abs(v)>=32760)))
normalized=R/'public-human-meeting-playback-normalized.wav';log=R/'normalization.log';command=['ffmpeg','-hide_banner','-nostdin','-i',str(source),'-t',str(speaker['requestedSeconds']),'-af','loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json','-ar','16000','-ac','1','-c:a','pcm_s16le',str(normalized)]
with log.open('wb')as stream:run=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=120)
assert run.returncode==0 and normalized.is_file();z=samples(normalized);assert abs(len(z)/16000-speaker['requestedSeconds'])<.1;assert sha(raw)==before
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='ACTUAL019F_LEVEL_ANALYZED_LOUDER_LIMITED_PUBLIC_PLAYBACK_COPY_PREPARED',originalRecordedWav=dict(path=str(raw),sha256=before,**info(x)),publicPlaybackSource=dict(path=str(source),sha256=sha(source),**info(s[:round(speaker['requestedSeconds']*16000)])),measuredAcousticAlignment=dict(expectedSourceStartAfterRecordingSeconds=offset,bestEnvelopeAlignmentSeconds=best[1],envelopeCorrelation=best[0],prePlaybackMedian50msRms=float(np.median(pre)),duringPublicPlaybackMedian50msRms=float(np.median(during)),interpretation='Relative signal evidence only; includes microphone/room/background sounds and is not calibrated SPL, guaranteed SNR or intelligibility qualification.'),newPlaybackCopy=dict(path=str(normalized),sha256=sha(normalized),seconds=len(z)/16000,**info(z),normalizationFilter='loudnorm=I=-16:TP=-1.5:LRA=7',suggestedPlayerVolumePercent=100,previousDigitalGain=6,previousPlayerVolumePercent=70,estimatedDigitalRmsIncreaseVsPreviousPlaybackDb=float(20*np.log10(np.sqrt(np.mean(z*z))/(np.sqrt(np.mean(s[:len(z)]**2))*6*.7)))),synthesizedSpeech=False,referenceTranscriptUsed=False,boardAudioModified=False,newRecordingStarted=False,actualNewAcousticCaptureChecked=False,ownerAudibilityAccepted=False)
(R/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(record,ensure_ascii=False))
