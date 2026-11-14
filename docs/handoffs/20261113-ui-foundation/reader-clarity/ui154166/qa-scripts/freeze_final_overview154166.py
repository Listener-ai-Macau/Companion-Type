from pathlib import Path
from datetime import datetime
import copy,hashlib,json,re,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');Q=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/visual-meeting20261114')
G=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
def git(root,*args):return subprocess.check_output(G+list(args),cwd=root,text=True,encoding='utf8').strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
assert json.loads((Q/'overview-r3/result.json').read_bytes())['state']=='VISUAL_OVERVIEW_EXACT_SOURCE_NAVIGATION_THEMES_AND_NARROW_LAYOUT_PASSED'
assert json.loads((Q/'overview-types/result.json').read_bytes())['state']=='BOTH_OVERVIEW_TYPES_PASSED'
desktop=['packages/ui/src/CompanionMeetingNotes.tsx','packages/ui/src/notebookFoundation.css']
shared=['packages/ui/src/'+n for n in ['MeetingOverview.tsx','meetingOverview.css','MeetingReadingFrame.tsx']]
for rel in shared:assert(S/rel).read_bytes()==(A/rel).read_bytes()
qa=['tools/qa/core_acceptance20261109/'+n for n in ['meeting_overview_ui.cjs','meeting_clarity_ui.cjs','windows_visual_meeting_ui.cjs']]
git(S,'add','--',*(shared+desktop+qa));git(S,'diff','--cached','--check','--',*(shared+desktop+qa));git(S,'commit','--only','-m','Open meetings with a visual topic overview and clear access to complete notes','--',*(shared+desktop+qa));author=git(S,'rev-parse','HEAD')
base='93856cbc2ca7e5266e36e550e209c4fb2e994bb6';assert git(E,'rev-parse','HEAD')==base and not git(E,'status','--porcelain')
git(E,'fetch',str(S),author);git(E,'switch','-c','work/notebook-overview154-20261114',base);git(E,'restore','--source='+author,'--',*(shared+desktop))
versions=['package.json','package-lock.json','apps/windows/src-tauri/tauri.conf.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json']
for name,count in [('package.json',1),('package-lock.json',2),('apps/windows/src-tauri/tauri.conf.json',1)]:
 p=E/name;raw=p.read_bytes();assert raw.count(b'"version": "0.1.152"')==count;p.write_bytes(raw.replace(b'"version": "0.1.152"',b'"version": "0.1.154"'))
p=E/'apps/windows/src-tauri/Cargo.toml';raw=p.read_bytes();assert raw.count(b'version = "0.1.152"')==1;p.write_bytes(raw.replace(b'version = "0.1.152"',b'version = "0.1.154"'))
p=E/'apps/windows/src-tauri/Cargo.lock';raw,n=re.subn(rb'(name = "companion-type"\r?\nversion = ")0\.1\.152(")',rb'\g<1>0.1.154\2',p.read_bytes());assert n==1;p.write_bytes(raw)
p=E/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';raw=p.read_bytes()
for rel,old in json.loads(raw)['lockedInputs'].items():
 digest=sha(E/rel)
 if digest!=old:assert raw.count(old.encode())==1;raw=raw.replace(old.encode(),digest.encode())
p.write_bytes(raw);git(E,'add','--',*(shared+desktop+versions));git(E,'diff','--cached','--check');git(E,'commit','-m','Freeze154 visual meeting overview over installed148 unchanged native base')
assert not git(E,'diff',base,'HEAD','--','packages/desktop-input','apps/windows/src','apps/windows/src-tauri/src','packages/core','third_party')
at=datetime.now().astimezone().isoformat(timespec='seconds');old=json.loads((R/'docs/handoffs/20261112-product-closure/windows152/frozen-source.json').read_bytes());proof={**old,'at':at,'version':'0.1.154','sourceCommit':git(E,'rev-parse','HEAD'),'branch':git(E,'branch','--show-current'),'authoringSourceCommit':author,'relatedAuthoringFiles':list(dict.fromkeys(old['relatedAuthoringFiles']+shared+desktop)),'saved152UiSourcePreserved':base,'installed':False,'sourceVisualOverview':str(Q/'overview-r3/result.json'),'normalWindowsBuildPending':True}
H=R/'docs/handoffs/20261112-product-closure/windows154';H.mkdir(exist_ok=False);save(H/'frozen-source.json',proof)
p=A/'apps/android/app/build.gradle';raw=p.read_bytes();assert raw.count(b'versionCode 165')==1;p.write_bytes(raw.replace(b'versionCode 165',b'versionCode 166').replace(b"versionName '0.1.165'",b"versionName '0.1.166'"))
git(A,'add','--',*(shared+['apps/android/app/build.gradle']));git(A,'diff','--cached','--check');git(A,'commit','--only','-m','Use the shared visual meeting overview on the phone with original notes available','--',*(shared+['apps/android/app/build.gradle']))
assert sha(A/'apps/android/app/libs/companion-android-backend.aar')=='39acfbedb8cb4294be0455b3faa40d0033c25cc544aa6a2ae8c964f91a999a96'
old=json.loads((R/'docs/handoffs/20261110-android-media-import/android165/source.json').read_bytes());android={**old,'at':at,'versionCode':166,'versionName':'0.1.166','frontendSourceCommit':git(A,'rev-parse','HEAD'),'installed':False};H=R/'docs/handoffs/20261110-android-media-import/android166';H.mkdir(exist_ok=False);save(H/'source.json',android);save(Q/'source154166.json',dict(at=at,windows=proof,android=android,sourceReview=str(Q/'overview-r3/result.json'),scope='Graphical overview/navigation only; existing meeting facts, exact source text, notes/export, model/native/input behavior retained.'))
p=R/'docs/product_backlog.json';raw=p.read_bytes();text=raw.decode('utf8');d=json.loads(text);a=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];before=copy.deepcopy(a);v=a['ownerProductClosure20261112']['ownerUiUsabilityRework20261112']['completeProductRework20261113']['noteReadabilityFollowup']['visualMeeting20261114']['uiCraftFollowup20261114']['simpleExperienceFollowup20261114'];v.update(updatedAt=at,state='VISUAL_OVERVIEW_SOURCE_PASSED_NORMAL154166_BUILD_PENDING',auditFinding='148主入口仍默认长概览，结论与待确认在长文之后；已改主题选择/单段原文/结论行动问题的并列入口及完整纪要返回。复核正式手机源A已传入正确会议标题，保留，不将S旧手机副本计为实际缺陷。',source154166=str(Q/'source154166.json'),sourceReview=str(Q/'overview-r3/result.json'),next='正常构建154/166，确认实际公开会议图形首屏→主题→原文与完整纪要→笔记/导出和退出重开；同批自验后完整交付，不逐项打断Owner。');a.update(updatedAt=at,next=v['next'])
hits=[]
for m in re.finditer(r'(?m)^([ \t]*)"activeNonmodelCompletion20261110":\s*',text):
 value,n=json.JSONDecoder().raw_decode(text[m.end():])
 if value==before:hits.append((m,n))
assert len(hits)==1;m,n=hits[0];updated=text[:m.end()]+json.dumps(a,ensure_ascii=False,indent=2).replace('\n','\r\n'+m.group(1))+text[m.end()+n:];assert p.read_bytes()==raw;p.write_bytes(updated.encode('utf8'))
p=R/'docs/development_log.md';raw=p.read_bytes();text=raw.decode('utf8');assert text.count('<!-- ui116-simple-experience20261114 -->')==1;note=at+' 针对148真实体验“文字太多，图像化”同批改会议一览：可选择主题图形节点，仅展示所选原文；结论/行动/待确认并列可展开，未列行动如实标明，完整纪要/返回/来源定位/导图/按发言人保持可用，未生成额外事实。源生产组件同一公开半小时原纪要在浅深/320/390/980/1440、键盘与空态/换来源检查通过，两端类型通过。先前手机标题缺口判断来自S旧副本，复核A实际164已贯通，不作修复声称。冻结154/166，154保留148与正常143原生，避开在途149/150；AAR未改，无新模型/云/外放/板操作，152未安装到电脑且未交付Owner；165作为同批中间手机包保留。实际截图发现结果入口仍在主题后，笔记遗留绿色和旧说明；本最终154/166将结果前移并统一笔记区，待正常编译和实际自验。';assert p.read_bytes()==raw;p.write_bytes((text+'\r\n'+note+'\r\n').encode('utf8'))
print(json.dumps(dict(state='VISUAL_OVERVIEW154166_FROZEN',windows=proof['sourceCommit'],android=android['frontendSourceCommit']),ensure_ascii=False))
