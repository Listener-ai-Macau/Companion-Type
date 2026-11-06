from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
from PIL import Image
W=Path(__file__).parent;R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share068';O.mkdir(exist_ok=True)
C=Path('E:/CodexData/Companion/.build-cache/windows-share068');C.mkdir(exist_ok=True);P=C/'package';P.mkdir(exist_ok=True);(P/'Assets').mkdir(exist_ok=True)
sdk=Path('C:/Program Files (x86)/Windows Kits/10');version='10.0.26100.0'
vs=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools');vc=max((vs/'VC/Tools/MSVC').iterdir(),key=lambda p:p.name)
source=W/'windows_shareqa068/ShareReceiver.cpp';shutil.copy2(source,C/'ShareReceiver.cpp')
with Image.open(S/'apps/windows/src-tauri/icons/icon.ico') as icon:
 for name,size in [('Logo44.png',44),('Logo150.png',150),('StoreLogo.png',50)]:
  icon.convert('RGBA').resize((size,size),Image.Resampling.LANCZOS).save(P/'Assets'/name)
manifest='''<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10" IgnorableNamespaces="uap">
 <Identity Name="Denzic.Companion.PublicShareQA068" Publisher="CN=DenzicCompanionQA, OID.2.25.311729368913984317654407730594956997722=1" Version="1.0.0.0" ProcessorArchitecture="x64"/>
 <Properties><DisplayName>Companion 本机分享验收</DisplayName><PublisherDisplayName>Denzic local public QA</PublisherDisplayName><Logo>Assets\\StoreLogo.png</Logo></Properties>
 <Dependencies><TargetDeviceFamily Name="Windows.Universal" MinVersion="10.0.22000.0" MaxVersionTested="10.0.26100.0"/></Dependencies>
 <Resources><Resource Language="zh-CN"/><Resource Language="en-US"/></Resources>
 <Applications><Application Id="App" Executable="ShareReceiver.exe" EntryPoint="ShareQa.App">
 <uap:VisualElements DisplayName="Companion 本机分享验收" Description="只在本机接收本轮公开虚构文件，不联网" BackgroundColor="transparent" Square150x150Logo="Assets\\Logo150.png" Square44x44Logo="Assets\\Logo44.png"/>
 <Extensions><uap:Extension Category="windows.shareTarget"><uap:ShareTarget><uap:SupportedFileTypes>'''+''.join('<uap:FileType>'+ext+'</uap:FileType>' for ext in ['.txt','.md','.docx','.pdf','.pptx','.xlsx','.mm','.png','.srt','.wav','.mp3'])+'''</uap:SupportedFileTypes><uap:DataFormat>StorageItems</uap:DataFormat></uap:ShareTarget></uap:Extension></Extensions>
 </Application></Applications><Capabilities/>
</Package>'''
(P/'AppxManifest.xml').write_text(manifest,encoding='utf8')
includes=[vc/'include',sdk/'Include'/version/'ucrt',sdk/'Include'/version/'shared',sdk/'Include'/version/'um',sdk/'Include'/version/'winrt',sdk/'Include'/version/'cppwinrt']
libs=[vc/'lib/x64',sdk/'Lib'/version/'um/x64',sdk/'Lib'/version/'ucrt/x64']
env={**os.environ,'INCLUDE':'\x3b'.join(map(str,includes)),'LIB':'\x3b'.join(map(str,libs)),'PATH':str(vc/'bin/Hostx64/x64')+';'+os.environ['PATH']}
args=[str(vc/'bin/Hostx64/x64/cl.exe'),'/nologo','/std:c++20','/EHsc','/O1','/MT','/utf-8','/DWINAPI_FAMILY=WINAPI_FAMILY_APP','/D_WIN32_WINNT=0x0A00','/Fo'+str(C/'ShareReceiver.obj'),'/Fe'+str(P/'ShareReceiver.exe'),str(C/'ShareReceiver.cpp'),'/link','/SUBSYSTEM:WINDOWS','/APPCONTAINER','windowsapp.lib']
started=time.perf_counter()
if (O/'compile.log').exists():shutil.copy2(O/'compile.log',O/('compile-prior-'+str(time.time_ns())+'.log'))
run=subprocess.run(args,cwd=C,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
(O/'compile.log').write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0,(run.stdout+run.stderr)[-6000:]
package=O/'Companion-Public-Share-QA068.msix'
run=subprocess.run([str(sdk/'bin'/version/'x64/MakeAppx.exe'),'pack','/d',str(P),'/p',str(package),'/o'],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
(O/'pack.log').write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0,(run.stdout+run.stderr)[-5000:]
shutil.copy2(source,O/'ShareReceiver.cpp');shutil.copy2(P/'AppxManifest.xml',O/'AppxManifest.xml')
record={'state':'PUBLIC_LOCAL_SHARE_TARGET_BUILT_NOT_INSTALLED_OR_EXECUTED','identity':'Denzic.Companion.PublicShareQA068','package':str(package),'sha256':hashlib.sha256(package.read_bytes()).hexdigest(),'exeSha256':hashlib.sha256((P/'ShareReceiver.exe').read_bytes()).hexdigest(),'wallSeconds':round(time.perf_counter()-started,3),'onlyExactPublicTitleAccepted':True,'networkCapabilities':False,'securitySettingsChanged':False,'actualShareReceived':False,'modelsRun':False}
(O/'build-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False),flush=True)
