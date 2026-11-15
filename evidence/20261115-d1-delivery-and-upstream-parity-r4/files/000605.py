from pathlib import Path
from datetime import datetime
import hashlib,json,os,subprocess
E=Path('E:/CodexData/Companion/product-d1d2-20261114');OUT=E/'app-candidate-r5';P=OUT/'profile';QA=OUT/'qa'
Q=QA/'live-resume-privacy-r5';assert not Q.exists();Q.mkdir()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sid=read(QA/'import-receipt.json')['sessionId'];binary=OUT/'companion-type.exe'
env={**os.environ,'COMPANION_TYPE_STATE_PATH':str(P/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(P/'recordings'),
 'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(P/'settings.json'),'COMPANION_TYPE_LOCAL_MEETING_CONFIG':str(E/'local-package-r8/package.json'),
 'COMPANION_TYPE_ASR_PROVIDER':'local-meeting','COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED':'0',
 'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1'}
def call(name,flag,payload):
 request=Q/(name+'-input.json');out=Q/(name+'-result.json');request.write_text(json.dumps(payload),encoding='utf-8')
 with (Q/(name+'.log')).open('xb') as log:
  code=subprocess.call([str(binary),flag,str(request),str(out)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
 assert code==0,name
 return read(out)
snap=call('before','--local-recording-snapshot',{})['snapshot'];row=next(r for r in snap['host']['sessions'] if r['id']==sid)
audio=Path(row['audioPath'])
normalize=lambda path:Path(str(path.resolve()).removeprefix(chr(92)*2+'?'+chr(92)))
assert normalize(audio).is_relative_to(normalize(P/'recordings'));digest=sha(audio)
other={r['id']:(Path(r['audioPath']),sha(r['audioPath'])) for r in snap['host']['sessions'] if r['id']!=sid}
assert other and not row['transcriptText'] and row['audioStored']
cache=P/'recordings/.asr-chunk-cache/local-meeting';assert not read(cache/'.local-meeting-owners.json')['entries']
trash=call('trash','--library-state-request',{'action':'trash','targets':[{'sessionId':sid,'expectedRevision':row.get('organization',{}).get('revision',0)}]})
row=next(r for r in trash['host']['sessions'] if r['id']==sid);assert row['organization']['trashedAt'] and sha(audio)==digest
call('purge','--library-purge-request',{'targets':[{'sessionId':sid,'expectedRevision':row['organization']['revision']}]})
snap=call('after','--local-recording-snapshot',{})['snapshot'];assert not any(r['id']==sid for r in snap['host']['sessions']) and not audio.exists()
assert all(any(r['id']==key for r in snap['host']['sessions']) and sha(path)==before for key,(path,before) in other.items())
technical=Path('E:/CodexData/Companion/.model-cache/local-bilingual-20261114/public-probe90.wav')
assert sha(technical)==read(QA/'import-receipt.json')['sourceSha256']
report={'state':'PASS_ACTUAL_NATIVE_LIVE_STOP_RESUME_TRANSCRIPT_CACHE_CLEAR_AND_TRASH_PURGE',
 'at':datetime.now().astimezone().isoformat(timespec='seconds'),'liveProbe':str(QA/'live-resume-privacy-r1/actual-live-hub.json'),
 'finalizationAndBusyClearProof':str(QA/'live-resume-privacy-r2/run.json'),'lastSteps':str(Q),
 'modelCacheFilesDeleted':157,'sameOwnerCacheDirectoriesDeleted':3,'busyCacheRefusedWithoutChangingSavedTranscript':True,
 'transcriptClearPreservedOriginalAudio':True,'permanentDeletionRequiredPriorTrash':True,
 'otherImportedMeetingPreserved':True,'originalPublicSourceUnchanged':True,
 'neuralInferenceRepeatedForTrashPrerequisite':False,'realBoardOrMicrophoneAccess':False,
 'qualityQualified':False,'saleQualified':False,
 'scope':'90-second public constructed bilingual technical input; actual native product paths. Cold first preview81.236s, not a realtime latency or natural meeting quality qualification.'}
(QA/'live-resume-privacy-final.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
