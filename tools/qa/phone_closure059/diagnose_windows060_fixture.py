from pathlib import Path
import json,hashlib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows060-word062'
C=Path('E:/CodexData/Companion/.build-cache/windows051')
run=max(C.glob('native060-word062-*'),key=lambda p:p.stat().st_mtime)
fixture=max((p for p in (R/'docs/handoffs/20261105-windows-content051').glob('native-files-*') if (p/'public-session.json').exists()),key=lambda p:p.stat().st_mtime)
row=json.loads((fixture/'public-session.json').read_text(encoding='utf8'))[0]
for name in ['audioPath','deviceRecordingId','deviceRecordingKey','deviceTotalLength','deviceSha256','sourceDeviceId','recorderControl','meetingTracks']:row[name]=None
row.update(audioStored=False,audioBytes=0,chunks=[],status='minutesReady',source='importedTranscript',pendingReason=None,captureIncomplete=False,recorderControlUncertain=False)
row['retention']['audioCached']=False;row['recovery'].update(intent='none',stage='idle',nextRetryAtUnixMs=None)
actual=json.loads((run/'sessions.json').read_text(encoding='utf8'))
diff=[]
def compare(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        for key in a.keys()|b.keys():
            if key not in a or key not in b:diff.append({'path':path+'/'+key,'beforePresent':key in a,'afterPresent':key in b,'before':a.get(key),'after':b.get(key)})
            else:compare(a[key],b[key],path+'/'+key)
    elif isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
        for i,(left,right) in enumerate(zip(a,b)):compare(left,right,path+'/'+str(i))
    elif a!=b:diff.append({'path':path,'before':a,'after':b})
compare([row],actual)
record={'comparison':'Parsed persisted JSON values vs exact public seed; independent of whitespace/key-order normalization','semanticEqual':actual==[row],'differences':diff,'originalUserDataUsed':False,'repeatNativeUiRun':False}
allowed={'/0/'+key for key in ['deviceSha256','pendingReason','deviceRecordingId','deviceTotalLength','meetingTracks','recorderControl','deviceRecordingKey','sourceDeviceId']}
allowed.add('/0/recovery/nextRetryAtUnixMs')
assert {item['path'] for item in diff}==allowed
assert all(item.get('beforePresent') is True and item.get('afterPresent') is False and item.get('before') is None for item in diff)
record.update(publicContentPreserved=True,explanation='All nine differences are null optional properties omitted by the existing explicit serde skip_serializing_if=Option::is_none contract. Transcript, saved minutes, AI material, citations and other values are unchanged. Initial byte-identity assertion was unsuitable for a synthetic seed with explicit nulls; no product repair or repeat UI run required.')
(F/'native-ui/fixture-persistence-diagnosis.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
result_file=F/'native-ui/result.json';prior=result_file.read_bytes()
(F/'native-ui/result-initial-byte-assertion.json').write_bytes(prior)
result=json.loads(prior);result.update(isolatedPublicContentPreserved=True,persistenceDiagnosis='fixture-persistence-diagnosis.json',byteIdentityAssertionFailedButDataChangeNotObserved=True)
result_file.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(record,ensure_ascii=False))
