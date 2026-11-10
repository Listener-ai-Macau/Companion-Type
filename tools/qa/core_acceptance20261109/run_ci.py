"""Reuse an independently inspected native pair; no native rebuild or ASR."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shutil,subprocess,sys,traceback,zipfile
S=Path(__file__).resolve().parents[3];O=S/'core-ci-output';O.mkdir()
PHASE=os.environ.get('COMPANION_CORE_PHASE','saved');assert PHASE in {'saved','audio','whole','delivery','actions','context'}
SPEC=os.environ.get('COMPANION_ACCEPTANCE_CANDIDATE_SPEC')
spec=json.loads((S/SPEC).read_text(encoding='utf8')) if SPEC else None
assert os.environ.get('GITHUB_ACTIONS')=='true' and os.name=='nt'
private=Path(os.environ['RUNNER_TEMP'])/'companion-core-acceptance';private.mkdir()
product=private/'product';cache=private/'cache';native=private/'frozen-native';native.mkdir()
env={**os.environ,'COMPANION_ACCEPTANCE_PROJECT_ROOT':str(product),'COMPANION_ACCEPTANCE_CACHE':str(cache),'COMPANION_ACCEPTANCE_FROZEN_NATIVE':str(native)}
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(name,args,environment=env,required=True):
 print('Starting '+name,flush=True)
 with (O/(name+'.log')).open('wb') as log:p=subprocess.run(list(map(str,args)),cwd=S,env=environment,stdout=log,stderr=subprocess.STDOUT)
 print(name+' exit='+str(p.returncode),flush=True)
 if required:assert p.returncode==0,name+' failed; see retained log'
 return p.returncode
record={'at':datetime.now(timezone.utc).isoformat(),'state':'PREPARING_FROZEN_CORE_WORKFLOW','testSourceCommit':os.environ['GITHUB_SHA'],'appSourceCommit':'bb1550c42b674d7ec3e526db9f7fdefb84cff7ae','appVersion':'0.1.78','nativeRecompiled':False,'wholeCoreCandidateQualified':False,'modelsRun':False,'deviceOrPhoneAccess':False}
def save():(O/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
save()
try:
 artifact=private/'original-native-artifact';artifact.mkdir()
 if spec:
  assert PHASE in {'audio','whole','delivery','actions','context'} and spec['verification']['version'] in {'0.1.79','0.1.80','0.1.81','0.1.82','0.1.83','0.1.84','0.1.87'}
  assert spec['verification']['sameUpgradeIdentity'] and spec['verification']['ciWrapperOverallPassed']
  record.update(appVersion=spec['verification']['version'],appSourceCommit=spec['verification']['sourceCommit'])
  if spec.get('browserAttachmentReceipt'):
   env['COMPANION_ACCEPTANCE_BROWSER_ATTACHMENTS']='1'
   record['browserAttachmentReceiptRequired']=True
 run('download-frozen-native',['gh','run','download',str(spec['buildRun'] if spec else 42563058131),'--repo','Listener-ai-Macau/Companion-Type','--name','companion-windows-candidate-'+record['appSourceCommit'],'--dir',artifact])
 receipt=json.loads((artifact/'result.json').read_text(encoding='utf8'));assert receipt['sourceCommit']==record['appSourceCommit']
 v=spec['verification'] if spec else json.loads((S/'docs/handoffs/windows-file-copy078-20261109/windows-verification.json').read_text(encoding='utf8'))
 assert v['sourceCommit']==record['appSourceCommit'] and v['version']==record['appVersion']
 for row in receipt['nativeFiles']:assert sha(artifact/'windows-bin'/row['path'])==row['sha256']
 # Tauri's documented bundle-type placeholder is the sole packaging patch.
 # The final byte hash must equal the independently extracted/installed MSI
 # payload, not just a matching version label or a renamed older binary.
 raw=(artifact/'windows-bin/companion-type.exe').read_bytes();assert raw.count(b'__TAURI_BUNDLE_TYPE_VAR_UNK')==1
 (native/'companion-type.exe').write_bytes(raw.replace(b'__TAURI_BUNDLE_TYPE_VAR_UNK',b'__TAURI_BUNDLE_TYPE_VAR_MSI'))
 shutil.copy2(artifact/'windows-bin/companion_type_lib.dll',native/'companion_type_lib.dll')
 assert sha(native/'companion-type.exe')==v['embeddedExeSha256'];assert sha(native/'companion_type_lib.dll')==v['dllSha256']
 verification=product/'docs/handoffs/20261109-windows-file-copy078';verification.mkdir(parents=True)
 (verification/'windows-verification.json').write_text(json.dumps(v,ensure_ascii=False),encoding='utf8')
 env['COMPANION_ACCEPTANCE_VERIFICATION']=str(verification/'windows-verification.json')
 record.update(exactMsiExeSha256=v['embeddedExeSha256'],exactMsiDllSha256=v['dllSha256'],frozenNativeBytesMatchedApprovedMsi=True);save()
 if PHASE in {'audio','whole','delivery','context'}:
  public=private/'public-input';public.mkdir();audio=public/'public-audio-S_R004S03C01.wav'
  with audio.open('wb') as dest,(O/'download-public-audio.log').open('wb') as log:
   download=subprocess.run(['gh','api','repos/Listener-ai-Macau/Companion-Type/releases/assets/726625128','-H','Accept: application/octet-stream'],env=env,stdout=dest,stderr=log,cwd=S)
  assert download.returncode==0 and sha(audio)=='82ac9f8b25e2c085b2e0434e444727af0577e373ed5e1f587d3f28881862fe2f','The public audio must match its frozen source'
  record['publicAudio']={'meeting':'S_R004S03C01','seconds':2327.119,'sha256':sha(audio),'bytes':audio.stat().st_size,'privateDraftAsset':726625128};save()
 if PHASE=='whole':
  component=spec['fixedProductAsr'];bundle=private/'fixed-product-asr.zip';model=private/'fixed-product-asr';model.mkdir()
  with bundle.open('wb') as dest,(O/'download-fixed-product-asr.log').open('wb') as log:
   download=subprocess.run(['gh','api','repos/Listener-ai-Macau/Companion-Type/releases/assets/'+str(component['privateDraftAsset']),'-H','Accept: application/octet-stream'],env=env,stdout=dest,stderr=log,cwd=S)
  assert download.returncode==0 and sha(bundle)==component['bundleSha256']
  with zipfile.ZipFile(bundle) as archive:
   assert set(archive.namelist())==set(component['files'])|{'funasr-paraformer-large-zh-2024/ready'}
   archive.extractall(model)
  for name,digest in component['files'].items():assert sha(model/name)==digest,name
  assert (model/'funasr-paraformer-large-zh-2024/ready').read_text(encoding='ascii').strip()==component['readyValue']
  env['COMPANION_ACCEPTANCE_FIXED_ASR_ROOT']=str(model)
  record.update(modelsRun=True,localModelsRun=False,modelTrainingRun=False,productProvider='local-paraformer-official',modelSelectionChanged=False,fixedProductAsrBundleSha256=component['bundleSha256']);save()
 if PHASE=='delivery':
  previous=private/'actual-asr-artifact';previous.mkdir()
  run('download-actual-same-meeting-asr',['gh','run','download',str(spec['sameMeetingAsrRun']),'--repo','Listener-ai-Macau/Companion-Type','--name','companion-core-audio-'+spec['sameMeetingAsrTestSource'],'--dir',previous])
  prior=json.loads((previous/'result.json').read_text(encoding='utf8'));assert prior['state']=='WINDOWS079_SAME_PUBLIC_AUDIO_IMPORT_AND_PRODUCT_ASR_PASSED_AI_CONTINUES'
  material=private/'same-meeting-material';material.mkdir();manifest=json.loads((previous/'same-meeting-state/manifest.json').read_text(encoding='utf8'))
  assert manifest['sourceAudioSha256']==record['publicAudio']['sha256'] and sha(previous/'same-meeting-state/decoded.wav')==manifest['decodedAudioSha256']
  shutil.copy2(previous/'same-meeting-state/decoded.wav',material/'decoded.wav');shutil.copy2(audio,material/'original.wav')
  (material/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf8');env['COMPANION_ACCEPTANCE_WHOLE_DELIVERY_DIR']=str(material)
 for key in ['GH_TOKEN','GITHUB_TOKEN','ACTIONS_RUNTIME_TOKEN','ACTIONS_ID_TOKEN_REQUEST_TOKEN']:env.pop(key,None)
 run('install-test-dependencies',[sys.executable,'-m','pip','install','--disable-pip-version-check','psutil==7.2.2','pypdf==6.11.0'])
 run('install-locked-node-tools',['npm.cmd','ci','--no-audit','--no-fund'])
 if PHASE=='context':
  run('install-native-picker-dependency',[sys.executable,'-m','pip','install','--disable-pip-version-check','comtypes==1.4.16'])
  tool=S/'tools/qa/core_acceptance20261109'
  code=run('native-image-context-ui',[sys.executable,tool/'windows_meeting.py','--stage','context','--audio',audio],required=False)
  cases=product/'docs/handoffs/20261109-core-acceptance';paths=list(cases.iterdir());assert len(paths)==1
  result=json.loads((paths[0]/'result.json').read_text(encoding='utf8'));record.update(nativeUiExitCode=code,nativeUiState=result['state']);save();assert code==0
  assert result['ui']['state']=='REAL_TAURI_PUBLIC_AUDIO_IMAGE_NOTE_CANCEL_REJECT_EDIT_REOPEN_TIME_AND_SELECTED_ZIP_PASSED'
  backend=run('native-image-context-backup-restore-cleanup',[sys.executable,tool/'windows_context_backend.py','--case',paths[0]],required=False)
  detail=json.loads((paths[0]/'context-backend/result.json').read_text(encoding='utf8'));record.update(contextBackendExitCode=backend,contextBackendState=detail['state']);save();assert backend==0
  assert detail['state']=='ACTUAL_PACKAGED_IMAGE_CONTEXT_BACKUP_RESTORE_PREVIEW_TRASH_RESTORE_AND_EXACT_PURGE_PASSED'
  assert sha(audio)==record['publicAudio']['sha256']
  record.update(state='WINDOWS'+spec['verification']['version'].split('.')[-1].zfill(3)+'_REAL_PUBLIC_AUDIO_IMAGE_CONTEXT_UI_AND_BACKUP_RESTORE_CLEANUP_PASSED',modelsRun=False,sourceAudioUnchanged=sha(audio)==record['publicAudio']['sha256'],wholeCoreCandidateQualified=False)
 elif PHASE=='actions':
  fixture=S/spec['actionsFixture'];assert sha(fixture)==spec['actionsFixtureSha256']
  source_row=json.loads(fixture.read_text(encoding='utf8'))
  code=run('native-saved-action-followup',[sys.executable,S/'tools/qa/core_acceptance20261109/windows_meeting.py','--stage','actions','--reviewed-ai',fixture],required=False)
  cases=product/'docs/handoffs/20261109-core-acceptance';paths=list(cases.iterdir());assert len(paths)==1
  result=json.loads((paths[0]/'result.json').read_text(encoding='utf8'));record.update(nativeUiExitCode=code,nativeUiState=result['state']);save();assert code==0
  assert result['ui']['state']=='REAL_TAURI_SAVED_ACTION_FILTER_FOLLOWUP_NATIVE_COPY_AND_DURABLE_COMPLETION_PASSED'
  after=json.loads((Path(result['privateRoot'])/'state/sessions.json').read_text(encoding='utf8'))[0]
  for key in ['transcriptText','utterances','transcriptReview']:assert after[key]==source_row[key],key+' must stay unchanged by action completion'
  original=source_row['minutesByMode']['offlineStore']['markdown'].strip();target='- 待核对：制作广告宣传海报'
  assert original.splitlines().count(target)==1
  expected='\n'.join('- [ ] 待核对：制作广告宣传海报' if line==target else line for line in original.split('\n'))
  assert after['minutes']['markdown']==expected and after['minutesByMode']['offlineStore']['markdown']==expected
  assert after['minutes']['source']=='userEdited','A completion edit must keep the existing manual provenance'
  record.update(state='WINDOWS082_NATIVE_ACTION_FILTER_FOLLOWUP_COPY_AND_REOPEN_PASSED',rawAsrUnchanged=True,savedMarkdownOnlyIntentionalUncheckedMarkerChanged=True,existingManualEditProvenancePreserved=True,nativeClipboardMatched=result['ui']['nativeClipboard']['actualWindowsUnicodeClipboardMatched'],nativeActionUi=result['ui'],modelsRun=False,newCloudOrAsrCalls=0,saleQualified=False)
 elif PHASE=='delivery':
  run('install-native-picker-dependency',[sys.executable,'-m','pip','install','--disable-pip-version-check','comtypes==1.4.16'])
  fixture=S/spec['sameMeetingAiFixture'];assert sha(fixture)==spec['sameMeetingAiFixtureSha256']
  source_row=json.loads(fixture.read_text(encoding='utf8'));assert source_row['id']==manifest['sessionId'] and hashlib.sha256(source_row['transcriptText'].encode('utf8')).hexdigest()==manifest['rawTranscriptSha256']
  tool=S/'tools/qa/core_acceptance20261109';code=run('same-real-audio-asr-ai-ui-and-word',[sys.executable,tool/'windows_meeting.py','--stage','ai','--reviewed-ai',fixture],required=False)
  cases=product/'docs/handoffs/20261109-core-acceptance';paths=list(cases.iterdir());assert len(paths)==1
  result=json.loads((paths[0]/'result.json').read_text(encoding='utf8'));record.update(nativeUiExitCode=code,nativeUiState=result['state']);save();assert code==0 and result['ordinaryRecipientTested']
  root=Path(result['privateRoot']);details=O/'same-meeting-delivery';details.mkdir()
  base_env={**env,'COMPANION_TYPE_STATE_PATH':str(root/'state/sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(root/'recordings'),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(root/'product-settings.json'),'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1'}
  def native_call(name,flag,payload,environment=base_env):
   request=details/(name+'-request.json');dest=details/(name+'-result.json');request.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8')
   run(name,[root/'app/companion-type.exe',flag,request,dest],environment=environment)
   return json.loads(dest.read_text(encoding='utf8'))
  before=native_call('01-reopen-after-real-ui','--local-recording-snapshot',{})['snapshot']['host']['sessions'][0]
  for key in ['transcriptText','utterances','minutes','minutesByMode']:assert before[key]==source_row[key],key
  backup_dir=root/'backups';backup_dir.mkdir();backup=native_call('02-backup-same-audio-asr-ai','--library-backup-request',{'directory':str(backup_dir)})
  restored=root/'restored-library';restored.mkdir();(restored/'recordings').mkdir()
  restored_env={**base_env,'COMPANION_TYPE_STATE_PATH':str(restored/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(restored/'recordings')}
  native_call('03-restore-audio-asr-ai-to-fresh-library','--library-restore-request',{'directory':backup['path']},restored_env)
  after=native_call('04-reopen-restored-same-meeting','--local-recording-snapshot',{},restored_env)['snapshot']['host']['sessions'][0]
  for key in ['id','title','transcriptText','utterances','minutes','minutesByMode']:assert after[key]==before[key],key
  assert sha(after['audioPath'])==manifest['decodedAudioSha256']
  original=next(c for c in after['chunks'] if c['status']=='importedOriginal');assert sha(original['path'])==manifest['sourceAudioSha256']
  assert sha(audio)==manifest['sourceAudioSha256'];record.update(state='WINDOWS_SAME_REAL_AUDIO_PRODUCT_ASR_AI_DOCUMENT_BACKUP_REOPEN_PASSED',sameMeeting=manifest,sameAudioAndActualAsrAiLineageVerified=True,actualWordReceived=True,rawAsrAndAiUnchangedByUi=True,rawOriginalAndDecodedAudioRestoredByteIdentical=True,newCloudOrAsrCallsThisDeliveryStage=0,wholeCoreCandidateQualified=False,saleQualified=False)
 elif PHASE=='whole':
  run('install-native-picker-dependency',[sys.executable,'-m','pip','install','--disable-pip-version-check','comtypes==1.4.16'])
  tool=S/'tools/qa/core_acceptance20261109';code=run('same-public-audio-import-and-product-asr',[sys.executable,tool/'windows_meeting.py','--stage','transcribe','--audio',audio],required=False)
  cases=product/'docs/handoffs/20261109-core-acceptance';paths=list(cases.iterdir());assert len(paths)==1
  result=json.loads((paths[0]/'result.json').read_text(encoding='utf8'));record.update(nativeUiExitCode=code,nativeUiState=result['state']);save()
  assert code==0 and result['state']=='REAL_NATIVE_FIXED_PRODUCT_AUDIO_TRANSCRIPTION_PASSED'
  root=Path(result['privateRoot']);rows=json.loads((root/'state/sessions.json').read_text(encoding='utf8'));rows=[r for r in rows if r['source']=='importedAudio'];assert len(rows)==1
  row=rows[0];assert row['transcriptFinal'] and len(row['transcriptText'])>1000 and row['utterances']
  original=next(c for c in row['chunks'] if c['status']=='importedOriginal');assert sha(original['path'])==record['publicAudio']['sha256']
  dest=O/'same-meeting-state';dest.mkdir();shutil.copy2(row['audioPath'],dest/'decoded.wav')
  (dest/'session.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  manifest={'sessionId':row['id'],'sourceAudioSha256':sha(original['path']),'decodedAudioSha256':sha(dest/'decoded.wav'),'sourceOriginalPath':original['path'],'sourceDecodedPath':row['audioPath'],'rawTranscriptSha256':hashlib.sha256(row['transcriptText'].encode('utf8')).hexdigest(),'utterances':len(row['utterances']),'transcriptCharacters':len(row['transcriptText']),'durationMs':row['durationMs'],'asrSeconds':result['ui']['asrSeconds'],'productProvider':'local-paraformer-official','modelQualityQualified':False,'sourceAndWeightsUnchanged':True}
  (dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  record.update(state='WINDOWS079_SAME_PUBLIC_AUDIO_IMPORT_AND_PRODUCT_ASR_PASSED_AI_CONTINUES',sameMeeting=manifest,wholeCoreCandidateQualified=False);save()
 elif PHASE=='audio':
  run('install-native-picker-dependency',[sys.executable,'-m','pip','install','--disable-pip-version-check','comtypes==1.4.16'])
  tool=S/'tools/qa/core_acceptance20261109'
  gui_code=run('native-public-audio-flow',[sys.executable,tool/'windows_meeting.py','--stage','audio','--audio',audio],required=False);record['nativeUiExitCode']=gui_code
  cases=product/'docs/handoffs/20261109-core-acceptance';gui=list(cases.iterdir());assert len(gui)==1
  result=json.loads((gui[0]/'result.json').read_text(encoding='utf8'));record['nativeUiState']=result['state']
  root=Path(result['privateRoot']);library=root/'state/sessions.json'
  reopen_env={**env,'COMPANION_TYPE_STATE_PATH':str(library),'COMPANION_TYPE_RECORDING_DIR':str(root/'recordings'),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(root/'product-settings.json'),'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1'}
  request=gui[0]/'reopen-audio-request.json';request.write_text('{}',encoding='utf8')
  reopened=gui[0]/'reopen-audio-result.json'
  reopen_code=run('reopen-audio-library',[root/'app/companion-type.exe','--local-recording-snapshot',request,reopened],environment=reopen_env,required=False)
  if reopened.exists():
   snapshot=json.loads(reopened.read_text(encoding='utf8'))['snapshot'];rows=[r for r in snapshot['host']['sessions'] if r['source']=='importedAudio']
   record['reopenedImports']=[{'id':r['id'],'title':r['title'],'durationMs':r['durationMs'],'audioStored':r['audioStored'],'originalChunks':sum(c['status']=='importedOriginal' for c in r['chunks'])} for r in rows]
   if gui_code==0:
    assert len(rows)==2 and all(r['audioStored'] and abs(r['durationMs']-2327119)<600 for r in rows)
    copied_mp3=next(f for f in result['receivedFiles'] if f['fileName'].endswith('.mp3'))
    expected={audio.stem:record['publicAudio']['sha256'],Path(copied_mp3['fileName']).stem:copied_mp3['sha256']}
    for row in rows:
     original=next(c for c in row['chunks'] if c['status']=='importedOriginal')
     assert sha(original['path'])==expected[row['title']] and original['id'].endswith(expected[row['title']])
    record['reimportedOriginalsBoundToActualWavAndDeliveredMp3']=True
  if (root/'exports/original.wav').exists():assert sha(root/'exports/original.wav')==record['publicAudio']['sha256'];record['savedOriginalByteIdentical']=True
  payload=root/'exports/compatible.mp3'
  if payload.exists():
   folder=O/'public-audio-output';folder.mkdir();shutil.copy2(payload,folder/payload.name);record['mp3Output']={'sha256':sha(payload),'bytes':payload.stat().st_size,'preservedInCiArtifact':True}
  assert sha(audio)==record['publicAudio']['sha256'];record['originalInputUnchanged']=True
  record['state']='WINDOWS_REAL_PUBLIC_AUDIO_IMPORT_PLAYBACK_DELIVERY_REOPEN_PASSED' if gui_code==0 and reopen_code==0 else 'WINDOWS_REAL_PUBLIC_AUDIO_FLOW_NOT_QUALIFIED_FAILURE_RETAINED'
  assert gui_code==0 and reopen_code==0,'Real audio flow remains unqualified; preserve the actual failing stage'
  if spec:
   fixture=S/spec['reviewedAiFixture'];assert sha(fixture)==spec['reviewedAiFixtureSha256']
   before=json.loads(fixture.read_text(encoding='utf8'))
   ai_code=run('native-reviewed-ai-reading-and-export',[sys.executable,tool/'windows_meeting.py','--stage','ai','--reviewed-ai',fixture],required=False)
   ai_cases=[p for p in cases.iterdir() if p.is_dir() and p!=gui[0]];assert len(ai_cases)==1
   ai=json.loads((ai_cases[0]/'result.json').read_text(encoding='utf8'));record['reviewedAiUi']={'exitCode':ai_code,'state':ai['state'],'ordinaryFileReceived':ai.get('ordinaryRecipientTested',False),'cachedRealCloudAi':True,'newCloudCalls':0,'newAsrRun':False}
   if ai_code==0:
    after=json.loads((Path(ai['privateRoot'])/'state/sessions.json').read_text(encoding='utf8'))[0]
    for key in ['transcriptText','utterances','transcriptReview','minutes','minutesByMode']:assert after[key]==before[key],key+' changed during reading and export'
    record['publicRawReviewAndAiUnchangedByReadingAndExport']=True
   assert ai_code==0 and ai.get('ordinaryRecipientTested',False),'Grouped candidate AI reading/export remains unqualified'
   record['state']='WINDOWS079_GROUPED_AUDIO_REVIEWED_AI_AND_DELIVERY_RUNTIME_PASSED'
 else:
  run('current-source-typecheck',['node',S/'node_modules/typescript/bin/tsc','--project',S/'apps/windows/tsconfig.json','--noEmit'])
  record['currentUiSourceTypecheckOnly']=True;record['currentUiSourcePackaged']=False;save()
  tool=S/'tools/qa/core_acceptance20261109'
  code=run('saved-meeting-backend',[sys.executable,tool/'windows_saved_meeting.py'],required=False);record['backendExitCode']=code;save()
  cases=product/'docs/handoffs/20261109-core-acceptance';saved=list(cases.glob('saved-*'));assert len(saved)==1
  backend=json.loads((saved[0]/'result.json').read_text(encoding='utf8'));record['backendState']=backend['state']
  assert (saved[0]/'10-reopen-after-document-result.json').is_file(),'Native UI input was not prepared; never substitute a demo'
  gui_code=run('native-ui-and-file-receiver',[sys.executable,tool/'windows_meeting.py','--stage','handoff','--library',saved[0]],required=False);record['nativeUiExitCode']=gui_code
  gui=[p for p in cases.iterdir() if p.is_dir() and not p.name.startswith('saved-')];assert len(gui)==1
  native_result=json.loads((gui[0]/'result.json').read_text(encoding='utf8'));record['nativeUiState']=native_result['state']
  record['ordinaryReceiverPassed']=native_result.get('ordinaryRecipientTested',False)
  record['receiverScope']='Windows standard Shell Paste; third-party messengers and actual sending remain unqualified'
  record['state']='WINDOWS_SAVED_MEETING_AND_SHELL_FILE_HANDOFF_PASSED' if code==0 and gui_code==0 and record['ordinaryReceiverPassed'] else 'WINDOWS_CORE_WORKFLOW_NOT_QUALIFIED_FAILURES_RETAINED'
  assert code==0 and gui_code==0 and record['ordinaryReceiverPassed'],'One or more core software stages remain unqualified'
except BaseException as error:
 record.setdefault('error',repr(error));record['state']='WINDOWS_CORE_WORKFLOW_NOT_QUALIFIED_FAILURES_RETAINED'
 (O/'failure.txt').write_text(traceback.format_exc(),encoding='utf8');raise
finally:
 source=product/'docs/handoffs/20261109-core-acceptance'
 if source.exists():shutil.copytree(source,O/'workflow-evidence',dirs_exist_ok=True)
 record['finishedAt']=datetime.now(timezone.utc).isoformat();save()
