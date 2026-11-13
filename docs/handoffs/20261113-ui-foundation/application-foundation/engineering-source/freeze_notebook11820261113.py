from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,os,re,subprocess,copy
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');B=R/'docs/handoffs/20261112-product-closure/windows118';B.mkdir(exist_ok=False)
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol'];at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
head=lambda root:subprocess.check_output(git+['rev-parse','HEAD'],cwd=root,text=True).strip()
assert head(S)=='4ca0f7509fff69543311d1ed8c5808422eecba5c'
assert not subprocess.check_output(git+['status','--porcelain'],cwd=E,text=True).strip()
parent=head(S)
if subprocess.run(git+['cat-file','-e',parent+'^{commit}'],cwd=E,capture_output=True).returncode:subprocess.run(git+['fetch','origin',parent],cwd=E,check=True)
subprocess.run(git+['switch','-c','work/notebook118-frozen-20261113',parent],cwd=E,check=True)
assert subprocess.check_output(git+['rev-parse','HEAD:third_party/denzic-platform'],cwd=E,text=True).strip()==head(E/'third_party/denzic-platform')
versions=['package.json','package-lock.json','apps/windows/src-tauri/tauri.conf.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json']
def bump(root):
 for rel,count in [('package.json',1),('package-lock.json',2),('apps/windows/src-tauri/tauri.conf.json',1)]:
  p=root/rel;raw=p.read_bytes();assert raw.count(b'"version": "0.1.117"')==count;p.write_bytes(raw.replace(b'"version": "0.1.117"',b'"version": "0.1.118"'))
 p=root/'apps/windows/src-tauri/Cargo.toml';raw=p.read_bytes();assert raw.count(b'version = "0.1.117"')==1;p.write_bytes(raw.replace(b'version = "0.1.117"',b'version = "0.1.118"'))
 p=root/'apps/windows/src-tauri/Cargo.lock';raw,n=re.subn(rb'(name = "companion-type"\r?\nversion = ")0\.1\.117(")',rb'\g<1>0.1.118\2',p.read_bytes());assert n==1;p.write_bytes(raw)
 p=root/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';raw=p.read_bytes();data=json.loads(raw)
 for name,old in data['lockedInputs'].items():
  new=hashlib.sha256((root/name).read_bytes()).hexdigest()
  if new!=old:assert raw.count(old.encode())==1;raw=raw.replace(old.encode(),new.encode())
 p.write_bytes(raw)
for root in [S,E]:bump(root)
p=S/'tools/qa/core_acceptance20261109/windows_product_ui.cjs';s=p.read_text(encoding='utf-8');s=s.replace("name:'设备与同步',exact:true","name:/^录音卡 ·/").replace("name:'我的记录',exact:true","name:'录音',exact:true").replace("name:'录音与文字',exact:true","name:'文字',exact:true").replace('name:/笔记与资料/','name:/补充/');p.write_bytes(s.replace('\n','\r\n').encode('utf-8'))
for root,paths in [(S,versions+['tools/qa/core_acceptance20261109/windows_product_ui.cjs']),(E,versions)]:
 for args in [['add','--',*paths],['diff','--cached','--check','--',*paths],['commit','--only','-m','Freeze notebook118 on current117 core without changing active recording','--',*paths]]:subprocess.run(git+args,cwd=root,check=True)
record=dict(at=at,state='NOTEBOOK118_FROZEN_ON117_CORE_NORMAL_BUILD_PENDING',version='0.1.118',sourceCommit=head(E),authoringSourceCommit=head(S),sourceRoot=str(E),frozenSourceRoot=str(E),branch='work/notebook118-frozen-20261113',priorDeliveredSource='2433bf662a79ea3b11da657bd59356d3a6c7e4f8',core117Source='bdfeed4cfce5a5f6ad104c4d876c9ed0e577a69e',retainsCurrent117Core=True,active117LongRecordingExecutableOverwritten=False,ownerExperienceAccepted=False,saleQualified=False)
(B/'frozen-source.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf-8');d=json.loads(text);a=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];old=copy.deepcopy(a);u=a['ownerProductClosure20261112']['ownerUiUsabilityRework20261112'];u['designFoundationRework20261113'].update(state='REAL_NOTEBOOK_SOURCE_CHECKED_NORMAL118145_BUILDING',windowsSource=record,androidSource='fbb10d1ee34c241d96829c8307e0cbb5441957b0',sourceWholeJourneyPassed=True,nativeInstalled=False)
a.update(state='NOTEBOOK118145_SOURCE_CHECKED_NORMAL_BUILD_IN_PROGRESS',plannedWindowsVersion='0.1.118',plannedAndroidVersion='0.1.145',plannedVersionsBuilt=False,updatedAt=at,next='118已基于当前117共用核心冻结，145手机源码已冻结。沿原固定源和共享缓存准备同批正常包；旧117长录实际EXE在独立不可变目录，不覆盖、不接板。原生UI隔离自验关闭BLE/重连，集中匹配交付；实体长录由原在途继续，不能用UI测试关闭。',knownJobState='Android145 build exec session95688 running; Windows118 normal build ready in existing fixed source/shared target. Active117 long uses its own frozen-msi-native executable and is unaffected.')
hits=[]
for match in re.finditer(r'(?m)^([ \t]*)"activeNonmodelCompletion20261110":\s*',text):
 value,n=json.JSONDecoder().raw_decode(text[match.end():])
 if value==old:hits.append((match,n))
assert len(hits)==1;match,n=hits[0];text=text[:match.end()]+json.dumps(a,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:];json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf-8'))
for root in [S,E]:subprocess.run(git+['push','-u','origin','HEAD'],cwd=root,env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe'},check=True)
print(json.dumps(record,ensure_ascii=False))
