from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,subprocess,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent
rel=Path('docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12');P=R/rel
F=P/'windows060-system-handoff';G=P/'windows067-literal-and-rendering';H=G/'system-handoff'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):
 with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
package=read(G/'windows-verification.json');installed=read(G/'installation.json');actual=read(H/'actual-content-result.json');copy=read(H/'actual-copy.json')
assert actual['actualSaveAsFormats']==8 and actual['officeSchemaErrors']==0 and actual['cancellation']['savedFilesIdentical']
assert installed['dataManifestIdentical'] and installed['existingDataFiles']==245
assert sha(Path(package['msi']))==package['msiSha256']
assert not [p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='companion-type.exe'],'Own/private or owner product still active; preserve it'
state='WINDOWS067_INSTALLED_EIGHT_SYSTEM_SAVE_AS_AND_COPY_PASSED_SHARE_AND_PHONE_FINAL_PENDING'
record={'at':now,'state':state,'version':'0.1.67','sourceCommit':package['sourceCommit'],'msiSha256':package['msiSha256'],
 'actualInstalled':True,'originalDataFilesIdentical':245,'actualSaveAsFormats':['Word','PDF','PowerPoint','TXT','Markdown','Excel','editableMindmap','PNG'],
 'actualCancelProducedNoNewFile':True,'actualContentResult':'system-handoff/actual-content-result.json','actualCopy':copy['state'],
 'clipboardRestorationQualified':False,'publicSyntheticFixture':True,'modelsRun':False,'ordinaryShareRecipientVerified':False,'fullPriority12Complete':False,'wholeProductQualified':False,
 'fixedBehavior':['Raw transcript literal prefixes, indentation, XML/emoji and formula-looking text are preserved through selected rich documents; source/copy/TXT/MD remain unchanged.',
 'PDF/PNG wait for complete closed output while owned child renderers still run, bounded by original timeout/cancellation and job cleanup; generic ASR wrapper parent-exit behavior retained.',
 'Document-only UUID cache cleanup tolerates brief Windows file-sharing locks, bounded2sec and constrained to own temp subtree.'],
 'inspection':'Actual saved PDF page and mindmap PNG visually inspected; both legible and unclipped for this synthetic fixture. No real long-meeting model quality claim.',
  'qaLimitations':['Non-input desktop select popup not consistently observable after native modal. Fresh private App desktop per remaining format completed all8 actual SaveAs; this does not qualify foreground focus behavior.',
 'Copy text matched exactly. OLE original-clipboard restore raised CLIPBRD_E_CANT_CLOSE; original restoration unknown, subsequent observation public test text absent/Unicode format absent. No original clipboard data inspected/recorded. Do not reuse this preservation method.',
 'Initial content checker expected raw text without the intentional ## 录音文字 section header; adjusted to retain exact source after that system header, no product change.',
 'Current phone/board lease is held by existing embedded power/long-record flow since17:32; no claim, install or phone input performed in this batch.'],
 'remaining':['Windows actual ShareSheet and intended local-recipient handoff; current data-package checks are not recipient delivery.',
 'After shared lease release, re-read latest Android/FW; unified066 candidate must not downgrade any newer installed app. Verify actual corrected Word and current own-new recording pause/resume/playback/delete/audio as affected.',
 'Return phone from public test library to original retained library after existing shared flow releases.',
 'Other existing non-model/physical sale gaps remain; these two scopes are not the entire product.']}
write(G/'progress-result.json',record)
path=R/'docs/product_backlog.json';raw=path.read_bytes();data=json.loads(raw);front=data['owner_module_execution']['frontendWindowsMobile20261102'];task=front['ownerDevicePhoneClosure055']
task['windows067Delivery']=record;task['state']=state;task['priority12Actual']['windows067Actual']=record
task['ownerPriority12']['state']=state
task['next']='Windows067已安装并实走八格式系统保存/取消/内容核验与复制；接续Windows真实系统分享及接收文件，不能把DataPackage单测当完成。手机/板当前另一个嵌软长录/电源任务占用，待其释放后读实际最新版本，不降级066；只验原待办受影响的新录控制/接收/回听/受控删除/原音和Word修复，最后切回原库。整机及其它非模型缺口仍保留。'
coverage=front['ownerCoreDeliveryPriority20261104']['ownerCompetitiveParity20261105']['coverage']
for item in coverage:
 if item['id']=='exports':item['engineering']['windows067Actual']={'receipt':str(G/'progress-result.json'),'installed':True,'eightActualSaveAs':True,'contentPreserved':True,'actualCopy':True,'actualShareRecipient':False,'clipboardRestorationQualified':False}
 if item['id']=='updates':item['engineering']['windows067Installed']={'receipt':str(G/'installation.json'),'sameUpgradeIdentityAndDowngradeGuard':True,'installed':True,'original245FilesIdentical':True}
assert path.read_bytes()==raw,'Concurrent canonical update; rerun from fresh bytes'
temp=path.with_suffix('.windows067delivery.tmp');write(temp,data);os.replace(temp,path)
with (R/'docs/development_log.md').open('a',encoding='utf8') as stream:
 stream.write(f'''\n\n## {now}｜前两项续作：Windows067正式安装，八格式真实系统保存/取消及内容通过，分享/手机剩余不虚关\n\n源码60166fa3bd22cc277d4a6c69962d39fa3c13e9e0已先远端保护。源头修复原始转写符号被格式解析吞掉、PDF/PNG父启动器早退导致子渲染被过早终止，以及首次实际完整渲染后Windows临时profile短暂锁导致清理失败。保留060坏Word、PDF/PNG失败、同参数启动器/后代时间对照及首编/监测器/清理失败，不把它们覆盖成通过。只改文档等待策略/自身UUID清理，不改ASR任务退出策略；本轮无模型/推理/训练，构建单作业/低优先级/4逻辑CPU。\n\n067网页准备与许可检查通过；原生生产构建455.269秒，匹配MSI {package['msiSha256']}，包内EXE {package['embeddedExeSha256']}、DLL {package['dllSha256']}，256许可载荷及升级身份/拒绝降级规则匹配。18:00静默060→067安装完成0，245个原有文件长度/SHA前后全同；用户资料备份/文件名清单只留本机E私有缓存，不入远端。Tauri封包仅改Cargo换行，按冻结Git逐字节恢复同源；没有以新源配旧二进制。\n\n实际已安装067在独立非输入桌面、明确虚构资料、关闭BLE/AI/自动恢复，原生界面逐一选择Word/PDF/PPTX/TXT/MD/XLSX/mm/PNG并真正调用系统另存为到全新QA文件；8份实际文件、系统取消且文件不变、Microsoft OpenXML结构0错，原句/否定/20%/11月8日/#literal/公式样文字保留，未选材料不混入，原始虚构资料内容不变。实际PDF和PNG已目检可读且无裁切。原生CLI八格式也独立通过，但与系统保存区分。每次原生模态后隐藏桌面下拉框不稳定，SetFocus/Value不解决；去掉SetFocus并换全新非输入QA实例逐格式实走成功，未切换/激活日用桌面，全部自身进程已关闭，不据此宣称前台焦点体验合格。\n\n普通复制所选内容确实写入与预期包含系统章节头的原文字节相同文本。验收工具恢复原剪贴板时OleSetClipboard报CLIPBRD_E_CANT_CLOSE，随后进程退出，恢复完整性无法确认；只回查测试文字已不在、Unicode格式不在，没有读取/记录原剪贴板内容。已向Owner说明，不再复用该OLE备份方法。初始文本检查器误期望无系统“## 录音文字”章节头，纠正预期为保留该头+逐字原文后通过，未为适配测试改产品。\n\n当前共享板/手机自17:32仍被另一原嵌软电源/长录流程占用，未抢占、安装066或输入手机；现行AGENTS报告FW66689/Android065并保留功耗与声学等缺口，实际接手仍须重查最新身份。Windows实际系统ShareSheet/接收应用、Android合并修复后Word及原录控/回听/受控删/原音和切回原库仍未结束。任务不标全通过，亦非“只剩模型”。进展与剩余见{G/'progress-result.json'}。\n''')
# Select only public synthetic evidence and build receipts. Never copy private profiles,
# upgrade inventories, original user filenames/backups, or unneeded duplicate binaries.
dest=S/rel;dest.mkdir(parents=True,exist_ok=True)
g=dest/G.name;g.mkdir(exist_ok=True)
for file in G.iterdir():
 if file.is_file() and file.suffix in {'.json','.log','.msi','.png','.toml','.jsonl'}:shutil.copy2(file,g/file.name)
for folder in ['release-native','system-handoff']:
 shutil.copytree(G/folder,g/folder,dirs_exist_ok=True)
for folder in G.glob('native-files-*'):
 if (folder/'manifest.json').exists():
  out=g/folder.name;out.mkdir(exist_ok=True)
  for file in folder.iterdir():
   if file.is_file() and file.name!='public-session.json':shutil.copy2(file,out/file.name)
(g/'msi-inspection').mkdir(exist_ok=True)
for name in ['installer.wxs','decompile.log']:shutil.copy2(G/'msi-inspection'/name,g/'msi-inspection'/name)
f=dest/F.name;f.mkdir(exist_ok=True)
for name in ['actual-system-save-word060.json','baseline-native-progress.json','headless-lifetime-diagnosis.json']:
 shutil.copy2(F/name,f/name)
for folder in ['failures','baseline-native']:
 shutil.copytree(F/folder,f/folder,dirs_exist_ok=True)
qa=S/'tools/qa/phone_closure059';qa.mkdir(exist_ok=True)
for name in ['windows060_system_session.py','windows060_system_native.py','windows060_literal_baseline.py','windows060_system_web.cjs','diagnose_headless_document_lifetime.py','checkpoint_windows067_issues.py','run_windows067_focused_tests.py','inspect_windows067_native_files.py','prepare_windows067_release.py','build_windows067_release.py','package_windows067_release.py','prepare_windows067_actual.py','install_windows067_verified.py','windows067_release_native.py','windows067_system_session.py','windows067_system_native.py','windows067_actual_save_batch.py','windows067_actual_save_fresh.py','inspect_windows067_actual_saved.py','windows067_copy_preserving_clipboard.py','preserve_windows067_delivery.py']:
 shutil.copy2(W/name,qa/name)
for name in ['product_backlog.json','development_log.md']:shutil.copy2(R/'docs'/name,S/'docs'/name)
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
 r=subprocess.run(['git','-c','maintenance.auto=false',*map(str,args)],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert r.returncode==0,r.stdout+r.stderr;return r.stdout.strip()
git('add','--','tools/qa/phone_closure059','docs/product_backlog.json','docs/development_log.md')
git('add','-f','--',rel/G.name,rel/F.name)
git('-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol','diff','--cached','--check','--','tools/qa/phone_closure059')
git('commit','-m','Deliver Windows067 faithful documents with actual eight-format Save As acceptance')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
assert git('ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
for file in [Path(package['msi']),G/'progress-result.json',H/'actual-content-result.json']:
 relative=rel/G.name/file.relative_to(G)
 r=subprocess.run(['git','show',pin+':'+relative.as_posix()],cwd=S,capture_output=True);assert r.returncode==0 and hashlib.sha256(r.stdout).hexdigest()==sha(file)
write(G/'remote-readback.json',{'at':now,'commit':pin,'remoteReadback':True,'msiAndActualAcceptanceBlobsVerified':True,'wholeProductQualified':False})
print(json.dumps({'commit':pin,'remoteReadback':True,'installedVersion':'0.1.67','actualSaveAsFormats':8,'remainingShareAndPhone':True,'wholeProductQualified':False},ensure_ascii=False),flush=True)
