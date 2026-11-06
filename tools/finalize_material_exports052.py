"""Record the actually installed batch, preserving all Owner acceptance states."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib, json, os, shutil, subprocess, zipfile

base = Path(__file__).parent
r = Path('C:/Users/Billy/Desktop/Denzic/Companion')
s = r / 'recovered-software050'
b = r / 'docs/handoffs/20261106-material-exports052'
now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
pin = 'e684fa73b3c14423c0f62cd961af6732470b3a02'
branch = 'work/material-exports052-20261106'
def read(path): return json.loads(path.read_text(encoding='utf8'))
def write(path, obj): path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
def git(*args):
    p = subprocess.run(['git', *args], cwd=s, capture_output=True, text=True, encoding='utf8', errors='replace')
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()
assert git('branch', '--show-current') == branch
assert git('rev-parse', 'HEAD') == pin
frozen = read(b/'source-frozen.json')
assert frozen['sourceCommit'] == pin and frozen['remoteVerified']
line_endings = []
for entry in frozen['sourceFiles']:
    actual = (s/entry['path']).read_bytes()
    actual_sha = hashlib.sha256(actual).hexdigest()
    if actual_sha == entry['sha256']: continue
    assert entry['path'] == 'apps/windows/src-tauri/Cargo.toml', entry['path']
    committed = subprocess.check_output(['git','show',pin+':'+entry['path']],cwd=s)
    assert hashlib.sha256(committed).hexdigest() == entry['sha256']
    assert actual.replace(b'\r\n',b'\n') == committed.replace(b'\r\n',b'\n')
    line_endings.append({'path':entry['path'],'frozenSha256':entry['sha256'],'workingSha256':actual_sha,
                         'normalizedContentIdentical':True,'difference':'CRLF versus LF only; retained working tree, no semantic source change'})
write(b/'post-build-source-check.json', {'at':now,'trackedFileCount':len(frozen['sourceFiles']),
      'exactShaMatched':len(frozen['sourceFiles'])-len(line_endings),'lineEndingOnlyDifferences':line_endings,
      'functionalSourceUnchanged':True})
up = read(b/'windows-upgrade/result.json')
ui = read(b/'installed-native-readonly-ui-result.json')
assert up['installerExitCode'] == 0 and up['dataManifestIdentical'] and up['existingDataFiles'] == 245
assert ui['state'] == 'ACTUAL_NATIVE_UI_ASSETS_LIGHT_DARK_AND_PROTECTED_SOURCES_PASSED'
schema = read(b/'packaged-format-check/openxml-schema.json')
assert len(schema) == 1 and schema[0]['errors'] == 0 and schema[0]['slides'] == 14
state = read(b/'state.json')
assert state['state'] == 'IMPLEMENTING_SAVED_MATERIAL_PPTX_AND_MINDMAP_PNG_EXPORTS'
state.update(
    at=now, state='WINDOWS052_INSTALLED_SAVED_MATERIAL_PPTX_PNG_VERIFIED_ACCEPTANCE_OPEN',
    sourceCommit=pin, remoteSourceVerified=True, installed=True, version='0.1.52',
    androidVersionUnchanged='050r2/code51', ownerAccepted=False, customerResult=None,
    installer=str(b/'Companion-Windows-0.1.52-演示材料与导图.msi'), msiSha256=up['msiSha256'],
    userOutcome='Windows按同一份已保存内容/材料选择，导出可编辑自动分页PPTX、完整导图PNG及可编辑mm；预览、复制与文件分享沿现有内容来源校验。',
    checks={
        'nativePreFinalRootBalance':'cargo-tests.json: 11 targeted tests on 26ea29d; final root-only correction independently tested',
        'finalTextLayout':'final-text-layout-tests.log', 'documents':'document-verification.json',
        'frozenReleaseActualFormats':'packaged-format-check/result.json',
        'actual14SlidePptxSchema':'packaged-format-check/openxml-schema.json',
        'msi':'windows-verification.json', 'upgrade':'windows-upgrade/result.json',
        'installedReadonlyUi':'installed-native-readonly-ui-result.json',
    },
    installedData={'existingFiles':245, 'sha256ManifestIdentical':True, 'privateManifestsLocalOnly':True},
    release={'finalSeconds':474.05, 'source':pin, 'jobs':1,
             'retainedCorrection':'release-visual-correction-stop.json: own pre-package build stopped to fix visually detected single-character root orphan'},
    boundaries=[
        '实际系统Save As窗口、分享选择器/接收应用本轮未操作；不称完整系统交互验收通过。',
        'PPTX经Microsoft Open XML SDK完整模式及几何检查；本机无PowerPoint/LibreOffice，未冒称在Office应用打开。',
        '这是已保存材料的格式转换，非AI智能填Word/Excel、AI生图或新事实生成。',
        'Android新PPTX/PNG尚未交付；完整双端对标、客户深用与Owner验收保持未完成。',
        '本轮无新模型推理/训练、板卡/手机I/O，不改原音或用户资料；系统剪贴板未触碰。',
        '导图长文在声明尺寸范围内完整输出，超出上限明确拒绝；未宣称无限长图。',
        'Windows053设备管理在另一个工作树推进；后续集成必须保留本批最终e684fa73的格式修复，不能仅沿早期a8d3b707冻结源。',
    ],
    remoteReceiptVerification=str(b/'remote-verification.json'),
)
write(b/'state.json', state)
write(b/'delivery-result.json', state)

# Field-level compare-and-swap: never replace another chat's entire task tree.
scope = {}
exec((base/'complete_accuracy_backend_batch_20261103.py').read_text(encoding='utf8').split('\nnow=')[0], scope)
rep, ins = scope['replace'], scope['insert']
fp = ['owner_module_execution','frontendWindowsMobile20261102']
frontend = scope['data']['owner_module_execution']['frontendWindowsMobile20261102']
assert frontend['ownerWindowsMaterialExports052']['branch'] == branch
rep(fp+['ownerWindowsMaterialExports052'], state)
rep(fp+['state'], 'WINDOWS052_INSTALLED_SAVED_MATERIAL_EXPORTS_PARTIAL_PARITY')
rep(fp+['result'], 'Windows0.1.52已装：已存材料可编辑分页PPTX、完整PNG与mm；实际原生输出/14页PPTX模式/8格式预览/深浅色通过，245原资料SHA不变。系统保存分享交互、Android新格式、AI填表及完整售卖验收保留。')
rep(fp+['next'], '参见owner_module_execution.nextBatch.next；053设备管理在另一个工作树，本批最终e684fa73须合入后续候选。')
owner = scope['data']['owner_module_execution']
if owner.get('currentBatch',{}).get('branch') == branch:
    rep(['owner_module_execution','currentBatch'], state)
np = ['owner_module_execution','nextBatch']
rep(np+['status'], 'DAY_WINDOWS052_DELIVERED_NONMODEL_CONTINUES_GPU_DEFERRED')
rep(np+['at'], now)
rep(np+['goal'], '沿原36项售卖标准推进；Windows052已交付，手机/系统交互/AI材料和真实使用范围继续收敛。模型待实际外置卡接回后按原整会指标验证。')
rep(np+['reference'], str(b/'state.json'))
rep(np+['next'], '052已交付：沿原25/17继续Android新格式、系统保存/分享真实接收及AI Word/Excel表样填充，按实际可执行条件集中完成；另一个工作树的053设备空间/选场/维护不在本侧重复实现，须合入052最终e684fa73修复。待实际接回6800XT，再以新control命名继续固定整会和独立评分；早上不等卡、不调查重启。')
rep(np+['modelDirection','executionDirective'], 'Owner明确早上无外置卡，本轮不运行GPU模型也不驻留等待；日间推进软件。接回后既有模型授权有效，沿已保护身份选卡和整会→评分入口继续。')
rep(np+['modelDirection','resumeCondition'], '实际接回外置RX6800XT且身份/资源适合后继续；不需重问授权，不以重启调查为先决，不回退内置780M推理。')
cp = fp+['ownerCoreDeliveryPriority20261104','ownerCompetitiveParity20261105','coverage']
coverage = frontend['ownerCoreDeliveryPriority20261104']['ownerCompetitiveParity20261105']['coverage']
assert len(coverage)==36 and all(x['ownerAcceptance']['status']=='PENDING' for x in coverage)
for index,row in enumerate(coverage):
    if row['id'] not in ['exports','mindmap']: continue
    rp = cp+[index]
    if row['id']=='exports':
        current='Android既有内容选择/SAF保存/复制/分享沿048r3历史实机范围保留，现版050r2。Windows052已安装，保留051内容与音频导出，新增已存材料可编辑自动分页PPTX、完整PNG；冻结原生14页PPTX/PNG、来源变更与删除拒绝、8格式实际预览、深浅色和245原资料SHA不变已验。实际Save As/分享接收、Android新格式、AI Word/Excel填表及全对标仍待。'
        label='Windows052新增PPTX/PNG已交付；安卓新格式、系统交互、AI填表与完整对标待完成'
    else:
        current='两端原导图保留；Windows052已安装完整PNG与可编辑mm导出，同一已保存内容结构、中文/英文换行、尺寸上限明确拒绝。原生1352×5900 PNG内容与图形已验；长图交互/正文定位、Android新格式、客户使用及全项资格未关闭。'
        label='Windows052完整PNG与可编辑mm已交付；长图交互及安卓完整范围待完成'
    rep(rp+['current'], current)
    rep(rp+['engineering','status'], 'PARTIAL_DELIVERED')
    rep(rp+['engineering','label'], label)
    rep(rp+['engineering','deliveredVersion'], 'Windows0.1.52 / Android050r2 code51 unchanged')
    rep(rp+['engineering','evidence'], row['engineering']['evidence']+[str(b/'state.json')])
    ins(rp+['engineering'], 'windowsMaterialExports052', {
        'state':state['state'], 'receipt':str(b/'state.json'), 'sourceCommit':pin,
        'installed':True, 'readySubscope':'Windows已保存内容PPTX/PNG/mm格式导出',
        'ownerAccepted':False, 'fullParityQualified':False, 'customerResult':None,
    })
updated = json.loads(scope['text'])
rows = updated['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCompetitiveParity20261105']['coverage']
assert len(rows)==36 and all(x['ownerAcceptance']==y['ownerAcceptance'] for x,y in zip(coverage,rows))
assert scope['p'].read_bytes()==scope['original'], 'Canonical task changed concurrently; reread before writing'
scope['p'].write_bytes(scope['text'].encode('utf8'))

entry=f'''## {now}｜白天无独显：Windows052已安装，已存材料PPTX/PNG交付，原资料保持

沿08:33原25/17批次，Owner“早上没有显卡的”按资源安排承接，不新增等待/重启调查，不跑GPU、训练、手机或板卡I/O。Windows0.1.52从已验证051续作：同一已保存内容与逐条材料选择，PPTX原生可编辑文字/16:9/自动分页并保留免责声明和出处；PNG沿相同导图层级、本机隔离无GPU浏览器渲染，中英文换行、全部节点及尺寸上限明确拒绝；mm识别材料中的引用标题。渲染后、落盘前再核来源，过期/已删除材料拒绝输出。不是AI填表/生图或模型质量提升。冻结源码{pin}已推work/material-exports052-20261106并读回，平台6f30ab58不变；1086项文件最终核对中1085项SHA完全一致，Cargo.toml工作区为LF而冻结Git源为CRLF，标准化后内容完全相同；保留既有工作区和独立差异收据，不称逐字节同源、也不因此重复未受影响构建。

11项受影响原生测试在26ea29d通过（165.16秒），3组UI检查通过；视觉发现导图根节点单字孤行，保留未发布26ea及停止收据，在打包前停止自有构建修正。最终e684根布局单独测试通过，单作业release474.05秒；最终实际原生EXE用隔离虚构材料导出14页PPTX、1352×5900 PNG/mm并核全部文字/引文、未选内容排除、源变更/删除拒绝。Microsoft Open XML SDK对实际14页PPTX零模式错误，几何检查无越界；无PowerPoint/LibreOffice，几何预览不冒称Office应用打开。16项文档检查及原051受影响格式回归保留，最终原生8格式预览/同源资源/深浅色/受保护源字段通过。无关路径不重跑。

MSI SHA{up['msiSha256']}，许可资源256项/相同升级身份/防降级/包内EXE和DLL对应验证通过。{up['startedAt']}至{up['finishedAt']}静默升级exit0，245原资料文件SHA完整一致，安装后独立隐藏实例再次核8格式预览与深浅色通过，剪贴板未触碰、未激活Owner前台。原数据备份/路径清单仅本机不入Git。安装及证据docs/handoffs/20261106-material-exports052；源码/安全收据和唯一任务树/时间线不可变快照随同远端保护，读回见该目录remote-verification.json。

仍未完成：真实Save As/系统分享接收、PowerPoint应用实开、Android新格式、AI Word/Excel表样填充、普通客户完整目的体验与Owner36项PENDING。另一个工作树053设备管理正推进，下一候选须保留本批最终e684格式修复，不覆盖其固件/在途源码。最终整会新成绩仍无；实际接回6800XT后沿已保护的新control整会→独立评分入口继续，不用旧单场3.61%概括通用达标。下一步沿原nextBatch.next续作，不把本次打包、日志和验证数量算新功能。

'''
log=r/'docs/development_log.md'
before=log.read_bytes()
assert '白天无独显：Windows052已安装'.encode('utf8') not in before
# A new result at the front makes the current stage visible without rewriting history.
assert log.read_bytes()==before
log.write_bytes(entry.encode('utf8')+before)
render=subprocess.run([os.sys.executable,'tools/render_product_backlog.py','--docs-only'],cwd=r,capture_output=True,text=True,encoding='utf8',errors='replace')
assert render.returncode==0,render.stderr

# Only explicitly safe, synthetic/test receipts are copied. No app-data backup or manifests.
dest=s/'docs/handoffs/20261106-material-exports052';dest.mkdir(parents=True,exist_ok=False)
safe=['state.json','delivery-result.json','source-frozen.json','post-build-source-check.json','cargo-check.json','cargo-tests.json','cargo-release.json',
      'document-verification.json','openxml-schema-first.json','windows-verification.json',
      'installed-native-readonly-ui-result.json','native-readonly-ui-result.json',
      'release-visual-correction-stop.json','final-text-layout-tests.log']
for name in safe:shutil.copy2(b/name,dest/name)
shutil.copy2(b/'windows-upgrade/result.json',dest/'upgrade-result-safe.json')
samples=dest/'public-format-samples';samples.mkdir()
for name in ['result.json','openxml-schema.json','saved-material.pptx','saved-material.png','saved-material.mm']:
    shutil.copy2(b/'packaged-format-check'/name,samples/name)
ui_path=Path(ui['evidence'])
for name in ['ui-result.json','native-light.png','native-dark.png']:
    shutil.copy2(ui_path/name,dest/name)
(dest/'README.md').write_text('''# Windows 0.1.52 saved-material exports

Functional source: e684fa73b3c14423c0f62cd961af6732470b3a02, branch work/material-exports052-20261106. Frozen source/production web assets in source-frozen.json. Installed payload and unchanged 245 existing app-data files verified by the safe upgrade receipt. Actual installed executable was exercised in an isolated, hidden public-fixture library; no Owner clipboard, model or hardware I/O.

PPTX is editable and paginated from the selected saved text; PNG/MM preserve the selected outline. Public samples are synthetic stress fixtures, not transcription accuracy or customer-use evidence. The 14-slide exported PPTX passed Microsoft Open XML SDK schema validation. Structural/geometry checks and previews do not mean PowerPoint or LibreOffice application testing; neither is installed here.

Native tests predate the final root-only balancing change: 11 checks on 26ea29d, then final layout unit checks and actual frozen-release outputs on e684fa73. The stopped pre-package build is preserved. All 36 Owner acceptance rows remain PENDING. Actual Windows Save As/share recipient, Android new formats, AI template field filling and customer experience remain open.

The canonical live task and complete timeline remain only in the Companion project docs. The ZIP here is an immutable historical backup, not a second execution tree. Do not upload local windows-upgrade/data-before or data-after manifests, installed-before files, recordings, session database or private backups. The following 053 device-management branch must integrate e684fa73 final format fixes before delivery.
''',encoding='utf8')
with zipfile.ZipFile(dest/'canonical-task-history-20261106-delivery.zip','w',zipfile.ZIP_DEFLATED,compresslevel=7) as archive:
    for name in ['docs/product_backlog.json','docs/development_log.md','docs/PRODUCT_BACKLOG.md']:
        archive.write(r/name,name)
for name in ['test_installed_windows052_readonly.py','test_windows052_native_readonly.py','windows052_native_gui.cjs',
             'verify_exports052_documents.py','check_packaged_exports052.py','render_pptx_geometry052.py','capture_pptx_geometry052.cjs']:
    target=s/'tools'/name
    assert not target.exists(),target
    shutil.copy2(base/name,target)
print(json.dumps({'at':now,'state':state['state'],'safeReceiptDirectory':str(dest),'canonicalOwnerRows':len(rows),'render':render.stdout.strip()},ensure_ascii=False))
