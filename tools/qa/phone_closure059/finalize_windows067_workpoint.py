from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent
rel=Path('docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering');G=R/rel
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds');proof=json.loads((G/'remote-readback.json').read_text(encoding='utf8'));assert proof['remoteReadback']
path=R/'docs/product_backlog.json';raw=path.read_bytes();data=json.loads(raw);task=data['owner_module_execution']['frontendWindowsMobile20261102']['ownerDevicePhoneClosure055']
for slot in [task['windows067Delivery'],task['priority12Actual']['windows067Actual']]:slot['remoteProtection']=proof
task['priority12Actual']['next']=task['next'];task['ownerPriority12']['next']=task['next'];task['ownerPriority12']['latestWindows067']={'at':now,'receipt':str(G/'progress-result.json'),'installed':True,'actualEightSaveAs':True,'copyExact':True,'shareRecipientPending':True,'phoneFinalPending':True,'remoteCommit':proof['commit']}
assert path.read_bytes()==raw,'Concurrent update, retry fresh'
temp=path.with_suffix('.windows067final.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,path)
with (R/'docs/development_log.md').open('a',encoding='utf8') as stream:stream.write(f'''\n\n- {now}｜Windows067本批交付远端回读完成：{proof['commit']}；MSI与真实八格式保存/内容收据Git blob SHA回读匹配。首次既有ssh.github.com:443超时，未改代理/DNS或安全设置；同一GitHub原生22端口连接成功后仅本次命令使用该正常SSH入口，保StrictHostKeyChecking，成功push及ls-remote核对。首次附加证据白空格检查把Windows CRLF当尾空白，改QA脚本范围并显式cr-at-eol后通过，未改产品/历史日志来掩盖。原剪贴板OLE失败保留且工具入口已退役，不能再复用。当前所有本侧Windows QA进程/桌面已关闭，输入桌面仍Default；他方17:32设备租约未释放，不碰手机/板。原前两项下一步在task/ownerPriority12/priority12Actual三处同步，不恢复旧059候选或宣称只剩模型。\n''')
record={'at':now,'firstSsh443Attempt':'TIMEOUT_RETAINED','successfulTransport':'Native GitHub SSH22, per-command only; no proxy/DNS/security changes','remoteCommit':proof['commit'],'stagedWhitespaceIssue':'Windows CRLF interpreted as trailing whitespace; QA-only check with cr-at-eol passed','modelsRun':False}
(G/'protection-transport.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for name in ['product_backlog.json','development_log.md']:shutil.copy2(R/'docs'/name,S/'docs'/name)
for name in ['remote-readback.json','protection-transport.json']:shutil.copy2(G/name,S/rel/name)
for name in ['finish_windows067_protection.py','finalize_windows067_workpoint.py']:shutil.copy2(W/name,S/'tools/qa/phone_closure059'/name)
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
 p=subprocess.run(['git','-c','maintenance.auto=false',*map(str,args)],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert p.returncode==0,(p.stdout+p.stderr)[-4000:];return p.stdout.strip()
git('add','--','docs/product_backlog.json','docs/development_log.md','tools/qa/phone_closure059/finish_windows067_protection.py','tools/qa/phone_closure059/finalize_windows067_workpoint.py')
git('add','-f','--',rel/'remote-readback.json',rel/'protection-transport.json')
git('commit','-m','Record remote Windows067 delivery and retain remaining phone and share workpoint')
head=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
assert git('ls-remote','origin',f'refs/heads/{branch}').split()[0]==head
assert not git('status','--porcelain')
print(json.dumps({'artifactCommit':proof['commit'],'finalMetadataCommit':head,'remoteConfirmed':True,'sourceWorktreeClean':True,'wholeProductQualified':False},ensure_ascii=False),flush=True)
