"""Record the completed saved-action user outcome in the original backlog and timeline."""
from pathlib import Path
from datetime import datetime
import copy,hashlib,json,os,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;S=R/'companion-device-closure055';A=R/'companion-core-android20261109'
P=Path('E:/CodexData/Companion/.build-cache/actions-followup20261110')
load=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
at=datetime.now().astimezone().isoformat(timespec='seconds')
win=load(C/'windows082/runtime-result.json');wi=load(C/'windows082/installation.json');phone=load(C/'android117/ui-result.json');clip=load(C/'android117/native-clipboard-result.json');cleanup=load(C/'android117/cleanup.json')
assert win['state']=='WINDOWS082_NATIVE_ACTION_FILTER_FOLLOWUP_COPY_AND_REOPEN_PASSED' and wi['state']=='WINDOWS082_INSTALLED_EXISTING_DATA_IDENTICAL'
assert phone['state']=='ANDROID117_REAL_PHONE_ACTION_FILTER_FOLLOWUP_NATIVE_COPY_AND_REOPEN_PASSED' and clip['actualAndroidClipboardPastedIntoUnsentQuestion']
assert cleanup['originalLibraryRestored'] and cleanup['onlyPublicTestMinutesAndNavigationIndexChanged'] and cleanup['mainUnchanged']
for folder in ['windows082','android117']:assert load(C/folder/'remote-candidate-backup.json')['readbackByteIdentical']
record=load(C/'batch.json');record.update(completedAt=at,state='SAVED_ACTION_FILTER_FOLLOWUP_NATIVE_COPY_AND_DURABLE_COMPLETION_DELIVERED_BOTH_PLATFORMS',
 windows={'version':'0.1.82','source':'e72d16ed941cb7070cc7bd6e8d21f3b830192254','buildRun':42723975145,'runtimeSource':win['testSourceCommit'],'runtimeRun':42726992295,'installed':True,'originalFilesByteIdentical':245,'nativeClipboardReadbackMatched':True,'clipboardComparison':'Windows CF_UNICODETEXT CRLF to LF only; words and selection exact','privateDraftReadbackVerified':True},
 android={'version':'0.1.117','source':'9b6b8858d36feb170a9347a56f57b0e0ee5980d2','buildRun':42725482756,'frozenBackendSource':'608790132701ede93fa24a00b687874cb7e70c6b','installed':True,'installFilesByteIdentical':1907,'actualPublicSavedActions':21,'pendingFilterMatches':20,'normalNativeCopyAndActualKeyboardPastePassed':True,'clipboardCharacters':clip['characters'],'clipboardSha256':clip['sha256'],'originalLibraryRestored':True,'primaryDisplayUnchanged':True,'ownedTestDisplayClosed':True,'privateDraftReadbackVerified':True},
 delivered=['Shared owner, completion, missing-owner/time/review and literal keyword filters over saved action identities.','One full-list filter and scope across Android folded remainder; default reading still folds after four.','Read-only local followup draft from the current saved filtered items. Existing original-item editing is the edit authority.','Explicit pending/unconfirmed and marked-complete groups, unknown owners/dates remain unknown.','Actual clipboard copy on both native runtimes, durable completion/reopen and original-source entry preserved.'],
 failuresRetained=[{'stage':'Android116 native public meeting','finding':'The original MinutesDocument fold rendered two MobileActionCards, creating separate 4/17 item scopes.','fix':'Android117 renders the full action section once; cards own folding and reveal all filter matches. Integrated full MinutesDocument test now protects the real composition.','evidence':'android116/ui-failure-r2.json'},
 {'stage':'Windows native runtime r1','finding':'Literal clipboard comparison failed on Windows CRLF representation.','fix':'Same exact082 MSI, compare CRLF to LF only and retain both raw hashes/character counts. Actual words/selection unchanged.','failedRun':42726625518,'passedRun':42726992295},
 {'stage':'Android owned display harness','finding':'Native confirm requires scoped native control, asynchronous completion must await saved state, and the background accessibility tree does not expose the WebView receiver label. USB disconnects destroyed displays7/8.','fix':'Owned-display native confirm, await saved state/reopen, and actual Control+V into an ordinary unsent question field on display9. No receiver text injected by the harness.','evidence':['android117/ui-failure-r1.json','android117/ui-failure-r2.json','android117/native-clipboard-result.json']}],
 scopeLimits={'modelQualityChanged':False,'newAsrOrCloudInference':0,'timeRangeFilterDelivered':False,'independentlyEditableAiMaterialDeliveredByThisChange':False,'globalContentExportChangedToFilteredActions':False,'remindersDelivered':False,'newHumanCustomerQualified':False,'boardAccessed':False,'ownerAcceptanceChanged':False,'wholeCoreCandidateQualified':False,'saleQualified':False},
 next='沿原核心候选继续固定Qwen完整实会对照与复杂多人/事实门；本机实际资源具备后才从原断点恢复。非模型方面复用082/117已交付流程，后续只处理原清单未验的实际阻断；可编辑AI材料、提醒、实卡和真人客户按各原验收项保留，不将本批筛选/本地跟进文字等同全部竞品能力。')
(C/'batch.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
# Preserve public CI evidence and the first genuine failing stage, without owner
# manifests, app data, API keys, downloaded binaries or cloud credentials.
for run_name,folder in [('windows-runtime-r1','failed-runtime-r1'),('windows-runtime-r2','passed-runtime-r2')]:
 source=P/run_name;dest=C/'windows082'/folder;dest.mkdir(exist_ok=True)
 for name in ['result.json','failure.txt','native-saved-action-followup.log']:
  if (source/name).exists():shutil.copyfile(source/name,dest/name)
 for case in (source/'workflow-evidence').iterdir():
  if not case.is_dir():continue
  for name in ['result.json','plan.json','ui-result.json','ui-failure.json','ui.log','text-clipboard-comparison.json','text-clipboard-reply.json','actions-filtered-followup.png','actions-original-source.png','ui-failure.png']:
   if (case/name).exists():shutil.copyfile(case/name,dest/name)
source=P/'android117-source-package/core-ui-output'
if not source.exists():source=next((P/'android117-source-package').rglob('test_action_review_tools.log')).parent
shutil.copyfile(source/'test_action_review_tools.log',C/'android117/source-contract.log')
path=R/'docs/product_backlog.json';raw=path.read_bytes();d=json.loads(raw);quality=copy.deepcopy(d['quality_targets']);core=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104'];row=next(row for row in core['ownerCompetitiveParity20261105']['coverage'] if row['id']=='actions')
row['savedActionsFollowup20261110']=record
row['current']='Windows082/Android117 已交付并安装：已保存事项按负责人/完成/缺失信息/关键词筛选，长清单共用范围，当前筛选生成本地跟进文字并真实原生复制；完成/撤销/重开与原文入口已验。时间区间、独立可编辑材料、提醒和原完整竞品验收继续按原项，不自动关单。'
row['engineering'].update(status='PARTIAL_NOT_READY',label='已交付筛选与本地跟进文字；完整竞品条款待完成',readyForOwnerAcceptance=False,deliveredVersion='Windows0.1.82 / Android0.1.117')
row['engineering']['evidence'].append('docs/handoffs/20261110-actions-followup/batch.json') if 'docs/handoffs/20261110-actions-followup/batch.json' not in row['engineering']['evidence'] else None
candidate=core['ownerCoreAcceptanceCandidate20261109'];candidate['activeActionsFollowup20261110']=record;candidate['next']=record['next']
assert d['quality_targets']==quality and path.read_bytes()==raw
temp=path.with_suffix('.actions-finished.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,path)
timeline=R/'docs/development_log.md';entry=f'''\n\n## {at}｜已保存事项筛选与跟进文字双端交付20261110\n\n承接Owner“需要继续推进”。Windows0.1.82 / Android0.1.117现已安装，完成同一用户结果：已保存事项按负责人、完成、缺失信息和字面关键词筛选，当前筛选事项形成本地只读跟进文字，保留待核对、未知负责人/时间和已标记完成语义；原事项编辑仍是保存权威，原文入口与完成/撤销/重开持久化沿用原身份，不重排索引。Windows源e72d16ed941cb7070cc7bd6e8d21f3b830192254，正常构建42723975145、同MSI原生复验42726992295通过；复制后从真实Windows系统剪贴板读回，仅CRLF/LF表示不同，正文和范围完全相同，245份原资料文件一致。安卓源9b6b8858d36feb170a9347a56f57b0e0ee5980d2，远端42725482756，原6087901后端AAR/模型未改；更新前后1907份文件一致。实际公开会议21项、待核对20项，筛选/单项完成和撤销/重开/原文核对已过；复制104字符跟进文字，真实Ctrl+V进入未发送普通问题框完全一致，未注入接收正文。两份准确安装包上传既有私有草稿并下载读回SHA一致，未公开发布。\n\n真实返工保留：Android116原长清单折叠拆成4/17两套筛选，117修为全段共享单一范围、卡片内部折叠，筛选时显示全部匹配，补完整MinutesDocument组合保护。Windows首次原生42726625518仅剪贴板CRLF比较停止，保留失败、同包仅修检查器并读回两边原始哈希。手机原生确认框、异步勾选检查与后台无障碍接收控件问题分别保留；改用限定独立屏幕原生确认、等待实际保存再重开、普通键盘粘贴，未改业务结果。两次USB断连的自有虚拟屏幕证据保留；最终原有库已恢复、主屏指纹一致、自有显示/转发/临时UI驱动关闭，占用已释放。1905份原基线文件不变，另2份仅公开测试纪要与导航索引按预期变化，原有录音资料未改。\n\n本轮初实际RAM可用391340032B且低内存信号为真，未加载模型、未关闭其它应用；短暂恢复不当作模型质量进展。没有新ASR/AI请求、板卡操作、真人客户或模型/整机售卖合格。保留原严格5%目标与固定Qwen断点，完整竞品actions条款仍PARTIAL，时间区间、独立可编辑AI材料及提醒未由本批冒充完成。完成后已重读原候选下一项，沿固定完整实会/复杂多人及事实门，在实际资源允许时继续；已有082/117路径不重复重测。证据docs/handoffs/20261110-actions-followup/batch.json。\n'''
with timeline.open('a',encoding='utf8') as stream:stream.write(entry)
for p in [path,timeline]:shutil.copyfile(p,S/'docs'/p.name)
destination=S/'docs/handoffs/actions-followup20261110';destination.mkdir(exist_ok=True)
copied=[]
for source in C.rglob('*'):
 if source.is_file() and source.suffix.lower() in ['.py','.cjs','.java','.json','.png','.log','.txt'] and source.stat().st_size<3*1024*1024:
  target=destination/source.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);copied.append(source.relative_to(C).as_posix())
print(json.dumps({'state':record['state'],'windowsInstalled':'0.1.82','androidInstalled':'0.1.117','publicEvidenceFiles':len(copied),'phoneHoldReleased':not d['recorder_core']['speed_investigation_handoff']['endpointSelection']['ownerPhoneHold']['active'],'ownerAcceptanceUnchanged':True,'saleQualified':False,'next':record['next']},ensure_ascii=False))
