"""Complete the same public comparison recording, without supplying reference text."""
from pathlib import Path
from datetime import datetime
import json,os,subprocess,hashlib,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');V=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/notebook-foundation20261113/real-chinese019f118-r3/volume-reference');O=V/'comparison-analysis-r2';L=V/'capture-normalized-r1/short/library';receipt=O/'minutes-export-reopen.json';assert not receipt.exists()
asr=json.loads((O/'result.json').read_bytes());rows=json.loads((L/'sessions.json').read_bytes());assert len(rows)==1 and rows[0]['id']==asr['sessionId']
exe=Path('C:/Program Files/Companion Type/companion-type.exe');proof=json.loads((R/'docs/handoffs/20261112-product-closure/windows118/windows-verification.json').read_bytes());assert hashlib.sha256(exe.read_bytes()).hexdigest()==proof['embeddedExeSha256']
env={k:v for k,v in os.environ.items()if not k.startswith(('COMPANION_TYPE_TRANSCRIPT','COMPANION_TYPE_ASR_COMMAND','COMPANION_TYPE_MINUTES_COMMAND'))};env.update(COMPANION_TYPE_STATE_PATH=str(L/'sessions.json'),COMPANION_TYPE_RECORDING_DIR=str(L/'recordings'),COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_DISABLE_AUTO_RECONNECT='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1');env.pop('PSModulePath',None);env.pop('COMPANION_TYPE_PRODUCT_SETTINGS_PATH',None)
result=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='REVIEWED_PUBLIC01A0_STANDARD_MINUTES_EXPORT_REOPEN_IN_PROGRESS',sessionId=asr['sessionId'],textReview='Read the actual441-character local recognition. Public retail meeting: sales/display, reports, incoming/outgoing goods, poor-selling product removal proposed for discussion. No names or identifiable private information. Final short ambiguous voice fragment retained without treating it as a decision.',localTextReviewedBeforeCloud=True,cloudAudioUpload=False,old019eRead=False,referenceTextFed=False,steps=[])
def write():receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def request(name,flag,value,dest):
 p=O/(name+'-request.json');assert not p.exists();p.write_text(json.dumps(value,ensure_ascii=False),encoding='utf8');start=time.monotonic()
 with(O/(name+'.log')).open('xb')as log:run=subprocess.run([str(exe),flag,str(p),str(dest)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
 result['steps'].append(dict(name=name,exitCode=run.returncode,seconds=round(time.monotonic()-start,3)));write();assert run.returncode==0
try:
 write();request('standard-minutes','--meeting-minutes-request',dict(action='meetingGenerateMinutes',sessionId=asr['sessionId'],meetingMode='offlineStore',minutesTemplate=dict(id='meeting')),O/'minutes.json')
 row=json.loads((O/'minutes.json').read_bytes());minutes=row['minutesByMode']['offlineStore'];assert minutes['source']=='llm_deepseek'and minutes['markdown'].strip()and row['transcriptText']==rows[0]['transcriptText']
 request('readable-export','--meeting-export-request',dict(sessionId=asr['sessionId'],meetingMode='offlineStore',format='txt',contentSections=dict(minutes=True,transcript=True,highlights=False,timeline=False,noteIds=[])),O/'public-human-readable.txt')
 before=json.loads((L/'sessions.json').read_bytes());request('process-reopen','--local-recording-snapshot',{},O/'reopened.json');assert before==json.loads((O/'reopened.json').read_bytes())['snapshot']['host']['sessions']
 for name,digest in asr['originalAudioFiles'].items():assert hashlib.sha256(Path('\\\\?\\'+str((L/'recordings'/name).resolve())).read_bytes()).hexdigest()==digest
 result.update(state='NORMALIZED_PUBLIC01A0_REAL_ASR_STANDARD_MINUTES_READABLE_EXPORT_CLI_REOPEN_COMPLETED',minutesSource=minutes['source'],minutesCharacters=len(minutes['markdown']),originalAudioUnchanged=True,actualGuiReviewed=False,modelGeneralQualityQualified=False,ownerAudibilityAccepted=False)
except BaseException as error:result.update(state='NORMALIZED_PUBLIC01A0_CHAIN_STOPPED_EVIDENCE_RETAINED',error=repr(error));raise
finally:result['finishedAt']=datetime.now().astimezone().isoformat(timespec='seconds');write();print(json.dumps(result,ensure_ascii=False),flush=True)
