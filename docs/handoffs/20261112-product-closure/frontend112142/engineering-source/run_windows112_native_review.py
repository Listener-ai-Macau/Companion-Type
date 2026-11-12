"""New UI routes on exact112; reuse only independently unchanged OS backend/operation code."""
from pathlib import Path
from datetime import datetime
import json,hashlib,subprocess,os,re,tomllib
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=r/'companion-device-closure055';batch=r/'docs/handoffs/20261112-product-closure/windows112';out=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/windows112/native-background-r1')
proof=json.loads((batch/'windows-verification.json').read_bytes());prior=json.loads((batch.parent/'runtime-result.json').read_bytes());template=json.loads((batch.parent/'windows110/unchanged-os-handoff-evidence.json').read_bytes());old=prior['appSourceCommit'];new=proof['sourceCommit'];assert prior['state']=='WINDOWS109_COHERENT_NATIVE_MEETING_JOURNEY_PASSED'
def blob(ref,path):return subprocess.check_output(['git','show',ref+':'+path],cwd=s)
stable=[row for row in template['exactCommittedFiles']if row['path']!='packages/ui/src/ContentExportPanel.tsx'];assert len(stable)==7
for row in stable:assert blob(old,row['path'])==blob(new,row['path']) and hashlib.sha256(blob(new,row['path'])).hexdigest()==row['committedBlobSha256']
ui_path='packages/ui/src/ContentExportPanel.tsx'
def operations(ref):
 text=blob(ref,ui_path).decode().replace('\r\n','\n');return text[text.index('export function ContentExportPanel'):text.index(' return <details ref={panel}')].encode()
assert operations(old)==operations(new)
op_hash=hashlib.sha256(operations(new)).hexdigest()
for row in template['exactCommandBlocks']:
 chunks=blob(new,row['path']).decode().replace('\r\n','\n').split('#[tauri::command]');found=[x for x in chunks if re.match(r'\s*pub (?:async )?fn '+row['command']+r'\(',x)];assert len(found)==1 and hashlib.sha256(found[0].encode()).hexdigest()==row['normalizedLfBlockSha256']
names={'rfd','tauri','tauri-runtime','tauri-runtime-wry','wry','clipboard-win','windows','windows-core'};locks=[tomllib.loads(blob(c,'apps/windows/src-tauri/Cargo.lock').decode())for c in [old,new]];assert [[x for x in v['package']if x['name']in names]for v in locks][0]==[[x for x in v['package']if x['name']in names]for v in locks][1]
reuse={k:v for k,v in template.items()if '110'not in k};reuse.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='UNCHANGED_OS_BACKEND_WITH_CHANGED_UI_ROUTE_RECHECKED',currentAppSourceCommit=new,exactCommittedFiles=stable,uiExportStateAndOperations={'path':ui_path,'scope':'Entire component state, selection binding, request construction and operation implementation before JSX rendering','normalizedLfSha256':op_hash,'priorNormalizedLfSha256':op_hash,'bytes':len(operations(new)),'uiRenderingChanged':True},newOrdinaryRecipientTested=False,nativeSystemOperationsOn112Retested=False,currentNativeUiRouteRechecked=False)
out.mkdir(exist_ok=False);env={**os.environ,'COMPANION_ACCEPTANCE_PROJECT_ROOT':str(out/'product'),'COMPANION_ACCEPTANCE_CACHE':str(out/'private'),'COMPANION_ACCEPTANCE_VERIFICATION':str(batch/'windows-verification.json'),'COMPANION_ACCEPTANCE_FROZEN_NATIVE':proof['nativeRoot'],'COMPANION_ACCEPTANCE_VERIFY_DATE_ONLY':'1'}
with (out/'runner.log').open('wb')as log:run=subprocess.run(['python',str(s/'tools/qa/core_acceptance20261109/windows_meeting.py'),'--stage','product-background'],cwd=s,env=env,stdout=log,stderr=subprocess.STDOUT)
assert run.returncode==0,(out/'runner.log').read_text(encoding='utf-8',errors='replace')[-2500:]
cases=list((out/'product/docs/handoffs/20261109-core-acceptance').iterdir());assert len(cases)==1;detail=json.loads((cases[0]/'result.json').read_bytes());assert detail['state']=='REAL_NATIVE_COHERENT_BACKGROUND_PRODUCT_JOURNEY_PASSED' and detail['ui']['dateOnlyCalendarSavedAndReopened'] and detail['ui']['exactSelectedNote']
reuse.update(currentNativeUiRouteRechecked=True,currentNativeUiEvidence=str(cases[0]/'result.json'))
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'WINDOWS112_COHERENT_BACKGROUND_JOURNEY_PASSED_WITH_OS_BACKEND_EVIDENCE_REUSED','testSourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip(),'appSourceCommit':new,'appVersion':'0.1.112','nativeRecompiled':False,'nativeUiExitCode':0,'nativeUiState':detail['state'],'nativeUiEvidence':str(cases[0]/'result.json'),'newDateOnlySavedAndReopened':True,'desktopIsolation':detail['desktopIsolation'],'ownerKeyboardMouseOrForegroundControlUsed':False,'ownerClipboardSequenceUnchangedAtObservation':detail['ownerClipboardSequenceUnchangedAtObservation'],'newNativeSaveCancelOrOrdinaryRecipientRetested':False,'unchangedOsHandoffEvidence':reuse,'hostedRuntimeRun':None,'modelsRun':False,'deviceOrPhoneAccess':False,'saleQualified':False}
for path,data in [(batch/'runtime-result.json',record),(batch/'unchanged-os-handoff-evidence.json',reuse)]:path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items()if k!='unchangedOsHandoffEvidence'},ensure_ascii=False))
