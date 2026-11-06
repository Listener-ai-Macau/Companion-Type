from pathlib import Path
import hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent
rel=Path('docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12');G=R/rel/'windows067-literal-and-rendering'
shutil.copy2(W/'preserve_windows067_delivery.py',S/'tools/qa/phone_closure059/preserve_windows067_delivery.py')
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(*args):
 r=subprocess.run(['git','-c','maintenance.auto=false',*map(str,args)],cwd=S,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert r.returncode==0,(r.stdout+r.stderr)[-5000:];return r.stdout.strip()
git('add','--','tools/qa/phone_closure059/preserve_windows067_delivery.py')
git('-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol','diff','--cached','--check','--','tools/qa/phone_closure059')
files=[name for name in git('diff','--cached','--name-only','-z').split('\0') if name]
assert all(name.startswith(('docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/','tools/qa/phone_closure059/','docs/product_backlog.json','docs/development_log.md')) for name in files)
assert not any(any(token in name for token in ['data-before','data-after','metadata-before','installed-before','upgrade067-private','webview/']) for name in files)
print(json.dumps({'stagedPublicEvidenceAndHelpers':len(files),'msiBytes':next(G.glob('*.msi')).stat().st_size,'privateUserProfilesNotIncluded':True}),flush=True)
if files:git('commit','-m','Deliver Windows067 faithful documents with actual eight-format Save As acceptance')
else:assert git('show','-s','--format=%s')=='Deliver Windows067 faithful documents with actual eight-format Save As acceptance'
pin=git('rev-parse','HEAD');branch=git('branch','--show-current');git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
assert git('ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
for file in [next(G.glob('*.msi')),G/'progress-result.json',G/'system-handoff/actual-content-result.json']:
 relative=rel/G.name/file.relative_to(G);r=subprocess.run(['git','show',pin+':'+relative.as_posix()],cwd=S,capture_output=True)
 assert r.returncode==0 and hashlib.sha256(r.stdout).hexdigest()==hashlib.sha256(file.read_bytes()).hexdigest()
record={'commit':pin,'remoteReadback':True,'msiAndActualAcceptanceBlobsVerified':True,'version':'0.1.67','actualSaveAsFormats':8,'wholeProductQualified':False}
(G/'remote-readback.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False),flush=True)
