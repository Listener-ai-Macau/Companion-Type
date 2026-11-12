from pathlib import Path
from datetime import datetime
import copy,hashlib,json,os,shutil,subprocess,sys,zipfile

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';O=Path(__file__).resolve().parents[1]/'outputs';CACHE=Path('E:/CodexData/Companion/.build-cache/product-closure20261112');B=R/'docs/handoffs/20261112-product-closure/windows116';A=B.parent/'android144';C=R/'docs/handoffs/20261110-android-media-import/android144';F=B.parent/'frontend116144'
read=lambda path:json.loads(path.read_bytes())
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def now():return datetime.now().astimezone().isoformat(timespec='seconds')
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m']
proof=read(B/'windows-verification.json');runtime=read(B/'runtime-result.json');installation=read(B/'installation.json')
assert proof['version']==installation['installedVersion']=='0.1.116' and proof['sourceCommit']==runtime['appSourceCommit']==installation['sourceCommit']
assert installation['dataManifestIdentical'] and runtime['actualNativeProcessRestart']['allPublicLibraryRowsUnchanged']
assert sha(Path('C:/Program Files/Companion Type/companion-type.exe'))==proof['embeddedExeSha256']

if sys.argv[1]=='self':
    previous='ba26a969bb7f72966fe0ad18c7bcb67675650509';current=proof['sourceCommit'];retained=[]
    for name in ['apps/windows/src-tauri/src','packages/core/src']:
        old=subprocess.check_output(git+['rev-parse',previous+':'+name],cwd=S,text=True).strip();new=subprocess.check_output(git+['rev-parse',current+':'+name],cwd=S,text=True).strip();assert old==new
        retained.append(dict(path=name,priorTree=old,currentTree=new))
    voice=read(CACHE/'public-computer-voice115-r3/result.json');assert voice['actualLocalAsrCompleted'] and voice['minutesSource']=='llm_deepseek' and voice['savedStateUnchangedAcrossProcesses']
    public=CACHE/'public-computer-voice115-r3';destination=public/'selected-readable-result116.txt';assert not destination.exists()
    request=public/'selected-readable-request116.json';write(request,dict(sessionId='public-computer-voice115',meetingMode='offlineStore',format='txt',contentSections=dict(minutes=True,transcript=True,highlights=False,timeline=False,noteIds=[])))
    env={**os.environ,'COMPANION_TYPE_STATE_PATH':str(public/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(public/'recordings'),'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1'}
    with (public/'selected-readable-export116.log').open('wb') as log:run=subprocess.run(['C:/Program Files/Companion Type/companion-type.exe','--meeting-export-request',str(request),str(destination)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    assert run.returncode==0
    text=destination.read_text(encoding='utf8');assert all(word in text for word in ['李明','小林','周五','预算','没决定']);assert 'Generated:' not in text and 'Minutes engine:' not in text
    state=dict(at=now(),state='WINDOWS116_NORMAL_INSTALLED_COHERENT_SOFTWARE_ENGINEERING_SELF_ACCEPTANCE_PASSED',windowsVersion='0.1.116',softwareSelfAcceptancePassed=True,appSourceCommit=current,installedPayloadMatchedInspectedMsi=True,continuousUiEvidence=runtime['nativeUiEvidence'],actualProcessRestartEvidence=runtime['actualNativeProcessRestart'],sourceWholePurposeEvidence=str(CACHE/'ui-usability-source-r10/result.json'),normalNativeServiceReadiness=read(CACHE/'windows116/self-acceptance-service-readiness/result.json')['settings'],priorActualComputerSpeechBackendEvidence=voice,unchangedWholeProductionSourceTrees=retained,actual116SelectedReadableExportPassed=True,publicSelectedResult=str(destination),newGuiAudioImportQualified=False,newOsDialogsAndOrdinaryRecipientRetested=False,unchangedOsEvidence=runtime['unchangedOsHandoffEvidence'],ownerKeyboardMouseOrForegroundControlUsed=False,ownerAppearanceAccepted=False,ownerExperienceAccepted=False,physicalRecordingQualified=False,longRecordingQualified=False,modelGeneralAccuracyQualified=False,saleQualified=False)
    write(B/'engineering-self-acceptance/result.json',state);write(O/'Companion-116-self-acceptance.json',state)
    evidence=Path(runtime['nativeUiEvidence']).parent
    for source,target in [(evidence/'self-acceptance-library-entry.png',O/'Companion-116-entry.png'),(evidence/'product-handoff-light.png',O/'Companion-116-export.png')]:shutil.copyfile(source,target)
    print('Exact installed116 self-review, unchanged model/backend identity and actual readable public export confirmed.')
elif sys.argv[1]=='package':
    self_review=read(B/'engineering-self-acceptance/result.json');assert self_review['softwareSelfAcceptancePassed']
    build=read(A/'build-result.json');phone=read(C/'library-review-result.json');end=read(C/'end-session.json');installed=read(C/'installation.json');returned=read(C/'original-returned.json')
    assert build['versionName']=='0.1.144' and phone['historicalCancelNotMisrepresentedAsCurrentError'] and phone['allPublicRowsUnchanged'] and phone['priorAppearanceDarkRestoredAndReadBack']
    assert end['ownedAppDisplayForwardJarClosed'] and end['allPreviousLibrariesRetained'] and end['onlyOldChangeLibraryIndex']
    assert returned['state']=='ORIGINAL_LIBRARY_AND_PRIOR_APPEARANCE_RETURNED_BY_ORDINARY_UI'
    assert installed['apkSha256']==build['apkSha256']
    for name in ['installation.json','library-review-result.json','end-session.json','original-returned.json','appearance-before.json']:shutil.copyfile(C/name,A/name)
    for source,target in [(C/'library-light.png',O/'Companion-144-library.png'),(C/'detail-light.png',O/'Companion-144-detail.png')]:shutil.copyfile(source,target)
    windows=dict(version='0.1.116',sourceCommit=proof['sourceCommit'],installerSha256=proof['msiSha256'],installerBytes=Path(proof['msi']).stat().st_size,installed=True,originalDataFiles=installation['existingDataFiles'],originalDataManifestIdentical=True,coherentNativeJourneyPassed=True,actualProcessRestartPassed=True)
    android=dict(version='0.1.144',sourceCommit=build['sourceCommit'],apkSha256=build['apkSha256'],installed=True,existingFilesIdenticalDuringInstall=installed['existingFilesByteIdentical'],originalContentFilesIdenticalAfterReview=end['preexistingFilesByteIdentical'],onlyOldChangeLibraryIndex=end['onlyOldChangeLibraryIndex'],allPreviousLibrariesRetained=True,actualPhoneReviewed=True,historicalCancellationQuiet=True,priorActual143NameSearchRestartReused=True,nativeBackendUnchanged=True)
    software=dict(at=now(),state='RECORDING_LIBRARY116144_INSTALLED_ENGINEERING_REVIEWED_OWNER_SHORT_UX_REVIEW_PENDING',windows=windows,android=android,ownerAcceptanceScope='Short natural visual and usage-clarity experience only. Engineering owns functionality, computer-generated speech checks and complex/long checks.',ownerAppearanceAccepted=False,ownerExperienceAccepted=False,physicalTotalAcceptancePassed=False,longRecordingQualified=False,modelGeneralAccuracyQualified=False,saleQualified=False)
    F.mkdir(exist_ok=False);write(F/'frontend-result.json',software)
    stage=Path('E:/CodexData/Companion/deliveries/20261112-companion-recording116144');stage.mkdir(exist_ok=False);files=[]
    def put(source,name):
        target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);files.append(dict(path=name,bytes=target.stat().st_size,sha256=sha(target)))
    for source,name in [(Path(proof['msi']),'电脑/Companion-Windows-0.1.116.msi'),(Path(build['apk']),'手机/Companion-Android-0.1.144.apk'),(CACHE/'public-computer-voice115-r2/computer-public-example.wav','公开示例/演示安排-电脑合成声音.wav'),(Path(self_review['publicSelectedResult']),'公开示例/演示安排-实际识别与整理结果.txt'),(O/'Companion-116-entry.png','界面/电脑录音库.png'),(O/'Companion-144-library.png','界面/手机录音库-公开隔离资料.png'),(O/'Companion-144-detail.png','界面/手机录音详情-公开隔离资料.png')]:put(source,name)
    for parent,names,prefix in [(B,['frozen-source.json','windows-verification.json','installation.json','runtime-result.json','engineering-self-acceptance/result.json'],'工程记录/电脑'),(A,['frozen-source.json','build-result.json','installation.json','library-review-result.json','end-session.json','original-returned.json'],'工程记录/手机')]:
        for name in names:put(parent/name,prefix+'/'+name)
    instructions='''Companion｜本轮完整界面交付

已安装版本：电脑 0.1.116，Android 手机 0.1.144。

平常怎么用
1. 在“我的记录”找到一条录音。名称、时间、来源和已有文字帮助你辨认；搜索能查标题、文字和笔记。
2. 打开后回听或读文字。没有文字时，界面显示当前真正能做的下一步；需要时再整理纪要和待办。
3. 从同一条记录导出需要的内容。高级整理、分类与其它工具按需展开。

这次你只做简短体验
自然打开、找一条内容、看一下，感受是否看得懂、找得到、用起来顺。遇到问题直接说当时在哪、想做什么；每条问题单独保留，工程集中修复。没有固定八步、长录或复杂故障清单需要你做。

功能检查由工程完成。公开示例文件为电脑合成声音；对应文字来自实际本机识别，纪要来自已配置的文字服务，未预填识别结果。它不是实卡采音或长录证明。实卡及长期工程验证由工程继续跟踪，不要求你反复操作。

本包是电脑/手机界面与使用逻辑的一批交付；录音卡固件沿现有正常版本，不在此包内更换。原录音与手工名称保留。
'''
    readme=stage/'开始使用.txt';readme.write_text(instructions,encoding='utf-8-sig');files.append(dict(path='开始使用.txt',bytes=readme.stat().st_size,sha256=sha(readme)))
    manifest=dict(at=now(),state=software['state'],entry='开始使用.txt',files=files,softwarePurposeClosure=software)
    write(stage/'manifest.json',manifest);archive=O/'Companion-Recording-116-144-20261112.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in stage.rglob('*'):
            if file.is_file():z.write(file,file.relative_to(stage).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for file in files:assert hashlib.sha256(z.read(file['path'])).hexdigest()==file['sha256']
    delivery=dict(at=now(),state='ONE_RECORDING116144_KIT_INSTALLED_LOCAL_ARCHIVE_VERIFIED_PRIVATE_READBACK_PENDING',archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),manifest=manifest,allArchiveMemberChecksumsMatched=True,privateRemoteReadbackVerified=False,ownerExperienceAccepted=False,physicalTotalAcceptancePassed=False,saleQualified=False)
    write(F/'software-delivery.json',delivery);write(O/'Companion-Recording-116-144-20261112.json',delivery)
    for source,target in [(Path(proof['msi']),O/'Companion-Windows-0.1.116.msi'),(Path(build['apk']),O/'Companion-Android-0.1.144.apk'),(readme,O/'Companion-Guided-Whole-Acceptance.txt')]:shutil.copyfile(source,target)
    print(json.dumps({key:delivery[key] for key in ['state','archive','bytes','sha256']},ensure_ascii=False))
else:raise ValueError('Use self or package; neither stage starts an Owner acceptance window.')
