from pathlib import Path
from datetime import datetime
import copy,json,re,psutil

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');cache=Path('E:/CodexData/Companion/.build-cache/product-closure20261112');at=datetime.now().astimezone().isoformat(timespec='seconds')
def job(entry,directory,session):
    result=json.loads((directory/'result.json').read_bytes())
    matches=[]
    for process in psutil.process_iter(['pid','cmdline','create_time','name']):
        command=process.info['cmdline'] or []
        if len(command)>1 and command[1].replace('\\','/').endswith('/'+entry):matches.append(process.info)
    assert len(matches)<=1
    return dict(directory=str(directory),toolSessionId=session,sourceCommit=result['sourceCommit'],state=result['state'],worker=matches[0] if matches else None,steps=result['steps'],storageBefore=result['storageBefore'],installed=False)
windows=job('build_windows_delivery_local.py',cache/'windows116-local',71010)
android_number=144 if (cache/'android144-local/result.json').exists() else 143
android=job('build_android_local.py',cache/f'android{android_number}-local',26596 if android_number==144 else 99445)
windows_install=R/'docs/handoffs/20261112-product-closure/windows116/installation.json'
if windows_install.exists():
    installation=json.loads(windows_install.read_bytes());assert installation['dataManifestIdentical'];windows.update(installed=True,installation=str(windows_install))
P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];before=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);c=a['ownerProductClosure20261112'];u=c['ownerUiUsabilityRework20261112']
u.update(updatedAt=at,currentWindowsBuild=windows,currentAndroidBuild=android,state='COHERENT_RECORDING_LIBRARY116144_NORMAL_BUILDS_AND_ENGINEERING_REVIEW')
next_action='Windows116/Android143同一录音库批次正常包构建与工程实用续作；116已冻结2433bf66（仅5个明确前端文件），143源7bad2b57（录音库/默认阅读入口/样式，后台AAR不改）。按实物手机安装/隔离公开资料/正常重开与电脑同包原生流程、原资料哈希保留完成后一次打包回读。用户功能检查已取消，后续仅短人感体验；工程公开电脑声音真实ASR/DeepSeek/保存重开已过，实卡/长录等独立范围不虚关。'
if windows['installed']:a['currentInstalledWindows']='0.1.116'
for installed_android in [143,144]:
    receipt=R/f'docs/handoffs/20261110-android-media-import/android{installed_android}/installation.json'
    if receipt.exists():a['currentInstalledAndroid']=f'0.1.{installed_android}'
next_action='电脑116已正常安装并同包原生实际退出/重开通过，247份原资料完全一致；手机143也安装/原资料和真实公开资料回找重开通过。实际143画面发现历史取消导入仍红色常驻，已源头修正并同批正常144构建，保留143收据，不另交143包/派Owner；144升级后只复核该状态、入口和原资料保护，再交一个116/144包。原卡当前IMU占用不访问，Owner不做技术/长录检查。'
a.update(updatedAt=at,state=u['state'],plannedAndroidVersion=f'0.1.{android_number}',next=next_action,knownJobState=f'Windows116 exec71010 PID{windows["worker"]["pid"] if windows["worker"] else "exited"}, installed={windows["installed"]}; Android{android_number} exec{android["toolSessionId"]} PID{android["worker"]["pid"] if android["worker"] else "exited"}. Phone143 own review closed and hold released; current IMU board lease is not accessed here.')
c.update(updatedAt=at,ownerTotalStatus=a['state'])
m['currentBatch'].update(at=at,state=a['state'],remaining='116已安装/原生自验；143实际手机复核发现的历史取消红提示已修，144同批构建/针对性实机复核后交付；Owner无复杂验收待办。',next=next_action);m['nextBatch'].update(at=at,status=a['state'],next=next_action)
def splice(key,old,new):
    global text
    hits=[]
    for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
        value,n=json.JSONDecoder().raw_decode(text[match.end():])
        if value==old:hits.append((match,n))
    assert len(hits)==1;match,n=hits[0];text=text[:match.end()]+json.dumps(new,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:]
splice('activeNonmodelCompletion20261110',before,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf8'))
print(json.dumps(dict(at=at,windows=windows,android=android),ensure_ascii=False))
