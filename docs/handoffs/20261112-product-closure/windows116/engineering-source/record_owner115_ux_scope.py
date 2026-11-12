from pathlib import Path
from datetime import datetime
import copy
import json
import re

root = Path('C:/Users/Billy/Desktop/Denzic/Companion')
run = Path('E:/CodexData/Companion/.build-cache/product-closure20261112/owner-guided-windows115-step-issues-fw66828-20261112')
progress = json.loads((run/'progress.json').read_bytes())
at = datetime.now().astimezone().isoformat(timespec='seconds')
scope_quote = '这些你可以用那个电脑声音简单做一下吧，我只要体验人能体验的就好，其他那些长。什么长的会叫那些我就不体验了，主要是我体验的是人体验的东西，这些啊，就是简单体验一下就可以，那些复杂的功能就你来做或者是怎么样。反正我现在体验起来就是感觉 UI 啊那些都不是特别好。然后呢，使用逻辑比较混乱，功能那些我就没有再体验了，功能那些你确认没问题就行。'
path = root/'docs/product_backlog.json'
raw = path.read_bytes()
text = raw.decode('utf8')
data = json.loads(text)
module = data['owner_module_execution']
active = module['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110']
before = copy.deepcopy(active)
current_before = copy.deepcopy(module['currentBatch'])
next_before = copy.deepcopy(module['nextBatch'])
closure = active['ownerProductClosure20261112']
ui = closure['ownerUiUsabilityRework20261112']
attempt = copy.deepcopy(progress)
attempt.update(privateEvidenceDirectory=str(run),liveProcessObservedAt=at,toolSessionId=None)
ui['currentOwnerAttempt'] = attempt
existing = {item['id']: item for item in ui['issueReports']}
decisions = {
    'ISSUE-001': ('UI115-001', 'OWNER_CONFIRMED_APPEARANCE115_INSUFFICIENT_RESTRUCTURE_PENDING', 'Rebuild a coherent library, connection identity and recording detail hierarchy together; spacing-only115 did not resolve Owner perception.'),
    'ISSUE-002': ('UI115-002', 'RECORDING_DISCOVERY_AND_NAMING_REPAIR_PENDING', 'Make each recording identifiable by saved title or honest time/source fallback, short saved-content preview and direct opening. Preserve authored titles and original data.'),
    'ISSUE-003': ('UI115-003', 'PENDING_TEXT_STATE_AND_PRIMARY_ACTION_DIAGNOSIS_PENDING', 'Inspect actual processing state and reveal the next valid action on the selected recording. Distinguish queued, disabled, not configured, running and failed; do not invent a completed transcript or hide failures.')
}
for issue in progress.get('individualIssues', []):
    stable, state, decision = decisions[issue['id']]
    item = copy.deepcopy(issue)
    item.update(id=stable,originalRoundIssueId=issue['id'],state=state,decision=decision,blocking=False)
    if stable in existing:
        assert existing[stable]['ownerQuote'] == issue['ownerQuote']
    else:
        ui['issueReports'].append(item)
for issue in ui['issueReports']:
    if issue['id']=='UI114-APPEARANCE':
        issue.update(state='OWNER115_CONFIRMED_INSUFFICIENT_REPAIR_CONTINUES',followupIds=['UI115-001','UI115-002','UI115-003'])
    elif issue['id']=='GUIDE114-ISSUE-LOCALIZATION':
        issue.update(state='ACTUAL_OWNER115_THREE_SEPARATE_REPORTS_CAPTURED',blocking=False,actualOwnerReports=len(progress.get('individualIssues', [])),actualOwnerEvidence=str(run/'issues/index.json'))
ui['individualIssueGuidance'].update(actualOwnerModalRuntimeNewlyProved=True,actualOwnerIssueCount=len(progress.get('individualIssues', [])),actualOwnerEvidence=str(run/'issues/index.json'),ownerExperienceAccepted=False)
scope = dict(at=at,ownerQuote=scope_quote,state='OWNER_SHORT_UX_ONLY_ENGINEERING_OWNS_FUNCTIONAL_VERIFICATION',ownerExpectedExperience='Short natural use focused on visual quality, finding a recording and clear next action; no long recording, failure checklist or full-function qualification.',engineeringWork='Use clearly labelled computer-generated public audio for actual ordinary import, local ASR, result organisation, save, export and reopening. Complex and physical checks stay engineering responsibility; synthetic media does not qualify microphone, BLE, actual long recording or general model accuracy.',noAdditionalTechnicalOwnerRound=True,existingRoundNavigationIsNotFunctionalAcceptance=True)
ui['ownerAcceptanceScope20261112'] = scope
ui.update(updatedAt=at,state='OWNER115_UX_REJECTED_COHERENT_RESTRUCTURE_IN_PROGRESS',ownerAppearanceAccepted=False,ownerExperienceAccepted=False,noMoreOwnerPromptUntilSubstantiveRepair=True)
next_action = '按Owner115三条独立原话集中重整首页、可辨认录音列表和详情下一步；工程用明确电脑合成公开声音自验导入到文字/整理/保存/导出/重开，复杂/长录由工程负责，不再要求Owner功能逐项验收。修完集中交付后仅短自然体验。现有115轮先保留实际应用退出与准确占用释放，导航不算功能通过。'
active.update(updatedAt=at,state=ui['state'],next=next_action,knownJobState=f'Original Owner115 controller {progress["controllerPid"]}; app {progress.get("appPid")}; preserve actual closure and exact heldSince {progress.get("boardLeaseHeldSince")}.')
closure.update(updatedAt=at,ownerTotalStatus=active['state'],frontendAcceptedPurposeClosed=False,coherentSoftwarePurposeComplete=False)
module['currentBatch'].update(at=at,state=active['state'],remaining='Owner115认为UI仍丑、命名/录音管理/待转写逻辑不清楚；原逐条问题记录已实际使用，整体可用/美观未签收。功能工程负责，复杂/实物范围不虚关。',next=next_action)
module['nextBatch'].update(at=at,status=active['state'],next=next_action)

def splice(key, old, new):
    global text
    hits=[]
    for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
        value, count=json.JSONDecoder().raw_decode(text[match.end():])
        if value==old:hits.append((match,count))
    assert len(hits)==1, key
    match,count=hits[0]
    replacement=json.dumps(new,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))
    text=text[:match.end()]+replacement+text[match.end()+count:]

splice('activeNonmodelCompletion20261110',before,active)
splice('currentBatch',current_before,module['currentBatch'])
splice('nextBatch',next_before,module['nextBatch'])
json.loads(text)
assert path.read_bytes()==raw
path.write_bytes(text.encode('utf8'))
receipt=dict(at=at,version='0.1.115',sourceCommit=progress['sourceCommit'],issues=progress['individualIssues'],scope=scope,ownerAppearanceAccepted=False,functionalAcceptanceFromNavigation=False,physicalTotalAcceptancePassed=False)
dest=root/'docs/handoffs/20261112-product-closure/windows115/owner-ux-feedback-and-scope.json'
dest.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
log=root/'docs/development_log.md'
lograw=log.read_bytes()
entry=f'''<!-- owner115-short-ux-engineering-functional-responsibility -->
{at} Owner115已在原共享窗口实际分别提交ISSUE-001（连接/外观仍丑）、ISSUE-002（全部记录复杂、命名找不到）、ISSUE-003（一直待转写、录音管理不好）。原始逐条步骤/版本/原话保留；导航到第7步不是功能完成。原记录方式本身已真实收取3条，外观115未改善到Owner认可，旧114外观项继续，不能自验后改成满意。

Owner新指示完整保存在windows115/owner-ux-feedback-and-scope.json：只做简短人感体验；电脑声音及功能、长录/复杂检查由工程承担，Owner未继续体验功能。沿同一待办集中重整首页、可辨认命名与录音列表、详情有效下一步，不再间距/文字逐条打包。工程将用明确合成公开音频检查实际软件链，原音/用户标题不改；合成文件不等于实卡采音/BLE/长录或模型普适准确已过。现有controller{progress['controllerPid']}及app{progress.get('appPid')}现场保留，待实际退出后由其精确item+heldSince释放；不注入Owner点击、不停已有MIC。

'''
if b'<!-- owner115-short-ux-engineering-functional-responsibility -->' not in lograw:
    log.write_bytes(entry.replace('\n','\r\n').encode('utf8')+lograw)
status_path=Path(__file__).resolve().parents[1]/'outputs/Companion-115-current-status.json'
status=json.loads(status_path.read_bytes())
status.update(currentOwnerAttempt=attempt,ownerPromptStarted=True,ownerAcceptanceScope=scope,issueReports=ui['issueReports'],individualIssueGuidance=ui['individualIssueGuidance'],ownerAppearanceAccepted=False,ownerExperienceAccepted=False)
status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(recordedIssueIds=[x['id'] for x in ui['issueReports']],scope=scope['state'],actualOwnerIssueCount=len(progress.get('individualIssues', [])),controllerPreserved=progress['controllerPid']),ensure_ascii=False))
