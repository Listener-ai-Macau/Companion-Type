from pathlib import Path
from datetime import datetime
import json,os
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;p=R/'docs/product_backlog.json';raw=p.read_bytes();d=json.loads(raw);now=datetime.now().astimezone().isoformat(timespec='seconds');core=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104'];b=core['ownerCoreAcceptanceCandidate20261109'];source=json.loads((C/'candidate-source.json').read_text());embedded=d['owner_module_execution']['embedded']
b['latestOwnerContinuation']={'at':now,'quote':'除了模型以外的东西，都要达到售卖标准；加快开发效率，现在太慢了。','decision':'保持所有原非模型售卖/竞品范围。当前完整批次交付安卓文件导入到既有会议处理、保存和恢复链；同链路收敛后一次打包/真机验收，保留已有121交付。','workpoint':'ownerCoreAcceptanceCandidate20261109.activeAndroidMediaImport20261110'}
b['activeAndroidMediaImport20261110']={'at':now,'state':'SOURCE_JAVA_AND_STORAGE_WORKFLOW_PASSED_NATIVE_CANDIDATE_CI_RUNNING','userOutcome':'手机普通音视频通过系统选择器导入，保留原文件，解码后可沿用回听、转写、纪要、导出、备份和回收站。','existingTask':'CP27-01/import','sourceRoot':str(R/'companion-core-android20261109'),'source':source,'buildRun':42748629840,'backendNativeAndModelBinariesChanged':False,'softwareTests':['原文件/分段校验、失败不发布','相同时间轴/转写时间来源绑定','实际LibraryBackup保存恢复','回收站恢复、精确删除后无损坏空目录','其它录音保留、损坏音频不改原文件','重采样不依赖编解码包边界、抗混叠与立体声反相'],'runtimeQualified':False,'ownerDataUsed':False,'modelsTrained':False,'next':'原生候选通过后同签名安装，在已授权手机独立显示用真实公开音视频跑导入/后台/取消/原文件校验与完整处理交付链。'}
b['next']=b['activeAndroidMediaImport20261110']['next']
for block in b['remainingSaleBlocks']:
 if block['block']=='双端与实卡同一候选':block['facts']='Windows082与Android121均已实际安装；Android公开完整会议ASR/纪要/翻译/导出和121回听/校对/设置/公开备份恢复已过对应范围，原私有内容保持。当前固件与实卡长录/普通手机接收/异常恢复仍须按匹配版本验收；旧WinRT及具体聊天客户端不继承标准浏览器附件通过。'
 if block['block']=='长录/连接/异常恢复可靠性':block['facts']='最新共享嵌软记录'+embedded['updatedAt']+'，正常固件'+str(embedded['baseline']['firmwareVersion'])+'。其安装与明确已验范围只按原收据，长录、实物唤醒、电源与原未通过指标不继承关闭；本侧不抢板卡或手机中央设备。'
for title,facts,exit in [('非模型软件完整性','安卓普通文件导入正在整批交付；图片/时间备注、分类批量、剪辑合并及双端差异沿原coverage保留。','原规定功能有普通入口、保存/取消/失败/恢复和对应实际验收。'),('正式发布与服务边界','正式签名/分发、许可/隐私、支持/费用、账号跨端/团队及第三方服务等完整原对标仍开放；工程候选和AI模拟不代替售卖资格。','按真实发布身份、服务条件与原对标逐项完成，不虚构权益或资质。'),('完整用户验收','已交付局部流程和工程验证不能替代客户围绕完整会议目的使用；本批未新派顾客。','完成可用整批后沿原客户流程承接实际收益、困惑与错误，工程解决真实阻断。')]:
 if not any(x['block']==title for x in b['remainingSaleBlocks']):b['remainingSaleBlocks'].append({'block':title,'state':'OPEN','facts':facts,'exit':exit})
for row in core['ownerCompetitiveParity20261105']['coverage']:
 if row['id']=='import':row['current']='Windows既有导入保留；Android122源码已接系统音视频选择、原文件完整保存、后台可取消解码和统一会议/备份/精确删除链，Java和实际存储联动通过，原生包与真机尚待，不计交付。';row['currentImportWorkpoint']='ownerCoreAcceptanceCandidate20261109.activeAndroidMediaImport20261110'
 if row['id']=='trash':row['current']='Android121实际公开录音回收站恢复和永久清除、续听元数据精确归属已验。122导入文件归属、移除空目录和其它录音保留源码联动通过，真机随本批待验。Windows原保护/回收站保留。'
 if row['id']=='backup':row['current']='Windows原备份保留；Android121实际公开整库备份恢复、原音/转写/纪要/译文/材料/续听保持通过。122外部原文件和无损语音分段的真实备份类兼容检查过，真机待验；实体换机/双端互通仍未覆盖。'
 if row['id']=='updates':row['current']='Windows082与Android121已实际同身份更新，原资料核验保持；源码和私有草稿包已远端回读。固件OTA按embedded原收据；正式售卖签名/渠道、最新实卡匹配和原未验恢复范围保留。'
temp=p.with_suffix('.sale-import.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');assert p.read_bytes()==raw;os.replace(temp,p);print('Original sale scope/current delivery corrected; active import batch recorded. No overall percentage or sale pass invented.')
