"""Continuous saved-meeting backend journey on a real cached public ASR result.

No ASR/model/AI service call, device, GUI, synthetic capture or demo fallback.
Uses the production app CLI and explicit isolated library for every operation.
Manual annotations/documents are labeled as such and never meeting ground truth.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import ctypes,hashlib,json,os,sys,time,uuid,zipfile,xml.etree.ElementTree as ET
import psutil
from windows_meeting import S,R,C,D,K,w,ExtendedLimits,CpuRate,require,spawn,alive,sha,frozen_app,CPU_PERCENT

def main():
 psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
 defer_pdf='--defer-pdf' in sys.argv[1:]
 positional=[value for value in sys.argv[1:] if not value.startswith('--')]
 resume=Path(positional[0]).resolve() if positional else None
 previous=json.loads((resume/'result.json').read_text(encoding='utf8')) if resume else None
 if resume:
  assert resume.parent==C.resolve() and resume.name.startswith('saved-')
  out=resume;root=Path(previous['root']).resolve();assert root.parent==D.resolve()
  app=root/'app';version=json.loads((R/'docs/handoffs/20261109-windows-file-copy078/windows-verification.json').read_text(encoding='utf8'));assert sha(app/'companion-type.exe')==version['embeddedExeSha256']
 else:
  token='saved-'+uuid.uuid4().hex;root=D/token;root.mkdir(parents=True);out=C/token;out.mkdir(parents=True);app,version=frozen_app(root)
 source=Path(__file__).parent/'fixtures/public-S_R004S03C01-saved-asr.json'
 assert sha(source)=='543423e146ab4f5deb03d27d0d85e25fc2fe0e3dd436e9c82341e372869d5155','The frozen public ASR input changed; do not silently substitute a different meeting'
 output=json.loads(source.read_text(encoding='utf8'));raw_text=output['text'];assert len(raw_text)>8000
 template=json.loads((S/'apps/windows/src-tauri/src/calendar_test_fixtures/p738-sessions.json').read_text(encoding='utf8'))[0]
 row={**template,'id':'core-real-public-S_R004S03C01','title':'公开会议·超市运营与服务改进（软件链验收）','source':'importedTranscript','status':'transcribed','processingPolicy':'manual','startedAt':None,'stoppedAt':None,'durationMs':2327119,'audioPath':None,'audioBytes':0,'audioStored':False,'transcriptText':raw_text,'transcriptFinal':True,'transcriptPreview':raw_text[:160],'utterances':output['utterances'],'transcriptSegments':len(output['utterances']),'minutes':None,'minutesByMode':{},'exportMarkdown':'','exportedAt':None,'calendarCopies':[],'calendarSlotCopies':[],'calendarCopyRevision':0,'noteRevision':0,'meetingNotes':[],'retention':{**template['retention'],'audioCached':False,'minutesCached':False}}
 secondary={**row,'id':'core-secondary-control','title':'明确虚构·不应被修改的对照资料','transcriptText':'第二条资料只用于确认本场编辑不误改其他记录。','transcriptPreview':'第二条资料只用于确认本场编辑不误改其他记录。','utterances':[],'transcriptSegments':0,'durationMs':0}
 for name in ['state','recordings','roaming','local','temp']:(root/name).mkdir(exist_ok=bool(resume))
 state=root/'state/sessions.json'
 if not resume:state.write_text(json.dumps([row,secondary],ensure_ascii=False),encoding='utf8')
 elif previous.get('checkpointStateSha256'):assert sha(state)==previous['checkpointStateSha256']
 else:assert json.loads(state.read_text(encoding='utf8'))==json.loads((out/'07-reopen-after-review-result.json').read_text(encoding='utf8'))['snapshot']['host']['sessions']
 env={**os.environ,'APPDATA':str(root/'roaming'),'LOCALAPPDATA':str(root/'local'),'TEMP':str(root/'temp'),'TMP':str(root/'temp'),'COMPANION_TYPE_STATE_PATH':str(state),'COMPANION_TYPE_RECORDING_DIR':str(root/'recordings'),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(root/'settings.json'),'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1'}
 for name in ['DEEPSEEK_API_KEY','OPENAI_API_KEY','COMPANION_TYPE_ASR_API_KEY','COMPANION_TYPE_VOLC_APP_KEY','COMPANION_TYPE_VOLC_ACCESS_KEY','GH_TOKEN','GITHUB_TOKEN','ACTIONS_RUNTIME_TOKEN','ACTIONS_ID_TOKEN_REQUEST_TOKEN']:env.pop(name,None)
 budget=768*1024**2 if os.environ.get('GITHUB_ACTIONS')=='true' else 256*1024**2
 job=require(K.CreateJobObjectW(None,None));limit=ExtendedLimits();limit.BasicLimitInformation.LimitFlags=0x2000|0x200;limit.JobMemoryLimit=budget;require(K.SetInformationJobObject(job,9,ctypes.byref(limit),ctypes.sizeof(limit)));cpu=CpuRate(5,CPU_PERCENT*100);require(K.SetInformationJobObject(job,15,ctypes.byref(cpu),ctypes.sizeof(cpu)))
 record={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),'state':'RUNNING_SAVED_MEETING_NATIVE_BACKEND_JOURNEY','sourceMeeting':'S_R004S03C01','sourceAudioSeconds':2327.119,'sourceAsrArtifactSha256':sha(source),'frozenAppSource':version['sourceCommit'],'frozenExeSha256':version['embeddedExeSha256'],'root':str(root),'steps':[],'cpuHardCapPercent':CPU_PERCENT,'workerFamilyPrivateCommitCapBytes':budget,'manualDocumentNotAiGenerated':True,'humanSpeakerLabelNotRealIdentityClaim':True,'originalAudioAvailability':'Not imported into this software-only phase; playback/capture remain pending','modelCalls':0,'aiServiceCalls':0,'deviceAccess':False,'phoneAccess':False,'guiWorkflowQualified':False,'wholeCoreCandidateQualified':False}
 if previous:
  assert previous['sourceAsrArtifactSha256']==record['sourceAsrArtifactSha256'] and previous['frozenExeSha256']==record['frozenExeSha256']
  record=previous;record['state']='RESUMING_SAME_SAVED_MEETING_WORKFLOW';record.setdefault('retainedFailures',[]).append({'error':record.pop('error',None),'finishedAt':record.get('finishedAt')});record['toolPreparationCorrection']='Supply expected empty manual version and reviewed source, as required by the existing product contract; no product behavior changed.'
 def save():(out/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 def call(name,flag,request,suffix='json',environment=env,expected_failure=False):
  input_path=out/(name+'-request.json');dest=out/(name+'-result.'+suffix)
  if previous and any(step['name']==name for step in record['steps']):
   assert json.loads(input_path.read_text(encoding='utf8'))==request,'Completed request changed; cannot silently reuse '+name
   return None if expected_failure else json.loads(dest.read_text(encoding='utf8')) if suffix=='json' else dest
  if input_path.exists():
   retained=out/('retained-'+name+'-'+uuid.uuid4().hex);retained.mkdir()
   import shutil
   for p in [input_path,dest,out/(name+'.log')]:
    if p.exists():shutil.copy2(p,retained/p.name)
  input_path.write_text(json.dumps(request,ensure_ascii=False),encoding='utf8');started=time.perf_counter()
  with (out/(name+'.log')).open('wb') as log:
   process=spawn([app/'companion-type.exe',flag,input_path,dest],environment,app,None,job,log)
   try:
    deadline=time.monotonic()+60
    while alive(process) and time.monotonic()<deadline:time.sleep(.1)
    assert not alive(process),name+' exceeded bounded timeout'
    code=w.DWORD();require(K.GetExitCodeProcess(process.process,ctypes.byref(code)))
    assert (code.value!=0 if expected_failure else code.value==0),(name,code.value,(out/(name+'.log')).read_text(encoding='utf8',errors='replace')[-1600:])
   finally:K.CloseHandle(process.process)
  record['steps'].append({'name':name,'exitCode':code.value,'expectedRejection':expected_failure,'seconds':time.perf_counter()-started});save();print('Completed '+name,flush=True)
  if expected_failure:return None
  assert dest.is_file(),name+' did not publish its requested result'
  return json.loads(dest.read_text(encoding='utf8')) if suffix=='json' else dest
 def snapshot(name,environment=env):return call(name,'--local-recording-snapshot',{},environment=environment)['snapshot']
 def current(snap):return next(item for item in snap['host']['sessions'] if item['id']==row['id'])
 try:
  initial=snapshot('01-open-existing-asr');first=current(initial);control=next(x for x in initial['host']['sessions'] if x['id']==secondary['id']);assert first['transcriptText']==raw_text
  renamed=first['title']+' · 已校对';call('02-save-title','--meeting-edit-request',{'sessionId':row['id'],'expectedTitle':first['title'],'title':renamed})
  note_a=json.loads((out/'03-save-explicit-note-request.json').read_text())['noteId'] if previous else str(uuid.uuid4());note_b=json.loads((out/'04-save-excluded-note-request.json').read_text())['noteId'] if previous else str(uuid.uuid4())
  call('03-save-explicit-note','--meeting-note-request',{'sessionId':row['id'],'noteId':note_a,'expectedRevision':0,'action':'add','text':'工程验收补充（不是会议原话）：后续导出必须保留未确认状态。'})
  call('04-save-excluded-note','--meeting-note-request',{'sessionId':row['id'],'noteId':note_b,'expectedRevision':1,'action':'add','text':'EXCLUDED_CORE_NOTE_20261109：本次不应导出的补充。'})
  reopened=snapshot('05-reopen-after-title-notes');saved=current(reopened);assert saved['title']==renamed and saved['noteRevision']==2 and len(saved['meetingNotes'])==2
  utterance=saved['utterances'][0];edited=utterance['text'].replace('呃','',1);assert edited!=utterance['text'],'Fixture must contain an existing filler, not insert content'
  call('06-save-separate-transcript-review','--meeting-edit-request',{'sessionId':row['id'],'transcriptReview':{'expectedTranscriptText':raw_text,'expectedUtterances':saved['utterances'],'expectedRevision':0,'utteranceEdits':[{'index':0,'text':edited,'speakerName':'发言人甲（工程人工标注）'}],'speakerNames':[]}})
  reviewed=current(snapshot('07-reopen-after-review'));assert reviewed['transcriptText']==raw_text and reviewed['utterances']==first['utterances'];assert reviewed['transcriptReview']['revision']==1 and reviewed['transcriptReview']['utteranceEdits'][0]['speakerName']=='发言人甲（工程人工标注）'
  before_stale=sha(state);call('08-reject-stale-title','--meeting-edit-request',{'sessionId':row['id'],'expectedTitle':first['title'],'title':'这个过期草稿不得覆盖新标题'},expected_failure=True);assert sha(state)==before_stale
  document='## Summary\n人工软件验收草稿，不代表AI已生成或会议事实已合格。\n\n## Source Evidence\n'+edited+'\n\n## Action Items\n- [ ] 核对转写中的人名和金额（工程验收自建事项，不是会议决定）'
  reviewed_source='\n'.join(('发言人甲（工程人工标注）: '+edited) if i==0 else utterance['text'] for i,utterance in enumerate(saved['utterances']))
  call('09-create-explicit-manual-document','--meeting-edit-request',{'sessionId':row['id'],'meetingMode':'offlineStore','markdown':document,'expectedMarkdown':'','createManual':{'expectedTranscriptText':reviewed_source,'expectedReviewRevision':1,'expectedNoteRevision':2}})
  written=current(snapshot('10-reopen-after-document'));assert written['minutesByMode']['offlineStore']['markdown']==document
  source_sections={'minutes':False,'transcript':True,'highlights':False,'timeline':True,'noteIds':[]}
  notes_sections={'minutes':True,'transcript':False,'highlights':False,'timeline':False,'noteIds':[note_a]}
  products=[]
  for fmt,sections in [('txt',source_sections),('docx',notes_sections),('pdf',notes_sections)]:
   if fmt=='pdf' and defer_pdf:
    record['pdfAcceptance']={'state':'NOT_QUALIFIED_RESOURCE_DIAGNOSTIC_PENDING','reason':'Prior browser-backed PDF export failed in this256MiB isolated worker while host low-memory was active. Keep original failure; do not infer a product root cause or count a skipped PDF as passed.'};save();continue
   file=call('11-export-'+fmt,'--meeting-export-request',{'sessionId':row['id'],'meetingMode':'offlineStore','format':fmt,'contentSections':sections},suffix=fmt)
   if fmt=='txt':text=file.read_text(encoding='utf8');assert '发言人甲（工程人工标注）' in text and edited[:25] in text
   elif fmt=='docx':
    with zipfile.ZipFile(file) as z:text=''.join(ET.fromstring(z.read('word/document.xml')).itertext())
   else:
    from pypdf import PdfReader
    text='\n'.join(page.extract_text() or '' for page in PdfReader(file).pages)
   assert 'EXCLUDED_CORE_NOTE_20261109' not in text
   if fmt!='txt':assert '人工软件验收草稿' in text and '工程验收补充' in text
   products.append({'format':fmt,'sha256':sha(file),'bytes':file.stat().st_size,'selectedContentVerified':True})
  backup_root=root/'backups';backup_root.mkdir(exist_ok=bool(resume));backup=call('12-backup-reviewed-meeting','--library-backup-request',{'directory':str(backup_root)})
  record['backupReportKeys']=list(backup);record['exports']=products;save()
  recovered=root/'restored-library';recovered.mkdir(exist_ok=bool(resume));(recovered/'recordings').mkdir(exist_ok=bool(resume))
  restored_env={**env,'COMPANION_TYPE_STATE_PATH':str(recovered/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(recovered/'recordings'),'APPDATA':str(recovered/'roaming'),'LOCALAPPDATA':str(recovered/'local')}
  call('12b-restore-backup-into-fresh-library','--library-restore-request',{'directory':backup['path']},environment=restored_env)
  recovered_row=current(snapshot('12c-reopen-restored-library',restored_env))
  for key in ['title','transcriptText','utterances','transcriptReview','meetingNotes','noteRevision','minutesByMode']:assert recovered_row.get(key)==written.get(key),'Backup restore '+key
  # One destructive-looking action is checked only against this new isolated
  # record, using the same protection/recycle-bin rules as the product UI.
  target={'sessionId':row['id'],'expectedRevision':written.get('organization',{}).get('revision',0)}
  protect=call('13-protect-current-meeting','--library-state-request',{'targets':[target],'action':'protect'});protected=current(protect);assert protected['organization']['protected']
  before=sha(state);call('14-reject-protected-trash','--library-state-request',{'targets':[{'sessionId':row['id'],'expectedRevision':protected['organization']['revision']}],'action':'trash'},expected_failure=True);assert sha(state)==before
  unprotect=call('15-unprotect-current-meeting','--library-state-request',{'targets':[{'sessionId':row['id'],'expectedRevision':protected['organization']['revision']}],'action':'unprotect'});unprotected=current(unprotect)
  trashed=call('16-move-to-trash','--library-state-request',{'targets':[{'sessionId':row['id'],'expectedRevision':unprotected['organization']['revision']}],'action':'trash'});trash_row=current(trashed);assert trash_row['organization']['trashedAt']
  restored=call('17-restore-from-trash','--library-state-request',{'targets':[{'sessionId':row['id'],'expectedRevision':trash_row['organization']['revision']}],'action':'restore'});restored_row=current(restored);assert not restored_row['organization'].get('trashedAt')
  final=snapshot('18-reopen-complete-library');final_row=current(final)
  for key in ['transcriptText','utterances','transcriptReview','meetingNotes','noteRevision','minutesByMode']:assert final_row.get(key)==written.get(key),key
  assert next(x for x in final['host']['sessions'] if x['id']==secondary['id'])==control
  record.update(state='SAVED_MEETING_DATA_FLOW_PARTIAL_PDF_UI_AUDIO_AI_PENDING' if defer_pdf else 'SAVED_REAL_ASR_MEETING_LOCAL_REVIEW_EXPORT_BACKUP_RECYCLE_REOPEN_PASSED',originalAsrTextUnchanged=True,originalAsrUtterancesUnchanged=True,separateManualSpeakerAndTextReviewPersisted=True,selectedExportsVerified=True,secondaryRecordUnchanged=True,ordinaryRecipientTested=False,backupRestoredIntoFreshLibraryContentIdentical=True,limits='Real native backend and fresh-process persistence only. Manual document, no new ASR/AI/capture, no native UI or ordinary recipient/phone qualification.')
 except BaseException as error:record.update(state='SAVED_MEETING_WORKFLOW_STOPPED_RETAINED',error=repr(error));save();raise
 finally:
  K.CloseHandle(job);record['checkpointStateSha256']=sha(state);record['finishedAt']=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds');save()
 print(json.dumps({'state':record['state'],'evidence':str(out),'steps':len(record['steps']),'wholeCoreCandidateQualified':False},ensure_ascii=False))
if __name__=='__main__':main()
