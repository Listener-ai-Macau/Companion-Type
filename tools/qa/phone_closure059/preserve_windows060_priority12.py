from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent
rel=Path('docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12')
P=R/rel;F=P/'windows060-word062';now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
def read(p):return json.loads(p.read_text(encoding='utf8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
package=read(F/'windows-verification.json');ui=read(F/'native-ui/result.json');diagnosis=read(F/'native-ui/fixture-persistence-diagnosis.json')
assert sha(Path(package['msi']))==package['msiSha256']
assert ui['isolatedPublicContentPreserved'] and diagnosis['publicContentPreserved']
record={'at':now,'state':'WINDOWS060_CANDIDATE_PACKAGED_EIGHT_FORMAT_NATIVE_PREVIEW_PASSED_SYSTEM_HANDOFF_PENDING',
 'package':package,'nativeUi':ui,'source':read(F/'source-frozen.json')['sourceCommit'],
 'scope':'Shared Word footer correction now compiled into actual Windows060 native binary and matched MSI; eight selected formats previewed through real private hidden native App using synthetic imported text, both themes. Source text, saved material and citations preserved; no owner data, clipboard, model, BLE or primary desktop interaction.',
 'notYetVerified':['Installed Windows060 upgrade and actual native SaveAs dialog','Windows share sheet and actual local recipient','Actual new phone/card pause/resume/full playback/controlled delete and original audio export','Actual latest unified Android Word export/schema after current shared owner releases;062 must not downgrade065','Return original phone library after active shared test ends'],
 'android062CandidateIsNotCurrentInstalled':True,'candidate062MustNotDowngradeNewerVersion':True,
 'latestSharedObservation':'Existing OTA flow reports actual0.1.65 installation for reception2M comparison. Do not install062. Re-read final receipt and merge shared Word062 footer plus newer reception changes before next affected acceptance.',
 'nativeBuild':read(F/'cargo-release.json'),'modelsRun':False,'fullPriority12Complete':False,'wholeProductQualified':False}
write(F/'progress-result.json',record)
canonical=R/'docs/product_backlog.json';raw=canonical.read_bytes();data=json.loads(raw)
front=data['owner_module_execution']['frontendWindowsMobile20261102'];task=front['ownerDevicePhoneClosure055'];actual=task['priority12Actual']
actual['windowsCandidate060']=record;actual['candidate']=read(P/'word062/apk62-verification.json')
actual['latestSharedObservation']=record['latestSharedObservation']
actual['next']='当前嵌软收取065实测占用期间不安装/点击手机；释放后读取实际版本与终态，合并062共享Word页脚到最新候选而非降级。再验实际Word保存分享、仅新录音暂停续录/回听/受控删除/原音导出，最后切回原有资料。Windows060已匹配打包并跑实际独立原生八格式预览，系统保存/分享及安装未验。'
task['next']=actual['next']
coverage=front['ownerCoreDeliveryPriority20261104']['ownerCompetitiveParity20261105']['coverage']
for row in coverage:
    if row['id']=='exports':
        row['engineering']['windows060WordCandidate']={'receipt':str(F/'progress-result.json'),'matchedMsi':True,'privateNativeEightFormatPreview':True,'installed':False,'ordinarySaveAsOrShare':False}
    if row['id']=='updates':
        row['engineering']['windows060Candidate']={'receipt':str(F/'windows-verification.json'),'sameUpgradeIdentityAndDowngradeGuard':True,'installed':False}
assert canonical.read_bytes()==raw,'Canonical backlog changed concurrently; retry from fresh state'
tmp=canonical.with_suffix('.windows060.tmp');write(tmp,data);os.replace(tmp,canonical)
entry=f'''\n\n## {now}｜前两项续作：Windows060匹配MSI与原生八格式预览完成，手机共享065收取实测期间不降级\n\n源2b5f352907ff49ec334f1b906c6b6921931f0622：062共享Word页脚源头修复已进入Windows实际原生编译。首次Windows网页准备在编译前因许可输入指纹旧版停止；核对052与060外部Cargo依赖全同、只本产品版本差异，更新Cargo/package锁哈希后原检查通过。单作业/低优先级，随后只给本侧Cargo/Rust子进程4个逻辑CPU；原生构建511.266秒，未运行模型或推理。MSI {package['msiSha256']}，内嵌exe/dll、网页和256份许可/对应源材料匹配，UpgradeCode及拒绝降级规则通过；候选尚未安装，不替换Owner当前程序。\n\n真实独立隐藏Windows App、明确虚构文字库，普通UI切八种格式并预览所选原文、浅深色、分享按钮可用通过；没有打开系统保存/分享面板，没有读取/修改剪贴板，没有BLE/录音/模型。测试初始byte-identity断言失败单列保留；精确结构对照仅九个预置null可选字段被既有serde规范省略，所有原文、纪要、材料和其它值不变。不是产品数据丢失，不重跑无变化UI；轻重主题截图已检查。\n\nAndroid062通用APK准备器收据nativeRebuilt=false为只描述封包步骤的硬编码误项：已改成读取原生源收据，并补nativeRebuiltByApkBuildStep=false；上游真实重编92.641秒，原始收据保留，不重编。当前他方共享手机流程报告065实装、正在2M收取对照；本侧没有抢占/降级安装。062是Word源修复基线，接续应合并到实际最新版本，不以旧候选覆盖新传输修复。当前仍需原库切回、新录控制回听/受控删除及原音交付；前两项和全产品继续未完成，亦非“只剩模型”。对应结果 {F/'progress-result.json'}。\n'''
with (R/'docs/development_log.md').open('a',encoding='utf8') as stream:stream.write(entry)
target=S/rel;target.mkdir(parents=True,exist_ok=True)
for name in ['apk62-verification.json','apk62-verification-original-packaging-only-native-flag.json']:
    shutil.copy2(P/'word062'/name,target/'word062'/name)
out=target/'windows060-word062';out.mkdir(exist_ok=True)
for file in F.iterdir():
    if file.is_file() and file.suffix in {'.json','.log','.msi'}:shutil.copy2(file,out/file.name)
for folder in ['native-ui']:
    shutil.copytree(F/folder,out/folder,dirs_exist_ok=True)
(out/'msi-inspection').mkdir(exist_ok=True)
for name in ['installer.wxs','decompile.log']:shutil.copy2(F/'msi-inspection'/name,out/'msi-inspection'/name)
qa=S/'tools/qa/phone_closure059';qa.mkdir(exist_ok=True)
for name in ['build_verify_control059_apk.py','phone059_web.cjs','verify_public_exports059.py','prepare_windows060_word062.py','build_windows060_word062.py','package_windows060_word062.py','prepare_windows060_package_driver.py','test_windows060_word062_ui.py','windows060_native_gui.cjs','diagnose_windows060_fixture.py','preserve_windows060_priority12.py']:
    shutil.copy2(W/name,qa/name)
for name in ['product_backlog.json','development_log.md']:shutil.copy2(R/'docs'/name,S/'docs'/name)
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
    p=subprocess.run(['git','-c','maintenance.auto=false',*map(str,args)],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert p.returncode==0,p.stdout+p.stderr;return p.stdout.strip()
git('add','--','tools/qa/phone_closure059','docs/product_backlog.json','docs/development_log.md')
git('add','-f','--',rel/'word062/apk62-verification.json',rel/'word062/apk62-verification-original-packaging-only-native-flag.json',rel/'windows060-word062')
git('commit','-m','Preserve matched Windows Word repair package and native eight-format public preview')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
assert git('ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
for file in [Path(package['msi']),F/'progress-result.json']:
    relative=rel/'windows060-word062'/file.name
    p=subprocess.run(['git','show',pin+':'+relative.as_posix()],cwd=S,capture_output=True);assert p.returncode==0 and hashlib.sha256(p.stdout).hexdigest()==sha(file)
write(F/'remote-readback.json',{'commit':pin,'remoteReadback':True,'msiAndProgressBlobVerified':True,'fullPriority12Complete':False})
print(json.dumps({'commit':pin,'remoteReadback':True,'windowsMsiSha256':package['msiSha256'],'nativeEightFormatPreview':True,'windowsSystemSaveAsShareVerified':False,'phoneHandoffStillPending':True},ensure_ascii=False),flush=True)
