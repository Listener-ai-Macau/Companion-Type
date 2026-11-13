from pathlib import Path
from datetime import datetime,timezone,timedelta
import copy,json,hashlib,os,sys,subprocess,time,wave,math,re,unicodedata,numpy as np,argparse
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');parser=argparse.ArgumentParser();parser.add_argument('--folder',default='public-level-control-resumed20261113');args=parser.parse_args();assert args.folder.startswith('public-level-control-')and '/'not in args.folder and '\\'not in args.folder;P=O/args.folder;control=json.loads((P/'result.json').read_bytes());assert control['state']=='BOTH_PUBLIC_LEVEL_CONTROLS_CAPTURED_ASR_COMPARISON_PENDING';Q=P/'evaluation';Q.mkdir(exist_ok=False)
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(10,2*1024**3);pressure=SystemRamPressure();assert not pressure.low()
sys.path.insert(0,str(O/'evaluation-deps'));from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
from rapidfuzz.distance import Levenshtein
proof=json.loads((R/'docs/handoffs/20261112-product-closure/windows126/windows-verification.json').read_bytes());exe=Path(proof['nativeRoot'])/'companion-type.exe';models=O/'model-comparison-source-r2/official-paraformer/models'
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(exe)==proof['embeddedExeSha256']and models.is_dir()
def normalized(s):
 s=re.sub(r'<[^>]*>','',unicodedata.normalize('NFKC',s).lower());return ''.join(c for c in s if unicodedata.category(c)[0]in ['L','N'])
reference=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/S_R004S03C01.TextGrid');a=control['sourceStartSeconds'];b=a+control['durationSeconds'];rows=sorted([r for r in read_reference_intervals(reference)if r['text'].strip()and r['end']>a and r['start']<b],key=lambda r:(r['start'],r['end'],r['speaker']))
refs=dict(intersectingIntervals=normalized(''.join(r['text']for r in rows)),completeIntervalsOnly=normalized(''.join(r['text']for r in rows if r['start']>=a and r['end']<=b)))
report=dict(at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),state='RUNNING_SAME_PUBLIC_PASSAGE_NATIVE_LOCAL_ASR_COMPARISON',sourceStartSeconds=a,sourceEndSeconds=b,actualFirmware=control['actualFirmware'],normalEngineVersion='0.1.126',sourceCommit=proof['sourceCommit'],referenceParser=PARSER_ID,referenceSha256=sha(reference),referenceGivenToModels=False,referenceIntervals=len(rows),boundaryPartialIntervals=[r for r in rows if r['start']<a or r['end']>b],normalization='NFKC lower; letters/numbers, no spoken hesitation removal or numeric correction. Annotation-only angle markers excluded.',sourceAndPhysicalControls=[],privateOldAudioOrInterrupted01a3Read=False,cloudAudioOrTextUpload=False,globalVolumeChanged=False,systemVolume=control['systemVolume'],resourceLimits=limits.receipt)
def save():(Q/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
def signal(p):
 with wave.open(str(p),'rb')as f:
  assert f.getnchannels()==1 and f.getframerate()==16000 and f.getsampwidth()==2
  x=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
 one=[float(np.sqrt(np.mean(x[i:i+16000]**2)))for i in range(0,len(x)-15999,16000)]
 return dict(seconds=len(x)/16000,rms=float(np.sqrt(np.mean(x**2))),peak=float(np.max(np.abs(x))),clippedFraction=float(np.mean(np.abs(x)>=.999)),lowestOneSecondRms=min(one),quietOneSecondRmsP10=float(np.quantile(one,.1)))
save();cases=[]
for step in control['comparisons']:
 capture=Path(step['captureOutput']);done=json.loads((capture/'result.json').read_bytes());assert done['ownHandlesClosed']and done['release']['result']=='TURN_RELEASED'
 state=capture/'short/library/sessions.json';saved=json.loads(state.read_bytes());assert len(saved)==1;row=saved[0];assert row['source']=='boardDevice'and row['deviceRecordingKey']==step['captureObserved']['recordingKey']and row['deviceRecordingKey']['sessionId']not in ['00000000000001a3','000000000000019e'];assert not row['transcriptFinal']
 wave_file=Path(row['audioPath']);originals={str(x):sha(x)for x in (capture/'short/library/recordings').iterdir()if x.is_file()and x.suffix in ['.wav','.opus']};assert sha(wave_file)==next(digest for name,digest in originals.items()if Path(name).name==wave_file.name)
 cases.append(dict(name='card-'+step['label'],state=state,row=row,audio=wave_file,recordings=capture/'short/library/recordings',originals=originals,condition=step['label'],kind='actual_new_card_capture'))
 source_row=copy.deepcopy(row);audio=Path(step['playback']);source_row.update(id='public-source-'+str(control['durationSeconds'])+'-'+step['label'],title='公开会议源音电平对照',source='importedAudio',status='captured',processingPolicy='manual',durationMs=control['durationSeconds']*1000,audioPath=str(audio),audioBytes=audio.stat().st_size,audioStored=True,transcriptText='',transcriptFinal=False,transcriptSegments=0,utterances=[],transcriptUnrecognized=[],chunks=[],minutes=None,minutesByMode={'offlineStore':None,'onlineLive':None,'history':[]},pendingReason='needs_transcription',deviceRecordingId=None,deviceRecordingKey=None,sourceDeviceId=None,deviceTotalLength=None,deviceSha256=None,recorderControl=None,recorderControlUncertain=False,recovery={'intent':'none','requestedMeetingMode':'','stage':'idle','attemptCount':0,'maxAttempts':3,'retryStage':'','captureReviewConfirmed':False});source_row['retention'].update(audioCached=True,transcriptCached=False,minutesCached=False)
 source_folder=Q/('source-'+step['label']);source_folder.mkdir();source_state=source_folder/'sessions.json';source_state.write_text(json.dumps([source_row],ensure_ascii=False),encoding='utf8');cases.append(dict(name='source-'+step['label'],state=source_state,row=source_row,audio=audio,recordings=source_folder/'recordings',originals={str(audio):sha(audio)},condition=step['label'],kind='controlled_local_engine_source_audio_not_gui_import'))
for case in cases:
 assert not pressure.low(),'Actual Windows low memory; no new model job started'
 folder=Q/case['name'];folder.mkdir(exist_ok=case['kind'].startswith('controlled'));request=folder/'request.json';request.write_text(json.dumps(dict(sessionId=case['row']['id'])))
 env={k:v for k,v in os.environ.items()if not k.startswith(('COMPANION_TYPE_ASR_','COMPANION_TYPE_TRANSCRIPT','COMPANION_TYPE_MINUTES_COMMAND'))};env.update(COMPANION_TYPE_STATE_PATH=str(case['state']),COMPANION_TYPE_RECORDING_DIR=str(case['recordings']),COMPANION_TYPE_LOCAL_ASR_DIR=str(models),COMPANION_TYPE_ASR_CACHE_DIR=str(folder/'asr-cache'),COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_DISABLE_AUTO_RECONNECT='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1');start=time.monotonic()
 with(folder/'asr.log').open('xb')as log:run=subprocess.run([str(exe),'--meeting-transcribe-request',str(request),str(folder/'transcribed.json')],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
 assert run.returncode==0,(folder/'asr.log').read_text(errors='replace')[-1000:]
 result=json.loads((folder/'transcribed.json').read_bytes());assert result['operationError']is None,result['operationError'];row=next(r for r in result['snapshot']['host']['sessions']if r['id']==case['row']['id']);assert row['transcriptFinal'];text=row['transcriptText'];(folder/'hypothesis.txt').write_text(text,encoding='utf8');hyp=normalized(text);scores={}
 for kind,ref in refs.items():
  ops=Levenshtein.editops(ref,hyp);scores[kind]=dict(referenceCharacters=len(ref),hypothesisCharacters=len(hyp),errors=len(ops),cer=len(ops)/len(ref),**{x:sum(op.tag==x for op in ops)for x in ['replace','insert','delete']})
 for path,digest in case['originals'].items():assert sha(path)==digest
 evidence=dict(name=case['name'],condition=case['condition'],kind=case['kind'],seconds=round(time.monotonic()-start,3),hypothesis=str(folder/'hypothesis.txt'),provider=result['settings']['asrProvider'],scores=scores,signal=signal(case['audio']),originalAudioUnchanged=True,originalAudioSha256=sha(case['audio']));report['sourceAndPhysicalControls'].append(evidence);save();print(json.dumps(evidence,ensure_ascii=False),flush=True)
report.update(state='RESUMED_PUBLIC_LEVEL_AND_SOURCE_ASR_COMPARISON_COMPLETE',finishedAt=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),asrAccuracyQualified=False,softwareDefaultNotChanged=True);save();print(json.dumps(dict(state=report['state'],evidence=str(Q/'result.json'))),flush=True)
