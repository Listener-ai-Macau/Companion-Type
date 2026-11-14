from pathlib import Path
from datetime import datetime
import copy, ctypes, hashlib, json, os, re, subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
S=R/'companion-device-closure055'
O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/owner-guided135-20261114')
D=Path('docs/handoffs/20261113-ui-foundation/reader-clarity/owner135')
G=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
progress=json.loads((O/'owner-progress.json').read_bytes())
user=ctypes.windll.user32
windows=[]
CALLBACK=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
@CALLBACK
def collect(h,_):
    pid=ctypes.c_ulong()
    user.GetWindowThreadProcessId(h,ctypes.byref(pid))
    if pid.value==progress['promptPid'] and user.IsWindowVisible(h):
        title=ctypes.create_unicode_buffer(512)
        user.GetWindowTextW(h,title,512)
        windows.append(dict(pid=pid.value,title=title.value,visible=True))
    return True
user.EnumWindows(collect,0)
assert any(x['title'].startswith('Companion 整段使用体验') for x in windows), windows
at=datetime.now().astimezone().isoformat(timespec='seconds')
receipt=dict(at=at,state=progress['state'],version=progress['version'],sourceCommit=progress['sourceCommit'],promptWindows=windows,controllerPid=progress['controllerPid'],reviewSpec=progress['reviewSpec'],ownerStarted=bool(progress.get('ownerStartedAt')),ownerAccepted=False,boardLease=False,newMicOrModelCommands=0,engineeringReceipt=str(R/'docs/handoffs/20261113-ui-foundation/reader-clarity/notebook135158-delivery.json'))
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
save(O/'original-guide-visible.json',receipt)
p=R/'docs/product_backlog.json'; raw=p.read_bytes(); text=raw.decode(); d=json.loads(text)
u=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110']['ownerProductClosure20261112']['ownerUiUsabilityRework20261112']
old=copy.deepcopy(u); attempt=u['currentOwnerAttempt']
assert attempt['version']=='0.1.135'
attempt.update(state=progress['state'],originalGuideVisibleAt=at,promptPid=progress['promptPid'],controllerPid=progress['controllerPid'],guideVisibleReceipt=str(O/'original-guide-visible.json'),ownerAccepted=False)
u['preOwnerEngineeringAcceptance20261112']['ownerPromptStarted']=True
hits=[]
for m in re.finditer(r'(?m)^([ \t]*)"ownerUiUsabilityRework20261112":\s*',text):
    v,n=json.JSONDecoder().raw_decode(text[m.end():])
    if v==old:hits.append((m,n))
assert len(hits)==1; m,n=hits[0]
result=text[:m.end()]+json.dumps(u,ensure_ascii=False,indent=2).replace('\n','\r\n'+m.group(1))+text[m.end()+n:]
assert p.read_bytes()==raw
p.write_bytes(result.encode())
p=R/'docs/development_log.md';raw=p.read_bytes();text=raw.decode()
marker='<!-- ui116-owner-guided135-20261114 -->';i=text.index(marker)+len(marker)
addition='\r\n'+at+' 原共享验收窗实际可见，控制器与窗口进程正常；当前状态 '+progress['state']+'。Owner尚未开始，未记UI通过；同一独立公开会议按“读懂→补充→带走/重开”带路，每条问题分别保留。工程自验与实际135/158交付收据沿原135158批次，不新跑无关检查。\r\n'
assert p.read_bytes()==raw;p.write_bytes((text[:i]+addition+text[i:]).encode())
files=['tools/qa/core_acceptance20261109/owner_saved_meeting.py']
for name in ['review-spec.json','preparation.json','original-guide-visible.json']:
    p=S/D/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((O/name).read_bytes());files.append((D/name).as_posix())
helper=S/D/'record_owner135_ready.py';helper.write_bytes(Path(__file__).read_bytes());files.append((D/helper.name).as_posix())
subprocess.run(G+['diff','--check','--',*files],cwd=S,check=True)
subprocess.run(G+['add','--',*files],cwd=S,check=True)
subprocess.run(G+['commit','--only','-m','Prepare original single-window guided frontend135 experience','--',*files],cwd=S,check=True)
head=subprocess.check_output(G+['rev-parse','HEAD'],cwd=S,text=True).strip()
env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe','GIT_TERMINAL_PROMPT':'0'}
branch='work/owner135-guided-frontend-20261114'
subprocess.run(G+['push','origin',head+':refs/heads/'+branch],cwd=S,env=env,check=True,timeout=60)
remote=subprocess.check_output(G+['ls-remote','origin','refs/heads/'+branch],cwd=S,env=env,text=True,timeout=45).split()[0]
assert remote==head
save(O/'guide-source-protection.json',dict(at=at,sourceCommit=head,remoteBranch=branch,remoteVerified=True,exactPaths=files,ownerAccepted=False))
print(json.dumps(dict(state=progress['state'],originalGuideVisible=True,sourceCommit=head,remoteVerified=True),ensure_ascii=False))
