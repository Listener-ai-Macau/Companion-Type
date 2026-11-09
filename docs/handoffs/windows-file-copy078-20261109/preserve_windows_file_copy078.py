"""Close this Windows batch in the original task/log and verify remote readback."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import ast,copy,hashlib,json,os,shutil,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261109-windows-file-copy078'
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'))
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'<existing-publisher>','exec'))
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def read(name):
 p=C/name
 return json.loads(p.read_text(encoding='utf8')) if p.is_file() else None
installed=read('installation.json');package=read('windows-verification.json');ci=read('ci-current.json')
qualified_install=bool(installed and installed.get('state')=='WINDOWS078_INSTALLED_EXISTING_DATA_IDENTICAL')
record={'at':now(),'state':'WINDOWS078_FILE_COPY_INSTALLED_ORDINARY_RECIPIENT_PENDING' if qualified_install else 'WINDOWS078_FILE_COPY_SOURCE_PROTECTED_PACKAGE_NOT_INSTALLED','ownerQuote':'先搞win端到时候再调手机','version':'0.1.78','featureCommit':'f5d249edd5a0a9537fd9f608a6fa0c4bcabc04b3','sourceCommit':ci['sourceCommit'],'sourceRemoteReadbackVerified':True,'userOutcome':'已选格式的完整内容文件，以及所选原音/MP3，可以由用户点击复制后到支持文件粘贴的应用中自行粘贴；复制文字独立，原音保持，收件人和发送由用户决定。','nativeProof':read('native-isolated-result.json'),'nativeMainCheck':read('native-check-result.json'),'uiControlledProof':read('ui-verification.json'),'remoteBuild':ci,'bundleRecovery':read('bundle-recovery.json'),'sourceGuardVerification':read('ci-source-guard-verification.json'),'package':package,'installation':installed,'remoteCandidateBackup':read('remote-candidate-backup.json'),'platformPreservation':read('platform-preservation.json'),'localBuildFailures':[read(n) for n in ['native-release-result.json','native-release-lowram-result.json','native-release-paged-result.json']],'ordinaryThirdPartyPasteQualified':False,'oldWinRTSharePickerFixed':False,'modelsRun':False,'phoneAccessed':False,'boardAccessed':False,'installed':qualified_install,'saleQualified':False,'remaining':['支持文件粘贴的普通第三方应用实际收件与文件内容核对未验','原WinRT系统分享面板故障保留','手机100候选待真机流程，按Owner暂后置','多人/重叠模型质量门及整机售卖门均沿原记录开放']}
record['next']='Windows优先：在支持文件粘贴的普通接收应用中完成所选文档、原音/MP3实际收件，核对内容与未发送状态；不得用隔离原生模块或安装成功代替该项。原系统分享面板故障仍独立开放。复用078匹配产物，不再在当前内存压力下重编。手机100和模型原工作点不变。' if qualified_install else 'Windows优先：从本批CI终态及失败日志恢复匹配安装包交付；实际安装版以原收据为准，禁止把源码完成写成安装完成。保留原系统分享故障、手机100和模型工作点。'
(C/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
path=R/'docs/product_backlog.json'
for attempt in range(8):
 raw=path.read_bytes();d=json.loads(raw);quality=copy.deepcopy(d['quality_targets']);f=d['owner_module_execution']['frontendWindowsMobile20261102'];n=f['ownerDevicePhoneClosure055'];old=n['ownerWindowsFileCopy07820261109'];record['phoneInterruptedWorkpoint']=old['phoneInterruptedWorkpoint'];record['previousPhoneNext']=old['previousPhoneNext'];n['ownerWindowsFileCopy07820261109']=record;f['next']='沿ownerDevicePhoneClosure055.ownerWindowsFileCopy07820261109.next：Windows优先，手机稍后。';assert d['quality_targets']==quality
 temp=path.with_suffix('.windows078.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 if path.read_bytes()!=raw:temp.unlink();continue
 try:os.replace(temp,path)
 except PermissionError as e:
  if getattr(e,'winerror',None) not in [5,32,33]:raise
  temp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2));continue
 break
else:raise RuntimeError('Canonical backlog busy; preserve sources, do not overwrite another module')
log=R/'docs/development_log.md';marker='Windows078完整文件复制与远端可重建20261109'
old=log.read_bytes()
if marker.encode('utf8') not in old:
 text='\n\n## '+record['at']+'｜'+marker+'\n\n承接Owner“先搞win端到时候再调手机”。手机100候选/实际65观测/USB中断点保留，未接手机、板卡或跑模型。本批用户结果：'+record['userOutcome']+'\n\n文件操作复用所选范围、格式与expectedContentHash，在UI线程操作前再次确认来源；使用CF_HDROP和Preferred DropEffect COPY，不调用Shell命令或自动收件/发送。真实原生模块在独立非交互窗口站读回中文/emoji单文件及COPY标记和原字节，无效路径拒绝，Owner剪贴板序号未变；主程序cargo check63.0553911s过，前端/许可证342组件17源包过，原导出组件选区/来源hash/反馈合同及1080/1280/1440明暗受控布局过。这些不代替第三方普通收件。\n\n本机正常release60.065876s因Windows真实LOWRAM停止；低优化候选38.0543726s触及2GiB作业内存上限而失败，未采用；正常优化/物理驻留上限候选又出现LLVM OOM，控制进程枚举返回WinError1455，确认作业已退出，未安装旧产物。失败日志保留，控制器补终态异常记录，停止本机同条件重复构建，没有关闭Owner应用或改分页文件。转用只读权限、固定工具链、正常优化的远端Windows构建；首次workflow入口错误与后续checkout缺失共享核心的失败保留。发现原gitlink6f30ab5远端不可达，已原样推送Denzic-Platform专用preserve分支并读回，主仓库gitlink/业务逻辑未改。\n\nCI正常release原生编译18m48s通过，但后置源文件字节检查使整轮CI仍为failure。已取回原EXE/DLL，独立目录按CI的1228个源文件和6个完全相同Web资源复现bundle：仅Cargo.toml的CRLF变LF，解析配置相同，原生对和Web未变。未把CI整轮改成成功；复用原生对完成私有打包，无额外原生编译，包内257个许可证文件/EXE/DLL/同升级身份核对通过。CI源检查仅放行已复现的该一个manifest换行变化，版本/依赖/其它源变化仍拒绝，必要边界已验证，不重跑无变化的19分钟编译。\n\n最终交付：'+record['state']+'；CI '+record['sourceCommit']+' / run42563058131。'+('MSI包内EXE/DLL/许可证/同升级身份已核对，0.1.78后台升级且245个原资料文件hash一致；实际安装EXE/DLL及只读help启动通过。安装包另备份私有GitHub草稿并下载回读核SHA，未公开发布。' if qualified_install else '安装未完成，不能把源码或构建当已交付。')+' 售卖门、普通应用粘贴收件、旧系统分享面板故障仍开放；没有新的客户购买评价或整机合格结论。下一项：'+record['next']+' 证据在docs/handoffs/windows-file-copy078-20261109及原本机候选目录。墙钟只使用已有构建收据，不推算人工工时或token成本。\n'
 with log.open('ab') as stream:stream.write(text.encode('utf8'))
 assert log.read_bytes().startswith(old)
header=('<!-- frontend-windows078-current -->\nWindows当前（'+record['at']+'）：'+('已安装0.1.78，245个原资料文件hash一致；完整文件复制原生/界面/包内核对通过，普通第三方实际粘贴收件未验，旧系统分享故障开放。' if qualified_install else '本批源码已保留，安装未完成。')+' 手机100后置。当前点沿原待办ownerDevicePhoneClosure055.ownerWindowsFileCopy07820261109；本机收据 '+str(C/'installation.json')+'，远端证据 docs/handoffs/windows-file-copy078-20261109。\n<!-- /frontend-windows078-current -->\n\n').encode('utf8')
for attempt in range(8):
 raw_log=log.read_bytes()
 if b'<!-- frontend-windows078-current -->' in raw_log:break
 temp_log=log.with_suffix('.windows078.tmp');temp_log.write_bytes(header+raw_log)
 if log.read_bytes()!=raw_log:temp_log.unlink();continue
 os.replace(temp_log,log);break
else:raise RuntimeError('Log changed repeatedly; retained batch append, no overwrite')
dest=S/'docs/handoffs/windows-file-copy078-20261109';dest.mkdir(exist_ok=True)
for p in C.iterdir():
 if p.is_file() and p.suffix.lower() in ['.json','.log','.rs','.py','.png','.toml']:shutil.copy2(p,dest/p.name)
if (C/'ci-artifact').exists():
 for name in ['result.json','failure.txt','cargo-release.log','npm-ci.log','windows-web.log','msi-bundle.log']:
  p=C/'ci-artifact'/name
  if p.is_file():shutil.copy2(p,dest/('ci-'+name))
for name in ['package_windows_file_copy078.py','inspect_windows_file_copy078_ci.py','install_windows_file_copy078.py','preserve_windows_file_copy078.py','recover_windows078_ci_bundle.py','backup_windows_file_copy078.py']:shutil.copy2(Path(__file__).parent/name,dest/name)
for p in [path,log]:shutil.copyfile(p,S/'docs'/p.name)
h=ship(S,['tools/run_windows_file_copy078_native.py','tools/build_windows_candidate_ci.py','docs/product_backlog.json','docs/development_log.md','docs/handoffs/windows-file-copy078-20261109'],'Preserve Windows078 file clipboard delivery and exact remote rebuild evidence')
print(json.dumps({'state':record['state'],'deliveryCommit':h,'remoteReadbackConfirmed':True,'installed':qualified_install,'saleQualified':False},ensure_ascii=False))
