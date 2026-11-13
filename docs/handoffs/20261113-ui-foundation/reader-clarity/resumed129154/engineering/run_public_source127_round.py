"""One clean public-source software journey, separate from mixed-room capture."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113')
P=O/'public-source-full30-127';P.mkdir(exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['import','minutes','reader']);parser.add_argument('--attempt',type=int,default=1);parser.add_argument('--reader-version',type=int,choices=[127,129],default=127);args=parser.parse_args();phase=args.phase;assert 1<=args.attempt<=5
version=args.reader_version;assert phase=='reader' or version==127
proof_path=R/'docs/handoffs/20261112-product-closure'/('windows'+str(version))/'windows-verification.json'
proof=json.loads(proof_path.read_bytes());exe=Path('C:/Program Files/Companion Type/companion-type.exe')
def sha(path):
 with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
if phase=='reader':exe=Path(proof['nativeRoot'])/'companion-type.exe'
assert sha(exe)==proof['embeddedExeSha256'] and sha(exe.with_name('companion_type_lib.dll'))==proof['dllSha256']
if version==129:
 frozen=json.loads((proof_path.parent/'frozen-source.json').read_bytes());assert not subprocess.check_output(['git','-c','maintenance.auto=false','-c','gc.auto=0','diff','b5a15d2380923b7a700de87ac509d9800dcab85b',proof['sourceCommit'],'--',*frozen['unchangedSinceActual127PublicAsrAndMinutes']],cwd=Path(proof['frozenSourceRoot']))
if phase=='import':
 Q=P/('native-import' if args.attempt==1 else 'native-import-r'+str(args.attempt));Q.mkdir(exist_ok=False)
 source=O/'public-level-control-full30-fixed20261113/headroom-minus13.wav'
 assert sha(source)=='d6ab13a19fec81df257036b5cdc19eb47aea7c96fb140e3bd3f6977e84586347'
 public_audio=P/'公开中文会议（30分钟）.wav'
 if not public_audio.exists():public_audio.hardlink_to(source)
 else:assert public_audio.samefile(source) and sha(public_audio)==sha(source)
 model=Path(os.environ['APPDATA'])/'Companion Type/models/local-asr'
 spec=dict(publicSourceOnly=True,audioInput=str(public_audio),audioSha256=sha(public_audio),durationSeconds=1800,localModelRoot=str(model),sourceDataset='AISHELL4 S_R004S03C01 channel0',sourceFlacSha256='c21ce5ce455b87926ca6b486431db2889de5d14be91b55f8cffea31cd94c1262',sourceStartSeconds=214.06043,referenceGivenToModels=False,physicalNewCapture=False)
 save(Q/'spec.json',spec)
 env={**os.environ,'COMPANION_ACCEPTANCE_PROJECT_ROOT':str(Q/'product'),
  'COMPANION_ACCEPTANCE_CACHE':str(Q/'private'),'COMPANION_ACCEPTANCE_VERIFICATION':str(proof_path),
  'COMPANION_ACCEPTANCE_FROZEN_NATIVE':proof['nativeRoot'],'COMPANION_ACCEPTANCE_OWNER_PREFLIGHT':'1',
  'COMPANION_TYPE_BLE_NATIVE_DISABLED':'1','COMPANION_ACCEPTANCE_PUBLIC_SOURCE_IMPORT':str(Q/'spec.json'),
  'NO_PROXY':'127.0.0.1,localhost,::1','no_proxy':'127.0.0.1,localhost,::1'}
 with (Q/'runner.log').open('xb')as log:run=subprocess.run([sys.executable,str(S/'tools/qa/core_acceptance20261109/windows_meeting.py'),'--stage','product-background','--audio',str(public_audio)],cwd=S,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
 assert run.returncode==0,(Q/'runner.log').read_text(errors='replace')[-3000:]
 cases=list((Q/'product/docs/handoffs/20261109-core-acceptance').iterdir());assert len(cases)==1
 evidence=cases[0]/'result.json';detail=json.loads(evidence.read_bytes());assert detail['state']=='REAL_NATIVE_PUBLIC_SOURCE_IMPORT_LOCAL_ASR_AND_REOPEN_PASSED'
 assert detail['ui']['newAsrRun'] and detail['processRestart']['previousAppExited'] and detail['processRestart']['allPublicLibraryRowsUnchanged']
 state=Path(detail['privateRoot'])/'state/sessions.json';rows=json.loads(state.read_bytes());row=next(r for r in rows if r['id']==detail['ui']['sessionId']);assert row['source']=='importedAudio' and row['transcriptFinal']
 manifest=cases[0]/'public-source-import.json';m=json.loads(manifest.read_bytes());assert sha(m['originalPath'])==spec['audioSha256']
 save(P/'active-public-library.json',dict(statePath=str(state),recordingDir=str(Path(detail['privateRoot'])/'recordings'),sessionId=row['id'],transcriptSha256=hashlib.sha256(row['transcriptText'].encode()).hexdigest(),nativeImportEvidence=str(evidence),nativeImportManifest=str(manifest),sourceSha256=spec['audioSha256'],sourceStateRows=len(rows)))
 (P/'hypothesis.txt').write_text(row['transcriptText'],encoding='utf8')
 save(P/'import-result.json',dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='ACTUAL127_PUBLIC_SOURCE30_NATIVE_IMPORT_ASR_SAVE_AND_PROCESS_REOPEN_PASSED',evidence=str(evidence),originalSourceUnchanged=sha(public_audio)==spec['audioSha256'],cloudCalls=0,acousticOrBoardAccuracyQualified=False))
 print(json.dumps(dict(state='PUBLIC_SOURCE30_IMPORT_ASR_AND_REOPEN_COMPLETE',evidence=str(evidence),characters=len(row['transcriptText']))),flush=True)
elif phase=='minutes':
 active=json.loads((P/'active-public-library.json').read_bytes());state=Path(active['statePath']);before=json.loads(state.read_bytes());row=next(r for r in before if r['id']==active['sessionId'])
 assert row['source']=='importedAudio' and row['transcriptFinal'];assert hashlib.sha256(row['transcriptText'].encode()).hexdigest()==active['transcriptSha256']
 reviewed=json.loads((P/'text-reviewed-before-cloud.json').read_bytes());assert reviewed['allTextRead'] and reviewed['publicOnly'] and reviewed['transcriptSha256']==active['transcriptSha256']
 manifest=json.loads(Path(active['nativeImportManifest']).read_bytes());originals={name:sha(name)for name in [manifest['originalPath'],manifest['decodedPath']]};assert originals[manifest['originalPath']]==active['sourceSha256']
 sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
 limits=WorkerLimits(10,512*1024**2)
 env={k:v for k,v in os.environ.items()if not k.startswith(('COMPANION_TYPE_TRANSCRIPT','COMPANION_TYPE_ASR_COMMAND','COMPANION_TYPE_MINUTES_COMMAND'))};env.update(COMPANION_TYPE_STATE_PATH=str(state),COMPANION_TYPE_RECORDING_DIR=active['recordingDir'],COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_DISABLE_AUTO_RECONNECT='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1');env.pop('COMPANION_TYPE_PRODUCT_SETTINGS_PATH',None)
 output=P/'minutes-result.json';assert not output.exists()
 report=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='RUNNING_ACTUAL127_CLEAN_PUBLIC_SOURCE30_MINUTES_EXPORT_REOPEN',sessionId=row['id'],sourceCommit=proof['sourceCommit'],publicSourceOnly=True,cloudTextOnly=True,cloudAudioUpload=False,mixedRoomCapture01a7ReadOrUploaded=False,steps=[])
 def request(name,flag,data,destination,timeout=900):
  request_file=P/(name+'-request.json');assert not request_file.exists();save(request_file,data);start=time.monotonic()
  with (P/(name+'.log')).open('xb')as log:run=subprocess.run([str(exe),flag,str(request_file),str(destination)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
  report['steps'].append(dict(name=name,exitCode=run.returncode,seconds=round(time.monotonic()-start,3)));save(output,report);assert run.returncode==0,(P/(name+'.log')).read_text(errors='replace')[-1600:]
 try:
  request('standard-minutes','--meeting-minutes-request',dict(action='meetingGenerateMinutes',sessionId=row['id'],meetingMode='offlineStore',minutesTemplate=dict(id='meeting')),P/'minutes.json')
  result=json.loads((P/'minutes.json').read_bytes());minutes=result['minutesByMode']['offlineStore'];assert minutes['source']=='llm_deepseek' and minutes['quality']=='final' and minutes['status']=='minutesReady' and minutes.get('processing',{}).get('complete')is not False
  assert result['transcriptText']==row['transcriptText'] and result.get('transcriptReview')==row.get('transcriptReview')
  (P/'actual-minutes.md').write_text(minutes['markdown'],encoding='utf8')
  request('readable-export','--meeting-export-request',dict(sessionId=row['id'],meetingMode='offlineStore',format='txt',contentSections=dict(minutes=True,transcript=True,highlights=False,timeline=False,noteIds=[])),P/'公开中文会议30分钟-软件完整结果.txt')
  exported=(P/'公开中文会议30分钟-软件完整结果.txt').read_text(encoding='utf8');assert '超市'in exported and 'Generated:'not in exported and 'Minutes engine:'not in exported
  saved=json.loads(state.read_bytes());assert [r for r in saved if r['id']!=row['id']]==[r for r in before if r['id']!=row['id']]
  request('process-reopen','--local-recording-snapshot',{},P/'reopened.json');assert saved==json.loads((P/'reopened.json').read_bytes())['snapshot']['host']['sessions']
  for name,digest in originals.items():assert sha(name)==digest
  report.update(state='ACTUAL127_PUBLIC_SOURCE30_MINUTES_EXPORT_REOPEN_DONE_CONTENT_REVIEW_PENDING',originalSourceAndDecodedAudioUnchanged=True,allEarlierLibraryRowsAndRawTranscriptRetained=True,minutesCharacters=len(minutes['markdown']),physicalCaptureQualified=False,modelGeneralQualityQualified=False,ownerExperienceAccepted=False,saleQualified=False)
 except BaseException as error:report.update(state='ACTUAL127_PUBLIC_SOURCE30_MINUTES_CLOSURE_NEEDS_ATTENTION_RETAINED',error=repr(error));raise
 finally:report['finishedAt']=datetime.now().astimezone().isoformat(timespec='seconds');save(output,report);print(json.dumps(report,ensure_ascii=False),flush=True)
else:
 active=json.loads((P/'active-public-library.json').read_bytes());upstream=Path(active['statePath']);original_state=sha(upstream);row=next(r for r in json.loads(upstream.read_bytes())if r['id']==active['sessionId']);manifest=json.loads(Path(active['nativeImportManifest']).read_bytes())
 assert row['minutesByMode']['offlineStore']['source']=='llm_deepseek'
 base='native-reader'if version==127 else 'native-reader'+str(version)
 Q=P/(base if args.attempt==1 else base+'-r'+str(args.attempt));Q.mkdir(exist_ok=False);focused=Q/'one-actual-public-session.json';save(focused,[row])
 originals={Path(name).name:sha(name)for name in [manifest['originalPath'],manifest['decodedPath']]}
 markdown=row['minutesByMode']['offlineStore']['markdown'];heading='会议概览'if '## 会议概览\n'in markdown else '全会重点'
 spec=dict(statePath=str(focused),stateSha256=sha(focused),sourceKind='importedAudio',recordingKey=None,recordingDir=active['recordingDir'],originalAudioFiles=originals,sessionId=row['id'],audioDurationMs=manifest['durationMs'],nativeImportEvidence=active['nativeImportEvidence'],nativeImportManifest=active['nativeImportManifest'],upstreamStatePath=str(upstream),expectFoldedOverview=True,overviewHeading=heading,expectedMinutesTerms=[heading],expectedTranscriptTerms=['超市'],expectedExportTerms=['超市'])
 if version==129:spec.update(expectTopicDisclosures=True,expectedTopicCount=8)
 save(Q/'spec.json',spec)
 env={**os.environ,'COMPANION_ACCEPTANCE_PROJECT_ROOT':str(Q/'product'),'COMPANION_ACCEPTANCE_CACHE':str(Q/'private'),'COMPANION_ACCEPTANCE_VERIFICATION':str(proof_path),'COMPANION_ACCEPTANCE_FROZEN_NATIVE':proof['nativeRoot'],'COMPANION_ACCEPTANCE_OWNER_PREFLIGHT':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1','COMPANION_ACCEPTANCE_REAL_PUBLIC_SPEC':str(Q/'spec.json'),'NO_PROXY':'127.0.0.1,localhost,::1','no_proxy':'127.0.0.1,localhost,::1'}
 with(Q/'runner.log').open('xb')as log:run=subprocess.run([sys.executable,str(S/'tools/qa/core_acceptance20261109/windows_meeting.py'),'--stage','product-background'],cwd=S,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 assert run.returncode==0,(Q/'runner.log').read_text(errors='replace')[-2600:]
 cases=list((Q/'product/docs/handoffs/20261109-core-acceptance').iterdir());assert len(cases)==1;evidence=cases[0]/'result.json';detail=json.loads(evidence.read_bytes());assert detail['ui']['actualDefaultOverviewAndFoldedCompleteDetailChecked'] and detail['processRestart']['previousAppExited']
 assert sha(upstream)==original_state
 for name,digest in originals.items():assert sha(Path(active['recordingDir'])/name)==digest
 save(P/('reader-result.json'if version==127 else 'reader'+str(version)+'-result.json'),dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state=f'ACTUAL{version}_CLEAN_PUBLIC_SOURCE30_NATIVE_READING_THEMES_REPLAY_SELECTED_EXPORT_AND_REOPEN_PASSED',evidence=str(evidence),actualSourceAndUpstreamLibraryUnchanged=True,modelsOrCloudRerun=False,ownerExperienceAccepted=False,physicalOrSaleQualified=False))
 print(json.dumps(dict(state=f'ACTUAL{version}_PUBLIC_SOURCE_READER_COMPLETE',evidence=str(evidence))),flush=True)
