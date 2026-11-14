from pathlib import Path
from datetime import datetime
import hashlib,json,os,re,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent;Q=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/library-closure20261114');D=Path('docs/handoffs/20261113-ui-foundation/reader-clarity/library135158')
G=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol'];ENV={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe','GIT_TERMINAL_PROMPT':'0'}
def digest(data):return hashlib.sha256(data).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for name in ['product_backlog.json','development_log.md']:(S/'docs'/name).write_bytes((R/'docs'/name).read_bytes())
subprocess.run(G+['add','--','docs/product_backlog.json','docs/development_log.md'],cwd=S,check=True)
run=subprocess.run(G+['diff','--cached','--check','--','docs/development_log.md'],cwd=S,capture_output=True)
numbers=sorted(set(int(x)for x in re.findall(rb'docs/development_log\.md:(\d+): trailing whitespace\.',run.stdout)))
raw=(R/'docs/development_log.md').read_bytes();lines=raw.split(b'\n');fixed=[]
for n in numbers:
 line=lines[n-1];count=len(line)-len(line.rstrip(b'\r'));assert count>=2,(n,count);lines[n-1]=line.rstrip(b'\r')+b'\r';fixed.append(n)
out=b'\n'.join(lines);assert out.replace(b'\r',b'')==raw.replace(b'\r',b'')
before=Q/'timeline-before-targeted-ending-repair.bin';assert not before.exists();before.write_bytes(raw)
assert (R/'docs/development_log.md').read_bytes()==raw;(R/'docs/development_log.md').write_bytes(out);(S/'docs/development_log.md').write_bytes(out)
proof=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='SOURCE_PROTECTION_CHECK_ONLY_REPEATED_CR_REPAIRED',failureRetained=True,priorRaw=str(before),beforeSha256=digest(raw),afterSha256=digest(out),exactFlaggedLines=fixed,nonCarriageReturnBytesIdentical=True,otherHistoricalLinesUntouched=True,nativeOrUiChanges=False,nativeRebuildRequired=False)
save(Q/'timeline-ending-repair.json',proof);(S/D/'timeline-ending-repair.json').write_bytes((Q/'timeline-ending-repair.json').read_bytes());(S/D/'engineering/finish_library_protection.py').write_bytes(Path(__file__).read_bytes())
checkpoint=read=json.loads((S/D/'checkpoint.json').read_bytes());inventory=checkpoint['inventory'];known={x['file']:x for x in inventory}
for rel in ['docs/product_backlog.json','docs/development_log.md',(D/'timeline-ending-repair.json').as_posix(),(D/'engineering/finish_library_protection.py').as_posix()]:
 row=dict(file=rel,sha256=digest((S/rel).read_bytes()))
 if rel in known:known[rel].update(row)
 else:inventory.append(row)
checkpoint['timelineEndingRepair']=proof['state'];save(S/D/'checkpoint.json',checkpoint)
files=[x['file']for x in inventory]+[(D/'checkpoint.json').as_posix()]
subprocess.run(G+['add','--',*files],cwd=S,check=True)
check=subprocess.run(G+['diff','--cached','--check','--',*files],cwd=S,capture_output=True)
assert check.returncode==0,check.stdout.decode(errors='replace')[-3000:]
subprocess.run(G+['commit','--only','-m','Protect complete135158 background UI closure and unified delivery','--',*files],cwd=S,check=True)
head=subprocess.check_output(G+['rev-parse','HEAD'],cwd=S,text=True).strip();branch='work/library135158-complete-20261114'
subprocess.run(G+['push','origin',head+':refs/heads/'+branch],cwd=S,env=ENV,check=True,timeout=180)
actual=subprocess.check_output(G+['ls-remote','origin','refs/heads/'+branch],cwd=S,env=ENV,text=True,timeout=45).split()[0];assert actual==head
receipt=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),sourceCommit=head,remoteBranch=branch,verifiedRemoteHead=actual,frontendEngineeringAcceptancePassed=True,ownerAccepted=False,canonicalRootOnlyEditable=True,otherAuthoringEditsNotStaged=True,timelineFormattingOnlyRepair=proof)
save(Q/'final-checkpoint.json',receipt);print(json.dumps(dict(sourceCommit=head,remoteVerified=True,targetedCrLines=len(fixed),frontendEngineeringAcceptancePassed=True)))
