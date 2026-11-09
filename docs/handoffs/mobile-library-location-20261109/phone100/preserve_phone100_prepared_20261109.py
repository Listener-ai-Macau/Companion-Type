from pathlib import Path
from datetime import datetime,timezone,timedelta
import ast,hashlib,json,os,shutil,subprocess,time,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261109-mobile-library-location/phone100'
D=S/'docs/handoffs/mobile-library-location-20261109/phone100'
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
apk=json.loads((C/'apk100-verification.json').read_bytes());assert sha(apk['apk'])==apk['sha256']
assert apk['versionCode']==100 and apk['signerMatches050r2And055'] and apk['zip16KiBAligned']
assert len(apk['nativeLibraries'])==3 and len(apk['webAssetsExact'])==4
driver=S/'tools/qa/phone_closure059/phone_library100_session.py';ast.parse(driver.read_text(encoding='utf8'))
record={'recordedAt':now(),'ownerQuote':'有手机了',
 'state':'ANDROID100_VERIFIED_APK_READY_USB_DISCONNECTED_BEFORE_INSTALLATION',
 'actualPhoneObservation':{'serialSuffix':'45DU','model':'25060RK16C','package':'com.denzic.companion.app','versionName':'0.1.65','versionCode':65,
  'screenWasUnlocked':True,'appWasRunning':False,'appForegroundServicesObserved':False,
  'observedBeforeDisconnect':True,'observationTimeNotIndependentlyRecorded':True,
  'notAnInstallationDowngrade':'Live65 observation takes priority for this device over old98/99 receipts; no package installed this turn.'},
 'transportEndState':{'adbDeviceListEmpty':True,'windowsConnectedAndroidUsbDeviceAbsent':True,
  'connectionMissingBeforePrivateFileSnapshot':True,'virtualDisplayCreated':False,
  'installationAttempted':False,'appLaunched':False,'libraryChanged':False},
 'preparationFailures':[
  'Phone disconnected after initial read-only package/power/activity/service observation. Preflight stopped on adb device not found before file hashing. A subsequent virtual setup attempt also stopped on its first read; no process/display was created. Driver now explicitly requires completed preflight before virtual creation.',
  'First inline version-edit command had a PowerShell quoting SyntaxError, changed no file. Applied the exact Gradle version change through apply_patch instead.'],
 'candidate':apk,'webSourceReusedWithoutRebuild':True,'nativeRebuiltThisBatch':False,
 'sourceAndVersionCommit':apk['frontendSourceCommit'],
 'sharedItem':'Only Android100 local-library/export acceptance; no board BLE/recording.',
 'sharedItemReleased':True,'ownedModelOrBuildWorkersStillRunning':False,
 'phoneAcceptanceComplete':False,'originalFilesRetentionVerifiedThisTurn':False,
 'phoneOrUserFilesModified':False,'modelsRun':False,'ownerAccepted':False,'wholeProductQualified':False,
 'next':'USB恢复后重新读取这台45DU手机实际包版本/主屏/在途服务，领取原单项，先保留文件hash，再用已校验100包升级并复核原文件；如手机版本已更新则先合并，不降级。独立虚屏确认主屏不变后验证恢复公开备份→当前资料提示→取消/返回原库、回收站保护恢复、Word保存及本机分享收件，最后回原库并清理本轮辅助程序。现成包与Web资源复用，不重建或重跑模型；真实安装/系统交互保持未完成。'}
dump(C/'prepared-phone-result.json',record)
fixture=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/Companion-公开虚构导出验收056.zip'
expect=fixture.parent/'public-fixture-expected.json'
assert fixture.exists() and expect.exists()
dump(C/'public-fixture-binding.json',{'fixture':str(fixture),'bytes':fixture.stat().st_size,'sha256':sha(fixture),
 'expectation':str(expect),'expectationSha256':sha(expect),'realMeeting':False,'audioPlaybackAllowed':False,
 'purpose':'Only explicit synthetic export/library lifecycle verification; no model accuracy or acoustic pass.'})
D.mkdir(parents=True,exist_ok=True)
for p in C.iterdir():
 if p.is_file() and p.suffix in ['.json','.log']:
  shutil.copyfile(p,D/p.name)
shutil.copyfile(fixture,D/'public-synthetic-library056.zip');shutil.copyfile(expect,D/expect.name)
shutil.copyfile(__file__,D/Path(__file__).name)
path=R/'docs/product_backlog.json'
for attempt in range(8):
 original=path.read_bytes();data=json.loads(original);quality=json.dumps(data['quality_targets'],sort_keys=True,ensure_ascii=False)
 n=data['owner_module_execution']['frontendWindowsMobile20261102']['ownerDevicePhoneClosure055']
 current=n['ownerDaytimeLibraryLocation20261109'];current['phone100']=record;current['next']=record['next'];n['next']=record['next']
 n['state']=record['state']
 if 'candidateBeforePhone100' not in n:n['candidateBeforePhone100']=n.get('latestAndroidCandidate')
 n['latestAndroidCandidate']={'version':'0.1.100','code':100,'sourceCommit':apk['frontendSourceCommit'],
  'backendSourceCommit':apk['backendSourceCommit'],'apk':apk['apk'],'apkSha256':apk['sha256'],'installed':False,
  'scope':'Includes committed library-location/return Web source plus existing099 native/connection/Word/trash features. Phone absent before installation.'}
 n['latestPhoneLiveObservation']=record['actualPhoneObservation']
 assert quality==json.dumps(data['quality_targets'],sort_keys=True,ensure_ascii=False)
 tmp=path.with_suffix('.phone100.tmp');dump(tmp,data)
 if path.read_bytes()!=original:tmp.unlink();continue
 try:os.replace(tmp,path)
 except PermissionError:
  tmp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2));continue
 break
else:raise RuntimeError('Canonical backlog busy; candidate retained')
log=R/'docs/development_log.md';before=log.read_bytes();marker='手机100候选就绪但USB在安装前断开20261109'
if marker not in before.decode('utf8'):
 text=('\n\n## '+record['recordedAt']+'｜'+marker+'\n\n'
 'Owner告知“有手机了”。实际ADB识别45DU/25060RK16C，当前包0.1.65/code65、解锁、Companion无进程/前台服务；日用主屏在其它应用，仅过滤读取状态，不保存其内容。历史98/99收据不能代替这台手机当前值。'
 '沿前批已构建并逐文件核hash的Web资源，Android版本改100；同源提交'+apk['frontendSourceCommit']+'已推送读回。复用原受控APK构建器，75.438s完成单次Gradle构建；100APK SHA256 '+apk['sha256']+'，同原签名、三JNI与预定AAR逐字节一致且16KiB对齐、四Web资源精确匹配。未重建语音native、未改模型或板卡连接策略。'
 'USB随后从ADB及Windows已连接USB列表消失；文件hash前置读取即失败，后续虚屏准备同样在首个读取前停，无显示/辅助进程创建。驱动补齐先完成preflight才能建虚屏的顺序条件。没有开始安装、启动App、读取录音内容、切换/恢复/删除资料或系统保存分享，原文件保留本轮尚未核验，不虚报。'
 '手机测试原单项已释放，无遗留构建或模型作业。安装包在C受保护交付目录；源码、构建/签名/输入hash及公开虚构备份另存远端证据，APK本体不冒充已入Git。下一项：'+record['next']+'\n')
 with log.open('ab') as h:h.write(text.encode('utf8'))
 assert log.read_bytes().startswith(before)
for p in [path,log]:shutil.copyfile(p,S/'docs'/p.name)
env=os.environ.copy();env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
helper=S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py';tree=ast.parse(helper.read_text(encoding='utf8'));ns={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),str(helper),'exec'),ns)
head=ns['ship'](S,['tools/qa/phone_closure059/phone_library100_session.py','docs/product_backlog.json','docs/development_log.md',str(D.relative_to(S)).replace('\\','/')],'Preserve Android100 build and exact USB interruption before phone installation')
current=json.loads(path.read_bytes())['owner_module_execution']['frontendWindowsMobile20261102']['ownerDevicePhoneClosure055'];assert current['state']==record['state']
print(json.dumps({'state':record['state'],'remoteHead':head,'remoteReadbackVerified':True,'workingTree':ns['git'](S,'status','--short'),
 'apkVersion':100,'installed':False,'phoneFilesModified':False,'sharedItemReleased':True,'nextReadback':current['next']},ensure_ascii=False),flush=True)
