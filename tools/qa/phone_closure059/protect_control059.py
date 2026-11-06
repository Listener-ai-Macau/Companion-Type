from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,subprocess,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058'
W=Path(__file__).parent
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
source=json.loads((F/'source.json').read_text(encoding='utf8'))
apk=json.loads((F/'apk059-verification.json').read_text(encoding='utf8'))
assert source['versionCode']==apk['versionCode']==59 and not apk['installed']
assert sha(Path(apk['apk']))==apk['sha256']
peer_install=Path('E:/CodexData/Companion/.build-cache/android058-capability-fix/installation.json')
peer_ota=Path('E:/CodexData/Companion/.build-cache/android058-ota-real/status-history.json')
install=json.loads(peer_install.read_text(encoding='utf8'))
history=json.loads(peer_ota.read_text(encoding='utf8'))
assert install['installed'] and 'versionName=0.1.58' in install['installedVersions']
shutil.copy2(peer_install,F/'inherited058-installation.json')
shutil.copy2(peer_ota,F/'inherited058-ota-status-history.json')
record={'at':now,'state':'ANDROID059_INTEGRATED_CANDIDATE_READY_SHARED_PHONE_ACCEPTANCE_BUSY',
    'ownerLatest':'现在还有什么东西可以搞；手机是好了，可以用了。',
    'ownerPhoneAvailable':True,'foregroundPausedByOwner':False,
    'latestInstalledFromSharedReceipt':'0.1.58/code58','candidateInstalled':False,
    'source':source,'apk':apk,
    'changes':['Retain both112B legacy and120B dated local recording metadata, validating the inner/outer CRC and keeping original dates/files.',
        'Integrate committed058 OTA capability publication wait and complete-file retention before disconnect, shared foreground transfer ownership, and mobile playback bookmark lifecycle fix.',
        'Keep real nonblocking Android kernel file exclusion, distinguishing genuine concurrent work from filesystem failure.'],
    'checks':{'java':'Production callbacks accepted actual own-test dated120B and legacy112B; damaged date CRC rejected. Merged producer-package OTA transport regression passed including deferred retention and warming capability.',
        'bookmark':'Merged web rebuilt, unchanged synthetic DOM regression passed playback ticks, pause, library return and switching recording; not a real-phone playback result.',
        'native':'Reused prior16KiB production library; exact native source/Cargo inputs compared to5197a7b. No repeat native compilation, inference, training or weights changed.',
        'apk':'Same signing certificate, source and packaged web/native bytes, all3 ELF plusAPK16KiB alignment checked.'},
    'failureRetained':'First DOM invocation used the pre-merge dist and reproduced8 bookmark sections. The runner was corrected to build merged source before the unchanged test; first failure is retained separately.',
    'sharedPhoneProgress':{'installed058Receipt':str(F/'inherited058-installation.json'),
        'otaStatusHistory':str(F/'inherited058-ota-status-history.json'),
        'lastObservedPhase':history[-1]['phase'],'lastObservedAt':history[-1]['at'],
        'meaning':'Other existing flow observed full1359700B transfer followed by exact running-identity complete phase. Await its final ordinary-UI/maintenance receipt; do not replace the active058 test or declare item1 fully accepted.'},
    'remaining':['When the existing shared lease is released, recheck actual installed version and install059 only if still needed; never overwrite a newer candidate.',
        'Actual ordinary App recording control start/pause/resume/stop with new own sample, then receive/playback/delete confirm/cancel and recoverable interruption.',
        'Inherit the existing OTA/maintenance final receipt, retaining any failed attempts and original34 recordings.',
        'Public isolated library restore, selected-format save, copy and local-only share recipient, then return to original library.',
        'External Word/Excel sample filling and other original36-row parity gaps remain open; model quality/physical release requirements retain their own pending gates.'],
    'next':'共享手机058普通OTA/维护占用结束后先读取其最终收据与实际安装版本，补059日期格式修复所需普通控制/仅新录音回听删除和公开库系统保存复制分享；已有实证不重跑。设备忙时不抢占，不把候选构建算真机或售卖通过。',
    'modelsRun':False,'phoneUiActionsThisBatch':False,'boardLeaseClaimed':False,
    'ownerAccepted':False,'customerResult':None,'wholeProductQualified':False}
write(F/'result059.json',record)
path=R/'docs/product_backlog.json';raw=path.read_bytes();d=json.loads(raw)
frontend=d['owner_module_execution']['frontendWindowsMobile20261102'];task=frontend['ownerDevicePhoneClosure055']
task['continuation058']=record
task['state']=record['state'];task['next']=record['next'];task['candidateVersion']='0.1.59/code59, not installed'
task['currentCandidateSourceCommit']=source['frontendSourceCommit']
task['latestInstalledVersionObservation']={'version':'0.1.58/code58','receipt':str(F/'inherited058-installation.json'),'at':install['at']}
phone=task['ordinaryPhoneContinuation'];phone['foregroundAvailabilityNow']=True
phone['foregroundPausedByOwner']=False;phone['latestOwnerRaw']=record['ownerLatest'];phone['state']=record['state']
frontend['state']=record['state'];n=d['owner_module_execution']['nextBatch']
n['status']=record['state'];n['at']=now;n['next']=record['next']
assert path.read_bytes()==raw,'Concurrent canonical write; retry from current source'
temp=path.with_suffix('.059.tmp');write(temp,d);os.replace(temp,path)
entry=f'''\n\n## {now}｜第1项续作：059合并日期元数据、058升级与回听修复；源码及候选保护，真机共享占用未抢\n\nOwner现已说明手机可用，本轮不再沿用“Owner正在玩手机”的前台暂停。初查实际安装057、已解锁且Companion前台；随即发现另一既有流程持有13:22:59“Companion手机057普通OTA及维护验收”，它已推进058。本侧只查元数据和一次现有App树，未点击、安装、领BLE/COM/SWD占用或发送跨聊天steer，未重问已有授权；不安装旧056覆盖新版本。\n\n源检查发现057/058仍在Java NativeRecordingControl与Rust local_descriptor一侧限定112B，而本侧056已验证实际新e7的120B日期扩展。后端合并9f518bf（含7247985的FINISH完整文件保留后才断开、CRV2发布等待）至本侧5197a7b，保留严格112/120B内外CRC、原日期、原文件和实际内核flock（EINTR重试、真正并发拒绝），生产native文件/Cargo输入与已构建5197a7b逐一Git比较无差异。合并提交{source['backendSourceCommit']}已远端读回。前端承接95763801/72a38c4b及前台传输所有权修复，Android候选改059避免同在试装058；主源{source['frontendSourceCommit']}已推送读回。Windows未打包/未安装，本侧没有更换手机版本。\n\n合并后生产Java校验通过：实际新e7日期120B/旧112B与损坏CRC拒绝；完整签名生产包的传输、延后FINISH保留、发布中的身份前缀及重连身份校验等host检查通过。首次DOM回归误用旧dist，播放4次轮询后重复8个书签区域的失败已保留；先构建合并后网页再跑原不变回归，播放/暂停/退出/换录音均通过。它们仍是host/合成DOM证据，不能代替普通手机控制/回听。复用同源已验native产物，未重编native/推理/训练；Gradle单工作器、768MiB堆、低优先级19.597秒完成。APK0.1.59/code59，{apk['bytes']}B，SHA{apk['sha256']}，原050r2/055签名一致、包内网页与3个原生库精确匹配、ELF/ZIP16KiB兼容均过。\n\n共享058安装收据显示13:28:27已安装成功；另一流程的OTA状态历史最后13:33:56到complete，传入1359700B并进入精确运行身份验证。只保留其状态/安装收据供接续，不以状态片段代替其普通界面/维护完整终态；原记录中Android native golden的5个输出硬链接权限错误仍保留，不能声称全部native通过。共享占用当前仍在，不抢装059。原34录音、本轮新样本边界、公开库恢复后必须切回、36项Owner待验及售卖未合格均保留。下一动作沿nextBatch先承接他方终态与最新实际版本，再普通控制/接收/回听/删除、公开资料保存复制本机分享；AI表样、跨会模型指标等原待办不移除。\n'''
with (R/'docs/development_log.md').open('a',encoding='utf8') as out:out.write(entry)
archive=F/'canonical-backlog-and-log-after059.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for name in ['product_backlog.json','development_log.md']:z.write(R/'docs'/name,'docs/'+name)
write(F/'preservation059.json',{'at':now,'archive':archive.name,'archiveSha256':sha(archive),
    'canonicalFiles':[{'path':'docs/'+name,'sha256':sha(R/'docs'/name)} for name in ['product_backlog.json','development_log.md']],
    'source':source,'apkSha256':apk['sha256'],'audioPayloadUploaded':False})
for name in ['integrate_control058.py','finish_control059.py','build_verify_control059_apk.py','protect_control059.py']:
    dest=S/'tools/qa/phone_closure059'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(W/name,dest)
for name in ['product_backlog.json','development_log.md']:shutil.copy2(R/'docs'/name,S/'docs'/name)
dest=S/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058'
shutil.copytree(F,dest,dirs_exist_ok=True)
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
    p=subprocess.run(['git',*args],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace')
    assert p.returncode==0,p.stdout+p.stderr
    return p.stdout.strip()
git('add','--','tools/qa/phone_closure059','docs/product_backlog.json','docs/development_log.md')
git('add','-f','--','docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058')
git('-c','user.name=Codex','-c','user.email=codex@local','commit','-m','Preserve unified Android059 candidate and shared-phone acceptance workpoint')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current')
git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
assert git('ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
for name in [archive.name,Path(apk['apk']).name,'result059.json']:
    rel='docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/'+name
    p=subprocess.run(['git','show',pin+':'+rel],cwd=S,capture_output=True)
    assert p.returncode==0 and hashlib.sha256(p.stdout).hexdigest()==sha(F/name),name
receipt={'at':now,'deliveryCommit':pin,'branch':branch,'remoteHeadReadback':True,
    'trackedArchiveAndApkHashesVerified':True,'candidateInstalled':False,
    'foregroundPausedByOwner':False,'sharedPhoneBusy':True}
write(F/'remote059-readback.json',receipt)
print(json.dumps(receipt,ensure_ascii=False))
