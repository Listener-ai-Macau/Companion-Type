from pathlib import Path
from datetime import datetime
import hashlib,json
E=Path('E:/CodexData/Companion/product-d1d2-20261114');OUT=E/'app-candidate-r5';outputs=Path(__file__).resolve().parents[1]/'outputs'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert read(OUT/'qa/live-resume-privacy-final.json')['state'].startswith('PASS_')
assert read(OUT/'qa/speaker-review-portability-r1/result.json')['state'].startswith('PASS_')
binary=OUT/'companion-type.exe';assert sha(binary)==read(OUT/'source-binding.json')['binarySha256']
model=E/'local-package-r8/package.json';config=read(model)
assert sha(config['program'])==config['programSha256'] and sha(config['entryScript'])==config['entryScriptSha256']
owner=OUT/'owner-library';(owner/'recordings').mkdir(parents=True);assert not (owner/'sessions.json').exists();(owner/'sessions.json').write_text('[]\n',encoding='utf-8')
base={'COMPANION_TYPE_LOCAL_MEETING_CONFIG':str(model),'COMPANION_TYPE_ASR_PROVIDER':'local-meeting',
 'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1'}
launches={}
for name,profile in [('Companion-打开本地会议候选-20261115.cmd',owner),('Companion-查看完整会议结果-20261115.cmd',OUT/'review-library')]:
 env={**base,'COMPANION_TYPE_STATE_PATH':str(profile/'sessions.json'),
  'COMPANION_TYPE_RECORDING_DIR':str(profile/'recordings'),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(profile/'settings.json'),
  'WEBVIEW2_USER_DATA_FOLDER':str(profile/'webview')}
 clear=['COMPANION_TYPE_TRANSCRIPT_TEXT','COMPANION_TYPE_ASR_COMMAND','COMPANION_TYPE_LIVE_ASR_MOCK','COMPANION_TYPE_LIVE_ASR_OFF',
  'COMPANION_TYPE_BACKGROUND_WINDOW','COMPANION_TYPE_WEBVIEW_ARGS','COMPANION_LOCAL_ARTIFACT_ROOT','COMPANION_LOCAL_ARTIFACT_ROOTS']
 lines=['@echo off','setlocal']+[f'set "{key}={value}"' for key,value in env.items()]+[f'set "{key}="' for key in clear]
 lines += [f'start "" /D "{OUT}" "{binary}"','endlocal','']
 target=outputs/name;assert not target.exists();target.write_bytes('\r\n'.join(lines).encode('utf-8'))
 launches[name]={'file':str(target),'sha256':sha(target),'env':env,'clear':clear}
report={'state':'LOCAL_D1_EXECUTABLE_DELIVERY_FINAL_NATIVE_UI_CHECK_PENDING','at':datetime.now().astimezone().isoformat(timespec='seconds'),
 'binary':str(binary),'binarySha256':sha(binary),'modelPackage':str(model),'modelPackageSha256':sha(model),
 'launches':launches,'internalCandidateOnly':True,'installedDefaultChanged':False,'privateInputUsedForVerification':False,
 'modelInputsRemainLocal':True,'minutesUseExistingConfiguredProvider':True,'newCloudCredentialsWrittenToArtifacts':False,
 'evidence':{'nativeLiveStopResumePrivacy':str(OUT/'qa/live-resume-privacy-final.json'),
  'speakerReviewAndReopenExport':str(OUT/'qa/speaker-review-portability-r1/result.json'),
  'fullEnglishNativeMinutes':str(E/'app-candidate-r3/qa/whole-flow.json'),
  'draftUnknownSource':str(E/'app-candidate-r4/qa/source-review-flow.json')},
 'coldNativeFirstPreviewSeconds':81.2359646,'realtimeLatencyQualified':False,'ordinaryMeetingQualityQualified':False,
 'realCardAndroidOrCustomerHardwareQualified':False,'saleQualified':False}
path=outputs/'Companion-D1本机候选入口与核验-20261115.json';assert not path.exists();path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'binarySha256':report['binarySha256'],'launches':list(launches),'receipt':str(path)},ensure_ascii=False))
