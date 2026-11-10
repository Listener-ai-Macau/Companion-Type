"""Own APK update and owned virtual display only; never operate the physical display."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,sys,time
import psutil
CANDIDATE_CODE=int(sys.argv[2]) if len(sys.argv)>2 else 116;assert CANDIDATE_CODE in [116,117]
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent/('android'+str(CANDIDATE_CODE));P=Path('E:/CodexData/Companion/.build-cache/actions-followup20261110/phone116');P.mkdir(exist_ok=True)
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app'
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
tree=ast.parse((R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf8'))
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'retained-phone-helpers','exec'))
def hold(active):
    path=R/'docs/product_backlog.json';raw=path.read_bytes();d=json.loads(raw);row=d['recorder_core']['speed_investigation_handoff']['endpointSelection']['ownerPhoneHold']
    if active:
        assert not row['active'],'Another phone reservation is active'
        row.update(active=True,serial=SERIAL,reservedFor='Companion Android116 saved-action ordinary UI validation',requestedAt=now(),ownerInstruction='需要继续推进',scope='Own APK115 to116 update, original file hash preservation and public library ordinary UI on owned virtual display only; no main display, BLE, audio capture or owner record edits.')
    else:
        assert row['active'] and row['reservedFor']=='Companion Android116 saved-action ordinary UI validation'
        row.update(active=False,releasedAt=now(),releaseReason='Own Android116 saved-action test finished; public library restored and owned virtual display closed.')
    assert path.read_bytes()==raw
    temp=path.with_suffix('.actions116.tmp');save(temp,d);os.replace(temp,path)
action=sys.argv[1]
if action=='install':
    assert not (C/'installation.json').exists() and version()==115 and not adb(['shell','pidof',PKG],required=False).strip()
    assert 'ServiceRecord{' not in adb(['shell','dumpsys','activity','services',PKG])
    hold(True);before=primary();snapshot=files();old=hashes(snapshot);assert old
    (P/'before-install.sha256').write_text(snapshot,encoding='utf8')
    proof=json.loads((C/'build-result.json').read_text());apk=Path(proof['apk']);assert sha(apk)==proof['apkSha256']
    code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');assert '\n' not in code
    baseline=adb(['shell','sha256sum',code]).split()[0];assert baseline=='39a30664910e87c3e0ee32abd8fd336fdabffb3ae847b2409e4047589565a683'
    output=adb(['install','-r','-t',apk],timeout=120);assert 'Success' in output and version()==116
    after=files();(P/'after-install.sha256').write_text(after,encoding='utf8');new=hashes(after);assert all(new.get(k)==v for k,v in old.items())
    code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');actual=adb(['shell','sha256sum',code]).split()[0];assert actual==proof['apkSha256']
    record={'at':now(),'state':'ANDROID116_EXACT_APK_INSTALLED_ORIGINAL_FILES_IDENTICAL','versionCode':116,'sourceCommit':proof['sourceCommit'],'installedSha256':actual,'originalFilesByteIdentical':len(old),'primaryUnchanged':before==primary(),'modelsRun':False,'boardAccessed':False,'privateContentsUploaded':False}
    save(C/'installation.json',record);print(json.dumps(record))
elif action=='virtual':
    assert version()==CANDIDATE_CODE and not (P/'virtual.json').exists() and not adb(['shell','pidof',PKG],required=False).strip()
    before=primary();exe=Path('E:/CodexData/Companion/.build-cache/device-phone055/background-display/scrcpy-win64-v5.0.1/scrcpy.exe')
    args=[str(exe),'-s',SERIAL,'--new-display=1080x1920/360','--no-window','--record=NUL','--record-format=mkv','--no-audio','--no-clipboard-autosync','--display-ime-policy=local','--keyboard=disabled','--mouse=disabled','--no-power-on','--no-vd-system-decorations','--no-terminal-title','--max-fps=1','--video-bit-rate=128K']
    with (P/'virtual.log').open('wb') as log:child=subprocess.Popen(args,env={**os.environ,'ADB':str(A)},stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    state={'at':now(),'pid':child.pid,'createdAt':psutil.Process(child.pid).create_time(),'mainBefore':before,'audio':False,'clipboard':False,'physicalInput':False,'videoFile':False}
    save(P/'virtual.json',state)
    for _ in range(30):
        text=(P/'virtual.log').read_text(encoding='utf8',errors='replace');assert child.poll() is None,text[-800:]
        match=re.search(r'New display:[^\n]*\(id=(\d+)\)',text)
        if match:state['displayId']=int(match[1]);break
        time.sleep(.4)
    save(P/'virtual.json',state);assert state.get('displayId',0)>0
    assert primary()==before
    print(json.dumps(state))
elif action=='start':
    state=json.loads((P/'virtual.json').read_text());assert state['displayId']>0 and version()==CANDIDATE_CODE
    before=primary();assert not adb(['shell','pidof',PKG],required=False).strip()
    adb(['shell','am','start','--display',state['displayId'],'-n',PKG+'/.MainActivity']);assert before==primary()
    pid=adb(['shell','pidof',PKG]).strip();assert pid.isdigit()
    port=adb(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).strip();assert port.isdigit()
    record={'at':now(),'displayId':state['displayId'],'pid':int(pid),'cdpPort':int(port),'primaryFingerprint':before,'mainUnchanged':True}
    save(P/'cdp.json',record);save(C/'ui-session.json',record);print(json.dumps(record))
elif action=='stop':
    state=json.loads((P/'virtual.json').read_text());session=json.loads((P/'cdp.json').read_text()) if (P/'cdp.json').exists() else None
    if session:
        # The caller must restore the original library through ordinary app UI first.
        restored=json.loads((C/'ui-result.json').read_text());assert restored['originalLibraryRestored']
        pid=adb(['shell','pidof',PKG],required=False).strip();assert not pid or pid==str(session['pid'])
        if pid:adb(['shell','am','force-stop',PKG])
        listener='tcp:'+str(session['cdpPort'])
        if any(row.split()[:2]==[SERIAL,listener] for row in adb(['forward','--list']).splitlines()):adb(['forward','--remove',listener])
    if psutil.pid_exists(state['pid']):
        process=psutil.Process(state['pid']);assert process.create_time()==state['createdAt'];process.terminate();process.wait(10)
    before=hashes((P/'before-install.sha256').read_text());after=files();(P/'after-ui.sha256').write_text(after,encoding='utf8');current=hashes(after)
    unchanged=sum(current.get(name)==digest for name,digest in before.items());changed=[name for name,digest in before.items() if current.get(name)!=digest]
    # Public state and active-library index may be legitimately saved by the ordinary QA UI.
    save(P/'changed-files.private.json',changed)
    index=json.loads(adb(['shell','run-as',PKG,'cat','files/companion-library-index.json']));assert index['activeId']=='original' and len(index['libraries'])==2
    public_id=next(item['id'] for item in index['libraries'] if item['id']!='original')
    assert all(name=='files/companion-library-index.json' or name.startswith('files/companion-meetings-'+public_id+'/') for name in changed),'Unexpected original file changed; manifests retained'
    adb(['shell','rm','-f','/data/local/tmp/companion-ui-standard110.jar'])
    hold(False)
    record={'at':now(),'state':'ANDROID'+str(CANDIDATE_CODE)+'_OWNED_SESSION_RELEASED','unchangedBaselineFiles':unchanged,'changedBaselineFiles':len(changed),'onlyPublicTestMinutesAndNavigationIndexChanged':True,'originalLibraryRestored':True,'mainUnchanged':primary()==state['mainBefore'],'ownedDisplayClosed':True,'ownForwardRemoved':True,'temporaryUiDriverRemoved':True,'ownerPrivateContentsUploaded':False}
    save(C/'cleanup.json',record);print(json.dumps(record))
else:raise ValueError(action)
