from pathlib import Path
import json,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109'
p=A/'apps/mobile/src/App.tsx';raw=p.read_bytes();old=b"onOrganize={detail?.minutes?()=>{if(busy||updateRunning)return;const panel=document.querySelector<HTMLDetailsElement>('.existing-minutes');if(panel){panel.open=true;panel.scrollIntoView({block:'start'});}}:undefined}"
new=b"onOrganize={detail?.minutes?()=>{if(busy||updateRunning)return;selectDetailTab('minutes');window.requestAnimationFrame(()=>{const panel=document.querySelector<HTMLDetailsElement>('.existing-minutes');if(panel){panel.open=true;panel.scrollIntoView({block:'start'});}});}:undefined}"
if old in raw:assert raw.count(old)==1;p.write_bytes(raw.replace(old,new))
else:assert raw.count(new)==1
p=A/'apps/android/app/build.gradle';raw=p.read_bytes()
if b'versionCode 162'in raw:assert raw.count(b'versionCode 162')==1;p.write_bytes(raw.replace(b'versionCode 162',b'versionCode 163').replace(b"versionName '0.1.162'",b"versionName '0.1.163'"))
else:assert raw.count(b'versionCode 163')==1
paths=['apps/mobile/src/App.tsx','apps/android/app/build.gradle'];g=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
subprocess.run(g+['add','--',*paths],cwd=A,check=True);subprocess.run(g+['diff','--cached','--check','--',*paths],cwd=A,check=True);subprocess.run(g+['commit','--only','-m','Open chosen meeting organization controls from every reading pane','--',*paths],cwd=A,check=True)
old=R/'docs/handoffs/20261110-android-media-import/android162/source.json';d=json.loads(old.read_bytes());d.update(versionCode=163,versionName='0.1.163',frontendSourceCommit=subprocess.check_output(g+['rev-parse','HEAD'],cwd=A,text=True).strip(),previous162NativeRouteFailureRetained=True,installed=False)
p=old.parent.parent/'android163';p.mkdir(exist_ok=False);(p/'source.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('PHONE163_FIXES_TEMPLATE_ROUTE_FROM_ASSISTANT_NO_MODEL_NATIVE_CHANGES')
