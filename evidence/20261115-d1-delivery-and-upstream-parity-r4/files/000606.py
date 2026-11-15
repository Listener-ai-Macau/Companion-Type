"""Review actual saved full-English output through native product operations."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,subprocess
E=Path('E:/CodexData/Companion/product-d1d2-20261114');OUT=E/'app-candidate-r5';binary=OUT/'companion-type.exe'
QA=OUT/'qa/speaker-review-portability-r1';assert not QA.exists();QA.mkdir()
source=E/'app-candidate-r3/profile';target=OUT/'review-library';(target/'recordings').mkdir(parents=True)
(target/'sessions.json').write_text('[]\n',encoding='utf-8')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
before=sha(source/'sessions.json')
def env(profile):
 return {**os.environ,'COMPANION_TYPE_STATE_PATH':str(profile/'sessions.json'),
  'COMPANION_TYPE_RECORDING_DIR':str(profile/'recordings'),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(profile/'settings.json'),
  'COMPANION_TYPE_LOCAL_MEETING_CONFIG':str(E/'local-package-r8/package.json'),'COMPANION_TYPE_ASR_PROVIDER':'local-meeting',
  'COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED':'0','COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1'}
def call(profile,name,flag,payload,*,raw=False):
 request=QA/(name+'-input.json');dest=QA/(name+'-result.'+('md' if raw else 'json'))
 request.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
 with (QA/(name+'.log')).open('xb') as log:
  code=subprocess.call([str(binary),flag,str(request),str(dest)],env=env(profile),stdout=log,stderr=subprocess.STDOUT,
   timeout=120,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 assert code==0,'Actual native '+name+' failed; evidence preserved'
 return dest.read_text(encoding='utf-8') if raw else read(dest)
(QA/'backups').mkdir()
backup=call(source,'backup','--library-backup-request',{'directory':str(QA/'backups')})
assert backup['sessions']==1 and sha(source/'sessions.json')==before
call(target,'restore','--library-restore-request',{'directory':backup['path']})
snapshot=call(target,'reopen-restored','--local-recording-snapshot',{})['snapshot']
row,=snapshot['host']['sessions'];assert row['durationMs']==2109813 and len(row['utterances'])==852
sid=row['id'];original_text=row['transcriptText'];original_utterances=row['utterances'];unknown=row.get('transcriptUnrecognized',[])
assert unknown and all(row['minutesByMode'][mode]['quality']=='draft' for mode in ['offlineStore','onlineLive'])
original_audio=Path(row['audioPath']);audio_sha=sha(original_audio)
normalized=Path(str(original_audio.resolve()).removeprefix(chr(92)*2+'?'+chr(92)))
assert normalized.is_relative_to(target.resolve())
speaker=next(u['speaker'] for u in original_utterances if u['speaker'] is not None)
name='复核示例A'
edit={'sessionId':sid,'transcriptReview':{'expectedTranscriptText':original_text,'expectedUtterances':original_utterances,
 'expectedRevision':row.get('transcriptReview',{}).get('revision',0),'speakerNames':[{'speaker':speaker,'name':name}]}}
saved=call(target,'name-speaker','--meeting-edit-request',edit);assert saved['persistenceStatus']=='ready' and not saved['reviewStale']
snapshot=call(target,'reopen-named','--local-recording-snapshot',{})['snapshot'];named=next(r for r in snapshot['host']['sessions'] if r['id']==sid)
assert named['transcriptText']==original_text and named['utterances']==original_utterances
assert named['transcriptUnrecognized']==unknown and {'speaker':speaker,'name':name} in named['transcriptReview']['speakerNames']
export=call(target,'export-named','--meeting-export-request',{'sessionId':sid,'meetingMode':'offlineStore','format':'markdown',
 'contentSections':{'minutes':True,'transcript':True,'highlights':False,'timeline':False}},raw=True)
assert name in export and sha(original_audio)==audio_sha
# Return the public example to its original anonymous source after the review
# check, through the product's own restore-original action.
call(target,'restore-original','--meeting-edit-request',{'sessionId':sid,'transcriptReview':{
 'expectedTranscriptText':original_text,'expectedUtterances':original_utterances,
 'expectedRevision':named['transcriptReview']['revision'],'restoreOriginal':True}})
snapshot=call(target,'final-reopen','--local-recording-snapshot',{})['snapshot'];row=next(r for r in snapshot['host']['sessions'] if r['id']==sid)
assert row['transcriptText']==original_text and row['utterances']==original_utterances and row['transcriptUnrecognized']==unknown
assert not row.get('transcriptReview',{}).get('speakerNames') and sha(original_audio)==audio_sha
assert sha(source/'sessions.json')==before
report={'state':'PASS_ACTUAL_FULL_ENGLISH_BACKUP_RESTORE_SPEAKER_REVIEW_REOPEN_EXPORT_AND_RESTORE_ORIGINAL',
 'at':datetime.now().astimezone().isoformat(timespec='seconds'),'sessionId':sid,'profile':str(target),'sourceProfileUnchanged':True,
 'fullMeetingMilliseconds':row['durationMs'],'originalUtterancesPreserved':852,'unknownAudioRangesPreserved':unknown,
 'manualNameAppearedInActualMarkdown':True,'originalAnonymousSourceRestored':True,'originalAudioSha256':audio_sha,
 'newAsrOrSpeakerInferenceCalls':0,'newCloudTextOrMinutesCalls':0,'qualityQualified':False,'saleQualified':False}
(QA/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
