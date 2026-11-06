from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent
F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12';F.mkdir(parents=True,exist_ok=True)
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
raw_quote='先，那你优先把那个前两项给搞了，然后的话。继续做这个事情，然后做完这些事情就可以说。我们只剩下模型能力没做了，对吧？这个时间进度大概还要多久？'
record={'at':now,'ownerQuote':raw_quote,'state':'PRIORITY12_READY_FOR_PHONE_OTHER_EXISTING_LEASE_ACTIVE',
    'priority':['Ordinary phone/device recording control, only own-new sample receive/playback/delete/recovery and OTA/maintenance final receipts.',
        'Installed ordinary App selected-content SAF save, clipboard paste and ACTION_SEND recipient bytes/grants, then original-library return.'],
    'existingWorkpointPreserved':'Android059 compiled/verified/protected; installed058 maintained by existing embedded flow. Original36-row backlog and model directives preserved.',
    'estimate':{'engineeringAndAcceptanceHours':[4,8],'planningAllowance':'One working day for these two scopes, conditional on continuous device access and no new substantive native/firmware blocker.',
        'basis':'Control/OTA/format implementations already exist; partial real-phone receipts and unified059 package available. Remaining main work is ordinary end-to-end execution, directly related repair, content verification and preservation.',
        'notAWholeProductSaleDate':True,'sharedResourceWaitNotPredictable':True},
    'reusedEvidence':['docs/handoffs/20261106-companion-device-management/phone055-management-acceptance.json',
        'docs/handoffs/20261106-companion-device-management/phone056-ordinary-control-acceptance.json',
        'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/inherited058-ota-status-history.json'],
    'remainingPhoneChecks':['059 dated-metadata compatibility in ordinary App control/recovery as affected; no repeated unrelated pairing or OTA if final existing receipt suffices.',
        'Pause/resume/stop recording and real playback pause/resume/natural completion; controlled delete confirmation/cancel of a newly created own session.',
        'Public fixture ordinary restore, selected TXT/MD/DOCX/PDF/XLSX/PPTX/mm/PNG save/share and exact text copy; validate actual recipient content; return original library.'],
    'preparedThisTurn':['Phone drivers require exact own shared lease, unlocked/on screen and permitted foreground before each input; allocate/remove only own debugging forward.',
        'Local-only share recipient now also offers ordinary public-text paste/verification; no Internet, contacts or broad storage permission. Unexpected clipboard text is not recorded.',
        'Actual phone/export acceptance remains false until execution; preparation is not functional progress.'],
    'notOnlyModelsAfterTheseTwo':{'knownSoftwareGaps':['AI fill external Word/Excel sample fields','Remaining mobile import/organization/playback/editing flows and full cross-device parity','Account/shared-library/team and third-party integrations under full competitor scope'],
        'knownPhysicalReleaseGaps':['Actual battery sampling/charge/low-battery preservation/current/endurance','Pickup/first-word and actual audio qualification','Production signing and distribution','Companion screen/touch retained under Owner pause'],
        'source':'Existing36-row coverage plus embedded.releaseReadiness/blockedItems; no new feature scope added.'},
    'actualNewPhoneChecksPassed':False,'wholeProductQualified':False,
    'next':'Wait for existing phone/board lease final receipt/release, then recheck installed identity and claim one ordinary059 control/export item. Keep058/newer versions if candidate superseded; no cross-chat steering or lease stealing.'}
(F/'priority-and-estimate.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
path=R/'docs/product_backlog.json';raw=path.read_bytes();d=json.loads(raw)
task=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerDevicePhoneClosure055']
task['ownerPriority12']=record
task['next']=record['next']
n=d['owner_module_execution']['nextBatch'];n['status']=record['state'];n['next']=record['next'];n['at']=now
assert path.read_bytes()==raw,'Concurrent canonical write'
tmp=path.with_suffix('.priority12.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(tmp,path)
with (R/'docs/development_log.md').open('a',encoding='utf8') as out:
    out.write(f'\n\n## {now}｜Owner优先前两项；保留059工作点与实际剩余，先准备接续验收\n\nOwner原话：{raw_quote}\n\n按现有059候选及055/056普通手机、058升级范围估计这两项约4–8小时有效工程/验收，安排留1工作日；受连续设备可用和是否新出原生/固件阻断影响，不作为整机售卖日期。共享手机/板仍由13:22:59的057/058普通OTA维护一项持有；只读同项目状态确认该流程仍在进行、正在优化OTA速度，未发聊天消息steer/未抢句柄或装包。当前P1复用已验配对/目录/指定收取、START/STOP及开始回听；暂停续播/自然结束与受影响日期恢复、受控删除仍待。P2已保护公开虚构资料及本机接收端，补普通粘贴检查和逐动作就绪守卫；本轮只有验收准备，无新增手机通过，不计作产品功能交付。既有原音/原库和36项待办保持。\n\n完成P1/P2不能改写成只剩模型：现有原待办仍有外部表样AI填写、手机部分管理/导入/编辑播放与跨端范围，以及账号团队/集成；嵌软仍有电池充电低电/续航、实际拾音、正式签名与Owner暂停的屏幕。下一步从同一共享占用释放/终态接续，不重复已通过且未受影响的路径。\n')
qa=S/'tools/qa/phone_closure059'
for name in ['phone059_ui.py','phone059_web.cjs','prepare_shareqa059.py','build_share_receiver059.py','checkpoint_priority12_059.py']:
    shutil.copy2(W/name,qa/name)
(qa/'shareqa059').mkdir(exist_ok=True);shutil.copy2(W/'shareqa059/ShareReceiver056.java',qa/'shareqa059/ShareReceiver056.java')
build=json.loads((F/'share-receiver-build.json').read_text(encoding='utf8'))
artifact=Path(build['apk']);assert hashlib.sha256(artifact.read_bytes()).hexdigest()==build['sha256'];shutil.copy2(artifact,F/artifact.name)
for name in ['product_backlog.json','development_log.md']:shutil.copy2(R/'docs'/name,S/'docs'/name)
dest=S/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12';shutil.copytree(F,dest,dirs_exist_ok=True)
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
    p=subprocess.run(['git',*args],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert p.returncode==0,p.stdout+p.stderr;return p.stdout.strip()
git('add','--','tools/qa/phone_closure059','docs/product_backlog.json','docs/development_log.md')
git('add','-f','--','docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12')
git('-c','user.name=Codex','-c','user.email=codex@local','commit','-m','Preserve priority phone closure and public save-copy-share acceptance preparation')
pin=git('rev-parse','HEAD');branch=git('branch','--show-current')
git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
assert git('ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
print(json.dumps({'checkpoint':pin,'remoteReadback':True,'actualNewPhonePass':False,'estimateHours':[4,8],'sharedLeaseBusy':True}))
