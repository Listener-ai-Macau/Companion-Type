from pathlib import Path
from datetime import datetime
import copy,hashlib,json,os,re,shutil,subprocess

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');W=Path(__file__).parent;B=R/'docs/handoffs/20261112-product-closure/windows116';B.mkdir(exist_ok=False);at=datetime.now().astimezone().isoformat(timespec='seconds')
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
head=lambda root:subprocess.check_output(git+['rev-parse','HEAD'],cwd=root,text=True).strip()
assert head(E)=='ba26a969bb7f72966fe0ad18c7bcb67675650509' and not subprocess.check_output(git+['status','--porcelain'],cwd=E,text=True).strip()
cache=Path('E:/CodexData/Companion/.build-cache/product-closure20261112')
assert json.loads((cache/'ui-usability-source-r10/result.json').read_bytes())['state']=='COMPLETE_WORKSPACE_SOURCE_JOURNEY_PASSED'
run=cache/'owner-guided-windows115-step-issues-fw66828-20261112';terminal=json.loads((run/'progress.json').read_bytes());assert terminal.get('finishedAt') and not terminal['boardLease'] and terminal['ownerResponse']['selected']=='结束本轮'
voice=json.loads((cache/'public-computer-voice115-r3/result.json').read_bytes());assert voice['actualLocalAsrCompleted'] and voice['minutesSource']=='llm_deepseek' and voice['savedStateUnchangedAcrossProcesses']
(B.parent/'windows115/owner-guided115-terminal20261112.json').write_text(json.dumps(terminal,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
(B/'computer-voice-backend-evidence.json').write_text(json.dumps(voice,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
product=['apps/windows/src/App.tsx','packages/ui/src/CompanionDashboard.tsx','packages/ui/src/deviceConnectionStatus.ts','packages/ui/src/recordingPresentation.ts','packages/ui/src/recordingWorkspace.css']
versions=['package.json','package-lock.json','apps/windows/src-tauri/tauri.conf.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json']
original=(W/'freeze_connection114.py').read_text(encoding='utf8');code=original[original.index('def bump(root):'):original.index('bump(S)')];exec(re.sub(r'113|114',lambda m:'115' if m[0]=='113' else '116',code));bump(S)
P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];before=copy.deepcopy(a);cur=copy.deepcopy(m['currentBatch']);nxt=copy.deepcopy(m['nextBatch']);c=a['ownerProductClosure20261112'];u=c['ownerUiUsabilityRework20261112']
u['currentOwnerAttempt'].update(terminal,terminalObservedAt=at);u['previousOwner115Attempt']=copy.deepcopy(u['currentOwnerAttempt']);u['previousSoftwareSelfReview115']=copy.deepcopy(u['preOwnerEngineeringAcceptance20261112']);u['preOwnerEngineeringAcceptance20261112']=dict(windowsVersion='0.1.116',softwareSelfAcceptancePassed=False,ownerPromptStarted=False,state='RECORDING_WORKSPACE116_SOURCE_CHECKED_NORMAL_PACKAGE_PENDING')
u.update(updatedAt=at,state='COHERENT_RECORDING_WORKSPACE116_SOURCE_CHECKED_NORMAL_BUILD_PENDING',candidateVersion='0.1.116',installedAndEngineeringReviewed=False,noMoreOwnerPromptUntilSubstantiveRepair=True,engineeringComputerVoiceEvidence=str(B/'computer-voice-backend-evidence.json'))
for issue in u['issueReports']:
    if issue['id'].startswith('UI115-'):issue.update(state='COHERENT116_SOURCE_IMPLEMENTED_DELIVERY_PENDING',sourceWholePurposeEvidence=str(cache/'ui-usability-source-r10/result.json'))
next_action='116集中交付录音库/名称与日期/真实状态下一步/详情阅读层级；从已交付115冻结5个明确前端文件，其他会话在途指针源码不混入。工程已用23.22秒中文电脑声实际跑本机ASR、已配DeepSeek纪要、保存导出和跨进程回读；是公开合成文件/生产后端，不是实卡采音或长录。完成同包原生自验与原资料保护安装，同时收敛手机录音库对应外观；Owner后续只做短自然体验。'
a.update(updatedAt=at,state=u['state'],plannedWindowsVersion='0.1.116',plannedVersionsBuilt=False,next=next_action,knownJobState='Owner115 actually closed22:16:27, own lease released; original window has no pending functional checklist. Source116 complete workflow and presentation/data-preservation checks passed; normal build pending.')
c.update(updatedAt=at,ownerTotalStatus=a['state'],ownerTotalReceipt=str(B.parent/'windows115/owner-guided115-terminal20261112.json'))
m['currentBatch'].update(at=at,state=a['state'],remaining='116正常包和手机对应外观正在集中处理；软件实际功能由工程负责，Owner只短体验美观/理解/回找。',next=next_action);m['nextBatch'].update(at=at,status=a['state'],next=next_action)
def splice(key,old,new):
    global text
    hits=[]
    for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
        value,n=json.JSONDecoder().raw_decode(text[match.end():])
        if value==old:hits.append((match,n))
    assert len(hits)==1;match,n=hits[0];text=text[:match.end()]+json.dumps(new,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+n:]
splice('activeNonmodelCompletion20261110',before,a);splice('currentBatch',cur,m['currentBatch']);splice('nextBatch',nxt,m['nextBatch']);json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf8'))
agent=R/'AGENTS.md';lines=agent.read_text(encoding='utf-8-sig').splitlines();idx=next(i for i,x in enumerate(lines)if x.startswith('- 当前实际已装Windows'));lines[idx]='- 当前实际已装Windows0.1.115 / Android0.1.142。Owner115在原窗口实际逐条记录3个问题：仍丑、名称难找、待转写与管理混乱；结束本轮后22:16应用实际退出/准确占用释放。Owner明确只做简短人感体验，电脑声音/功能/复杂长录由工程负责。116已集中重整录音库、可辨名称/日期分组/真实状态和详情下一步，源码连续流程已过、正常包待构建；115实际生产后端用公开电脑中文声跑通本机ASR→已配DeepSeek→保存导出→跨进程回读，不是实卡/长录/模型普适准确通过。手机对应外观集中续作；实际外观好用与整机/售卖未签收。';agent.write_text('\n'.join(lines)+'\n',encoding='utf8')
log=R/'docs/development_log.md';old=log.read_bytes();entry=f'''<!-- recording-workspace116-freeze -->
{at} 承接Owner115原3条独立反馈和只短体验指示：同一录音库按日期分组，默认编号仅显示为已保存文字开头/真实时间，人工标题和原数据不改；移除默认重复“继续整理”大块，连接状态收紧为顶栏，录音行显示可辨认名称/日期/来源/预览/打开入口。可回听、自动关闭、需模型、等待/正在转写、失败/未收齐明确区分；无文字时准备服务和有效下一步不藏高级工具，原编辑/保存/范围/草稿/静默同步保留。源码完整流程r10与标题/状态不改数据检查通过；只合明确5份前端到已交付115。

工程使用Windows已装115真实本机ASR和已配DeepSeek：23.2245秒SAPI中文公开合成文件，零转写注入/旁车假识别，本机4.844秒识别74字，模型3.046秒返回final，李明/小林/三项时间和预算未决定保留，实际保存与跨进程回读一致。旧原始Markdown保留技术头是原格式，不当普通所选交接。r1受共用2GiB资源上限阻止准备、r2工程种子漏recovery/retention必填而被安全当不可读，无产品回退；保留失败后用同一WAV补完整合法种子r3通过。没有测试GUI导入、实卡采音、长录或通用模型准确，不虚关。Owner115正常退出22:16:27.300，原controller精确释放22:16:27.558，未发MIC/强杀/放弃草稿。

''';log.write_bytes(entry.replace('\n','\r\n').encode('utf8')+old)
def put(src,dst):dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
docs=['AGENTS.md','docs/product_backlog.json','docs/development_log.md','docs/handoffs/20261112-product-closure/windows115/owner-ux-feedback-and-scope.json','docs/handoffs/20261112-product-closure/windows115/owner-guided115-terminal20261112.json','docs/handoffs/20261112-product-closure/windows116/computer-voice-backend-evidence.json']
for rel in docs:put(R/rel,S/rel)
for name in ['freeze_recording_workspace116.py','check_public_computer_voice115.py','public_computer_voice.ps1','record_owner115_ux_scope.py','close_finished_owner115_normally.py']:put(W/name,S/'docs/handoffs/20261112-product-closure/windows116/engineering-source'/name)
paths=product+versions+docs+['tools/qa/core_acceptance20261109/meeting_workspace_harness.tsx','tools/test_recording_presentation.cjs','docs/handoffs/20261112-product-closure/windows116/engineering-source']
for args in [['add','--',*paths],['diff','--cached','--check','--',*paths,':(exclude)**/*.log',':(exclude)**/*.patch'],['commit','--only','-m','Restructure recording library identity and next actions after Owner115 feedback','--',*paths]]:subprocess.run(git+args,cwd=S,check=True)
authoring=head(S);subprocess.run(git+['switch','-c','work/recording-workspace116-frozen-20261112'],cwd=E,check=True)
for rel in product:put(S/rel,E/rel)
bump(E)
for args in [['add','--',*product,*versions],['diff','--cached','--check','--',*product,*versions],['commit','-m','Freeze coherent recording workspace116 on delivered115']]:subprocess.run(git+args,cwd=E,check=True)
frozen=head(E)
record=dict(at=at,state='RECORDING_WORKSPACE116_FROZEN_NORMAL_BUILD_PENDING',version='0.1.116',sourceCommit=frozen,sourceRoot=str(E),frozenSourceRoot=str(E),branch='work/recording-workspace116-frozen-20261112',priorDeliveredSource='ba26a969bb7f72966fe0ad18c7bcb67675650509',authoringSourceCommit=authoring,productFilesChanged=product,platformCommit=subprocess.check_output(git+['rev-parse','HEAD:third_party/denzic-platform'],cwd=E,text=True).strip(),currentAndroid='0.1.142',plannedAndroidVisualBatch='0.1.143',ownerExperienceAccepted=False,saleQualified=False)
(B/'frozen-source.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for repo in [S,E]:subprocess.run(git+['push','-u','origin','HEAD'],cwd=repo,env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe'},check=True)
print(json.dumps(record,ensure_ascii=False))
