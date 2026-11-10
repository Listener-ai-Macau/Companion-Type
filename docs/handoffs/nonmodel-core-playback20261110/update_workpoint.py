from pathlib import Path
from datetime import datetime
import json,os
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;p=R/'docs/product_backlog.json';raw=p.read_bytes();d=json.loads(raw)
n=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104'];b=n['ownerCoreAcceptanceCandidate20261109'];a=b['activeNonmodelCompletion20261110'];now=datetime.now().astimezone().isoformat(timespec='seconds')
a.update(updatedAt=now,state='ANDROID120_PHONE_PLAYBACK_CORRECTION_AND_INTERRUPTION_PASSED_SETTINGS121_NATIVE_BUILD_RUNNING',installed=True,currentInstalledAndroid='0.1.120',currentInstalledWindows='0.1.82',authorizedPhoneOnlineAtPackageCompletion=True)
a['dependencyObservation']={'authorizedAndroidOnline':True,'model':'Xiaomi13Ultra 2304FPN6DC','checkedThrough':'ADB device + FF48 MI01 ADB interface','action':'Only owned non-main virtual display for local public QA. No BLE, recording-card access or owner main-display operation.'}
a['nativePhoneResults']={key:json.loads((C/'android120'/name).read_text()) for key,name in [('installation','installation.json'),('playbackCorrection','playback-ui-result.json'),('processInterruption','interruption-result.json')]}
a['nativeAcceptanceRemaining']=['Native settings121 installed/restarted: appearance, default speed/resume toggle, permission status and dirty AI exit guard.','Ordinary backup/restore of new public library including checkpoint and correction, then exact purge of only owned public copy.','Source-time boundary movement if actual public audio contains multiple decoded parts; original audio remains untouched.']
a['settingsAddition']={'ownerQuote':'快点把东西全部做完，要开售了；然后要考虑那设置的东西。已经开了usb调试了','source':'76da5cf6ec359f49aa36b618d4710159c9431569','buildRun':42743230795,'implemented':['外观跟随系统/浅色/深色，兼容原外观选择','默认回听倍速，已有录音保留上次倍速','续播开关，不自动开播','真实附近设备/通知权限与应用版本','常用设置优先，AI服务折叠，未保存配置离开确认'],'runtimeQualified':False}
a['next']='完成同一非模型批次121设置真机验收及公开资料备份/恢复/精确删除，恢复原资料、释放手机，再保护源码和安装包。继续原待办内可执行非模型核心，模型质量与硬件依赖不冒充已完成。'
b['next']=a['next'];b['lastOwnerQuote']='已经开了usb调试了';b['latestOwnerContinuation']={'at':now,'quote':'已经开了usb调试了','decision':'授权手机已真实ADB在线，继续已授权后台本机流程；原非模型优先和设置要求保留。','workpoint':'ownerCoreAcceptanceCandidate20261109.activeNonmodelCompletion20261110'}
for row in n['ownerCompetitiveParity20261105']['coverage']:
 if row['id'] in ['playback','editing','premium_ui']:row['currentNonmodelBatch']='ownerCoreAcceptanceCandidate20261109.activeNonmodelCompletion20261110'
temp=p.with_suffix('.phone120-point.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');assert p.read_bytes()==raw;os.replace(temp,p);print('Original workpoint updated; sale qualification and owner acceptance unchanged.')
