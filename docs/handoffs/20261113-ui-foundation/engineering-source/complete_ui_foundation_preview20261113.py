from pathlib import Path
from datetime import datetime,timezone,timedelta
import copy,hashlib,json,re,shutil,subprocess,os

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
S=R/'companion-device-closure055'
E=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/ui-foundation20261113')
F=Path('C:/Users/Billy/.codex/visualizations/2026/11/12/01a1cd4e-ed69-7431-bbea-486848d70b7d/companion-design-foundation.html')
H=R/'docs/handoffs/20261113-ui-foundation'
at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
qa=json.loads((E/'preview-qa.json').read_text(encoding='utf-8'))
assert qa['passed'] and len(qa['checks'])==18 and not qa['pageErrors']
fragment=F.read_bytes();assert len(fragment)<1_000_000
assert not any(token in fragment.lower() for token in [b'<!doctype',b'<html',b'<body',b'fetch(',b'xmlhttprequest',b'websocket'])
receipt_path=H/'reference-selection.json'
receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
receipt['completedAt']=at
receipt['research'].update(state='PRIMARY_REFERENCES_AND_COHERENT_DESIGN_PREVIEW_READY_NATIVE_REWORK_OPEN',recommendedDirection='随身笔记',alternativeDirection='录音工作台',designDecision='Use one consistent typography/spacing/navigation vocabulary and recordings-to-reading hierarchy. Existing shadcn-derived CSS patches did not establish a coherent product foundation; do not combine dashboard/chat template skins.',upstreamCodeImported=False)
preview=dict(state='DESIGN_PREVIEW_READY_NOT_INSTALLED_PRODUCT',path=str(F),sha256=hashlib.sha256(fragment).hexdigest(),bytes=len(fragment),protectedSource=str(H/'design-preview.html'),variants=['随身笔记','录音工作台'],recommended='随身笔记',qa=str(H/'preview-qa.json'),engineeringViewedScreenshots=['notebook-1056-light.png','notebook-1056-dark.png','workbench-1056-light.png','notebook-422-light.png','workbench-422-light.png'],checkedWidths=[1024,736,390,320],themes=['light','dark'],checks='Actual standalone host carousel/icons, primary local interactions, keyboard tabs and label linkage, export text visible, narrow library/detail/back and device/settings availability, no horizontal overflow, embedded public audio duration23.2245 and muted headless playback.',scope='Interactive layout and appearance concept; no native build, install, board, microphone, user file access or model runs. Public SAPI audio reused with 32 derived waveform bins. Example note text marked fictional. Existing installed116/144 retained. Owner acceptance remains false.',failuresRetained=['preview-qa-initial-test-assertion-mismatch.json','preview-qa-second-test-assertion-mismatch.json','notebook-1056-light-before-visual-review.png','render-existing-destination-refusal.txt'],visualReviewCorrection='Export button foreground inherited dark-on-dark despite local interaction QA passing; corrected scoped specificity and checked fresh render. Narrow workbench navigation and tab semantics corrected. Wrapper destination refusal preserved; regenerated with force before final QA.')
receipt['preview']=preview
next_action='已给出公开模板来源及两套完整可交互设计草案，推荐“随身笔记”。当前116/144仍为已装基线，UI116-DESIGN-FOUNDATION未关闭；后续按一致视觉系统整体重组应用壳、录音库及内容阅读，把真实保存/回听/导出和设备状态接回同一路径，工程集中自验后整批交付。Owner只看观感与自然使用，不派逐功能或复杂长录清单。'
receipt['next']=next_action
P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf-8');d=json.loads(text);m=d['owner_module_execution']
a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];before=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);c=a['ownerProductClosure20261112'];u=c['ownerUiUsabilityRework20261112']
assert u['designFoundationRework20261113']['ownerFeedbackId']=='UI116-DESIGN-FOUNDATION'
state='COHERENT_DESIGN_PREVIEW_READY_NATIVE_FOUNDATION_REWORK_OPEN'
u.update(updatedAt=at,state=state,ownerAppearanceAccepted=False,ownerExperienceAccepted=False,noMoreOwnerPromptUntilSubstantiveRepair=True)
u['designFoundationRework20261113']={**receipt['research'],'preview':preview,'receipt':str(receipt_path),'next':next_action}
issue=next(row for row in u['issueReports'] if row['id']=='UI116-DESIGN-FOUNDATION')
issue.update(state='DESIGN_REFERENCES_AND_INTERACTIVE_CONCEPT_READY_NATIVE_REWORK_OPEN',previewReceipt=str(receipt_path),ownerAccepted=False)
a.update(updatedAt=at,state=state,next=next_action,knownJobState='Design references and responsive interactive concept checked. No new native/app/device/model job; installed116/144 retained. Product foundation implementation and Owner aesthetics remain open.')
c.update(updatedAt=at,state=state,currentPoint=next_action,ownerTotalStatus=state)
m['currentBatch'].update(at=at,state=state,remaining='整体设计草案已就绪；真实应用设计底层重构和Owner观感尚未关闭，未构建或安装新版本。',next=next_action)
m['nextBatch'].update(at=at,status=state,next=next_action)
def splice(key,old,new):
 global text
 hits=[]
 for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
  value,n=json.JSONDecoder().raw_decode(text[match.end():])
  if value==old:hits.append((match,n))
 assert len(hits)==1,key
 match,n=hits[0];text=text[:match.end()]+json.dumps(new,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:]
splice('activeNonmodelCompletion20261110',before,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf-8'))
receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
agent=R/'AGENTS.md';raw=agent.read_bytes();lines=raw.decode('utf-8-sig').splitlines();idx=next(i for i,line in enumerate(lines) if line.startswith('- 当前实际已装Windows'))
lines[idx]='- 当前实际已装Windows0.1.116 / Android0.1.144，原同源交付、资料保护、真实保存/导出/重开与23秒公开电脑声证据保留。Owner于2026-11-13明确认为UI仍像AI拼接、要求底层重构与公开模板；沿原UI116-DESIGN-FOUNDATION承接，外观/好用不通过。现已核验Untitled UI公开MIT组件（PRO另条款）、shadcn Mail v3和assistant-ui，并给出“随身笔记/录音工作台”两套完整响应式交互草案，推荐随身笔记；收据docs/handoffs/20261113-ui-foundation/reference-selection.json。仅设计预览就绪，尚未接入/构建/安装真实应用，不把草案当软件完成；后续按一个一致设计体系整体重组、工程集中自验交付。Owner只短看观感和自然使用，功能/长录/复杂检查由工程承担，不再八步清单。实卡长录、独立模型质量、完整IMU、最终硬件及正式售卖继续沿原待办，当前UI不接板、不停原录音。'
assert agent.read_bytes()==raw;agent.write_text('\n'.join(lines)+'\n',encoding='utf-8')
log=R/'docs/development_log.md';raw=log.read_bytes();marker='<!-- ui116-design-foundation-references-and-interactive-concept20261113 -->';assert marker.encode() not in raw
entry=f'''{marker}
{at} Owner原话：“{receipt['feedback']['ownerQuote']}”版本上下文为已装116/144，未观察具体应用步骤。沿原待办UI116-DESIGN-FOUNDATION承接，UI115-001/UI114-APPEARANCE继续未通过；前几轮旧结构样式收紧未解决整体视觉基础，不能以工程自验覆盖Owner否定。

公开一手来源已核：Untitled UI React公开仓库组件MIT，PRO完整页面另许可；shadcn/ui Mail v3为MIT列表/阅读布局参考（当前无v3的mail地址404，不使用）；assistant-ui为MIT对话组件，只作需要时AI区域参考。当前companionDesign.css已含Shadcn Dashboard改编样式，单换库名不能解决问题，本轮未导入上游代码。给出“随身笔记”和“录音工作台”两种完整可交互设计草案，推荐前者；录音列表、搜索、阅读、纪要/文字、收藏、导出预览、设备/设置入口和窄屏返回连在同一套布局，公开23.2245秒电脑声与32格真实波形仅用于预览，不造实卡/模型新证据。

实际Edge无界面渲染检查两布局/浅深色/1024、736、390、320宽度与主要本地交互，18项结果无页面或控制台错误、无横向溢出；实际宿主轮播和图标载入、键盘切换与关联、手机宽度入口及公开音频静音播放前进已确认。工程实际看图发现导出按钮因CSS优先级黑字黑底，已修并用重新生成的预览复核；前两次检查脚本字面断言不匹配、渲染已有目标拒绝和旧图均保留，不冒充产品故障或新增功能进展。完整草案{len(fragment)}B/SHA256 {preview['sha256']}，受保护片段、来源/检查收据在docs/handoffs/20261113-ui-foundation/；原线程内可直接看整体。

本轮只完成来源选择和设计概念，没有原生构建、安装、接板、MIC、读私人文件或新模型请求，没有新Owner技术带验/顾客派发。已装116/144和原功能/失败证据保留；设计底层真实接入、Owner外观好用、实卡/长录/独立模型/IMU/售卖保持开放。下一动作：{next_action}

'''
assert log.read_bytes()==raw;log.write_bytes(entry.replace('\n','\r\n').encode('utf-8')+raw)
shutil.copyfile(F,H/'design-preview.html');shutil.copyfile(E/'preview-qa.json',H/'preview-qa.json');shutil.copyfile(E/'preparation.json',H/'preparation.json')
for name in preview['failuresRetained']:
 shutil.copyfile(E/name,H/name)
for name in ['notebook-1056-light.png','notebook-1056-dark.png','notebook-422-library-light.png','workbench-1056-light.png','workbench-422-library-light.png']:
 shutil.copyfile(E/name,H/name)
for name in ['record_ui_foundation_feedback20261113.py','prepare_ui_foundation_preview20261113.py','verify_ui_foundation_preview20261113.cjs','complete_ui_foundation_preview20261113.py']:
 dest=H/'engineering-source'/name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(Path('work')/name,dest)
paths=['AGENTS.md','docs/product_backlog.json','docs/development_log.md','docs/handoffs/20261113-ui-foundation']
for rel in paths[:3]:shutil.copyfile(R/rel,S/rel)
for file in H.rglob('*'):
 if file.is_file():
  dest=S/file.relative_to(R);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,dest)
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m']
checks=git+['-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
for args in [['add','--',*paths],['diff','--cached','--check','--',*paths,':(exclude)**/*.log',':(exclude)**/*.patch'],['commit','--only','-m','Record Owner UI foundation rejection and coherent design preview','--',*paths]]:
 subprocess.run(checks+args,cwd=S,check=True)
subprocess.run(git+['push','origin','HEAD'],cwd=S,env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe'},check=True)
latest=json.loads(P.read_text(encoding='utf-8'))['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110']
print(json.dumps(dict(state=latest['state'],next=latest['next'],previewBytes=len(fragment),qaPassed=qa['passed'],installedAppChanged=False),ensure_ascii=False))
