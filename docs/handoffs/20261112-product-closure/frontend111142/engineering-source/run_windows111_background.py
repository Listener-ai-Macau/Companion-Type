from pathlib import Path
from datetime import datetime
import json,hashlib,subprocess,os,re,tomllib,sys
sys.path.insert(0,str(Path(__file__).parent));from windows_candidate_delivery import sha,write
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');source=r/'companion-device-closure055';batch=r/'docs/handoffs/20261112-product-closure/windows111';cache=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/windows111/native-background-r4')
proof=json.loads((batch/'windows-verification.json').read_bytes());old='cdf2ea0ab1712f67b8c4bce5e7fe38b55a11afdb';new=proof['sourceCommit'];prior=json.loads((batch.parent/'runtime-result.json').read_bytes());assert prior['state']=='WINDOWS109_COHERENT_NATIVE_MEETING_JOURNEY_PASSED'
template=json.loads((batch.parent/'windows110/unchanged-os-handoff-evidence.json').read_bytes())
def blob(commit,path):return subprocess.check_output(['git','show',commit+':'+path],cwd=source)
for item in template['exactCommittedFiles']:assert blob(old,item['path'])==blob(new,item['path']) and hashlib.sha256(blob(new,item['path'])).hexdigest()==item['committedBlobSha256']
for item in template['exactCommandBlocks']:
 chunks=blob(new,item['path']).decode().replace('\r\n','\n').split('#[tauri::command]');found=[x for x in chunks if re.match(r'\s*pub (?:async )?fn '+item['command']+r'\(',x)];assert len(found)==1 and hashlib.sha256(found[0].encode()).hexdigest()==item['normalizedLfBlockSha256']
names={'rfd','tauri','tauri-runtime','tauri-runtime-wry','wry','clipboard-win','windows','windows-core'};locks=[tomllib.loads(blob(c,'apps/windows/src-tauri/Cargo.lock').decode()) for c in [old,new]];rows=[[x for x in value['package'] if x['name'] in names] for value in locks];assert rows[0]==rows[1]
reuse={k:v for k,v in template.items() if '110' not in k};reuse.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),currentAppSourceCommit=new,newOrdinaryRecipientTested=False,nativeSystemOperationsOn111Retested=False)
cache.mkdir(exist_ok=False);env={**os.environ,'COMPANION_ACCEPTANCE_PROJECT_ROOT':str(cache/'product'),'COMPANION_ACCEPTANCE_CACHE':str(cache/'private'),'COMPANION_ACCEPTANCE_VERIFICATION':str(batch/'windows-verification.json'),'COMPANION_ACCEPTANCE_FROZEN_NATIVE':proof['nativeRoot'],'COMPANION_ACCEPTANCE_VERIFY_DATE_ONLY':'1'}
with (cache/'runner.log').open('wb') as log:result=subprocess.run(['python',str(source/'tools/qa/core_acceptance20261109/windows_meeting.py'),'--stage','product-background'],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT)
assert result.returncode==0,(cache/'runner.log').read_text(encoding='utf-8',errors='replace')[-3000:]
cases=list((cache/'product/docs/handoffs/20261109-core-acceptance').iterdir());assert len(cases)==1;detail=json.loads((cases[0]/'result.json').read_bytes());assert detail['state']=='REAL_NATIVE_COHERENT_BACKGROUND_PRODUCT_JOURNEY_PASSED' and detail['ui']['dateOnlyCalendarSavedAndReopened']
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='WINDOWS111_COHERENT_BACKGROUND_JOURNEY_PASSED_WITH_UNCHANGED_OS_HANDOFF_EVIDENCE_REUSED',testSourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip(),appSourceCommit=new,appVersion='0.1.111',nativeRecompiled=False,nativeUiExitCode=0,nativeUiState=detail['state'],nativeUiEvidence=str(cases[0]/'result.json'),newDateOnlySavedAndReopened=True,desktopIsolation=detail['desktopIsolation'],ownerKeyboardMouseOrForegroundControlUsed=False,ownerClipboardSequenceUnchangedAtObservation=detail['ownerClipboardSequenceUnchangedAtObservation'],newNativeSaveCancelOrOrdinaryRecipientRetested=False,unchangedOsHandoffEvidence=reuse,hostedRuntimeRun=None,modelsRun=False,deviceOrPhoneAccess=False,saleQualified=False)
write(batch/'runtime-result.json',record);write(batch/'unchanged-os-handoff-evidence.json',reuse)
print(json.dumps(record,ensure_ascii=False))
