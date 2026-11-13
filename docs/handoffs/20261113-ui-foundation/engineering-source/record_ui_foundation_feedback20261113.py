from pathlib import Path
from datetime import datetime,timezone,timedelta
import copy,json,re

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
quote='感觉你这个 ui 还是从底上要重构一下，现在感觉就像是一个 ai 在做的 ui。感觉可能做好看点，做精致点，有没有什么公开的 ai 模板，ui模板之类的。'
P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];before=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);c=a['ownerProductClosure20261112'];u=c['ownerUiUsabilityRework20261112']
assert not any(row.get('id')=='UI116-DESIGN-FOUNDATION' for row in u['issueReports'])
receipt=R/'docs/handoffs/20261113-ui-foundation/reference-selection.json'
feedback=dict(id='UI116-DESIGN-FOUNDATION',receivedAt=at,channel='Owner chat',versionContext=dict(windows=a['currentInstalledWindows'],android=a['currentInstalledAndroid']),specificInAppRunOrStepObserved=False,ownerQuote=quote,state='OWNER_REJECTS_CURRENT_OVERALL_DESIGN_ARCHITECTURE_REEVALUATION',relatedPriorIssues=['UI115-001','UI114-APPEARANCE'],ownerAccepted=False,decision='Stop consecutive cosmetic patches on the existing dashboard. Compare complete mature application layouts and an explicit design system; create one coherent recording/reading prototype before native integration. Owner still only judges visual quality and natural use; engineering owns functionality.',referenceSelectionReceipt=str(receipt))
u['issueReports'].append(feedback)
for row in u['issueReports']:
    if row.get('id') in ['UI115-001','UI114-APPEARANCE']:row.update(state='OWNER116144_REPORTS_STILL_UNREFINED_FOUNDATION_REWORK_CONTINUES',followupId='UI116-DESIGN-FOUNDATION',ownerAccepted=False)
u.update(updatedAt=at,state='OWNER116144_REJECTED_VISUAL_FOUNDATION_RESEARCH_AND_COHERENT_PROTOTYPE',ownerAppearanceAccepted=False,ownerExperienceAccepted=False,noMoreOwnerPromptUntilSubstantiveRepair=True)
u['designFoundationRework20261113']=dict(state='PRIMARY_SOURCE_TEMPLATES_VERIFIED_COHERENT_PREVIEW_IN_PROGRESS',ownerFeedbackId=feedback['id'],receipt=str(receipt),sources=[dict(name='shadcn/ui Mail v3',preview='https://v3.shadcn.com/examples/mail',license='MIT',licenseSource='https://github.com/shadcn-ui/ui/blob/main/LICENSE.md',role='Complete list/reading layout reference; legacy v3 preview explicitly identified.'),dict(name='Untitled UI React',preview='https://www.untitledui.com/react',source='https://github.com/untitleduico/react',license='MIT for public repository components; PRO pages have separate terms',role='Typography, spacing, navigation and component consistency reference.'),dict(name='assistant-ui',preview='https://www.assistant-ui.com/examples',source='https://github.com/assistant-ui/assistant-ui',license='MIT',role='Optional contextual AI panel reference, not the recording app shell.')],currentProductTemplateUse='Current companionDesign.css already contains adapted Shadcn Dashboard styles. Changing the library name alone would not remedy the composition problem.',thirdPartyCodeImportedThisRound=False,nativeBuildStarted=False,installedAppChanged=False)
next_action='沿UI116-DESIGN-FOUNDATION做真正设计底层重组：基于已核验公开页面/设计系统，先给录音列表—内容阅读的完整桌面/窄屏交互预览，统一导航、字体、留白、按钮与状态，不再旧dashboard逐块补CSS或即时重包。明确预览与已装116/144不同；选定整体方向后把既有真实数据/保存/回听/导出接入同一新壳，工程集中自验交付，Owner只短看观感和自然使用。'
a.update(updatedAt=at,state=u['state'],next=next_action,allNonmodelComplete=False,frontendAcceptedPurposeClosed=False,knownJobState='No new native/app/device/model job. Researching primary public UI sources and preparing one interactive visual direction; installed116/144 and functional evidence retained, visual appearance explicitly not accepted.')
c.update(updatedAt=at,state=u['state'],currentPoint=next_action,coherentSoftwarePurposeComplete=False,frontendAcceptedPurposeClosed=False)
m['currentBatch'].update(at=at,state=u['state'],remaining='Owner认为116/144仍像AI拼出的UI，当前视觉不通过；整体设计参考和交互预览进行中，未重新构建或安装。',next=next_action);m['nextBatch'].update(at=at,status=u['state'],next=next_action)
def splice(key,old,new):
    global text
    hits=[]
    for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
        value,n=json.JSONDecoder().raw_decode(text[match.end():])
        if value==old:hits.append((match,n))
    assert len(hits)==1,key
    match,n=hits[0];text=text[:match.end()]+json.dumps(new,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:]
splice('activeNonmodelCompletion20261110',before,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf8'))
receipt.parent.mkdir(exist_ok=False);receipt.write_text(json.dumps(dict(at=at,feedback=feedback,research=u['designFoundationRework20261113'],next=next_action),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(state=u['state'],feedbackId=feedback['id'],installedAppChanged=False),ensure_ascii=False))
