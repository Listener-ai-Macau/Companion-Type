from pathlib import Path
from datetime import datetime
import json,re,copy,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');out=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/windows114-local');b=json.loads((out/'result.json').read_bytes());p=psutil.Process(4684);assert abs(p.create_time()-1794487610.1067436)<.1;assert b['sourceCommit']=='8f68f19a9d1bc4fde96e79c459418c12e0772b47'and b['version']=='0.1.114';at=datetime.now().astimezone().isoformat(timespec='seconds');build=dict(directory=str(out),sourceCommit=b['sourceCommit'],sourceRoot='E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source',toolSessionId=75634,worker=dict(pid=p.pid,createdAt=p.create_time()),state=b['state'],normalWebBuildPassed=True,installed=False,storageBefore=b.get('storageBefore'))
P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];before=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);u=a['ownerProductClosure20261112']['ownerUiUsabilityRework20261112'];u.update(updatedAt=at,state='CONNECTION114_NORMAL_RELEASE_BUILD_IN_PROGRESS',currentWindowsBuild=build);u['connectionVisibilityFeedback'].update(state='SOURCE_VERIFIED_NORMAL114_BUILD_RUNNING',normalBuild=build)
next_action='实际第一屏/设备主区连接状态与入口已同批收敛并冻结8f68f19a；Windows114正常release正在固定缓存构建，工具75634/PID4684为实据。完成后独立核MSI、原生第一屏/连续流程/真实重开，再保资料升级并交付114/142；未完成前不再派旧113。'
a.update(updatedAt=at,state=u['state'],next=next_action,knownJobState='Only normal114 builder active here. No Owner prompt/app/board/model job;113/142 still actual installed until real upgrade. Exact shared-target worker and storage preflight retained.');m['currentBatch'].update(at=at,state=a['state'],next=next_action);m['nextBatch'].update(at=at,status=a['state'],next=next_action)
def splice(key,old,new):
 global text
 hits=[]
 for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
  v,n=json.JSONDecoder().raw_decode(text[match.end():])
  if v==old:hits.append((match,n))
 assert len(hits)==1;match,n=hits[0];text=text[:match.end()]+json.dumps(new,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:]
splice('activeNonmodelCompletion20261110',before,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf8'));print(json.dumps(build,ensure_ascii=False))
