from pathlib import Path
from datetime import datetime
import json,hashlib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;O=C/'android126';P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone126');at=datetime.now().astimezone().isoformat(timespec='seconds')
checks={n:json.loads((O/(n+'.json')).read_text(encoding='utf-8')) for n in ['build-result','installation','source-visual-result','ordinary-library','original-library-restored','end-session','remote-candidate-backup']}
assert checks['remote-candidate-backup']['readbackByteIdentical'] and checks['end-session']['ownerOriginalContentByteIdentical']
def hashes(name):return {line.split(None,1)[1]:line.split(None,1)[0] for line in (P/name).read_text().splitlines() if line.strip()}
before=hashes('before-install.sha256');after=hashes('final-files.private.sha256');changed=[name for name,digest in before.items() if after.get(name)!=digest];added=[name for name in after if name not in before];prefix='files/companion-meetings-0a2cc0ac-149a-4688-8ff8-3180d987144a/'
assert all(name.startswith(prefix) for name in added);checks['end-session'].update(expectedIndexChange='files/companion-library-index.json' in changed,newFilesOnlyInAuthorizedPublicLibrary=len(added));(O/'end-session.json').write_text(json.dumps(checks['end-session'],indent=2)+'\n')
feedback=O/'customer-presale.md';assert feedback.exists();source=checks['build-result']['sourceCommit'];receipt='docs/handoffs/20261110-android-media-import/library126-iteration.json'
triage={'source':'docs/handoffs/20261110-android-media-import/android126/customer-presale.md','sha256':hashlib.sha256(feedback.read_bytes()).hexdigest(),'type':'FIRST_USE_AI_SIMULATED_PRE_SALE_NOT_REAL_CUSTOMER','purpose':'阅读保存纪要/转写，留下自己的阅读判断，再从库回找','actual':'读纪要/精简原文和3处需求命中；保存整场人工备注，离开重开后保留；按工程找到转写，按自己的备注词未找到；可逆改成内容标题。','benefit':'摘要/原文回找与人工内容来源区分有用；深色统一可读，能完成其自选目的。','remaining':['全部内容不含刚写备注','图片曾暂不可读，正常重入又恢复；当时没有工程请求日志，不能追改为确定同一根因','详情未开始播放时仍占一大块禁用播放控制，阅读首屏拥挤','确切空结论占位None captured未本地化','已保存质量疑点被列为待解问题，模型/纪要语义门仍开','短公开样例/未提供新录音AI、真实硬件、价格服务与长期条件不足，购买暂不判断'],'purchase':'保留兴趣，正式价格与套餐未知，不作购买承诺，无真人或付款','retainedUserWork':'只修改本轮公开库一条context备注文件并新增同一条录音可逆标题；其它原文件和公开原图/原音保持。'}
record={'at':at,'state':'ANDROID126_LIBRARY_HIERARCHY_DELIVERED_FIRST_USE_RELIABILITY_REPAIR_NEXT','sourceCommit':source,'ciRun':42781446935,'version':'0.1.126','checks':checks,'feedback':triage,'nativeBuilds':1,'modelsOrAiCalled':False,'saleQualified':False,'next':'集中127：消除WebView读取与桥线程同进程文件锁假失败；人工备注本机搜索/直接打开定位；图片明确重读和禁止缓存失败；闲置播放器收紧与精确空结论显示。归属同一阅读—留判断—再回找收益，不逐句重包重派。'}
(C/'library126-iteration.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=R/'docs/product_backlog.json';raw=p.read_bytes();d=json.loads(raw);core=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104'];b=core['ownerCoreAcceptanceCandidate20261109'];coverage=core['ownerCompetitiveParity20261105']['coverage'];premium=next(x for x in coverage if x['id']=='premium_ui')
premium['androidLibraryHierarchy20261110'].update(status='ANDROID126_INSTALLED_FIRST_USE_OBSERVED_REPAIR127_IN_PROGRESS',source=source,receipt=receipt,customer=triage)
for key,issue in [('search','人工备注未被全部内容查找包含，新建备注回找受阻；127补同源字面查找/来源标记及直接定位。'),('notes_images','顾客暂时图片失败后重入恢复；工程已确定性复现同进程生命周期锁冲突并修源头，127实际UI待验。')]:
 row=next(x for x in coverage if x['id']==key);row['android126CustomerIssue']={'at':at,'feedback':triage['source'],'issue':issue,'status':'REPAIR127_IN_PROGRESS','saleQualified':False}
b['activeAndroidLibraryReading20261110']={'at':at,'state':record['state'],'sourceCommit':source,'receipt':receipt,'feedback':triage['source'],'next':record['next'],'nativeBuilds126':1,'phoneSessionClosed':True,'ownerAcceptanceClosed':False}
b['currentCheckpoint']['phone']='Android126已实装并核原文件，首屏/搜索筛选/选择/回收站/导入取消普通真机通过；AI独立首次使用完成阅读/备注/回找，发现备注搜索、瞬时图片失败与详情密度。原库恢复、占用释放；127同批源码修复中。'
b['next']=record['next'];b['nonmodelSaleStatus20261110']['at']=at;b['nonmodelSaleStatus20261110']['openSoftware'][0]='Android127阅读—备注—回找同批可靠性修复及完整用户用途'
text=json.dumps(d,ensure_ascii=False,indent=2)+'\n';p.write_bytes(text.replace('\n','\r\n').encode('utf-8') if b'\r\n' in raw else text.encode('utf-8'))
log=R/'docs/development_log.md';old=log.read_text(encoding='utf-8-sig');marker='<!-- android-library126-first-use -->';assert marker not in old
entry=f'''{marker}
## {at} — Android126录音库首屏交付并自然首次使用，集中修阅读/备注回找

沿原premium_ui/organization，源码{source}、CI42781446935，一次原生包。已有录音时导入与资料位置紧凑显示，搜索/分类/列表前移，卡端录音入口、回收站及闲置接收记录后移；正在接收、可继续任务和错误仍前置，空库保留完整开始入口。修原label全局间距叠加。完整生产前端在360/393/430无横溢，最窄首条可见；实际手机391×869首条完整在605.48–701.06px，底栏799.44px，过滤/多选/回收站/普通系统选择取消通过。原始126包及模型/AAR校验、已信任签名，APK SHA72e361e2…，私有草稿asset730668172全包回读一致。

新无旧工程历史AI模拟售前自选“读清安排—留阅读备注—回找”，完整原话`{triage['source']}`。实际读保存纪要及精简转写，需求3处，保存不假关联时间的整场备注；按“工程”命中转写找回、重开备注保留，可逆命名。肯定内容回找、人工来源区分及深色可读；保留兴趣而不作购买承诺，价格/服务/实物/新录音AI和长会未提供，非真人。原人工预算样例最初令其谨慎，后来图片恢复可见且明确generated fixture后理解来源，没有把图片补充当录音事实。

全部回传统一承接：自己的备注词搜不到；图片曾暂不可读、正常重入恢复；大段闲置播放控制挤占阅读；None captured与业务问题/识别疑点混列。图片当时未取工程请求日志，不能追改确定根因。后续最小确定性JVM复现却发现同进程两个生命周期实例会在另线程持锁时立即抛OverlappingFileLockException，原生图片路由吞成404；应用内排队串行后复现、旧版本拒绝、回收/恢复、原图备份精确清除等受影响检查通过。不是加重试掩盖持续坏文件。接着127把此源头、备注搜索/来源直接定位、明确图片重读/no-store、闲置播放器与精确空结论显示集中交付，模型语义疑点另留原门，不逐句话重包。

126收尾恢复原库并关闭App/独立显示/CDP及本轮精确驱动临时文件，USB保持唤醒2。2084旧文件中2083相同，另1是授权公开库context；新增标题也只在同一公开库，所有旧库、原音和原图保留。收据`{receipt}`。未操作Owner主屏、实板、模型或在线AI。原整体非模型/服务/正式发布与实物门未关。

'''
log.write_text(entry+old,encoding='utf-8');print(json.dumps({'state':record['state'],'next':record['next']},ensure_ascii=False))
