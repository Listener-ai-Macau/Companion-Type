from pathlib import Path
from datetime import datetime
import json,re,copy,hashlib,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';B=R/'docs/handoffs/20261112-product-closure/windows112';F=B.parent/'frontend112142';C=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/windows112');O=B/'engineering-self-acceptance';O.mkdir(exist_ok=False)
read=lambda p:json.loads(p.read_bytes())
write=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def put(src,name):
 target=O/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target)
at=datetime.now().astimezone().isoformat(timespec='seconds');fresh=read(C/'self-acceptance-r5/result.json');services=read(C/'self-acceptance-service-readiness/result.json');delivery=read(F/'software-delivery.json');assert fresh['state']=='INSTALLED112_FRESH_CONTINUOUS_SOFTWARE_AND_ACTUAL_PROCESS_RESTART_PASSED';assert delivery['privateRemoteReadbackVerified'] and delivery['individualWindowsMsiRemoteReadbackVerified'];assert services['settings']['localAsrAvailable'] and services['settings']['deepseekApiKeySet'] and not services['settings']['storageSaveBlocked']
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m'];stable=[];old_source='cdf2ea0ab1712f67b8c4bce5e7fe38b55a11afdb';new_source=fresh['appSourceCommit']
for path in ['apps/windows/src-tauri/src/backend/transcription.rs','apps/windows/src-tauri/src/backend/transcription','apps/windows/src-tauri/src/backend/minutes.rs','apps/windows/src-tauri/src/backend/minutes_context.rs','apps/windows/src-tauri/src/backend/product_settings.rs','apps/windows/src-tauri/src/backend/product_settings']:
 values=[subprocess.check_output(git+['rev-parse',ref+':'+path],cwd=S,text=True).strip()for ref in [old_source,new_source]];assert values[0]==values[1];stable.append(dict(path=path,priorObject=values[0],currentObject=values[1]))
for attempt in range(1,6):
 case=C/('self-acceptance-r'+str(attempt));put(case/'result.json',f'retained-attempts/r{attempt}/result.json');put(case/'runner.log',f'retained-attempts/r{attempt}/runner.log')
 record=read(case/'result.json')
 if record.get('nativeEvidence'):
  parent=Path(record['nativeEvidence']).parent
  for name in ['result.json','ui-result.json','ui-failure.json']:
   if (parent/name).exists():put(parent/name,f'retained-attempts/r{attempt}/native-'+name)
first=Path(fresh['completedContinuousJourneyEvidence']).parent;last=Path(fresh['nativeEvidence']).parent
for src,name in [(first/'self-acceptance-device-entry.png','device-entry.png'),(first/'product-date-only-calendar.png','date-only.png'),(last/'self-acceptance-after-process-restart.png','after-process-restart.png')]:put(src,name)
put(C/'self-acceptance-service-readiness/result.json','service-readiness.json')
result=dict(at=at,state='ENGINEERING_SOFTWARE_SELF_ACCEPTANCE_PASSED_OWNER_PHYSICAL_TOTAL_PENDING',windowsVersion='0.1.112',androidVersion='0.1.142',softwareSelfAcceptancePassed=True,installedPayloadMatchedInspectedMsi=True,appSourceCommit=new_source,continuousUiEvidence=fresh['completedContinuousJourneyEvidence'],actualProcessRestartEvidence=fresh['nativeEvidence'],deviceEntryHierarchyPassed=True,sourceFollowupSavePreviewPrivateExportAndDateOnlyPassed=True,actualNativeProcessExitAndRelaunchPassed=True,allPublicLibraryRowsUnchangedAfterRelaunch=True,normalNativeServiceReadiness=services['settings'],exactUnchangedModelAndSettingsObjects=stable,priorModelSource=old_source,modelInferenceNewlyRun=False,priorAndroid142EvidenceReused=True,nativeOsSaveCancelAndOrdinaryRecipientOn112NewlyTested=False,unchangedOsImplementationEvidence=str(B/'unchanged-os-handoff-evidence.json'),ownerPromptOpened=False,boardAccessed=False,ownerExperienceAccepted=False,physicalTotalAcceptancePassed=False,saleQualified=False,nativeBuildsThisReview=0,privateArchiveReadbackNowVerified=True,privateArchiveSha256=delivery['sha256'],retainedExecutionFailures=['r1 stopped on actual Windows low-memory signal (~0.8GB available); own job closed. Child CDP HTTP also reached inherited proxy502, fixed by child-only loopback NO_PROXY.','r2 complete native UI flow passed and real process exit/reopen occurred; new visible-reference assertion compared HTML whitespace with source LF. Exact persisted source retained; fix normalizes visible whitespace only.','r3 targeted reopen profile guard compared current output profile instead of explicitly reused prior private profile; bounded-job check retained.','r4 controller parse indentation error before any app launched; fixed and py_compile passed.','r5 only affected process-reopen phase resumed on the same r2 saved public library/profile; exact rows, visible reference, checklist and export scope passed.'],next='Read current embedded normal-firmware restoration and real lease. Bind final signed normal package to exact installed112, then one original shared guided Owner round. No physical prompt while the independent IMU/resource batch is in flight.')
write(O/'result.json',result)
P=R/'docs/product_backlog.json';raw=P.read_bytes();text=raw.decode('utf8');d=json.loads(text);m=d['owner_module_execution'];a=m['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109']['activeNonmodelCompletion20261110'];before=copy.deepcopy(a);c=a['ownerProductClosure20261112'];u=c['ownerUiUsabilityRework20261112'];entry=u['preOwnerEngineeringAcceptance20261112'];entry.update(result);entry['receipt']=str(O/'result.json');entry['completedAt']=at
u.update(updatedAt=at,state='WINDOWS112_ENGINEERING_SELF_ACCEPTED_OWNER_GUIDED_PHYSICAL_TOTAL_PENDING',privateRemoteReadbackVerified=True)
c.update(updatedAt=at,privateRemoteDeliveryReadbackMatched=True,ownerTotalStatus='ENGINEERING_SOFTWARE_SELF_ACCEPTED_WAITING_MATCHED_NORMAL_BOARD',frontendAcceptedPurposeClosed=False)
dep=c['physicalAcceptanceDependency'];dep.update(observedAt=at,latestReadOnlySharedBoardSnapshot=read(R/'docs/board_turn.json'),latestEmbeddedProgress='Original IMU thread has real UART output and is still shrinking no-display resource code/restoring normal firmware; no final restoration receipt matched here.',firmwareIdentityVerifiedByOriginalInstaller=False)
next_action='工程自行验收112的软件连续流程及真实进程重开已通过，服务就绪标记已核对，同包远端完整回读已恢复完成。等原IMU/资源批恢复最终正常固件并实际释放后，核对最终包/安装身份与112离线校验，在原一个窗口逐步带Owner做实卡整轮并最后集中反馈；未满足条件不提前弹窗，不把工程软件通过当实物或Owner体验通过。'
a.update(updatedAt=at,state='UI112142_SOFTWARE_SELF_ACCEPTED_PRIVATE_DELIVERED_OWNER_PHYSICAL_ROUND_PENDING',next=next_action,knownJobState='Engineering software round completed: no own GUI/build/model/device job active. Independent IMU/resource board lease remains active; final normal-firmware matching required. Same112142 archive and MSI private readback completed.',frontendAcceptedPurposeClosed=False)
a['deliveryExecution']['actualNativeDelivery'].update(state=a['state'],engineeringSoftwareSelfAcceptancePassed=True,ownerExperienceAccepted=False);a['deliveryExecution']['afterDelivery']=next_action
current=copy.deepcopy(m['currentBatch']);following=copy.deepcopy(m['nextBatch']);m['currentBatch'].update(at=at,state=a['state'],done='Windows112已装及原资料保持；本轮自行完成连续来源/跟进/导出/仅日期与真实进程退出重开，服务现有配置可用标记已核对。Android142未变范围复用；同一112142完整包及MSI已恢复私有远端完整回读。',remaining='Owner新版体验和当前实卡整轮未执行；原IMU/资源批仍持板，最终正常固件恢复/身份未匹配。当前自验未新跑模型、112 OS系统对话框/普通接收；相同实现既有范围保留。长录/模型质量/售卖仍未关闭。',next=next_action,ownerExperienceAccepted=False);m['nextBatch'].update(at=at,status='ENGINEERING_SOFTWARE_SELF_ACCEPTED_OWNER_GUIDED_PHYSICAL_ROUND_PENDING',next=next_action)
def splice(key,old,new):
 global text
 hits=[]
 for match in re.finditer(r'(?m)^([ \t]*)"'+re.escape(key)+r'":\s*',text):
  value,length=json.JSONDecoder().raw_decode(text[match.end():])
  if value==old:hits.append((match,length))
 assert len(hits)==1,(key,len(hits));match,length=hits[0];text=text[:match.end()]+json.dumps(new,ensure_ascii=False,indent=2).replace('\n','\r\n'+match.group(1))+text[match.end()+length:]
splice('activeNonmodelCompletion20261110',before,a);splice('currentBatch',current,m['currentBatch']);splice('nextBatch',following,m['nextBatch']);json.loads(text);assert P.read_bytes()==raw;P.write_bytes(text.encode('utf8'))
agent=R/'AGENTS.md';s=agent.read_text(encoding='utf-8-sig');assert '私有附件上传TLS失败待续，本地包已完整校验。' in s;s=s.replace('私有附件上传TLS失败待续，本地包已完整校验。','同一112/142包和MSI已恢复私有远端完整回读；Owner要求的工程软件自验及真实进程重开已通过，实卡整轮仍待当前正常固件/实际释放匹配。');agent.write_text(s,encoding='utf8')
failure=read(F/'retained-private-delivery-failure.json');failure.update(state='PRIOR_TLS_FAILURE_RETAINED_SAME_PACKAGE_DELIVERY_RECOVERED',recoveredAt=at,privateRemoteReadbackVerified=True,unchangedArchiveSha256=delivery['sha256'],networkRoutingChanged=False);write(F/'retained-private-delivery-failure.json',failure)
log=R/'docs/development_log.md';rawlog=log.read_bytes();oldlog=rawlog.decode('utf-8-sig');mark='<!-- self-acceptance112-before-owner20261112 -->';assert mark not in oldlog
note=f'''{mark}
## {at} — 先自行验收112软件，真实进程重开通过，同一交付包远端恢复；实卡轮尚未开始

Owner要求“接下来一步一步开始验收…你自己先验收一遍先，再叫我验收”，沿原UI反馈与原整轮待办接续。用当前已安装112的确切MSI载荷公开隔离实例自行连续操作，新增设备入口与次要区层级实际界面检查，保留纪要/原文引用、跟进保存/勾选、整篇及单条导出、仅日期保存；随后真的退出原生进程并重开同一公开库/资料。勾选、字面引用、所选导出及全库记录持久化均通过，明确超出此前仅page.reload范围；仍不是实卡、ASR/AI质量或112系统保存对话框/普通接收新通过。

执行失败原件保留：r1低内存真实告警时可用约0.8GB、96.8%，本任务私有job峰值约208MB，关闭仅自己的实例；Node本地CDP又遇继承代理502，后续仅子进程127/localhost/::1 NO_PROXY，不改系统/普通网站分流。r2连续软件步骤与第一次真实退出重开已执行，新增引用断言因HTML合并空白与原文LF差异失败，存储原文未变；只修可见空白比较，同时继续逐字核存储。r3续验沿原私有profile但检查器比较新输出目录，保留bounded-job身份条件修正；r4缩进语法在启动前失败，py_compile修正通过。r5只续受影响的同r2公开库进程重开，19:00:37通过，不重复构建/安装产品或已过连续步骤。12项原窗口生命周期检查通过，并加入未完成/错版本自验不能开启Owner轮的检查。

实际112原生只读服务标记：本地转写模型存在、DeepSeek凭据已配置、纪要启用、保存未阻断；空隔离库避免读取Owner原录音，密钥不输出，未发云请求/模型推理。109→112转写、纪要、设置六个文件/子树Git对象逐一完全一致，原相关证据复用，不把配置存在当新推理质量通过。Android142与未变OS交接继续复用原有效范围。

先前附件TLS故障现在有不同条件：uploads无授权HEAD恢复302后，原相同44MB包与MSI上传、完整下载回读通过；SHA仍{delivery['sha256']}，未重包、未重编译、未改网络规则。根据及失败历史已更新。

当前原IMU/资源批仍实际持板并收尾无屏资源与正常固件恢复，本任务0板访问/0主机MIC/0新Owner弹窗，不中断现场。工程软件自验通过与Owner新UI体验、当前实物长录/恢复、正式售卖分开。下一动作：{next_action}

'''
assert log.read_bytes()==rawlog;log.write_bytes((note+oldlog).encode('utf8'))
out=Path(__file__).resolve().parent.parent/'outputs';write(out/'Companion-112-self-acceptance.json',result)
print(json.dumps({key:result[key]for key in ['at','state','softwareSelfAcceptancePassed','actualNativeProcessExitAndRelaunchPassed','privateArchiveReadbackNowVerified','ownerPromptOpened','physicalTotalAcceptancePassed']},ensure_ascii=False))
