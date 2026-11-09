"""Continue the actual imported/audio-transcribed record, not cached ASR text."""
from pathlib import Path
from datetime import datetime
import ast,copy,hashlib,json,os,re,shutil,subprocess,sys,time,uuid
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=R/'docs/handoffs/20261109-core-acceptance';D=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109')
source=D/'same-meeting-asr-ci-42592563926';proof=json.loads((source/'result.json').read_text(encoding='utf8'));assert proof['state']=='WINDOWS079_SAME_PUBLIC_AUDIO_IMPORT_AND_PRODUCT_ASR_PASSED_AI_CONTINUES'
data=source/'same-meeting-state';manifest=json.loads((data/'manifest.json').read_text(encoding='utf8'));row=json.loads((data/'session.json').read_text(encoding='utf8'));raw=copy.deepcopy(row)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert hashlib.sha256(row['transcriptText'].encode('utf8')).hexdigest()==manifest['rawTranscriptSha256']
assert sha(data/'decoded.wav')==manifest['decodedAudioSha256']
original=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/meeting-channel1.wav');assert sha(original)==manifest['sourceAudioSha256']
token='whole-'+uuid.uuid4().hex;root=D/token;root.mkdir();out=C/token;out.mkdir();recordings=root/'recordings';recordings.mkdir();app=root/'app';app.mkdir()
v=json.loads((C/'candidate079/windows-verification.json').read_text(encoding='utf8'))
for name,key in [('companion-type.exe','embeddedExeSha256'),('companion_type_lib.dll','dllSha256')]:
 p=Path('C:/Program Files/Companion Type')/name;assert sha(p)==v[key];shutil.copy2(p,app/name)
old_original=next(c['path'] for c in row['chunks'] if c['status']=='importedOriginal');new_audio=recordings/(row['id']+'.wav');new_original=recordings/(row['id']+'.original.wav');shutil.copyfile(data/'decoded.wav',new_audio);shutil.copyfile(original,new_original)
mapping={row['audioPath']:str(new_audio),old_original:str(new_original)};row['audioPath']=mapping[row['audioPath']]
for chunk in row['chunks']:assert chunk['path'] in mapping;chunk['path']=mapping[chunk['path']]
state=root/'sessions.json';state.write_text(json.dumps([row],ensure_ascii=False),encoding='utf8')
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=128*1024**2)
env={**os.environ,'COMPANION_TYPE_STATE_PATH':str(state),'COMPANION_TYPE_RECORDING_DIR':str(recordings),'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1'}
env.pop('COMPANION_TYPE_PRODUCT_SETTINGS_PATH',None)
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'CONTINUING_ACTUAL_IMPORTED_AND_TRANSCRIBED_MEETING','root':str(root),'sessionId':row['id'],'nativeSource':v['sourceCommit'],'sourceAsrCi':42592563926,'sourceAudioSha256':manifest['sourceAudioSha256'],'decodedAudioSha256':manifest['decodedAudioSha256'],'rawTranscriptSha256':manifest['rawTranscriptSha256'],'rawTranscriptCharacters':len(row['transcriptText']),'productAsrProvider':manifest['productProvider'],'productAsrSeconds':manifest['asrSeconds'],'localModelInferenceOrTraining':False,'publicTextCloudAiOnly':True,'ownerLibraryAccess':False,'steps':[],'wholeCoreCandidateQualified':False,'saleQualified':False}
def save():(out/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def call(name,flag,payload,private=False):
 request=out/(name+'-request.json');request.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8');dest=(root/(name+'.private.json')) if private else out/(name+'.json');started=time.perf_counter()
 with (out/(name+'.log')).open('wb') as log:result=subprocess.run([str(app/'companion-type.exe'),flag,str(request),str(dest)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
 record['steps'].append({'name':name,'exitCode':result.returncode,'seconds':time.perf_counter()-started});save();assert result.returncode==0,name
 return json.loads(dest.read_text(encoding='utf8'))
save()
try:
 ready=call('01-open-same-audio-transcription','--local-recording-snapshot',{},private=True)
 settings=ready['settings'];assert settings['deepseekApiKeySet'] and settings['deepseekMinutesEnabled'] and not settings['storageSaveBlocked']
 generated=call('02-generate-ai-from-actual-audio-asr','--meeting-minutes-request',{'action':'meetingGenerateMinutes','sessionId':row['id'],'meetingMode':'offlineStore'})
 minutes=generated['minutes'];assert minutes['source']=='llm_deepseek' and minutes['quality']=='final' and minutes['processing']['complete']
 for key in ['transcriptText','utterances']:assert generated[key]==raw[key]
 assert sha(new_audio)==manifest['decodedAudioSha256'] and sha(new_original)==manifest['sourceAudioSha256']
 reopened=call('03-reopen-same-audio-ai','--local-recording-snapshot',{},private=True)['snapshot']['host']['sessions'][0]
 for key in ['transcriptText','utterances','minutes','minutesByMode']:assert reopened[key]==generated[key]
 fixture=S/'tools/qa/core_acceptance20261109/fixtures/whole-meeting-ai-session.json';fixture.write_text(json.dumps(generated,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 record.update(state='SAME_REAL_AUDIO_PRODUCT_ASR_AI_GENERATED_AND_REOPENED_DELIVERY_CONTINUES',aiSeconds=record['steps'][1]['seconds'],aiSource=minutes['source'],processing=minutes['processing'],audioAndRawAsrUnchanged=True,newCloudAudioUpload=False,fixtureSha256=sha(fixture),fixture=fixture.relative_to(S).as_posix(),minutesQualityQualified=False)
 sys.path.insert(0,'E:/CodexData/Companion/real-meeting-asr-validation-20261031/evaluation-deps')
 from reference_textgrid_20261104 import read_reference_intervals,PARSER_ID
 from rapidfuzz.distance import Levenshtein
 module=ast.parse((R/'model-research/src/full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf8'));import unicodedata
 scope={'re':re,'unicodedata':unicodedata};exec(compile(ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='normalize'],type_ignores=[]),'<existing-frozen-normalizer>','exec'),scope);normalize=scope['normalize']
 reference=Path('E:/CodexData/Companion/real-meeting-asr-validation-20261031/S_R004S03C01.TextGrid');assert sha(reference)=='ca515d60e370362aebbf481c465dadc0b8f0f0dc6eeb125845edd09f17cee3d3'
 ref=normalize(''.join(r['text'] for r in sorted(read_reference_intervals(reference),key=lambda r:(r['start'],r['end']))));hyp=normalize(raw['transcriptText']);ops=Levenshtein.editops(ref,hyp)
 record['currentProductAsrChronologicalDiagnostic']={'referenceCharacters':len(ref),'hypothesisCharacters':len(hyp),'edits':{kind:sum(op.tag==kind for op in ops) for kind in ['replace','delete','insert']},'cer':len(ops)/len(ref),'referenceParser':PARSER_ID,'referenceSha256':sha(reference),'scope':'Fixed exposed meeting, chronological mixed text only; not per-speaker overlap, DER or cross-meeting qualification','passedBelowFivePercent':len(ops)/len(ref)<.05}
 record['limits']=limits.query();save()
 (C/'same-meeting-ai-current.json').write_text(json.dumps({'evidence':str(out),'root':str(root),'fixture':str(fixture),'fixtureSha256':sha(fixture),'record':record},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps({k:v for k,v in record.items() if k not in ['steps','limits']},ensure_ascii=False),flush=True)
except BaseException as error:record.update(state='SAME_MEETING_AI_CONTINUATION_STOPPED_RETAINED',error=repr(error));save();raise
