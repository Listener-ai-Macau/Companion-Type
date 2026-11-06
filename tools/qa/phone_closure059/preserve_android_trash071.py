from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,hashlib,os,subprocess,shutil
W=Path(__file__).parent;R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
rel=Path('docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/android-trash071');O=R/rel
apk=json.loads((O/'apk-build-result.json').read_text(encoding='utf8'));checks=json.loads((O/'checks.json').read_text(encoding='utf8'));ui=json.loads((O/'ui-component-result.json').read_text(encoding='utf8'))
assert all(x['exitCode']==0 for x in checks) and ui['exitCode']==0
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'at':now,'state':apk['state'],'ownerQuote':'继续吧','latestOwnerInputs':['现在是插上手机了','另外现在显卡重新可以用了'],'candidate':apk,
 'implemented':['详情内保护/解除保护和移入本机回收站','回收站列表、恢复、明确范围的永久清除','移入不改原音/会议资料；回收站内容从普通列表、搜索、AI会议范围和旧分享入口排除','绑定库身份/修订及原文件清单；确认前全量核文件，清除中断可持久化续作','回收站与保护随现有整库备份保留，清除后留无正文的递增身份状态以拒绝陈旧操作'],
 'checks':checks,'uiComponents':ui,'nativeLibraryUnchanged':True,'computerUse':False,'phoneIo':False,'modelsRun':False,'installed':False,
 'scopeLimitations':['真实手机保护/移入/进程重开/恢复/取消和永久清除尚未验收，host故障注入不代表实机或断电合格。','永久清除仅当前库可确认归属的原音和会议资料；录音卡、其他库、已导出/分享副本、应用临时缓存与无法归属的旧损坏副本保留并明确提示，不宣称全局隐私擦除。','不完整/未结束录音及未解决的设备接收确认不进入永久清除；仅在无接收/升级/文件选择时修改。','当前共享占用是FW66692开停录与OTA，原手机验证继续；本侧不插入安装或抢手机/板，也不把旧066候选直接降级装回。'],
 'ownerAccepted':False,'wholeProductQualified':False,
 'next':'按共享记录等待原手机/板流程释放，随后核真实包身份和原资料，再安装069集中验Word与回收站等受影响链；Windows068真实收件与原库切回仍开放。Owner已恢复RX6800XT连接，非模型候选保护后从原受控整场L模型工作点续作，保CPU5%/私有内存2GiB/低内存停止/单模型，不调参、不重跑无变化短门、不改产品默认模型。'}
(O/'delivery-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=R/'docs/product_backlog.json';raw=p.read_bytes();data=json.loads(raw);front=data['owner_module_execution']['frontendWindowsMobile20261102'];task=front['ownerDevicePhoneClosure055']
task['androidTrash071']=record;task['state']=record['state'];task['next']=record['next']
task['latestAndroidCandidate']={'version':'0.1.69','code':69,'sourceCommit':apk['sourceCommit'],'apk':apk['apk'],'apkSha256':apk['apkSha256'],'installed':False,'containsUnified066WordAndTransport':True}
task['ownerPriority12']['state']=record['state'];task['ownerPriority12']['next']=record['next'];task['priority12Actual']['next']=record['next']
core=front['ownerCoreDeliveryPriority20261104']
for row in core['ownerCompetitiveParity20261105']['coverage']:
 if row['id']=='trash':
  row['current']='Windows原已交付；Android069新增保护/回收站/恢复及明确范围清除，候选已生成与后台核对，未装手机/未实际验收。'
  row['engineering']['status']='CANDIDATE_READY_DEVICE_PENDING';row['engineering']['label']='Android069回收站候选已准备，真实手机与资料保留验收待完成';row['engineering']['readyForOwnerAcceptance']=False;row['engineering']['candidateVersion']='Android0.1.69/code69'
  row['engineering']['androidTrash071']={'receipt':str(O/'delivery-result.json'),'sourceCommit':apk['sourceCommit'],'candidateBuilt':True,'installed':False,'actualPhoneQualified':False}
  evidence=row['engineering'].setdefault('evidence',[])
  if str(O/'delivery-result.json') not in evidence:evidence.append(str(O/'delivery-result.json'))
gpu={'at':now,'ownerQuote':'另外现在显卡重新可以用了','windowsInventory':[{'name':'AMD Radeon RX 6800 XT','status':'OK','driverVersion':'32.0.21043.19003'},{'name':'AMD Radeon 780M Graphics','status':'OK'}],'computeRunThisStage':False,'decision':'Night GPU resume condition met. Read original complete-L wrapper/previous failure; retain exact resource policy, no installed product model change.'}
core['ownerNightGpuModelPriority20261104']['ownerGpuReconnected20261106']=gpu
assert p.read_bytes()==raw,'Concurrent canonical edit; re-read before retry';tmp=p.with_suffix('.trash071.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(tmp,p)
with (R/'docs/development_log.md').open('a',encoding='utf8') as f:f.write(f'''\n\n## {now}｜不用Computer Use继续原P0：Android069保护、可恢复回收站及范围清除候选完成；Owner接回手机与6800XT\n\n从Windows068已安装/实际收件未验的原点接续，不把分享UI依赖当停工条件。新增独立本机管理层与普通手机详情/库入口，保护/解除、移入、恢复和回收站内永久清除完整接线。软删除仅提交耐久状态、原音/纪要/译文/AI材料均留，普通库/搜索/AI会议范围/旧准备分享入口排除隐藏记录。库token、递增revision、明确文件清单/哈希与原生确认防陈旧操作；同库接收静态监视器内禁止并行开传，等待确认不持Service监视器。开始永久清除前核全清单并持久化处理中状态，部分删除不能假报恢复完整，可跨进程重读原清单继续；完成后只留无正文身份/修订避免同key重导ABA。沿现有整库备份，无新后端/模型依赖。清除明确不含设备、其他库、外部副本、全局临时缓存与无法归属的旧损坏副本，不当全局隐私擦除。\n\n完整App Java编译、mobile类型与隔离组件检查通过；仅本轮E内虚构文件验证保护/取消/陈旧revision、完整软删与重开恢复字节不变、清除前文件变化拒绝、确认token失效、模拟删除中断与重开续作、另一UID同会话及AI材料保留、整库备份保留保护和回收站、损坏管理文件拒绝、路径越界与目录发布失败前不删原文件。真Android目录fsync已接入，但未拿host回调冒充实机/断电通过。源码{apk['sourceCommit']}远端确认，Android069/code69候选{apk['apkSha256']}生成，包内全部4个web资源匹配，签名/版本检查通过，native212ec44d与原AAR逐字节保留；{apk['wallSeconds']}秒、单工/两CPU/Java堆768MiB，无语音重编、模型、手机、板或桌面操作。\n\nOwner随后“现在是插上手机了”“另外现在显卡重新可以用了”。只读Windows确认RX6800XT状态OK，780M另在；不沿旧ordinal盲选。共享当前FW66692开停录/OTA占用未释放，原聊天明确将用手机继续，因此本侧未插入安装。原资料库切回/Word真机/Android069生命周期/Windows068实际收件仍开放；夜间模型从原完整L受控方案接续，不重放原R15失败或更改已安装默认模型。\n''')
dest=S/rel;dest.mkdir(parents=True,exist_ok=True)
for name in ['delivery-result.json','checks.json','full-app-java-compile.log','local-lifecycle-data-safety.log','mobile-types.log','ui-component-result.json','source-release.json','source-frozen.json','apk-build-result.json','signature-verification.log','apk-identity.log']:
 shutil.copy2(O/name,dest/name)
shutil.copy2(Path(apk['apk']),dest/Path(apk['apk']).name)
qa=S/'tools/qa/phone_closure059'
for name in ['integrate_android_trash071.py','check_android_trash071.py','prepare_android_trash071.py','build_android_trash071.py','preserve_android_trash071.py']:shutil.copy2(W/name,qa/name)
for name in ['product_backlog.json','development_log.md']:shutil.copy2(R/'docs'/name,S/'docs'/name)
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
 q=subprocess.run(['git','-c','maintenance.auto=false',*map(str,args)],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert q.returncode==0,q.stdout+q.stderr;return q.stdout.strip()
git('add','--','docs/product_backlog.json','docs/development_log.md','tools/qa/phone_closure059');git('add','-f','--',rel);git('-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof','diff','--cached','--check');git('commit','-m','Preserve Android069 recycle bin candidate and resume GPU availability workpoint')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin','HEAD:refs/heads/'+branch);assert git('ls-remote','origin','refs/heads/'+branch).split()[0]==pin
blob=subprocess.run(['git','show',pin+':'+(rel/Path(apk['apk']).name).as_posix()],cwd=S,capture_output=True,check=True).stdout;assert hashlib.sha256(blob).hexdigest()==apk['apkSha256']
receipt={'protectedCommit':pin,'remoteReadbackConfirmed':True,'apkBlobMatched':True,'sourceCommit':apk['sourceCommit'],'versionName':'0.1.69','installed':False,'computerUse':False}
(O/'remote-readback.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps(receipt),flush=True)
