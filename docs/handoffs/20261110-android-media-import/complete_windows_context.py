from pathlib import Path
from datetime import datetime
import json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;O=C/'windows087';at=datetime.now().astimezone().isoformat(timespec='seconds')
checks={n:json.loads((O/(n+'.json')).read_text(encoding='utf-8')) for n in ['windows-verification','runtime-result','runtime-backend-result','installation','remote-candidate-backup']}
v=checks['windows-verification'];i=checks['installation'];rt=checks['runtime-result'];remote=checks['remote-candidate-backup']
assert v['sourceCommit']==rt['appSourceCommit']==i['sourceCommit']==remote['sourceCommit']=='cff425076be3c3c4ba8bfb2e6d1c8ba0a703520f'
assert rt['nativeUiExitCode']==rt['contextBackendExitCode']==0 and rt['sourceAudioUnchanged']
assert v['embeddedExeSha256']==i['installedExeSha256'] and v['dllSha256']==i['installedDllSha256']
assert remote['readbackByteIdentical'] and remote['msiSha256']==v['msiSha256'] and i['installedHelpStartupPassed']
result={'at':at,'state':'WINDOWS087_IMAGE_CONTEXT_SCOPED_DELIVERY_COMPLETE','version':'0.1.87','sourceCommit':v['sourceCommit'],'nativeCiRun':42772579089,'runtimeRun':rt['runtimeRun'],'checks':checks,'scope':['Original JPEG/PNG/WebP plus bounded aspect-preserving previews, captions and recording ownership','Direct current-playback position bookmark and note anchor, precise authored validation failures, draft/retry protection','Only-selected image context ZIP with exact originals and offline reading page','Packaged backup/restore, note edit/reopen, recycle restore and exact permanent image cleanup'],'existingInstallationReused':True,'nativeRecompiledForFinalRuntime':False,'modelsRun':False,'ownerForegroundOperated':False,'saleQualified':False,'limits':['Word/PDF/other text formats include captions and source position; original images are in the explicit context ZIP.','Shared installation preserved 245 prior files and passed current cold connection; this task verified installed native hashes without another installer or physical retest.','Earlier failed UI/verifier attempts083 and084 retained; their corrections did not replace production native bytes.','Original cross-platform, AI usage, formal signing/channel, real customer and physical gates remain open.']}
(C/'windows-context-delivered-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=R/'docs/product_backlog.json';raw=p.read_bytes();d=json.loads(raw);core=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104'];b=core['ownerCoreAcceptanceCandidate20261109'];coverage=core['ownerCompetitiveParity20261105']['coverage'];row=next(x for x in coverage if x['id']=='notes_images');receipt='docs/handoffs/20261110-android-media-import/windows-context-delivered-result.json'
row['current']='Android124/125图文备注既有真机链保留；Windows087统一安装源cff4250已匹配验证直接时间关联、原图/完整预览、编辑重开、所选图文ZIP、整库备份恢复及精确清除；原跨端互通、AI采用与完整用户验收仍开放。'
row['windows087ScopedDelivery']={'at':at,'source':v['sourceCommit'],'receipt':receipt,'installedNativeMatched':True,'runtimePassed':True,'ownerAccepted':False}
if receipt not in row['engineering']['evidence']:row['engineering']['evidence'].append(receipt)
b['activeWindowsImageContext20261110']={'at':at,'state':result['state'],'sourceCommit':v['sourceCommit'],'receipt':receipt,'installed':True,'sharedInstallationReused':True,'saleQualified':False}
b['currentCheckpoint']['windows']='Windows087统一候选源cff4250已安装；本侧实际EXE/DLL与冻结MSI逐字节一致，图文完整UI及备份/恢复/精确清除通过；复用共享安装及冷连接证据，不降级/重复安装或抢用录音卡。'
state=b['nonmodelSaleStatus20261110'];state['at']=at;state['delivered']['windows']='统一Windows087实装；直接时间关联、图文备注、所选图文ZIP及完整资料生命周期已通过匹配包。共享录音卡086修复包含在统一源，实际安装复用共享收据。'
state['openSoftware']=['安卓录音库首屏层级与完整用户用途','文档导入和原跨端差异','非破坏剪辑、切分与合并','旧WinRT/具体客户端分享、实体换机及原其它软件门']
b['next']='沿原premium_ui集中修安卓录音库首屏，让录音/搜索/分类优先、导入/资料位置紧凑且真实进度和错误可见；后续回读原待办推进下一完整软件项。'
out=json.dumps(d,ensure_ascii=False,indent=2)+'\n';p.write_bytes(out.replace('\n','\r\n').encode('utf-8') if b'\r\n' in raw else out.encode('utf-8'))
log=R/'docs/development_log.md';old=log.read_text(encoding='utf-8-sig');marker='<!-- windows-image-context087-delivered -->';assert marker not in old
entry=f'''{marker}
## {at} — Windows087统一候选图文备注完整链交付，复用共享安装

原notes_images项完整交付一批：JPEG/PNG/WebP原件、尺寸有界完整比例预览、说明编辑、直接关联当前回听位置、已保存时间点定位、错误/草稿/重试保护；所选图文ZIP包含准确原图、来源JSON和离线阅读页，Word/PDF等文字格式保留说明和时间。原音不变。083先实现原生并保留六次真实UI/验证器失败及修正；084集中修正直接入口、准确原生错误和预览。升级前发现共享086已安装，正确停止降级。最终复用共享087源cff425076be3c3c4ba8bfb2e6d1c8ba0a703520f、原生CI42772579089，既有录音卡连接修复和本侧图文源已统一，未重新编译同一核心。

匹配087 MSI实际运行CI42778070163通过公开会议原音的图片取消/无效/有效选择、编辑重开、12秒原音定位、深浅色完整预览、多图片保留说明、仅所选ZIP。真实打包后端备份/恢复图片与备注逐字节一致、回收站/恢复及精确永久清除通过。1240源码文件、263许可文件、升级身份核对通过。MSI SHA4c8c31cd1e365a603c62c199c2cc8f3dffd3d45104c88934649311852d929ab7，私有草稿asset730583012上传回读一致，未公开发布。

共享任务已在本机安装087并校验245既有文件，普通冷连接2869.109ms；本侧复用该实际安装，独立比较实际EXE/DLL与本批MSI哈希一致、只读help启动通过，没有再启动安装器、操作Owner前台或重复实板录音。完整收据`{receipt}`。本范围不替代原AI/跨端用途、实物、Owner/真人客户及正式渠道验收；整体售卖状态仍开放。接着集中修Android125实际截图所见录音库首屏层级，沿原最高优先级软件事项推进。

'''
log.write_text(entry+old,encoding='utf-8');print(json.dumps({'state':result['state'],'next':b['next']},ensure_ascii=False))
