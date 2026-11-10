from pathlib import Path
from datetime import datetime
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;O=C/'android125';at=datetime.now().astimezone().isoformat(timespec='seconds')
names=['build-result','installation','remote-candidate-backup','ordinary-organization','reopened','backup-content','restored-ui','restored-content','restored-purge','purge-content','note-error-feedback','original-library-restored','end-session','public-backup-remote']
checks={name:json.loads((O/(name+'.json')).read_text(encoding='utf-8')) for name in names}
assert checks['end-session']['ownerOriginalContentByteIdentical'] and checks['end-session']['ownAppDisplayForwardAndExactTemporaryFilesClosed']
assert checks['remote-candidate-backup']['readbackByteIdentical'] and checks['public-backup-remote']['sha256']==checks['backup-content']['backupSha256']
assert checks['restored-content']['byteIdentical']==39 and checks['purge-content']['sourceAndOwnerLibrariesUnchanged']
source=checks['build-result']['sourceCommit'];assert source=='cd66759a5a3bfef24ebb0764dcd7db69cc518048'
result={'at':at,'state':'ANDROID125_RECORDING_ORGANIZATION_SCOPED_DELIVERY_COMPLETE','version':'0.1.125','sourceCommit':source,'backendSource':'f55f8e83b77c10ca34db442971a045eca1acfdf4','ciRun':42773070743,'nativeBuilds':1,'nativeProductRework':0,'checks':checks,'modelsChangedOrRun':False,'aiServiceCalls':0,'ownerMainDisplayOperated':False,'saleQualified':False,'ownerAcceptanceClosed':False,'scope':'Offline folders, tags, selection, protected/reversible batch management, persistent metadata and exact library backup/purge integration.','limits':['Batch folder/tag edits publish one revisioned atomic metadata file; hidden/foreign/stale/over-limit targets reject before file publication.','Batch protection/trash prevalidates all identities; a later storage failure reports confirmed/pending targets and does not claim all-or-nothing filesystem writes. Permanent purge stays per recording with final native confirmation.','Only the authorized public test library and its new restored copy were modified. Original files and all previous libraries retained.','Precise native invalid-image feedback was checked via controlled UI activation and ordinary system picker. The input adapter stopped generating clicks in this note composer; this condition is retained, not called ordinary touch acceptance. Existing124 ordinary image entry is unchanged.','Actual dark/light first-screen capture showed import/library/status administration preceding the recordings; improve the library hierarchy next, with a usable source-library indicator retained.','Windows087 matched runtime/installed coherence, documents, non-destructive editing, cross-platform/service/release/customer and physical gates still follow the original backlog.']}
(C/'organization-delivered-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=R/'docs/product_backlog.json';raw=p.read_bytes();d=json.loads(raw);core=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104'];b=core['ownerCoreAcceptanceCandidate20261109'];coverage=core['ownerCompetitiveParity20261105']['coverage'];row=next(x for x in coverage if x['id']=='organization')
row['current']='Windows既有分类/筛选/批量路径保留；Android125实装新增文件夹/标签/多选，普通真机校验、保护与可恢复批量删除、39文件整库恢复和精确永久清除通过。双端完整用户验收仍开放。'
row['android125ScopedDelivery']={'version':'0.1.125','source':source,'receipt':'docs/handoffs/20261110-android-media-import/organization-delivered-result.json','nativePhoneManagementBackupLifecyclePassed':True,'ownerAccepted':False}
evidence=row['engineering']['evidence'];receipt='docs/handoffs/20261110-android-media-import/organization-delivered-result.json'
if receipt not in evidence:evidence.append(receipt)
b['activeRecordingOrganization20261110']={'at':at,'state':result['state'],'version':'0.1.125','sourceCommit':source,'receipt':receipt,'installed':True,'phoneSessionClosed':True,'ownerAcceptanceClosed':False,'saleQualified':False,'next':'沿原premium_ui集中修安卓录音库首屏：已有录音优先，导入/资料位置/状态和回收站入口收敛，原位置/失败/进度仍可访问；不重跑未受影响模型或实板。'}
b['currentCheckpoint']['phone']='Android125实装源'+source+'，分类/标签/多选、保护/可恢复批量删除、进程重开、整库恢复及精确清除已验；原库恢复并关闭测试显示。JNI/模型未变，普通图片错误入口本轮受输入适配器限制，受控UI单一明确错误已验。'
b['currentCheckpoint']['windows']='统一087源cff4250已由共享任务安装，实际EXE/DLL与本侧冻结MSI一致；本侧图文完整UI、备份/恢复/精确清除已通过同一匹配原生包，不重复安装或降级。'
premium=next(x for x in coverage if x['id']=='premium_ui');premium['androidLibraryHierarchy20261110']={'at':at,'evidence':['docs/handoffs/20261110-android-media-import/android125/organization-library-dark.png','docs/handoffs/20261110-android-media-import/android125/organization-library-light.png'],'finding':'真实首屏被导入卡/资料位置/闲置接收状态/回收站占据，实际录音与分类在下方；功能通过不等于一目了然。','decision':'沿原录音库布局集中修已有内容优先、紧凑导入/位置、真实进行中状态与维护入口，复用125保存/备份/清除，不加新模型。','status':'SOURCE_REFINEMENT_NEXT'}
state=b['nonmodelSaleStatus20261110'];state['at']=at;state['delivered']['android']='Android125分类/标签/批量管理与完整资料恢复清除已交付，原121/123/124能力保留。';state['openSoftware']=['Windows087统一候选收尾与安卓录音库首屏层级','文档导入和原跨端差异','非破坏剪辑、切分与合并','旧WinRT/具体客户端分享、实体换机及原其它软件门'];state['efficiencyEvidence']['recordingOrganization125']={'nativeBuilds':1,'nativeProductRework':0,'source':source,'ciRun':42773070743,'modelsRun':0,'result':'一批原生构建完成分类和管理的持久化/备份/精确生命周期；验证器纠正复用同一APK，输入适配限制不冒充产品通过。'}
b['next']='先收尾Windows087匹配图文候选并核对当前共享安装；同时沿原premium_ui收敛安卓录音库首屏，之后按原软件项继续，不等待Owner再说继续。'
text=json.dumps(d,ensure_ascii=False,indent=2)+'\n';p.write_bytes(text.replace('\n','\r\n').encode('utf-8') if b'\r\n' in raw else text.encode('utf-8'))
marker='<!-- android-recording-organization125-delivered -->';log=R/'docs/development_log.md';old=log.read_text(encoding='utf-8-sig');assert marker not in old
entry=f'''{marker}
## {at} — Android125文件夹、标签与所选录音管理整链交付，接续首屏可用性

沿Owner“完整修复打包提交、售卖标准后再找我”及原CP27-01/organization续作。Android125源{source}，CI42773070743，一次新原生包、原签名安装；后端f55f8e8/JNI/权重不变，无ASR、AI、录音、BLE或实板动作。多录音分类/标签采用同一有界校验封装与乐观版本文件，一次原子提交；归档为同一资料库原备份所收内容。选择范围、错库/旧版本、晚出现的标签超限拒绝整批写入；永久清除先核分类原件，再只移除目标条目，不改另一录音。批量保护/移入回收站先核全部身份，实际存储中断诚实保留完成/待确认范围，不伪称跨文件事务。

独立手机显示16、既有公开QA库4条普通导入媒体。普通界面选2条归入“公开验收/客户会议”、添加两标签，父文件夹/标签筛选通过；非法路径保留输入和选择且版本不动。保护2条后批量删除被正确拒绝；解除保护、批量入回收站及逐条恢复通过，另外2条不变。结束进程重开后组织信息保持。普通系统备份/恢复新公开库51a383b0…，39文件全部逐字节相同，含分类、原音、备注/图片；备份SHA05129b2d…。在新恢复库中经普通最终确认仅清一条WAV，变化13文件均属目标，另2082原有文件不变，另一录音分类和原音不变。只剩空同步锁属于原规划保留，不当内容泄漏。所有JVM/源码检查与真机工程范围分别保留。

125同时把备注的失败交回编辑器，避免页面和编辑器重复报错。后续图片错误检查的标准输入通道未生成DOM点击事件，保留实际观察和失败；通过既有UI按钮受控激活、普通系统图片选择核对单一明确错误、输入及两条原备注保留，不把该段写为新普通触控通过。系统选择器退后台时CDP不可连接亦保留为工具条件。验证器另纠正原UI驱动Java路径、实际MP3文件名、带datalist输入的combobox角色及精确清除的空锁判据，未追加APK/模型构建。

收尾恢复原库，2051个安装前文件中2050完全相同，另1为预期资料库索引；旧资料库全部保留，仅新增本轮公开恢复库。关闭本侧App/显示/CDP，按哈希仅移除本轮公开ZIP/无效PNG/驱动3件，USB唤醒值2不变、手机占用释放。APK和公开备份都在原私有草稿上传回读一致，未发布；详情`docs/handoffs/20261110-android-media-import/organization-delivered-result.json`。

实际深浅色首屏仍先显示导入/资料位置/闲置状态等管理卡，录音列表在下方。这是接着要修的真实层级问题，不能用数据功能完成冒充精致可售。Windows统一087已由共享任务安装，本侧已核对实际二进制与冻结MSI一致；084曾因检测到共享086而正确停止降级，087复用同一原生构建完成完整图文UI和生命周期验收。原文档导入、非破坏剪辑、跨端/服务/渠道、真实顾客和实物门仍开放。无整体完成百分比或“只剩模型”的虚关。

'''
log.write_text(entry+old,encoding='utf-8');print(json.dumps({'at':at,'state':result['state'],'next':b['next']},ensure_ascii=False))
