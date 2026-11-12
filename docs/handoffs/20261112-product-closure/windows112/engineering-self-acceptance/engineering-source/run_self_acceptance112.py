"""Owner-requested fresh engineering round; exact installed112, no rebuild/board."""
from pathlib import Path
from datetime import datetime
import os,sys,json,hashlib,subprocess
REOPEN='--resume-reopen' in sys.argv
attempt=int(next((arg.partition('=')[2] for arg in sys.argv if arg.startswith('--attempt=')),'3' if REOPEN else '2'));assert 2<=attempt<=9
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';B=R/'docs/handoffs/20261112-product-closure/windows112';O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/windows112')/('self-acceptance-r'+str(attempt));O.mkdir(exist_ok=False)
proof=json.loads((B/'windows-verification.json').read_bytes());installed=Path('C:/Program Files/Companion Type')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(installed/'companion-type.exe')==proof['embeddedExeSha256'] and sha(installed/'companion_type_lib.dll')==proof['dllSha256']
record=dict(startedAt=datetime.now().astimezone().isoformat(timespec='seconds'),state='INSTALLED112_FRESH_SELF_ACCEPTANCE_RUNNING',appVersion='0.1.112',appSourceCommit=proof['sourceCommit'],installedPayloadMatchedInspectedMsi=True,nativeBuildStarted=False,ownerPromptOpened=False,boardAccessed=False,modelsRun=False,physicalQualified=False,saleQualified=False)
write=lambda:(O/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
write();env={**os.environ,'COMPANION_ACCEPTANCE_PROJECT_ROOT':str(O/'product'),'COMPANION_ACCEPTANCE_CACHE':str(O/'private'),'COMPANION_ACCEPTANCE_VERIFICATION':str(B/'windows-verification.json'),'COMPANION_ACCEPTANCE_FROZEN_NATIVE':str(installed),'COMPANION_ACCEPTANCE_VERIFY_DATE_ONLY':'1','COMPANION_ACCEPTANCE_OWNER_PREFLIGHT':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1'}
# The inherited proxy is for ordinary Internet traffic. Private CDP traffic
# stays on loopback; do not change the user's system routing or remote policy.
env['NO_PROXY']=env['no_proxy']='127.0.0.1,localhost,::1'
record['loopbackOnlyProxyBypass']=True
if REOPEN:
 previous=json.loads((O.parent/'self-acceptance-r2/result.json').read_bytes());previous_evidence=Path(previous['nativeEvidence']);previous_native=json.loads(previous_evidence.read_bytes());completed_ui=json.loads((previous_evidence.parent/'ui-result.json').read_bytes())
 assert previous_native['firstAppExitObserved'] and completed_ui['notesPersisted'] and completed_ui['dateOnlyCalendarSavedAndReopened'] and completed_ui['exactSelectedNote']
 env.update(COMPANION_ACCEPTANCE_OWNER_PREFLIGHT='0',COMPANION_ACCEPTANCE_REOPEN_FROM_EVIDENCE=str(previous_evidence));record['completedContinuousJourneyEvidence']=str(previous_evidence.parent/'ui-result.json')
try:
 with (O/'runner.log').open('wb') as log:run=subprocess.run([sys.executable,str(S/'tools/qa/core_acceptance20261109/windows_meeting.py'),'--stage','product-background'],cwd=S,env=env,stdout=log,stderr=subprocess.STDOUT)
 cases_root=O/'product/docs/handoffs/20261109-core-acceptance';assert cases_root.is_dir(),(O/'runner.log').read_text(encoding='utf8',errors='replace')[-2300:]
 cases=list(cases_root.iterdir());assert len(cases)==1;detail=json.loads((cases[0]/'result.json').read_bytes());record['nativeEvidence']=str(cases[0]/'result.json');record['nativeExitCode']=run.returncode;write()
 assert run.returncode==0,(O/'runner.log').read_text(encoding='utf8',errors='replace')[-2300:]
 assert detail['state']==('REAL_NATIVE_PROCESS_REOPEN_SCOPE_PASSED' if REOPEN else 'REAL_NATIVE_COHERENT_BACKGROUND_PRODUCT_JOURNEY_PASSED') and detail['processRestart']['allPublicLibraryRowsUnchanged'] and detail['processRestart']['firstPid']!=detail['processRestart']['reopenedPid']
 assert detail['ownerKeyboardMouseOrForegroundControlUsed'] is False and detail['ownerClipboardSequenceUnchangedAtObservation']
 record.update(state='INSTALLED112_FRESH_CONTINUOUS_SOFTWARE_AND_ACTUAL_PROCESS_RESTART_PASSED',actualExitAndRelaunchPassed=True,deviceEntryHierarchyRechecked=True,selectedContentExportRechecked=True,dateOnlySaveReopenPassed=True,wholePhysicalQualification=False,sourceAndNotesRetainedAfterProcessRestart=True)
except BaseException as error:record.update(state='INSTALLED112_ENGINEERING_SELF_ACCEPTANCE_NOT_PASSED_RETAINED',error=repr(error));raise
finally:record['finishedAt']=datetime.now().astimezone().isoformat(timespec='seconds');write()
print(json.dumps(record,ensure_ascii=False))
