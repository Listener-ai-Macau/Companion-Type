from pathlib import Path
from datetime import datetime
import json,re,copy,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];before=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);c=a['ownerProductClosure20261112'];u=c['ownerUiUsabilityRework20261112'];out=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/windows113-local');b=json.loads((out/'result.json').read_bytes());at=datetime.now().astimezone().isoformat(timespec='seconds')
assert b['sourceCommit']=='1c6cceb4514dd229ed3fcdd79e9a007d02943250' and b['version']=='0.1.113'
p=psutil.Process(21176);assert abs(p.create_time()-1794484736.093089)<0.1
build=dict(directory=str(out),sourceRoot='E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source',sourceCommit=b['sourceCommit'],normalProductBaseline='bd4b902795c6103e34d7b4f5f09a99c9f6e03bfe',toolSessionId=26891,worker=dict(pid=p.pid,createdAt=p.create_time()),normalWebBuildPassed=True,state=b['state'],installed=False)
u.update(updatedAt=at,state='WINDOWS113_QUIET_SYNC_NORMAL_RELEASE_BUILD_IN_PROGRESS',currentWindowsBuild=build)
u['quietSyncFeedback'].update(newNativeBuildStarted=True,normalBuild=build,state='SOURCE_VERIFIED_NORMAL113_BUILD_RUNNING')
dep=c['physicalAcceptanceDependency'];dep.update(observedAt=at,state='LATEST_BOARD827_INSTALLATION_REQUIRES_MATCH_BEFORE_OWNER_ONLY',firmwareIdentityVerifiedByOriginalInstaller=False,latestReadOnlySharedBoardSnapshot=json.loads((R/'docs/board_turn.json').read_bytes()),latestEmbeddedProgress='Original IMU thread reports actual66827 raw-IMU capture and continuing mouse integration. Preserve826 receipt as previous; do not assume826 is still installed. No board access by this UI task.')
next_action='Windows113安静后台收取正常包构建中；源于已交付112，只合本轮同步显示，不混入其它鼠标候选。完成后独立核MSI、原生连续流程与真实重开、保资料升级，同批交付113/142。原IMU线程已报告新827安装，实卡Owner轮前须重新绑定最新正常包/安装身份和实际释放；不影响非固件收口，不重复旧112弹窗。'
a.update(updatedAt=at,state='QUIET_SYNC113_SOURCE_VERIFIED_NORMAL_BUILD_RUNNING',next=next_action,knownJobState='Only normal113 builder is active here; exact process/session/currentWindowsBuild retained. No Owner popup/app/board/model job. Current installedWindows112/Android142 unchanged; independent hardware work progressed to827.')
m['currentBatch'].update(at=at,state=a['state'],done='Owner原话已落实到同步显示：连接后继续自动收取，正常页面安静，主动查看才展示进度；受影响源码状态及连续资料流程已复核，正常113正在构建。',remaining='113包核验、实际原生自验/保资料升级、同批交付、Owner引导体验待完成；当前实板新827需重新匹配，原长录/模型/售卖未验保持。',next=next_action,ownerExperienceAccepted=False)
m['nextBatch'].update(at=at,status=a['state'],next=next_action)
def splice(key,old,new):
 global text
 hits=[]
 for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
  value,length=json.JSONDecoder().raw_decode(text[match.end():])
  if value==old:hits.append((match,length))
 assert len(hits)==1,(key,len(hits));match,length=hits[0];text=text[:match.end()]+json.dumps(new,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+length:]
splice('activeNonmodelCompletion20261110',before,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf8'))
print(json.dumps(dict(state=a['state'],build=build,physicalGate=dep['state']),ensure_ascii=False))
