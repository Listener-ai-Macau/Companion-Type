from pathlib import Path
import json,os,psutil,subprocess,time,uuid
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows060-system-handoff';C=Path('E:/CodexData/Companion/.build-cache/windows051')/('headless-diagnostic-'+uuid.uuid4().hex[:8]);C.mkdir()
source=C/'public.html';source.write_text('<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"></head><body><h1>公开虚构文档诊断</h1><p># literal &lt;A&amp;B&gt; 😀</p></body></html>',encoding='utf8')
exe=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe');results=[]
for kind in ['pdf','png']:
 output=C/('public.'+kind);profile=C/('profile-'+kind)
 args=[str(exe),'--headless=new','--disable-gpu','--disable-extensions','--disable-background-networking','--disable-sync','--no-first-run','--no-default-browser-check','--no-pdf-header-footer','--user-data-dir='+str(profile)]
 args+=['--print-to-pdf='+str(output)] if kind=='pdf' else ['--hide-scrollbars','--force-device-scale-factor=1','--virtual-time-budget=1000','--window-size=800,600','--screenshot='+str(output)]
 args+=[source.as_uri()];begin=time.monotonic();p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 code=p.wait(timeout=20);parent_seconds=time.monotonic()-begin;at_parent=output.exists()
 end=time.monotonic()+15
 while not output.exists() and time.monotonic()<end:time.sleep(.1)
 appears=output.exists();at_output=time.monotonic()-begin
 try:stdout,stderr=p.communicate(timeout=10)
 except subprocess.TimeoutExpired:stdout=b'';stderr=b'Output pipes remained open after parent exit; unique QA family retained for scoped inspection.'
 result={'format':kind,'parentExitCode':code,'parentExitSeconds':round(parent_seconds,3),'outputAtParentExit':at_parent,'outputEventuallyExists':appears,'observedOutputSeconds':round(at_output,3),'bytes':output.stat().st_size if appears else None,'headlessOnly':True}
 (C/(kind+'-stdout.log')).write_bytes(stdout);(C/(kind+'-stderr.log')).write_bytes(stderr)
 (F/('headless-'+kind+'-stderr-public.log')).write_bytes(stderr)
 results.append(result);print(json.dumps(result),flush=True)
(F/'headless-lifetime-diagnosis.json').write_text(json.dumps({'result':results,'diagnosticFolderLocal':str(C),'sourceIsPublicSynthetic':True,'noOwnerBrowserProfileUsed':True},ensure_ascii=False,indent=2),encoding='utf8')
